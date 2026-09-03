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
