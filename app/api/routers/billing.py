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

from processing.output_manager import (
    create_output_batches,
    list_output_dates,
    list_cycles_for_date,
    list_batches_for_cycle,
    list_pdfs_in_batch,
    get_pdf_path,
)
from templates.registry import TEMPLATE_REGISTRY

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
    failures: List[dict] = []

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

    # Per-cycle summary (including Test_GMFs)
    cycles = {}
    for folder in ("Cycle_1", "Cycle_2", "Cycle_3", "Cycle_4", "Test_GMFs"):
        uploads = db.query(GmfUpload).filter(GmfUpload.folder_type == folder).all()
        if uploads:
            statuses = [u.status.value for u in uploads]
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
            "received": len(uploads),
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

    pending_uploads = db.query(GmfUpload).filter(
        GmfUpload.status.in_([GmfUploadStatus.APPROVED, GmfUploadStatus.PARTIALLY_PROCESSED]),
        GmfUpload.folder_type != "Test_GMFs",
        or_(
            GmfUpload.billing_run_id.is_(None),
            GmfUpload.total_records_count == 0,
            GmfUpload.processed_records_count < GmfUpload.total_records_count
        )
    ).order_by(GmfUpload.detected_at.asc()).all()

    cycles = {}
    dates = {}
    for upload in pending_uploads:
        c = upload.cycle_number or upload.folder_type
        if c not in cycles:
            cycles[c] = []
            dates[c] = upload.detected_at.strftime("%Y-%m-%d")
        cycles[c].append(upload)
        
    batches = []
    for c, uploads_list in sorted(cycles.items(), key=lambda x: str(x[0])):
        upload_ids = [u.id for u in uploads_list]
        proc = sum(u.processed_records_count or 0 for u in uploads_list)
        tot = sum(u.total_records_count or 0 for u in uploads_list)
        batches.append({
            "cycle_number": c,
            "date": dates[c],
            "batch_index": 1,
            "file_count": len(upload_ids),
            "upload_ids": upload_ids,
            "processed_records": proc,
            "total_records": tot,
            "remaining_records": max(0, tot - proc) if tot > 0 else 0
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

    args = (upload.file_path, str(preview_dir), 1, True)
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

    active_templates = set(
        t.template_code for t in db.query(InvoiceTemplate).filter(InvoiceTemplate.is_active == True).all()
    )

    if os.path.exists(file_path):
        try:
            docs = split_gmf_documents(file_path)
            if docs:
                total_docs = len(docs)
                with tempfile.TemporaryDirectory(prefix="gmf_summary_") as tmp:
                    counts = {}
                    for idx, doc_lines in enumerate(docs, start=1):
                        tmp_path = write_doc_to_temp(doc_lines, tmp, upload.filename, idx)
                        ident = identify_template(tmp_path)
                        t_id = ident.template_id or "unknown"
                        counts[t_id] = counts.get(t_id, 0) + 1

                    for t_id, count in counts.items():
                        is_active = t_id in active_templates
                        breakdown.append({
                            "template_id": t_id,
                            "template_name": t_id.replace("_", " ").title(),
                            "count": count,
                            "is_approved": is_active,
                            "status": "APPROVED" if is_active else "PENDING_APPROVAL"
                        })
        except Exception:
            pass

    # Fallback breakdown if file parsing was not possible
    if not breakdown and upload.template_detected:
        raw = str(upload.template_detected)
        for char in ['(', ')', "'", '"']:
            raw = raw.replace(char, '')
        parts = [p.strip() for p in raw.split(',') if p.strip() and not p.strip().isdigit()]
        for t_id in parts:
            is_active = t_id in active_templates
            breakdown.append({
                "template_id": t_id,
                "template_name": t_id.replace("_", " ").title(),
                "count": total_docs if len(parts) == 1 else max(1, total_docs // len(parts)),
                "is_approved": is_active,
                "status": "APPROVED" if is_active else "PENDING_APPROVAL"
            })

    processed = upload.processed_records_count or 0
    if upload.status == GmfUploadStatus.COMPLETED:
        processed = total_docs
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
    
    # Calculate expected total accounts for this batch run
    expected_count = req.limit if req.limit else sum((u.total_records_count or 1) - (u.processed_records_count or 0) for u in uploads)
    total_accounts = max(1, expected_count)

    today_str = datetime.now().strftime("%Y-%m-%d")
    first_up = uploads[0] if uploads else None
    f_type = first_up.folder_type if first_up else ""
    t_id = first_up.template_detected if first_up else ""
    folder_name = f_type if f_type in ("Cycle_1", "Cycle_2", "Cycle_3", "Cycle_4", "LOD", "VAT_Confirmation", "Final_Notice", "Customer_Letter") else TEMPLATE_FOLDER_MAP.get(str(t_id), str(t_id) or "output")
    out_dir_path = str(settings.output_dir / today_str / folder_name)

    # Create BillingRun to track progress
    run = BillingRun(
        batch_name=f"Batch {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        cycle_number=uploads[0].cycle_number if (uploads and hasattr(uploads[0], "cycle_number")) else None,
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
    
    # First, mark uploads as approved and set billing_run_id in DB, and commit
    valid_uploads = []
    for upload in uploads:
        if upload.status not in (GmfUploadStatus.APPROVED, GmfUploadStatus.PENDING_APPROVAL, GmfUploadStatus.PARTIALLY_PROCESSED):
            continue
        if not os.path.exists(upload.file_path):
            continue
        upload.status = GmfUploadStatus.APPROVED
        upload.billing_run_id = run.id
        valid_uploads.append(upload)
        
    db.commit()
    
    # CRITICAL: After this commit, background workers may immediately start
    # processing files and incrementing run.succeeded / run.failed in the DB.
    # We must NOT write stale cached values (succeeded=0, failed=0) back to the
    # DB in the second commit below. Expire the run object so SQLAlchemy will
    # re-read from DB if we access its attributes, and avoid setting succeeded/failed.
    db.expire(run)
    
    # Now, copy the files to incoming queue AFTER database transaction has committed
    success_count = 0
    staging_failures = 0
    for upload in valid_uploads:
        filename = Path(upload.file_path).name
        try:
            new_path = settings.queue_incoming_dir / filename
            if os.path.exists(new_path):
                os.remove(new_path)
            if str(Path(upload.file_path)) != str(new_path):
                shutil.copy2(upload.file_path, str(new_path))

            # Write sidecar JSON metadata for worker queue (offset & limit)
            meta_path = settings.queue_incoming_dir / f"{filename}.meta.json"
            meta_data = {
                "upload_id": upload.id,
                "offset": upload.processed_records_count or 0,
                "limit": req.limit,
                "billing_run_id": run_id,
            }
            with open(meta_path, "w", encoding="utf-8") as meta_f:
                json.dump(meta_data, meta_f)

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


@router.get("/output/{date_str}/{cycle}/{batch}/{filename}")
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
    
    if new_status == TemplateApprovalStatus.APPROVED:
        all_pending = db.query(GmfUpload).filter(
            GmfUpload.status.in_([GmfUploadStatus.PENDING_APPROVAL, GmfUploadStatus.REJECTED])
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
            raw_detected = str(upload.template_detected or "")
            for char in ['(', ')', "'", '"']:
                raw_detected = raw_detected.replace(char, '')
            detected_list = [t.strip() for t in raw_detected.split(",") if t.strip() and not t.strip().isdigit()]

            if detected_list and not any(t in target_ids_set for t in detected_list):
                continue


            if upload.folder_type != "Test_GMFs":
                old_path = Path(upload.file_path)

                if billing_mode == "auto":
                    new_path = settings.queue_incoming_dir / upload.filename
                    if old_path.exists():
                        upload.status = GmfUploadStatus.APPROVED
                        upload.rejection_reason = None
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
                        upload.status = GmfUploadStatus.APPROVED
                        upload.rejection_reason = None
                        non_test_uploads.append(upload)
                else:
                    new_path = settings.queue_pending_dir / upload.filename
                    if old_path.exists():
                        upload.status = GmfUploadStatus.APPROVED
                        upload.rejection_reason = None
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
                        upload.status = GmfUploadStatus.APPROVED
                        upload.rejection_reason = None
                        upload.billing_run_id = None
            else:
                upload.status = GmfUploadStatus.APPROVED
                upload.rejection_reason = None

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
            GmfUpload.status.in_([GmfUploadStatus.PENDING_APPROVAL, GmfUploadStatus.APPROVED])
        ).all()
        for upload in candidate_uploads:
            raw_detected = str(upload.template_detected or "")
            for char in ['(', ')', "'", '"']:
                raw_detected = raw_detected.replace(char, '')
            detected_list = [t.strip() for t in raw_detected.split(",") if t.strip() and not t.strip().isdigit()]

            if detected_list and not any(t in target_ids_set for t in detected_list):
                continue


            if upload.folder_type != "Test_GMFs":
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
            upload.status = GmfUploadStatus.REJECTED
            upload.rejection_reason = body.reason

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
    return ext_clean in ("", "gmf", "zip", "xlsx", "csv") or ext_clean.isdigit()


def _background_register_staged_gmfs(staged_files: list[tuple[str, str]], folder_type: str, cleanup_dir: str):
    """Register uploaded GMFs after the HTTP request has already returned."""
    import logging
    import shutil
    from app.db.base import SessionLocal
    from app.db.models import GmfUpload, GmfUploadStatus, NotificationEvent, NotificationEventType, InvoiceTemplate, TemplateApprovalStatus
    from app.uploads.watcher import _detect_template, _get_cycle

    logger = logging.getLogger("gmf_upload")
    logger.setLevel(logging.INFO)

    cycle_number = _get_cycle(folder_type)
    is_test = folder_type in ("Test_GMFs", "LOD", "VAT_Confirmation")
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

            template_detected, total_records_count = _detect_template(str(source_path))
            template_status = templates_cache.get(template_detected)
            is_approved = (template_status == TemplateApprovalStatus.APPROVED)
            is_rejected = (template_status == TemplateApprovalStatus.REJECTED)

            if is_test:
                final_path = settings.gmf_drive_path / folder_type / filename
                final_status = GmfUploadStatus.PENDING_APPROVAL
                final_path.parent.mkdir(parents=True, exist_ok=True)
                if template_detected:
                    t_obj = db.query(InvoiceTemplate).filter(InvoiceTemplate.template_code == template_detected).first()
                    if not t_obj:
                        t_obj = InvoiceTemplate(template_code=template_detected, name=template_detected, is_system_template=True)
                        db.add(t_obj)
                    t_obj.approval_status = TemplateApprovalStatus.PENDING
                    templates_cache[template_detected] = TemplateApprovalStatus.PENDING

            elif is_approved:
                final_path = settings.queue_incoming_dir / filename
                final_status = GmfUploadStatus.APPROVED
            elif is_rejected:
                final_path = settings.queue_pending_dir / filename
                final_status = GmfUploadStatus.REJECTED
            else:
                final_path = settings.queue_pending_dir / filename
                final_status = GmfUploadStatus.PENDING_APPROVAL

            existing = db.query(GmfUpload).filter(
                GmfUpload.filename == filename,
                GmfUpload.folder_type == folder_type,
            ).first()
            if existing:
                if existing.status == GmfUploadStatus.COMPLETED:
                    logger.info(f"GMF {filename} in {folder_type} is already COMPLETED. Skipping duplicate invoice generation.")
                    if source_path.exists():
                        try:
                            source_path.unlink()
                        except Exception as rm_err:
                            logger.warning(f"Could not remove duplicate staged file {source_path}: {rm_err}")
                    registered_count += 1
                    continue

            from core.gmf_splitter import count_documents_with_breakdown
            total_cnt, breakdown = count_documents_with_breakdown(str(source_path))

            if existing:
                existing.file_path = str(final_path)
                existing.status = final_status
                existing.error_message = None
                existing.rejection_reason = None
                existing.billing_run_id = None
                existing.total_records_count = total_cnt
                existing.template_breakdown = json.dumps(breakdown) if breakdown else None
            else:
                db.add(GmfUpload(
                    filename=filename,
                    file_path=str(final_path),
                    folder_type=folder_type,
                    cycle_number=cycle_number,
                    template_detected=template_detected,
                    status=final_status,
                    total_records_count=total_cnt,
                    template_breakdown=json.dumps(breakdown) if breakdown else None,
                ))


            registered_count += 1
            move_plan.append((source_path, final_path, filename))

        db.commit()

        for source_path, final_path, filename in move_plan:
            try:
                final_path.parent.mkdir(parents=True, exist_ok=True)
                if final_path.exists():
                    final_path.unlink()
                shutil.move(str(source_path), str(final_path))
            except Exception as move_err:
                failed_count += 1
                logger.error("Failed to move staged GMF %s to %s: %s", filename, final_path, move_err)
                upload = db.query(GmfUpload).filter(
                    GmfUpload.filename == filename,
                    GmfUpload.folder_type == folder_type,
                ).first()
                if upload:
                    upload.status = GmfUploadStatus.FAILED
                    upload.error_message = f"Failed to stage uploaded file: {move_err}"

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
    from app.uploads.watcher import _detect_template, _get_cycle, _should_skip
    
    logger = logging.getLogger("gmf_upload")
    logger.setLevel(logging.INFO)
    
    cycle_number = _get_cycle(folder_type)
    is_test = folder_type in ("Test_GMFs", "LOD", "VAT_Confirmation")
    
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
            
            templates_cache = {t.template_code: t.approval_status for t in db.query(InvoiceTemplate).all()}
            
            for idx, file_path in enumerate(extracted_files):
                filename = file_path.name
                
                template_detected, total_records_count = _detect_template(str(file_path))
                is_approved = templates_cache.get(template_detected) == TemplateApprovalStatus.APPROVED if template_detected else False
                
                if is_test:
                    final_path = settings.gmf_drive_path / folder_type / filename
                    final_status = GmfUploadStatus.PENDING_APPROVAL
                    final_path.parent.mkdir(parents=True, exist_ok=True)
                else:
                    if is_approved:
                        final_path = settings.queue_incoming_dir / filename
                        final_status = GmfUploadStatus.APPROVED
                    else:
                        final_path = settings.queue_pending_dir / filename
                        final_status = GmfUploadStatus.PENDING_APPROVAL
                
                # 1. Update/Insert DB record FIRST
                existing = db.query(GmfUpload).filter(
                    GmfUpload.filename == filename,
                    GmfUpload.folder_type == folder_type
                ).first()
                if existing:
                    existing.file_path = str(final_path)
                    existing.status = final_status
                    existing.error_message = None
                    existing.rejection_reason = None
                    existing.billing_run_id = None
                    existing.template_detected = template_detected
                    existing.total_records_count = total_records_count
                else:
                    upload = GmfUpload(
                        filename=filename,
                        file_path=str(final_path),
                        folder_type=folder_type,
                        cycle_number=cycle_number,
                        template_detected=template_detected,
                        total_records_count=total_records_count,
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
    if folder_type not in ("Cycle_1", "Cycle_2", "Cycle_3", "Cycle_4", "Test_GMFs", "LOD", "VAT_Confirmation", "Final_Notice", "Customer_Letter", "Customer_Letter_Logo_V1Print"):
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
