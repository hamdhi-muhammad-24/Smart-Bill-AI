"""USD Open Item Parser (BILLSTYLE=21) - co-branded international operator invoice.

Rebuilt from a crude whole-content-regex implementation (which hardcoded a
"REMOVE_LABELS" exclusion set and a bandwidth-only description regex matching
only one of the three real charge lines) into proper line-by-line pipe
tokenization, matching the pattern already proven in vat_enterprise/vat_home.

Ground truth: `usd_open_item.xlsx` is not present in this repo - CLAUDE.md's
condensed section 2 mapping is the working spec, cross-verified against the
real GMF (`data/inbound/521662_4-21-02-1-USD-103-00-BILL-NONRED_1.1`) via
sub-agent investigation. Six code paths (SLTPRODLABELUSAGEDET,
SLTPRODLABELDISCDET, all 6 discount tag families, ADJ, and the alternate-
currency tag set) have zero real-data coverage in this GMF - see
BUILD_NOTE.md for what's fixture-tested vs still unproven.
"""
import os
import re

from core.bill_common import (
    to_float, strip_before_underscore, MARKETING_MESSAGE_TAGS,
    TopLevelDiscountCollector,
)

_ITEM_TAG_RE = re.compile(
    r'^(BSTARTITEM|BENDITEM|EVSOURCE|EVENTSTEXT|EVENTHEADING'
    r'|EVENT|TSTARTEVENT|TENDEVENT|SLTITEMGRANDTOTAL)_(\d+)$'
)
_ITEMGROUP_RE     = re.compile(r'^ITEMGROUPNAME_1_(\d+)$')
_GROUPSUBTOTAL_RE = re.compile(r'^ITEMGROUPSUBTOTAL_(\d+)_(\d+)$')

ADDRESS_FIELDS = [
    'ADDRESSNAME', 'POSITION', 'DEPARTMENT', 'BUSINESSNAME',
    'ADDRESS1', 'ADDRESS2', 'ADDRESS3', 'ADDRESS4', 'ADDRESS5',
    'ZIPCODE', 'COUNTRY',
]


def _parse_filename_segments(file_path):
    """Rednotice condition (section 2's "Rednotice") is sourced from the GMF
    FILENAME itself, not a content tag. Confirmed filename convention via the
    real file `521662_4-21-02-1-USD-103-00-BILL-NONRED_1.1`: dash-split the
    middle underscore-segment and the value immediately before the literal
    "BILL" token is the LatestCreditControlActionId (confirmed "00" sits in
    that exact position in this non-red-notice sample; no other template in
    this codebase parses this convention, so there's no prior implementation
    to cross-check against - flagged in BUILD_NOTE.md as a best-effort
    mapping, not a certainty)."""
    stem = os.path.basename(file_path).removesuffix(".processing")
    parts = stem.split('-')
    action_id = ''
    for i, p in enumerate(parts):
        if p.upper() == 'BILL' and i > 0:
            action_id = parts[i - 1]
            break
    return action_id


def _format_date_range_suffix(start, end, data):
    """Same conditional date-range rule as vat_enterprise/vat_home: only show
    a sub-range when it genuinely differs from the bill period."""
    if start and end and (
        start != data['billing_period_start'] or
        end   != data['billing_period_end']
    ):
        return f" ({start}-{end})"
    return ""


def _quantity_bracket(count, unit):
    """Bracketed-quantity-annotation, reused verbatim from vat_home's
    zero/null-suppression fix (FIX_DESC_CURRENCY_ZERO.md #0.5): a count of
    "0" with no unit text means "no real quantity to show" - the bracket
    must be omitted, not printed as a bare "[0]"."""
    has_qty = count not in ('', '0') or unit not in ('', None)
    if not has_qty:
        return ""
    cu = f"{count} {unit}".strip() if unit else count
    return f" [{cu}]" if cu else ""


