"""
Main billing router — all endpoints for the admin dashboard.
Calls SmartAI_Bill functions for PDF generation (never reimplements them).
"""
import os
import sys
import shutil
import json
import tempfile
import logging
from typing import List, Optional
from pathlib import Path
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import func, or_, and_
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.api.deps import get_db
from app.auth.dependencies import require_admin, require_admin1_or_admin
from app.auth.schemas import UserOut
from app.db.models import (
    GmfUpload, GmfUploadStatus,
    BillingRun, BillingRunItem, BillingRunFailure, BillingRunApproval,
    RunStatus, BillingSchedule, BillingScheduleMode,
    NotificationEvent, NotificationEventType,
    InvoiceTemplate, TemplateApprovalStatus,
    SystemSetting, TemplateHistory,
)
from app.db.base import SessionLocal
from app.core.config import settings
from app.billing_scheduler import reload_schedules

# ── SmartAI_Bill on sys.path ──────────────────────────────────────────────────
_smartai_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../Models/SmartAI_Bill")
)
if _smartai_path not in sys.path:
    sys.path.insert(0, _smartai_path)

from processing.batch_processor import process_single_file, process_batch
from core.gmf_reader import is_red_notice
from core.gmf_splitter import split_gmf_documents, write_doc_to_temp
from core.template_identifier import identify_template
from core.self_seal_appender import get_approved_self_seal_pdf, append_self_seal_if_needed

from processing.output_manager import (
    create_output_batches,
    list_output_dates,
    list_cycles_for_date,
    list_batches_for_cycle,
    list_pdfs_in_batch,
    get_pdf_path,
)
from templates.registry import TEMPLATE_REGISTRY, get_parser
from app.billing.worker_queue import TEMPLATE_FOLDER_MAP

router = APIRouter(prefix="/billing", tags=["billing"])


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic schemas
# ─────────────────────────────────────────────────────────────────────────────

class GmfUploadOut(BaseModel):
    id: int
    filename: str
    file_path: str
    folder_type: str
    cycle_number: Optional[int]
    template_detected: Optional[str]
    status: str
    detected_at: datetime
    processed_at: Optional[datetime]
    error_message: Optional[str]
    rejection_reason: Optional[str]
    billing_run_id: Optional[int]
    template_status: Optional[str] = None
    processed_records_count: Optional[int] = 0
    total_records_count: Optional[int] = 0
    template_breakdown: Optional[dict[str, int]] = None

    class Config:
        from_attributes = True


class BillingRunFailureOut(BaseModel):
    id: int
    account_number: Optional[str]
    error_message: str
    created_at: datetime

    class Config:
        from_attributes = True


class BillingRunOut(BaseModel):
    id: int
    batch_name: str
    cycle_number: Optional[int]
    status: str
    total_accounts: int
    succeeded: int
    failed: int
    started_at: datetime
    finished_at: Optional[datetime]
    output_path: Optional[str]
    failures: List[BillingRunFailureOut] = []

    class Config:
        from_attributes = True


class ScheduleOut(BaseModel):
    id: int
    name: str
    day_of_month: int
    run_time: str
    timezone: str
    schedule_mode: str
    is_active: bool
    approval_lead_days: int
    created_at: datetime

    class Config:
        from_attributes = True


class ScheduleCreate(BaseModel):
    name: str
    day_of_month: int
    run_time: str = "02:00"
    timezone: str = "Asia/Colombo"
    schedule_mode: str = "APPROVAL_REQUIRED"
    is_active: bool = True
    approval_lead_days: int = 1


class NotificationOut(BaseModel):
    id: int
    event_type: str
    title: str
    message: str
    upload_id: Optional[int]
    run_id: Optional[int]
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class RejectBody(BaseModel):
    reason: str = "Rejected by admin"


class SettingsOut(BaseModel):
    billing_mode: str


class SettingsUpdate(BaseModel):
    billing_mode: str


class TemplateHistoryOut(BaseModel):
    id: int
    template_name: str
    action: str
    filename: Optional[str]
    reason: Optional[str]
    timestamp: datetime

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────────────────────
# Settings and Logs
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/settings", response_model=SettingsOut)
def get_settings(db: Session = Depends(get_db), _: UserOut = Depends(require_admin)):
    setting = db.query(SystemSetting).filter(SystemSetting.key == "billing_mode").first()
    if not setting:
        setting = SystemSetting(key="billing_mode", value="auto")
        db.add(setting)
        db.commit()
        db.refresh(setting)
    return {"billing_mode": setting.value}


@router.patch("/settings", response_model=SettingsOut)
def update_settings(body: SettingsUpdate, db: Session = Depends(get_db), _: UserOut = Depends(require_admin)):
    if body.billing_mode not in ("auto", "manual"):
        raise HTTPException(status_code=400, detail="Invalid billing_mode. Must be 'auto' or 'manual'.")
    setting = db.query(SystemSetting).filter(SystemSetting.key == "billing_mode").first()
    if not setting:
        setting = SystemSetting(key="billing_mode", value=body.billing_mode)
        db.add(setting)
    else:
        setting.value = body.billing_mode
    db.commit()
    return {"billing_mode": setting.value}


@router.get("/template-history", response_model=List[TemplateHistoryOut])
def get_template_history(db: Session = Depends(get_db), _: UserOut = Depends(require_admin)):
    return db.query(TemplateHistory).order_by(TemplateHistory.timestamp.desc()).all()


@router.delete("/template-history/{history_id}")
def delete_template_history(history_id: int, db: Session = Depends(get_db), _: UserOut = Depends(require_admin)):
    history = db.query(TemplateHistory).filter(TemplateHistory.id == history_id).first()
    if not history:
        raise HTTPException(status_code=404, detail="Template history log not found")

    db.delete(history)
    db.commit()
    return {"message": "Template history log deleted successfully"}


@router.delete("/template-history")
def delete_all_template_history(db: Session = Depends(get_db), _: UserOut = Depends(require_admin)):
    db.query(TemplateHistory).delete(synchronize_session=False)
    db.commit()
    return {"message": "All template history logs deleted successfully"}


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard stats
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/stats")
def get_stats(db: Session = Depends(get_db), _: UserOut = Depends(require_admin1_or_admin)):
    """Aggregate stats for the Overview dashboard."""
    today = date.today()

    gmfs_today = db.query(func.count(GmfUpload.id)).filter(
        func.date(GmfUpload.detected_at) == today
    ).scalar() or 0

    gmfs_pending = db.query(func.count(GmfUpload.id)).filter(
        GmfUpload.status == GmfUploadStatus.PENDING_APPROVAL
    ).scalar() or 0

    # Count from billing run items for precise per-invoice numbers
    total_succeeded = db.query(func.sum(BillingRun.succeeded)).scalar() or 0
    total_failed = db.query(func.sum(BillingRun.failed)).scalar() or 0
    total_generated = total_succeeded + total_failed

    success_rate = round(total_succeeded / total_generated * 100, 2) if total_generated > 0 else 0

    active_runs = db.query(func.count(BillingRun.id)).filter(
        BillingRun.status == RunStatus.RUNNING
    ).scalar() or 0

    active_schedules = db.query(func.count(BillingSchedule.id)).filter(
        BillingSchedule.is_active == True
    ).scalar() or 0

    # Per-cycle summary (including Test_GMFs) - single batch query
    target_folders = ("Cycle_1", "Cycle_2", "Cycle_3", "Cycle_4", "Test_GMFs")
    folder_uploads = db.query(GmfUpload.folder_type, GmfUpload.status).filter(
        GmfUpload.folder_type.in_(target_folders)
    ).all()

    grouped_statuses: dict[str, list[str]] = {f: [] for f in target_folders}
    for f_type, status in folder_uploads:
        if f_type in grouped_statuses:
            status_val = status.value if hasattr(status, "value") else str(status)
            grouped_statuses[f_type].append(status_val)

    cycles = {}
    for folder in target_folders:
        statuses = grouped_statuses[folder]
        if statuses:
            if all(s == "COMPLETED" for s in statuses):
                cycle_status = "completed"
            elif any(s == "GENERATING" for s in statuses):
                cycle_status = "generating"
            elif any(s == "APPROVED" for s in statuses):
                cycle_status = "approved"
            else:
                cycle_status = "pending"
        else:
            cycle_status = "no_gmf"

        cycles[folder] = {
            "received": len(statuses),
            "status": cycle_status,
        }

    unread_notifications = db.query(func.count(NotificationEvent.id)).filter(
        NotificationEvent.is_read == False
    ).scalar() or 0

    return {
        "gmfs_received_today": gmfs_today,
        "gmfs_pending_review": gmfs_pending,
        "total_invoices_generated": int(total_succeeded),
        "total_invoices_failed": int(total_failed),
        "success_rate": success_rate,
        "active_runs": active_runs,
        "active_schedules": active_schedules,
        "unread_notifications": unread_notifications,
        "cycles": cycles,
    }


# ─────────────────────────────────────────────────────────────────────────────
# GMF Uploads
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_upload_file_path(upload: GmfUpload) -> Optional[Path]:
    """Find the existing file on disk across possible storage locations."""
    if upload.file_path and os.path.exists(upload.file_path):
        return Path(upload.file_path)
    fn = upload.filename
    possible_paths = [
        settings.queue_pending_dir / fn,
        settings.queue_incoming_dir / fn,
        settings.gmf_drive_path / "Staged" / fn,
        settings.gmf_drive_path / (upload.folder_type or "") / fn,
        settings.gmf_drive_path / "Processed" / (upload.folder_type or "unknown") / fn,
    ]
    for p in possible_paths:
        if p.exists():
            return p
    return None

