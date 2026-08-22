import os
import openpyxl
import csv
import tempfile
import shutil


def count_documents(file_path: str) -> int:
    """Counts customer records in GMF text file, Excel spreadsheet, or CSV."""
    if not file_path or not os.path.exists(file_path):
        return 0

    clean_path = file_path[:-11] if file_path.lower().endswith(".processing") else file_path
    ext = os.path.splitext(clean_path)[1].lower()

    if ext in (".xlsx", ".xls"):
        try:
            with open(file_path, "rb") as f:
                wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
                ws = wb.active
                count = 0
                has_header = False
                for row in ws.iter_rows(values_only=True):
                    if row and any(cell is not None and str(cell).strip() != "" for cell in row):
                        if not has_header:
                            has_header = True
                        else:
                            count += 1
                wb.close()
                return count
        except Exception:
            return 0
    elif ext == ".csv":
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                lines = [r for r in reader if r and any(cell.strip() for cell in r)]
                return max(0, len(lines) - 1)
        except Exception:
            return 0
    else:
        # Standard GMF text file record counting: Count DOCSTART blocks
        docstart_count = 0
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    l = line.strip().upper()
                    if l.startswith("DOCSTART"):
                        docstart_count += 1
            if docstart_count > 0:
                return docstart_count
            return 1
        except Exception:
            return 1


def count_documents_with_breakdown(file_path: str) -> tuple[int, dict[str, int]]:
    """Returns (total_customer_count, template_breakdown_dict) for any GMF file."""
    if not file_path or not os.path.exists(file_path):
        return 0, {}

    clean_path = file_path[:-11] if file_path.lower().endswith(".processing") else file_path
    ext = os.path.splitext(clean_path)[1].lower()

    if ext in (".xlsx", ".xls", ".csv"):
        total = count_documents(file_path)
        from core.template_identifier import identify_template
        tid = identify_template(file_path).template_id or "spreadsheet"
        return total, {tid: total}
    else:
        from core.template_identifier import identify_template
        doc_blocks = []
        current_block = []
        in_doc = False

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                stripped = line.strip()
                if stripped.upper().startswith("DOCSTART"):
                    if current_block:
                        doc_blocks.append("\n".join(current_block))
                    current_block = [line]
                    in_doc = True
                elif stripped.upper().startswith("DOCEND"):
                    current_block.append(line)
                    doc_blocks.append("\n".join(current_block))
                    current_block = []
                    in_doc = False
                elif in_doc:
                    current_block.append(line)

        if current_block:
            doc_blocks.append("\n".join(current_block))

        if not doc_blocks:
            total = count_documents(file_path)
            res = identify_template(file_path)
            tid = res.template_id or "unknown"
            return total, {tid: total}

        breakdown = {}
        for block in doc_blocks:
            with tempfile.NamedTemporaryFile("w", delete=False, suffix=".gmf", encoding="utf-8") as tf:
                tf.write(block)
                tmp_name = tf.name
            try:
                res = identify_template(tmp_name)
                tid = res.template_id or "unknown"
                breakdown[tid] = breakdown.get(tid, 0) + 1
            finally:
                if os.path.exists(tmp_name):
                    try:
                        os.remove(tmp_name)
                    except OSError:
                        pass

        total = sum(breakdown.values())
        return total, breakdown


