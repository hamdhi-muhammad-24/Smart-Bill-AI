"""VAT Home Parser.

Parses a HOME-customer, VAT-registered GMF into a `data` dict for renderer.py.

Differs from the vat_enterprise/nonvat_home parsers in one deliberate way (see
CLAUDE.md's discovery-pass note and BUILD_NOTE.md): usage sections are scoped by
(family, ref) instead of by bare family suffix. The enterprise/nonvat_home pattern
resets `usage_sections[item_id]` on every `BSTARTITEM_xx`, which silently drops all
but the last <ref> when a family (e.g. EVENT_46 "Extra GB") appears more than once
for the same account - confirmed via the real GMF fragment quoted in vat_enterprise's
own CLAUDE.md (repeated `BSTARTITEM_11` blocks, one per phone ref, under one family).

`usage_entries`/`data['usage_sections']` is a FLAT list, one entry per ref, in
GMF-native encounter order across ALL families - not grouped by usage type. An
earlier version grouped refs into a dict keyed by family id (one usage type's
refs all under one key), which silently reordered the rendered output: since
dict iteration groups all of one type's refs together, 65 golden interleaved
type-runs (Additional Channels, Extra GB, Additional Channels x8, P_Domestic
Voice Usage, ...) collapsed into 7 type-blocks (all Domestic Voice, then all
Additional Channels, then all Extra GB, ...) even though refs within each type
were individually in the right order. Grouping by type must never be
reintroduced here - each BSTARTITEM_xx block becomes its own flat entry,
whichever family id it belongs to, so the render order matches encounter order.
"""
import os
import re

from core.bill_common import (
    to_float, strip_before_underscore, apply_label_override,
    reorder_addresses, TopLevelDiscountCollector, parse_cancel_payment,
    PhoneNumberFromNoSubRefBlock, MARKETING_MESSAGE_TAGS,
    ADDRESS_PRINT_ORDER, is_vat_reg_printable, is_tax_section_printable,
)

_ITEM_TAG_RE = re.compile(
    r'^(BSTARTITEM|BENDITEM|EVSOURCE|EVENTSTEXT|EVENTHEADING'
    r'|EVENT|TSTARTEVENT|TENDEVENT|SLTITEMGRANDTOTAL)_(\d+)$'
)
_ITEMGROUP_RE     = re.compile(r'^ITEMGROUPNAME_1_(\d+)$')
_GROUPSUBTOTAL_RE = re.compile(r'^ITEMGROUPSUBTOTAL_(\d+)_(\d+)$')


