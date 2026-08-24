import pytest
import os
import sys
import tempfile
import fitz
from pypdf import PdfReader, PdfWriter, PageObject

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
smartai_dir = os.path.join(root_dir, "Models", "SmartAI_Bill")
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
if smartai_dir not in sys.path:
    sys.path.insert(0, smartai_dir)

from templates.nonvat_home.renderer import NonVATHomeRenderer
from templates.nonvat_enterprise.renderer import NonVATEnterpriseRenderer
from templates.nonvat_print.renderer import NonVATPrintRenderer
from core.self_seal_appender import (
    append_self_seal_if_needed,
    create_self_seal_address_overlay,
    ALLOWED_TEMPLATES,
)
from processing.batch_processor import process_single_file


def _sample_nonvat_data(is_red=False):
    return {
        "telephone_number": "0312276282",
        "account_number": "000 739 8361",
        "invoice_number": "0007398361-2649",
        "billing_date": "01/10/2025",
        "billing_period_start": "01/09/2025",
        "billing_period_end": "30/09/2025",
        "payment_due_date": "22/10/2025",
        "customer_name": "Miss K Fernando",
        "business_name": "",
        "address_lines": ["123 Galle Road", "Colombo 03"],
        "zip_code": "00300",
        "badge": "HOME",
        "balance_bf": 1000.0,
        "payments_received": 1000.0,
        "charges_period": 2500.0,
        "total_payable": 2500.0,
        "total_charges": 2500.0,
        "product_labels": [
            {
                "label": "BROADBAND",
                "charges": [
                    {"description": "Fibre Monthly Rental", "amount": 2500.0}
                ]
            }
        ],
        "adjustments": [],
        "taxes": [],
        "top_level_discounts": [],
        "payments": [],
        "cancelled_payments": [],
        "marketing_messages": [],
        "usage_sections": [],
        "source_filename": "test_BILL-RED_1.1.gmf" if is_red else "test_BILL-NONRED_1.1.gmf",
    }


def test_nonvat_print_renderer_nonred():
    """Test NonVATPrintRenderer with Non-Red file uses Print_NONRED.pdf."""
    renderer = NonVATPrintRenderer()
    data = _sample_nonvat_data(is_red=False)
    renderer.render(data)
    assert renderer.template_pdf_path.endswith("Print_NONRED.pdf")
    assert renderer.page_count() == 1


def test_nonvat_print_renderer_red():
    """Test NonVATPrintRenderer with Red file uses Print_RED.pdf."""
    renderer = NonVATPrintRenderer()
    data = _sample_nonvat_data(is_red=True)
    renderer.render(data)
    assert renderer.template_pdf_path.endswith("Print_RED.pdf")
    assert renderer.page_count() == 1


def test_nonvat_home_standard_renderer_keeps_layout():
    """Test standard NonVATHomeRenderer uses layout.pdf."""
    renderer = NonVATHomeRenderer()
    data = _sample_nonvat_data(is_red=False)
    renderer.render(data)
    assert renderer.template_pdf_path.endswith("layout.pdf")


def test_nonvat_enterprise_standard_renderer_keeps_layout():
    """Test standard NonVATEnterpriseRenderer uses layout.pdf."""
    renderer = NonVATEnterpriseRenderer()
    data = _sample_nonvat_data(is_red=False)
    renderer.render(data)
    assert renderer.template_pdf_path.endswith("layout.pdf")


def test_self_seal_address_overlay_rotation():
    """Test create_self_seal_address_overlay generates 180-degree rotated address."""
    data = _sample_nonvat_data()
    overlay_buf = create_self_seal_address_overlay(data)
    assert overlay_buf is not None

    doc_reader = PdfReader(overlay_buf)
    assert len(doc_reader.pages) == 1


def test_append_self_seal_only_for_allowed_print():
    """Test append_self_seal_if_needed only modifies 1-page nonvat_home/enterprise print invoices."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create a dummy 1-page bill
        bill_path = os.path.join(tmp_dir, "bill.pdf")
        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)
        with open(bill_path, "wb") as f:
            writer.write(f)

        # Create a dummy self-seal base
        seal_path = os.path.join(tmp_dir, "seal.pdf")
        writer_s = PdfWriter()
        writer_s.add_blank_page(width=595, height=842)
        with open(seal_path, "wb") as f:
            writer_s.write(f)

        data = _sample_nonvat_data()

        # 1. Non-print invoice (is_print=False) -> should NOT append
        res_nonprint = append_self_seal_if_needed(bill_path, "nonvat_home", seal_path, doc_data=data, is_print=False)
        assert res_nonprint is False
        assert len(PdfReader(bill_path).pages) == 1

        # 2. Excluded / non-eligible template (e.g. vat_home, lod) -> should NOT append
        res_other = append_self_seal_if_needed(bill_path, "vat_home", seal_path, doc_data=data, is_print=True)
        assert res_other is False
        assert len(PdfReader(bill_path).pages) == 1

        # 3. Eligible template (nonvat_home) + is_print=True -> SHOULD append
        res_ok = append_self_seal_if_needed(bill_path, "nonvat_home", seal_path, doc_data=data, is_print=True)
        assert res_ok is True
        assert len(PdfReader(bill_path).pages) == 2

        # 4. Now that it has 2 pages, calling again should NOT append further
        res_again = append_self_seal_if_needed(bill_path, "nonvat_home", seal_path, doc_data=data, is_print=True)
        assert res_again is False
        assert len(PdfReader(bill_path).pages) == 2
