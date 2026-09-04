import os
import sys
import tempfile
import pytest
import fitz

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
smartai_dir = os.path.join(root_dir, "Models", "SmartAI_Bill")
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
if smartai_dir not in sys.path:
    sys.path.insert(0, smartai_dir)

from templates.vat_enterprise.renderer import VATEnterpriseRenderer
from templates.vat_enterprise.parser import parse_vat_enterprise


def _sample_vat_enterprise_data():
    return {
        "telephone_number": "0522267554",
        "account_number": "000 201 075X",
        "invoice_number": "000201075X-2652",
        "billing_date": "01/10/2025",
        "billing_period_start": "01/09/2025",
        "billing_period_end": "30/09/2025",
        "payment_due_date": "22/10/2025",
        "customer_name": "To .",
        "position": "THE WARDEN",
        "department": "",
        "business_name": "Plantation Staff College",
        "address_lines": [
            "Director CEO",
            "National Institute Of Plantation Management",
            "MDH Jayawardhana Mawatha",
            "Athurugiriya",
        ],
        "zip_code": "10150",
        "badge": "ENTERPRISE",
        "balance_bf": 4509.01,
        "payments_received": 4509.03,
        "charges_period": 4529.65,
        "total_payable": 4529.63,
        "total_charges": 4529.65,
        "slt_vat_reg": "294001727 7000",
        "customer_vat_reg": "0000000007000",
        "show_vat_lines": True,
        "address_name_not_required": True,
        "currency_code": "Rs",
        "product_labels": [],
        "adjustments": [],
        "taxes": [],
        "top_level_discounts": [],
        "payments": [],
        "cancelled_payments": [],
        "marketing_messages": [],
        "usage_sections": [],
        "source_filename": "test_BILL-NONRED_1.7.gmf",
    }


def test_vat_enterprise_to_placeholder_removed():
    """Verify 'To .' placeholder is not rendered in the address box."""
    data = _sample_vat_enterprise_data()
    renderer = VATEnterpriseRenderer()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
        pdf_path = tmp_pdf.name

    try:
        renderer.render(data)
        renderer.save(pdf_path)

        doc = fitz.open(pdf_path)
        page1_text = doc[0].get_text()
        doc.close()

        # 'To .' should NOT be present in page 1
        lines = [line.strip() for line in page1_text.splitlines() if line.strip()]
        assert "To ." not in lines
        assert "To." not in lines

        # THE WARDEN should be present and precede Plantation Staff College
        assert "THE WARDEN" in lines
        assert "Plantation Staff College" in lines
        warden_idx = lines.index("THE WARDEN")
        college_idx = lines.index("Plantation Staff College")
        assert warden_idx < college_idx
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)


def test_vat_enterprise_valid_customer_name_kept_when_required():
    """Verify legitimate customer name is rendered when address_name_not_required is False."""
    data = _sample_vat_enterprise_data()
    data["customer_name"] = "Mr John Doe"
    data["address_name_not_required"] = False
    renderer = VATEnterpriseRenderer()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
        pdf_path = tmp_pdf.name

    try:
        renderer.render(data)
        renderer.save(pdf_path)

        doc = fitz.open(pdf_path)
        page1_text = doc[0].get_text()
        doc.close()

        lines = [line.strip() for line in page1_text.splitlines() if line.strip()]
        assert "Mr John Doe" in lines
        assert "THE WARDEN" in lines
        doe_idx = lines.index("Mr John Doe")
        warden_idx = lines.index("THE WARDEN")
        assert doe_idx < warden_idx
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)


def test_vat_enterprise_parser_cleans_to_placeholder():
    """Verify parser strips 'To .' placeholder from ADDRESSNAME."""
    gmf_content = (
        "ACCOUNTNO 000201075X |\n"
        "BILLREF 000201075X-2652 |\n"
        "INVOICEACTUALDATE 01/10/2025 |\n"
        "INVOICESTART 01/09/2025 |\n"
        "INVOICEEND 30/09/2025 |\n"
        "PAYMENTDUEDATE 22/10/2025 |\n"
        "ACC_ADDRESS_NAME_N_REQIURED Y |\n"
        "ADDRESSNAME To . |\n"
        "POSITION THE WARDEN |\n"
        "BUSINESSNAME Plantation Staff College |\n"
        "CUSTOMERTYPE ENTERPRISE |\n"
        "ACCCURRENCYCODE Rs |\n"
        "CHARGES 100.00 |\n"
        "NEWBAL 100.00 |\n"
        "DOCEND |\n"
    )

    with tempfile.NamedTemporaryFile(suffix=".gmf", mode="w", delete=False, encoding="utf-8") as f:
        f.write(gmf_content)
        tmp_gmf = f.name

    try:
        parsed = parse_vat_enterprise(tmp_gmf)
        assert parsed["customer_name"] == ""
        assert parsed["position"] == "THE WARDEN"
        assert parsed["business_name"] == "Plantation Staff College"
        assert parsed["address_name_not_required"] is True
    finally:
        if os.path.exists(tmp_gmf):
            os.remove(tmp_gmf)


def test_vat_enterprise_vat_reg_font_size():
    """Verify VAT registration lines in VAT Enterprise are rendered with font size 7."""
    data = _sample_vat_enterprise_data()
    renderer = VATEnterpriseRenderer()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
        pdf_path = tmp_pdf.name

    try:
        renderer.render(data)
        renderer.save(pdf_path)

        doc = fitz.open(pdf_path)
        blocks = doc[0].get_text("dict")["blocks"]
        doc.close()

        found_slt = False
        found_customer = False
        for b in blocks:
            if "lines" in b:
                for line in b["lines"]:
                    for span in line["spans"]:
                        if "SLT VAT Registration Number" in span["text"]:
                            assert span["size"] == 7.0
                            found_slt = True
                        if "Customer VAT Registration Number" in span["text"]:
                            assert span["size"] == 7.0
                            found_customer = True

        assert found_slt, "SLT VAT Registration Number was not found in PDF output"
        assert found_customer, "Customer VAT Registration Number was not found in PDF output"
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)

