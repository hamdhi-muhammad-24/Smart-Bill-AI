import re
import os
import pytest
from Models.SmartAI_Bill.config import OUTPUT_PDF_NAMES, OUTPUT_PDF_NAME_DEFAULT


def format_output_name(account_number_raw, template_id):
    """Replicates the output naming logic from batch_processor.py."""
    account_number = str(account_number_raw or "unknown")
    account_number = re.sub(r'[^A-Za-z0-9_-]+', '_', account_number).strip('_').replace('_', '')
    if not account_number:
        account_number = "unknown"

    name_pattern = OUTPUT_PDF_NAMES.get(str(template_id), OUTPUT_PDF_NAME_DEFAULT)
    return name_pattern.format(
        account_number=account_number,
        template_id=template_id,
    )


def test_account_number_with_underscores():
    # Example: XXX_XXX_XXXX -> XXXXXXXXXX_NONVAT_HOME.pdf
    result = format_output_name("XXX_XXX_XXXX", "nonvat_home")
    assert result == "XXXXXXXXXX_NONVAT_HOME.pdf"

    result = format_output_name("000_739_8361", "vat_home")
    assert result == "0007398361_VAT_HOME.pdf"

    result = format_output_name("011_234_5678", "vat_enterprise")
    assert result == "0112345678_VAT_ENTERPRISE.pdf"


def test_account_number_with_spaces():
    # Example: 000 739 8361 -> 0007398361_NONVAT_HOME.pdf
    result = format_output_name("000 739 8361", "nonvat_home")
    assert result == "0007398361_NONVAT_HOME.pdf"


def test_various_templates_preserve_template_underscores():
    acc = "000_739_8361"
    assert format_output_name(acc, "nonvat_enterprise") == "0007398361_NONVAT_ENTERPRISE.pdf"
    assert format_output_name(acc, "customer_letter") == "0007398361_Customer_Letter.pdf"
    assert format_output_name(acc, "final_notice") == "0007398361_Final_Notice.pdf"
    assert format_output_name(acc, "lod") == "0007398361_LOD.pdf"
    assert format_output_name(acc, "vat_confirmation") == "0007398361_Vat_confirmation.pdf"
    assert format_output_name(acc, "usd_open_item") == "0007398361_USD_OPEN_Item.pdf"
    assert format_output_name("CR001530388", "summary_statement") == "CR001530388_SUMMARY.pdf"
