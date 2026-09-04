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

from templates.invoice_of_summary.renderer import InvoiceOfSummaryRenderer
from templates.invoice_of_summary.parser import parse_invoice_of_summary


def _create_sample_gmf():
    return (
        "ACCOUNTNO 0001234567 |\n"
        "BILLREF 0001234567-2649 |\n"
        "INVOICEACTUALDATE 01/06/2026 |\n"
        "INVOICESTART 01/05/2026 |\n"
        "INVOICEEND 31/05/2026 |\n"
        "PAYMENTDUEDATE 22/06/2026 |\n"
        "ADDRESSNAME Test Customer |\n"
        "CUSTOMERTYPE HOME |\n"
        "ACCCURRENCYCODE Rs |\n"
        "CHARGES 700.00 |\n"
        "NEWBAL 700.00 |\n"
        "BSTARTITEM_33 1 |\n"
        "EVSOURCE_33 0112089628 |\n"
        "EVENTSTEXT_33 Additional Channels |\n"
        "ITEMGROUPNAME_1_1 0112089628 |\n"
        "EVENTHEADING_33 Date | Time | Service Type | Description | Charge |\n"
        "EVENT_33 03/05/2026 | 16:48:29 | Channel | Star Sports Bouquet | 225.000 |\n"
        "EVENT_33 04/05/2026 | 10:33:52 | Channel | Cartoon Network | 100.000 |\n"
        "EVENT_33 05/05/2026 | 12:26:54 | Channel | ANIMAL PLANET | 50.000 |\n"
        "TENDEVENT_33 1 |\n"
        "ITEMGROUPSUBTOTAL_1_1 Total for 0112089628 | | 375.000 |\n"
        "SLTITEMGRANDTOTAL_33 Total Usage Charges for Additional Channels | 375.000 |\n"
        "BENDITEM_33 1 |\n"
    )


def test_invoice_of_summary_parser_strips_trailing_pipe():
    """Verify parser strips trailing empty strings from EVENT rows with trailing pipe."""
    gmf_content = _create_sample_gmf()

    with tempfile.NamedTemporaryFile(suffix=".gmf", mode="w", delete=False, encoding="utf-8") as f:
        f.write(gmf_content)
        tmp_path = f.name

    try:
        data = parse_invoice_of_summary(tmp_path)
        assert len(data["usage_sections"]) == 1
        sub = data["usage_sections"][0]["subsections"][0]
        # Should have exactly 5 elements in row (no trailing empty string)
        for r in sub["rows"]:
            assert len(r) == 5
            assert r[-1] != ""
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_invoice_of_summary_renderer_no_doubled_cost():
    """Verify renderer does not print doubled/overlapping charges in usage table."""
    gmf_content = _create_sample_gmf()

    with tempfile.NamedTemporaryFile(suffix=".gmf", mode="w", delete=False, encoding="utf-8") as f:
        f.write(gmf_content)
        tmp_path = f.name

    try:
        data = parse_invoice_of_summary(tmp_path)

        # Defensively test with an unstripped row appended (e.g. from an external source)
        data["usage_sections"][0]["subsections"][0]["rows"].append(
            ["06/05/2026", "11:00:00", "Channel", "nick", "100.000", ""]
        )

        renderer = InvoiceOfSummaryRenderer()

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
            pdf_path = tmp_pdf.name

        try:
            renderer.render(data)
            renderer.save(pdf_path)

            doc = fitz.open(pdf_path)
            full_text = "\n".join(page.get_text() for page in doc)
            doc.close()

            # Legitimate single values should be present
            assert "225.000" in full_text
            assert "100.000" in full_text
            assert "50.000" in full_text

            # Doubled / overlapping visual artifacts must NOT appear
            assert "22250000" not in full_text
            assert "10000000" not in full_text
            assert "50.500000" not in full_text
        finally:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_invoice_of_summary_tax_invoice_and_department():
    """Verify 'Tax Invoice' and 'department' appear when applicable."""
    gmf_path = os.path.join(
        root_dir, "local_gmf_uploads", "Test_GMFs",
        "521515_1-18-02-1-LKR-101-1-BILL-NONRED_1.1"
    )
    if not os.path.exists(gmf_path):
        pytest.skip("Test GMF not present on disk")

    data = parse_invoice_of_summary(gmf_path)
    assert data.get("show_vat_lines") is True
    assert data.get("department") == "LIFE DIVITION"
    assert data.get("business_name") == "CEYLINCO INSURANCE CO LTD"

    renderer = InvoiceOfSummaryRenderer()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
        pdf_path = tmp_pdf.name

    try:
        renderer.render(data)
        renderer.save(pdf_path)

        doc = fitz.open(pdf_path)
        page1_text = doc[0].get_text()
        doc.close()

        # Both "Tax Invoice" and "LIFE DIVITION" must appear on Page 1
        assert "Tax Invoice" in page1_text
        assert "LIFE DIVITION" in page1_text
        assert "CEYLINCO INSURANCE CO LTD" in page1_text

        # Verify ordering in address box: LIFE DIVITION before CEYLINCO INSURANCE CO LTD
        lines = [l.strip() for l in page1_text.splitlines() if l.strip()]
        dept_idx = lines.index("LIFE DIVITION")
        biz_idx = lines.index("CEYLINCO INSURANCE CO LTD")
        assert dept_idx < biz_idx

        # Verify Charges in Detail is on Page 1
        assert "Charges in Detail" in page1_text
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)


