import re
import os
import datetime


def parse_vat_creditnote(file_path: str) -> dict:
    """
    Parser for VAT Credit Note BILLSTYLE=6.
    Extracts header, customer details, summary,
    adjustments and taxes.
    """

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    data = {
        "account_number": "",
        "invoice_number": "",
        "billing_date": "",
        "bill_period": "",
        "acc_currency_code": "",

        "address_line1": "",
        "address_line2": "",
        "address_line3": "",
        "address_line4": "",
        "address_line5": "",
        "address_line6": "",
        "address_line7": "",
        "address_line8": "",
        "address_line9": "",
        "address_line10": "",

        "below_address_line1": "",
        "below_address_line2": "",

        "header_extra_line1": "",
        "header_extra_line2": "",

        "summary": {
            "balance_bf": "0.00",
            "payments_received": "0.00",
            "arrears": "0.00",
            "adjustment_value": "0.00",
            "total_payable": "0.00"
        },

        "charge_for_period": "0.00",

        "adjustments": [],
        "taxes_levies": [],

        "source_filename": os.path.basename(file_path).removesuffix(".processing")
    }


    def extract_field(pattern, text):
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1).strip() if match else ""


    # Header
    data["account_number"] = extract_field(
        r"ACCOUNTNO\s+([^|]+)",
        content
    )

    data["invoice_number"] = extract_field(
        r"BILLREF\s+([^|]+)",
        content
    )

    data["billing_date"] = extract_field(
        r"INVOICEACTUALDATE\s+([^|]+)",
        content
    )

    data["acc_currency_code"] = extract_field(
        r"ACCCURRENCYCODE\s+([^|]+)",
        content
    )


    # Billing period

    start = extract_field(
        r"INVOICESTART\s+([^|]+)",
        content
    )

    end = extract_field(
        r"INVOICEEND\s+([^|]+)",
        content
    )

    if start and end:
        data["bill_period"] = f"{start} - {end}"


    # Address

    address_mapping = {
        "address_line1": "ADDRESSNAME",
        "address_line2": "POSITION",
        "address_line3": "DEPARTMENT",
        "address_line4": "BUSINESSNAME",
        "address_line5": "ADDRESS5",
        "address_line6": "ADDRESS2",
        "address_line7": "ADDRESS3",
        "address_line8": "ADDRESS4",
        "address_line9": "ADDRESS1",
        "address_line10": "ZIPCODE"
    }


    for field, key in address_mapping.items():
        data[field] = extract_field(
            rf"\b{key}\s+([^|]+)",
            content
        )


    # Extra header lines

    filename = os.path.basename(file_path).removesuffix(".processing")
    if "__" in filename:
        filename = filename.split("__")[0]
        
    timestamp = datetime.datetime.now().strftime("%H:%M:%d%m%Y")

    data["header_extra_line1"] = (
        f"S{filename}/{timestamp}"
    )

    data["header_extra_line2"] = extract_field(
        r"ACC_CUSTOMER_SEGMENT\s+([^|]+)",
        content
    )


    # VAT

    slt_vat = extract_field(
        r"INVOICINGCOVATREG\s+([^|]+)",
        content
    )

    if slt_vat:
        data["below_address_line1"] = (
            f"SLT VAT Registration Number : {slt_vat}"
        )


    customer_vat = extract_field(
        r"CUSTOMERVATREF\s+([^|]+)",
        content
    )

    if customer_vat:
        data["below_address_line2"] = (
            f"Customer VAT Registration Number : {customer_vat}"
        )


    # Summary

    data["summary"]["balance_bf"] = extract_field(
        r"BALFWD\s+([^|]+)",
        content
    )

    data["summary"]["payments_received"] = extract_field(
        r"ACCBALPAYTOT\s+([^|]+)",
        content
    )

    data["summary"]["arrears"] = extract_field(
        r"BALOUT\s+([^|]+)",
        content
    )

    data["summary"]["adjustment_value"] = extract_field(
        r"INVTOTALROUNDED\s+([^|]+)",
        content
    )

    data["summary"]["total_payable"] = extract_field(
        r"NEWBAL\s+([^|]+)",
        content
    )


    data["charge_for_period"] = extract_field(
        r"CHARGES[\s|]+([^|]+)",
        content
    )


    # Adjustments and Taxes

    for line in content.splitlines():

        upper = line.strip().upper()

        if upper.startswith("ADJ"):

            parts = line.split("|")

            if len(parts) >= 16:

                title = parts[2].strip()
                title = title.replace("FTTH_", "")

                amount = parts[3].strip()

                reason = parts[15].strip()

                description = (
                    f"{title} {reason}"
                )

                data["adjustments"].append({
                    "description": " ".join(description.split()),
                    "amount": amount,
                    "level": 2
                })


        elif upper.startswith("TAXCODE"):

            parts = line.split("|")

            if len(parts) >= 15:

                data["taxes_levies"].append({
                    "description": parts[1].strip(),
                    "amount": parts[14].strip(),
                    "level": 2
                })


    return data