def _calculate_upload_approved_counts(upload: GmfUpload, approved_templates: set) -> tuple:
    """
    Returns (approved_total_records, approved_remaining_records, is_fully_approved, active_batch_total, active_batch_processed).
    - approved_total_records: total customer records in this upload matching approved templates.
    - approved_remaining_records: records still pending generation for approved templates.
    - is_fully_approved: True if all detected templates in the upload are approved.
    - active_batch_total: Target total records for the current active approved templates workload.
    - active_batch_processed: Records processed so far for the current active approved templates workload.
    """
    f_type = upload.folder_type or ""
    processed = upload.processed_records_count or 0

    # Case 1: Spreadsheets / Special cycle folders
    if f_type in ("LOD", "VAT_Confirmation", "Final_Notice", "Customer_Letter", "Customer_Letter_Logo_V1Print", "Customer_Migration_Letter"):
        mapped = {
            "LOD": {"lod"},
            "VAT_Confirmation": {"vat_confirmation"},
            "Final_Notice": {"final_notice"},
            "Customer_Letter": {"customer_letter_logo_v1print", "customer_migration_letter", "customer_letter"},
            "Customer_Letter_Logo_V1Print": {"customer_letter_logo_v1print", "customer_migration_letter", "customer_letter"},
            "Customer_Migration_Letter": {"customer_letter_logo_v1print", "customer_migration_letter", "customer_letter"},
        }.get(f_type, set())
        
        is_app = bool(mapped.intersection(approved_templates)) if mapped else True
        tot = upload.total_records_count or 1
        app_tot = tot if is_app else 0
        app_rem = max(0, app_tot - processed)
        active_batch_tot = tot if is_app else 0
        active_batch_proc = max(0, active_batch_tot - app_rem) if is_app else 0
        return app_tot, app_rem, is_app, active_batch_tot, active_batch_proc

    # Case 2: Multi-Document GMF file with breakdown JSON
    if upload.template_breakdown:
        try:
            bd = json.loads(upload.template_breakdown)
            if isinstance(bd, dict) and bd:
                tot_in_bd = sum(bd.values())
                
                # Separate templates completed in past generation runs from the currently active approved workload
                cum_processed = processed
                past_completed_count = 0
                active_tot = 0
                
                for tid, cnt in bd.items():
                    if tid in approved_templates:
                        if cum_processed >= cnt:
                            past_completed_count += cnt
                            cum_processed -= cnt
                        else:
                            active_tot += cnt
                
                app_tot = past_completed_count + active_tot
                is_fully = (app_tot == tot_in_bd) and (tot_in_bd > 0)
                app_rem = max(0, app_tot - processed)
                
                if active_tot > 0:
                    active_batch_tot = active_tot
                    active_batch_proc = max(0, active_batch_tot - app_rem)
                else:
                    active_batch_tot = 0
                    active_batch_proc = 0
                    
                return app_tot, app_rem, is_fully, active_batch_tot, active_batch_proc
        except Exception:
            pass

    # Case 3: Single detected template
    tot = upload.total_records_count or 1
    t_id = (upload.template_detected or "").strip()
    if t_id and "," not in t_id:
        is_app = t_id in approved_templates
        app_tot = tot if is_app else 0
        app_rem = max(0, app_tot - processed)
        active_batch_tot = tot if is_app else 0
        active_batch_proc = max(0, active_batch_tot - app_rem) if is_app else 0
        return app_tot, app_rem, is_app, active_batch_tot, active_batch_proc

    # Case 4: Fallback for comma-separated template list without breakdown JSON
    raw_detected = str(upload.template_detected or "")
    for char in ['(', ')', "'", '"']:
        raw_detected = raw_detected.replace(char, '')
    detected_list = [t.strip() for t in raw_detected.split(",") if t.strip() and not t.strip().isdigit()]
    
    if not detected_list:
        return 0, 0, False, 0, 0

    matching = [t for t in detected_list if t in approved_templates]
    is_fully = len(matching) == len(detected_list)
    if is_fully:
        app_tot = tot
    elif matching:
        app_tot = max(1, int(tot * (len(matching) / len(detected_list))))
    else:
        app_tot = 0

    app_rem = max(0, app_tot - processed)
    active_batch_tot = app_tot
    active_batch_proc = max(0, active_batch_tot - app_rem)
    return app_tot, app_rem, is_fully, active_batch_tot, active_batch_proc


@router.get("/pending-batches")
def get_pending_batches(
    db: Session = Depends(get_db),
    _: UserOut = Depends(require_admin),
):
    # Check active billing mode. In Auto Mode, Ready for Generation should NOT list files.
    setting = db.query(SystemSetting).filter(SystemSetting.key == "billing_mode").first()
    billing_mode = setting.value if setting else "auto"
    if billing_mode == "auto":
        return []

    # Get all active approved templates
    app_tmpls = db.query(InvoiceTemplate).filter(
        InvoiceTemplate.approval_status == TemplateApprovalStatus.APPROVED,
        InvoiceTemplate.is_active == True
    ).all()
    approved_templates = {t.template_code for t in app_tmpls}
    if "customer_letter_logo_v1print" in approved_templates:
        approved_templates.add("customer_migration_letter")
        approved_templates.add("customer_letter")

    # Fetch all uploads in relevant states to accurately maintain batch total counts
    all_cycle_uploads = db.query(GmfUpload).filter(
        GmfUpload.status.in_([
            GmfUploadStatus.APPROVED,
            GmfUploadStatus.PARTIALLY_PROCESSED,
            GmfUploadStatus.COMPLETED,
            GmfUploadStatus.GENERATING,
        ]),
        GmfUpload.folder_type != "Test_GMFs",
    ).order_by(GmfUpload.detected_at.asc()).all()

    # Group uploads by (cycle_number or folder_type, date)
    cycle_groups = {}
    for upload in all_cycle_uploads:
        c = upload.cycle_number or upload.folder_type
        d = upload.detected_at.strftime("%Y-%m-%d") if upload.detected_at else "Unknown"
        group_key = (c, d)
        if group_key not in cycle_groups:
            cycle_groups[group_key] = []
        cycle_groups[group_key].append(upload)

    # Pre-fetch active running billing run IDs in a single query
    running_run_ids = {r[0] for r in db.query(BillingRun.id).filter(BillingRun.status == RunStatus.RUNNING).all()}

    batches = []
    for (c, d), group_uploads in sorted(cycle_groups.items(), key=lambda x: (str(x[0][0]), str(x[0][1]))):
        group_tot = 0
        group_proc = 0
        group_rem = 0
        group_pending_ids = []

        for upload in group_uploads:
            # Check if upload is currently part of an active running billing run
            is_active_generating = upload.billing_run_id in running_run_ids if upload.billing_run_id is not None else False
            if upload.billing_run_id is not None and not is_active_generating:
                upload.billing_run_id = None

            app_tot, app_rem, _, active_tot, active_proc = _calculate_upload_approved_counts(upload, approved_templates)

            if app_rem > 0:
                group_tot += active_tot
                group_proc += active_proc
                group_rem += app_rem
                if (
                    upload.status in (GmfUploadStatus.APPROVED, GmfUploadStatus.PARTIALLY_PROCESSED)
                    and not is_active_generating
                ):
                    group_pending_ids.append(upload.id)

        # Only include in "Ready for Generation" if there are remaining records AND pending uploads to run
        if group_rem > 0 and group_pending_ids:
            batches.append({
                "cycle_number": c,
                "date": d,
                "batch_index": 1,
                "file_count": len(group_pending_ids),
                "upload_ids": group_pending_ids,
                "processed_records": group_proc,
                "total_records": group_tot,
                "remaining_records": group_rem
            })
            
    return batches

@router.get("/uploads", response_model=List[GmfUploadOut])
def get_uploads(
    status: Optional[str] = None,
    cycle: Optional[int] = None,
    db: Session = Depends(get_db),
    _: UserOut = Depends(require_admin1_or_admin),
):
    """List all detected GMF files with optional filters."""
    q = db.query(GmfUpload)
    if status:
        try:
            q = q.filter(GmfUpload.status == GmfUploadStatus[status])
        except KeyError:
            pass
    if cycle:
        q = q.filter(GmfUpload.cycle_number == cycle)
    
    uploads = q.order_by(GmfUpload.detected_at.desc()).all()
    
    templates = db.query(InvoiceTemplate.template_code, InvoiceTemplate.approval_status).all()
    template_status_map = {t.template_code: t.approval_status.value for t in templates}
    
    res = []
    for u in uploads:
        d = {
            "id": u.id,
            "filename": u.filename,
            "file_path": u.file_path,
            "folder_type": u.folder_type,
            "cycle_number": u.cycle_number,
            "template_detected": u.template_detected,
            "status": u.status.value if hasattr(u.status, 'value') else u.status,
            "detected_at": u.detected_at,
            "processed_at": u.processed_at,
            "error_message": u.error_message,
            "rejection_reason": u.rejection_reason,
            "billing_run_id": u.billing_run_id,
            "template_status": template_status_map.get(u.template_detected) if u.template_detected else None,
            "processed_records_count": u.processed_records_count or 0,
            "total_records_count": u.total_records_count or 0,
            "template_breakdown": json.loads(u.template_breakdown) if (u.template_breakdown and u.template_breakdown.startswith('{')) else (
                {u.template_detected: u.total_records_count or 1} if u.template_detected else None
            ),
        }
        res.append(d)
    return res


