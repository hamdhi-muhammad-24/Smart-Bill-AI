"""
Multi-process batch processor with retry logic.
"""
import os
import time
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.template_identifier import identify_template
from templates.registry import get_renderer, get_parser
from config import (
    DEFAULT_WORKERS,PROCESSED_DIR, FAILED_DIR, MOVE_AFTER_PROCESS,OUTPUT_PDF_NAMES, OUTPUT_PDF_NAME_DEFAULT
)


class ProcessingResult:
    def __init__(self, source_file, template_id=None, output_pdf=None,
                 success=False, error=None, duration=0, attempt=1):
        self.source_file = source_file
        self.template_id = template_id
        self.output_pdf = output_pdf
        self.success = success
        self.error = error
        self.duration = duration
        self.attempt = attempt

def process_single_file(args):
    file_path = args[0]
    temp_pdf_dir = args[1]
    attempt = args[2] if len(args) > 2 else 1
    is_preview = args[3] if len(args) > 3 else False
    
    start_time = time.perf_counter()
    result = ProcessingResult(source_file=file_path, attempt=attempt)

    try:
        identification = identify_template(file_path)

        if not identification.is_supported:
            result.error = f"Unsupported: {identification.template_id}"
            return result

        template_id = identification.template_id
        result.template_id = template_id

        parser_func = get_parser(template_id)
        RendererClass = get_renderer(template_id)

        data = parser_func(file_path)

        if is_preview:
            for list_key in ["product_labels", "lines", "charges", "adjustments", "payments", "taxes", "equipment", "rentals"]:
                if list_key in data and isinstance(data[list_key], list) and len(data[list_key]) > 10:
                    data[list_key] = data[list_key][:10]

        renderer = RendererClass()
        renderer.render(data)


        account_number = str(data.get("account_number", "unknown"))
        account_number = account_number.replace(" ", "")

        # Get template-specific pattern or fallback
        name_pattern = OUTPUT_PDF_NAMES.get(str(template_id), OUTPUT_PDF_NAME_DEFAULT)

        output_name = name_pattern.format(
            account_number=account_number,
            template_id=template_id,
        )

        os.makedirs(temp_pdf_dir, exist_ok=True)
        output_path = os.path.join(temp_pdf_dir, output_name)
        result.output_pdf = output_path
        
        renderer.save(output_path)
        
        result.success = True

    except Exception as e:
        result.error = f"{type(e).__name__}: {str(e)}"
        if result.output_pdf and os.path.exists(result.output_pdf):
            try:
                os.remove(result.output_pdf)
            except OSError:
                pass

    finally:
        result.duration = time.perf_counter() - start_time

    return result



def process_batch(files, temp_pdf_dir, workers=DEFAULT_WORKERS,
                   log_callback=None, progress_callback=None):
    """
    Process files in parallel. Retry failed files up to 3 times.
    Only failed files are retried.
    """
    if not files:
        return []

    MAX_RETRIES = 3
    all_results = {}
    pending = list(files)
    total_files = len(files)

    if log_callback:
        log_callback(f"Starting: {total_files} files, {workers} workers")

    overall_start = time.perf_counter()

    for attempt in range(1, MAX_RETRIES + 1):
        if not pending:
            break

        if attempt > 1 and log_callback:
            log_callback(f"\n  RETRY {attempt - 1}/3: {len(pending)} failed files")

        round_start = time.perf_counter()
        args_list = [(f, temp_pdf_dir, attempt) for f in pending]

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(process_single_file, args): args[0]
                for args in args_list
            }

            for future in as_completed(futures):
                result = future.result()
                file_path = futures[future]
                all_results[file_path] = result

                if progress_callback:
                    done = sum(1 for r in all_results.values() if r.success)
                    progress_callback(done, total_files)

                completed = len([r for r in all_results.values()
                                  if r.attempt == attempt])
                if log_callback and completed % 100 == 0 and completed > 0:
                    elapsed = time.perf_counter() - round_start
                    rate = completed / elapsed if elapsed > 0 else 0
                    log_callback(
                        f"    Progress: {completed}/{len(pending)} "
                        f"({rate:.1f} files/sec, {rate*3600:.0f}/hr)"
                    )

        round_elapsed = time.perf_counter() - round_start
        round_success = sum(1 for f in pending if all_results[f].success)
        round_fail = len(pending) - round_success

        if log_callback:
            rate = len(pending) / round_elapsed if round_elapsed > 0 else 0
            if attempt == 1:
                log_callback(
                    f"  Round 1: {round_success} success, {round_fail} failed "
                    f"in {round_elapsed:.1f}s ({rate*3600:.0f}/hr)"
                )
            else:
                log_callback(
                    f"  Retry {attempt-1}: {round_success} recovered, "
                    f"{round_fail} still failing"
                )

        pending = [
            f for f in pending 
            if not all_results[f].success 
            and "Unsupported template" not in str(all_results[f].error)
            and "Unknown template" not in str(all_results[f].error)
        ]

    if MOVE_AFTER_PROCESS:
        _move_processed_files(list(all_results.values()), log_callback)

    results = list(all_results.values())
    total_success = sum(1 for r in results if r.success)
    total_fail = len(results) - total_success
    total_elapsed = time.perf_counter() - overall_start

    if log_callback:
        rate = total_files / total_elapsed if total_elapsed > 0 else 0
        log_callback(
            f"\nBatch complete: {total_success} success, {total_fail} failed "
            f"in {total_elapsed:.1f}s ({rate*3600:.0f}/hr)"
        )
        if total_fail > 0:
            log_callback(f"  {total_fail} file(s) failed after {MAX_RETRIES} attempts")
            for r in results:
                if not r.success:
                    log_callback(f"    FAILED: {os.path.basename(r.source_file)}: {r.error}")

    return results


def _move_processed_files(results, log_callback=None):
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    os.makedirs(FAILED_DIR, exist_ok=True)

    for result in results:
        source = result.source_file
        if not os.path.exists(source):
            continue

        try:
            if result.success:
                dest = os.path.join(PROCESSED_DIR, os.path.basename(source))
                shutil.move(source, dest)
            else:
                dest = os.path.join(FAILED_DIR, os.path.basename(source))
                shutil.move(source, dest)
        except Exception as e:
            if log_callback:
                log_callback(f"  Warning: could not move {os.path.basename(source)}: {e}")