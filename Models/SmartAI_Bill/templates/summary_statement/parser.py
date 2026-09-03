"""Parser for Summary Statement (DOCTYPE=SUMMARYSTATEMENT)."""
import os

from core.bill_common import SUMST_ADDRESS_PRINT_ORDER, to_float


def parse_summary_statement(file_path: str) -> dict:
    data = {
        "date_of_statement": "",
        "customer_ref_no":   "",
        "invoice_number":    "",
        "contact_name":      "",
        "contact_position":  "",
        "contact_department":"",
        "contact_company":   "",
        "contact_address":   [],
        "contact_zip":       "",
        "accounts":          [],
        "total_net":         0,
        "total_tax":         0,
        "total_gross":       0,
        "source_filename":   os.path.basename(file_path).removesuffix(".processing"),
    }

    # Collect raw address tags for BPR13 reordering
    raw_contact_address = {}

    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        in_invoice_summary = False
        current_account    = None
        last_billref       = None

        for line in f:
            line = line.strip()
            if not line:
                continue

            if line.startswith('BSTARTINVOICESUMMARY'):
                in_invoice_summary = True
                current_account    = {
                    "account_no":   "",
                    "account_name": "",
                    "net_amount":   0,
                    "tax_amount":   0,
                    "gross_total":  0,
                }
                continue

            if line.startswith('BENDINVOICESUMMARY'):
                if current_account and current_account["account_no"]:
                    data["accounts"].append(current_account)
                current_account    = None
                in_invoice_summary = False
                continue

            if (line.startswith('SUBDOCSTART') or
                    line.startswith('SUBDOCEND')):
                continue

            if line.startswith('DOCEND'):
                break

            if '|' not in line:
                continue

            parts  = line.split('|', 1)
            tokens = parts[0].strip().split(None, 1)
            if len(tokens) < 2:
                continue

            key   = tokens[0].upper()
            value = tokens[1].strip()

            # header
            if key == 'ACTUALBILLDATE':
                data["date_of_statement"] = value
            elif key == 'CUSTOMERREF':
                data["customer_ref_no"] = value

            # contact block
            elif key == 'SUMSTCONTACTNAME':
                data["contact_name"] = value
            elif key == 'SUMSTCONTACTPOSITION':
                data["contact_position"] = value
            elif key == 'SUMSTCONTACTDEPARTMENT':
                data["contact_department"] = value
            elif key == 'SUMSTCONTACTCOMPANYNAME':
                data["contact_company"] = value
            elif key in ('SUMSTCONTACTADDR1', 'SUMSTCONTACTADDR2',
                         'SUMSTCONTACTADDR3', 'SUMSTCONTACTADDR4',
                         'SUMSTCONTACTADDR5'):
                # BPR13: store in dict, reorder after parse
                if value:
                    raw_contact_address[key] = value
            elif key == 'SUMSTCONTACTZIP':
                data["contact_zip"] = value

            # Capture BILLREF regardless of invoice summary state
            if key == 'BILLREF':
                last_billref = value

            # accounts
            elif in_invoice_summary:
                if key == 'ACCOUNTNO':
                    current_account["account_no"] = value
                elif key == 'BILLINGCONTACTNAME':
                    current_account["account_name"] = value
                elif key == 'INVNETTTOTAL':
                    current_account["net_amount"] = to_float(value)
                elif key == 'INVTAXTOTAL':
                    current_account["tax_amount"] = to_float(value)
                elif key == 'INVGROSSTOTAL':
                    current_account["gross_total"] = to_float(value)

            # totals
            elif key == 'SUMSTNETTTOTAL':
                data["total_net"] = to_float(value)
            elif key == 'SUMSTTAXTOTAL':
                data["total_tax"] = to_float(value)
            elif key == 'SUMSTGROSSTOTAL':
                data["total_gross"] = to_float(value)

    if last_billref:
        data["invoice_number"] = last_billref

    # BPR13: reorder contact address (5,2,3,4,1)
    data["contact_address"] = [
        raw_contact_address[k]
        for k in SUMST_ADDRESS_PRINT_ORDER
        if raw_contact_address.get(k)
    ]

    # Fallback totals
    if not data["total_net"] and data["accounts"]:
        data["total_net"]   = sum(a["net_amount"]  for a in data["accounts"])
        data["total_tax"]   = sum(a["tax_amount"]  for a in data["accounts"])
        data["total_gross"] = sum(a["gross_total"] for a in data["accounts"])

    return data