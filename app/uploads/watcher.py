"""
GMF Folder Watcher — monitors the Google Drive SLT_GMF_Uploads folder.

Watches for ANY new file (GMF files have no extension).
Auto-detects the billing cycle from which sub-folder the file is in.
Auto-detects the invoice template using SmartAI_Bill's identifier.
Creates a GmfUpload record and a NotificationEvent record in the database.
"""
import logging
import os
import threading
import sys
import time
import json
import shutil
from datetime import datetime
import re
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.db.models import (
    GmfUpload, 
    GmfUploadStatus, 
    NotificationEvent, 
    NotificationEventType, 
    InvoiceTemplate, 
    TemplateApprovalStatus,
    SystemSetting
)
from app.core.config import settings

logger = logging.getLogger(__name__)

# Add SmartAI_Bill to sys.path so we can use the template identifier
_smartai_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../Models/SmartAI_Bill")
)
if _smartai_path not in sys.path:
    sys.path.insert(0, _smartai_path)

WATCH_DIR = settings.gmf_drive_path

# Valid folder names that correspond to billing cycles
CYCLE_FOLDERS = {
    "Cycle_1": 1,
    "Cycle_2": 2,
    "Cycle_3": 3,
    "Cycle_4": 4,
}
INCOMING_CYCLE_FOLDER = "Cycle"
NO_CYCLE_FOLDER = "No_Cycle"
TEST_FOLDER = "Test_GMFs"
LOD_FOLDER = "LOD"
VAT_CONF_FOLDER = "VAT_Confirmation"
FINAL_NOTICE_FOLDER = "Final_Notice"
CUSTOMER_LETTER_FOLDER = "Customer_Letter"
CUSTOMER_LETTER_ALT_FOLDER = "Customer_Letter_Logo_V1Print"
VALID_FOLDERS = set(CYCLE_FOLDERS.keys()) | {INCOMING_CYCLE_FOLDER, NO_CYCLE_FOLDER} | {
    TEST_FOLDER, 
    LOD_FOLDER, 
    VAT_CONF_FOLDER, 
    FINAL_NOTICE_FOLDER, 
    CUSTOMER_LETTER_FOLDER, 
    CUSTOMER_LETTER_ALT_FOLDER
}

# Files to skip (system/temp files)
SKIP_PREFIXES = (".", "~", "__")
SKIP_SUFFIXES = (".tmp", ".part", ".partial", ".crdownload")

# Lock to prevent concurrent DB writes
_process_lock = threading.Lock()


def _detect_template(file_path: str) -> tuple[str | None, int]:
    """Run SmartAI_Bill's template identifier across document blocks. Returns (template_summary, total_count)."""
    try:
        from core.gmf_splitter import split_gmf_documents, write_doc_to_temp, count_documents
        from core.template_identifier import identify_template
        import tempfile

        docs = split_gmf_documents(file_path)
        total_count = count_documents(file_path)
        detected_set = set()

        with tempfile.TemporaryDirectory(prefix="gmf_scan_") as tmp_dir:
            source_filename = os.path.basename(file_path)
            for idx, doc_lines in enumerate(docs, start=1):
                tmp_path = doc_lines if isinstance(doc_lines, str) and os.path.exists(doc_lines) else write_doc_to_temp(
                    doc_lines, tmp_dir, source_filename, idx)
                res = identify_template(tmp_path)
                if res.template_id:
                    detected_set.add(res.template_id)

        detected_list = sorted(list(detected_set))
        summary_str = ", ".join(detected_list) if detected_list else None
        return summary_str, total_count
    except Exception as e:
        logger.warning(f"Template identification failed for {file_path}: {e}")
        return None, 1


def _get_cycle(folder_name: str) -> int | None:
    """Return cycle number (1-4) from folder name, or None for Test_GMFs."""
    return CYCLE_FOLDERS.get(folder_name)


