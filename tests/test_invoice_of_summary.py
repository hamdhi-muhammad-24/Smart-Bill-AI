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


def test_invoice_of_summary_discounts_and_taxes_including_sscl():
    """Verify discounts appear in both summary and detail, and taxes include Recovery in lieu of SSCL in order."""
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

    # 2. Verify taxes include VAT-18%, Recovery in lieu of SSCL, Telecommunication Levy-15%, CESS in order
    tax_names = [t["name"] for t in data.get("taxes", [])]
    assert tax_names == ["VAT-18%", "Recovery in lieu of SSCL", "Telecommunication Levy-15%", "CESS"]

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

        # All 4 taxes must appear under Taxes & Levies in order
        assert "VAT-18%" in page1_text
        assert "Recovery in lieu of SSCL" in page1_text
        assert "Telecommunication Levy-15%" in page1_text
        assert "CESS" in page1_text

        pos_vat = page1_text.find("VAT-18%")
        pos_sscl = page1_text.find("Recovery in lieu of SSCL")
        pos_telecom = page1_text.find("Telecommunication Levy-15%")
        pos_cess = page1_text.find("CESS")
        assert pos_vat < pos_sscl < pos_telecom < pos_cess

        # Total charges remains intact
        assert "299,231.23" in page1_text
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)


def test_invoice_of_summary_bpr20_zero_charge_lines_retained_and_rendered():
    """Verify BPR20: zero-amount SLTPRODLABELDET charges are retained and printed without charge."""
    gmf_content = (
        "ACCOUNTNO 0001234567 |\n"
        "BILLREF 0001234567-2649 |\n"
        "INVOICEACTUALDATE 01/06/2026 |\n"
        "INVOICESTART 01/05/2026 |\n"
        "INVOICEEND 31/05/2026 |\n"
        "PAYMENTDUEDATE 22/06/2026 |\n"
        "ADDRESSNAME Test Customer |\n"
        "CUSTOMERTYPE HOME |\n"
        "ACCCURRENCYCODE Rs |\n"
        "CHARGES 749.00 |\n"
        "NEWBAL 749.00 |\n"
        "SLTSUBSCRIPTIONREF 0112226441 |\n"
        "SLTPRODUCTLABEL 0112226441 |\n"
        "SLTPRODLABELDET 749.00 | Megaline .Office | Single Play | 56 | 59 | P | 01/05/2026 | 31/05/2026 | SAPROD | 0 |\n"
        "SLTPRODLABELDET 0.00 | SLT | CLI Free | 56 | 59 | P | 01/05/2026 | 31/05/2026 | SAPROD | 0 |\n"
        "SLTSUBSCRIPTIONREF 0112692167 |\n"
        "SLTPRODUCTLABEL 0112692167 |\n"
        "SLTPRODLABELDET 0.00 | V_Voice VAS | Bundle Charge | 56 | 59 | P | 01/05/2026 | 31/05/2026 | SAPROD | 0 |\n"
        "SLTPRODLABELDET 0.00 | Call | hunting Enhanced Service | 56 | 59 | P | 01/05/2026 | 31/05/2026 | SAPROD | 0 |\n"
        "SLTPRODLABELDET 0.00 | Single | VAS Bundle Charge Free | 56 | 59 | P | 01/05/2026 | 31/05/2026 | SAPROD | 0 |\n"
        "SLTPRODLABELDET 0.00 | Double | VAS Bundle Charge Free | 56 | 59 | P | 01/05/2026 | 31/05/2026 | SAPROD | 0 |\n"
    )

    with tempfile.NamedTemporaryFile(suffix=".gmf", mode="w", delete=False, encoding="utf-8") as f:
        f.write(gmf_content)
        tmp_gmf = f.name

    try:
        data = parse_invoice_of_summary(tmp_gmf)

        # 1. Verify all charge descriptions are parsed into charge_groups
        all_descriptions = [
            c["description"]
            for grp in data["charge_groups"]
            for prod in grp["products"]
            for c in prod["charges"]
        ]
        assert "Megaline .Office Single Play [Rental]" in all_descriptions
        assert "SLT CLI Free [Rental]" in all_descriptions
        assert "Voice VAS Bundle Charge [Rental]" in all_descriptions
        assert "Call hunting Enhanced Service [Rental]" in all_descriptions
        assert "Single VAS Bundle Charge Free [Rental]" in all_descriptions
        assert "Double VAS Bundle Charge Free [Rental]" in all_descriptions

        # 2. Verify zero-amount charges have amount=None (printed without charge)
        zero_charges = [
            c for grp in data["charge_groups"]
            for prod in grp["products"]
            for c in prod["charges"]
            if c["description"] != "Megaline .Office Single Play [Rental]"
        ]
        for c in zero_charges:
            assert c["amount"] is None

        # 3. Render and verify PDF
        renderer = InvoiceOfSummaryRenderer()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
            pdf_path = tmp_pdf.name

        try:
            renderer.render(data)
            renderer.save(pdf_path)

            doc = fitz.open(pdf_path)
            full_text = "\n".join(page.get_text() for page in doc)
            doc.close()

            assert "SLT CLI Free [Rental]" in full_text
            assert "Voice VAS Bundle Charge [Rental]" in full_text
            assert "Call hunting Enhanced Service [Rental]" in full_text
            assert "Single VAS Bundle Charge Free [Rental]" in full_text
            assert "Double VAS Bundle Charge Free [Rental]" in full_text
        finally:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
    finally:
        if os.path.exists(tmp_gmf):
            os.remove(tmp_gmf)


