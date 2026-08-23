"""Invoice of Summary parser (Sheet 18, BILLSTYLE=18)."""
import os
import re

from core.bill_common import (
    to_float, strip_before_underscore, apply_label_override,
    reorder_addresses, TopLevelDiscountCollector, parse_cancel_payment,
    MARKETING_MESSAGE_TAGS, ADDRESS_PRINT_ORDER,
    is_vat_reg_printable,
)

_ITEM_TAG_RE = re.compile(
    r'^(BSTARTITEM|BENDITEM|EVSOURCE|EVENTSTEXT|EVENTHEADING'
    r'|EVENT|TSTARTEVENT|TENDEVENT|SLTITEMGRANDTOTAL)_(\d+)$'
)
_ITEMGROUP_RE     = re.compile(r'^ITEMGROUPNAME_1_(\d+)$')
_GROUPSUBTOTAL_RE = re.compile(r'^ITEMGROUPSUBTOTAL_(\d+)_(\d+)$')


def parse_invoice_of_summary(file_path: str) -> dict:
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
        "badge":                 "ENTERPRISE",
        "customer_type":         "",
        "balance_bf":            0,
        "payments_received":     0,
        "charges_period":        0,
        "total_payable":         0,
        "rental_subtotal":       0,
        "usage_subtotal":        0,
        "adjustments":           [],
        "adjustments_subtotal":  0,
        "discounts":             [],
        "top_level_discounts":   [],
        "taxes":                 [],
        "tax_status":            "",
        "total_charges":         0,
        # Customer-facing display currency, e.g. "Rs" - from ACCCURRENCYCODE.
        # NOT the same as SLTACCCURRENCYCODE (SLT's internal accounting
        # currency code, e.g. "LKR") - confirmed distinct tags/values in the
        # real GMF, must not be confused.
        "currency_code":         "",
        "charge_groups":         [],
        "payments":              [],
        "cancelled_payments":    [],
        "total_payments":        0,
        "marketing_messages":    [],
        "suspended_message":     "",
        "source_filename":       os.path.basename(file_path).removesuffix(".processing"),
        "customer_segment":      "",
        "slt_vat_reg":           "",
        "customer_vat_reg":      "",
        "show_vat_lines":        False,
        "address_name_not_required": False,
        "usage_sections":        [],
    }

    raw_address   = {}
    top_discounts = TopLevelDiscountCollector()

    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        current_group            = None
        current_product          = None
        in_subscription_ref      = False
        in_no_sub_ref            = False
        usage_sections           = {}
        current_item_id          = None
        current_subsection       = None
        pending_subsection_label = None
        last_closed_subsection   = None

        # BPR32 promo group state
        in_promo_group        = False
        current_promo_product = None

        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith('DOCEND'):
                break

            # block boundaries
            if line.startswith('BSTARTSLTSUBSCRIPTIONREF'):
                in_subscription_ref = True
                in_no_sub_ref       = False
                continue
            if line.startswith('BENDSLTSUBSCRIPTIONREF'):
                in_subscription_ref = False
                current_group       = None
                continue
            if line.startswith('BSTARTSLTNOSUBSCRIPTIONREF'):
                in_subscription_ref = False
                in_no_sub_ref       = True
                current_group       = None
                continue
            if line.startswith('BENDSLTNOSUBSCRIPTIONREF'):
                in_no_sub_ref = False
                continue

            # BPR32 promo group boundaries
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

            # usage item block
            m = _ITEM_TAG_RE.match(key)
            if m:
                tag, item_id = m.group(1), m.group(2)
                if tag == 'BSTARTITEM':
                    current_item_id = item_id
                    usage_sections[item_id] = {
                        'phone':             '',
                        'label':             '',
                        'subsections':       [],
                        'grand_total':       0,
                        'aggregated_totals': {},
                    }
                elif tag == 'BENDITEM':
                    current_item_id = None
                elif tag == 'EVSOURCE':
                    if item_id in usage_sections:
                        usage_sections[item_id]['phone'] = value
                elif tag == 'EVENTSTEXT':
                    if item_id in usage_sections:
                        usage_sections[item_id]['label'] = value
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
                        row = [value] + [p.strip()
                                         for p in rest.split('|')]
                        current_subsection['rows'].append(row)
                elif tag == 'TENDEVENT':
                    if (current_subsection is not None and
                            item_id in usage_sections):
                        usage_sections[item_id]['subsections'].append(
                            current_subsection)
                        last_closed_subsection = current_subsection
                    current_subsection = None
                elif tag == 'SLTITEMGRANDTOTAL':
                    gparts = [value] + [p.strip() for p in rest.split('|')
                                        if p.strip()]
                    if item_id in usage_sections and len(gparts) >= 2:
                        usage_sections[item_id]['grand_total'] = \
                            to_float(gparts[1])
                continue

            gm = _ITEMGROUP_RE.match(key)
            if gm:
                pending_subsection_label = value
                continue

            sm = _GROUPSUBTOTAL_RE.match(key)
            if sm:
                tag_n = sm.group(1)
                if last_closed_subsection is not None:
                    sub_parts = [value] + [p.strip()
                                           for p in rest.split('|')
                                           if p.strip()]
                    if len(sub_parts) >= 3:
                        last_closed_subsection['subtotal'] = \
                            to_float(sub_parts[2])
                    last_closed_subsection = None
                elif (tag_n == '1' and current_item_id is not None
                        and pending_subsection_label):
                    amt    = to_float(value)
                    totals = usage_sections[
                        current_item_id]['aggregated_totals']
                    totals[pending_subsection_label] = \
                        totals.get(pending_subsection_label, 0) + amt
                    pending_subsection_label = None
                continue

            # BPR32 promo group content
            if in_promo_group:
                if key == 'SLTPRODGROUPLABEL':
                    all_parts = [value] + [p.strip()
                                           for p in rest.split('|')]
                    name = (strip_before_underscore(all_parts[1])
                            if len(all_parts) > 1 else value)
                    name = apply_label_override(name)
                    current_promo_product = {
                        "label": name, "charges": []}
                    # attach to current group or create standalone
                    if current_group is not None:
                        current_group['products'].append(
                            current_promo_product)
                    else:
                        sg = {"ref": "", "products": [current_promo_product]}
                        data['charge_groups'].append(sg)
                        current_group = sg
                    # BPR14: telephone from no-sub-ref block
                    if (in_no_sub_ref and not data['telephone_number']
                            and name.isdigit() and len(name) == 10):
                        data['telephone_number'] = name

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

                elif key == 'SLTPRODLABELDISCDET' and current_promo_product:
                    all_parts = [value] + [p.strip()
                                           for p in rest.split('|')
                                           if p.strip()]
                    if len(all_parts) >= 2:
                        amt = to_float(all_parts[1])
                        if amt:
                            current_promo_product['charges'].append({
                                'description': strip_before_underscore(
                                    all_parts[0]),
                                'amount': -amt,
                            })
                continue

            # BPR23 top-level discounts
            if top_discounts.handle(key, value):
                continue

            # BPR28 marketing messages
            if key in MARKETING_MESSAGE_TAGS:
                if value:
                    data['marketing_messages'].append(value)
                continue
            if key == 'SLT_ALLPRODSUSPENDED':
                data['suspended_message'] = value.split('|')[0].strip()
                continue

            if len(tokens) < 2:
                continue

            # standard fields
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
                data['address_name_not_required'] = \
                    value.strip().upper() == 'Y'

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

            elif key == 'SLT_RENTAL_SUBTOTAL':
                data['rental_subtotal'] = to_float(value)
            elif key == 'SLTEVENTSSUBTOTAL':
                data['usage_subtotal'] = to_float(value)
            elif key == 'SLT_ALL_ADJ_SUBTOTAL':
                data['adjustments_subtotal'] = to_float(value)

            elif key == 'SLTDISCDETAIL':
                all_parts = [value] + [p.strip() for p in rest.split('|')
                                       if p.strip()]
                if len(all_parts) >= 2:
                    amt = to_float(all_parts[0])
                    if amt:
                        data['discounts'].append({
                            'description': strip_before_underscore(
                                all_parts[1]),             # BPR21
                            'amount': -amt,
                        })

            elif key == 'SLTSUBSCRIPTIONREF':
                current_group = {"ref": value, "products": []}
                data['charge_groups'].append(current_group)

            elif key == 'SLTSUBSDETAIL':
                all_parts = [value] + [p.strip() for p in rest.split('|')
                                       if p.strip()]
                if (current_group is not None and len(all_parts) >= 2
                        and to_float(all_parts[0]) != 0):
                    current_group['detail_name'] = all_parts[1]

            elif key == 'SLTPRODUCTLABEL':
                label = apply_label_override(value)      # BPR30
                current_product = {"label": label, "charges": []}
                if current_group is not None:
                    current_group['products'].append(current_product)
                else:
                    sg = {"ref": "", "products": [current_product]}
                    data['charge_groups'].append(sg)
                # BPR14: telephone from no-sub-ref block only
                if (in_no_sub_ref and not data['telephone_number']
                        and value.isdigit() and len(value) == 10):
                    data['telephone_number'] = value

            elif key == 'SLTPRODLABELDET':
                raw       = rest.split('|')
                all_parts = [value] + raw
                if current_product and len(all_parts) > 6:
                    prefix = all_parts[1].split('_')[-1].strip()
                    suffix = all_parts[2].split('_')[-1].strip()
                    desc   = f"{prefix} {suffix}".strip()
                    flag   = (all_parts[5].strip().upper()
                              if len(all_parts) > 5 else '')
                    if flag == 'P':
                        desc += " [Rental]"
                        extra = (all_parts[9].strip()
                                 if len(all_parts) > 9 else '')
                        count = (all_parts[8].strip()
                                 if len(all_parts) > 8 else '')
                        if count and extra:
                            desc += f" [{count} {extra}]"
                    elif flag == 'O':
                        desc += " [One Time]"
                    elif flag == 'I':
                        desc += " [Initiation]"
                    amt = to_float(all_parts[0])
                    current_product['charges'].append(
                        {'description': desc, 'amount': amt})

            elif key == 'SLTPRODLABELUSAGEDET':
                raw       = [p.strip() for p in rest.split('|') if p.strip()]
                all_parts = [value] + raw
                if current_product and len(all_parts) >= 2:
                    amt = to_float(all_parts[1])
                    if amt == 0:                         # BPR22
                        continue
                    desc = strip_before_underscore(all_parts[0])  # BPR21
                    # strip legacy P_ prefix too
                    if desc.startswith('P_'):
                        desc = desc[2:]
                    current_product['charges'].append(
                        {'description': desc, 'amount': amt})

            elif key == 'SLTPRODLABELDISCDET':
                raw       = [p.strip() for p in rest.split('|') if p.strip()]
                all_parts = [value] + raw
                if current_product and len(all_parts) >= 2:
                    amt = to_float(all_parts[1])
                    if amt:
                        current_product['charges'].append({
                            'description': strip_before_underscore(
                                all_parts[0]),             # BPR21
                            'amount': -amt,
                        })

            elif key == 'SLTTAXCODE':
                all_parts = [value] + [p.strip() for p in rest.split('|')
                                       if p.strip()]
                if len(all_parts) >= 4:
                    data['taxes'].append({
                        'name':   all_parts[0],
                        'amount': to_float(all_parts[3]),
                    })

            elif key == 'ADJ':
                raw       = rest.split('|')
                all_parts = [value] + raw
                if len(all_parts) > 15:
                    short_desc = strip_before_underscore(
                        all_parts[2].strip())              # BPR21
                    reason = all_parts[15].strip()[:52]
                    desc   = (f"{short_desc} - {reason}"
                              if reason else short_desc)
                    data['adjustments'].append({
                        'description': desc,
                        'amount':      to_float(all_parts[3]),
                    })

            elif key == 'ACCBALPAYDET':
                raw_parts = [value] + rest.split('|')
                amount    = (to_float(raw_parts[3])
                             if len(raw_parts) > 3 else 0)
                pay_type  = (raw_parts[13].strip()
                             if len(raw_parts) > 13 and raw_parts[13].strip()
                             else 'Payment')
                data['payments'].append({
                    'date': value, 'pay_type': pay_type,
                    'location': '', 'amount': amount,
                })
            elif key == 'ACCBALFPAYDET':             # BPR26
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

    # post-parse
    data['address_lines']       = reorder_addresses(raw_address)
    data['show_vat_lines']      = is_vat_reg_printable(data['customer_vat_reg'])
    data['top_level_discounts'] = top_discounts.discounts

    # BPR20: remove empty products from charge groups
    for grp in data['charge_groups']:
        grp['products'] = [p for p in grp['products'] if p['charges']]
    data['charge_groups'] = [
        g for g in data['charge_groups'] if g['products']
    ]

    # BPR14: fallback telephone if no-sub-ref block had none
    if not data['telephone_number']:
        for grp in data['charge_groups']:
            for prod in grp['products']:
                lbl = prod['label']
                if lbl.isdigit() and len(lbl) == 10:
                    data['telephone_number'] = lbl
                    break
            if data['telephone_number']:
                break

    from core.customer_type_mapper import get_badge
    data['badge'] = get_badge(data['customer_type'])

    # Aggregate no-CDR usage totals into subsections
    for sec in usage_sections.values():
        agg = sec.pop('aggregated_totals', {})
        for label, amt in agg.items():
            sec['subsections'].append({
                'label':    label,
                'headers':  [],
                'rows':     [],
                'subtotal': amt,
            })

    data['usage_sections'] = list(usage_sections.values())
    return data