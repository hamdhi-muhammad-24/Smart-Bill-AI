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

    if cycle_label and "cycle" in cycle_label.lower():
        import re
        match = re.search(r'(\d+)', str(cycle_label))
        if match:
            cycle_label = f"Cycle_{match.group(1)}"
        else:
            cycle_label = str(cycle_label).strip().replace(" ", "_")
    elif cycle_label:
        cycle_label = str(cycle_label).strip().replace(" ", "_")
    else:
        cycle_label = "Cycle_1"

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
                local_base = os.path.join("./output", today, cycle_label)
                # Find local batch dir with < 10 PDFs
                b_num = 1
                while True:
                    local_vm_batch_dir = os.path.join(local_base, f"Batch_{b_num}")
                    os.makedirs(local_vm_batch_dir, exist_ok=True)
                    local_cnt = len([f for f in os.listdir(local_vm_batch_dir) if f.lower().endswith(".pdf")])
                    if local_cnt < BATCH_FOLDER_SIZE:
                        break
                    b_num += 1
                target_copy = os.path.join(local_vm_batch_dir, os.path.basename(pdf_path))
                if os.path.abspath(pdf_path) != os.path.abspath(target_copy):
                    shutil.copy2(pdf_path, target_copy)
            except Exception as copy_err:
                if log_callback:
                    log_callback(f"  Warning: failed to duplicate copy to VM local folder: {copy_err}")
                    
            if os.path.abspath(pdf_path) != os.path.abspath(dest):
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
    import re
    return sorted(list(cycles), key=lambda x: [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', x)])


def list_batches_for_cycle(date_str, cycle_label):
    """Return list of batch folders for a given date/cycle across all output roots."""
    batches = set()
    for root in get_output_roots():
        cycle_path = os.path.join(root, date_str, cycle_label)
        if os.path.exists(cycle_path):
            has_direct_pdfs = False
            for d in os.listdir(cycle_path):
                full_p = os.path.join(cycle_path, d)
                if os.path.isdir(full_p):
                    batches.add(d)
                elif d.lower().endswith('.pdf'):
                    has_direct_pdfs = True
            if has_direct_pdfs:
                batches.add("Batch_01")
    import re
    return sorted(list(batches), key=lambda x: [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', x)])


def list_pdfs_in_batch(date_str, cycle_label, batch_name):
    """Return list of PDF filenames in a specific batch folder across all output roots."""
    pdfs = set()
    for root in get_output_roots():
        batch_path = os.path.join(root, date_str, cycle_label, batch_name)
        if os.path.exists(batch_path) and os.path.isdir(batch_path):
            for dirpath, _, filenames in os.walk(batch_path):
                for f in filenames:
                    if f.lower().endswith(".pdf"):
                        # Get path relative to the batch folder
                        full_path = os.path.join(dirpath, f)
                        rel_path = os.path.relpath(full_path, batch_path)
                        # Replace backslashes with forward slashes for URLs
                        pdfs.add(rel_path.replace("\\", "/"))
        
        # Check direct files if batch_name is Batch_01
        if batch_name == "Batch_01":
            cycle_path = os.path.join(root, date_str, cycle_label)
            if os.path.exists(cycle_path):
                for f in os.listdir(cycle_path):
                    if f.lower().endswith(".pdf"):
                        pdfs.add(f)
    return sorted(list(pdfs))


def get_pdf_path(date_str, cycle_label, batch_name, filename):
    """Return absolute path to a specific PDF file across all output roots."""
    basename = os.path.basename(filename)
    for root in get_output_roots():
        # Check batch subfolder recursively
        batch_path = os.path.join(root, date_str, cycle_label, batch_name)
        if os.path.exists(batch_path):
            for dirpath, _, filenames in os.walk(batch_path):
                if basename in filenames:
                    return os.path.join(dirpath, basename)
        # Check direct cycle directory
        p_direct = os.path.join(root, date_str, cycle_label, basename)
        if os.path.exists(p_direct):
            return p_direct
    return os.path.join(get_output_roots()[0], date_str, cycle_label, batch_name, basename)


def create_summary_groups(date_base_dir, processing_results, log_callback=None):
    """
    Create a summary/ folder under date_base_dir that groups each Summary Statement
    with all its sub-account bills, searching across ALL cycle folders for that date.

    Structure:
        output/YYYY-MM-DD/
        ├── Summary_Statement/     ← cycle folders unchanged
        ├── VAT_Enterprise/
        └── summary/               ← NEW: sits at the date level
            └── CRxxxxxxxxx/       ← one folder per summary statement
                ├── 00_<summary>.pdf   ← summary statement first (00_ prefix)
                ├── <account1>.pdf
                └── <account2>.pdf

    Args:
        date_base_dir (str|Path): The dated output folder (e.g. output/2026-08-21/).
        processing_results (list[ProcessingResult]): Results from process_single_file / process_batch.
        log_callback (callable|None): Optional logging function.
    """
    date_base_dir = str(date_base_dir)

    # Filter results that carry summary metadata
    summary_results = [r for r in processing_results if getattr(r, "summary_meta", None)]
    if not summary_results:
        return

    # Collect ALL PDFs under date_base_dir across every cycle folder,
    # but skip the summary/ folder itself to avoid circular copying.
    all_pdfs = {}  # filename -> absolute path
    for dirpath, dirnames, filenames in os.walk(date_base_dir):
        rel = os.path.relpath(dirpath, date_base_dir)
        # Skip the summary folder itself
        if rel == "summary" or rel.startswith("summary" + os.sep):
            dirnames[:] = []  # don't descend further
            continue
        for fname in filenames:
            if fname.lower().endswith(".pdf"):
                # First occurrence wins (avoids Batch_2 overwriting Batch_1 copy)
                if fname not in all_pdfs:
                    all_pdfs[fname] = os.path.join(dirpath, fname)

    summary_root = os.path.join(date_base_dir, "summary")

    for result in summary_results:
        meta = result.summary_meta
        customer_ref = meta.get("customer_ref", "unknown")
        account_nos = meta.get("account_nos", [])
        summary_pdf_name = meta.get("pdf_name", "")

        group_dir = os.path.join(summary_root, customer_ref)
        os.makedirs(group_dir, exist_ok=True)

        copied = 0
        errors = 0

        # 1. Move the summary statement PDF first (prefixed with 00_ to sort to top)
        if summary_pdf_name and summary_pdf_name in all_pdfs:
            src = all_pdfs[summary_pdf_name]
            dest_name = f"00_{summary_pdf_name}"
            dest = os.path.join(group_dir, dest_name)
            try:
                if os.path.exists(src):
                    shutil.move(src, dest)
                    copied += 1
            except Exception as e:
                errors += 1
                if log_callback:
                    log_callback(f"  Summary group warning: could not move summary PDF {summary_pdf_name}: {e}")

        # 2. Move matching sub-account bills (account number must appear in filename)
        for acc_no in account_nos:
            if not acc_no:
                continue
            matched = [
                (fname, path)
                for fname, path in all_pdfs.items()
                if acc_no in fname and fname != summary_pdf_name
            ]
            for fname, src in matched:
                dest = os.path.join(group_dir, fname)
                if os.path.exists(dest) or not os.path.exists(src):
                    continue  # already moved (e.g. account appears in multiple summaries)
                try:
                    shutil.move(src, dest)
                    copied += 1
                except Exception as e:
                    errors += 1
                    if log_callback:
                        log_callback(f"  Summary group warning: could not move {fname}: {e}")

        if log_callback:
            status = f"({errors} errors)" if errors else "OK"
            log_callback(
                f"  Summary group [{customer_ref}]: {copied} file(s) -> {group_dir} {status}"
            )