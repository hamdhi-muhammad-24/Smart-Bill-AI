"""
Shared helpers used across all GMF bill parsers/renderers.
Only truly cross-cutting logic lives here (needed in 4+ templates).
"""
# BPR13: fixed print order for address lines
ADDRESS_PRINT_ORDER = ('ADDRESS5', 'ADDRESS2', 'ADDRESS3', 'ADDRESS4', 'ADDRESS1')
SUMST_ADDRESS_PRINT_ORDER = (
    'SUMSTCONTACTADDR5', 'SUMSTCONTACTADDR2',
    'SUMSTCONTACTADDR3', 'SUMSTCONTACTADDR4',
    'SUMSTCONTACTADDR1',
)

# BPR30: product label renames
LABEL_OVERRIDES = {
    'VPA':        'LPF',
    'VPA UnBill': 'LPF Reversal',
}

# BPR23: top-level Discounts block tag pairs
TOP_LEVEL_DISCOUNT_TAGS = {
    'ACCDISCNAME':      'ACCDISCTOTAL',
    'CUSTDISCNAME':     'CUSTDISCTOTAL',
    'PACKDISCNAME':     'PACKDISCTOTAL',
    'PRODDISCNAME':     'PRODDISCTOTAL',
    'EVENTSRCDISCNAME': 'EVENTSRCDISCTOTAL',
    'SUBSDISCNAME':     'SUBSDISCTOTAL',
}
TOP_LEVEL_DISCOUNT_TOTAL_TAGS = set(TOP_LEVEL_DISCOUNT_TAGS.values())

# BPR28: marketing message tags in print order
MARKETING_MESSAGE_TAGS = [f'MARKETINGMESSAGE{i}' for i in range(1, 11)]


# Shared to_float (replaces all local _to_float)
def to_float(value):
    if value is None or value == "":
        return 0
    try:
        return float(str(value).replace(",", ""))
    except (ValueError, TypeError):
        return 0


# BPR21: strip characters before first underscore
def strip_before_underscore(text):
    if not text:
        return text
    text = text.strip()
    return text.split('_', 1)[-1].strip() if '_' in text else text


# BPR30: VPA → LPF etc.
def apply_label_override(label):
    return LABEL_OVERRIDES.get(label, label)


# BPR13: reorder address lines to fixed order
def reorder_addresses(raw_address, keys=ADDRESS_PRINT_ORDER):
    return [raw_address[k] for k in keys if raw_address.get(k)]


# BPR05/07: VAT reg printable check
def is_vat_reg_printable(customer_vat_ref):
    if not customer_vat_ref:
        return False
    return not customer_vat_ref.strip().upper().startswith('VATDL')


# BPR11/24: tax section printable check
def is_tax_section_printable(tax_status, has_nonzero_tax):
    if (tax_status or '').strip().upper() == 'INCLUSIVE':
        return False
    return bool(has_nonzero_tax)


# BPR23: top-level discount collector
class TopLevelDiscountCollector:
    """
    Accumulates ACCDISCNAME/ACCDISCTOTAL-style pairs.
    Call handle(key, value) on every tag — returns True if consumed.
    """

    def __init__(self):
        self._pending_name = {}
        self.discounts = []

    def handle(self, key, value):
        if key in TOP_LEVEL_DISCOUNT_TAGS:
            self._pending_name[key] = value
            return True
        if key in TOP_LEVEL_DISCOUNT_TOTAL_TAGS:
            name_key = next(
                (k for k, v in TOP_LEVEL_DISCOUNT_TAGS.items() if v == key),
                None
            )
            amt = to_float(value)
            if amt:
                name = (self._pending_name.pop(name_key, '')
                        if name_key else '')
                self.discounts.append({
                    'description': strip_before_underscore(name) or key,
                    'amount': -abs(amt),
                })
            return True
        return False


# BPR26: parse cancelled/reversed payment line
def parse_cancel_payment(value, rest_parts):
    """
    $ACCBALFPAYDET layout:
      display date = field #2 (index 1)
      amount       = field #4 (index 3)
      pay type     = field #14 (index 13)
    """
    all_parts = [value] + list(rest_parts)
    date = all_parts[1] if len(all_parts) > 1 and all_parts[1] else all_parts[0]
    amount = to_float(all_parts[3]) if len(all_parts) > 3 else 0
    pay_type = (
        all_parts[13].strip()
        if len(all_parts) > 13 and all_parts[13].strip()
        else 'Cancelled Payment'
    )
    return {
        'date':     date,
        'pay_type': pay_type,
        'location': '',
        'amount':   amount,
    }


# BPR14: telephone from no-sub-ref block only
# (used by nonvat_home + nonvat_enterprise)
class PhoneNumberFromNoSubRefBlock:
    """
    Finds the invoice telephone number:
      - Must be inside BSTARTSLTNOSUBSCRIPTIONREF block
      - Must be a 10-digit SLTPRODUCTLABEL
      - Must have at least one real charge line confirmed
    """

    def __init__(self):
        self._in_block  = False
        self._pending   = None
        self.result     = ''

    def enter_block(self):
        self._in_block = True
        self._pending  = None

    def exit_block(self):
        self._in_block = False
        self._pending  = None

    def candidate(self, label):
        if self.result:
            return
        if self._in_block and label.isdigit() and len(label) == 10:
            self._pending = label
        else:
            self._pending = None

    def confirm_charge(self):
        if not self.result and self._pending:
            self.result = self._pending