def split_gmf_documents(file_path: str, offset: int = 0, limit: int = None, original_filename: str = None, approved_templates: set = None) -> list[str]:
    """
    Splits a multi-document GMF text file into individual temporary document file paths.
    For spreadsheets/CSV files, returns [file_path].
    When approved_templates is provided, filters for documents matching approved templates before slicing.
    """
    if not file_path or not os.path.exists(file_path):
        return []

    clean_path = file_path[:-11] if file_path.lower().endswith(".processing") else file_path
    ext = os.path.splitext(clean_path)[1].lower()

    if ext in (".xlsx", ".xls", ".csv"):
        return [file_path]

    doc_blocks = []
    current_block = []
    in_doc = False

    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            stripped = line.strip()
            if stripped.upper().startswith("DOCSTART"):
                if current_block:
                    doc_blocks.append("\n".join(current_block))
                current_block = [line]
                in_doc = True
            elif stripped.upper().startswith("DOCEND"):
                current_block.append(line)
                doc_blocks.append("\n".join(current_block))
                current_block = []
                in_doc = False
            elif in_doc:
                current_block.append(line)

    if current_block:
        doc_blocks.append("\n".join(current_block))

    if not doc_blocks:
        return [file_path]

    # Filter for approved templates in multi-document bulk files
    if approved_templates is not None and len(doc_blocks) > 1:
        from core.template_identifier import identify_template
        filtered_blocks = []
        for block in doc_blocks:
            with tempfile.NamedTemporaryFile("w", delete=False, suffix=".gmf", encoding="utf-8") as tf:
                tf.write(block)
                tmp_name = tf.name
            try:
                res = identify_template(tmp_name)
                tid = res.template_id
                if tid and tid in approved_templates:
                    filtered_blocks.append(block)
            finally:
                if os.path.exists(tmp_name):
                    try:
                        os.remove(tmp_name)
                    except OSError:
                        pass
        doc_blocks = filtered_blocks

    if offset > 0:
        doc_blocks = doc_blocks[offset:]
    if limit is not None and limit > 0:
        doc_blocks = doc_blocks[:limit]

    temp_files = []
    base_name = original_filename or os.path.basename(file_path)
    if base_name.lower().endswith(".processing"):
        base_name = base_name[:-11]
    
    # Prefix is the original filename stripped of extension, to preserve it for downstream checks.
    # GMF files carry no real extension - a trailing ".7" (etc.) is part of
    # the filename's own version/sequence number, not a file extension, so
    # only strip it when it's an actual Office file extension.
    _base_root, _base_ext = os.path.splitext(base_name)
    base_prefix = _base_root if _base_ext.lower() in (".xlsx", ".xls", ".csv") else base_name
    
    for i, block in enumerate(doc_blocks, 1):
        tf = tempfile.NamedTemporaryFile("w", delete=False, prefix=f"{base_prefix}__", suffix=f"_{i}.gmf", encoding="utf-8")
        tf.write(block)
        tf.close()
        temp_files.append(tf.name)

    return temp_files


def write_doc_to_temp(doc_lines, temp_dir, source_filename, doc_index, original_file_path=None):
    """
    Write a single document's lines to a temporary GMF file.
    Preserves original outer filename and binary integrity for Excel files.
    """
    clean_filename = source_filename[:-11] if source_filename.lower().endswith('.processing') else source_filename
    base, ext = os.path.splitext(clean_filename)
    if ext.lower() not in ('.xlsx', '.xls'):
        # GMF files carry no real extension - a trailing ".7" (etc.) is part
        # of the filename's own version/sequence number, not a file
        # extension. Don't let splitext() truncate it.
        base, ext = clean_filename, ""
    if ext.lower() in ('.xlsx', '.xls'):
        temp_name = f"{base}__doc{doc_index:04d}{ext}"
        temp_path = os.path.join(temp_dir, temp_name)
        
        source_path = None
        for line in doc_lines:
            if isinstance(line, str) and line.startswith("PATH="):
                source_path = line.split("PATH=", 1)[1].strip()
                break
        if not source_path and original_file_path:
            source_path = original_file_path

        if source_path and os.path.exists(source_path):
            shutil.copy2(source_path, temp_path)
            return temp_path

    temp_name = f"{base}__doc{doc_index:04d}.gmf"
    temp_path = os.path.join(temp_dir, temp_name)

    with open(temp_path, 'w', encoding='utf-8') as f:
        f.writelines(doc_lines)

    return temp_path
