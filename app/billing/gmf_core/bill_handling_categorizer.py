"""
Categorizes bills by BILLHANDLINGCODE into delivery method folders.

Categories:
  - email          : E-statement delivery only (no printing)
  - print          : Hard copy printing only (no email)
  - print_and_email: Both delivery methods
  - other          
"""

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

    #Print only (hard copy delivery)
    '01': 'print',   # Hard Copy
    '05': 'print',   # Prestige - Post (treat as 01)
    '08': 'print',   # By Hand - Data
    '09': 'print',   # By Hand - BCU
    '10': 'print',   # By Hand - Operator
    '11': 'print',   # By Hand - Special
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
    'email':           'e-statement',
    'print':           'print',
    'print_and_email': 'print_and_e-statement',
    'other':           'other',
}


def categorize_bill_handling_code(code):
    if not code:
        return 'other'
    
    # Normalize (strip whitespace, keep leading zeros)
    code = str(code).strip().zfill(2)
    
    return BILL_HANDLING_CATEGORY.get(code, 'other')


def get_category_folder(category):
    return CATEGORY_FOLDERS.get(category, 'other')