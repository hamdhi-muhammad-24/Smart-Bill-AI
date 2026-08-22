import os

# Category mapping — based on BPR03 rules
BILL_HANDLING_CATEGORY = {
    #Email / E-statement only
    '02': 'email',   # E-statement by email
    '04': 'email',   # E-statement on web
    '06': 'email',   # Prestige - E-statement (treat as 02)
    '13': 'email',   # Corporate_E-Statement by FTP
    '21': 'email',   # Corporate_E-statement by Email
    '22': 'email',   # Corporate_E-statement by Report
    '23': 'email',   # E-Statement-App Mode
    '24': 'email',   # E-Statement by SMS
    '10': 'email',   # By Hand - Operator
    '11': 'email',   # By Hand - Special
    '25': 'email',   # whatsapp
    '26': 'email',   # cooparate e bill

    #Print only (hard copy delivery)
    '01': 'print',   # Hard Copy
    '05': 'print',   # Prestige - Post (treat as 01)
    '08': 'print',   # By Hand - Data
    '09': 'print',   # By Hand - BCU
    '15': 'print',   # BCU Single side print

    #Both print and email/digital
    '03': 'print_and_email',  # E-statement & Post
    '16': 'print_and_email',  # Prestige - Post & E-statement
    '19': 'print_and_email',  # Corporate Hard Copy & E-Bill
    '20': 'print_and_email',  # Hard Copy & CD (physical + digital)

    #Other
    '07': 'other',   # Prepaid (no bill delivery)
    '12': 'other',   # No Print (explicitly no delivery)
    '14': 'other',   # DNR (Do Not Return)
    '17': 'other',   # Special List 1 (needs manual review)
    '18': 'other',   # Special List 2 (needs manual review)
}

CATEGORY_FOLDERS = {
    'email':           'Email',
    'print':           'Print',
    'print_and_email': 'Email & Print',
    'other':           'Other',
}

def categorize_bill_handling_code(code):
    if not code:
        return 'other'
    # Normalize (strip whitespace, keep leading zeros)
    code = str(code).strip().zfill(2)
    return BILL_HANDLING_CATEGORY.get(code, 'other')

def get_category_folder(category):
    return CATEGORY_FOLDERS.get(category, 'Other')



class GMFHeader:
    def __init__(self):
        self.doctype = None
        self.billstyle = None
        self.billtype = None
        self.customer_vat_ref = None
        self.customer_type = None
        self.acc_tax_status = None
        self.acc_currency_code = None
        self.raw_tags = {}
        self.filename = ""
        self.file_path = ""

    def __repr__(self):
        return f"<GMFHeader doctype={self.doctype} billstyle={self.billstyle}>"


def read_gmf_header(file_path: str) -> GMFHeader:
    """Read only the outer DOCSTART block for identification (fast).

    IMPORTANT: Summary Statement files (DOCTYPE=SUMMARYSTATEMENT) wrap
    multiple per-account bill blocks inside SUBDOCSTART...SUBDOCEND
    sections, and each of those nested blocks has its own DOCTYPE BILL,
    BILLSTYLE, BILLTYPE, CUSTOMERVATREF, CUSTOMERTYPE, ACCTAXSTATUS tags.
    We must stop reading as soon as we hit the first SUBDOCSTART, or
    those nested tags will silently overwrite the outer document's
    identification tags (e.g. DOCTYPE SUMMARYSTATEMENT getting clobbered
    by the first nested DOCTYPE BILL).
    """
    header = GMFHeader()
    header.file_path = file_path
    header.filename = os.path.basename(file_path)

    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        in_docstart = False
        for line in f:
            line = line.strip()

            if line.startswith('DOCSTART'):
                in_docstart = True
                continue

            if in_docstart:
                # Stop at the first nested sub-document OR the first
                # body block OR end of document -- whichever comes first.
                if (line.startswith('SUBDOCSTART')
                        or line.startswith('BSTARTBFSTATEMENT')
                        or line.startswith('DOCEND')):
                    break

                if '|' in line:
                    parts = line.split('|', 1)
                    key_val = parts[0].strip()
                    tokens = key_val.split(None, 1)
                    if len(tokens) >= 2:
                        key = tokens[0].upper()
                        value = tokens[1].strip()
                        header.raw_tags[key] = value

                        if key == 'DOCTYPE':
                            header.doctype = value
                        elif key == 'BILLSTYLE':
                            try:
                                header.billstyle = int(value)
                            except ValueError:
                                header.billstyle = value
                        elif key == 'BILLTYPE':
                            try:
                                header.billtype = int(value)
                            except ValueError:
                                header.billtype = value
                        elif key == 'CUSTOMERVATREF':
                            header.customer_vat_ref = value if value else None
                        elif key == 'CUSTOMERTYPE':
                            header.customer_type = value
                        elif key == 'ACCTAXSTATUS':
                            header.acc_tax_status = value
                        elif key == 'ACCCURRENCYCODE':
                            header.acc_currency_code = value

    return header


def parse_filename(filename: str) -> dict:
    result = {}
    try:
        parts = filename.rsplit('_', 1)
        if len(parts) != 2:
            return result

        left = parts[0]
        result['subseq'] = parts[1]

        first_split = left.split('_', 1)
        if len(first_split) != 2:
            return result

        result['seq'] = first_split[0]
        rest = first_split[1]

        tokens = rest.split('-')
        if len(tokens) >= 8:
            result['invoicing_co']  = tokens[0]
            result['bill_style']    = int(tokens[1])
            result['bill_handling'] = tokens[2]
            result['bill_lang']     = tokens[3]
            result['currency']      = tokens[4]
            result['country']       = tokens[5]
            result['cca']           = tokens[6]
            result['doctype']       = tokens[7]
            if len(tokens) > 8:
                result['flags'] = tokens[8:]
    except (ValueError, IndexError):
        pass
    return result


def is_red_notice(filename: str) -> bool:
    """Return True if filename matches RED notice pattern (e.g. BILL-RED)."""
    if not filename:
        return False
    name = str(filename).upper()
    return "BILL-RED" in name or "-RED_" in name or "_RED." in name or name.endswith("-RED")