def test_invoice_of_summary_zero_charge_subscription_ref_rendered():
    """Verify subscription ref with only 0-amount charges (e.g. SB010018588) is not pruned."""
    gmf_content = (
        "ACCOUNTNO 0001234567 |\n"
        "BILLREF 0001234567-2649 |\n"
        "INVOICEACTUALDATE 01/06/2026 |\n"
        "INVOICESTART 01/05/2026 |\n"
        "INVOICEEND 31/05/2026 |\n"
        "PAYMENTDUEDATE 22/06/2026 |\n"
        "ADDRESSNAME Test Enterprise |\n"
        "CUSTOMERTYPE ENTERPRISE |\n"
        "ACCCURRENCYCODE Rs |\n"
        "CHARGES 0.00 |\n"
        "NEWBAL 0.00 |\n"
        "SLTSUBSCRIPTIONREF SB010018588 |\n"
        "SLTPRODUCTLABEL AD-MKS-NODE-AD-MKS-00031-DAB-0001 |\n"
        "SLTPRODLABELDET 0.00 | Data Access Bearer | Cop-NTU L3(basic) up to 512K | 56 | 59 | P | 01/05/2026 | 31/05/2026 | SAPROD | 0 |\n"
        "SLTPRODUCTLABEL E1100980 |\n"
        "SLTPRODLABELDET 0.00 | PremiumIPVPN | 512 kbps - Bronze | 56 | 59 | P | 01/05/2026 | 31/05/2026 | SAPROD | 0 |\n"
    )

    with tempfile.NamedTemporaryFile(suffix=".gmf", mode="w", delete=False, encoding="utf-8") as f:
        f.write(gmf_content)
        tmp_gmf = f.name

    try:
        data = parse_invoice_of_summary(tmp_gmf)
        assert len(data["charge_groups"]) == 1
        assert data["charge_groups"][0]["ref"] == "SB010018588"
        assert len(data["charge_groups"][0]["products"]) == 2

        renderer = InvoiceOfSummaryRenderer()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
            pdf_path = tmp_pdf.name

        try:
            renderer.render(data)
            renderer.save(pdf_path)

            doc = fitz.open(pdf_path)
            full_text = "\n".join(page.get_text() for page in doc)
            doc.close()

            assert "SB010018588" in full_text
            assert "AD-MKS-NODE-AD-MKS-00031-DAB-0001" in full_text
            assert "Data Access Bearer Cop-NTU L3(basic) up to 512K [Rental]" in full_text
            assert "E1100980" in full_text
            assert "PremiumIPVPN 512 kbps - Bronze [Rental]" in full_text
            # Exactly one Total Charges row under Charges in Detail
            assert full_text.count("Total Charges for the Period") == 2  # 1 in summary box, 1 in charges detail
        finally:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
    finally:
        if os.path.exists(tmp_gmf):
            os.remove(tmp_gmf)


