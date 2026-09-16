"""
Super Admin API Router — Dedicated endpoints for Super Admin operations,
GMF test validation runs, audit reports, and pipeline verification.
Guarded by require_super_admin.
"""
import os
import json
import logging
import threading
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.auth.dependencies import require_super_admin
from app.auth.schemas import UserOut
from app.db.base import SessionLocal
from app.db.models import GmfTestRun, GmfTestRunStatus, GmfUpload
from app.billing.super_admin_service import (
    sample_gmf_uploads,
    run_gmf_validation_test_suite,
    is_eligible_invoice_file,
    render_single_invoice_pdf,
    execute_system_reset,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/super-admin", tags=["super-admin"])


# ── Pydantic Schemas ─────────────────────────────────────────────────────────

class GmfTestRunSummaryOut(BaseModel):
    id: int
    status: str
    triggered_by: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    total_files_sampled: int
    total_invoices_tested: int
    passed_count: int
    failed_count: int
    has_report_pdf: bool = False
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class GmfTestRunDetailOut(GmfTestRunSummaryOut):
    results: List[Dict[str, Any]] = []


class SuperAdminOverviewOut(BaseModel):
    total_uploads_in_system: int
    eligible_invoice_gmfs_count: int
    latest_run: Optional[GmfTestRunSummaryOut] = None


# ── Background Worker Helper ─────────────────────────────────────────────────

def _run_test_in_background(run_id: int, triggered_by: str, max_files: int):
    """Executes the test suite in an isolated DB session within a background thread."""
    db: Session = SessionLocal()
    try:
        test_run = db.query(GmfTestRun).filter(GmfTestRun.id == run_id).first()
        if not test_run:
            logger.error(f"GmfTestRun #{run_id} not found in background worker.")
            return

        sampled = sample_gmf_uploads(db, max_files=max_files)
        test_run.total_files_sampled = len(sampled)
        db.commit()

        # Import splitter and validator
        from core.gmf_splitter import split_gmf_documents
        from app.billing.super_admin_service import (
            validate_single_document,
            generate_validation_pdf_report,
        )
        from decimal import Decimal
        import tempfile

        all_results = []
        passed = 0
        failed = 0

        for upload_id, filename, file_path in sampled:
            try:
                doc_paths = split_gmf_documents(file_path, original_filename=filename)
                if not doc_paths:
                    doc_paths = [file_path]

                with tempfile.TemporaryDirectory(prefix="gmf_split_docs_") as split_dir:
                    for doc_idx, dpath in enumerate(doc_paths, start=1):
                        doc_res = validate_single_document(
                            doc_path=dpath,
                            source_filename=filename,
                            doc_index=doc_idx,
                        )
                        doc_res_json = dict(doc_res)
                        doc_res_json["gmf_calculated_total"] = float(doc_res["gmf_calculated_total"])
                        doc_res_json["gmf_charges_tag"] = float(doc_res["gmf_charges_tag"]) if doc_res["gmf_charges_tag"] is not None else None
                        doc_res_json["pdf_total_charges"] = float(doc_res["pdf_total_charges"]) if doc_res["pdf_total_charges"] is not None else None
                        doc_res_json["pdf_details_total"] = float(doc_res["pdf_details_total"])

                        all_results.append(doc_res_json)
                        if doc_res["status"] == "PASS":
                            passed += 1
                        else:
                            failed += 1

                # Incremental commit so UI can track progress live
                test_run.total_invoices_tested = len(all_results)
                test_run.passed_count = passed
                test_run.failed_count = failed
                test_run.results_json = json.dumps(all_results)
                db.commit()

            except Exception as e:
                logger.error(f"Error validating file {filename}: {e}", exc_info=True)
                all_results.append({
                    "filename": filename,
                    "doc_index": 1,
                    "template_id": "error",
                    "account_number": "N/A",
                    "invoice_number": "N/A",
                    "gmf_calculated_total": 0.0,
                    "gmf_charges_tag": None,
                    "pdf_total_charges": None,
                    "pdf_details_total": 0.0,
                    "gmf_line_items_count": 0,
                    "pdf_line_items_count": 0,
                    "status": "FAIL",
                    "mismatch_details": f"File processing exception: {str(e)}",
                    "details_summary": [],
                })
                failed += 1
                test_run.total_invoices_tested = len(all_results)
                test_run.passed_count = passed
                test_run.failed_count = failed
                test_run.results_json = json.dumps(all_results)
                db.commit()

        test_run.total_invoices_tested = len(all_results)
        test_run.passed_count = passed
        test_run.failed_count = failed
        test_run.results_json = json.dumps(all_results)
        test_run.finished_at = datetime.utcnow()
        test_run.status = GmfTestRunStatus.COMPLETED

        # Generate official PDF Report
        reports_dir = os.path.abspath("./output/super_admin_reports")
        report_filename = f"GMF_Validation_Report_Run_{test_run.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        report_path = os.path.join(reports_dir, report_filename)

        report_results = []
        for r in all_results:
            rr = dict(r)
            rr["gmf_calculated_total"] = Decimal(str(r["gmf_calculated_total"]))
            rr["gmf_charges_tag"] = Decimal(str(r["gmf_charges_tag"])) if r["gmf_charges_tag"] is not None else None
            rr["pdf_total_charges"] = Decimal(str(r["pdf_total_charges"])) if r["pdf_total_charges"] is not None else None
            report_results.append(rr)

        generate_validation_pdf_report(test_run, report_results, report_path)
        test_run.report_pdf_path = report_path
        db.commit()
        logger.info(f"GmfTestRun #{run_id} completed successfully. Report saved at {report_path}")

    except Exception as e:
        logger.error(f"GmfTestRun #{run_id} crashed: {e}", exc_info=True)
        test_run = db.query(GmfTestRun).filter(GmfTestRun.id == run_id).first()
        if test_run:
            test_run.status = GmfTestRunStatus.FAILED
            test_run.error_message = str(e)
            test_run.finished_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()


# ── Router Endpoints ─────────────────────────────────────────────────────────

@router.get("/overview", response_model=SuperAdminOverviewOut)
def get_super_admin_overview(
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(require_super_admin),
):
    """Returns overview KPI metrics for the Super Admin console."""
    total_uploads = db.query(GmfUpload).count()
    all_uploads = db.query(GmfUpload.filename, GmfUpload.template_detected).all()
    eligible_count = sum(1 for u in all_uploads if is_eligible_invoice_file(u[0], u[1]))

    latest_run = (
        db.query(GmfTestRun)
        .order_by(GmfTestRun.started_at.desc())
        .first()
    )

    latest_out = None
    if latest_run:
        latest_out = GmfTestRunSummaryOut(
            id=latest_run.id,
            status=latest_run.status.value,
            triggered_by=latest_run.triggered_by,
            started_at=latest_run.started_at,
            finished_at=latest_run.finished_at,
            total_files_sampled=latest_run.total_files_sampled,
            total_invoices_tested=latest_run.total_invoices_tested,
            passed_count=latest_run.passed_count,
            failed_count=latest_run.failed_count,
            has_report_pdf=bool(latest_run.report_pdf_path and os.path.exists(latest_run.report_pdf_path)),
            error_message=latest_run.error_message,
        )

    return SuperAdminOverviewOut(
        total_uploads_in_system=total_uploads,
        eligible_invoice_gmfs_count=eligible_count,
        latest_run=latest_out,
    )


@router.post("/gmf-test/run", response_model=GmfTestRunSummaryOut)
def start_gmf_test_run(
    max_files: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(require_super_admin),
):
    """
    Triggers a GMF validation test run on up to max_files (default 100).
    Runs asynchronously in the background so the HTTP request returns immediately.
    """
    # Check if a run is already actively running
    active_run = (
        db.query(GmfTestRun)
        .filter(GmfTestRun.status == GmfTestRunStatus.RUNNING)
        .first()
    )
    if active_run:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A test run (#{active_run.id}) is already currently in progress.",
        )

    test_run = GmfTestRun(
        status=GmfTestRunStatus.RUNNING,
        triggered_by=current_user.email,
        started_at=datetime.utcnow(),
    )
    db.add(test_run)
    db.commit()
    db.refresh(test_run)

    # Spawn background thread for asynchronous execution
    t = threading.Thread(
        target=_run_test_in_background,
        args=(test_run.id, current_user.email, max_files),
        daemon=True,
    )
    t.start()

    return GmfTestRunSummaryOut(
        id=test_run.id,
        status=test_run.status.value,
        triggered_by=test_run.triggered_by,
        started_at=test_run.started_at,
        finished_at=test_run.finished_at,
        total_files_sampled=test_run.total_files_sampled,
        total_invoices_tested=test_run.total_invoices_tested,
        passed_count=test_run.passed_count,
        failed_count=test_run.failed_count,
        has_report_pdf=False,
        error_message=None,
    )


@router.get("/gmf-test/status", response_model=Optional[GmfTestRunSummaryOut])
def get_current_test_status(
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(require_super_admin),
):
    """Returns the most recent test run status and live progress counters."""
    latest = (
        db.query(GmfTestRun)
        .order_by(GmfTestRun.started_at.desc())
        .first()
    )
    if not latest:
        return None

    return GmfTestRunSummaryOut(
        id=latest.id,
        status=latest.status.value,
        triggered_by=latest.triggered_by,
        started_at=latest.started_at,
        finished_at=latest.finished_at,
        total_files_sampled=latest.total_files_sampled,
        total_invoices_tested=latest.total_invoices_tested,
        passed_count=latest.passed_count,
        failed_count=latest.failed_count,
        has_report_pdf=bool(latest.report_pdf_path and os.path.exists(latest.report_pdf_path)),
        error_message=latest.error_message,
    )


@router.get("/gmf-test/runs", response_model=List[GmfTestRunSummaryOut])
def list_test_runs(
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(require_super_admin),
):
    """Returns historical validation test runs."""
    runs = (
        db.query(GmfTestRun)
        .order_by(GmfTestRun.started_at.desc())
        .limit(50)
        .all()
    )
    return [
        GmfTestRunSummaryOut(
            id=r.id,
            status=r.status.value,
            triggered_by=r.triggered_by,
            started_at=r.started_at,
            finished_at=r.finished_at,
            total_files_sampled=r.total_files_sampled,
            total_invoices_tested=r.total_invoices_tested,
            passed_count=r.passed_count,
            failed_count=r.failed_count,
            has_report_pdf=bool(r.report_pdf_path and os.path.exists(r.report_pdf_path)),
            error_message=r.error_message,
        )
        for r in runs
    ]


@router.get("/gmf-test/runs/{run_id}", response_model=GmfTestRunDetailOut)
def get_test_run_details(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(require_super_admin),
):
    """Returns detailed results and invoice line items for a specific validation run."""
    run = db.query(GmfTestRun).filter(GmfTestRun.id == run_id).first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test run #{run_id} not found.",
        )

    parsed_results = []
    if run.results_json:
        try:
            parsed_results = json.loads(run.results_json)
        except Exception:
            parsed_results = []

    return GmfTestRunDetailOut(
        id=run.id,
        status=run.status.value,
        triggered_by=run.triggered_by,
        started_at=run.started_at,
        finished_at=run.finished_at,
        total_files_sampled=run.total_files_sampled,
        total_invoices_tested=run.total_invoices_tested,
        passed_count=run.passed_count,
        failed_count=run.failed_count,
        has_report_pdf=bool(run.report_pdf_path and os.path.exists(run.report_pdf_path)),
        error_message=run.error_message,
        results=parsed_results,
    )