def test_invoice_of_summary_no_tax_invoice_when_non_vat():
    """Verify 'Tax Invoice' is omitted when show_vat_lines is False."""
    gmf_content = _create_sample_gmf()

    with tempfile.NamedTemporaryFile(suffix=".gmf", mode="w", delete=False, encoding="utf-8") as f:
        f.write(gmf_content)
        tmp_path = f.name

    try:
        data = parse_invoice_of_summary(tmp_path)
        data["show_vat_lines"] = False

        renderer = InvoiceOfSummaryRenderer()
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


def test_invoice_of_summary_discounts_and_no_sscl():
    """Verify discounts appear in both summary and detail, and SSCL is removed."""
    gmf_path = os.path.join(
        root_dir, "local_gmf_uploads", "Test_GMFs",
        "521515_1-18-02-1-LKR-101-1-BILL-NONRED_1.1"
    )
    if not os.path.exists(gmf_path):
        pytest.skip("Test GMF not present on disk")

    data = parse_invoice_of_summary(gmf_path)

    # 1. Verify discounts parsed into top_level_discounts
    assert len(data.get("top_level_discounts", [])) > 0
    ceylinco_disc = next(
        (d for d in data["top_level_discounts"] if d["description"] == "Discount Ceylinco"),
        None
    )
    assert ceylinco_disc is not None
    assert ceylinco_disc["amount"] == -24093.22

    # 2. Verify Recovery in lieu of SSCL removed from taxes
    tax_names = [t["name"] for t in data.get("taxes", [])]
    assert "Recovery in lieu of SSCL" not in tax_names
    assert not any("SSCL" in name.upper() for name in tax_names)

    # 3. Render and verify PDF text
    renderer = InvoiceOfSummaryRenderer()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
        pdf_path = tmp_pdf.name

    try:
        renderer.render(data)
        renderer.save(pdf_path)

        doc = fitz.open(pdf_path)
        page1_text = doc[0].get_text()
        doc.close()

        # Both Summary of Invoice and Charges in Detail must contain Discounts and Discount Ceylinco
        assert page1_text.count("Discounts") >= 2
        assert page1_text.count("Discount Ceylinco") >= 2
        assert "- 24,093.22" in page1_text

        # SSCL must NOT appear anywhere in the rendered invoice
        assert "Recovery in lieu of SSCL" not in page1_text
        assert "SSCL" not in page1_text

        # Total charges remains intact
        assert "299,231.23" in page1_text
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)

