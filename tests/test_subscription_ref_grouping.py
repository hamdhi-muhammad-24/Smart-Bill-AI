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

from templates.subscription_ref_grouping.renderer import SubscriptionRefGroupingRenderer
from templates.subscription_ref_grouping.parser import parse_subscription_ref_grouping


def _create_sample_gmf():
    return (
        "ACCOUNTNO 005 131 979X |\n"
        "BILLREF 005131979X-0111 |\n"
        "INVOICEACTUALDATE 01/08/2024 |\n"
        "INVOICESTART 01/07/2024 |\n"
        "INVOICEEND 31/07/2024 |\n"
        "PAYMENTDUEDATE 22/08/2024 |\n"
        "ADDRESSNAME Mr Suren |\n"
        "BUSINESSNAME Golf Club Nuwara Eliya |\n"
        "CUSTOMERTYPE Regional-SME |\n"
        "CUSTOMERVATREF 409087450 7000 |\n"
        "INVOICINGCOVATREG 294001727 7000 |\n"
        "ACCCURRENCYCODE Rs |\n"
        "CHARGES 258013.49 |\n"
        "NEWBAL 258013.51 |\n"
        "SLT_RENTAL_SUBTOTAL 203750.00 |\n"
        "BSTARTSLTSUBSCRIPTIONREF |\n"
        "SLTSUBSCRIPTIONREF SB010024229 |\n"
        "SLTSUBSDETAIL 0.00|Data Service Bearer|Subcription|P|01/07/2024|31/07/2024|\n"
        "SLTPRODUCTLABEL NW-NODE-NW-FNW-00019-DAB-0002 |\n"
        "SLTPRODLABELDET 0.00|D_Data Access Bearer|GPON Access|0|2|P|01/07/2024|31/07/2024|SAPROD|0|\n"
        "SLTPRODLABELDET 0.00|D_CPE|Router|2|3|P|01/07/2024|31/07/2024|SAPROD|0|\n"
        "SLTPRODUCTLABEL E1106166 |\n"
        "SLTPRODLABELDET 0.00|D_Business Internet Line|Subscription Fee|0|4|P|01/07/2024|31/07/2024|SAPROD|0|\n"
        "SLTPRODLABELDET 169190.00|D-Business Internet Line_FBW|10 MBPS|4|5|P|01/07/2024|31/07/2024|SAPROD|0|\n"
        "SLTSUBSLVL_RECURR_SUBTOTAL 203750.00 |\n"
        "BENDSLTSUBSCRIPTIONREF |\n"
        "SLTTAXCODE CESS|203750.00|2.04|4156.50|0.00|\n"
        "SLTTAXCODE VAT-18%|218655.50|18.00|39357.99|0.00|\n"
        "DOCEND |\n"
    )


