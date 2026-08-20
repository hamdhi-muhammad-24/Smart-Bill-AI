import time
import os
import shutil
import logging
import multiprocessing
import sys
import json
import inspect
import threading
from pathlib import Path
from datetime import datetime

# Add Models/SmartAI_Bill to sys.path
_smartai_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../Models/SmartAI_Bill"))
if _smartai_path not in sys.path:
    sys.path.insert(0, _smartai_path)

from app.db.base import SessionLocal
from app.db.models import GmfUpload, GmfUploadStatus, InvoiceTemplate, TemplateApprovalStatus, BillingRun, BillingRunFailure, RunStatus
from app.core.config import settings
from processing.output_manager import create_output_batches
from config import OUTPUT_PDF_NAMES, OUTPUT_PDF_NAME_DEFAULT
from sqlalchemy import update as sql_update, or_
from core.self_seal_appender import get_approved_self_seal_pdf, apply_self_seal_to_directory

logger = logging.getLogger("worker_queue")
logger.setLevel(logging.INFO)

COMPLETED_TEMP = Path("./queue/completed_temp")

TEMPLATE_FOLDER_MAP = {
    "lod": "LOD",
    "vat_confirmation": "VAT_Confirmation",
    "final_notice": "Final_Notice",
    "customer_letter_logo_v1print": "Customer_Letter",
    "customer_migration_letter": "Customer_Letter",
    "customer_letter": "Customer_Letter",
    "vat_home": "VAT_Home",
    "nonvat_home": "NonVAT_Home",
    "vat_enterprise": "VAT_Enterprise",
    "nonvat_enterprise": "NonVAT_Enterprise",
    "vat_gov": "VAT_Gov",
    "nonvat_gov": "NonVAT_Gov",
    "vat_creditnote": "VAT_CreditNote",
    "nonvat_creditnote": "NonVAT_CreditNote",
    "product_label_grouping": "Product_Label_Grouping",
    "summary_statement": "Summary_Statement",
    "usd_open_item": "USD_Open_Item"
}

def _robust_file_op(func, *args, max_retries=5, delay=0.5):
    """Retries a file operation to overcome transient Windows file locks (WinError 32)."""
    last_err = None
    for _ in range(max_retries):
        try:
            return func(*args)
        except OSError as e:
            last_err = e
            time.sleep(delay)
    raise last_err

def _get_approved_templates():
    """Fetch set of currently APPROVED templates from DB."""
    approved_templates = set()
    try:
        with SessionLocal() as db:
            app_tmpls = db.query(InvoiceTemplate).filter(
                InvoiceTemplate.approval_status == TemplateApprovalStatus.APPROVED
            ).all()
            approved_templates = {t.template_code for t in app_tmpls}
            if "customer_letter_logo_v1print" in approved_templates:
                approved_templates.add("customer_migration_letter")
                approved_templates.add("customer_letter")
    except Exception as e:
        logger.warning(f"Could not load approved templates: {e}")
    return approved_templates

def _get_active_templates():
    """Get active templates from DB including system defaults unless rejected."""
    with SessionLocal() as db:
        db_templates = db.query(InvoiceTemplate).filter(
            or_(InvoiceTemplate.is_active == True, 
                InvoiceTemplate.approval_status != TemplateApprovalStatus.REJECTED)
        ).all()
        active_templates = set(t.template_code for t in db_templates)
        # Include standard system templates by default unless explicitly rejected
        all_sys = (
            "lod", "vat_confirmation", "final_notice",
            "customer_letter_logo_v1print", "customer_migration_letter", "customer_letter",
            "nonvat_home", "nonvat_enterprise", "vat_enterprise", "vat_home",
            "product_label_grouping", "subscription_ref_grouping", "summary_statement",
            "invoice_of_summary", "vat_creditnote", "nonvat_creditnote", "usd_open_item"
        )
        for sys_tid in all_sys:
            t_obj = next((t for t in db_templates if t.template_code == sys_tid), None)
            if not t_obj or t_obj.approval_status != TemplateApprovalStatus.REJECTED:
                active_templates.add(sys_tid)
    return active_templates