@router.get("/gmf-test/runs/{run_id}/report-pdf")
def download_test_report_pdf(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(require_super_admin),
):
    """Downloads the generated PDF report for a completed test run."""
    run = db.query(GmfTestRun).filter(GmfTestRun.id == run_id).first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test run #{run_id} not found.",
        )

    if not run.report_pdf_path or not os.path.exists(run.report_pdf_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF test report is not available for this run.",
        )

    filename = os.path.basename(run.report_pdf_path)
    return FileResponse(
        path=run.report_pdf_path,
        media_type="application/pdf",
        filename=filename,
    )


@router.get("/gmf-test/invoice-pdf")
def view_single_invoice_pdf(
    filename: str = Query(..., description="GMF filename"),
    doc_index: int = Query(1, description="1-indexed invoice document index inside GMF"),
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(require_super_admin),
):
    """
    Renders and streams the generated PDF for any individual invoice document
    within a tested GMF file so Super Admin can inspect or download it.
    """
    pdf_bytes = render_single_invoice_pdf(db=db, filename=filename, doc_index=doc_index)
    if not pdf_bytes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Could not render PDF for {filename} (Document #{doc_index}).",
        )

    clean_name = filename.replace(".txt", "").replace(".gmf", "")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{clean_name}_doc_{doc_index}.pdf"',
        },
    )


@router.post("/reset-test-data")
def reset_system_test_data(
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(require_super_admin),
):
    """
    Completely wipes all transaction history, uploaded GMFs, generated PDFs,
    billing runs, and Super Admin test records.
    Retains Users, Base Templates, and System Settings intact.
    """
    try:
        res = execute_system_reset(db)
        return res
    except Exception as e:
        logger.error(f"Failed to reset system test data: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"System reset failed: {str(e)}",
        )


