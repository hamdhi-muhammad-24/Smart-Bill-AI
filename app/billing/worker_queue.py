import time
import os
import shutil
import logging
import multiprocessing
import sys
from pathlib import Path
from datetime import datetime

# Add Models/SmartAI_Bill to sys.path
_smartai_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../Models/SmartAI_Bill"))
if _smartai_path not in sys.path:
    sys.path.insert(0, _smartai_path)

from app.db.base import SessionLocal
from app.db.models import GmfUpload, GmfUploadStatus
from app.core.config import settings
from processing.output_manager import create_output_batches
from config import OUTPUT_PDF_NAMES, OUTPUT_PDF_NAME_DEFAULT

logger = logging.getLogger("worker_queue")
logger.setLevel(logging.INFO)

COMPLETED_TEMP = Path("./queue/completed_temp")

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

def _worker_process(worker_id):
    """
    Parallel worker process that generates PDFs from GMFs in the incoming queue.
    """
    # Imports must be inside the process to avoid multiprocessing pickling issues
    from core.template_identifier import identify_template
    from templates.registry import get_renderer, get_parser
    
    logger.info(f"Worker {worker_id} started")
    COMPLETED_TEMP.mkdir(parents=True, exist_ok=True)
    
    while True:
        filename = None
        working_path = None
        upload_id = None
        run_id = None
        try:
            # Throttle 5 per sec = 0.2s sleep per iteration minimum
            start_time = time.time()
            
            incoming_dir = settings.queue_incoming_dir
            if not incoming_dir.exists():
                time.sleep(1)
                continue
                
            files = [f for f in incoming_dir.iterdir() if f.is_file() and not f.name.startswith(".") and not f.name.endswith(".processing")]
            
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
                # Another worker grabbed it, or it's persistently locked
                time.sleep(0.1)
                continue

            filename = file_path.name
            logger.info(f"Worker {worker_id} processing {filename}")
            
            # DB lookup to get cycle and template ID (with up to 3 retry attempts for delayed transaction commits)
            upload = None
            for retry in range(3):
                with SessionLocal() as db:
                    upload = db.query(GmfUpload).filter(
                        GmfUpload.filename == filename,
                        GmfUpload.status == GmfUploadStatus.APPROVED,
                        GmfUpload.folder_type != "Test_GMFs"
                    ).first()
                if upload:
                    break
                time.sleep(1)
                
            if not upload:
                logger.warning(f"No APPROVED DB record for {filename} after retries, deleting orphan file")
                if os.path.exists(working_path):
                    try:
                        _robust_file_op(os.remove, working_path)
                    except OSError as rm_err:
                        logger.error(f"Could not remove orphan file {working_path}: {rm_err}")
                continue
                
            upload_id = upload.id
            cycle_label = upload.folder_type
            template_id = upload.template_detected
            run_id = upload.billing_run_id
                
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
                            from app.db.models import BillingRun, BillingRunFailure, RunStatus
                            from sqlalchemy import update as sql_update
                            db.execute(
                                sql_update(BillingRun)
                                .where(BillingRun.id == upload.billing_run_id)
                                .values(failed=BillingRun.failed + 1)
                            )
                            db.add(BillingRunFailure(billing_run_id=upload.billing_run_id, account_number=filename, error_message="Template unknown"))
                            db.flush()
                            run = db.query(BillingRun).filter(BillingRun.id == upload.billing_run_id).first()
                            if run and run.succeeded + run.failed >= run.total_accounts:
                                run.status = RunStatus.DONE if run.failed == 0 else RunStatus.PARTIAL
                                run.finished_at = datetime.now()
                        db.commit()
                continue
                
            # Render PDF
            parser_func = get_parser(template_id)
            RendererClass = get_renderer(template_id)
            
            if not parser_func or not RendererClass:
                logger.error(f"Cannot process {filename}: parser/renderer not found for {template_id}")
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
                        upload.error_message = f"Parser/Renderer not found for {template_id}"
                        
                        if upload.billing_run_id:
                            from app.db.models import BillingRun, BillingRunFailure, RunStatus
                            from sqlalchemy import update as sql_update
                            db.execute(
                                sql_update(BillingRun)
                                .where(BillingRun.id == upload.billing_run_id)
                                .values(failed=BillingRun.failed + 1)
                            )
                            db.add(BillingRunFailure(billing_run_id=upload.billing_run_id, account_number=filename, error_message=f"Parser/Renderer not found for {template_id}"))
                            db.flush()
                            run = db.query(BillingRun).filter(BillingRun.id == upload.billing_run_id).first()
                            if run and run.succeeded + run.failed >= run.total_accounts:
                                run.status = RunStatus.DONE if run.failed == 0 else RunStatus.PARTIAL
                                run.finished_at = datetime.now()
                        db.commit()
                continue
            
            # Parse GMF data
            try:
                data = parser_func(str(working_path))
            except Exception as parse_err:
                raise Exception(f"GMF structure parse error: {parse_err}")

            # Render layout
            try:
                renderer = RendererClass()
                renderer.render(data)
            except Exception as render_err:
                raise Exception(f"PDF layout render error: {render_err}")
            
            # Save PDF
            account_number = str(data.get("account_number", "unknown")).replace(" ", "")
            name_pattern = OUTPUT_PDF_NAMES.get(str(template_id), OUTPUT_PDF_NAME_DEFAULT)
            output_name = name_pattern.format(account_number=account_number, template_id=template_id)
            
            cycle_temp = COMPLETED_TEMP / cycle_label
            cycle_temp.mkdir(parents=True, exist_ok=True)
            output_pdf_path = cycle_temp / output_name
            
            try:
                renderer.save(str(output_pdf_path))
            except Exception as save_err:
                raise Exception(f"PDF save/write error: {save_err}")
            
            # Move source GMF to Processed folder and update DB
            try:
                processed_dest = settings.gmf_drive_path / "Processed" / (cycle_label or "unknown")
                processed_dest.mkdir(parents=True, exist_ok=True)
                dest_file_path = processed_dest / filename
                if dest_file_path.exists():
                    try:
                        _robust_file_op(dest_file_path.unlink)
                    except Exception as rm_err:
                        logger.warning(f"Could not remove existing processed GMF file {dest_file_path}: {rm_err}")
                _robust_file_op(shutil.move, str(working_path), str(dest_file_path))
                
                with SessionLocal() as db:
                    upload = db.query(GmfUpload).filter(GmfUpload.id == upload_id).first()
                    if upload:
                        upload.status = GmfUploadStatus.COMPLETED
                        upload.processed_at = datetime.now()
                        upload.file_path = str(dest_file_path)
                        
                        if upload.billing_run_id:
                            from app.db.models import BillingRun, RunStatus
                            from sqlalchemy import update
                            # Atomic SQL increment — no read-modify-write race possible
                            db.execute(
                                update(BillingRun)
                                .where(BillingRun.id == upload.billing_run_id)
                                .values(succeeded=BillingRun.succeeded + 1)
                            )
                            db.flush()
                            # Re-read to check completion
                            run = db.query(BillingRun).filter(BillingRun.id == upload.billing_run_id).first()
                            if run and run.succeeded + run.failed >= run.total_accounts:
                                run.status = RunStatus.DONE if run.failed == 0 else RunStatus.PARTIAL
                                run.finished_at = datetime.now()
                        db.commit()
            except Exception as move_err:
                logger.error(f"Failed to move completed GMF {filename} to Processed: {move_err}")
                if os.path.exists(working_path):
                    try:
                        _robust_file_op(os.remove, working_path)
                    except OSError as err:
                        logger.error(f"Could not remove {working_path} after move failure: {err}")
            
            # Delete from remote Google Drive Cycle folder
            try:
                import subprocess
                if shutil.which("rclone"):
                    subprocess.Popen(["rclone", "deletefile", f"gdrive:SLT_GMF_Uploads/{cycle_label}/{filename}"])
                else:
                    logger.info("rclone not available in container; host sync service will clean remote GMF %s", filename)
            except Exception as delete_err:
                logger.error(f"Failed to launch rclone delete for {filename}: {delete_err}")
                
            logger.info(f"Worker {worker_id} successfully generated {output_name}")
            
            # Throttle
            elapsed = time.time() - start_time
            if elapsed < 0.2:
                time.sleep(0.2 - elapsed)
                
        except Exception as e:
            logger.error(f"Worker {worker_id} error: {e}", exc_info=True)
            if filename and working_path is not None and working_path.exists():
                try:
                    # Get cycle_label and run_id from DB
                    cycle_label = "unknown"
                    local_run_id = None
                    if 'run_id' in locals():
                        local_run_id = locals()['run_id']
                        
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
                    _robust_file_op(shutil.move, str(working_path), str(dest_file_path))
                    
                    # Delete from remote Google Drive Cycle folder
                    try:
                        import subprocess
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
                            upload.error_message = str(e)
                            upload.file_path = str(dest_file_path)
                            
                            if upload.billing_run_id:
                                from app.db.models import BillingRun, BillingRunFailure, RunStatus
                                from sqlalchemy import update as sql_update
                                # Atomic SQL increment for failed counter
                                db.execute(
                                    sql_update(BillingRun)
                                    .where(BillingRun.id == upload.billing_run_id)
                                    .values(failed=BillingRun.failed + 1)
                                )
                                db.add(BillingRunFailure(
                                    billing_run_id=upload.billing_run_id,
                                    account_number=filename,
                                    error_message=str(e)
                                ))
                                db.flush()
                                # Re-read to check completion
                                run = db.query(BillingRun).filter(BillingRun.id == upload.billing_run_id).first()
                                if run and run.succeeded + run.failed >= run.total_accounts:
                                    run.status = RunStatus.DONE if run.failed == 0 else RunStatus.PARTIAL
                                    run.finished_at = datetime.now()
                        db.commit()
                except Exception as inner_err:
                    logger.error(f"Failed to record failure details: {inner_err}")
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
                        # We have PDFs for this cycle, batch them into the final output dir
                        create_output_batches(str(cycle_dir), cycle_label=cycle_dir.name)
            time.sleep(2)
        except Exception as e:
            logger.error(f"Archiver error: {e}", exc_info=True)
            time.sleep(5)


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