def _resolve_cycle_folder(upload):
    """Resolve cycle folder name from upload record."""
    cycle_num = getattr(upload, "cycle_number", None)
    f_type = str(getattr(upload, "folder_type", None) or "").strip()

    if cycle_num and isinstance(cycle_num, int) and 1 <= cycle_num <= 4:
        return f"Cycle_{cycle_num}"
    elif f_type in ("LOD", "VAT_Confirmation", "Test_GMFs", "Final_Notice", "Customer_Letter"):
        return f_type
    elif f_type in ("Customer_Letter_Logo_V1Print", "Customer_Migration_Letter", "customer_letter"):
        return "Customer_Letter"
    elif "cycle" in f_type.lower():
        import re
        match = re.search(r'(\d+)', f_type)
        return f"Cycle_{match.group(1)}" if match else f_type.replace(" ", "_")
    else:
        t_id = getattr(upload, "template_detected", None)
        if t_id and t_id in TEMPLATE_FOLDER_MAP:
            return TEMPLATE_FOLDER_MAP[t_id]
        return f_type.replace(" ", "_") if f_type else "Cycle_1"

def _get_batch_folder(base_dir: Path, max_per_batch: int = 10) -> Path:
    """Get next available batch folder with space for more PDFs."""
    b_num = 1
    while True:
        b_dir = base_dir / f"Batch_{b_num}"
        b_dir.mkdir(parents=True, exist_ok=True)
        pdf_count = len([f for f in b_dir.iterdir() if f.is_file() and f.name.lower().endswith(".pdf")])
        if pdf_count < max_per_batch:
            return b_dir
        b_num += 1

def _read_metadata_file(incoming_dir, filename):
    """Read and parse metadata JSON file if it exists."""
    meta_file = incoming_dir / f"{filename}.meta.json"
    meta_data = {}
    if meta_file.exists():
        try:
            with open(meta_file, "r", encoding="utf-8") as mf:
                meta_data = json.load(mf)
            _robust_file_op(meta_file.unlink)
        except Exception as e:
            logger.warning(f"Could not read meta file {meta_file}: {e}")
    return meta_data

def _lookup_upload_record(filename, meta_upload_id=None, run_id=None):
    """Look up GmfUpload record with retries for delayed transaction commits."""
    upload = None
    for retry in range(3):
        with SessionLocal() as db:
            if meta_upload_id:
                upload = db.query(GmfUpload).filter(GmfUpload.id == meta_upload_id).first()
            if not upload:
                query = db.query(GmfUpload).filter(
                    GmfUpload.filename == filename,
                    GmfUpload.folder_type != "Test_GMFs"
                )
                if run_id:
                    query = query.filter(GmfUpload.billing_run_id == run_id)
                upload = query.first()
        if upload:
            break
        time.sleep(1)
    return upload

def _update_billing_run(db, run_id, generated_count, cycle_base_dir=None):
    """Update BillingRun with generated count and check completion status."""
    if not run_id:
        return
    
    db.execute(
        sql_update(BillingRun)
        .where(BillingRun.id == run_id)
        .values(succeeded=BillingRun.succeeded + generated_count)
    )
    db.flush()
    
    run = db.query(BillingRun).filter(BillingRun.id == run_id).first()
    if run:
        if cycle_base_dir:
            run.output_path = str(cycle_base_dir)
        if run.succeeded + run.failed >= run.total_accounts:
            run.total_accounts = run.succeeded + run.failed
            run.status = RunStatus.DONE if run.failed == 0 else RunStatus.PARTIAL
            run.finished_at = datetime.now()

