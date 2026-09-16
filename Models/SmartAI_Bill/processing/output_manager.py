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
                if os.path.exists(target_copy):
                    base_n, ext_n = os.path.splitext(os.path.basename(pdf_path))
                    dup_i = 2
                    while os.path.exists(os.path.join(local_vm_batch_dir, f"{base_n}_dup{dup_i}{ext_n}")):
                        dup_i += 1
                    target_copy = os.path.join(local_vm_batch_dir, f"{base_n}_dup{dup_i}{ext_n}")
                if os.path.abspath(pdf_path) != os.path.abspath(target_copy):
                    shutil.copy2(pdf_path, target_copy)
            except Exception as copy_err:
                if log_callback:
                    log_callback(f"  Warning: failed to duplicate copy to VM local folder: {copy_err}")
                    
            if os.path.exists(dest):
                base_n, ext_n = os.path.splitext(os.path.basename(pdf_path))
                dup_i = 2
                while os.path.exists(os.path.join(batch_dir, f"{base_n}_dup{dup_i}{ext_n}")):
                    dup_i += 1
                dest = os.path.join(batch_dir, f"{base_n}_dup{dup_i}{ext_n}")
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


def normalize_account_number(acc_no: str) -> str:
    """
    Strip all whitespace, underscores, hyphens, and punctuation from an account number,
    and convert to uppercase. Handles values with spaces like '005 341 6491' -> '0053416491'.
    """
    import re
    if not acc_no:
        return ""
    return re.sub(r'[^A-Za-z0-9]+', '', str(acc_no)).upper()


def extract_account_from_filename(filename: str) -> str:
    """
    Extract the account number from a generated bill filename, ignoring template type.
    Examples:
      '0005842786_NONVAT_HOME.pdf' -> '0005842786'
      '0053416491_VAT_ENTERPRISE.pdf' -> '0053416491'
      '005104340X_NONVAT_HOME.pdf' -> '005104340X'
      '0053416491_ProductLevel.pdf' -> '0053416491'
      '0053416491_InvoiceOfSummary.pdf' -> '0053416491'
      '0053416491_NONVAT_HOME_dup1.pdf' -> '0053416491'
      'SLT20eBill-0005842786.pdf' -> '0005842786'
      '0005842786.pdf' -> '0005842786'
    """
    if not filename:
        return ""
    base = os.path.splitext(filename)[0]
    u_base = base.upper()
    if u_base.startswith("00_") or u_base == "SUMMARY" or u_base.endswith("_SUMMARY") or u_base.startswith("SUMMARY_"):
        return ""
    if base.startswith("SLT20eBill-"):
        base = base[len("SLT20eBill-"):]
    
    # Split on the first underscore to separate account number from template type
    parts = base.split("_", 1)
    return normalize_account_number(parts[0])


def extract_accounts_from_summary_pdf(pdf_path: str) -> list[str]:
    """
    Extract account numbers in document order from a summary statement PDF.
    Account numbers in summary statements follow the format XXX XXX XXXX (or with X/x suffix).
    """
    if not pdf_path or not os.path.exists(pdf_path):
        return []
    import re
    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf_path)
        text = "\n".join([page.extract_text() or "" for page in reader.pages])
        raw_matches = re.findall(r'\b\d{3}\s+\d{3}\s+[\dX]{4}\b', text, flags=re.IGNORECASE)
        ordered = []
        for m in raw_matches:
            norm = normalize_account_number(m)
            if norm and norm not in ordered:
                ordered.append(norm)
        return ordered
    except Exception:
        return []


