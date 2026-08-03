"""Split a multi-document GMF file into individual document blocks."""
import os
import shutil


def split_gmf_documents(file_path):
    clean_path = str(file_path)[:-11] if str(file_path).lower().endswith('.processing') else str(file_path)
    # If the file is an Excel file (.xlsx / .xls), treat as a single document
    if clean_path.lower().endswith(('.xlsx', '.xls')):
        return [["__EXCEL_FILE__\n", f"PATH={os.path.abspath(file_path)}\n"]]

    documents = []
    current_lines = []
    in_doc = False

    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            all_lines = f.readlines()
            for line in all_lines:
                stripped = line.strip()

                if stripped.startswith('DOCSTART'):
                    in_doc = True
                    current_lines = [line]
                elif stripped.startswith('DOCEND'):
                    if in_doc:
                        current_lines.append(line)
                        documents.append(current_lines)
                        current_lines = []
                        in_doc = False
                elif in_doc:
                    current_lines.append(line)
    except Exception:
        pass

    if not documents:
        # Fallback for simple GMF files without explicit DOCSTART/DOCEND blocks
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                documents = [f.readlines()]
        except Exception:
            documents = [[]]

    return documents


def write_doc_to_temp(doc_lines, temp_dir, source_filename, doc_index, original_file_path=None):
    """
    Write a single document's lines to a temporary GMF file.
    Preserves original outer filename and binary integrity for Excel files.
    """
    clean_filename = source_filename[:-11] if source_filename.lower().endswith('.processing') else source_filename
    base, ext = os.path.splitext(clean_filename)
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


def count_documents(file_path):
    clean_path = str(file_path)[:-11] if str(file_path).lower().endswith('.processing') else str(file_path)
    ext = os.path.splitext(clean_path)[1].lower()
    if ext in ('.xlsx', '.xls', '.csv'):
        try:
            if ext == '.csv':
                import csv
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    reader = csv.reader(f)
                    rows = [r for r in reader if any(cell.strip() for cell in r)]
                    return max(1, len(rows) - 1 if len(rows) > 1 else len(rows))
            else:
                import openpyxl
                wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
                sheet = wb.active
                # Count non-empty rows
                row_count = 0
                for row in sheet.iter_rows(values_only=True):
                    if any(cell is not None and str(cell).strip() != "" for cell in row):
                        row_count += 1
                wb.close()
                return max(1, row_count - 1 if row_count > 1 else row_count)
        except Exception as e:
            return 1
    count = 0
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                if line.strip().startswith('DOCSTART'):
                    count += 1
    except Exception:
        pass
    return count if count > 0 else 1