def _create_billing_run(db, upload, filename, offset, limit):
    """Create a new BillingRun for the upload."""
    tot_acc = (upload.total_records_count or 1) - (offset or 0)
    if limit:
        tot_acc = min(tot_acc, limit)
    tot_acc = max(1, tot_acc)
    
    run = BillingRun(
        batch_name=f"Auto Gen {filename} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        cycle_number=upload.cycle_number,
        period_start=datetime.now().date(),
        period_end=datetime.now().date(),
        status=RunStatus.RUNNING,
        total_accounts=tot_acc,
        succeeded=0,
        failed=0,
        started_at=datetime.now()
    )
    db.add(run)
    db.flush()
    upload.billing_run_id = run.id
    db.commit()
    return run.id

def _handle_failed_upload(filename, working_path, upload_id, run_id, error_message):
    """Handle failed upload by moving to Failed folder and updating DB."""
    try:
        # Get cycle_label from DB
        cycle_label = "unknown"
        local_run_id = run_id
        
        with SessionLocal() as db:
            upload = None
            if upload_id:
                upload = db.query(GmfUpload).filter(GmfUpload.id == upload_id).first()
            if not upload and local_run_id:
                upload = db.query(GmfUpload).filter(
                    GmfUpload.filename == filename,
                    GmfUpload.billing_run_id == local_run_id,
                    GmfUpload.folder_type != "Test_GMFs"
                ).first()
            if not upload:
                upload = db.query(GmfUpload).filter(
                    GmfUpload.filename == filename,
                    GmfUpload.status == GmfUploadStatus.APPROVED,
                    GmfUpload.folder_type != "Test_GMFs"
                ).first()
            if upload:
                cycle_label = upload.folder_type
                local_run_id = upload.billing_run_id
                upload_id = upload.id
                
        failed_dest = settings.gmf_drive_path / "Failed" / (cycle_label or "unknown")
        failed_dest.mkdir(parents=True, exist_ok=True)
        dest_file_path = failed_dest / filename
        if dest_file_path.exists():
            try:
                _robust_file_op(dest_file_path.unlink)
            except Exception as rm_err:
                logger.warning(f"Could not remove existing failed GMF file {dest_file_path}: {rm_err}")
        
        # Move to failed queue
        if os.path.exists(working_path):
            _robust_file_op(shutil.move, str(working_path), str(dest_file_path))
        
        # Delete from remote Google Drive Cycle folder
        try:
            if shutil.which("rclone"):
                subprocess.Popen(["rclone", "deletefile", f"gdrive:SLT_GMF_Uploads/{cycle_label}/{filename}"])
            else:
                logger.info("rclone not available in container; host sync service will clean remote GMF %s", filename)
        except Exception as delete_err:
            logger.error(f"Failed to launch rclone delete for {filename}: {delete_err}")
            
        with SessionLocal() as db:
            upload = None
            if upload_id:
                upload = db.query(GmfUpload).filter(GmfUpload.id == upload_id).first()
            if not upload and local_run_id:
                upload = db.query(GmfUpload).filter(
                    GmfUpload.filename == filename,
                    GmfUpload.billing_run_id == local_run_id,
                    GmfUpload.folder_type != "Test_GMFs"
                ).first()
            if not upload:
                upload = db.query(GmfUpload).filter(
                    GmfUpload.filename == filename,
                    GmfUpload.status == GmfUploadStatus.APPROVED,
                    GmfUpload.folder_type != "Test_GMFs"
                ).first()
                
            if upload:
                upload.status = GmfUploadStatus.FAILED
                upload.error_message = error_message
                upload.file_path = str(dest_file_path)
                
                if upload.billing_run_id:
                    db.execute(
                        sql_update(BillingRun)
                        .where(BillingRun.id == upload.billing_run_id)
                        .values(failed=BillingRun.failed + 1)
                    )
                    db.add(BillingRunFailure(
                        billing_run_id=upload.billing_run_id,
                        account_number=filename,
                        error_message=error_message
                    ))
                    db.flush()
                    
                    run = db.query(BillingRun).filter(BillingRun.id == upload.billing_run_id).first()
                    if run and run.succeeded + run.failed >= run.total_accounts:
                        run.status = RunStatus.DONE if run.failed == 0 else RunStatus.PARTIAL
                        run.finished_at = datetime.now()
            db.commit()
    except Exception as inner_err:
        logger.error(f"Failed to record failure details: {inner_err}")