def test_invoice_of_summary_no_full_page_vertical_line():
    """Verify that no vertical line is drawn across the full page (y=50 to 770)."""
    data = {
        "account_number": "1234567890",
        "invoice_number": "INV-001",
        "billing_date": "01/03/2026",
        "billing_period_start": "01/02/2026",
        "billing_period_end": "28/02/2026",
        "telephone_number": "0112345678",
        "currency_code": "Rs",
        "charge_groups": [],
        "total_charges": 100.0,
        "total_payments": 50.0,
        "balance_bf": 0.0,
        "payments_received": 50.0,
        "charges_period": 100.0,
        "total_payable": 50.0,
        "payment_due_date": "20/03/2026",
        "payments": [
            {"pay_type": "Physical", "date": "01/02/2026", "location": "Maradana", "amount": 50.0}
        ],
        "usage_sections": [
            {
                "label": "International Voice Usage",
                "phone": "0112345678",
                "subsections": [
                    {
                        "label": "International",
                        "headers": ["Date", "Time", "Dialled No.", "Duration", "Charge"],
                        "rows": [["01/02/2026", "10:00:00", "00123456", "00:01:00", "100.000"]],
                    }
                ],
            }
        ],
    }

    renderer = InvoiceOfSummaryRenderer()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
        pdf_path = tmp_pdf.name

    try:
        renderer.render(data)
        renderer.save(pdf_path)

        doc = fitz.open(pdf_path)
        found_divider = False
        for page in doc:
            for d in page.get_drawings():
                # Check lines
                for item in d.get("items", []):
                    if item[0] == "l":  # line
                        p1, p2 = item[1], item[2]
                        # If vertical line at x ~ 302
                        if abs(p1.x - 302) < 2 and abs(p2.x - 302) < 2:
                            length = abs(p1.y - p2.y)
                            found_divider = True
                            # Must NOT span across the whole page (e.g. > 500pt), but should exist beside payments
                            assert 20 < length < 200, f"Vertical line length was {length}pt, expected 20-200pt"
        doc.close()
        assert found_divider, "Vertical divider line beside payments was not found"
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)


def test_invoice_of_summary_vertical_line_covers_usage_without_payments():
    """Verify that vertical divider line is drawn when only usage charges exist (no payments)."""
    data = {
        "account_number": "1234567890",
        "invoice_number": "INV-001",
        "billing_date": "01/03/2026",
        "billing_period_start": "01/02/2026",
        "billing_period_end": "28/02/2026",
        "telephone_number": "0112345678",
        "currency_code": "Rs",
        "charge_groups": [],
        "total_charges": 100.0,
        "total_payments": 0.0,
        "balance_bf": 0.0,
        "payments_received": 0.0,
        "charges_period": 100.0,
        "total_payable": 100.0,
        "payment_due_date": "20/03/2026",
        "payments": [],
        "usage_sections": [
            {
                "label": "International Voice Usage",
                "phone": "0112345678",
                "subsections": [
                    {
                        "label": "International",
                        "headers": ["Date", "Time", "Dialled No.", "Duration", "Charge"],
                        "rows": [["01/02/2026", "10:00:00", "00123456", "00:01:00", "100.000"]],
                    }
                ],
            }
        ],
    }

    renderer = InvoiceOfSummaryRenderer()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
        pdf_path = tmp_pdf.name

    try:
        renderer.render(data)
        renderer.save(pdf_path)

        doc = fitz.open(pdf_path)
        found_divider = False
        for page in doc:
            for d in page.get_drawings():
                for item in d.get("items", []):
                    if item[0] == "l":
                        p1, p2 = item[1], item[2]
                        if abs(p1.x - 302) < 2 and abs(p2.x - 302) < 2:
                            found_divider = True
                            length = abs(p1.y - p2.y)
                            assert 20 < length < 200, f"Expected divider length 20-200pt, got {length}pt"
        doc.close()
        assert found_divider, "Vertical divider line beside usage was not found"
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)


