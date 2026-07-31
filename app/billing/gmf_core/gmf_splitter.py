"""Split a multi-document GMF file into individual document blocks."""
import os


def split_gmf_documents(file_path):
    documents = []
    current_lines = []
    in_doc = False

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

    if not documents:
        # Fallback for simple GMF files without explicit DOCSTART/DOCEND blocks
        documents = [all_lines]

    return documents


def write_doc_to_temp(doc_lines, temp_dir, source_filename, doc_index):
    """
    Write a single document's lines to a temporary GMF file.
    Preserves original outer filename for RED/NONRED notice detection.
    """
    base = os.path.splitext(source_filename)[0]
    temp_name = f"{base}__doc{doc_index:04d}.gmf"
    temp_path = os.path.join(temp_dir, temp_name)

    with open(temp_path, 'w', encoding='utf-8') as f:
        f.writelines(doc_lines)

    return temp_path


def count_documents(file_path):
    count = 0
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            if line.strip().startswith('DOCSTART'):
                count += 1
    return count if count > 0 else 1
