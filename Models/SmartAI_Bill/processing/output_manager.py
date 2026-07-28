"""
Output batch manager for SLT Bill Generator.

Organised folder-based output browser support for both local ./output and Drive output folders:
  ./output/<YYYY-MM-DD>/<Cycle_or_Template>/Batch_1/
  G:/My Drive/SLT_GMF_Uploads/Output/<YYYY-MM-DD>/<Cycle_or_Template>/Batch_1/
"""
import os
import shutil
from datetime import datetime
from config import BATCH_FOLDER_SIZE, OUTPUT_BASE_DIR


def get_output_roots():
    """Return list of valid output root paths (checking ./output and drive Output)."""
    roots = []
    try:
        from app.core.config import settings
        out_p = str(settings.output_dir)
        if os.path.exists(out_p):
            roots.append(out_p)
    except Exception:
        pass

    if os.path.exists("./output") and "./output" not in roots:
        roots.append("./output")

    if os.path.exists(OUTPUT_BASE_DIR) and OUTPUT_BASE_DIR not in roots:
        roots.append(OUTPUT_BASE_DIR)

    return roots if roots else [OUTPUT_BASE_DIR]


def create_output_batches(temp_pdf_dir, cycle_label="Cycle_1", log_callback=None):
    """
    Move generated PDFs from temp_pdf_dir into organised date/cycle/batch folders.

    Returns a list of batch folder paths that were created.
    """
    if cycle_label == "Test_GMFs":
        if log_callback:
            log_callback("Skipping output batch creation for test GMF preview run")
        return []

    if not os.path.exists(temp_pdf_dir):
        if log_callback:
            log_callback("No PDFs to organise — temp dir does not exist")
        return []

    # Collect all PDFs
    pdfs = sorted([
        os.path.join(temp_pdf_dir, f)
        for f in os.listdir(temp_pdf_dir)
        if f.lower().endswith(".pdf")
    ])

    if not pdfs:
        if log_callback:
            log_callback("No PDFs found to organise")
        return []

    today = datetime.now().strftime("%Y-%m-%d")
    base = os.path.join(OUTPUT_BASE_DIR, today, cycle_label)
    os.makedirs(base, exist_ok=True)

    if log_callback:
        log_callback(
            f"\nOrganising {len(pdfs)} PDFs -> {base} "
            f"(batches of {BATCH_FOLDER_SIZE})"
        )

    batch_folders = []
    current_batch_num = 1
    pdf_index = 0
    
    while pdf_index < len(pdfs):
        batch_dir = os.path.join(base, f"Batch_{current_batch_num}")
        os.makedirs(batch_dir, exist_ok=True)
        
        existing_files = [f for f in os.listdir(batch_dir) if f.lower().endswith(".pdf")]
        existing_count = len(existing_files)
        
        space_left = BATCH_FOLDER_SIZE - existing_count
        
        if space_left <= 0:
            current_batch_num += 1
            continue
            
        moved_in_this_batch = 0
        while pdf_index < len(pdfs):
            existing_count = len([f for f in os.listdir(batch_dir) if f.lower().endswith(".pdf")])
            if existing_count >= BATCH_FOLDER_SIZE:
                current_batch_num += 1
                batch_dir = os.path.join(base, f"Batch_{current_batch_num}")
                os.makedirs(batch_dir, exist_ok=True)
                existing_count = len([f for f in os.listdir(batch_dir) if f.lower().endswith(".pdf")])

            pdf_path = pdfs[pdf_index]
            dest = os.path.join(batch_dir, os.path.basename(pdf_path))
            
            try:
                local_vm_batch_dir = os.path.join("./output", today, cycle_label, f"Batch_{current_batch_num}")
                os.makedirs(local_vm_batch_dir, exist_ok=True)
                shutil.copy2(pdf_path, os.path.join(local_vm_batch_dir, os.path.basename(pdf_path)))
            except Exception as copy_err:
                if log_callback:
                    log_callback(f"  Warning: failed to duplicate copy to VM local folder: {copy_err}")
                    
            shutil.move(pdf_path, dest)
            moved_in_this_batch += 1
            pdf_index += 1
            
        if log_callback:
            log_callback(
                f"  Batch {current_batch_num}: "
                f"added {moved_in_this_batch} invoices -> {batch_dir}"
            )
            
        if batch_dir not in batch_folders:
            batch_folders.append(batch_dir)
            
        current_batch_num += 1

    if log_callback:
        log_callback(f"Created {len(batch_folders)} batch folder(s) in {base}")

    return batch_folders


def get_output_root(date_str=None, cycle_label=None):
    """Return the output root path (optionally scoped by date and cycle)."""
    roots = get_output_roots()
    parts = [roots[0]]
    if date_str:
        parts.append(date_str)
    if cycle_label:
        parts.append(cycle_label)
    return os.path.join(*parts)


def list_output_dates():
    """Return sorted list of dates that have output across all output root locations, newest first."""
    dates = set()
    for root in get_output_roots():
        if os.path.exists(root):
            for d in os.listdir(root):
                if d == "previews":
                    continue
                if os.path.isdir(os.path.join(root, d)):
                    dates.add(d)
    return sorted(list(dates), reverse=True)


def list_cycles_for_date(date_str):
    """Return list of cycle/template folders for a given date across all output roots."""
    cycles = set()
    for root in get_output_roots():
        date_path = os.path.join(root, date_str)
        if os.path.exists(date_path):
            for d in os.listdir(date_path):
                if os.path.isdir(os.path.join(date_path, d)):
                    cycles.add(d)
    return sorted(list(cycles))


def list_batches_for_cycle(date_str, cycle_label):
    """Return list of batch folders for a given date/cycle across all output roots."""
    batches = set()
    for root in get_output_roots():
        cycle_path = os.path.join(root, date_str, cycle_label)
        if os.path.exists(cycle_path):
            for d in os.listdir(cycle_path):
                if os.path.isdir(os.path.join(cycle_path, d)):
                    batches.add(d)
    return sorted(list(batches))


def list_pdfs_in_batch(date_str, cycle_label, batch_name):
    """Return list of PDF filenames in a specific batch folder across all output roots."""
    pdfs = set()
    for root in get_output_roots():
        batch_path = os.path.join(root, date_str, cycle_label, batch_name)
        if os.path.exists(batch_path):
            for f in os.listdir(batch_path):
                if f.lower().endswith(".pdf"):
                    pdfs.add(f)
    return sorted(list(pdfs))


def get_pdf_path(date_str, cycle_label, batch_name, filename):
    """Return absolute path to a specific PDF file across all output roots."""
    for root in get_output_roots():
        p = os.path.join(root, date_str, cycle_label, batch_name, filename)
        if os.path.exists(p):
            return p
    return os.path.join(get_output_roots()[0], date_str, cycle_label, batch_name, filename)