def test_invoice_of_summary_no_vertical_line_when_no_post_tc_content():
    """Verify that no vertical divider line is drawn when there are no payments or usage."""
    data = {
        "account_number": "1234567890",
        "invoice_number": "INV-001",
        "billing_date": "01/03/2026",
        "billing_period_start": "01/02/2026",
        "billing_period_end": "28/02/2026",
        "telephone_number": "0112345678",
        "currency_code": "Rs",
        "charge_groups": [],
        "total_charges": 100.0,
        "total_payments": 0.0,
        "balance_bf": 0.0,
        "payments_received": 0.0,
        "charges_period": 100.0,
        "total_payable": 100.0,
        "payment_due_date": "20/03/2026",
        "payments": [],
        "usage_sections": [],
    }

    renderer = InvoiceOfSummaryRenderer()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
        pdf_path = tmp_pdf.name

    try:
        renderer.render(data)
        renderer.save(pdf_path)

        doc = fitz.open(pdf_path)
        found_divider = False
        for page in doc:
            for d in page.get_drawings():
                for item in d.get("items", []):
                    if item[0] == "l":
                        p1, p2 = item[1], item[2]
                        if abs(p1.x - 302) < 2 and abs(p2.x - 302) < 2:
                            found_divider = True
        doc.close()
        assert not found_divider, "Vertical divider line should not exist when there is no post-TC content"
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)


def test_invoice_of_summary_uniform_summary_font_size():
    """Verify that lines in Summary of Invoice (subtotals, discounts, taxes) use uniform 9pt font."""
    data = {
        "account_number": "1234567890",
        "invoice_number": "INV-001",
        "billing_date": "01/03/2026",
        "billing_period_start": "01/02/2026",
        "billing_period_end": "28/02/2026",
        "telephone_number": "0112345678",
        "currency_code": "Rs",
        "charge_groups": [],
        "total_charges": 100.0,
        "total_payments": 0.0,
        "balance_bf": 0.0,
        "payments_received": 0.0,
        "charges_period": 100.0,
        "total_payable": 100.0,
        "payment_due_date": "20/03/2026",
        "rental_subtotal": 26018.0,
        "discounts": [{"description": "FTTH SP Office Rev. Commitment2022", "amount": -89.60}],
        "taxes": [
            {"name": "VAT-18%", "amount": 5805.08},
            {"name": "Recovery in lieu of SSCL", "amount": 805.00},
            {"name": "Telecommunication Levy-15%", "amount": 4090.27},
            {"name": "CESS", "amount": 546.89}
        ],
        "tax_status": "Exclusive",
        "customer_vat_reg": "114062758 7000",
        "show_vat_lines": True,
    }

    renderer = InvoiceOfSummaryRenderer()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        pdf_path = f.name

    try:
        renderer.render(data)
        renderer.save(pdf_path)

        doc = fitz.open(pdf_path)
        page = doc[0]
        text_dict = page.get_text("dict")
        checked_spans = {}
        for block in text_dict["blocks"]:
            if "lines" in block:
                for line in block["lines"]:
                    for span in line["spans"]:
                        t = span["text"].strip()
                        for target in ["Subtotal Rental and Other Charges", "FTTH SP Office Rev. Commitment2022",
                                       "VAT-18%", "Recovery in lieu of SSCL", "CESS"]:
                            if target == t:
                                checked_spans[target] = round(span["size"], 1)
        doc.close()

        # All items must be font size 9.0 (no 7.0)
        assert len(checked_spans) == 5
        for target, size in checked_spans.items():
            assert size == 9.0, f"{target} has size {size}, expected 9.0"
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)


