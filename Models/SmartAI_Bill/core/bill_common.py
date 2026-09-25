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


# BPR13 & BPR10: reorder address lines to fixed order, appending COUNTRY for non-LKR customers
def reorder_addresses(raw_address, keys=ADDRESS_PRINT_ORDER, currency_code=None, country=None):
    lines = [raw_address[k] for k in keys if raw_address.get(k)]
    # BPR10: Country name printing under billing address for non LKR customers.
    # Logic: If "ACCCURRENCYCODE" is not Rs, then print "COUNTRY"
    c_val = country or raw_address.get('COUNTRY')
    curr = (currency_code or raw_address.get('ACCCURRENCYCODE') or '').strip().upper()
    if curr and curr != 'RS' and c_val:
        c_clean = str(c_val).strip()
        if c_clean and c_clean not in lines:
            lines.append(c_clean)
    return lines


# BPR20 & BPR10: standard charge type flag decoder
def decode_charge_flag(flag, start=None, end=None, count=None, unit=None,
                       billing_start=None, billing_end=None):
    """
    Decodes charge types:
      P/S: Rental (date range only if different from bill period)
      I:   Initiation (only start date)
      E:   Early Termination Charge (only start date)
      T:   Termination Charge
      O:   One time (start date/time and quantity)
    """
    f = (flag or '').strip().upper()
    has_qty = count not in ('', '0', None) or unit not in ('', None)
    qty_str = f" [{f'{count} {unit}'.strip() if unit else count}]" if has_qty else ""

    if f in ('P', 'S'):
        desc = " [Rental]" + qty_str
        if start and end and (start != billing_start or end != billing_end):
            desc += f" ({start}-{end})"
        return desc
    elif f == 'O':
        desc = " [One Time]" + (f" [{count}]" if has_qty else "")
        if start:
            desc += f" ({start})"
        return desc
    elif f == 'I':
        desc = " [Initiation]" + qty_str
        if start:
            desc += f" ({start})"
        return desc
    elif f == 'E':
        desc = " [Early Termination Charge]" + qty_str
        if start:
            desc += f" ({start})"
        return desc
    elif f == 'T':
        return " [Termination Charge]" + qty_str
    return ""


# BPR05/07: VAT reg printable check
def is_vat_reg_printable(customer_vat_ref):
    if not customer_vat_ref:
        return False
    ref = str(customer_vat_ref).strip()
    if not ref:
        return False
    cleaned = ref.upper().replace(" ", "").replace("-", "")
    if cleaned.startswith("VATDL") or "VATDL" in cleaned:
        return False
    digits = [c for c in ref if c.isdigit()]
    if not digits or all(c == "0" for c in digits):
        return False
    return True


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


# BPR14: telephone number finder
class PhoneNumberFromNoSubRefBlock:
    """
    Finds the invoice telephone number:
      - By default (allow_sub_ref=False), must be inside BSTARTSLTNOSUBSCRIPTIONREF block
      - If allow_sub_ref=True, accepts 10-digit labels from any block (including subscription ref groups)
      - Must be a 10-digit SLTPRODUCTLABEL
      - Must have at least one real charge line confirmed
    """

    def __init__(self, allow_sub_ref=False):
        self.allow_sub_ref = allow_sub_ref
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
        if (self._in_block or self.allow_sub_ref) and label.isdigit() and len(label) == 10:
            self._pending = label
        else:
            self._pending = None

    def confirm_charge(self):
        if not self.result and self._pending:
            self.result = self._pending