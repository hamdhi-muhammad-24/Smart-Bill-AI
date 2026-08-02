"""Split a multi-document GMF file into individual document blocks."""
import os
import shutil


def split_gmf_documents(file_path):
    # If the file is an Excel file (.xlsx / .xls), treat as a single document
    if str(file_path).lower().endswith(('.xlsx', '.xls')):
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
    base, ext = os.path.splitext(source_filename)
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
    if str(file_path).lower().endswith(('.xlsx', '.xls')):
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