def _delete_from_remote(cycle_label, filename):
    """Delete file from remote Google Drive using rclone."""
    try:
        import subprocess
        if shutil.which("rclone"):
            subprocess.Popen(["rclone", "deletefile", f"gdrive:SLT_GMF_Uploads/{cycle_label}/{filename}"])
        else:
            logger.info("rclone not available in container; host sync service will clean remote GMF %s", filename)
    except Exception as delete_err:
        logger.error(f"Failed to launch rclone delete for {filename}: {delete_err}")

def _worker_process(worker_id):
    """
    Parallel worker process that generates PDFs from GMFs in the incoming queue.
    """
    # Imports must be inside the process to avoid multiprocessing pickling issues
    from core.template_identifier import identify_template
    from templates.registry import get_renderer, get_parser
    from core.gmf_splitter import split_gmf_documents, count_documents
    from processing.batch_processor import process_single_file
    
    logger.info(f"Worker {worker_id} started")
    COMPLETED_TEMP.mkdir(parents=True, exist_ok=True)
    
    while True:
        filename = None
        working_path = None
        upload_id = None
        run_id = None
        try:
            start_time = time.time()
            
            incoming_dir = settings.queue_incoming_dir
            if not incoming_dir.exists():
                time.sleep(1)
                continue
                
            files = [
                f for f in incoming_dir.iterdir()
                if f.is_file()
                and not f.name.startswith(".")
                and not f.name.endswith(".processing")
                and not f.name.endswith(".meta.json")
            ]
            
            if not files:
                time.sleep(1)
                continue
                
            # Pick a file
            file_path = files[0]
            working_path = incoming_dir / (file_path.name + ".processing")
            
            # Atomic rename to claim the file
            try:
                _robust_file_op(os.rename, file_path, working_path, max_retries=3, delay=0.2)
            except OSError:
                time.sleep(0.1)
                continue

            filename = file_path.name
            logger.info(f"Worker {worker_id} processing {filename}")

            # Read metadata file
            meta_data = _read_metadata_file(incoming_dir, filename)
            meta_upload_id = meta_data.get("upload_id")
            raw_offset = meta_data.get("offset", 0)
            raw_limit = meta_data.get("limit")
            try:
                offset = int(raw_offset) if raw_offset is not None else 0
            except (ValueError, TypeError):
                offset = 0
            try:
                limit = int(raw_limit) if raw_limit is not None else None
            except (ValueError, TypeError):
                limit = None

            # DB lookup
            upload = _lookup_upload_record(filename, meta_upload_id)
            if not upload:
                logger.warning(f"No DB record for {filename} after retries, deleting orphan file")
                if os.path.exists(working_path):
                    try:
                        _robust_file_op(os.remove, working_path)
                    except OSError as rm_err:
                        logger.error(f"Could not remove orphan file {working_path}: {rm_err}")
                continue
                
            upload_id = upload.id
            cycle_label = upload.folder_type
            template_id = upload.template_detected
            run_id = upload.billing_run_id or meta_data.get("billing_run_id")

            if not template_id:
                logger.error(f"Cannot process {filename}: template unknown")
                try:
                    _robust_file_op(os.remove, working_path)
                except OSError as err:
                    logger.error(f"Could not remove {working_path}: {err}")
                with SessionLocal() as db:
                    upload = db.query(GmfUpload).filter(
                        GmfUpload.filename == filename,
                        GmfUpload.billing_run_id == run_id,
                        GmfUpload.folder_type != "Test_GMFs"
                    ).first()
                    if upload:
                        upload.status = GmfUploadStatus.FAILED
                        upload.error_message = "Template unknown"
                        
                        if upload.billing_run_id:
                            db.execute(
                                sql_update(BillingRun)
                                .where(BillingRun.id == upload.billing_run_id)
                                .values(failed=BillingRun.failed + 1)
                            )
                            db.add(BillingRunFailure(
                                billing_run_id=upload.billing_run_id, 
                                account_number=filename, 
                                error_message="Template unknown"
                            ))
                            db.flush()
                            run = db.query(BillingRun).filter(BillingRun.id == upload.billing_run_id).first()
                            if run and run.succeeded + run.failed >= run.total_accounts:
                                run.status = RunStatus.DONE if run.failed == 0 else RunStatus.PARTIAL
                                run.finished_at = datetime.now()
                        db.commit()
                continue
                
            # Resolve cycle folder name
            folder_name = _resolve_cycle_folder(upload)
            cycle_label = folder_name

            # Get active and approved templates
            active_templates = _get_active_templates()
            meta_approved = meta_data.get("approved_templates") if isinstance(meta_data, dict) else None
            if meta_approved:
                approved_templates = set(meta_approved)
            else:
                approved_templates = _get_approved_templates()

            # Setup output directory
            today_str = datetime.now().strftime("%Y-%m-%d")
            cycle_base_dir = settings.output_dir / today_str / folder_name
            cycle_base_dir.mkdir(parents=True, exist_ok=True)

            # Create BillingRun if needed
            if not run_id:
                try:
                    with SessionLocal() as db:
                        u_rec = db.query(GmfUpload).filter(GmfUpload.id == upload_id).first()
                        if u_rec:
                            run_id = _create_billing_run(db, u_rec, filename, offset, limit)
                except Exception as create_run_err:
                    logger.warning(f"Could not create BillingRun for {filename}: {create_run_err}")

            # Process the GMF file
            import tempfile
            import shutil
            with tempfile.TemporaryDirectory(prefix="gmf_pdf_gen_") as temp_pdf_dir:
                args = (str(working_path), temp_pdf_dir, 1, False, approved_templates, offset, limit)
                results = process_single_file(args)

                # ── Self-Seal envelope post-processing ─────────────────────
                # If an approved Self-Seal artwork exists, append its composite
                # PDF as page 2 to every 1-page bill in the temp directory.
                # Excluded templates (LOD, VAT Confirmation, Final Notice,
                # Customer Letter) are skipped automatically by the appender.
                approved_self_seal_pdf = get_approved_self_seal_pdf()
                if approved_self_seal_pdf:
                    apply_self_seal_to_directory(
                        temp_pdf_dir,
                        template_id,
                        approved_self_seal_pdf,
                    )
                # ───────────────────────────────────────────────────────────

                # Copy generated files to output folder
                pdf_files = list(Path(temp_pdf_dir).glob("*.pdf"))
                for file_path in pdf_files:
                    shutil.copy2(file_path, cycle_base_dir / file_path.name)
                
                generated_count = len(pdf_files)
                total_count = len(results)
            
            # Move source GMF to Processed/Staged folder and update DB
            try:
                with SessionLocal() as db:
                    upload = db.query(GmfUpload).filter(GmfUpload.id == upload_id).first()
                    if upload:
                        upload.processed_records_count = (upload.processed_records_count or 0) + generated_count
                        if not upload.total_records_count or upload.total_records_count <= 1:
                            try:
                                real_total = count_documents(str(working_path))
                                upload.total_records_count = max(real_total, total_count)
                            except Exception:
                                upload.total_records_count = max(upload.total_records_count or 0, total_count)

                        if upload.processed_records_count >= upload.total_records_count and upload.total_records_count > 0:
                            processed_dest = settings.gmf_drive_path / "Processed" / (cycle_label or "unknown")
                            processed_dest.mkdir(parents=True, exist_ok=True)
                            dest_file_path = processed_dest / filename
                            if dest_file_path.exists():
                                try:
                                    dest_file_path.unlink()
                                except Exception:
                                    pass
                            if os.path.exists(working_path):
                                try:
                                    shutil.move(str(working_path), str(dest_file_path))
                                    upload.file_path = str(dest_file_path)
                                except Exception as mv_err:
                                    logger.warning(f"Could not move file {working_path} to {dest_file_path}: {mv_err}")

                            upload.status = GmfUploadStatus.COMPLETED
                            upload.billing_run_id = None
                        else:
                            staged_dest = settings.gmf_drive_path / "Staged"
                            staged_dest.mkdir(parents=True, exist_ok=True)
                            dest_file_path = staged_dest / filename
                            if str(working_path) != str(dest_file_path):
                                if dest_file_path.exists():
                                    try:
                                        dest_file_path.unlink()
                                    except Exception:
                                        pass
                                if os.path.exists(working_path):
                                    try:
                                        shutil.move(str(working_path), str(dest_file_path))
                                    except Exception as mv_err:
                                        logger.warning(f"Could not move file {working_path} to {dest_file_path}: {mv_err}")

                            upload.status = GmfUploadStatus.PARTIALLY_PROCESSED if upload.processed_records_count > 0 else GmfUploadStatus.APPROVED
                            upload.file_path = str(dest_file_path)
                            upload.billing_run_id = None
                            
                        upload.processed_at = datetime.now()
                        
                        run_id_to_update = run_id or upload.billing_run_id
                        if run_id_to_update:
                            _update_billing_run(db, run_id_to_update, generated_count, cycle_base_dir)
                        
                        db.commit()
            except Exception as move_err:
                logger.error(f"Failed to move completed GMF {filename} to Processed: {move_err}")
                if os.path.exists(working_path):
                    try:
                        _robust_file_op(os.remove, working_path)
                    except OSError as err:
                        logger.error(f"Could not remove {working_path} after move failure: {err}")
            
            # Delete from remote
            _delete_from_remote(cycle_label, filename)
                
            logger.info(f"Worker {worker_id} successfully generated {generated_count} PDF(s) for {filename}")
            
            # Throttle
            elapsed = time.time() - start_time
            if elapsed < 0.2:
                time.sleep(0.2 - elapsed)
                
        except Exception as e:
            logger.error(f"Worker {worker_id} error: {e}", exc_info=True)
            if filename and working_path is not None and working_path.exists():
                _handle_failed_upload(filename, str(working_path), upload_id, run_id, str(e))
            time.sleep(1)


