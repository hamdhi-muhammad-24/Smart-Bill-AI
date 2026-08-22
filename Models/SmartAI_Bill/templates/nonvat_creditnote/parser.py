# parser.py
import re
import os
import datetime
from typing import Any


def parse_nonvat_creditnote(file_path):

    """
    Parses Non VAT Credit Note raw file.
    BILLSTYLE = 6
    """

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")


    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()



    summary: dict[str, str] = {
        "balance_bf": "0.00",
        "payments_received": "0.00",
        "arrears": "0.00",
        "adjustment_value": "0.00",
        "total_payable": "0.00"
    }

    adjustments: list[dict] = []

    data: dict[str, Any] = {
        # Header
        "account_number": "",
        "invoice_number": "",
        "billing_date": "",
        "bill_period": "",
        "acc_currency_code": "",

        # Barcode
        "barcode": "",

        # Address
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

        # VAT lines
        "below_address_line1": "",
        "below_address_line2": "",

        # Extra lines
        "header_extra_line1": "",
        "header_extra_line2": "",

        # Summary
        "summary": summary,
        "charge_for_period": "0.00",

        # Adjustment rows
        "adjustments": adjustments
    }




    def extract_field(pattern, text):

        match = re.search(pattern, text, re.IGNORECASE)

        return match.group(1).strip() if match else ""





    # --------------------------------------------------
    # Header Details
    # --------------------------------------------------

    data["account_number"] = extract_field(
        r"ACCOUNTNO\s+([^|]+)",
        content
    )


    data["invoice_number"] = extract_field(
        r"BILLREF\s+([^|]+)",
        content
    )


    # Barcode uses a cleaned invoice reference
    barcode_value = data["invoice_number"] or data["account_number"] or ""
    data["barcode"] = "".join(ch for ch in barcode_value if ch.isalnum())



    data["billing_date"] = extract_field(
        r"INVOICEACTUALDATE\s+([^|]+)",
        content
    )


    data["acc_currency_code"] = extract_field(
        r"ACCCURRENCYCODE\s+([^|]+)",
        content
    )



    start_match = re.search(
        r"INVOICESTART\s+([^|]+)",
        content,
        re.IGNORECASE
    )


    end_match = re.search(
        r"INVOICEEND\s+([^|]+)",
        content,
        re.IGNORECASE
    )


    if start_match and end_match:

        data["bill_period"] = (
            f"{start_match.group(1).strip()} - "
            f"{end_match.group(1).strip()}"
        )




    # --------------------------------------------------
    # Address
    # --------------------------------------------------

    data["address_line1"] = extract_field(
        r"\bADDRESSNAME\s+([^|]+)",
        content
    )


    data["address_line2"] = extract_field(
        r"\bPOSITION\s+([^|]+)",
        content
    )


    data["address_line3"] = extract_field(
        r"\bDEPARTMENT\s+([^|]+)",
        content
    )


    data["address_line4"] = extract_field(
        r"\bBUSINESSNAME\s+([^|]+)",
        content
    )


    data["address_line5"] = extract_field(
        r"\bADDRESS5\s+([^|]+)",
        content
    )


    data["address_line6"] = extract_field(
        r"\bADDRESS2\s+([^|]+)",
        content
    )


    data["address_line7"] = extract_field(
        r"\bADDRESS3\s+([^|]+)",
        content
    )


    data["address_line8"] = extract_field(
        r"\bADDRESS4\s+([^|]+)",
        content
    )


    data["address_line9"] = extract_field(
        r"\bADDRESS1\s+([^|]+)",
        content
    )


    data["address_line10"] = extract_field(
        r"\bZIPCODE\s+([^|]+)",
        content
    )




    # --------------------------------------------------
    # Extra Header Information
    # --------------------------------------------------

    filename = os.path.basename(file_path).removesuffix(".processing")
    # Clean the source filename by removing the random suffix (e.g. __a9ijep_x_1.gmf)
    if "__" in filename:
        filename = filename.split("__")[0]

    timestamp = datetime.datetime.now().strftime(
        "%H:%M:%d%m%Y"
    )


    data["header_extra_line1"] = (
        f"S{filename}/{timestamp}"
    )



    data["header_extra_line2"] = extract_field(
        r"\bACC_CUSTOMER_SEGMENT\s+([^|]+)",
        content
    )





    # --------------------------------------------------
    # VAT Information
    # --------------------------------------------------

    data["below_address_line1"] = ""
    data["below_address_line2"] = ""


    # --------------------------------------------------
    # Summary
    # --------------------------------------------------

    data["summary"]["balance_bf"] = extract_field(
        r"\bBALFWD\s+([^|]+)",
        content
    )


    data["summary"]["payments_received"] = extract_field(
        r"\bACCBALPAYTOT\s+([^|]+)",
        content
    )


    data["summary"]["arrears"] = extract_field(
        r"\bBALOUT\s+([^|]+)",
        content
    )


    data["summary"]["adjustment_value"] = extract_field(
        r"\bINVTOTALROUNDED\s+([^|]+)",
        content
    )


    data["summary"]["total_payable"] = extract_field(
        r"\bNEWBAL\s+([^|]+)",
        content
    )



    data["charge_for_period"] = extract_field(
        r"\bCHARGES[\s|]+([^|]+)",
        content
    )





    # --------------------------------------------------
    # Adjustments + Taxes
    # --------------------------------------------------

    for line in content.splitlines():

        line_upper = line.strip().upper()



        if line_upper.startswith("ADJ"):

            parts = line.split("|")


            if len(parts) >= 16:


                title = parts[2].strip()

                title = title.replace(
                    "FTTH_",
                    ""
                )


                amount = parts[3].strip()

                description = (
                    f"{title} {parts[15].strip()}"
                )


                data["adjustments"].append({

                    "description":
                    " ".join(description.split()),

                    "amount":
                    amount if amount else None,

                    "level":2

                })




        elif line_upper.startswith("INVTOTALTAX"):


            number = re.search(
                r'(-?\d+\.\d+)',
                line
            )


            tax_amount = (
                number.group(1)
                if number else None
            )



            data["adjustments"].append({

                "description":
                "Taxes & Levies",

                "amount":
                tax_amount,

                "level":2

            })




    return data