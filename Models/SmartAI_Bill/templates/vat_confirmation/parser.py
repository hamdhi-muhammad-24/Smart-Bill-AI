import io
import os
import openpyxl
import csv

def _clean(val):
    if val is None:
        return ""
    return str(val).strip()

def parse_vat_confirmation(file_path, limit=None):
    if hasattr(file_path, 'read'):
        return parse_vat_confirmation_stream(file_path, limit=limit)
        
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

def parse_vat_confirmation_stream(stream, limit=None, filename=""):
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
        name = _clean(row.get("VAT Name") or row.get("recipient_name") or row.get("CUSTOMER_NAME"))
        if not name:
            continue
        ref = _clean(row.get("CR No") or row.get("Account No") or row.get("reference") or row.get("ACCOUNT_NO") or str(idx + 1))
        vat_no = _clean(row.get("VAT No") or row.get("vat_no"))
        addr1 = _clean(row.get("Registered Address 1") or row.get("address_line1"))
        addr2 = _clean(row.get("Registered Address 2") or row.get("address_line2"))
        addr3 = _clean(row.get("Registered Address 3") or row.get("address_line3"))
        addr4 = _clean(row.get("Registered Address 4") or row.get("address_line4"))
        
        address_lines = [line for line in (name, addr1, addr2, addr3, addr4) if line]
        data.append({
            "recipient_name": name,
            "reference": ref,
            "vat_no": vat_no or "N/A",
            "address_lines": address_lines,
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

    header_clean = [_clean(h) for h in header]
    columns = {name: idx for idx, name in enumerate(header_clean) if name}
    
    name_idx = columns.get("VAT Name") or columns.get("recipient_name") or columns.get("CUSTOMER_NAME")
    ref_idx = columns.get("CR No") or columns.get("Account No") or columns.get("reference") or columns.get("ACCOUNT_NO")
    vat_idx = columns.get("VAT No") or columns.get("vat_no")
    
    addr1_idx = columns.get("Registered Address 1") or columns.get("address_line1")
    addr2_idx = columns.get("Registered Address 2") or columns.get("address_line2")
    addr3_idx = columns.get("Registered Address 3") or columns.get("address_line3")
    addr4_idx = columns.get("Registered Address 4") or columns.get("address_line4")

    data = []
    for idx, row in enumerate(rows):
        name = _clean(row[name_idx]) if name_idx is not None and name_idx < len(row) else ""
        if not name:
            continue
            
        ref = _clean(row[ref_idx]) if ref_idx is not None and ref_idx < len(row) else str(idx + 1)
        vat_no = _clean(row[vat_idx]) if vat_idx is not None and vat_idx < len(row) else "N/A"
        
        a1 = _clean(row[addr1_idx]) if addr1_idx is not None and addr1_idx < len(row) else ""
        a2 = _clean(row[addr2_idx]) if addr2_idx is not None and addr2_idx < len(row) else ""
        a3 = _clean(row[addr3_idx]) if addr3_idx is not None and addr3_idx < len(row) else ""
        a4 = _clean(row[addr4_idx]) if addr4_idx is not None and addr4_idx < len(row) else ""
        
        address_lines = [line for line in (name, a1, a2, a3, a4) if line]
        data.append({
            "recipient_name": name,
            "reference": ref,
            "vat_no": vat_no,
            "address_lines": address_lines,
        })
        if limit and len(data) >= limit:
            break
            
    wb.close()
    return data