def test_invoice_of_summary_customervatref_all_zeros_omits_vat_details():
    """Verify 'Tax Invoice', SLT VAT reg, and Customer VAT reg are omitted when CUSTOMERVATREF is all zeros."""
    gmf_content = (
        _create_sample_gmf() +
        "CUSTOMERVATREF 000000000 0000 |\n"
        "INVOICINGCOVATREG 294001727 7000 |\n"
    )

    with tempfile.NamedTemporaryFile(suffix=".gmf", mode="w", delete=False, encoding="utf-8") as f:
        f.write(gmf_content)
        tmp_path = f.name

    try:
        data = parse_invoice_of_summary(tmp_path)
        assert data.get("show_vat_lines") is False
        assert data.get("customer_vat_reg") == "000000000 0000"

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
            assert "SLT VAT Registration Number" not in page1_text
            assert "Customer VAT Registration Number" not in page1_text
        finally:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_invoice_of_summary_customervatref_vatdl_omits_vat_details():
    """Verify 'Tax Invoice', SLT VAT reg, and Customer VAT reg are omitted when CUSTOMERVATREF starts with VATDL."""
    gmf_content = (
        _create_sample_gmf() +
        "CUSTOMERVATREF VATDL409054749 7000 |\n"
        "INVOICINGCOVATREG 294001727 7000 |\n"
    )

    with tempfile.NamedTemporaryFile(suffix=".gmf", mode="w", delete=False, encoding="utf-8") as f:
        f.write(gmf_content)
        tmp_path = f.name

    try:
        data = parse_invoice_of_summary(tmp_path)
        assert data.get("show_vat_lines") is False
        assert data.get("customer_vat_reg") == "VATDL409054749 7000"

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
            assert "SLT VAT Registration Number" not in page1_text
            assert "Customer VAT Registration Number" not in page1_text
        finally:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_invoice_of_summary_customervatref_valid_number_prints_vat_details():
    """Verify 'Tax Invoice', SLT VAT reg, and Customer VAT reg are printed when CUSTOMERVATREF has a valid number."""
    gmf_content = (
        _create_sample_gmf() +
        "CUSTOMERVATREF 1142181117000 |\n"
        "INVOICINGCOVATREG 294001727 7000 |\n"
    )

    with tempfile.NamedTemporaryFile(suffix=".gmf", mode="w", delete=False, encoding="utf-8") as f:
        f.write(gmf_content)
        tmp_path = f.name

    try:
        data = parse_invoice_of_summary(tmp_path)
        assert data.get("show_vat_lines") is True
        assert data.get("customer_vat_reg") == "1142181117000"

        renderer = InvoiceOfSummaryRenderer()
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
            assert "Customer VAT Registration Number: 1142181117000" in page1_text
        finally:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_invoice_of_summary_non_vat_renders_single_taxes_and_levies_line():
    """BPR06 / Sheet 19: For NON-VAT invoice, Taxes & Levies must be a single summary line,
    not itemized by individual TAXCODEs (e.g. VAT-18%, CESS)."""
    gmf_content = (
        "ACCOUNTNO 001040156X |\n"
        "BILLREF 001040156X-2729 |\n"
        "INVOICEACTUALDATE 03/06/2026 |\n"
        "INVOICESTART 01/05/2026 |\n"
        "INVOICEEND 31/05/2026 |\n"
        "PAYMENTDUEDATE 24/06/2026 |\n"
        "ADDRESSNAME HETTIGODA INDUSTRIES (PVT) LTD |\n"
        "CUSTOMERTYPE ENTERPRISE |\n"
        "ACCCURRENCYCODE Rs |\n"
        "ACCTAXSTATUS Exclusive |\n"
        "CUSTOMERVATREF 0000000000 |\n"
        "SLT_RENTAL_SUBTOTAL 49332.00 |\n"
        "SLTEVENTSSUBTOTAL 2164.20 |\n"
        "SLTDISCDETAIL 1314.00 | Discount Telephone Rental |\n"
        "SLTDISCDETAIL 23.50 | Discount Domestic Calls-FixedLine |\n"
        "INVTOTALTAX 13643.95 |\n"
        "CHARGES 63802.65 |\n"
        "NEWBAL 63802.20 |\n"
        "TSTARTSLTTAXCODE |\n"
        "SLTTAXCODE CESS | 0 | 0 | 546.89 | 0.00 |\n"
        "SLTTAXCODE Recovery in lieu of SSCL | 0 | 0 | 805.00 | 0.00 |\n"
        "SLTTAXCODE Telecommunication Levy-15% | 0 | 0 | 4090.27 | 0.00 |\n"
        "SLTTAXCODE VAT-18% | 0 | 0 | 8201.79 | 0.00 |\n"
        "TENDSLTTAXCODE |\n"
    )

    with tempfile.NamedTemporaryFile(suffix=".gmf", mode="w", delete=False, encoding="utf-8") as f:
        f.write(gmf_content)
        tmp_path = f.name

    try:
        data = parse_invoice_of_summary(tmp_path)
        assert data["inv_total_tax"] == 13643.95
        assert data["taxes_total"] == 13643.95
        assert data["show_vat_lines"] is False

        renderer = InvoiceOfSummaryRenderer()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
            pdf_path = tmp_pdf.name

        try:
            renderer.render(data)
            renderer.save(pdf_path)

            doc = fitz.open(pdf_path)
            full_text = "\n".join(page.get_text() for page in doc)
            doc.close()

            # Must have Taxes & Levies and the total tax amount
            assert "Taxes & Levies" in full_text
            assert "13,643.95" in full_text

            # Must NOT have itemized individual tax codes because it's NON-VAT
            assert "VAT-18%" not in full_text
            assert "Recovery in lieu of SSCL" not in full_text
            assert "Telecommunication Levy-15%" not in full_text
            assert "CESS" not in full_text
        finally:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_invoice_of_summary_vat_renders_itemized_tax_lines():
    """BPR05 / Sheet 18: For VAT invoice, Taxes & Levies must be itemized by TAXCODE."""
    gmf_content = (
        "ACCOUNTNO 0000028589 |\n"
        "BILLREF 0000028589-2737 |\n"
        "INVOICEACTUALDATE 03/06/2026 |\n"
        "INVOICESTART 01/05/2026 |\n"
        "INVOICEEND 31/05/2026 |\n"
        "PAYMENTDUEDATE 24/06/2026 |\n"
        "ADDRESSNAME ST. ANTHONY'S INDUSTRIES GROUP (PVT) LTD |\n"
        "CUSTOMERTYPE ENTERPRISE |\n"
        "ACCCURRENCYCODE Rs |\n"
        "ACCTAXSTATUS Exclusive |\n"
        "CUSTOMERVATREF 114062758 7000 |\n"
        "INVOICINGCOVATREG 294001727 7000 |\n"
        "SLT_RENTAL_SUBTOTAL 26018.00 |\n"
        "SLTEVENTSSUBTOTAL 879.90 |\n"
        "SLTDISCDETAIL 89.60 | FTTH SP Office Rev. Commitment2022 |\n"
        "INVTOTALTAX 11247.24 |\n"
        "CHARGES 38055.54 |\n"
        "NEWBAL 33055.33 |\n"
        "TSTARTSLTTAXCODE |\n"
        "SLTTAXCODE CESS | 0 | 0 | 546.89 | 0.00 |\n"
        "SLTTAXCODE Recovery in lieu of SSCL | 0 | 0 | 805.00 | 0.00 |\n"
        "SLTTAXCODE Telecommunication Levy-15% | 0 | 0 | 4090.27 | 0.00 |\n"
        "SLTTAXCODE VAT-18% | 0 | 0 | 5805.08 | 0.00 |\n"
        "TENDSLTTAXCODE |\n"
    )

    with tempfile.NamedTemporaryFile(suffix=".gmf", mode="w", delete=False, encoding="utf-8") as f:
        f.write(gmf_content)
        tmp_path = f.name

    try:
        data = parse_invoice_of_summary(tmp_path)
        assert data["show_vat_lines"] is True

        renderer = InvoiceOfSummaryRenderer()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
            pdf_path = tmp_pdf.name

        try:
            renderer.render(data)
            renderer.save(pdf_path)

            doc = fitz.open(pdf_path)
            full_text = "\n".join(page.get_text() for page in doc)
            doc.close()

            # Must have Tax Invoice and registration numbers
            assert "Tax Invoice" in full_text
            assert "SLT VAT Registration Number: 294001727 7000" in full_text
            assert "Customer VAT Registration Number: 114062758 7000" in full_text

            # Must have itemized individual tax codes because it's VAT
            assert "VAT-18%" in full_text
            assert "5,805.08" in full_text
            assert "Recovery in lieu of SSCL" in full_text
            assert "805.00" in full_text
            assert "Telecommunication Levy-15%" in full_text
            assert "4,090.27" in full_text
            assert "CESS" in full_text
            assert "546.89" in full_text
        finally:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)



