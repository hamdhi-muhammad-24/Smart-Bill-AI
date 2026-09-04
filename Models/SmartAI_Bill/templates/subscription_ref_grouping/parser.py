"""Subscription Ref Grouping parser (Sheet 23, BILLSTYLE=20)."""
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


def parse_subscription_ref_grouping(file_path: str) -> dict:
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
        "subscription_refs":     [],
        "rental_subtotal":       0,
        "usage_subtotal":        0,
        "adjustments":           [],
        "taxes":                 [],
        "taxes_total":           0,
        "tax_status":            "",
        "total_charges":         0,
        # Customer-facing display currency, e.g. "Rs" - from ACCCURRENCYCODE.
        # NOT the same as SLTACCCURRENCYCODE (SLT's internal accounting
        # currency code, e.g. "LKR") - confirmed distinct tags/values in the
        # real GMF, must not be confused.
        "currency_code":         "",
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
        "show_vat_lines":        False,
        "address_name_not_required": False,
        "usage_sections":        [],
    }

    raw_address   = {}
    top_discounts = TopLevelDiscountCollector()

    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        current_sub_ref          = None
        current_product          = None
        in_no_sub_ref            = False
        usage_sections           = {}
        current_item_id          = None
        current_subsection       = None
        pending_subsection_label = None
        last_closed_subsection   = None

        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith('DOCEND'):
                break

            # subscription ref block boundaries
            if line.startswith('BSTARTSLTSUBSCRIPTIONREF'):
                in_no_sub_ref   = False
                current_product = None
                continue
            if line.startswith('BENDSLTSUBSCRIPTIONREF'):
                current_sub_ref = None
                current_product = None
                in_no_sub_ref   = False
                continue
            if line.startswith('BSTARTSLTNOSUBSCRIPTIONREF'):
                in_no_sub_ref   = True
                current_sub_ref = None
                current_product = None
                continue
            if line.startswith('BENDSLTNOSUBSCRIPTIONREF'):
                in_no_sub_ref   = False
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

            # usage item block
            m = _ITEM_TAG_RE.match(key)
            if m:
                tag, item_id = m.group(1), m.group(2)
                if tag == 'BSTARTITEM':
                    current_item_id = item_id
                    usage_sections[item_id] = {
                        'phone': '', 'label': '',
                        'subsections': [], 'grand_total': 0,
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
                if last_closed_subsection is not None:
                    sub_parts = [value] + [p.strip()
                                           for p in rest.split('|')
                                           if p.strip()]
                    if len(sub_parts) >= 3:
                        last_closed_subsection['subtotal'] = \
                            to_float(sub_parts[2])
                    last_closed_subsection = None
                continue

            # BPR23
            if top_discounts.handle(key, value):
                continue

            # BPR28
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

            elif key == 'SLTSUBSCRIPTIONREF':
                current_sub_ref = {
                    "ref":                value,
                    "detail_name":        "",
                    "products":           [],
                    "recurring_subtotal": 0,
                    "oneoff_subtotal":    0,
                }
                data['subscription_refs'].append(current_sub_ref)

            elif key == 'SLTSUBSDETAIL':
                all_parts = [value] + [p.strip() for p in rest.split('|')
                                       if p.strip()]
                if current_sub_ref and len(all_parts) >= 2:
                    current_sub_ref['detail_name'] = all_parts[1]

            elif key == 'SLTPRODUCTLABEL':
                label = apply_label_override(value)      # BPR30
                current_product = {"label": label, "charges": []}

                if in_no_sub_ref:
                    # BPR14: standalone product outside sub-ref block
                    standalone = {
                        "ref":                "",
                        "detail_name":        "",
                        "products":           [current_product],
                        "recurring_subtotal": 0,
                        "oneoff_subtotal":    0,
                    }
                    data['subscription_refs'].append(standalone)
                elif current_sub_ref is not None:
                    current_sub_ref['products'].append(current_product)
                else:
                    # Fallback: no open ref, create implicit group
                    implicit = {
                        "ref":                "",
                        "detail_name":        "",
                        "products":           [current_product],
                        "recurring_subtotal": 0,
                        "oneoff_subtotal":    0,
                    }
                    data['subscription_refs'].append(implicit)
                    current_sub_ref = implicit

                # BPR14 telephone: first 10-digit label
                if (not data['telephone_number'] and
                        value.isdigit() and len(value) == 10):
                    data['telephone_number'] = value

            elif key == 'SLTPRODLABELDET':
                all_parts = [value] + [p.strip() for p in rest.split('|')
                                       if p.strip()]
                if current_product and len(all_parts) >= 6:
                    prefix = all_parts[1].split('_')[-1].strip()
                    suffix = all_parts[2].split('_')[-1].strip()
                    desc   = f"{prefix} {suffix}".strip()
                    flag   = all_parts[5].strip().upper()
                    start  = (all_parts[6].strip()
                              if len(all_parts) > 6 else '')
                    end    = (all_parts[7].strip()
                              if len(all_parts) > 7 else '')
                    count  = (all_parts[9].strip()
                              if len(all_parts) > 9 else '')
                    unit   = (all_parts[10].strip()
                              if len(all_parts) > 10 else '')
                    if flag == 'P':
                        desc += " [Rental]"
                        if start and end and (
                            start != data['billing_period_start'] or
                            end   != data['billing_period_end']
                        ):
                            desc += f" ({start}-{end})"
                    elif flag == 'O':
                        desc += " [One Time]"
                        if count:
                            desc += f" [{count}]"
                        if start:
                            desc += f" ({start})"
                    elif flag == 'I':
                        desc += " [Initiation]"
                        cu = f"{count} {unit}".strip() if unit else count
                        if cu:
                            desc += f" [{cu}]"
                        if start:
                            desc += f" ({start}-{end})"
                    amt = to_float(all_parts[0])
                    current_product['charges'].append({
                        'description': desc,
                        'amount': amt,
                        'kind': 'charge',
                        'flag': flag,
                    })

            elif key == 'SLTPRODLABELUSAGEDET':
                all_parts = [value] + [p.strip() for p in rest.split('|')
                                       if p.strip()]
                if current_product and len(all_parts) >= 2:
                    amt = to_float(all_parts[1])
                    if amt == 0:                         # BPR22
                        continue
                    desc = strip_before_underscore(all_parts[0])  # BPR21
                    current_product['charges'].append({
                        'description': desc,
                        'amount': amt,
                        'kind': 'usage',
                    })

            elif key == 'SLTPRODLABELDISCDET':
                all_parts = [value] + [p.strip() for p in rest.split('|')
                                       if p.strip()]
                if current_product and len(all_parts) >= 2:
                    amt = to_float(all_parts[1])
                    if amt:
                        current_product['charges'].append({
                            'description': strip_before_underscore(
                                all_parts[0]),             # BPR21
                            'amount': -amt,
                            'kind': 'discount',
                        })

            elif key == 'SLTSUBSLVL_RECURR_SUBTOTAL':
                if current_sub_ref:
                    current_sub_ref['recurring_subtotal'] = to_float(value)

            elif key == 'SLTSUBSLVL_ONEOFF_SUBTOTAL':
                if current_sub_ref:
                    current_sub_ref['oneoff_subtotal'] = to_float(value)

            elif key == 'SLT_RENTAL_SUBTOTAL':
                data['rental_subtotal'] = to_float(value)

            elif key == 'SLTEVENTSSUBTOTAL':
                data['usage_subtotal'] = to_float(value)

            elif key == 'SLTTAXCODE':
                all_parts = [value] + [p.strip() for p in rest.split('|')
                                       if p.strip()]
                if len(all_parts) >= 4:
                    amt = to_float(all_parts[3])
                    data['taxes'].append(
                        {'name': all_parts[0], 'amount': amt})
                    data['taxes_total'] += amt

            elif key == 'ADJ':
                raw       = rest.split('|')
                all_parts = [value] + raw
                if len(all_parts) > 15:
                    short_desc = strip_before_underscore(
                        all_parts[2].strip())
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

    # post-parse
    data['address_lines']       = reorder_addresses(raw_address)
    data['show_vat_lines']      = is_vat_reg_printable(data['customer_vat_reg'])
    data['top_level_discounts'] = top_discounts.discounts

    # BPR20: remove empty products from each sub-ref
    for sr in data['subscription_refs']:
        sr['products'] = [p for p in sr['products'] if p['charges']]
    data['subscription_refs'] = [
        sr for sr in data['subscription_refs'] if sr['products']
    ]

    from core.customer_type_mapper import get_badge
    data['badge'] = get_badge(data['customer_type'])

    data['usage_sections'] = list(usage_sections.values())
    return data