def _archiver_process():
    """
    Periodically checks the COMPLETED_TEMP dir and moves PDFs to the final structured archive.
    """
    logger.info("Archiver process started")
    while True:
        try:
            if COMPLETED_TEMP.exists():
                for cycle_dir in COMPLETED_TEMP.iterdir():
                    if cycle_dir.is_dir() and any(f.name.endswith(".pdf") for f in cycle_dir.iterdir()):
                        create_output_batches(str(cycle_dir), cycle_label=cycle_dir.name)
            time.sleep(2)
        except Exception as e:
            logger.error(f"Archiver error: {e}", exc_info=True)
            time.sleep(5)


def start_worker_threads(num_workers=4):
    """
    Starts worker daemon threads directly inside the application process.
    """
    threads = []
    for i in range(num_workers):
        t = threading.Thread(target=_worker_process, args=(i,), daemon=True)
        t.start()
        threads.append(t)
    logger.info(f"Started {num_workers} background worker threads.")
    return threads


def start_workers(num_workers=10):
    """
    Starts the parallel worker pool and archiver daemon.
    """
    processes = []
    
    # Start Archiver
    archiver = multiprocessing.Process(target=_archiver_process, daemon=True)
    archiver.start()
    processes.append(archiver)
    
    # Start Workers
    for i in range(num_workers):
        p = multiprocessing.Process(target=_worker_process, args=(i,), daemon=True)
        p.start()
        processes.append(p)
        
    return processes


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Starting background worker queue daemon...")
    procs = start_workers()
    try:
        for p in procs:
            p.join()
    except KeyboardInterrupt:
        logger.info("Stopping workers...")