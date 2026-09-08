"""Tests for extra page fixes on 0003858340_NONVAT_HOME and 0008813038_ProductLevel."""
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

from templates.nonvat_home.parser import parse_nonvat_home
from templates.nonvat_home.renderer import NonVATHomeRenderer
from templates.product_label_grouping.parser import parse_product_label_grouping
from templates.product_label_grouping.renderer import ProductLabelGroupingRenderer


def test_0003858340_nonvat_home_renders_2_pages_not_3():
    """Verify 0003858340 (519734) renders in exactly 2 pages with no orphan header or 1-line page."""
    gmf_path = os.path.join(
        root_dir, "local_gmf_uploads", "Processed", "Cycle_1",
        "519734_1-1-23-1-LKR-101-1-BILL-NONRED_1.7"
    )
    if not os.path.exists(gmf_path):
        pytest.skip(f"GMF file not found: {gmf_path}")

    data = parse_nonvat_home(gmf_path)
    renderer = NonVATHomeRenderer()
    renderer.render(data)

    assert renderer.page_count() == 2, f"Expected 2 pages, got {renderer.page_count()}"

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        pdf_path = tmp.name

    try:
        renderer.save(pdf_path)
        doc = fitz.open(pdf_path)
        assert len(doc) == 2

        p1_text = doc[0].get_text()
        p2_text = doc[1].get_text()
        doc.close()

        # Page 1 must have Details of Payments Received AND the Additional Channels row
        assert "Details of Payments Received" in p1_text
        assert "Detailed Usage Charges for Additional Channels 0112951818" in p1_text
        assert "Cinema Talkies" in p1_text
        assert "1  of  2" in p1_text

        # Page 2 must have totals and subsequent usage sections (Extra GB, Voice Usage)
        assert "Total for 0112951818" in p2_text
        assert "Detailed Usage Charges for Extra GB 94112951818" in p2_text
        assert "Total Usage Charges for Extra GB" in p2_text
        assert "Detailed Usage Charges for P_Domestic Voice Usage" in p2_text
        assert "2  of  2" in p2_text
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)


def test_0008813038_product_level_renders_1_page_not_2():
    """Verify 0008813038 (520174) renders in exactly 1 page when usage fits on Page 1."""
    gmf_path = os.path.join(
        root_dir, "local_gmf_uploads", "Processed", "Cycle_1",
        "520174_1-19-24-1-LKR-101-1-BILL-NONRED_1.1"
    )
    if not os.path.exists(gmf_path):
        pytest.skip(f"GMF file not found: {gmf_path}")

    data = parse_product_label_grouping(gmf_path)
    renderer = ProductLabelGroupingRenderer()
    renderer.render(data)

    assert renderer.page_count() == 1, f"Expected 1 page, got {renderer.page_count()}"

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        pdf_path = tmp.name

    try:
        renderer.save(pdf_path)
        doc = fitz.open(pdf_path)
        assert len(doc) == 1

        p1_text = doc[0].get_text()
        doc.close()

        # Page 1 must contain charges, payments, and detailed usage
        assert "Total Charges for the Period" in p1_text
        assert "Details of Payments Received" in p1_text
        assert "Detailed Usage Charges for Extra GB 94412232116" in p1_text
        assert "Total Usage Charges for Extra GB" in p1_text
        assert "1  of  1" in p1_text
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)


def test_product_level_overflows_to_page_2_when_usage_is_large():
    """Verify product_label_grouping creates Page 2 when usage is too large to fit on Page 1."""
    gmf_path = os.path.join(
        root_dir, "local_gmf_uploads", "Processed", "Cycle_1",
        "520174_1-19-24-1-LKR-101-1-BILL-NONRED_1.1"
    )
    if not os.path.exists(gmf_path):
        pytest.skip(f"GMF file not found: {gmf_path}")

    data = parse_product_label_grouping(gmf_path)
    # Add many rows to force overflow
    big_rows = [
        [f"23/09/2025 19:{i:02d}:00", "1GB", "", "100.000"]
        for i in range(40)
    ]
    data["usage_sections"][0]["subsections"][0]["rows"] = big_rows

    renderer = ProductLabelGroupingRenderer()
    renderer.render(data)

    assert renderer.page_count() >= 2, f"Expected >=2 pages for large usage, got {renderer.page_count()}"


def test_520205_nonvat_home_still_renders_2_pages():
    """Verify existing multi-page nonvat home bill (520205) continues to render in 2 pages."""
    gmf_path = os.path.join(
        root_dir, "local_gmf_uploads", "Test_GMFs",
        "520205_1-1-01-1-LKR-101-1-BILL-NONRED_1.4"
    )
    if not os.path.exists(gmf_path):
        pytest.skip(f"GMF file not found: {gmf_path}")

    data = parse_nonvat_home(gmf_path)
    renderer = NonVATHomeRenderer()
    renderer.render(data)

    assert renderer.page_count() == 2, f"Expected 2 pages, got {renderer.page_count()}"