def _get_cycle_from_billdate(file_path: str | Path) -> int | None:
    """Return the cycle assigned to the first BILLDATE in a GMF file."""
    try:
        with Path(file_path).open("r", encoding="utf-8", errors="replace") as file:
            for line in file:
                match = re.match(r"^BILLDATE\s+([^|\s]+)", line.strip())
                if match:
                    bill_day = datetime.strptime(match.group(1), "%d/%m/%Y").day
                    for cycle, days in ((1, range(1, 4)), (2, range(8, 11)), (3, range(16, 19)), (4, range(24, 27))):
                        if bill_day in days:
                            return cycle
                    return None
    except (OSError, ValueError):
        return None
    return None


def _resolve_folder_type(folder_name: str, file_path: str | Path) -> str:
    """Normalize the incoming Cycle folder to a stored cycle or No_Cycle folder type."""
    if folder_name != INCOMING_CYCLE_FOLDER:
        return folder_name
    cycle_number = _get_cycle_from_billdate(file_path)
    return f"Cycle_{cycle_number}" if cycle_number else NO_CYCLE_FOLDER


def _get_billing_mode() -> str:
    """Query active billing mode from system settings."""
    try:
        with SessionLocal() as db:
            setting = db.query(SystemSetting).filter(SystemSetting.key == "billing_mode").first()
            return setting.value if setting else "auto"
    except Exception:
        return "auto"


def _should_skip(filename: str) -> bool:
    """Return True if this file should be ignored."""
    name = os.path.basename(filename).lower()
    # Skip Windows folder config and thumbnail database files
    if name in ("desktop.ini", "thumbs.db"):
        return True
    if any(name.startswith(p) for p in SKIP_PREFIXES):
        return True
    if any(name.endswith(s) for s in SKIP_SUFFIXES):
        return True
    ext = os.path.splitext(name)[1].lower()
    ext_clean = ext[1:] if ext.startswith(".") else ext
    if ext_clean and ext_clean not in ("gmf", "xlsx", "csv", "zip") and not ext_clean.isdigit():
        return True
    return False