def _decode_flag(flag):
    """P/O/I/S flag -> bracket label. Same decode already used in
    vat_enterprise/vat_home for this exact flag convention - no new decode
    table needed (none exists anywhere in the codebase for the *other*
    varying numeric field in this tag; see BUILD_NOTE.md for why field
    interpretation landed here)."""
    if flag in ('P', 'S'):
        return " [Rental]"
    if flag == 'O':
        return " [One Time]"
    if flag == 'I':
        return " [Initiation]"
    return ""


def parse_usd_open_item(file_path: str) -> dict:
    data = {
        "account_number":        "",
        "invoice_number":        "",
        "billing_date":          "",
        "billing_period_start":  "",
        "billing_period_end":    "",
        "bill_period":           "",
        "payment_due_date":      "",
        "customer_segment":      "",
        "file_info_string":      "",
        "invoice_amount":        "",
        "total_charges":         0.0,

        "address_lines":         {},  # field name -> value, conditional print

        # Charges: ordered list of blocks, each either a subscription-ref
        # group (with nested product-label sub-blocks) or a standalone
        # product-label block (no subscription ref wraps it - confirmed both
        # shapes exist in the real GMF: SB010018888 wraps two product labels,
        # while G100323 has none). "unlabeled_charges" holds charge lines
        # with no SLTPRODUCTLABEL scope at all - rendered as their own final
        # block after every labeled block, per section 2's explicit ordering
        # rule, never left to incidental GMF order.
        "charge_blocks":         [],
        "unlabeled_charges":     [],

        "adjustments":           [],
        "top_level_discounts":   [],
        "marketing_messages":    [],

        # Currency: ACCCURRENCYCODE drives the "Amount <code>" column header
        # (confirmed via real GMF: value "US$"). ACCCURRCODE is a distinctly-
        # named tag in the alternate-currency conditional per CLAUDE.md's
        # spec text - kept separate rather than assumed to be the same tag;
        # flagged in BUILD_NOTE.md since this GMF has no ACCCURRCODE tag at
        # all to cross-check the assumption against.
        "acc_currency_code":     "",
        "acc_curr_code":         "",
        "info_curr_code":        "",
        "acc_rate":              "",
        "info_inv_total_rounded": 0.0,

        "rednotice_action_id":   _parse_filename_segments(file_path),

        "usage_sections":        [],

        "source_filename":       os.path.basename(file_path).removesuffix(".processing"),
    }

    top_discounts = TopLevelDiscountCollector()

    current_block          = None  # the charge_blocks[-1] dict currently open
    current_subref_block    = None  # subscription-ref wrapper, if any is open
    current_product         = None  # the {"label":..,"charges":[]} dict
    in_subref               = False

    usage_families         = {}
    current_family_id      = None
    current_ref            = None
    current_subsection     = None
    pending_subsection_label = None
    last_closed_subsection  = None

    def start_product_block(label):
        nonlocal current_product, current_block
        block = {"label": label, "charges": []}
        current_product = block
        if in_subref and current_subref_block is not None:
            current_subref_block["product_labels"].append(block)
        else:
            data["charge_blocks"].append({"kind": "product_label", **block})
            current_block = data["charge_blocks"][-1]
            current_product = current_block

    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith('DOCEND'):
                break

            if line.startswith('BSTARTSLTSUBSCRIPTIONREF'):
                in_subref = True
                current_subref_block = None  # set on SLTSUBSCRIPTIONREF itself
                continue
            if line.startswith('BENDSLTSUBSCRIPTIONREF'):
                in_subref = False
                current_subref_block = None
                continue
            if (line.startswith('TSTARTSLTPRODUCTLABEL')
                    or line.startswith('BSTARTSLTPRODUCTLABEL')):
                continue
            if (line.startswith('TENDSLTPRODUCTLABEL')
                    or line.startswith('BENDSLTPRODUCTLABEL')):
                current_product = None
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

            # ── itemized usage tables (EVENTHEADING_xx pattern, reused
            # verbatim from vat_home - same tag family, same generic shape) ──
            m = _ITEM_TAG_RE.match(key)
            if m:
                tag, family_id = m.group(1), m.group(2)
                if tag == 'BSTARTITEM':
                    current_ref = {"phone": "", "subsections": []}
                    fam = usage_families.setdefault(
                        family_id, {"label": "", "refs": [], "grand_total": 0}
                    )
                    fam["refs"].append(current_ref)
                    current_family_id = family_id
                elif tag == 'BENDITEM':
                    current_ref = None
                    current_family_id = None
                elif tag == 'EVSOURCE':
                    if current_ref is not None:
                        current_ref["phone"] = value
                elif tag == 'EVENTSTEXT':
                    if current_family_id in usage_families:
                        # BPR21: strip everything before the first '_' in
                        # event names, same generic rule used for tariff,
                        # product, discount, and adjustment-type names -
                        # not just a literal "P_" prefix.
                        label = strip_before_underscore(value)
                        usage_families[current_family_id]["label"] = label
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
                    if current_family_id in usage_families and len(gparts) >= 2:
                        usage_families[current_family_id]['grand_total'] = \
                            to_float(gparts[1])
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

            # ── BPR23 top-level discounts (shared collector - reused as-is) ─
            if top_discounts.handle(key, value):
                continue

            # ── marketing messages ───────────────────────────────────
            if key in MARKETING_MESSAGE_TAGS:
                if value:
                    data['marketing_messages'].append(value)
                continue

            # ── header / standard fields ─────────────────────────────
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
            elif key == 'ACC_CUSTOMER_SEGMENT':
                data['customer_segment'] = value
            elif key == 'INVTOTALROUNDED':
                data['invoice_amount'] = value
                data['total_charges'] = to_float(value)
            elif key == 'ACCCURRENCYCODE':
                data['acc_currency_code'] = value
            elif key == 'ACCCURRCODE':
                data['acc_curr_code'] = value
            elif key == 'INFOCURRCODE':
                data['info_curr_code'] = value
            elif key == 'ACCRATE':
                data['acc_rate'] = value
            elif key == 'INFOINVTOTALROUNDED':
                data['info_inv_total_rounded'] = to_float(value)

            elif key in ADDRESS_FIELDS:
                if value:
                    data['address_lines'][key] = value

            elif key == 'SLTSUBSCRIPTIONREF':
                current_subref_block = {
                    "kind": "subscription_ref",
                    "ref": value,
                    "product_labels": [],
                }
                data["charge_blocks"].append(current_subref_block)

            elif key == 'SLTPRODUCTLABEL':
                # BPR21: strip everything before the first '_' in product
                # names - same rule already applied to tariff/discount/
                # adjustment-type names.
                start_product_block(strip_before_underscore(value))

            elif key == 'SLTPRODLABELDET':
                raw       = rest.split('|')
                all_parts = [value] + raw
                # Confirmed pipe-index mapping (0-based), verified against
                # all 3 real occurrences in the GMF - see BUILD_NOTE.md:
                #   0=amount 1=prefix(tariff name) 2=suffix(product name)
                #   3=const/unused 4=sequence id (not decoded - no lookup
                #   table exists anywhere in this codebase for it)
                #   5=flag(P/O/I/S) 6=start 7=end 8=source-system marker
                #   (unused) 9=count 10=unit (absent in all 3 real samples -
                #   no bracket shown).
                # BPR21: strip everything before the first '_' in BOTH the
                # tariff name AND the product name independently (confirmed
                # against the real GMF: "G_Capacity Bearer" + "In Advance
                # Monthly Charge BW_ 10Gbps" must render as just "Capacity
                # Bearer 10Gbps", not the raw "...Charge BW_ 10Gbps" tail -
                # the earlier assumption that field 2 must stay raw because
                # it "legitimately contains _" was wrong).
                if current_product is not None and len(all_parts) > 7:
                    prefix = strip_before_underscore(all_parts[1])
                    suffix = strip_before_underscore(all_parts[2])
                    desc   = f"{prefix} {suffix}".strip()
                    flag   = all_parts[5].strip().upper()
                    start  = all_parts[6].strip()
                    end    = all_parts[7].strip()
                    count  = all_parts[9].strip() if len(all_parts) > 9 else ''
                    unit   = all_parts[10].strip() if len(all_parts) > 10 else ''
                    desc += _decode_flag(flag)
                    desc += _quantity_bracket(count, unit)
                    desc += _format_date_range_suffix(start, end, data)
                    amt = to_float(all_parts[0])
                    current_product['charges'].append(
                        {'description': desc, 'amount': amt})
                else:
                    # No open SLTPRODUCTLABEL scope at all - a genuinely
                    # unlabeled charge line. Collected separately so it can
                    # be rendered as its own final block, after every
                    # labeled block, per section 2's explicit ordering rule.
                    if len(all_parts) > 7:
                        prefix = strip_before_underscore(all_parts[1])
                        suffix = strip_before_underscore(all_parts[2])
                        desc   = f"{prefix} {suffix}".strip()
                        flag   = all_parts[5].strip().upper()
                        start  = all_parts[6].strip()
                        end    = all_parts[7].strip()
                        count  = all_parts[9].strip() if len(all_parts) > 9 else ''
                        unit   = all_parts[10].strip() if len(all_parts) > 10 else ''
                        desc += _decode_flag(flag)
                        desc += _quantity_bracket(count, unit)
                        desc += _format_date_range_suffix(start, end, data)
                        amt = to_float(all_parts[0])
                        data['unlabeled_charges'].append(
                            {'description': desc, 'amount': amt})

            elif key == 'SLTPRODLABELUSAGEDET':
                raw       = [p.strip() for p in rest.split('|') if p.strip()]
                all_parts = [value] + raw
                if current_product is not None and len(all_parts) >= 2:
                    amt = to_float(all_parts[1])
                    if amt == 0:
                        continue
                    desc = strip_before_underscore(all_parts[0])
                    current_product['charges'].append(
                        {'description': desc, 'amount': amt})

            elif key == 'SLTPRODLABELDISCDET':
                raw       = [p.strip() for p in rest.split('|') if p.strip()]
                all_parts = [value] + raw
                if current_product is not None and len(all_parts) >= 2:
                    amt = to_float(all_parts[1])
                    if amt:
                        current_product['charges'].append({
                            'description': strip_before_underscore(all_parts[0]),
                            'amount': -amt,
                        })

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

    # ── post-parse ──────────────────────────────────────────────────
    if data['billing_period_start'] and data['billing_period_end']:
        data['bill_period'] = (
            f"{data['billing_period_start']} - {data['billing_period_end']}"
        )
    data['file_info_string'] = data['source_filename']
    data['top_level_discounts'] = top_discounts.discounts

    # Drop empty product-label blocks (no charges) and empty subscription-ref
    # groups (no product labels left after that filter).
    cleaned_blocks = []
    for block in data['charge_blocks']:
        if block['kind'] == 'subscription_ref':
            block['product_labels'] = [
                p for p in block['product_labels'] if p['charges']
            ]
            if block['product_labels']:
                cleaned_blocks.append(block)
        else:
            if block['charges']:
                cleaned_blocks.append(block)
    data['charge_blocks'] = cleaned_blocks

    for fam in usage_families.values():
        for ref in fam["refs"]:
            ref["subsections"] = [
                s for s in ref["subsections"]
                if s.get('rows') or s.get('subtotal')
            ]
    data['usage_sections'] = [
        {"label": fam["label"], "refs": [r for r in fam["refs"] if r["subsections"]],
         "grand_total": fam["grand_total"]}
        for fam in usage_families.values()
        if any(r["subsections"] for r in fam["refs"])
    ]

    return data