def list_pdfs_in_batch(date_str, cycle_label, batch_name):
    """Return list of PDF filenames in a specific batch folder across all output roots."""
    import json
    pdfs = set()
    manifest_account_order = {}
    summary_pdf_path = None
    manifest_path_found = None

    for root in get_output_roots():
        batch_path = os.path.join(root, date_str, cycle_label, batch_name)
        if os.path.exists(batch_path) and os.path.isdir(batch_path):
            manifest_p = os.path.join(batch_path, "manifest.json")
            if os.path.exists(manifest_p):
                manifest_path_found = manifest_p
                if not manifest_account_order:
                    try:
                        with open(manifest_p, "r", encoding="utf-8") as mf:
                            mdata = json.load(mf)
                            acc_list = mdata.get("account_nos", [])
                            if acc_list:
                                manifest_account_order = {
                                    normalize_account_number(a): idx
                                    for idx, a in enumerate(acc_list)
                                    if normalize_account_number(a)
                                }
                    except Exception:
                        pass

            for dirpath, _, filenames in os.walk(batch_path):
                for f in filenames:
                    if f.lower().endswith(".pdf"):
                        full_path = os.path.join(dirpath, f)
                        rel_path = os.path.relpath(full_path, batch_path)
                        pdfs.add(rel_path.replace("\\", "/"))
                        if not summary_pdf_path:
                            u_f = f.upper()
                            if f.startswith("00_") or "SUMMARY" in u_f:
                                summary_pdf_path = full_path

        # Check direct files if batch_name is Batch_01
        if batch_name == "Batch_01":
            cycle_path = os.path.join(root, date_str, cycle_label)
            if os.path.exists(cycle_path):
                for f in os.listdir(cycle_path):
                    if f.lower().endswith(".pdf"):
                        pdfs.add(f)
                        if not summary_pdf_path and (f.startswith("00_") or "SUMMARY" in f.upper()):
                            summary_pdf_path = os.path.join(cycle_path, f)

    pdf_list = list(pdfs)
    is_summary = (
        (cycle_label and cycle_label.lower() == "summary") or
        bool(manifest_path_found) or
        any(os.path.basename(p).startswith("00_") or "SUMMARY" in os.path.basename(p).upper() for p in pdf_list)
    )

    if is_summary:
        # If manifest was missing, empty, or sorted ascending by legacy code (where doc order differs),
        # extract accounts in document order directly from the summary PDF.
        if summary_pdf_path and os.path.exists(summary_pdf_path):
            needs_pdf_extract = False
            if not manifest_account_order:
                needs_pdf_extract = True
            else:
                acc_keys = list(manifest_account_order.keys())
                if len(acc_keys) > 2 and acc_keys == sorted(acc_keys):
                    needs_pdf_extract = True

            if needs_pdf_extract:
                pdf_accs = extract_accounts_from_summary_pdf(summary_pdf_path)
                if pdf_accs:
                    manifest_account_order = {a: idx for idx, a in enumerate(pdf_accs)}
                    if manifest_path_found and os.path.exists(manifest_path_found):
                        try:
                            with open(manifest_path_found, "r", encoding="utf-8") as mf:
                                cur_data = json.load(mf)
                            cur_data["account_nos"] = pdf_accs
                            with open(manifest_path_found, "w", encoding="utf-8") as mf:
                                json.dump(cur_data, mf, indent=2)
                        except Exception:
                            pass

        def summary_sort_key(p):
            fname = os.path.basename(p)
            u = fname.upper()
            # 1. Summary statement always on top
            if fname.startswith("00_") or "SUMMARY" in u:
                return (0, 0, fname)

            # 2. Matching bills according to order in that summary
            acc = extract_account_from_filename(fname)
            if acc and acc in manifest_account_order:
                return (1, manifest_account_order[acc], fname)

            # 3. Fallback: descending order for bills not in manifest (summary bills are naturally descending)
            return (2, [-ord(c) for c in fname], fname)

        return sorted(pdf_list, key=summary_sort_key)

    return sorted(pdf_list)


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


