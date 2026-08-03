"""
Multi-process batch processor with retry logic.
Supports multi-document GMF files, single-document GMF files, and approved template filtering.
"""
import os
import time
import shutil
import tempfile
import re
from concurrent.futures import ProcessPoolExecutor, as_completed

from core.template_identifier import identify_template
from core.gmf_splitter import split_gmf_documents, write_doc_to_temp
from templates.registry import get_renderer, get_parser
from config import (
    DEFAULT_WORKERS, PROCESSED_DIR, FAILED_DIR, MOVE_AFTER_PROCESS,
    OUTPUT_PDF_NAMES, OUTPUT_PDF_NAME_DEFAULT,
)


class ProcessingResult:
    def __init__(self, source_file, template_id=None, output_pdf=None,
                 success=False, error=None, duration=0, attempt=1,
                 doc_index=0):
        self.source_file = source_file
        self.template_id = template_id
        self.output_pdf = output_pdf
        self.success = success
        self.error = error
        self.duration = duration
        self.attempt = attempt
        self.doc_index = doc_index


def process_single_file(args):
    """
    Process a GMF file which may contain 1 or multiple documents.
    args format: (file_path, temp_pdf_dir, attempt, is_preview, approved_templates, offset, limit)
    Returns a LIST of ProcessingResult (one per document).
    """
    file_path = args[0]
    temp_pdf_dir = args[1]
    attempt = args[2] if len(args) > 2 else 1
    is_preview = args[3] if len(args) > 3 else False
    approved_templates = args[4] if len(args) > 4 else None
    offset = args[5] if len(args) > 5 else 0
    limit = args[6] if len(args) > 6 else None

    results = []
    source_filename = os.path.basename(file_path)

    try:
        documents = split_gmf_documents(file_path)

        if not documents:
            results.append(ProcessingResult(
                source_file=file_path,
                attempt=attempt,
                error="No document content found"
            ))
            return results

        with tempfile.TemporaryDirectory(prefix="gmf_split_") as split_dir:
            for doc_index, doc_lines in enumerate(documents, start=1):
                result = _process_one_document(
                    doc_lines=doc_lines,
                    doc_index=doc_index,
                    source_file=file_path,
                    source_filename=source_filename,
                    split_dir=split_dir,
                    temp_pdf_dir=temp_pdf_dir,
                    attempt=attempt,
                    is_preview=is_preview,
                    approved_templates=approved_templates,
                    offset=offset,
                    limit=limit,
                )
                results.append(result)

    except Exception as e:
        results.append(ProcessingResult(
            source_file=file_path,
            attempt=attempt,
            error=f"Split failed: {type(e).__name__}: {str(e)}"
        ))

    return results


def _process_one_document(doc_lines, doc_index, source_file, source_filename,
                           split_dir, temp_pdf_dir, attempt, is_preview=False,
                           approved_templates=None, offset=0, limit=None):
    """Process a single document block from a GMF file."""
    start_time = time.perf_counter()
    result = ProcessingResult(
        source_file=source_file,
        attempt=attempt,
        doc_index=doc_index,
    )

    try:
        temp_gmf_path = write_doc_to_temp(
            doc_lines, split_dir, source_filename, doc_index, original_file_path=source_file)


        identification = identify_template(temp_gmf_path)

        if not identification.is_supported:
            result.error = f"Doc {doc_index}: Unsupported ({identification.template_id})"
            return result

        template_id = identification.template_id
        result.template_id = template_id

        # Check if this template is approved for execution (if filtering enabled)
        if approved_templates is not None and template_id not in approved_templates:
            result.error = f"Doc {doc_index}: Template '{template_id}' is awaiting approval"
            return result

        parser_func = get_parser(template_id)
        RendererClass = get_renderer(template_id)

        if is_preview:
            try:
                data = parser_func(temp_gmf_path, limit=1)
            except TypeError:
                data = parser_func(temp_gmf_path)

            if "records" in data and isinstance(data["records"], list) and len(data["records"]) > 1:
                data["records"] = data["records"][:1]

            for list_key in ["product_labels", "lines", "charges", "adjustments", "payments", "taxes", "equipment", "rentals"]:
                if list_key in data and isinstance(data[list_key], list) and len(data[list_key]) > 10:
                    data[list_key] = data[list_key][:10]
        else:
            try:
                data = parser_func(temp_gmf_path, limit=limit, offset=offset)
            except TypeError:
                data = parser_func(temp_gmf_path)

        renderer = RendererClass()
        renderer.render(data)

        account_number = str(data.get("account_number", "unknown"))
        account_number = re.sub(r'[^A-Za-z0-9_-]+', '_', account_number).strip('_')
        if not account_number:
            account_number = "unknown"

        name_pattern = OUTPUT_PDF_NAMES.get(str(template_id), OUTPUT_PDF_NAME_DEFAULT)

        output_name = name_pattern.format(
            account_number=account_number,
            template_id=template_id,
        )

        os.makedirs(temp_pdf_dir, exist_ok=True)
        output_path = os.path.join(temp_pdf_dir, output_name)
        if os.path.exists(output_path):
            base, ext = os.path.splitext(output_name)
            output_path = os.path.join(temp_pdf_dir, f"{base}_dup{doc_index}{ext}")

        renderer.save(output_path)

        gen_count = len(getattr(renderer, "generated_pdfs", []))
        result.output_pdf_count = max(1, gen_count) if gen_count > 0 else 1
        result.output_pdf = output_path
        result.success = True

    except Exception as e:
        result.error = f"Doc {doc_index}: {type(e).__name__}: {str(e)}"
        if result.output_pdf and os.path.exists(result.output_pdf):
            try:
                os.remove(result.output_pdf)
            except OSError:
                pass

    finally:
        result.duration = time.perf_counter() - start_time

    return result


def process_batch(files, temp_pdf_dir, workers=DEFAULT_WORKERS,
                   log_callback=None, progress_callback=None,
                   approved_templates=None):
    """
    Process files in parallel. Each file may contain multiple documents.
    Retry failed files up to 3 times. Returns a list of ProcessingResult.
    """
    if not files:
        return []

    MAX_RETRIES = 3
    all_results = {}
    pending = list(files)
    total_files = len(files)

    if log_callback:
        log_callback(f"Starting: {total_files} files, {workers} workers")

    for attempt in range(1, MAX_RETRIES + 1):
        if not pending:
            break

        if attempt > 1 and log_callback:
            log_callback(f"\n  RETRY {attempt - 1}/3: {len(pending)} failed files")

        args_list = [(f, temp_pdf_dir, attempt, False, approved_templates) for f in pending]
        file_had_failure = {f: False for f in pending}

        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(process_single_file, args): args[0]
                for args in args_list
            }

            for future in as_completed(futures):
                results_list = future.result()
                file_path = futures[future]

                for r in results_list:
                    key = (file_path, r.doc_index)
                    all_results[key] = r
                    if not r.success and "awaiting approval" not in str(r.error):
                        file_had_failure[file_path] = True

                if progress_callback:
                    done = sum(1 for r in all_results.values() if r.success)
                    progress_callback(done, total_files)

        # Retry files that had real processing failures (not unapproved templates)
        pending = [f for f, failed in file_had_failure.items() if failed]

    final_results = list(all_results.values())

    if log_callback:
        succeeded = sum(1 for r in final_results if r.success)
        log_callback(f"\nCompleted: {succeeded}/{len(final_results)} documents processed successfully.")

    return final_results