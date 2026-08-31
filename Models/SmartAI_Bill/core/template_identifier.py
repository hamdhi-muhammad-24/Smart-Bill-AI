from core.gmf_reader import read_gmf_header, parse_filename, GMFHeader
from core.customer_type_mapper import get_badge, is_vat_registered


# Supported template IDs
TEMPLATE_NONVAT_HOME               = "nonvat_home"
TEMPLATE_NONVAT_ENTERPRISE         = "nonvat_enterprise"
TEMPLATE_VAT_ENTERPRISE            = "vat_enterprise"
TEMPLATE_VAT_HOME                  = "vat_home"
TEMPLATE_VAT_CREDITNOTE            = "vat_creditnote"
TEMPLATE_NONVAT_CREDITNOTE         = "nonvat_creditnote"
TEMPLATE_PRODUCT_LABEL_GROUPING    = "product_label_grouping"
TEMPLATE_SUBSCRIPTION_REF_GROUPING = "subscription_ref_grouping"
TEMPLATE_SUMMARY_STATEMENT         = "summary_statement"
TEMPLATE_INVOICE_OF_SUMMARY        = "invoice_of_summary"
TEMPLATE_USD_OPEN_ITEM             = "usd_open_item"  

# Out-of-scope
UNSUPPORTED_FOREIGN_CURRENCY  = "foreign_currency"


class IdentificationResult:
    def __init__(self):
        self.template_id = None
        self.badge = None
        self.is_supported = False
        self.reasons = []
        self.warnings = []
        self.header = None
        self.filename_info = {}

    def __repr__(self):
        return (f"<Identification template={self.template_id} "
                f"badge={self.badge} supported={self.is_supported}>")


def identify_template_from_header(header: GMFHeader, original_filename: str = None) -> IdentificationResult:
    """Identify template directly from an in-memory GMFHeader object (0ms disk I/O)."""
    result = IdentificationResult()
    result.header = header
    fname = (original_filename or header.filename or "").lower()
    if fname.endswith('.processing'):
        fname = fname[:-11]

    # Special filename matching
    if "lod" in fname or "letter of demand" in fname:
        result.template_id = "lod"
        result.is_supported = True
        result.reasons.append("Filename matches LOD template")
        return result
    if "vat" in fname and ("confirm" in fname or "customer" in fname or "recipients" in fname or "list" in fname or "002" in fname):
        result.template_id = "vat_confirmation"
        result.is_supported = True
        result.reasons.append("Filename matches VAT Confirmation template")
        return result
    if "final" in fname and "notice" in fname:
        result.template_id = "final_notice"
        result.is_supported = True
        result.reasons.append("Filename matches Final Notice template")
        return result
    if "letter" in fname or "migration" in fname or "v1print" in fname:
        result.template_id = "customer_letter_logo_v1print"
        result.is_supported = True
        result.reasons.append("Filename matches Customer Letter template")
        return result

    result.filename_info = parse_filename(header.filename)

    # Exclusion checks
    if header.billtype == 5:
        is_vat = is_vat_registered(header.customer_vat_ref or "")
        if is_vat:
            result.template_id = TEMPLATE_VAT_CREDITNOTE
            result.reasons.append("BILLTYPE=5 → VAT Credit Note")
        else:
            result.template_id = TEMPLATE_NONVAT_CREDITNOTE
            result.reasons.append("BILLTYPE=5 → NonVAT Credit Note")
        result.is_supported = True
        return result

    if header.acc_currency_code and header.acc_currency_code.strip().upper() != "RS":
        if header.billstyle != 21:
            result.template_id = UNSUPPORTED_FOREIGN_CURRENCY
            result.reasons.append(f"ACCCURRENCYCODE={header.acc_currency_code} → Foreign currency")
            return result

    # DOCTYPE routing
    if header.doctype == "SUMMARYSTATEMENT":
        result.template_id = TEMPLATE_SUMMARY_STATEMENT
        result.reasons.append("DOCTYPE=SUMMARYSTATEMENT → Summary Statement")
        result.is_supported = True
        return result

    if header.doctype not in ("BILL", "BCR"):
        result.reasons.append(f"Unrecognized DOCTYPE: {header.doctype}")
        result.warnings.append("Manual review needed")
        return result

    # BILLSTYLE routing
    style = header.billstyle
    is_vat = is_vat_registered(header.customer_vat_ref or "")

    if style == 19:
        result.template_id = TEMPLATE_PRODUCT_LABEL_GROUPING
        result.reasons.append("BILLSTYLE=19 → Product Label Grouping")
        result.is_supported = True
    elif style == 20:
        result.template_id = TEMPLATE_SUBSCRIPTION_REF_GROUPING
        result.reasons.append("BILLSTYLE=20 → Subscription Ref Grouping")
        result.is_supported = True
    elif style == 21:
        result.template_id = TEMPLATE_USD_OPEN_ITEM
        result.reasons.append("BILLSTYLE=21 → USD Open Item")
        result.is_supported = True
    elif style == 1:
        if is_vat:
            badge = get_badge(header.customer_type or "")
            if badge == "HOME":
                result.template_id = TEMPLATE_VAT_HOME
                result.reasons.append("BILLSTYLE=1, VAT Customer, Home → VAT Home")
            else:
                result.template_id = TEMPLATE_VAT_ENTERPRISE
                result.reasons.append("BILLSTYLE=1, VAT Customer → VAT Enterprise")
        else:
            badge = get_badge(header.customer_type or "")
            if badge == "HOME":
                result.template_id = TEMPLATE_NONVAT_HOME
                result.reasons.append(f"BILLSTYLE=1, non-VAT, {header.customer_type} → NonVAT Home")
            else:
                result.template_id = TEMPLATE_NONVAT_ENTERPRISE
                result.reasons.append(f"BILLSTYLE=1, non-VAT, {header.customer_type} → NonVAT Enterprise")
        result.is_supported = True
    elif style == 18:
        result.template_id = TEMPLATE_INVOICE_OF_SUMMARY
        result.reasons.append("BILLSTYLE=18 → Invoice of Summary")
        result.is_supported = True
    else:
        result.reasons.append(f"Unrecognized BILLSTYLE: {style}")
        result.warnings.append("Manual review needed")
        return result

    result.badge = get_badge(header.customer_type or "")
    if result.badge == "UNKNOWN":
        result.warnings.append(f"CUSTOMERTYPE={header.customer_type} not mapped")

    return result