def create_summary_groups(date_base_dir, processing_results=None, log_callback=None):
    """
    Create a summary/ folder under date_base_dir that groups each Summary Statement
    with all its sub-account bills, searching across ALL cycle folders for that date.

    Structure:
        output/YYYY-MM-DD/
        ├── Summary_Statement/     ← cycle folders unchanged
        ├── VAT_Enterprise/
        └── summary/               ← sits at the date level
            └── CRxxxxxxxxx/       ← one folder per summary statement
                ├── manifest.json      ← cached account mapping for future runs
                ├── 00_<summary>.pdf   ← summary statement first (00_ prefix)
                ├── <account1>.pdf
                └── <account2>.pdf

    Args:
        date_base_dir (str|Path): The dated output folder (e.g. output/2026-08-21/).
        processing_results (list[ProcessingResult]|None): Results from process_single_file / process_batch.
        log_callback (callable|None): Optional logging function.
    """
    import json
    import re
    date_base_dir = str(date_base_dir)
    if not os.path.exists(date_base_dir):
        return

    summary_root = os.path.join(date_base_dir, "summary")
    os.makedirs(summary_root, exist_ok=True)

    # 1. Gather all summary metadata (from current processing_results + existing manifests)
    # Mapping: customer_ref -> {"account_nos": list(...), "pdf_names": list(...)}
    summary_map = {}

    # Load existing manifests from disk if present
    if os.path.exists(summary_root):
        for cr_name in os.listdir(summary_root):
            cr_dir = os.path.join(summary_root, cr_name)
            manifest_p = os.path.join(cr_dir, "manifest.json")
            if os.path.isdir(cr_dir) and os.path.exists(manifest_p):
                try:
                    with open(manifest_p, "r", encoding="utf-8") as mf:
                        mdata = json.load(mf)
                        c_ref = mdata.get("customer_ref", cr_name)
                        accs = []
                        for a in mdata.get("account_nos", []):
                            na = normalize_account_number(a)
                            if na and na not in accs:
                                accs.append(na)
                        pdf_n = mdata.get("pdf_name", "")
                        pdf_names = []
                        if pdf_n:
                            pdf_names.append(pdf_n)
                        for pn in mdata.get("pdf_names", []):
                            if pn and pn not in pdf_names:
                                pdf_names.append(pn)
                        summary_map[c_ref] = {
                            "account_nos": accs,
                            "pdf_names": pdf_names,
                        }
                except Exception:
                    pass

    # Incorporate incoming processing_results
    if processing_results:
        for r in processing_results:
            meta = getattr(r, "summary_meta", None)
            if not meta or not isinstance(meta, dict):
                continue
            c_ref = re.sub(r'[^A-Za-z0-9_-]+', '_', str(meta.get("customer_ref", "") or "")).strip('_')
            if not c_ref:
                continue
            accs = []
            for a in meta.get("account_nos", []):
                na = normalize_account_number(a)
                if na and na not in accs:
                    accs.append(na)
            pdf_n = meta.get("pdf_name", "")

            if c_ref not in summary_map:
                summary_map[c_ref] = {"account_nos": [], "pdf_names": []}
            
            # Incoming results preserve the exact summary order
            for a in accs:
                if a not in summary_map[c_ref]["account_nos"]:
                    summary_map[c_ref]["account_nos"].append(a)
            if pdf_n and pdf_n not in summary_map[c_ref]["pdf_names"]:
                summary_map[c_ref]["pdf_names"].append(pdf_n)

    if not summary_map:
        return

    # 2. Persist updated manifest.json for each CR group
    for c_ref, info in summary_map.items():
        cr_dir = os.path.join(summary_root, c_ref)
        os.makedirs(cr_dir, exist_ok=True)
        manifest_p = os.path.join(cr_dir, "manifest.json")
        try:
            with open(manifest_p, "w", encoding="utf-8") as mf:
                json.dump({
                    "customer_ref": c_ref,
                    "account_nos": info["account_nos"],  # Preserves order in summary statement
                    "pdf_names": info["pdf_names"],
                }, mf, indent=2)
        except Exception:
            pass

    # 3. Discover all candidate PDF files under date_base_dir (excluding summary/ folder)
    discovered_pdfs = []
    for dirpath, dirnames, filenames in os.walk(date_base_dir):
        rel = os.path.relpath(dirpath, date_base_dir)
        if rel == "summary" or rel.startswith("summary" + os.sep):
            dirnames[:] = []  # Do not descend into summary/
            continue
        for fname in filenames:
            if fname.lower().endswith(".pdf"):
                discovered_pdfs.append((fname, os.path.join(dirpath, fname)))

    # 4. Inverted map: norm_account_no -> list of c_ref
    account_to_cr = {}
    for c_ref, info in summary_map.items():
        for acc in info["account_nos"]:
            account_to_cr.setdefault(acc, []).append(c_ref)

    # All summary PDF names across all groups
    all_summary_pdf_names = set()
    for info in summary_map.values():
        all_summary_pdf_names.update(info["pdf_names"])

    moved_count_by_cr = {c_ref: 0 for c_ref in summary_map}
    errors_by_cr = {c_ref: 0 for c_ref in summary_map}

    # First move summary statements
    for c_ref, info in summary_map.items():
        cr_dir = os.path.join(summary_root, c_ref)
        summary_targets = set(info["pdf_names"])
        summary_targets.add(f"{c_ref}_SUMMARY.pdf")

        for fname, src_path in discovered_pdfs:
            if not os.path.exists(src_path):
                continue
            is_match = False
            if fname in summary_targets:
                is_match = True
            elif f"{c_ref}_SUMMARY" in fname.upper():
                is_match = True

            if is_match:
                dest_name = f"00_{fname}" if not fname.startswith("00_") else fname
                dest_path = os.path.join(cr_dir, dest_name)
                try:
                    if os.path.exists(src_path) and os.path.abspath(src_path) != os.path.abspath(dest_path):
                        shutil.move(src_path, dest_path)
                        moved_count_by_cr[c_ref] += 1
                except Exception as e:
                    errors_by_cr[c_ref] += 1
                    if log_callback:
                        log_callback(f"  Summary group warning: could not move summary PDF {fname}: {e}")

    # Next move matching account bills
    for fname, src_path in discovered_pdfs:
        if not os.path.exists(src_path):
            continue
        # Skip summary files themselves
        if fname in all_summary_pdf_names or fname.startswith("00_") or "SUMMARY" in fname.upper():
            continue

        extracted_acc = extract_account_from_filename(fname)
        if not extracted_acc:
            continue

        matching_crs = account_to_cr.get(extracted_acc, [])
        if not matching_crs:
            continue

        for target_cr in matching_crs:
            cr_dir = os.path.join(summary_root, target_cr)
            dest_path = os.path.join(cr_dir, fname)
            if os.path.exists(dest_path):
                continue
            try:
                if os.path.exists(src_path):
                    shutil.move(src_path, dest_path)
                    moved_count_by_cr[target_cr] += 1
                    break  # File moved to this CR folder
            except Exception as e:
                errors_by_cr[target_cr] += 1
                if log_callback:
                    log_callback(f"  Summary group warning: could not move {fname} to {target_cr}: {e}")

    if log_callback:
        for c_ref in summary_map:
            moved = moved_count_by_cr.get(c_ref, 0)
            errs = errors_by_cr.get(c_ref, 0)
            if moved > 0 or errs > 0:
                status = f"({errs} errors)" if errs else "OK"
                log_callback(
                    f"  Summary group [{c_ref}]: {moved} file(s) moved -> {os.path.join(summary_root, c_ref)} {status}"
                )