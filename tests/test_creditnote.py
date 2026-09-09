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

from templates.nonvat_creditnote.parser import parse_nonvat_creditnote
from templates.nonvat_creditnote.renderer import NonVATCreditNoteRenderer
from templates.vat_creditnote.parser import parse_vat_creditnote
from templates.vat_creditnote.renderer import VATCreditNoteRenderer


def test_nonvat_creditnote_strip_before_underscore_adjustment():
    """Verify that characters before the first underscore (including _) are removed in adjustment type."""
    gmf_path = os.path.join(
        os.path.dirname(__file__), "..", "local_gmf_uploads", "Test_GMFs",
        "377299_1-1-02-1-LKR-101-00-BILL_1.1"
    )
    if not os.path.exists(gmf_path):
        pytest.skip("Test GMF not present on disk")

    data = parse_nonvat_creditnote(gmf_path)

    # 1. Verify parsed adjustment descriptions do not contain prefix with underscore
    adj_descs = [a["description"] for a in data["adjustments"]]
    assert any("PSTN Rental rebates on faults" in d for d in adj_descs)
    assert not any("P_PSTN" in d for d in adj_descs)

    # 2. Render and verify PDF
    renderer = NonVATCreditNoteRenderer()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
        pdf_path = tmp_pdf.name

    try:
        renderer.render(data)
        renderer.save(pdf_path)

        doc = fitz.open(pdf_path)
        page1_text = doc[0].get_text()
        doc.close()

        assert "PSTN Rental rebates on faults Test" in page1_text
        assert "P_PSTN" not in page1_text
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)


def test_vat_creditnote_strip_before_underscore_adjustment():
    """Verify that characters before the first underscore (including _) are removed in vat creditnote adjustment."""
    gmf_path = os.path.join(
        os.path.dirname(__file__), "..", "local_gmf_uploads", "Test_GMFs",
        "377299_1-1-02-1-LKR-101-00-BILL_1.1"
    )
    if not os.path.exists(gmf_path):
        pytest.skip("Test GMF not present on disk")

    data = parse_vat_creditnote(gmf_path)

    adj_descs = [a["description"] for a in data["adjustments"]]
    assert any("PSTN Rental rebates on faults" in d for d in adj_descs)
    assert not any("P_PSTN" in d for d in adj_descs)
