"""NonVAT Enterprise parser (Sheet 19)."""
import os
import re
from typing import Any

from core.bill_common import (
    to_float, strip_before_underscore, apply_label_override,
    reorder_addresses, TopLevelDiscountCollector, parse_cancel_payment,
    PhoneNumberFromNoSubRefBlock, MARKETING_MESSAGE_TAGS,
    ADDRESS_PRINT_ORDER, is_vat_reg_printable,
)

_ITEM_TAG_RE = re.compile(
    r'^(BSTARTITEM|BENDITEM|EVSOURCE|EVENTSTEXT|EVENTHEADING'
    r'|EVENT|TSTARTEVENT|TENDEVENT|SLTITEMGRANDTOTAL)_(\d+)$'
)
_ITEMGROUP_RE     = re.compile(r'^ITEMGROUPNAME_1_(\d+)$')
_GROUPSUBTOTAL_RE = re.compile(r'^ITEMGROUPSUBTOTAL_(\d+)_(\d+)$')


def parse_nonvat_enterprise(file_path: str) -> dict:
    data: dict[str, Any] = {
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
        "show_vat_lines":        False,
        "address_name_not_required": False,
        "usage_sections":        [],
    }

    raw_address   = {}
    top_discounts = TopLevelDiscountCollector()
    phone_finder  = PhoneNumberFromNoSubRefBlock()

    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        current_product: dict[str, Any] | None = None
        usage_sections: dict[str, Any]         = {}
        current_item_id                        = None
        current_subsection: dict[str, Any] | None = None
        pending_subsection_label               = None
        last_closed_subsection: dict[str, Any] | None = None
        in_promo_group                         = False
        current_promo_product: dict[str, Any] | None  = None

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

            # ── usage block ─────────────────────────────────────────
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
                        # Strip P_ prefix from section label
                        label = value
                        if label.startswith('P_'):
                            label = label[2:]
                        usage_sections[item_id]['label'] = label
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
                    sub_parts = [value] + [p.strip() for p in rest.split('|')
                                           if p.strip()]
                    if len(sub_parts) >= 3:
                        last_closed_subsection['subtotal'] = \
                            to_float(sub_parts[2])
                    last_closed_subsection = None
                continue

            # ── promo group ─────────────────────────────────────────
            if in_promo_group:
                if key == 'SLTPRODGROUPLABEL':
                    all_parts = [value] + [p.strip()
                                           for p in rest.split('|')]
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
                            phone_finder.confirm_charge()
                continue

            # ── BPR23 ───────────────────────────────────────────────
            if top_discounts.handle(key, value):
                continue

            # ── BPR28 ───────────────────────────────────────────────
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

            elif key == 'SLTPRODUCTLABEL':
                label = apply_label_override(value)
                current_product = {"label": label, "charges": []}
                data['product_labels'].append(current_product)
                phone_finder.candidate(value)

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
                    current_product['charges'].append(
                        {'description': desc, 'amount': amt})
                    if amt:
                        phone_finder.confirm_charge()

            elif key == 'SLTPRODLABELUSAGEDET':
                raw       = [p.strip() for p in rest.split('|') if p.strip()]
                all_parts = [value] + raw
                if current_product and len(all_parts) >= 2:
                    amt = to_float(all_parts[1])
                    if amt == 0:                        # BPR22
                        continue
                    desc = strip_before_underscore(all_parts[0])  # BPR21
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
                            'description': strip_before_underscore(
                                all_parts[0]),             # BPR21
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

    # ── post-parse ───────────────────────────────────────────────────
    data['address_lines']       = reorder_addresses(raw_address)
    data['show_vat_lines']      = is_vat_reg_printable(data['customer_vat_reg'])
    data['telephone_number']    = phone_finder.result
    data['top_level_discounts'] = top_discounts.discounts

    # BPR20: remove empty products
    data['product_labels'] = [
        p for p in data['product_labels'] if p['charges']
    ]

    from core.customer_type_mapper import get_badge
    data['badge'] = get_badge(data['customer_type'])

    # BPR22: drop subsections with no rows AND zero subtotal
    for sec in usage_sections.values():
        sec['subsections'] = [
            s for s in sec['subsections']
            if s.get('rows') or s.get('subtotal')
        ]

    # Drop entire usage sections that have no remaining subsections
    data['usage_sections'] = [
        s for s in usage_sections.values() if s['subsections']
    ]

    return data