def test_subscription_ref_grouping_tax_invoice_present_when_vat():
    """Verify 'Tax Invoice' is rendered when show_vat_lines is True."""
    gmf_content = _create_sample_gmf()

    with tempfile.NamedTemporaryFile(suffix=".gmf", mode="w", delete=False, encoding="utf-8") as f:
        f.write(gmf_content)
        tmp_path = f.name

    try:
        data = parse_subscription_ref_grouping(tmp_path)
        assert data.get("show_vat_lines") is True

        renderer = SubscriptionRefGroupingRenderer()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
            pdf_path = tmp_pdf.name

        try:
            renderer.render(data)
            renderer.save(pdf_path)

            doc = fitz.open(pdf_path)
            page1_text = doc[0].get_text()
            doc.close()

            assert "Tax Invoice" in page1_text
            assert "SLT VAT Registration Number: 294001727 7000" in page1_text
            assert "Customer VAT Registration Number: 409087450 7000" in page1_text
        finally:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_subscription_ref_grouping_no_tax_invoice_when_nonvat():
    """Verify 'Tax Invoice' is omitted when show_vat_lines is False."""
    gmf_content = _create_sample_gmf()

    with tempfile.NamedTemporaryFile(suffix=".gmf", mode="w", delete=False, encoding="utf-8") as f:
        f.write(gmf_content)
        tmp_path = f.name

    try:
        data = parse_subscription_ref_grouping(tmp_path)
        data["show_vat_lines"] = False

        renderer = SubscriptionRefGroupingRenderer()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
            pdf_path = tmp_pdf.name

        try:
            renderer.render(data)
            renderer.save(pdf_path)

            doc = fitz.open(pdf_path)
            page1_text = doc[0].get_text()
            doc.close()

            assert "Tax Invoice" not in page1_text
        finally:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_subscription_ref_grouping_product_charges_rendered():
    """Verify product rental charge lines are rendered under their product labels."""
    gmf_content = _create_sample_gmf()

    with tempfile.NamedTemporaryFile(suffix=".gmf", mode="w", delete=False, encoding="utf-8") as f:
        f.write(gmf_content)
        tmp_path = f.name

    try:
        data = parse_subscription_ref_grouping(tmp_path)
        assert len(data["subscription_refs"]) == 1
        products = data["subscription_refs"][0]["products"]
        assert len(products) == 2
        assert len(products[0]["charges"]) == 2
        assert products[0]["charges"][0]["description"] == "Data Access Bearer GPON Access [Rental]"
        assert products[0]["charges"][1]["description"] == "CPE Router [Rental]"

        renderer = SubscriptionRefGroupingRenderer()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
            pdf_path = tmp_pdf.name

        try:
            renderer.render(data)
            renderer.save(pdf_path)

            doc = fitz.open(pdf_path)
            page1_text = doc[0].get_text()
            doc.close()

            assert "SB010024229" in page1_text
            assert "NW-NODE-NW-FNW-00019-DAB-0002" in page1_text
            assert "Data Access Bearer GPON Access [Rental]" in page1_text
            assert "CPE Router [Rental]" in page1_text
            assert "E1106166" in page1_text
            assert "Business Internet Line Subscription Fee [Rental]" in page1_text
            assert "FBW 10 MBPS [Rental]" in page1_text
            assert "Data Service Bearer Recurring Subtotal" in page1_text
            assert "203,750.00" in page1_text
        finally:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_subscription_ref_grouping_actual_test_gmf():
    """Verify full rendering with the real test GMF 438883."""
    gmf_path = os.path.join(
        root_dir, "local_gmf_uploads", "Test_GMFs",
        "438883_1-20-01-1-LKR-101-00-BILL-NONRED_1.1"
    )
    if not os.path.exists(gmf_path):
        pytest.skip("Test GMF not present on disk")

    data = parse_subscription_ref_grouping(gmf_path)
    assert data.get("show_vat_lines") is True

    renderer = SubscriptionRefGroupingRenderer()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
        pdf_path = tmp_pdf.name

    try:
        renderer.render(data)
        renderer.save(pdf_path)

        doc = fitz.open(pdf_path)
        # Should be a single-page bill
        assert len(doc) == 1
        page1_text = doc[0].get_text()
        doc.close()

        # Check Tax Invoice
        assert "Tax Invoice" in page1_text

        # Check VAT registration numbers
        assert "SLT VAT Registration Number: 294001727 7000" in page1_text
        assert "Customer VAT Registration Number: 409087450 7000" in page1_text

        # Check Subscription Ref and Products
        assert "SB010024229" in page1_text
        assert "NW-NODE-NW-FNW-00019-DAB-0002" in page1_text
        assert "Data Access Bearer GPON Access [Rental]" in page1_text
        assert "CPE Router [Rental]" in page1_text
        assert "E1106166" in page1_text
        assert "Business Internet Line Subscription Fee [Rental]" in page1_text
        assert "FBW 10 MBPS [Rental]" in page1_text
        assert "NW-NODE-NW-FNW-00019-DAB-0001" in page1_text
        assert "E1106177" in page1_text
        assert "Enterprise Peo TV Peo Prime [Rental]" in page1_text
        assert "Data Service Bearer Recurring Subtotal" in page1_text
        assert "203,750.00" in page1_text

        # Check Taxes & Levies
        assert "Taxes & Levies" in page1_text
        assert "CESS" in page1_text
        assert "4,156.50" in page1_text
        assert "Recovery in lieu of SSCL" in page1_text
        assert "5,457.86" in page1_text
        assert "Telecommunication Levy-15%" in page1_text
        assert "5,291.14" in page1_text
        assert "VAT-18%" in page1_text
        assert "39,357.99" in page1_text

        # Check Total Charges
        assert "Total Charges for the Period" in page1_text
        assert "258,013.49" in page1_text
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