class GmfFolderHandler(FileSystemEventHandler):
    """Handles file creation events inside the GMF watch directory."""

    def on_created(self, event):
        if event.is_directory:
            return

        filepath = Path(event.src_path)
        filename = filepath.name
        folder_name = filepath.parent.name

        # Skip temp/system files
        if _should_skip(filename):
            return

        # Only process files inside valid sub-folders
        if folder_name not in VALID_FOLDERS:
            logger.debug(f"Skipping file in unrecognised folder '{folder_name}': {filename}")
            return

        logger.info(f"Detected new file: {filepath} (folder: {folder_name}). Offloading to thread...")

        # Spawn a thread to prevent blocking the watchdog observer for other files
        t = threading.Thread(target=self._process_file, args=(filepath, filename, folder_name))
        t.start()

    def on_moved(self, event):
        if event.is_directory:
            return

        filepath = Path(event.dest_path)
        filename = filepath.name
        folder_name = filepath.parent.name

        # Skip temp/system files
        if _should_skip(filename):
            return

        # Only process files inside valid sub-folders
        if folder_name not in VALID_FOLDERS:
            return

        logger.info(f"Detected newly synced file: {filepath} (folder: {folder_name}). Offloading to thread...")

        t = threading.Thread(target=self._process_file, args=(filepath, filename, folder_name))
        t.start()

    def _process_file(self, filepath: Path, filename: str, folder_name: str):
        # Wait briefly to ensure the file has finished copying
        time.sleep(0.1)

        if not filepath.exists():
            logger.warning(f"File disappeared before processing: {filepath}")
            return

        # Auto-detect billing cycle from BILLDATE in the shared Cycle folder.
        resolved_folder_name = _resolve_folder_type(folder_name, filepath)
        folder_name = resolved_folder_name
        cycle_number = _get_cycle(folder_name)
        is_test = folder_name == TEST_FOLDER

        # Auto-detect invoice templates and total document count
        template_detected, total_records_count = _detect_template(str(filepath))
        logger.info(f"Templates identified: {template_detected} (Total docs: {total_records_count})")

        with _process_lock:
            with SessionLocal() as db:
                try:
                    # Avoid duplicate records
                    existing = db.query(GmfUpload).filter(
                        GmfUpload.filename == filename,
                        GmfUpload.folder_type == folder_name
                    ).first()
                    
                    if existing:
                        if existing.status == GmfUploadStatus.COMPLETED:
                            logger.info(f"GMF {filename} in {folder_name} is already COMPLETED. Skipping duplicate watcher registration.")
                            return
                            
                        if existing.status in (GmfUploadStatus.FAILED, GmfUploadStatus.REJECTED, GmfUploadStatus.PENDING_APPROVAL):
                            is_approved = False
                            if is_test:
                                new_filepath = filepath
                                final_status = GmfUploadStatus.PENDING_APPROVAL
                                if template_detected:
                                    template_obj = db.query(InvoiceTemplate).filter(InvoiceTemplate.template_code == template_detected).first()
                                    if not template_obj:
                                        template_obj = InvoiceTemplate(template_code=template_detected, name=template_detected, is_system_template=True)
                                        db.add(template_obj)
                                    template_obj.approval_status = TemplateApprovalStatus.PENDING
                                    # Reset any previously REJECTED real GMFs for this template back to PENDING_APPROVAL
                                    db.query(GmfUpload).filter(
                                        GmfUpload.template_detected == template_detected,
                                        GmfUpload.folder_type != TEST_FOLDER,
                                        GmfUpload.status == GmfUploadStatus.REJECTED
                                    ).update({"status": GmfUploadStatus.PENDING_APPROVAL, "rejection_reason": None}, synchronize_session=False)
                            else:
                                detected_list = [t.strip() for t in (template_detected or "").split(",") if t.strip()]
                                approved_set = set(
                                    t.template_code for t in db.query(InvoiceTemplate).filter(InvoiceTemplate.approval_status == TemplateApprovalStatus.APPROVED).all()
                                )
                                rejected_set = set(
                                    t.template_code for t in db.query(InvoiceTemplate).filter(InvoiceTemplate.approval_status == TemplateApprovalStatus.REJECTED).all()
                                )
                                is_approved = bool(detected_list) and any(t in approved_set for t in detected_list)
                                is_rejected = bool(detected_list) and any(t in rejected_set for t in detected_list)

                                settings.queue_incoming_dir.mkdir(parents=True, exist_ok=True)
                                settings.queue_pending_dir.mkdir(parents=True, exist_ok=True)
                                
                                billing_mode = _get_billing_mode()
                                if is_approved and billing_mode == "auto":
                                    new_filepath = settings.queue_incoming_dir / filename
                                    final_status = GmfUploadStatus.APPROVED
                                elif is_approved and billing_mode == "manual":
                                    new_filepath = settings.queue_pending_dir / filename
                                    final_status = GmfUploadStatus.APPROVED
                                elif is_rejected:
                                    new_filepath = settings.queue_pending_dir / filename
                                    final_status = GmfUploadStatus.REJECTED
                                else:
                                    new_filepath = settings.queue_pending_dir / filename
                                    final_status = GmfUploadStatus.PENDING_APPROVAL
                                
                                try:
                                    if filepath.exists() and filepath != new_filepath:
                                        if new_filepath.exists():
                                            new_filepath.unlink()
                                        shutil.move(str(filepath), str(new_filepath))
                                    existing.file_path = str(new_filepath)
                                except Exception as move_err:
                                    logger.error(f"Failed to move file {filename} during re-registration: {move_err}")
                                    return
                                    
                            existing.status = final_status
                            existing.error_message = None
                            existing.rejection_reason = None
                            existing.billing_run_id = None
                            
                            # Create notification event
                            if is_test:
                                notif = NotificationEvent(
                                    event_type=NotificationEventType.TEST_GMF_RECEIVED,
                                    title="Test GMF Re-uploaded",
                                    message=(
                                        f"Test GMF file '{filename}' has been re-uploaded and is ready "
                                        f"for preview. Template detected: {template_detected or 'Unknown'}."
                                    ),
                                    upload_id=existing.id,
                                )
                            else:
                                if is_approved:
                                    notif_title = f"GMF Auto-Approved — Cycle {cycle_number}"
                                    notif_msg = f"Re-uploaded GMF file '{filename}' (Template: {template_detected}) was auto-approved and queued for generation."
                                else:
                                    notif_title = f"GMF Re-uploaded — Cycle {cycle_number}"
                                    notif_msg = f"Re-uploaded GMF file '{filename}' (Template: {template_detected or 'Unknown'}) awaiting template approval."
                                
                                notif = NotificationEvent(
                                    event_type=NotificationEventType.GMF_DETECTED,
                                    title=notif_title,
                                    message=notif_msg,
                                    upload_id=existing.id,
                                )
                            db.add(notif)
                            db.commit()
                            logger.info(f"Re-registered GMF (reset status to {final_status.value}): {filename}")
                        else:
                            logger.info(f"Already registered (currently in status {existing.status.value}): {filename}")
                        return

                    detected_list = [t.strip() for t in (template_detected or "").split(",") if t.strip()]
                    approved_set = set(
                        t.template_code for t in db.query(InvoiceTemplate).filter(InvoiceTemplate.approval_status == TemplateApprovalStatus.APPROVED).all()
                    )
                    rejected_set = set(
                        t.template_code for t in db.query(InvoiceTemplate).filter(InvoiceTemplate.approval_status == TemplateApprovalStatus.REJECTED).all()
                    )
                    is_approved = bool(detected_list) and any(t in approved_set for t in detected_list)
                    is_rejected = bool(detected_list) and any(t in rejected_set for t in detected_list)

                    if is_test:
                        new_filepath = filepath
                        final_status = GmfUploadStatus.PENDING_APPROVAL
                        if template_detected:
                            template_obj = db.query(InvoiceTemplate).filter(InvoiceTemplate.template_code == template_detected).first()
                            if not template_obj:
                                template_obj = InvoiceTemplate(template_code=template_detected, name=template_detected, is_system_template=True)
                                db.add(template_obj)
                            template_obj.approval_status = TemplateApprovalStatus.PENDING
                            # Reset any previously REJECTED real GMFs for this template back to PENDING_APPROVAL
                            db.query(GmfUpload).filter(
                                GmfUpload.template_detected == template_detected,
                                GmfUpload.folder_type != TEST_FOLDER,
                                GmfUpload.status == GmfUploadStatus.REJECTED
                            ).update({"status": GmfUploadStatus.PENDING_APPROVAL, "rejection_reason": None}, synchronize_session=False)
                    else:
                        # Ensure directories exist
                        settings.queue_incoming_dir.mkdir(parents=True, exist_ok=True)
                        settings.queue_pending_dir.mkdir(parents=True, exist_ok=True)
                        
                        billing_mode = _get_billing_mode()
                        if is_approved and billing_mode == "auto":
                            new_filepath = settings.queue_incoming_dir / filename
                            final_status = GmfUploadStatus.APPROVED
                        elif is_approved and billing_mode == "manual":
                            new_filepath = settings.queue_pending_dir / filename
                            final_status = GmfUploadStatus.APPROVED
                        elif is_rejected:
                            new_filepath = settings.queue_pending_dir / filename
                            final_status = GmfUploadStatus.REJECTED
                        else:
                            new_filepath = settings.queue_pending_dir / filename
                            final_status = GmfUploadStatus.PENDING_APPROVAL
                            
                        # Move the file from Google Drive to the VM local queue
                        try:
                            if new_filepath.exists():
                                new_filepath.unlink()
                            shutil.move(str(filepath), str(new_filepath))
                            logger.info(f"Moved {filename} to {new_filepath}")
                        except Exception as move_err:
                            logger.error(f"Failed to move file {filename}: {move_err}")
                            return

                    from core.gmf_splitter import count_documents_with_breakdown
                    total_cnt, breakdown = count_documents_with_breakdown(str(new_filepath))
                    upload = GmfUpload(
                        filename=filename,
                        file_path=str(new_filepath),
                        folder_type=folder_name,
                        cycle_number=cycle_number,
                        template_detected=template_detected,
                        total_records_count=total_records_count,  # Using the parameter value, NOT the count from breakdown
                        status=final_status,
                        template_breakdown=json.dumps(breakdown) if breakdown else None,
                    )

                    db.add(upload)
                    db.flush()  # get upload.id

                    # Create notification event
                    if is_test:
                        notif = NotificationEvent(
                            event_type=NotificationEventType.TEST_GMF_RECEIVED,
                            title="Test GMF Received",
                            message=(
                                f"Test GMF file '{filename}' has been received and is ready "
                                f"for preview. Template detected: {template_detected or 'Unknown'}."
                            ),
                            upload_id=upload.id,
                        )
                    else:
                        if is_approved:
                            notif_title = f"GMF Auto-Approved — Cycle {cycle_number}"
                            notif_msg = f"New GMF file '{filename}' (Template: {template_detected}) was auto-approved and queued for generation."
                        else:
                            notif_title = f"GMF Detected — Cycle {cycle_number}"
                            notif_msg = f"New GMF file '{filename}' (Template: {template_detected or 'Unknown'}) awaiting template approval."
                            
                        notif = NotificationEvent(
                            event_type=NotificationEventType.GMF_DETECTED,
                            title=notif_title,
                            message=notif_msg,
                            upload_id=upload.id,
                        )
                    db.add(notif)
                    db.commit()

                    logger.info(
                        f"Registered GMF: {filename} | cycle={cycle_number} | "
                        f"template={template_detected}"
                    )
                except Exception as e:
                    db.rollback()
                    logger.error(f"Error saving GMF upload to DB: {e}", exc_info=True)


