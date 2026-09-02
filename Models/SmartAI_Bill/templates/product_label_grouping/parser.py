"""Product Label Grouping parser (Sheet 22, BILLSTYLE=19)."""

import os
import re

from core.bill_common import (
    to_float,
    strip_before_underscore,
    apply_label_override,
    reorder_addresses,
    TopLevelDiscountCollector,
    parse_cancel_payment,
    MARKETING_MESSAGE_TAGS,
    ADDRESS_PRINT_ORDER,
    is_vat_reg_printable,
)

_ITEM_TAG_RE = re.compile(
    r"^(BSTARTITEM|BENDITEM|EVSOURCE|EVENTSTEXT|EVENTHEADING"
    r"|EVENT|TSTARTEVENT|TENDEVENT|SLTITEMGRANDTOTAL)_(\d+)$"
)

_ITEMGROUP_RE = re.compile(
    r"^ITEMGROUPNAME_1_(\d+)$"
)

_GROUPSUBTOTAL_RE = re.compile(
    r"^ITEMGROUPSUBTOTAL_(\d+)_(\d+)$"
)


def parse_product_label_grouping(file_path: str) -> dict:
    data = {
        "telephone_number": "",
        "account_number": "",
        "invoice_number": "",
        "billing_date": "",
        "billing_period_start": "",
        "billing_period_end": "",
        "payment_due_date": "",
        "customer_name": "",
        "position": "",
        "department": "",
        "business_name": "",
        "address_lines": [],
        "zip_code": "",
        "badge": "HOME",
        "customer_type": "",
        "balance_bf": 0,
        "payments_received": 0,
        "charges_period": 0,
        "total_payable": 0,
        "product_labels": [],
        "adjustments": [],
        "taxes": [],
        "taxes_total": 0,
        "tax_status": "",
        "total_charges": 0,

        # Customer-facing display currency.
        # This is read from ACCCURRENCYCODE, not SLTACCCURRENCYCODE.
        "currency_code": "",

        "payments": [],
        "cancelled_payments": [],
        "total_payments": 0,
        "top_level_discounts": [],
        "marketing_messages": [],
        "suspended_message": "",
        "source_filename": (
            os.path.basename(file_path).removesuffix(".processing")
        ),
        "customer_segment": "",
        "slt_vat_reg": "",
        "customer_vat_reg": "",
        "show_vat_lines": False,
        "address_name_not_required": False,
        "usage_sections": [],
    }

    raw_address = {}
    top_discounts = TopLevelDiscountCollector()

    with open(
        file_path,
        "r",
        encoding="utf-8",
        errors="replace",
    ) as f:
        current_product = None

        usage_sections = {}
        current_item_id = None
        current_subsection = None
        pending_subsection_label = None
        last_closed_subsection = None

        in_promo_group = False
        current_promo_product = None

        for line in f:
            line = line.strip()

            if not line:
                continue

            if line.startswith("DOCEND"):
                break

            # ---------------------------------------------------------
            # Promo group boundaries - BPR32
            # ---------------------------------------------------------
            if (
                line.startswith("BSTARTGROUPPROMO")
                or line.startswith("TSTARTGROUPPROMO")
            ):
                in_promo_group = True
                continue

            if (
                line.startswith("TENDGROUPPROMO")
                or line.startswith("BENDGROUPPROMO")
            ):
                in_promo_group = False
                current_promo_product = None
                continue

            if (
                line.startswith("TSTARTSLTPROMOSUBLABEL")
                or line.startswith("TENDSLTPROMOSUBLABEL")
            ):
                continue

            # Only process records that contain the GMF separator.
            if "|" not in line:
                continue

            parts = line.split("|", 1)
            key_val = parts[0].strip()
            rest = parts[1] if len(parts) > 1 else ""

            tokens = key_val.split(None, 1)
            if not tokens:
                continue

            key = tokens[0].upper()
            value = tokens[1].strip() if len(tokens) > 1 else ""

            # ---------------------------------------------------------
            # Detailed usage item blocks
            # ---------------------------------------------------------
            item_match = _ITEM_TAG_RE.match(key)

            if item_match:
                tag, item_id = item_match.group(1), item_match.group(2)

                if tag == "BSTARTITEM":
                    current_item_id = item_id

                    usage_sections[item_id] = {
                        "phone": "",
                        "label": "",
                        "subsections": [],
                        "grand_total": 0,
                    }

                elif tag == "BENDITEM":
                    current_item_id = None

                elif tag == "EVSOURCE":
                    if item_id in usage_sections:
                        usage_sections[item_id]["phone"] = value

                elif tag == "EVENTSTEXT":
                    if item_id in usage_sections:
                        usage_sections[item_id]["label"] = value

                elif tag == "EVENTHEADING":
                    cols = [value] + [
                        p.strip()
                        for p in rest.split("|")
                        if p.strip()
                    ]

                    current_subsection = {
                        "label": pending_subsection_label or "",
                        "headers": cols,
                        "rows": [],
                        "subtotal": 0,
                    }

                    pending_subsection_label = None

                elif tag == "EVENT":
                    if current_subsection is not None:
                        row = [value] + [
                            p.strip()
                            for p in rest.split("|")
                        ]

                        current_subsection["rows"].append(row)

                elif tag == "TENDEVENT":
                    if (
                        current_subsection is not None
                        and item_id in usage_sections
                    ):
                        usage_sections[item_id]["subsections"].append(
                            current_subsection
                        )

                        last_closed_subsection = current_subsection

                    current_subsection = None

                elif tag == "SLTITEMGRANDTOTAL":
                    grand_total_parts = [value] + [
                        p.strip()
                        for p in rest.split("|")
                        if p.strip()
                    ]

                    if (
                        item_id in usage_sections
                        and len(grand_total_parts) >= 2
                    ):
                        usage_sections[item_id]["grand_total"] = to_float(
                            grand_total_parts[1]
                        )

                continue

            # ---------------------------------------------------------
            # Usage subsection label
            # ---------------------------------------------------------
            group_match = _ITEMGROUP_RE.match(key)

            if group_match:
                pending_subsection_label = value
                continue

            # ---------------------------------------------------------
            # Usage subsection subtotal
            # ---------------------------------------------------------
            subtotal_match = _GROUPSUBTOTAL_RE.match(key)

            if subtotal_match:
                if last_closed_subsection is not None:
                    subtotal_parts = [value] + [
                        p.strip()
                        for p in rest.split("|")
                        if p.strip()
                    ]

                    if len(subtotal_parts) >= 3:
                        last_closed_subsection["subtotal"] = to_float(
                            subtotal_parts[2]
                        )

                    last_closed_subsection = None

                continue

            # ---------------------------------------------------------
            # Promo group content - BPR32
            # ---------------------------------------------------------
            if in_promo_group:
                if key == "SLTPRODGROUPLABEL":
                    all_parts = [value] + [
                        p.strip()
                        for p in rest.split("|")
                    ]

                    name = (
                        strip_before_underscore(all_parts[1])
                        if len(all_parts) > 1
                        else value
                    )

                    name = apply_label_override(name)

                    current_promo_product = {
                        "label": name,
                        "charges": [],
                        "recurring_subtotal": 0,
                        "oneoff_subtotal": 0,
                    }

                    data["product_labels"].append(
                        current_promo_product
                    )

                elif (
                    key == "SLTPRODLABELDET"
                    and current_promo_product is not None
                ):
                    all_parts = [value] + rest.split("|")

                    if len(all_parts) > 6:
                        prefix = all_parts[1].split("_")[-1].strip()
                        suffix = all_parts[2].split("_")[-1].strip()

                        description = f"{prefix} {suffix}".strip()

                        flag = (
                            all_parts[5].strip().upper()
                            if len(all_parts) > 5
                            else ""
                        )

                        if flag == "P":
                            description += " [Rental]"
                        elif flag == "O":
                            description += " [One Time]"
                        elif flag == "I":
                            description += " [Initiation]"

                        amount = to_float(all_parts[0])

                        # SLTPRODLABELDET is a product charge line.
                        # Its amount is displayed in the subtotal, not
                        # beside the description.
                        current_promo_product["charges"].append({
                            "description": description,
                            "amount": amount,
                            "kind": "charge",
                            "flag": flag,
                        })

                elif (
                    key == "SLTPRODLABELDISCDET"
                    and current_promo_product is not None
                ):
                    all_parts = [value] + [
                        p.strip()
                        for p in rest.split("|")
                        if p.strip()
                    ]

                    if len(all_parts) >= 2:
                        amount = to_float(all_parts[1])

                        if amount:
                            # Product-level discounts remain amount lines.
                            current_promo_product["charges"].append({
                                "description": strip_before_underscore(
                                    all_parts[0]
                                ),
                                "amount": -amount,
                                "kind": "discount",
                            })

                elif key == "SLTPRODLABEL_RECURR_SUBTOTAL":
                    if current_promo_product is not None:
                        current_promo_product[
                            "recurring_subtotal"
                        ] = to_float(value)

                elif key == "SLTPRODLABEL_ONEOFF_SUBTOTAL":
                    if current_promo_product is not None:
                        current_promo_product[
                            "oneoff_subtotal"
                        ] = to_float(value)

                continue

            # ---------------------------------------------------------
            # BPR23 - top-level discounts
            # ---------------------------------------------------------
            if top_discounts.handle(key, value):
                continue

            # ---------------------------------------------------------
            # BPR28 - marketing messages
            # ---------------------------------------------------------
            if key in MARKETING_MESSAGE_TAGS:
                if value:
                    data["marketing_messages"].append(value)

                continue

            if key == "SLT_ALLPRODSUSPENDED":
                data["suspended_message"] = value.split("|")[0].strip()
                continue

            # Records without a value are not standard fields.
            if len(tokens) < 2:
                continue

            # ---------------------------------------------------------
            # Standard bill fields
            # ---------------------------------------------------------
            if key == "ACCOUNTNO":
                data["account_number"] = value

            elif key == "BILLREF":
                data["invoice_number"] = value

            elif key == "INVOICEACTUALDATE":
                data["billing_date"] = value

            elif key == "INVOICESTART":
                data["billing_period_start"] = value

            elif key == "INVOICEEND":
                data["billing_period_end"] = value

            elif key == "PAYMENTDUEDATE":
                data["payment_due_date"] = value

            elif key == "CUSTOMERTYPE":
                data["customer_type"] = value

            elif key == "ACCTAXSTATUS":
                data["tax_status"] = value

            elif key == "ACC_ADDRESS_NAME_N_REQIURED":
                data["address_name_not_required"] = (
                    value.strip().upper() == "Y"
                )

            elif key == "ADDRESSNAME":
                data["customer_name"] = value

            elif key == "POSITION":
                data["position"] = value

            elif key == "DEPARTMENT":
                data["department"] = value

            elif key == "BUSINESSNAME":
                data["business_name"] = value

            elif key in ADDRESS_PRINT_ORDER:
                if value:
                    raw_address[key] = value

            elif key == "ZIPCODE":
                data["zip_code"] = value

            elif key == "BALFWD":
                data["balance_bf"] = to_float(value)

            elif key == "ACCBALPAYTOT":
                data["payments_received"] = to_float(value)
                data["total_payments"] = to_float(value)

            elif key == "CHARGES":
                data["charges_period"] = to_float(value)
                data["total_charges"] = to_float(value)

            elif key == "NEWBAL":
                data["total_payable"] = to_float(value)

            elif key == "ACCCURRENCYCODE":
                data["currency_code"] = value

            # ---------------------------------------------------------
            # Product label
            # ---------------------------------------------------------
            elif key == "SLTPRODUCTLABEL":
                label = apply_label_override(value)

                current_product = {
                    "label": label,
                    "charges": [],
                    "recurring_subtotal": 0,
                    "oneoff_subtotal": 0,
                }

                data["product_labels"].append(current_product)

            # ---------------------------------------------------------
            # Product charge detail
            # ---------------------------------------------------------
            elif key == "SLTPRODLABELDET":
                raw = rest.split("|")
                all_parts = [value] + raw

                if current_product is not None and len(all_parts) > 7:
                    prefix = all_parts[1].split("_")[-1].strip()
                    suffix = all_parts[2].split("_")[-1].strip()

                    description = f"{prefix} {suffix}".strip()

                    flag = (
                        all_parts[5].strip().upper()
                        if len(all_parts) > 5
                        else ""
                    )

                    start = (
                        all_parts[6].strip()
                        if len(all_parts) > 6
                        else ""
                    )

                    end = (
                        all_parts[7].strip()
                        if len(all_parts) > 7
                        else ""
                    )

                    if flag == "P":
                        description += " [Rental]"

                        if (
                            start
                            and end
                            and (
                                start
                                != data["billing_period_start"]
                                or end
                                != data["billing_period_end"]
                            )
                        ):
                            description += f" ({start}-{end})"

                    elif flag == "O":
                        count = (
                            all_parts[9].strip()
                            if len(all_parts) > 9
                            else ""
                        )

                        description += " [One Time]"

                        if count:
                            description += f" [{count}]"

                        if start:
                            description += f" ({start})"

                    elif flag == "I":
                        description += " [Initiation]"

                        count = (
                            all_parts[9].strip()
                            if len(all_parts) > 9
                            else ""
                        )

                        unit = (
                            all_parts[10].strip()
                            if len(all_parts) > 10
                            else ""
                        )

                        count_unit = (
                            f"{count} {unit}".strip()
                            if unit
                            else count
                        )

                        if count_unit:
                            description += f" [{count_unit}]"

                        if start:
                            description += f" ({start}-{end})"

                    amount = to_float(all_parts[0])

                    # Important:
                    # This is classified as "charge", so the renderer
                    # prints only the description. The amount is printed
                    # through Product Recurring Subtotal or Product
                    # One-off Subtotal.
                    current_product["charges"].append({
                        "description": description,
                        "amount": amount,
                        "kind": "charge",
                        "flag": flag,
                    })

            # ---------------------------------------------------------
            # Product usage/event detail
            # ---------------------------------------------------------
            elif key == "SLTPRODLABELUSAGEDET":
                raw = [
                    p.strip()
                    for p in rest.split("|")
                    if p.strip()
                ]

                all_parts = [value] + raw

                if current_product is not None and len(all_parts) >= 2:
                    amount = to_float(all_parts[1])

                    # BPR22 - do not display zero-value usage lines.
                    if amount == 0:
                        continue

                    description = strip_before_underscore(
                        all_parts[0]
                    )

                    # This is classified as "usage", so the renderer
                    # prints both the description and the amount after
                    # the Product Recurring Subtotal.
                    current_product["charges"].append({
                        "description": description,
                        "amount": amount,
                        "kind": "usage",
                    })

            # ---------------------------------------------------------
            # Product discount detail
            # ---------------------------------------------------------
            elif key == "SLTPRODLABELDISCDET":
                raw = [
                    p.strip()
                    for p in rest.split("|")
                    if p.strip()
                ]

                all_parts = [value] + raw

                if current_product is not None and len(all_parts) >= 2:
                    amount = to_float(all_parts[1])

                    if amount:
                        current_product["charges"].append({
                            "description": strip_before_underscore(
                                all_parts[0]
                            ),
                            "amount": -amount,
                            "kind": "discount",
                        })

            # ---------------------------------------------------------
            # BPR12 - product subtotals
            # ---------------------------------------------------------
            elif key == "SLTPRODLABEL_RECURR_SUBTOTAL":
                if current_product is not None:
                    current_product[
                        "recurring_subtotal"
                    ] = to_float(value)

            elif key == "SLTPRODLABEL_ONEOFF_SUBTOTAL":
                if current_product is not None:
                    current_product[
                        "oneoff_subtotal"
                    ] = to_float(value)

            # ---------------------------------------------------------
            # Taxes
            # ---------------------------------------------------------
            elif key == "SLTTAXCODE":
                raw = [
                    p.strip()
                    for p in rest.split("|")
                    if p.strip()
                ]

                all_parts = [value] + raw

                if len(all_parts) >= 4:
                    amount = to_float(all_parts[3])

                    data["taxes"].append({
                        "name": all_parts[0],
                        "amount": amount,
                    })

                    data["taxes_total"] += amount

            # ---------------------------------------------------------
            # Adjustments
            # ---------------------------------------------------------
            elif key == "ADJ":
                raw = rest.split("|")
                all_parts = [value] + raw

                if len(all_parts) > 15:
                    short_description = strip_before_underscore(
                        all_parts[2].strip()
                    )

                    reason = all_parts[15].strip()[:52]

                    description = (
                        f"{short_description} - {reason}"
                        if reason
                        else short_description
                    )

                    data["adjustments"].append({
                        "description": description,
                        "amount": to_float(all_parts[3]),
                    })

            # ---------------------------------------------------------
            # Payments
            # ---------------------------------------------------------
            elif key == "ACCBALPAYDET":
                raw_parts = [value] + rest.split("|")

                amount = (
                    to_float(raw_parts[3])
                    if len(raw_parts) > 3
                    else 0
                )

                pay_type = (
                    raw_parts[13].strip()
                    if (
                        len(raw_parts) > 13
                        and raw_parts[13].strip()
                    )
                    else "Payment"
                )

                data["payments"].append({
                    "date": value,
                    "pay_type": pay_type,
                    "location": "",
                    "amount": amount,
                })

            elif key == "ACCBALFPAYDET":
                data["cancelled_payments"].append(
                    parse_cancel_payment(value, rest.split("|"))
                )

            elif key == "SLT_PAYMENT_LOCATION":
                if data["payments"]:
                    data["payments"][-1]["location"] = value

            # ---------------------------------------------------------
            # Other customer fields
            # ---------------------------------------------------------
            elif key == "ACC_CUSTOMER_SEGMENT":
                data["customer_segment"] = value

            elif key == "INVOICINGCOVATREG":
                data["slt_vat_reg"] = value

            elif key == "CUSTOMERVATREF":
                data["customer_vat_reg"] = value

    # -------------------------------------------------------------
    # Post-processing
    # -------------------------------------------------------------
    data["address_lines"] = reorder_addresses(raw_address)

    data["show_vat_lines"] = is_vat_reg_printable(
        data["customer_vat_reg"]
    )

    data["top_level_discounts"] = top_discounts.discounts

    # BPR20 - remove products that have no detail lines.
    #
    # A zero-value product such as:
    #     Double VAS Bundle Charge Free
    # still remains because SLTPRODLABELDET creates a charge record,
    # even though its amount is zero.
    data["product_labels"] = [
        product
        for product in data["product_labels"]
        if product["charges"]
    ]

    # Telephone number:
    # use the first product label containing 10 or 11 digits.
    for product in data["product_labels"]:
        label = product["label"]

        if label.isdigit() and 10 <= len(label) <= 11:
            data["telephone_number"] = label
            break

    from core.customer_type_mapper import get_badge

    data["badge"] = get_badge(data["customer_type"])

    data["usage_sections"] = list(usage_sections.values())

    return data