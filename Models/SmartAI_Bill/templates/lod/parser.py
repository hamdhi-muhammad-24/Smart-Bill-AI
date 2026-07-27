import io
import os
import openpyxl
import csv

ADDRESS_COLUMNS = ["ADDRESS_1", "ADDRESS_2", "ADDRESS_3", "ADDRESS_4", "ADDRESS_5"]

def _clean(value):
    if value is None:
        return ""
    return str(value).strip()

def _format_balance(value):
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return _clean(value)

def parse_lod(file_path, limit=None):
    if hasattr(file_path, 'read'):
        return parse_lod_stream(file_path, limit=limit)
    
    path_str = str(file_path)
    if path_str.endswith('.processing'):
        path_str = path_str[:-11]
        
    if path_str.endswith('.csv'):
        with open(file_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
            return _parse_csv_rows(csv.DictReader(f), limit=limit)
    else:
        with open(file_path, 'rb') as f:
            wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
            return _parse_workbook_rows(wb, limit=limit)

def parse_lod_stream(stream, limit=None, filename=""):
    if filename.endswith('.csv'):
        if isinstance(stream, bytes):
            stream = io.StringIO(stream.decode('utf-8-sig', errors='ignore'))
        return _parse_csv_rows(csv.DictReader(stream), limit=limit)
    else:
        if isinstance(stream, str):
            stream = open(stream, 'rb')
        wb = openpyxl.load_workbook(stream, read_only=True, data_only=True)
        return _parse_workbook_rows(wb, limit=limit)

def _parse_csv_rows(reader, limit=None):
    data = []
    for idx, row in enumerate(reader):
        acc = _clean(row.get("ACCOUNT_NO"))
        if not acc:
            continue
        address_lines = [
            _clean(row.get(col)) for col in ADDRESS_COLUMNS if _clean(row.get(col))
        ]
        data.append({
            "client_name": _clean(row.get("CUSTOMER_NAME")),
            "client_address_lines": address_lines,
            "outstanding_balance": _format_balance(row.get("ARREARS")),
            "account_number": acc,
            "telephone_number": _clean(row.get("EVENT_SOURCE")),
            "regional_office": _clean(row.get("BILLING_CENTRE")),
            "reference_number": str(len(data) + 1),
            "letter_date": _clean(row.get("DATE")),
        })
        if limit and len(data) >= limit:
            break
    return data

def _parse_workbook_rows(wb, limit=None):
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    try:
        header = next(rows)
    except StopIteration:
        wb.close()
        return []
        
    columns = {str(name).strip(): idx for idx, name in enumerate(header) if name is not None}
    data = []
    
    acc_idx = columns.get("ACCOUNT_NO")
    name_idx = columns.get("CUSTOMER_NAME")
    arr_idx = columns.get("ARREARS")
    src_idx = columns.get("EVENT_SOURCE")
    ctr_idx = columns.get("BILLING_CENTRE")
    dt_idx = columns.get("DATE")
    
    for row in rows:
        account_no = _clean(row[acc_idx]) if acc_idx is not None and acc_idx < len(row) else ""
        if not account_no:
            continue

        address_lines = []
        for col in ADDRESS_COLUMNS:
            col_idx = columns.get(col)
            if col_idx is not None and col_idx < len(row):
                val = _clean(row[col_idx])
                if val:
                    address_lines.append(val)

        data.append({
            "client_name": _clean(row[name_idx]) if name_idx is not None and name_idx < len(row) else "",
            "client_address_lines": address_lines,
            "outstanding_balance": _format_balance(row[arr_idx]) if arr_idx is not None and arr_idx < len(row) else "0.00",
            "account_number": account_no,
            "telephone_number": _clean(row[src_idx]) if src_idx is not None and src_idx < len(row) else "",
            "regional_office": _clean(row[ctr_idx]) if ctr_idx is not None and ctr_idx < len(row) else "",
            "reference_number": str(len(data) + 1),
            "letter_date": _clean(row[dt_idx]) if dt_idx is not None and dt_idx < len(row) else "",
        })

        if limit and len(data) >= limit:
            break

    wb.close()
    return data