def identify_template(gmf_file_path: str, original_filename: str = None) -> IdentificationResult:
    """Identify which template a GMF file needs."""
    result = IdentificationResult()
    
    from pathlib import Path
    path_obj = Path(gmf_file_path)
    
    fname = (original_filename or path_obj.name).lower()
    
    if fname.endswith('.processing'):
        fname = fname[:-11]

    # Special spreadsheet template matching ONLY if filename matches and file is NOT a temp GMF document block
    is_temp_gmf_block = not original_filename and fname.startswith("tmp")

    if not is_temp_gmf_block:
        if "lod" in fname or "letter of demand" in fname:
            result.template_id = "lod"
            result.is_supported = True
            result.reasons.append("Filename matches LOD template")
            return result
        if "vat" in fname and ("confirm" in fname or "customer" in fname or "recipients" in fname or "list" in fname or "002" in fname):
            result.template_id = "vat_confirmation"
            result.is_supported = True
            result.reasons.append("Filename matches VAT Confirmation template")
            return result
        if "final" in fname and "notice" in fname:
            result.template_id = "final_notice"
            result.is_supported = True
            result.reasons.append("Filename matches Final Notice template")
            return result
        if "letter" in fname or "migration" in fname or "v1print" in fname:
            result.template_id = "customer_letter_logo_v1print"
            result.is_supported = True
            result.reasons.append("Filename matches Customer Letter template")
            return result

    path_str = str(gmf_file_path).lower()
    if path_str.endswith('.processing'):
        path_str = path_str[:-11]

    # Check Excel / CSV headers if extension is spreadsheet
    if path_str.endswith(('.xlsx', '.xls', '.csv')):
        try:
            if path_str.endswith('.csv'):
                import csv
                with open(gmf_file_path, 'r', encoding='utf-8', errors='replace') as f:
                    reader = csv.reader(f)
                    first_row = [str(cell).upper() for cell in next(reader, [])]
            else:
                import openpyxl
                with open(gmf_file_path, 'rb') as f:
                    wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
                    ws = wb.active
                    first_row = [str(cell).upper() for cell in next(ws.iter_rows(values_only=True), []) if cell is not None]
                    wb.close()

            if any("TOTAL_ARREARS" in h or "DUE DATE" in h for h in first_row):
                result.template_id = "final_notice"
                result.is_supported = True
                result.reasons.append("Headers match Final Notice template")
                return result
            if any("ADDR_FULL" in h or "TELEPHONE_STATUS" in h or "SERIAL_NUM" in h or "CUSTOMER_REF" in h for h in first_row):
                result.template_id = "customer_letter_logo_v1print"
                result.is_supported = True
                result.reasons.append("Headers match Customer Letter template")
                return result
        except Exception:
            pass

    header = read_gmf_header(gmf_file_path)
    result.header = header
    result.filename_info = parse_filename(header.filename)

    # Exclusion checks
    if header.billtype == 5:
        is_vat = is_vat_registered(header.customer_vat_ref or "")
        if is_vat:
            result.template_id = TEMPLATE_VAT_CREDITNOTE
            result.reasons.append("BILLTYPE=5 → VAT Credit Note")
        else:
            result.template_id = TEMPLATE_NONVAT_CREDITNOTE
            result.reasons.append("BILLTYPE=5 → NonVAT Credit Note")

        result.is_supported = True
        return result

    if header.acc_currency_code and header.acc_currency_code.strip().upper() != "RS":
        # Allow foreign currency only for USD Open Item (BILLSTYLE 21)
        if header.billstyle != 21:
            result.template_id = UNSUPPORTED_FOREIGN_CURRENCY
            result.reasons.append(
                f"ACCCURRENCYCODE={header.acc_currency_code} → Foreign currency"
            )
            return result

    # DOCTYPE routing
    if header.doctype == "SUMMARYSTATEMENT":
        result.template_id = TEMPLATE_SUMMARY_STATEMENT
        result.reasons.append("DOCTYPE=SUMMARYSTATEMENT → Summary Statement")
        result.is_supported = True
        return result

    if header.doctype not in ("BILL", "BCR"):
        result.reasons.append(f"Unrecognized DOCTYPE: {header.doctype}")
        result.warnings.append("Manual review needed")
        return result

    # BILLSTYLE routing
    style = header.billstyle
    is_vat = is_vat_registered(header.customer_vat_ref or "")

    if style == 19:
        result.template_id = TEMPLATE_PRODUCT_LABEL_GROUPING
        result.reasons.append("BILLSTYLE=19 → Product Label Grouping")
        result.is_supported = True

    elif style == 20:
        result.template_id = TEMPLATE_SUBSCRIPTION_REF_GROUPING
        result.reasons.append("BILLSTYLE=20 → Subscription Ref Grouping")
        result.is_supported = True

    elif style == 21:
        result.template_id = TEMPLATE_USD_OPEN_ITEM
        result.reasons.append("BILLSTYLE=21 → USD Open Item")
        result.is_supported = True

    elif style == 1:
        # Check explicitly if the customer has a VAT registration
        if is_vat:
            badge = get_badge(header.customer_type or "")
            if badge == "HOME":
                result.template_id = TEMPLATE_VAT_HOME
                result.reasons.append("BILLSTYLE=1, VAT Customer, Home → VAT Home")
            else:
                result.template_id = TEMPLATE_VAT_ENTERPRISE
                result.reasons.append("BILLSTYLE=1, VAT Customer → VAT Enterprise")
        else:
            badge = get_badge(header.customer_type or "")
            if badge == "HOME":
                result.template_id = TEMPLATE_NONVAT_HOME
                result.reasons.append(
                    f"BILLSTYLE=1, non-VAT, {header.customer_type} → NonVAT Home"
                )
            else:
                result.template_id = TEMPLATE_NONVAT_ENTERPRISE
                result.reasons.append(
                    f"BILLSTYLE=1, non-VAT, {header.customer_type} → NonVAT Enterprise"
                )
        result.is_supported = True

    elif style == 18:
        result.template_id = TEMPLATE_INVOICE_OF_SUMMARY
        result.reasons.append("BILLSTYLE=18 → Invoice of Summary")
        result.is_supported = True

    else:
        result.reasons.append(f"Unrecognized BILLSTYLE: {style}")
        result.warnings.append("Manual review needed")
        return result

    # Badge
    result.badge = get_badge(header.customer_type or "")
    if result.badge == "UNKNOWN":
        result.warnings.append(f"CUSTOMERTYPE={header.customer_type} not mapped")

    return result