def _scan_existing_files(watch_path: Path):
    """Scan for files that already exist in the watch directory and register any
    that are not yet in the database.  This covers files uploaded while the
    watcher was not running (or events that Google Drive's virtual filesystem
    failed to deliver)."""
    handler = GmfFolderHandler()
    with SessionLocal() as db:
        known_uploads = {
            (row.filename, row.folder_type): row.status
            for row in db.query(GmfUpload.filename, GmfUpload.folder_type, GmfUpload.status).all()
        }

    for subfolder in watch_path.iterdir():
        if not subfolder.is_dir():
            continue
        folder_name = subfolder.name
        if folder_name not in VALID_FOLDERS:
            continue
        for file in subfolder.iterdir():
            if not file.is_file() or _should_skip(file.name):
                continue
            existing_status = known_uploads.get((file.name, folder_name))
            if existing_status and existing_status != GmfUploadStatus.FAILED:
                continue
            logger.info(f"Drive scan processing file: {file}")
            handler._process_file(file, file.name, folder_name)


def _periodic_scan_loop(watch_path: Path):
    """Recover Drive/rclone files when filesystem events are missed."""
    interval = max(1, int(settings.gmf_scan_interval_seconds))
    while True:
        time.sleep(interval)
        try:
            _scan_existing_files(watch_path)
        except Exception as err:
            logger.error(f"Periodic GMF scan failed: {err}", exc_info=True)


def start_watcher():
    """Start monitoring the GMF upload folder."""
    watch_path = WATCH_DIR

    if not watch_path.exists():
        logger.warning(f"Watch directory does not exist, creating: {watch_path}")
        watch_path.mkdir(parents=True, exist_ok=True)
    (watch_path / INCOMING_CYCLE_FOLDER).mkdir(parents=True, exist_ok=True)
    (watch_path / NO_CYCLE_FOLDER).mkdir(parents=True, exist_ok=True)

    # First, pick up any files that were uploaded while the watcher was stopped
    logger.info("Running startup scan for existing files...")
    _scan_existing_files(watch_path)
    logger.info("Startup scan complete.")

    scan_thread = threading.Thread(target=_periodic_scan_loop, args=(watch_path,), daemon=True)
    scan_thread.start()
    logger.info(f"Periodic GMF scan enabled every {settings.gmf_scan_interval_seconds} seconds.")

    handler = GmfFolderHandler()
    observer = Observer()
    observer.schedule(handler, str(watch_path), recursive=True)
    observer.start()

    logger.info(f"Watching for GMF files in: {watch_path}")
    logger.info(f"Valid folders: {sorted(VALID_FOLDERS)}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    start_watcher()