# ─────────────────────────────────────────────────────────────────────────────
# Test Invoice Preview
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/preview/{upload_id}")
def preview_invoice(
    upload_id: int,
    db: Session = Depends(get_db),
    _: UserOut = Depends(require_admin),
):
    """Generate a single test invoice PDF for admin review."""
    upload = db.query(GmfUpload).filter(GmfUpload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    if not os.path.exists(upload.file_path):
        raise HTTPException(
            status_code=400,
            detail=f"GMF file not found on disk: {upload.file_path}"
        )

    preview_dir = settings.output_dir / "previews"
    preview_dir.mkdir(parents=True, exist_ok=True)

    # Pass limit=1 and offset=0 so the splitter immediately stops after the first document
    args = (upload.file_path, str(preview_dir), 1, True, None, 0, 1)
    results = process_single_file(args)

    if isinstance(results, list):
        if not results or not results[0].success:
            err = results[0].error if results else "Invoice engine failed"
            raise HTTPException(
                status_code=500,
                detail=f"Invoice engine failed: {err}"
            )
        result = results[0]
    else:
        result = results
        if not result.success:
            raise HTTPException(
                status_code=500,
                detail=f"Invoice engine failed: {result.error}"
            )


    # Collect detected templates across document blocks
    if isinstance(results, list):
        detected_templates = sorted(list({r.template_id for r in results if r.template_id}))
        total_docs = len(results)
    else:
        detected_templates = [results.template_id] if results.template_id else []
        total_docs = 1

    template_str = ", ".join(detected_templates) if detected_templates else (result.template_id or "unknown")

    # ── Self-Seal envelope post-processing (preview) ───────────────────
    # Apply the same envelope logic to the preview PDF so that admins can
    # see the two-page result before approving a batch run.
    if result.output_pdf and os.path.exists(result.output_pdf):
        _preview_template_id = result.template_id or (detected_templates[0] if detected_templates else "")
        _approved_self_seal_pdf = get_approved_self_seal_pdf()
        if _approved_self_seal_pdf and _preview_template_id in ("nonvat_home", "nonvat_enterprise"):
            doc_data = None
            try:
                parser_func = get_parser(_preview_template_id)
                preview_data = parser_func(upload.file_path, limit=1)
                if isinstance(preview_data, list) and preview_data:
                    doc_data = preview_data[0]
                elif isinstance(preview_data, dict):
                    if "records" in preview_data and isinstance(preview_data["records"], list) and preview_data["records"]:
                        doc_data = preview_data["records"][0]
                    else:
                        doc_data = preview_data
            except Exception as e:
                logger.warning("Could not extract preview doc_data: %s", e)

            append_self_seal_if_needed(
                result.output_pdf,
                _preview_template_id,
                _approved_self_seal_pdf,
                doc_data=doc_data,
                is_print=True,
            )
    # ───────────────────────────────────────────────────────────

    # Ensure InvoiceTemplate records exist in DB for all detected templates
    for t_code in detected_templates:
        if t_code and t_code != "unknown":
            tmpl_obj = db.query(InvoiceTemplate).filter(InvoiceTemplate.template_code == t_code).first()
            if not tmpl_obj:
                tmpl_obj = InvoiceTemplate(
                    template_code=t_code,
                    name=t_code.replace("_", " ").title(),
                    is_system_template=True,
                    approval_status=TemplateApprovalStatus.PENDING,
                    is_active=False
                )
                db.add(tmpl_obj)

    # Update upload status and log notification
    upload.template_detected = template_str
    upload.status = GmfUploadStatus.PENDING_APPROVAL
    notif = NotificationEvent(
        event_type=NotificationEventType.PREVIEW_GENERATED,
        title="Test Invoice Preview Ready",
        message=f"Preview for '{upload.filename}' ({total_docs} document(s), templates: {template_str}) generated successfully. Ready for approval.",
        upload_id=upload.id,
    )
    db.add(notif)
    db.commit()


    pdf_filename = os.path.basename(result.output_pdf)
    return {
        "message": "Preview generated successfully",
        "pdf_url": f"/billing/preview-pdfs/{pdf_filename}",
        "template_detected": template_str,
        "total_documents": total_docs,
        "templates_detected": detected_templates,
    }



@router.get("/preview-pdfs/{filename}")
def serve_preview_pdf(
    filename: str,
    _: UserOut = Depends(require_admin),
):
    """Serve a generated preview PDF from backend-managed storage."""
    safe_filename = Path(filename).name
    if safe_filename != filename or not safe_filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Invalid preview PDF filename")

    path = settings.output_dir / "previews" / safe_filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Preview PDF not found")

    return FileResponse(path, media_type="application/pdf", filename=safe_filename)


@router.get("/uploads/{upload_id}/summary")
def get_upload_summary(
    upload_id: int,
    db: Session = Depends(get_db),
    _: UserOut = Depends(require_admin),
):

    """Return detailed document, RED notice, and template breakdown for a GMF upload."""
    upload = db.query(GmfUpload).filter(GmfUpload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    is_red = is_red_notice(upload.filename)

    breakdown = []
    total_docs = upload.total_records_count or 1
    
    app_tmpls = db.query(InvoiceTemplate).filter(
        InvoiceTemplate.approval_status == TemplateApprovalStatus.APPROVED,
        InvoiceTemplate.is_active == True
    ).all()
    approved_templates = {t.template_code for t in app_tmpls}
    if "customer_letter_logo_v1print" in approved_templates:
        approved_templates.add("customer_migration_letter")
        approved_templates.add("customer_letter")

    rej_tmpls = db.query(InvoiceTemplate).filter(
        InvoiceTemplate.approval_status == TemplateApprovalStatus.REJECTED
    ).all()
    rejected_templates = {t.template_code for t in rej_tmpls}

    processed = upload.processed_records_count or 0
    if upload.status == GmfUploadStatus.COMPLETED:
        processed = total_docs

    def _fmt_tname(tid: str) -> str:
        tid_lower = tid.lower()
        if tid_lower in ("customer_letter_logo_v1print", "customer_letter", "customer_migration_letter"):
            return "Customer Migration Letter"
        if tid_lower == "lod":
            return "Letter of Demand (LOD)"
        if tid_lower == "vat_confirmation":
            return "VAT Confirmation"
        if tid_lower == "final_notice":
            return "Final Notice"
        return tid.replace("_", " ").title()

    # 1. Use stored template_breakdown JSON if available
    if upload.template_breakdown:
        try:
            bd = json.loads(upload.template_breakdown)
            if isinstance(bd, dict) and bd:
                tot_bd = sum(bd.values())
                acc_processed = processed
                for t_id, count in bd.items():
                    is_app = t_id in approved_templates
                    is_rej = t_id in rejected_templates
                    status_str = "APPROVED" if is_app else ("REJECTED" if is_rej else "PENDING_APPROVAL")
                    
                    # Estimate processed count for this specific template if file is in progress
                    if is_app:
                        t_proc = min(count, acc_processed)
                        acc_processed = max(0, acc_processed - t_proc)
                    else:
                        t_proc = 0

                    breakdown.append({
                        "template_id": t_id,
                        "template_name": _fmt_tname(t_id),
                        "count": count,
                        "processed_count": t_proc,
                        "is_approved": is_app,
                        "status": status_str,
                    })
        except Exception:
            pass

    # 2. If no stored breakdown, parse from disk file
    if not breakdown:
        # Locate existing file on disk with fallbacks
        file_path = upload.file_path
        if not os.path.exists(file_path):
            fn = upload.filename
            fallbacks = [
                settings.queue_incoming_dir / fn,
                settings.queue_pending_dir / fn,
                settings.gmf_drive_path / "Processed" / (upload.folder_type or "unknown") / fn,
                settings.gmf_drive_path / "Staged" / fn,
                settings.gmf_drive_path / (upload.folder_type or "") / fn
            ]
            for fb in fallbacks:
                if os.path.exists(fb):
                    file_path = str(fb)
                    break

        if os.path.exists(file_path):
            try:
                from core.gmf_splitter import count_documents_with_breakdown
                tot_cnt, bd_dict = count_documents_with_breakdown(file_path)
                if bd_dict:
                    acc_processed = processed
                    for t_id, count in bd_dict.items():
                        is_app = t_id in approved_templates
                        is_rej = t_id in rejected_templates
                        status_str = "APPROVED" if is_app else ("REJECTED" if is_rej else "PENDING_APPROVAL")
                        if is_app:
                            t_proc = min(count, acc_processed)
                            acc_processed = max(0, acc_processed - t_proc)
                        else:
                            t_proc = 0
                        breakdown.append({
                            "template_id": t_id,
                            "template_name": _fmt_tname(t_id),
                            "count": count,
                            "processed_count": t_proc,
                            "is_approved": is_app,
                            "status": status_str,
                        })
            except Exception:
                pass

    # 3. Fallback breakdown if file parsing was not possible
    if not breakdown and upload.template_detected:
        raw = str(upload.template_detected)
        for char in ['(', ')', "'", '"']:
            raw = raw.replace(char, '')
        parts = [p.strip() for p in raw.split(',') if p.strip() and not p.strip().isdigit()]
        acc_processed = processed
        for t_id in parts:
            is_app = t_id in approved_templates
            is_rej = t_id in rejected_templates
            status_str = "APPROVED" if is_app else ("REJECTED" if is_rej else "PENDING_APPROVAL")
            cnt = total_docs if len(parts) == 1 else max(1, total_docs // len(parts))
            if is_app:
                t_proc = min(cnt, acc_processed)
                acc_processed = max(0, acc_processed - t_proc)
            else:
                t_proc = 0
            breakdown.append({
                "template_id": t_id,
                "template_name": _fmt_tname(t_id),
                "count": cnt,
                "processed_count": t_proc,
                "is_approved": is_app,
                "status": status_str,
            })

    remaining = max(0, total_docs - processed)

    return {
        "upload_id": upload.id,
        "filename": upload.filename,
        "is_red_notice": is_red,
        "folder_type": upload.folder_type,
        "status": upload.status.value,
        "total_documents": total_docs,
        "processed_documents": processed,
        "remaining_documents": remaining,
        "template_detected": upload.template_detected,
        "detected_at": upload.detected_at,
        "template_breakdown": breakdown,
    }



# ─────────────────────────────────────────────────────────────────────────────
# Approve / Reject
# ─────────────────────────────────────────────────────────────────────────────


@router.post("/approve/{upload_id}")
def approve_upload(
    upload_id: int,
    db: Session = Depends(get_db),
    _: UserOut = Depends(require_admin),
):
    """Approve a GMF file — enables batch generation."""
    upload = db.query(GmfUpload).filter(GmfUpload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    upload.status = GmfUploadStatus.APPROVED
    notif = NotificationEvent(
        event_type=NotificationEventType.APPROVED,
        title="GMF Approved",
        message=f"'{upload.filename}' approved. Ready for invoice generation.",
        upload_id=upload.id,
    )
    db.add(notif)
    db.commit()
    return {"message": "Approved successfully", "upload_id": upload_id}


@router.post("/reject/{upload_id}")
def reject_upload(
    upload_id: int,
    body: RejectBody,
    db: Session = Depends(get_db),
    _: UserOut = Depends(require_admin),
):
    """Reject a GMF file — blocks generation."""
    upload = db.query(GmfUpload).filter(GmfUpload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    upload.status = GmfUploadStatus.FAILED
    upload.rejection_reason = body.reason
    notif = NotificationEvent(
        event_type=NotificationEventType.REJECTED,
        title="GMF Rejected",
        message=f"'{upload.filename}' rejected. Reason: {body.reason}",
        upload_id=upload.id,
    )
    db.add(notif)
    db.commit()
    return {"message": "Rejected", "upload_id": upload_id}


# ─────────────────────────────────────────────────────────────────────────────
# Batch Generation
# ─────────────────────────────────────────────────────────────────────────────

def _background_generate(upload_id: int, run_id: int):
    """Background task: calls friend's engine then organises output into folders."""

@router.post("/generate/{upload_id}")
def generate_batch(
    upload_id: int,
    db: Session = Depends(get_db),
    _: UserOut = Depends(require_admin),
):
    """Queue a single GMF file for parallel generation."""
    upload = db.query(GmfUpload).filter(GmfUpload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    if upload.status not in (GmfUploadStatus.APPROVED, GmfUploadStatus.PENDING_APPROVAL, GmfUploadStatus.PARTIALLY_PROCESSED):
        raise HTTPException(
            status_code=400,
            detail=f"GMF is already generating/completed. Current status: {upload.status.value}"
        )

    if not os.path.exists(upload.file_path):
        raise HTTPException(status_code=400, detail=f"GMF file not found on disk: {upload.file_path}")

    # Create BillingRun to track progress
    run = BillingRun(
        batch_name=f"Single GMF {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        cycle_number=upload.cycle_number if hasattr(upload, "cycle_number") else None,
        period_start=date.today(),
        period_end=date.today(),
        status=RunStatus.RUNNING,
        total_accounts=1,
        succeeded=0,
        failed=0,
        started_at=datetime.now()
    )
    db.add(run)
    db.flush()

    upload.status = GmfUploadStatus.APPROVED
    upload.billing_run_id = run.id
    db.commit()
    
    # Expire the run object so the second commit won't overwrite
    # any worker-modified counter values with stale cached zeros.
    db.expire(run)

    # Move to incoming queue AFTER database is committed
    settings.queue_incoming_dir.mkdir(parents=True, exist_ok=True)
    filename = Path(upload.file_path).name
    new_path = settings.queue_incoming_dir / filename
    
    try:
        if os.path.exists(new_path):
            os.remove(new_path)
        shutil.move(upload.file_path, str(new_path))
        upload.file_path = str(new_path)
        db.commit()
    except Exception as e:
        # Rollback db updates if move fails
        upload.status = GmfUploadStatus.PENDING_APPROVAL
        upload.billing_run_id = None
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to move file to queue: {e}")

    return {"message": "File queued for generation"}


class GenerateBatchRequest(BaseModel):
    upload_ids: List[int]
    limit: Optional[int] = None

@router.post("/generate-batch")
def generate_batch_endpoint(
    req: GenerateBatchRequest,
    db: Session = Depends(get_db),
    _: UserOut = Depends(require_admin),
):
    """Queue multiple GMF files for parallel generation."""
    upload_ids = req.upload_ids
    if not upload_ids:
        raise HTTPException(status_code=400, detail="No uploads provided")

    uploads = db.query(GmfUpload).filter(GmfUpload.id.in_(upload_ids)).all()
    if not uploads:
        raise HTTPException(status_code=404, detail="Uploads not found")

    settings.queue_incoming_dir.mkdir(parents=True, exist_ok=True)
    
    # Calculate expected total accounts for this batch run using ONLY approved remaining records
    app_tmpls = db.query(InvoiceTemplate).filter(
        InvoiceTemplate.approval_status == TemplateApprovalStatus.APPROVED,
        InvoiceTemplate.is_active == True
    ).all()
    approved_templates = {t.template_code for t in app_tmpls}
    
    # Always consider spreadsheet-based utility templates as approved for generation
    approved_templates.update({"lod", "vat_confirmation", "final_notice"})

    if "customer_letter_logo_v1print" in approved_templates:
        approved_templates.add("customer_migration_letter")
        approved_templates.add("customer_letter")

    # Filter eligible uploads and allocate batch record limit across them
    valid_uploads_with_limits = []
    remaining_budget = req.limit if req.limit is not None else None
    allocated_total = 0

    for upload in uploads:
        if upload.status == GmfUploadStatus.GENERATING:
            continue
        if upload.billing_run_id is not None:
            active_run = db.query(BillingRun).filter(BillingRun.id == upload.billing_run_id).first()
            if active_run and active_run.status == RunStatus.RUNNING:
                continue
            else:
                upload.billing_run_id = None
        if upload.status not in (GmfUploadStatus.APPROVED, GmfUploadStatus.PENDING_APPROVAL, GmfUploadStatus.PARTIALLY_PROCESSED):
            continue

        resolved_path = _resolve_upload_file_path(upload)
        if not resolved_path:
            continue
        upload.file_path = str(resolved_path)

        app_tot, app_rem, *_ = _calculate_upload_approved_counts(upload, approved_templates)
        if app_rem <= 0:
            continue

        if remaining_budget is not None:
            if remaining_budget <= 0:
                break
            file_limit = min(app_rem, remaining_budget)
            remaining_budget -= file_limit
        else:
            file_limit = None

        allocated_total += (file_limit if file_limit is not None else app_rem)
        valid_uploads_with_limits.append((upload, file_limit))

    if not valid_uploads_with_limits:
        raise HTTPException(
            status_code=400,
            detail="The selected batch is already actively generating or has no valid pending records. Please wait for the current run to finish."
        )

    total_accounts = max(1, allocated_total)

    today_str = datetime.now().strftime("%Y-%m-%d")
    first_up = valid_uploads_with_limits[0][0] if valid_uploads_with_limits else None
    f_type = first_up.folder_type if first_up else ""
    t_id = first_up.template_detected if first_up else ""
    folder_name = f_type if f_type in ("Cycle_1", "Cycle_2", "Cycle_3", "Cycle_4", "LOD", "VAT_Confirmation", "Final_Notice", "Customer_Letter", "Customer_Letter_Logo_V1Print", "Customer_Migration_Letter") else TEMPLATE_FOLDER_MAP.get(str(t_id), str(t_id) or "output")
    out_dir_path = str(settings.output_dir / today_str / folder_name)

    # Create BillingRun to track progress
    run = BillingRun(
        batch_name=f"Batch {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        cycle_number=first_up.cycle_number if (first_up and hasattr(first_up, "cycle_number")) else None,
        period_start=date.today(),
        period_end=date.today(),
        status=RunStatus.RUNNING,
        total_accounts=total_accounts,
        succeeded=0,
        failed=0,
        output_path=out_dir_path,
        started_at=datetime.now()
    )
    db.add(run)
    db.flush()
    run_id = run.id
    
    # Mark staged uploads as GENERATING
    for upload, _ in valid_uploads_with_limits:
        upload.status = GmfUploadStatus.GENERATING
        upload.billing_run_id = run.id
        
    db.commit()
    
    # CRITICAL: After this commit, background workers may immediately start
    # processing files and incrementing run.succeeded / run.failed in the DB.
    db.expire(run)
    
    # Now, copy the files to incoming queue AFTER database transaction has committed
    success_count = 0
    staging_failures = 0
    for upload, file_limit in valid_uploads_with_limits:
        filename = Path(upload.file_path).name
        try:
            # 1. Write sidecar JSON metadata FIRST before placing the data file in the queue
            meta_path = settings.queue_incoming_dir / f"{filename}.meta.json"
            meta_data = {
                "upload_id": upload.id,
                "offset": upload.processed_records_count or 0,
                "limit": file_limit,
                "billing_run_id": run_id,
                "approved_templates": list(approved_templates),
            }
            with open(meta_path, "w", encoding="utf-8") as meta_f:
                json.dump(meta_data, meta_f)

            # 2. Copy data file to queue
            new_path = settings.queue_incoming_dir / filename
            if os.path.exists(new_path):
                os.remove(new_path)
            if str(Path(upload.file_path)) != str(new_path):
                shutil.copy2(upload.file_path, str(new_path))

            success_count += 1
        except Exception as e:
            # If staging fails, mark this GMF as failed immediately so the run status stays consistent
            upload.status = GmfUploadStatus.FAILED
            upload.error_message = f"Failed to stage file: {e}"
            staging_failures += 1
            from app.db.models import BillingRunFailure
            db.add(BillingRunFailure(
                billing_run_id=run_id,
                account_number=filename,
                error_message=f"Failed to stage file: {e}"
            ))

    # Use atomic SQL UPDATE to set total_accounts and increment failed counter
    # without overwriting the succeeded/failed values that workers may have
    # already modified since our first commit.
    from sqlalchemy import update
    db.execute(
        update(BillingRun)
        .where(BillingRun.id == run_id)
        .values(
            total_accounts=total_accounts,
            failed=BillingRun.failed + staging_failures,
        )
    )
    db.commit()
    return {"message": f"{success_count} files queued for generation"}


def _background_retry_failed_batch(run_id: int):
    """Background task: retry only the failed files for a given billing run."""
    with SessionLocal() as db:
        run = db.query(BillingRun).filter(BillingRun.id == run_id).first()
        if not run or not run.failures:
            return

        failed_filenames = [f.account_number for f in run.failures]
        uploads = db.query(GmfUpload).filter(GmfUpload.filename.in_(failed_filenames)).all()
        
        if not uploads:
            return

        temp_pdf_dir = tempfile.mkdtemp(prefix="slt_batch_retry_")
        try:
            cycle_label = uploads[0].folder_type
            file_paths = [u.file_path for u in uploads]

            results = process_batch(file_paths, temp_pdf_dir)

            new_successes = sum(1 for r in results if r.success)
            
            # create outputs
            batch_folders = create_output_batches(temp_pdf_dir, cycle_label=cycle_label)
            if batch_folders:
                run.output_path = str(Path(batch_folders[0]).parent)

            run.succeeded += new_successes
            run.failed -= new_successes

            # Remove resolved failures
            for res in results:
                if res.success:
                    filename = Path(res.source_file).name
                    # Remove from DB
                    failure_record = db.query(BillingRunFailure).filter(
                        BillingRunFailure.billing_run_id == run.id,
                        BillingRunFailure.account_number == filename
                    ).first()
                    if failure_record:
                        db.delete(failure_record)
                    # update upload status
                    upload = db.query(GmfUpload).filter(
                        GmfUpload.filename == filename,
                        GmfUpload.folder_type == cycle_label
                    ).first()
                    if upload:
                        upload.status = GmfUploadStatus.COMPLETED
                else:
                    filename = Path(res.source_file).name
                    failure_record = db.query(BillingRunFailure).filter(
                        BillingRunFailure.billing_run_id == run.id,
                        BillingRunFailure.account_number == filename
                    ).first()
                    if failure_record:
                        failure_record.error_message = str(res.error) if res.error else "Unknown error"

            run.status = RunStatus.DONE if run.failed == 0 else RunStatus.PARTIAL
            run.finished_at = datetime.now()

            db.commit()

        except Exception as e:
            run.status = RunStatus.FAILED
            run.finished_at = datetime.now()
            db.commit()
        finally:
            if os.path.exists(temp_pdf_dir):
                shutil.rmtree(temp_pdf_dir, ignore_errors=True)


@router.post("/runs/{run_id}/retry")
def retry_failed_run(
    run_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: UserOut = Depends(require_admin)
):
    """Retry all failed files in a specific run."""
    run = db.query(BillingRun).filter(BillingRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
        
    if run.failed == 0 or not run.failures:
        raise HTTPException(status_code=400, detail="No failures to retry")
        
    run.status = RunStatus.RUNNING
    db.commit()
    
    background_tasks.add_task(_background_retry_failed_batch, run.id)
    return {"message": "Retry started"}


# ─────────────────────────────────────────────────────────────────────────────
# Billing Runs (history + live status)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/runs", response_model=List[BillingRunOut])
def get_runs(db: Session = Depends(get_db), _: UserOut = Depends(require_admin)):
    """List all billing run history."""
    return db.query(BillingRun).order_by(BillingRun.started_at.desc()).limit(100).all()


@router.get("/runs/{run_id}", response_model=BillingRunOut)
def get_run(run_id: int, db: Session = Depends(get_db), _: UserOut = Depends(require_admin)):
    """Get a single billing run (used for live progress polling)."""
    run = db.query(BillingRun).filter(BillingRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/runs/{run_id}/results")
def get_run_results(run_id: int, db: Session = Depends(get_db), _: UserOut = Depends(require_admin)):
    """Get successes and failures for a specific run, used for Generation Hub summary."""
    run = db.query(BillingRun).filter(BillingRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
        
    failures_list = [{"account_number": f.account_number, "error_message": f.error_message} for f in run.failures]
    
    successes = []
    if run.output_path and os.path.exists(run.output_path):
        out_path = Path(run.output_path)
        date_str = out_path.parent.name
        cycle_label = out_path.name
        
        for batch_dir in out_path.iterdir():
            if batch_dir.is_dir() and batch_dir.name.startswith("Batch_"):
                for pdf_file in batch_dir.glob("*.pdf"):
                    successes.append({
                        "date": date_str,
                        "cycle": cycle_label,
                        "batch": batch_dir.name,
                        "filename": pdf_file.name,
                        "account_number": pdf_file.stem
                    })
                    
    # Also scan completed_temp for active runs
    cycle_label = f"Cycle_{run.cycle_number}" if run.cycle_number else None
    if cycle_label:
        completed_temp_dir = Path("./queue/completed_temp") / cycle_label
        if completed_temp_dir.exists():
            from datetime import date
            date_str = date.today().strftime("%Y-%m-%d")
            archived_filenames = {s["filename"] for s in successes}
            for pdf_file in completed_temp_dir.glob("*.pdf"):
                if pdf_file.name not in archived_filenames:
                    successes.append({
                        "date": date_str,
                        "cycle": cycle_label,
                        "batch": "COMPLETED_TEMP",
                        "filename": pdf_file.name,
                        "account_number": pdf_file.stem
                    })
                    
    # Fetch GMF source files details
    uploads = db.query(GmfUpload).filter(GmfUpload.billing_run_id == run_id).all()
    
    gmf_successes = []
    gmf_failures = []
    gmf_running = []
    
    for u in uploads:
        item = {
            "id": u.id,
            "filename": u.filename,
            "folder_type": u.folder_type,
            "status": u.status.value if hasattr(u.status, "value") else u.status,
            "error_message": u.error_message
        }
        if u.status == GmfUploadStatus.COMPLETED:
            gmf_successes.append(item)
        elif u.status == GmfUploadStatus.FAILED:
            gmf_failures.append(item)
        else:
            gmf_running.append(item)
            
    return {
        "run_id": run.id,
        "successes": successes,
        "failures": failures_list,
        "gmf_successes": gmf_successes,
        "gmf_failures": gmf_failures,
        "gmf_running": gmf_running
    }


@router.delete("/runs/{run_id}")
def delete_run(run_id: int, db: Session = Depends(get_db), _: UserOut = Depends(require_admin)):
    run = db.query(BillingRun).filter(BillingRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    # Check if run is active
    if run.status in (RunStatus.RUNNING, RunStatus.PENDING):
        raise HTTPException(status_code=400, detail="Cannot delete an active run.")
    
    db.query(GmfUpload).filter(GmfUpload.billing_run_id == run_id).update(
        {GmfUpload.billing_run_id: None},
        synchronize_session=False,
    )
    db.query(NotificationEvent).filter(NotificationEvent.run_id == run_id).update(
        {NotificationEvent.run_id: None},
        synchronize_session=False,
    )
    db.query(BillingRunApproval).filter(BillingRunApproval.billing_run_id == run_id).update(
        {BillingRunApproval.billing_run_id: None},
        synchronize_session=False,
    )
    db.query(BillingRunFailure).filter(BillingRunFailure.billing_run_id == run_id).delete(synchronize_session=False)
    db.query(BillingRunItem).filter(BillingRunItem.billing_run_id == run_id).delete(synchronize_session=False)
    db.delete(run)
    db.commit()
    return {"message": "Run deleted successfully"}


@router.delete("/runs")
def delete_all_runs(db: Session = Depends(get_db), _: UserOut = Depends(require_admin)):
    # Delete all runs that are not active
    inactive_runs = db.query(BillingRun).filter(
        BillingRun.status.notin_([RunStatus.RUNNING, RunStatus.PENDING])
    ).all()
    
    inactive_run_ids = [r.id for r in inactive_runs]
    if inactive_run_ids:
        db.query(GmfUpload).filter(GmfUpload.billing_run_id.in_(inactive_run_ids)).update(
            {GmfUpload.billing_run_id: None},
            synchronize_session=False,
        )
        db.query(NotificationEvent).filter(NotificationEvent.run_id.in_(inactive_run_ids)).update(
            {NotificationEvent.run_id: None},
            synchronize_session=False,
        )
        db.query(BillingRunApproval).filter(BillingRunApproval.billing_run_id.in_(inactive_run_ids)).update(
            {BillingRunApproval.billing_run_id: None},
            synchronize_session=False,
        )
        db.query(BillingRunFailure).filter(BillingRunFailure.billing_run_id.in_(inactive_run_ids)).delete(synchronize_session=False)
        db.query(BillingRunItem).filter(BillingRunItem.billing_run_id.in_(inactive_run_ids)).delete(synchronize_session=False)
        db.query(BillingRun).filter(BillingRun.id.in_(inactive_run_ids)).delete(synchronize_session=False)
        db.commit()
        
    return {"message": "All completed/failed runs deleted successfully"}


# ─────────────────────────────────────────────────────────────────────────────
# Output Browser
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/output/dates")
def output_dates(_: UserOut = Depends(require_admin)):
    """List all dates that have generated output."""
    return {"dates": list_output_dates()}


@router.get("/output/{date_str}")
def output_cycles(date_str: str, _: UserOut = Depends(require_admin)):
    """List all cycles (Cycle_1, etc.) for a given date."""
    cycles = list_cycles_for_date(date_str)
    if not cycles:
        raise HTTPException(status_code=404, detail=f"No output found for date: {date_str}")
    return {"date": date_str, "cycles": cycles}


@router.get("/output/{date_str}/{cycle}")
def output_batches(date_str: str, cycle: str, _: UserOut = Depends(require_admin)):
    """List all batches for a given date and cycle."""
    batches = list_batches_for_cycle(date_str, cycle)
    if not batches:
        raise HTTPException(
            status_code=404,
            detail=f"No batches found for {date_str}/{cycle}"
        )
    # Add PDF count per batch
    result = []
    for b in batches:
        pdfs = list_pdfs_in_batch(date_str, cycle, b)
        result.append({"batch": b, "pdf_count": len(pdfs)})
    return {"date": date_str, "cycle": cycle, "batches": result}


@router.get("/output/{date_str}/{cycle}/{batch}")
def output_pdfs(
    date_str: str, cycle: str, batch: str,
    _: UserOut = Depends(require_admin)
):
    """List all PDF files in a specific batch."""
    pdfs = list_pdfs_in_batch(date_str, cycle, batch)
    return {"date": date_str, "cycle": cycle, "batch": batch, "files": pdfs}


@router.get("/output/{date_str}/{cycle}/{batch}/{filename:path}")
def serve_pdf(
    date_str: str, cycle: str, batch: str, filename: str,
    _: UserOut = Depends(require_admin)
):
    """Serve a single PDF file for inline viewing."""
    if batch == "COMPLETED_TEMP":
        path = os.path.abspath(os.path.join("./queue/completed_temp", cycle, filename))
    else:
        path = get_pdf_path(date_str, cycle, batch, filename)
        
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="PDF file not found")
    return FileResponse(path, media_type="application/pdf", filename=filename)


# ─────────────────────────────────────────────────────────────────────────────
# Invoice Templates
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/templates")
def get_templates(db: Session = Depends(get_db), _: UserOut = Depends(require_admin)):
    """List all invoice templates, combining registry info with DB approval status."""
    templates = []
    
    # Pre-fetch all DB templates
    db_templates = {t.template_code: t for t in db.query(InvoiceTemplate).all()}
    
    for tid, info in TEMPLATE_REGISTRY.items():
        import importlib, pkgutil
        template_dir = os.path.join(_smartai_path, "templates", tid)
        layout_pdf = os.path.join(template_dir, "layout.pdf")
        has_layout = os.path.exists(layout_pdf)
        
        # Ensure DB record exists
        if tid not in db_templates:
            new_t = InvoiceTemplate(
                template_code=tid,
                name=info["name"],
                is_system_template=True,
                is_active=True,
                approval_status=TemplateApprovalStatus.APPROVED,
            )
            db.add(new_t)
            db.commit()
            db.refresh(new_t)
            db_templates[tid] = new_t
            
        db_record = db_templates[tid]

        templates.append({
            "id": tid,
            "name": info["name"],
            "description": info["description"],
            "ready": info.get("ready", False),
            "has_layout_preview": has_layout,
            "approval_status": db_record.approval_status.value if hasattr(db_record, "approval_status") else "PENDING",
        })
    return {"templates": templates}

class TemplateStatusUpdate(BaseModel):
    status: str
    reason: Optional[str] = None

@router.patch("/templates/{template_id}/status")
def update_template_status(
    template_id: str,
    body: TemplateStatusUpdate,
    db: Session = Depends(get_db),
    _: UserOut = Depends(require_admin)
):
    """Approve or Reject an invoice template globally."""
    try:
        from app.db.models import TemplateApprovalStatus
        new_status = TemplateApprovalStatus[body.status]
    except KeyError:
        raise HTTPException(status_code=400, detail="Invalid status")

    target_ids = [t.strip() for t in template_id.split(",") if t.strip()]
    if not target_ids:
        target_ids = [template_id]
    target_ids_set = set(target_ids)

    for t_code in target_ids:
        t = db.query(InvoiceTemplate).filter(InvoiceTemplate.template_code == t_code).first()
        if not t:
            t = InvoiceTemplate(
                template_code=t_code,
                name=t_code.replace("_", " ").title(),
                is_system_template=True,
                is_active=(new_status == TemplateApprovalStatus.APPROVED),
                approval_status=new_status,
            )
            db.add(t)
        else:
            t.approval_status = new_status
            t.is_active = (new_status == TemplateApprovalStatus.APPROVED)

    db.commit()

    
    # Cascade status update to pending uploads and physically move files
    import logging
    logger = logging.getLogger(__name__)
    
    # Get active billing mode setting
    setting = db.query(SystemSetting).filter(SystemSetting.key == "billing_mode").first()
    billing_mode = setting.value if setting else "auto"
    
    # Get the test GMF used to preview this template
    test_gmf = db.query(GmfUpload).filter(
        GmfUpload.template_detected == template_id,
        GmfUpload.folder_type == "Test_GMFs"
    ).order_by(GmfUpload.detected_at.desc()).first()
    test_filename = test_gmf.filename if test_gmf else None

    # Write log to TemplateHistory
    hist = TemplateHistory(
        template_name=template_id,
        action=body.status,
        filename=test_filename,
        reason=body.reason
    )
    db.add(hist)
    
    app_tmpls = db.query(InvoiceTemplate).filter(
        InvoiceTemplate.approval_status == TemplateApprovalStatus.APPROVED,
        InvoiceTemplate.is_active == True
    ).all()
    approved_templates = {t.template_code for t in app_tmpls}
    if "customer_letter_logo_v1print" in approved_templates:
        approved_templates.add("customer_migration_letter")
        approved_templates.add("customer_letter")

    if new_status == TemplateApprovalStatus.APPROVED:
        all_pending = db.query(GmfUpload).filter(
            GmfUpload.status.in_([GmfUploadStatus.PENDING_APPROVAL, GmfUploadStatus.REJECTED, GmfUploadStatus.PARTIALLY_PROCESSED])
        ).all()
        
        candidate_uploads = []
        for u in all_pending:
            if u.template_detected == template_id:
                candidate_uploads.append(u)
            elif u.template_breakdown:
                try:
                    bd = json.loads(u.template_breakdown)
                    if template_id in bd:
                        candidate_uploads.append(u)
                except Exception:
                    pass
        non_test_uploads = []
        for upload in candidate_uploads:
            if upload.folder_type == "Test_GMFs":
                upload.status = GmfUploadStatus.APPROVED
                upload.rejection_reason = None
                continue

            app_tot, app_rem, is_fully, *_ = _calculate_upload_approved_counts(upload, approved_templates)
            proc = upload.processed_records_count or 0

            if is_fully:
                target_status = GmfUploadStatus.APPROVED if proc == 0 else GmfUploadStatus.PARTIALLY_PROCESSED
            elif app_tot > 0:
                target_status = GmfUploadStatus.PARTIALLY_PROCESSED
            else:
                target_status = GmfUploadStatus.PENDING_APPROVAL

            upload.status = target_status
            upload.rejection_reason = None
            old_path = Path(upload.file_path)

            if billing_mode == "auto" and is_fully:
                new_path = settings.queue_incoming_dir / upload.filename
                if old_path.exists():
                    try:
                        settings.queue_incoming_dir.mkdir(parents=True, exist_ok=True)
                        if old_path != new_path:
                            if new_path.exists():
                                new_path.unlink()
                            shutil.move(str(old_path), str(new_path))
                            upload.file_path = str(new_path)
                        non_test_uploads.append(upload)
                    except Exception as e:
                        logger.error(f"Failed to move file {upload.filename} to incoming queue: {e}")
                else:
                    non_test_uploads.append(upload)
            else:
                new_path = settings.queue_pending_dir / upload.filename
                if old_path.exists():
                    upload.billing_run_id = None
                    try:
                        settings.queue_pending_dir.mkdir(parents=True, exist_ok=True)
                        if old_path != new_path:
                            if new_path.exists():
                                new_path.unlink()
                            shutil.move(str(old_path), str(new_path))
                            upload.file_path = str(new_path)
                    except Exception as e:
                        logger.error(f"Failed to ensure file {upload.filename} in pending queue: {e}")
                else:
                    upload.billing_run_id = None

        # In Auto Mode, automatically generate invoices immediately
        if billing_mode == "auto" and non_test_uploads:
            run = BillingRun(
                batch_name=f"Auto Gen {template_id} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                cycle_number=non_test_uploads[0].cycle_number if hasattr(non_test_uploads[0], "cycle_number") else None,
                period_start=date.today(),
                period_end=date.today(),
                status=RunStatus.RUNNING,
                total_accounts=sum(u.total_records_count or 1 for u in non_test_uploads),
                succeeded=0,
                failed=0,
                started_at=datetime.now()
            )
            db.add(run)
            db.flush()

            for upload in non_test_uploads:
                upload.billing_run_id = run.id

            notif = NotificationEvent(
                event_type=NotificationEventType.BATCH_STARTED,
                title="Auto Batch Generation Started",
                message=f"Auto billing run started for template '{template_id}' with {len(non_test_uploads)} files.",
                run_id=run.id,
            )
            db.add(notif)

    elif new_status == TemplateApprovalStatus.REJECTED:
        candidate_uploads = db.query(GmfUpload).filter(
            GmfUpload.status.in_([GmfUploadStatus.PENDING_APPROVAL, GmfUploadStatus.APPROVED, GmfUploadStatus.PARTIALLY_PROCESSED])
        ).all()
        for upload in candidate_uploads:
            if upload.folder_type == "Test_GMFs":
                if upload.template_detected == template_id:
                    upload.status = GmfUploadStatus.REJECTED
                    upload.rejection_reason = body.reason
                continue

            app_tot, app_rem, is_fully, *_ = _calculate_upload_approved_counts(upload, approved_templates)
            if app_tot == 0:
                upload.status = GmfUploadStatus.REJECTED
                upload.rejection_reason = body.reason
            elif not is_fully:
                upload.status = GmfUploadStatus.PARTIALLY_PROCESSED
                upload.rejection_reason = None

            old_path = Path(upload.file_path)
            new_path = settings.queue_pending_dir / upload.filename
            try:
                settings.queue_pending_dir.mkdir(parents=True, exist_ok=True)
                if old_path.exists() and old_path != new_path:
                    if new_path.exists():
                        new_path.unlink()
                    shutil.move(str(old_path), str(new_path))
                    upload.file_path = str(new_path)
            except Exception as e:
                logger.error(f"Failed to move file {upload.filename} to pending queue: {e}")

    db.commit()
    return {"message": "Status updated successfully", "status": new_status.value}




@router.get("/templates/{template_id}/preview")
def preview_template_layout(template_id: str, _: UserOut = Depends(require_admin)):
    """Serve the blank layout PDF for a template."""
    layout_path = os.path.join(_smartai_path, "templates", template_id, "layout.pdf")
    if not os.path.exists(layout_path):
        raise HTTPException(status_code=404, detail="Layout PDF not found for this template")
    return FileResponse(layout_path, media_type="application/pdf")


# ─────────────────────────────────────────────────────────────────────────────
# Notifications / Activity Log
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/notifications", response_model=List[NotificationOut])
def get_notifications(
    unread_only: bool = False,
    db: Session = Depends(get_db),
    _: UserOut = Depends(require_admin1_or_admin),
):
    """Get all system notification events."""
    q = db.query(NotificationEvent)
    if unread_only:
        q = q.filter(NotificationEvent.is_read == False)
    return q.order_by(NotificationEvent.created_at.desc()).limit(200).all()


@router.patch("/notifications/{notif_id}/read")
def mark_read(
    notif_id: int,
    db: Session = Depends(get_db),
    _: UserOut = Depends(require_admin1_or_admin),
):
    notif = db.query(NotificationEvent).filter(NotificationEvent.id == notif_id).first()
    if notif:
        notif.is_read = True
        db.commit()
    return {"ok": True}


@router.patch("/notifications/mark-all-read")
def mark_all_read(db: Session = Depends(get_db), _: UserOut = Depends(require_admin1_or_admin)):
    db.query(NotificationEvent).filter(
        NotificationEvent.is_read == False
    ).update({"is_read": True})
    db.commit()
    return {"ok": True}


@router.delete("/notifications/clear-read")
def clear_read(db: Session = Depends(get_db), _: UserOut = Depends(require_admin1_or_admin)):
    db.query(NotificationEvent).filter(NotificationEvent.is_read == True).delete()
    db.commit()
    return {"ok": True}


# ─────────────────────────────────────────────────────────────────────────────
# Schedule Manager
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/schedules", response_model=List[ScheduleOut])
def get_schedules(db: Session = Depends(get_db), _: UserOut = Depends(require_admin)):
    return db.query(BillingSchedule).order_by(BillingSchedule.id).all()


@router.post("/schedules", response_model=ScheduleOut)
def create_schedule(
    body: ScheduleCreate,
    db: Session = Depends(get_db),
    _: UserOut = Depends(require_admin),
):
    try:
        mode = BillingScheduleMode[body.schedule_mode]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid schedule_mode: {body.schedule_mode}")

    schedule = BillingSchedule(
        name=body.name,
        day_of_month=body.day_of_month,
        run_time=body.run_time,
        timezone=body.timezone,
        schedule_mode=mode,
        is_active=body.is_active,
        approval_lead_days=body.approval_lead_days,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    reload_schedules()
    return schedule


@router.put("/schedules/{schedule_id}", response_model=ScheduleOut)
def update_schedule(
    schedule_id: int,
    body: ScheduleCreate,
    db: Session = Depends(get_db),
    _: UserOut = Depends(require_admin),
):
    schedule = db.query(BillingSchedule).filter(BillingSchedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    try:
        mode = BillingScheduleMode[body.schedule_mode]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid schedule_mode: {body.schedule_mode}")

    schedule.name = body.name
    schedule.day_of_month = body.day_of_month
    schedule.run_time = body.run_time
    schedule.timezone = body.timezone
    schedule.schedule_mode = mode
    schedule.is_active = body.is_active
    schedule.approval_lead_days = body.approval_lead_days
    db.commit()
    db.refresh(schedule)
    reload_schedules()
    return schedule


@router.patch("/schedules/{schedule_id}/toggle")
def toggle_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    _: UserOut = Depends(require_admin),
):
    schedule = db.query(BillingSchedule).filter(BillingSchedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    schedule.is_active = not schedule.is_active
    db.commit()
    reload_schedules()
    return {"id": schedule_id, "is_active": schedule.is_active}


@router.delete("/schedules/{schedule_id}")
def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    _: UserOut = Depends(require_admin),
):
    schedule = db.query(BillingSchedule).filter(BillingSchedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    db.delete(schedule)
    db.commit()
    reload_schedules()
    return {"ok": True}


# ─────────────────────────────────────────────────────────────────────────────
# GMF Uploads and Drive Syncing
# ─────────────────────────────────────────────────────────────────────────────

def _is_valid_gmf_upload_name(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    ext_clean = ext[1:] if ext.startswith(".") else ext
    return ext_clean in ("", "gmf", "zip", "xlsx", "xls", "csv") or ext_clean.isdigit()


def _background_register_staged_gmfs(staged_files: list[tuple[str, str]], folder_type: str, cleanup_dir: str):
    """Register uploaded GMFs after the HTTP request has already returned."""
    import logging
    import shutil
    from app.db.base import SessionLocal
    from app.db.models import GmfUpload, GmfUploadStatus, NotificationEvent, NotificationEventType, InvoiceTemplate, TemplateApprovalStatus
    from app.uploads.watcher import _get_cycle, _resolve_folder_type
    from core.gmf_splitter import count_documents_with_breakdown

    logger = logging.getLogger("gmf_upload")
    logger.setLevel(logging.INFO)

    is_test = (folder_type == "Test_GMFs")
    registered_count = 0
    failed_count = 0

    db = SessionLocal()
    try:
        settings.queue_incoming_dir.mkdir(parents=True, exist_ok=True)
        settings.queue_pending_dir.mkdir(parents=True, exist_ok=True)
        templates_cache = {t.template_code: t.approval_status for t in db.query(InvoiceTemplate).all()}
        move_plan: list[tuple[Path, Path, str]] = []

        for source_path_str, filename in staged_files:
            source_path = Path(source_path_str)
            if not source_path.exists():
                failed_count += 1
                logger.error("Staged upload disappeared before registration: %s", source_path)
                continue

            resolved_folder_type = _resolve_folder_type(folder_type, source_path)
            cycle_number = _get_cycle(resolved_folder_type)

            total_cnt, breakdown = count_documents_with_breakdown(str(source_path))
            detected_list = sorted(list(breakdown.keys())) if breakdown else []
            template_detected = ", ".join(detected_list) if detected_list else None
            total_records_count = total_cnt if total_cnt > 0 else 1

            is_approved = bool(detected_list) and any(templates_cache.get(t) == TemplateApprovalStatus.APPROVED for t in detected_list)
            is_rejected = bool(detected_list) and any(templates_cache.get(t) == TemplateApprovalStatus.REJECTED for t in detected_list)

            if is_test:
                final_path = settings.gmf_drive_path / folder_type / filename
                final_status = GmfUploadStatus.PENDING_APPROVAL
                final_path.parent.mkdir(parents=True, exist_ok=True)
                for t_code in detected_list:
                    t_obj = db.query(InvoiceTemplate).filter(InvoiceTemplate.template_code == t_code).first()
                    if not t_obj:
                        t_obj = InvoiceTemplate(template_code=t_code, name=t_code, is_system_template=True)
                        db.add(t_obj)
                    t_obj.approval_status = TemplateApprovalStatus.PENDING
                    templates_cache[t_code] = TemplateApprovalStatus.PENDING

            elif is_approved:
                # Respect global billing_mode so we don't auto-generate if in manual mode
                from app.db.models import SystemSetting
                billing_mode_setting = db.query(SystemSetting).filter(SystemSetting.key == "billing_mode").first()
                billing_mode = billing_mode_setting.value if billing_mode_setting else "auto"
                if billing_mode == "auto":
                    final_path = settings.queue_incoming_dir / filename
                else:
                    final_path = settings.queue_pending_dir / filename
                final_status = GmfUploadStatus.APPROVED
            elif is_rejected:
                final_path = settings.queue_pending_dir / filename
                final_status = GmfUploadStatus.REJECTED
            else:
                final_path = settings.queue_pending_dir / filename
                final_status = GmfUploadStatus.PENDING_APPROVAL

            existing = db.query(GmfUpload).filter(
                GmfUpload.filename == filename,
                GmfUpload.folder_type == resolved_folder_type,
            ).first()
            if existing:
                if existing.status == GmfUploadStatus.COMPLETED:
                    logger.info(f"GMF {filename} in {folder_type} is already COMPLETED. Skipping duplicate invoice generation.")
                    if source_path.exists():
                        try:
                            source_path.unlink()
                        except Exception:
                            pass
                    registered_count += 1
                    continue

                existing.file_path = str(final_path)
                existing.status = final_status
                existing.error_message = None
                existing.rejection_reason = None
                existing.billing_run_id = None
                existing.total_records_count = total_records_count
                existing.template_breakdown = json.dumps(breakdown) if breakdown else None
            else:
                db.add(GmfUpload(
                    filename=filename,
                    file_path=str(final_path),
                    folder_type=resolved_folder_type,
                    cycle_number=cycle_number,
                    template_detected=template_detected,
                    status=final_status,
                    total_records_count=total_records_count,
                    template_breakdown=json.dumps(breakdown) if breakdown else None,
                ))

            # Move physical file to destination immediately
            try:
                final_path.parent.mkdir(parents=True, exist_ok=True)
                if final_path.exists():
                    final_path.unlink()
                shutil.move(str(source_path), str(final_path))
            except Exception as move_err:
                failed_count += 1
                logger.error("Failed to move staged GMF %s to %s: %s", filename, final_path, move_err)

            # Commit EACH file immediately so GMF Monitor shows it in real time
            db.commit()
            registered_count += 1

        db.add(NotificationEvent(
            event_type=NotificationEventType.TEST_GMF_RECEIVED if is_test else NotificationEventType.GMF_DETECTED,
            title=f"GMF Upload Batch Queued - {folder_type}",
            message=(
                f"Registered {registered_count} uploaded GMF file(s)"
                + (f"; {failed_count} failed." if failed_count else ".")
            ),
        ))
        db.commit()
        logger.info("Background GMF registration complete: registered=%d failed=%d", registered_count, failed_count)
    except Exception as err:
        db.rollback()
        logger.error("Error in background GMF registration: %s", err, exc_info=True)
    finally:
        db.close()
        shutil.rmtree(cleanup_dir, ignore_errors=True)


def _background_process_gmf_zip(temp_zip_path: str, folder_type: str):
    """Processes uploaded ZIP containing GMF files in the background."""
    import zipfile
    import tempfile
    import shutil
    import logging
    from app.db.base import SessionLocal
    from app.db.models import GmfUpload, GmfUploadStatus, NotificationEvent, NotificationEventType, InvoiceTemplate, TemplateApprovalStatus
    from app.uploads.watcher import _get_cycle, _should_skip, _resolve_folder_type
    from core.gmf_splitter import count_documents_with_breakdown
    
    logger = logging.getLogger("gmf_upload")
    logger.setLevel(logging.INFO)
    
    is_test = (folder_type == "Test_GMFs")
    
    temp_extract_dir = tempfile.mkdtemp(prefix="slt_zip_extract_")
    try:
        with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_extract_dir)
            
        extracted_files = []
        for root, dirs, files in os.walk(temp_extract_dir):
            for file in files:
                if not _should_skip(file):
                    extracted_files.append(Path(root) / file)
                    
        logger.info(f"Unzipped {len(extracted_files)} files.")
        
        batch_size = 100
        db = SessionLocal()
        try:
            settings.queue_incoming_dir.mkdir(parents=True, exist_ok=True)
            settings.queue_pending_dir.mkdir(parents=True, exist_ok=True)
            
            billing_mode_setting = db.query(SystemSetting).filter(SystemSetting.key == "billing_mode").first()
            billing_mode = billing_mode_setting.value if billing_mode_setting else "auto"
            templates_cache = {t.template_code: t.approval_status for t in db.query(InvoiceTemplate).all()}
            
            for idx, file_path in enumerate(extracted_files):
                filename = file_path.name

                resolved_folder_type = _resolve_folder_type(folder_type, file_path)
                cycle_number = _get_cycle(resolved_folder_type)
                
                total_cnt, breakdown = count_documents_with_breakdown(str(file_path))
                detected_list = sorted(list(breakdown.keys())) if breakdown else []
                template_detected = ", ".join(detected_list) if detected_list else None
                total_records_count = total_cnt if total_cnt > 0 else 1
                
                is_approved = bool(detected_list) and any(templates_cache.get(t) == TemplateApprovalStatus.APPROVED for t in detected_list)
                is_rejected = bool(detected_list) and any(templates_cache.get(t) == TemplateApprovalStatus.REJECTED for t in detected_list)
                
                if is_test:
                    final_path = settings.gmf_drive_path / folder_type / filename
                    final_status = GmfUploadStatus.PENDING_APPROVAL
                    final_path.parent.mkdir(parents=True, exist_ok=True)
                else:
                    if is_approved and billing_mode == "auto":
                        final_path = settings.queue_incoming_dir / filename
                        final_status = GmfUploadStatus.APPROVED
                    elif is_approved and billing_mode == "manual":
                        final_path = settings.queue_pending_dir / filename
                        final_status = GmfUploadStatus.APPROVED
                    elif is_rejected:
                        final_path = settings.queue_pending_dir / filename
                        final_status = GmfUploadStatus.REJECTED
                    else:
                        final_path = settings.queue_pending_dir / filename
                        final_status = GmfUploadStatus.PENDING_APPROVAL
                
                # 1. Update/Insert DB record FIRST
                existing = db.query(GmfUpload).filter(
                    GmfUpload.filename == filename,
                    GmfUpload.folder_type == resolved_folder_type
                ).first()
                if existing:
                    existing.file_path = str(final_path)
                    existing.status = final_status
                    existing.error_message = None
                    existing.rejection_reason = None
                    existing.billing_run_id = None
                    existing.template_detected = template_detected
                    existing.total_records_count = total_records_count
                    existing.template_breakdown = json.dumps(breakdown) if breakdown else None
                else:
                    upload = GmfUpload(
                        filename=filename,
                        file_path=str(final_path),
                        folder_type=resolved_folder_type,
                        cycle_number=cycle_number,
                        template_detected=template_detected,
                        total_records_count=total_records_count,
                        template_breakdown=json.dumps(breakdown) if breakdown else None,
                        status=final_status,
                    )
                    db.add(upload)

                
                # 2. COMMIT DB to ensure the watcher sees this record if it triggers
                db.commit()
                
                # 3. NOW copy the file to disk (which fires the watcher)
                shutil.copy2(str(file_path), str(final_path))
            
            # Create a single summary notification
            notif = NotificationEvent(
                event_type=NotificationEventType.GMF_DETECTED if not is_test else NotificationEventType.TEST_GMF_RECEIVED,
                title=f"ZIP Upload Batch Completed — {folder_type}",
                message=f"Processed and registered {len(extracted_files)} files into {folder_type}."
            )
            db.add(notif)
            db.commit()
            
        finally:
            db.close()
            
    except Exception as err:
        logger.error(f"Error in background ZIP processing: {err}")
    finally:
        if os.path.exists(temp_zip_path):
            os.remove(temp_zip_path)
        if os.path.exists(temp_extract_dir):
            shutil.rmtree(temp_extract_dir, ignore_errors=True)


@router.post("/upload-gmf")
def upload_gmf(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    folder_type: str = Form(...),
    db: Session = Depends(get_db),
    _: UserOut = Depends(require_admin1_or_admin)
):
    """Accept direct GMF file or ZIP uploads."""
    if folder_type not in ("Cycle", "Cycle_1", "Cycle_2", "Cycle_3", "Cycle_4", "No_Cycle", "Test_GMFs", "LOD", "VAT_Confirmation", "Final_Notice", "Customer_Letter", "Customer_Letter_Logo_V1Print"):
        raise HTTPException(status_code=400, detail="Invalid folder_type.")

    staged_files: list[tuple[str, str]] = []
    staging_dir = tempfile.mkdtemp(prefix="slt_gmf_upload_")
    try:
        for file in files:
            filename = Path(file.filename or "").name
            if not filename:
                continue

            if not _is_valid_gmf_upload_name(filename):
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid file format: {filename}. Only GMF files (no extension, numeric suffixes like .1, .6, or .gmf) and .zip archives are allowed.",
                )

            if filename.lower().endswith(".zip"):
                temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
                try:
                    shutil.copyfileobj(file.file, temp_zip, length=1024 * 1024)
                    temp_zip.close()
                    background_tasks.add_task(_background_process_gmf_zip, temp_zip.name, folder_type)
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Failed to stage uploaded ZIP: {e}")
            else:
                staged_path = Path(staging_dir) / filename
                try:
                    with staged_path.open("wb") as out_file:
                        shutil.copyfileobj(file.file, out_file, length=1024 * 1024)
                    staged_files.append((str(staged_path), filename))
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Failed to stage uploaded file {filename}: {e}")

        if staged_files:
            background_tasks.add_task(_background_register_staged_gmfs, staged_files, folder_type, staging_dir)
        else:
            shutil.rmtree(staging_dir, ignore_errors=True)
    except Exception:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise

    return {"message": "Files uploaded and queued for background processing."}


@router.post("/scan-drive")
def scan_drive(background_tasks: BackgroundTasks, _: UserOut = Depends(require_admin1_or_admin)):
    """Manually trigger watch folder scans."""
    from app.uploads.watcher import _scan_existing_files, WATCH_DIR
    background_tasks.add_task(_scan_existing_files, WATCH_DIR)
    return {"message": "Drive scan triggered in background."}


def _is_admin1_role(role: str) -> bool:
    role_value = getattr(role, "value", role)
    return str(role_value).upper().split(".")[-1] == "ADMIN1"


@router.delete("/uploads/{upload_id}")
def delete_upload(
    upload_id: int,
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(require_admin1_or_admin)
):
    if not _is_admin1_role(current_user.role):
        raise HTTPException(status_code=403, detail="Only Admin1 can delete uploaded GMF files.")

    upload = db.query(GmfUpload).filter(GmfUpload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="GMF upload not found.")
        
    if upload.template_detected:
        template = db.query(InvoiceTemplate).filter(
            InvoiceTemplate.template_code == upload.template_detected
        ).first()
        if template and template.approval_status in (TemplateApprovalStatus.APPROVED, TemplateApprovalStatus.REJECTED):
            raise HTTPException(
                status_code=403,
                detail="Cannot delete GMF uploads associated with an approved or rejected template."
            )
            
    if upload.file_path and os.path.exists(upload.file_path):
        try:
            os.remove(upload.file_path)
        except Exception as e:
            logger.error(f"Failed to delete physical GMF file: {e}")
            
    db.delete(upload)
    db.commit()
    return {"message": "GMF upload deleted successfully."}


@router.delete("/uploads")
def delete_all_uploads(
    folder_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(require_admin1_or_admin)
):
    if not _is_admin1_role(current_user.role):
        raise HTTPException(status_code=403, detail="Only Admin1 can clear uploaded GMF files.")

    query = db.query(GmfUpload)
    if folder_type:
        query = query.filter(GmfUpload.folder_type == folder_type)
    uploads = query.all()
    
    deleted_count = 0
    skipped_count = 0
    
    for upload in uploads:
        can_delete = True
        if upload.template_detected:
            template = db.query(InvoiceTemplate).filter(
                InvoiceTemplate.template_code == upload.template_detected
            ).first()
            if template and template.approval_status in (TemplateApprovalStatus.APPROVED, TemplateApprovalStatus.REJECTED):
                can_delete = False
                
        if can_delete:
            if upload.file_path and os.path.exists(upload.file_path):
                try:
                    os.remove(upload.file_path)
                except Exception as e:
                    logger.error(f"Failed to delete physical GMF file: {e}")
            db.delete(upload)
            deleted_count += 1
        else:
            skipped_count += 1
            
    db.commit()
    return {
        "message": f"Successfully deleted {deleted_count} GMF uploads. Skipped {skipped_count} uploads associated with approved/rejected templates.",
        "deleted_count": deleted_count,
        "skipped_count": skipped_count
    }