def parse_vat_home(file_path: str) -> dict:
    data = {
        "telephone_number":      "",
        "account_number":        "",
        "invoice_number":        "",
        "billing_date":          "",
        "billing_period_start":  "",
        "billing_period_end":    "",
        "payment_due_date":      "",
        "customer_name":         "",
        "position":              "",
        "department":            "",
        "business_name":         "",
        "address_lines":         [],
        "zip_code":              "",
        "badge":                 "HOME",
        "customer_type":         "",
        "balance_bf":            0,
        "payments_received":     0,
        "charges_period":        0,
        "total_payable":         0,
        "product_labels":        [],
        "adjustments":           [],
        "taxes":                 [],
        "taxes_total":           0,
        "tax_status":            "",
        "total_charges":         0,
        "payments":              [],
        "cancelled_payments":    [],
        "total_payments":        0,
        "top_level_discounts":   [],
        "marketing_messages":    [],
        "suspended_message":     "",
        "source_filename":       os.path.basename(file_path).removesuffix(".processing"),
        "customer_segment":      "",
        "slt_vat_reg":           "",
        "customer_vat_reg":      "",
        "show_vat_lines":        True,
        "address_name_not_required": False,
        "usage_sections":        [],
        # Customer-facing display currency, e.g. "Rs" - from ACCCURRENCYCODE.
        # NOT the same as SLTACCCURRENCYCODE (SLT's internal accounting
        # currency code, e.g. "LKR") - confirmed distinct tags/values in the
        # real GMF, must not be confused.
        "currency_code":         "",
    }

    raw_address   = {}
    top_discounts = TopLevelDiscountCollector()
    phone_finder  = PhoneNumberFromNoSubRefBlock()

    # Flat list, in GMF-native encounter order (NOT grouped by family/type -
    # see module docstring update): [{"label": str, "grand_total": 0,
    # "ref": {"phone": str, "subsections": [...]}}, ...]. One entry per
    # BSTARTITEM_xx block, in the order it's opened, regardless of which
    # family id (usage type) it belongs to - this is what lets refs of
    # different usage types interleave in the rendered output exactly as
    # they interleave in the source GMF.
    usage_entries         = []
    current_entry         = None
    current_ref           = None
    current_subsection    = None
    pending_subsection_label = None
    last_closed_subsection = None
    in_promo_group         = False
    current_promo_product  = None
    current_product        = None
    in_subscription_ref         = False
    current_subscription_group  = None

    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith('DOCEND'):
                break

            if line.startswith('BSTARTSLTNOSUBSCRIPTIONREF'):
                phone_finder.enter_block()
                continue
            if (line.startswith('BENDSLTSUBSCRIPTIONREF') or
                    line.startswith('BSTARTSLTSUBSCRIPTIONREF')):
                phone_finder.exit_block()
                continue
            if line.startswith('TSTARTSLTSUBSCRIPTIONREF'):
                in_subscription_ref = True
                continue
            if line.startswith('TENDSLTSUBSCRIPTIONREF'):
                in_subscription_ref        = False
                current_subscription_group = None
                continue

            if (line.startswith('BSTARTGROUPPROMO') or
                    line.startswith('TSTARTGROUPPROMO')):
                in_promo_group = True
                continue
            if (line.startswith('TENDGROUPPROMO') or
                    line.startswith('BENDGROUPPROMO')):
                in_promo_group        = False
                current_promo_product = None
                continue
            if (line.startswith('TSTARTSLTPROMOSUBLABEL') or
                    line.startswith('TENDSLTPROMOSUBLABEL')):
                continue

            if '|' not in line:
                continue

            parts   = line.split('|', 1)
            key_val = parts[0].strip()
            rest    = parts[1] if len(parts) > 1 else ''
            tokens  = key_val.split(None, 1)
            if not tokens:
                continue
            key   = tokens[0].upper()
            value = tokens[1].strip() if len(tokens) > 1 else ''

            # ── usage block (family/ref grouped - see module docstring) ────
            m = _ITEM_TAG_RE.match(key)
            if m:
                tag, family_id = m.group(1), m.group(2)
                if tag == 'BSTARTITEM':
                    current_ref = {"phone": "", "subsections": []}
                    current_entry = {"label": "", "grand_total": 0, "ref": current_ref}
                    usage_entries.append(current_entry)
                elif tag == 'BENDITEM':
                    current_entry = None
                    current_ref = None
                elif tag == 'EVSOURCE':
                    if current_ref is not None:
                        current_ref["phone"] = value
                elif tag == 'EVENTSTEXT':
                    if current_entry is not None:
                        # Preserve verbatim - "P_" is literal source data (e.g.
                        # "P_Domestic Voice Usage"), not a formatting artifact.
                        current_entry["label"] = value
                elif tag == 'EVENTHEADING':
                    cols = [value] + [p.strip() for p in rest.split('|')
                                      if p.strip()]
                    current_subsection = {
                        'label':    pending_subsection_label or '',
                        'headers':  cols,
                        'rows':     [],
                        'subtotal': 0,
                    }
                    pending_subsection_label = None
                elif tag == 'EVENT':
                    if current_subsection is not None:
                        row = [value] + [p.strip() for p in rest.split('|')]
                        # Raw GMF rows end with a trailing pipe (e.g.
                        # "...|ANIMAL PLANET|50.000|"), producing a trailing
                        # empty string EVENTHEADING's own parsing filters out
                        # but this didn't - leaving row one element longer
                        # than headers. renderer.py derives each column's x
                        # position from len(row), so the mismatch shifted the
                        # Charge value into its own extra left-aligned cell
                        # right next to Description, on top of the real
                        # right-aligned Charge cell - not a string
                        # concatenation, a column-count drift. Only strip
                        # TRAILING empties (never interior ones, which could
                        # be genuine blank fields in some other table).
                        while row and row[-1] == '':
                            row.pop()
                        current_subsection['rows'].append(row)
                elif tag == 'TENDEVENT':
                    if current_subsection is not None and current_ref is not None:
                        current_ref["subsections"].append(current_subsection)
                        last_closed_subsection = current_subsection
                    current_subsection = None
                elif tag == 'SLTITEMGRANDTOTAL':
                    gparts = [value] + [p.strip() for p in rest.split('|')
                                        if p.strip()]
                    if current_entry is not None and len(gparts) >= 2:
                        current_entry['grand_total'] = to_float(gparts[1])
                continue

            gm = _ITEMGROUP_RE.match(key)
            if gm:
                pending_subsection_label = value
                continue

            sm = _GROUPSUBTOTAL_RE.match(key)
            if sm:
                if last_closed_subsection is not None:
                    sub_parts = [value] + [p.strip() for p in rest.split('|')
                                           if p.strip()]
                    if len(sub_parts) >= 2:
                        last_closed_subsection['subtotal'] = \
                            to_float(sub_parts[-1])
                    last_closed_subsection = None
                continue

            # ── promo group ─────────────────────────────────────────
            if in_promo_group:
                if key == 'SLTPRODGROUPLABEL':
                    all_parts = [value] + [p.strip() for p in rest.split('|')]
                    name = (strip_before_underscore(all_parts[1])
                            if len(all_parts) > 1 else value)
                    name = apply_label_override(name)
                    current_promo_product = {"label": name, "charges": []}
                    data['product_labels'].append(current_promo_product)
                    phone_finder.candidate(name)
                elif key == 'SLTPRODLABELDET' and current_promo_product:
                    all_parts = [value] + rest.split('|')
                    if len(all_parts) > 6:
                        prefix = all_parts[1].split('_')[-1].strip()
                        suffix = all_parts[2].split('_')[-1].strip()
                        desc   = f"{prefix} {suffix}".strip()
                        flag   = (all_parts[5].strip().upper()
                                  if len(all_parts) > 5 else '')
                        if flag == 'P':
                            desc += " [Rental]"
                        elif flag == 'O':
                            desc += " [One Time]"
                        elif flag == 'I':
                            desc += " [Initiation]"
                        amt = to_float(all_parts[0])
                        current_promo_product['charges'].append(
                            {'description': desc, 'amount': amt})
                        if amt:
                            phone_finder.confirm_charge()
                elif key == 'SLTPRODLABELDISCDET' and current_promo_product:
                    all_parts = [value] + [p.strip() for p in rest.split('|')
                                           if p.strip()]
                    if len(all_parts) >= 2:
                        amt = to_float(all_parts[1])
                        if amt:
                            current_promo_product['charges'].append({
                                'description': strip_before_underscore(all_parts[0]),
                                'amount': -amt,
                            })
                            phone_finder.confirm_charge()
                continue

            # ── BPR23 top-level discounts ───────────────────────────
            if top_discounts.handle(key, value):
                continue

            # ── BPR28 marketing messages ────────────────────────────
            if key in MARKETING_MESSAGE_TAGS:
                if value:
                    data['marketing_messages'].append(value)
                continue
            if key == 'SLT_ALLPRODSUSPENDED':
                data['suspended_message'] = value.split('|')[0].strip()
                continue

            if len(tokens) < 2:
                continue

            # ── standard fields ─────────────────────────────────────
            if key == 'ACCOUNTNO':
                data['account_number'] = value
            elif key == 'BILLREF':
                data['invoice_number'] = value
            elif key == 'INVOICEACTUALDATE':
                data['billing_date'] = value
            elif key == 'INVOICESTART':
                data['billing_period_start'] = value
            elif key == 'INVOICEEND':
                data['billing_period_end'] = value
            elif key == 'PAYMENTDUEDATE':
                data['payment_due_date'] = value
            elif key == 'CUSTOMERTYPE':
                data['customer_type'] = value
            elif key == 'ACCTAXSTATUS':
                data['tax_status'] = value
            elif key == 'ACC_ADDRESS_NAME_N_REQIURED':
                data['address_name_not_required'] = value.strip().upper() == 'Y'

            elif key == 'ADDRESSNAME':
                data['customer_name'] = value
            elif key == 'POSITION':
                data['position'] = value
            elif key == 'DEPARTMENT':
                data['department'] = value
            elif key == 'BUSINESSNAME':
                data['business_name'] = value
            elif key in ADDRESS_PRINT_ORDER:
                if value:
                    raw_address[key] = value
            elif key == 'ZIPCODE':
                data['zip_code'] = value

            elif key == 'BALFWD':
                data['balance_bf'] = to_float(value)
            elif key == 'ACCBALPAYTOT':
                data['payments_received'] = to_float(value)
                data['total_payments']    = to_float(value)
            elif key == 'CHARGES':
                data['charges_period'] = to_float(value)
                data['total_charges']  = to_float(value)
            elif key == 'NEWBAL':
                data['total_payable'] = to_float(value)
            elif key == 'ACCCURRENCYCODE':
                data['currency_code'] = value

            elif key == 'SLTPRODUCTLABEL':
                label = apply_label_override(value)
                current_product = {"label": label, "charges": []}
                # Nested under a SB subscription-ref group (BSTARTSLTPRODUCTLABEL
                # block inside TSTARTSLTSUBSCRIPTIONREF/TENDSLTSUBSCRIPTIONREF):
                # attach as a child so the subscription header only prints when
                # the group (itself or a child) actually has content - see the
                # empty-group filter below.
                if in_subscription_ref and current_subscription_group is not None:
                    current_subscription_group['children'].append(current_product)
                else:
                    data['product_labels'].append(current_product)
                phone_finder.candidate(value)

            # SB-prefixed charge-group refs (e.g. SB000030381) live under this
            # tag family, not SLTPRODUCTLABEL - confirmed via the real GMF:
            # `SLTSUBSCRIPTIONREF SB000030381|` + `SLTSUBSDETAIL 0.00|Data
            # Service Bearer|Subcription|P|01/09/2025|30/09/2025|`, structured
            # as its own group header + one charge-detail line, the same shape
            # as SLTPRODUCTLABEL/SLTPRODLABELDET. Previously entirely unread,
            # silently dropping these refs. Parsed identically to a numeric
            # ref's group so it renders with the same formatting, in natural
            # GMF encounter order (no separate collection/re-insertion step).
            elif key == 'SLTSUBSCRIPTIONREF':
                label = apply_label_override(value)
                current_product = {"label": label, "charges": [], "children": []}
                current_subscription_group = current_product
                data['product_labels'].append(current_product)
                phone_finder.candidate(value)

            elif key == 'SLTSUBSDETAIL':
                raw       = rest.split('|')
                all_parts = [value] + raw
                # BPR18: SLTSUBSDETAIL must be ignored entirely (no line
                # printed at all) when its amount - the value before the
                # first '|' - is zero. Not just a blank amount column.
                amt = to_float(all_parts[0]) if all_parts else 0
                if current_product and len(all_parts) > 5 and amt:
                    prefix = all_parts[1].split('_')[-1].strip()
                    suffix = all_parts[2].split('_')[-1].strip()
                    desc   = f"{prefix} {suffix}".strip()
                    flag   = all_parts[3].strip().upper()
                    start  = all_parts[4].strip()
                    end    = all_parts[5].strip() if len(all_parts) > 5 else ''
                    if flag in ('P', 'S'):
                        desc += " [Rental]"
                        if start and end and (
                            start != data['billing_period_start'] or
                            end   != data['billing_period_end']
                        ):
                            desc += f" ({start}-{end})"
                    elif flag == 'O':
                        desc += " [One Time]"
                    elif flag == 'I':
                        desc += " [Initiation]"
                    current_product['charges'].append(
                        {'description': desc, 'amount': amt})
                    phone_finder.confirm_charge()

            elif key == 'SLTPRODLABELDET':
                raw       = rest.split('|')
                all_parts = [value] + raw
                if current_product and len(all_parts) > 7:
                    prefix = all_parts[1].split('_')[-1].strip()
                    suffix = all_parts[2].split('_')[-1].strip()
                    desc   = f"{prefix} {suffix}".strip()
                    flag   = all_parts[5].strip().upper()
                    start  = all_parts[6].strip()
                    end    = all_parts[7].strip()
                    count  = all_parts[9].strip() if len(all_parts) > 9 else ''
                    unit   = all_parts[10].strip() if len(all_parts) > 10 else ''
                    # A quantity of "0" with no unit text means "no real
                    # quantity to show" (confirmed against raw GMF: e.g.
                    # `SLTPRODLABELDET  0.00|D-ITL_Service CPE|Router|...|P|
                    # ...|SAPROD|0|` has count="0", unit missing/empty) - the
                    # bracket must be omitted entirely in that case, not
                    # printed as a bare "[0]". `count` is a truthy non-empty
                    # STRING even when its value is "0", so the previous
                    # `if cu:`/`if count:` checks never caught this.
                    has_qty = count not in ('', '0') or unit not in ('', None)
                    if flag in ('P', 'S'):
                        desc += " [Rental]"
                        if has_qty:
                            cu = f"{count} {unit}".strip() if unit else count
                            desc += f" [{cu}]"
                        if start and end and (
                            start != data['billing_period_start'] or
                            end   != data['billing_period_end']
                        ):
                            desc += f" ({start}-{end})"
                    elif flag == 'O':
                        desc += " [One Time]"
                        if has_qty:
                            desc += f" [{count}]"
                        if start:
                            desc += f" ({start})"
                    elif flag == 'I':
                        desc += " [Initiation]"
                        if has_qty:
                            cu = f"{count} {unit}".strip() if unit else count
                            desc += f" [{cu}]"
                        if start:
                            desc += f" ({start}-{end})"
                    amt = to_float(all_parts[0])
                    current_product['charges'].append(
                        {'description': desc, 'amount': amt})
                    if amt:
                        phone_finder.confirm_charge()

            elif key == 'SLTPRODLABELUSAGEDET':
                raw       = [p.strip() for p in rest.split('|') if p.strip()]
                all_parts = [value] + raw
                if current_product and len(all_parts) >= 2:
                    amt = to_float(all_parts[1])
                    if amt == 0:
                        continue
                    desc = strip_before_underscore(all_parts[0])
                    current_product['charges'].append(
                        {'description': desc, 'amount': amt})
                    phone_finder.confirm_charge()

            elif key == 'SLTPRODLABELDISCDET':
                raw       = [p.strip() for p in rest.split('|') if p.strip()]
                all_parts = [value] + raw
                if current_product and len(all_parts) >= 2:
                    amt = to_float(all_parts[1])
                    if amt:
                        current_product['charges'].append({
                            'description': strip_before_underscore(all_parts[0]),
                            'amount': -amt,
                        })
                        phone_finder.confirm_charge()

            elif key == 'SLTTAXCODE':
                raw       = [p.strip() for p in rest.split('|') if p.strip()]
                all_parts = [value] + raw
                if len(all_parts) >= 4:
                    amt = to_float(all_parts[3])
                    data['taxes'].append({'name': all_parts[0], 'amount': amt})
                    data['taxes_total'] += amt

            elif key == 'ADJ':
                raw       = rest.split('|')
                all_parts = [value] + raw
                if len(all_parts) > 15:
                    short_desc = strip_before_underscore(all_parts[2].strip())
                    reason = all_parts[15].strip()[:52]
                    desc   = f"{short_desc} - {reason}" if reason else short_desc
                    data['adjustments'].append({
                        'description': desc,
                        'amount':      to_float(all_parts[3]),
                    })

            elif key == 'ACCBALPAYDET':
                raw_parts = [value] + rest.split('|')
                amount    = to_float(raw_parts[3]) if len(raw_parts) > 3 else 0
                pay_type  = (raw_parts[13].strip()
                             if len(raw_parts) > 13 and raw_parts[13].strip()
                             else 'Payment')
                data['payments'].append({
                    'date': value, 'pay_type': pay_type,
                    'location': '', 'amount': amount,
                })
            elif key == 'ACCBALFPAYDET':
                data['cancelled_payments'].append(
                    parse_cancel_payment(value, rest.split('|')))
            elif key == 'SLT_PAYMENT_LOCATION':
                if data['payments']:
                    data['payments'][-1]['location'] = value

            elif key == 'ACC_CUSTOMER_SEGMENT':
                data['customer_segment'] = value
            elif key == 'INVOICINGCOVATREG':
                data['slt_vat_reg'] = value
            elif key == 'CUSTOMERVATREF':
                data['customer_vat_reg'] = value

    # ── post-parse ──────────────────────────────────────────────────
    data['address_lines']       = reorder_addresses(raw_address)
    data['show_vat_lines']      = is_vat_reg_printable(data['customer_vat_reg'])
    data['telephone_number']    = phone_finder.result
    data['top_level_discounts'] = top_discounts.discounts

    for p in data['product_labels']:
        if 'children' in p:
            p['children'] = [c for c in p['children'] if c['charges']]
    data['product_labels'] = [
        p for p in data['product_labels']
        if p['charges'] or p.get('children')
    ]

    from core.customer_type_mapper import get_badge
    data['badge'] = get_badge(data['customer_type']) or "HOME"

    # Drop refs with no real event rows anywhere, then families with no refs
    # - same filter cascade as enterprise/nonvat_home, just applied one level
    # deeper (per ref).
    #
    # This must be a REF-level decision, not a per-subsection one: some GMF
    # families (confirmed on the real domestic-voice-usage family) emit an
    # EVENTHEADING/TENDEVENT pair with a nonzero ITEMGROUPSUBTOTAL for every
    # ref that merely has a product/rental line - even refs with zero actual
    # EVENT rows anywhere - as bookkeeping noise (1,468 of 1,489 refs on the
    # real GMF). Those must be dropped entirely. But a *genuine* ref can
    # legitimately have some subsections with real rows (e.g. "Others") and
    # others with none (e.g. "Off Net"/"On Net" showing only a label + a real
    # nonzero total, no itemized calls) - confirmed against golden, e.g. ref
    # 0252280222's Off Net/On Net total 425.500+807.000 print with no rows
    # between their label and "Total for X" line. So: keep ALL of a ref's
    # subsections (rows or not) as long as ANY of them has real rows;
    # otherwise the whole ref is bookkeeping noise and gets dropped.
    # Flat and GMF-ordered (see usage_entries comment above) - a section per
    # ref, in encounter order, NOT grouped/sorted by usage type. Confirmed
    # bug: grouping by type here (the old dict-of-lists shape) collapsed 65
    # golden interleaved type-runs down to 7 type-blocks in the rendered
    # output, since dict iteration groups all of one family's refs together
    # even though this loop itself preserves per-family ref order correctly.
    ordered_sections = []
    for entry in usage_entries:
        ref = entry["ref"]
        if not any(s.get('rows') for s in ref["subsections"]):
            continue
        ordered_sections.append({
            "label":       entry["label"],
            "ref":         ref,
            "grand_total": entry["grand_total"],
        })
    data['usage_sections'] = ordered_sections

    return data
