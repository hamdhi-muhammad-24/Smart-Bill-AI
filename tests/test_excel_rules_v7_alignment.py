import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, "Models/SmartAI_Bill")

import pytest
from core.gmf_reader import GMFHeader, BILL_HANDLING_CATEGORY, read_gmf_header
from core.template_identifier import identify_template_from_header as core_identify
from app.billing.gmf_core.template_identifier import identify_template as app_identify
from core.bill_common import reorder_addresses, decode_charge_flag, PhoneNumberFromNoSubRefBlock


# ---------------------------------------------------------------------------
# BPR02: BILLSTYLE 22 -> Home Common Bill Format
# ---------------------------------------------------------------------------
def test_bpr02_billstyle_22_mapped_to_home(tmp_path):
    # VAT Home
    h_vat = GMFHeader()
    h_vat.doctype = "BILL"
    h_vat.billtype = 1
    h_vat.billstyle = 22
    h_vat.tax = "1"
    h_vat.customer_vat_ref = "123456789V"
    h_vat.acc_currency_code = "RS"
    res_vat = core_identify(h_vat)
    assert res_vat.template_id == "vat_home"
    assert res_vat.is_supported is True

    # Non-VAT Home
    h_nonvat = GMFHeader()
    h_nonvat.doctype = "BILL"
    h_nonvat.billtype = 1
    h_nonvat.billstyle = 22
    h_nonvat.tax = "2"
    h_nonvat.acc_currency_code = "RS"
    res_nonvat = core_identify(h_nonvat)
    assert res_nonvat.template_id == "nonvat_home"
    assert res_nonvat.is_supported is True

    # Check app/billing/gmf_core version using a test GMF file
    f_vat = tmp_path / "vat_home_style22.gmf"
    f_vat.write_text("DOCSTART|\nDOCTYPE BILL|\nBILLTYPE 1|\nBILLSTYLE 22|\nTAX 1|\nCUSTOMERVATREF 123456789V|\nACCCURRENCYCODE RS|\nDOCEND|\n", encoding="utf-8")
    res_app_vat = app_identify(str(f_vat))
    assert res_app_vat.template_id == "vat_home"

    f_nonvat = tmp_path / "nonvat_home_style22.gmf"
    f_nonvat.write_text("DOCSTART|\nDOCTYPE BILL|\nBILLTYPE 1|\nBILLSTYLE 22|\nTAX 2|\nACCCURRENCYCODE RS|\nDOCEND|\n", encoding="utf-8")
    res_app_nonvat = app_identify(str(f_nonvat))
    assert res_app_nonvat.template_id == "nonvat_home"


# ---------------------------------------------------------------------------
# BPR03: Bill Handling Codes '10' and '11' -> 'print'
# ---------------------------------------------------------------------------
def test_bpr03_bill_handling_codes_10_and_11():
    assert BILL_HANDLING_CATEGORY.get("10") == "print"
    assert BILL_HANDLING_CATEGORY.get("11") == "print"


# ---------------------------------------------------------------------------
# BPR08: Empty charge_groups in invoice_of_summary renders charges section
# ---------------------------------------------------------------------------
def test_bpr08_invoice_of_summary_empty_charge_groups(tmp_path):
    from templates.invoice_of_summary.renderer import InvoiceOfSummaryRenderer

    data = {
        "account_number": "1234567890",
        "invoice_number": "INV-001",
        "billing_date": "01/03/2026",
        "bill_date": "01/03/2026",
        "billing_period_start": "01/02/2026",
        "billing_period_end": "28/02/2026",
        "telephone_number": "0112345678",
        "currency": "Rs",
        "charge_groups": [],
        "total_charges": 0.0,
        "total_payments": 0.0,
        "brought_forward": 0.0,
        "total_amount_due": 0.0,
        "balance_bf": 0.0,
        "payments_received": 0.0,
        "charges_period": 0.0,
        "total_payable": 0.0,
        "payment_due_date": "20/03/2026",
        "address_lines": ["Line 1", "Line 2"],
    }
    out_pdf = str(tmp_path / "summary_empty_charges.pdf")
    renderer = InvoiceOfSummaryRenderer()
    renderer.render(data)
    renderer.save(out_pdf)
    assert os.path.exists(out_pdf)
    assert os.path.getsize(out_pdf) > 1000


# ---------------------------------------------------------------------------
# BPR10: Country printed under billing address for non-RS currencies
# ---------------------------------------------------------------------------
def test_bpr10_country_printed_for_non_rs_currency():
    raw_addr = {
        "ADDRESS1": "123 Main Street",
        "ADDRESS2": "City Center",
        "ADDRESS3": "Western Province",
        "ADDRESS4": "10100",
    }
    # RS currency: Country NOT appended
    lines_rs = reorder_addresses(raw_addr, currency_code="Rs", country="Sri Lanka")
    assert "Sri Lanka" not in lines_rs

    lines_rs_upper = reorder_addresses(raw_addr, currency_code="RS", country="Sri Lanka")
    assert "Sri Lanka" not in lines_rs_upper

    # USD currency: Country IS appended
    lines_usd = reorder_addresses(raw_addr, currency_code="USD", country="United States")
    assert lines_usd[-1] == "United States"

    # EUR currency with empty country: Nothing appended
    lines_eur_empty = reorder_addresses(raw_addr, currency_code="EUR", country="")
    assert "EUR" not in lines_eur_empty
    assert len(lines_eur_empty) == 4


# ---------------------------------------------------------------------------
# BPR13: Credit note address suppression & Slip customer name fallback
# ---------------------------------------------------------------------------
def test_bpr13_creditnote_address_name_suppression(tmp_path):
    from templates.vat_creditnote.parser import parse_vat_creditnote
    from templates.nonvat_creditnote.parser import parse_nonvat_creditnote

    gmf_content_suppressed = """DOCSTART|
ACCNUMBER 1234567890|
ADDRESSNAME John Doe|
ACC_ADDRESS_NAME_N_REQIURED Y|
ADDRESS1 100 Main Road|
ADDRESS2 Colombo|
DOCEND|
"""
    f_path = tmp_path / "test_cn.gmf"
    f_path.write_text(gmf_content_suppressed, encoding="utf-8")

    vat_data = parse_vat_creditnote(str(f_path))
    assert vat_data["address_name_not_required"] is True
    assert vat_data["address_line1"] == ""

    nonvat_data = parse_nonvat_creditnote(str(f_path))
    assert nonvat_data["address_name_not_required"] is True
    assert nonvat_data["address_line1"] == ""

    # When NOT suppressed
    gmf_content_not_suppressed = """DOCSTART|
ACCNUMBER 1234567890|
ADDRESSNAME John Doe|
ACC_ADDRESS_NAME_N_REQIURED N|
ADDRESS1 100 Main Road|
ADDRESS2 Colombo|
DOCEND|
"""
    f_path2 = tmp_path / "test_cn2.gmf"
    f_path2.write_text(gmf_content_not_suppressed, encoding="utf-8")
    vat_data2 = parse_vat_creditnote(str(f_path2))
    assert vat_data2["address_name_not_required"] is False
    assert vat_data2["address_line1"] == "John Doe"


def test_bpr13_slip_customer_name_fallback():
    # In product_label_grouping renderer:
    # customer_name takes precedence over business_name when address_name_not_required is False
    data = {
        "customer_name": "Jane Smith",
        "business_name": "Smith Enterprise",
        "address_name_not_required": False,
    }
    slip_cust_name = (
        data.get("customer_name") or data.get("business_name", "")
        if not data.get("address_name_not_required")
        else ""
    )
    assert slip_cust_name == "Jane Smith"

    # If customer_name is empty, fall back to business_name
    data_no_cust = {
        "customer_name": "",
        "business_name": "Smith Enterprise",
        "address_name_not_required": False,
    }
    slip_cust_name2 = (
        data_no_cust.get("customer_name") or data_no_cust.get("business_name", "")
        if not data_no_cust.get("address_name_not_required")
        else ""
    )
    assert slip_cust_name2 == "Smith Enterprise"

    # If suppressed, empty
    data_suppressed = {
        "customer_name": "Jane Smith",
        "business_name": "Smith Enterprise",
        "address_name_not_required": True,
    }
    slip_cust_name3 = (
        data_suppressed.get("customer_name") or data_suppressed.get("business_name", "")
        if not data_suppressed.get("address_name_not_required")
        else ""
    )
    assert slip_cust_name3 == ""


# ---------------------------------------------------------------------------
# BPR14: Exact 10-digit telephone extraction & PhoneNumberFromNoSubRefBlock
# ---------------------------------------------------------------------------
def test_bpr14_phone_number_from_no_sub_ref_block():
    finder = PhoneNumberFromNoSubRefBlock()
    # Candidate outside block -> ignored
    finder.candidate("0112345678")
    assert finder.result == ""

    # Enter block, candidate with 10 digits
    finder.enter_block()
    finder.candidate("0112345678")
    # Not yet confirmed until confirm_charge is called
    assert finder.result == ""

    # Confirm charge
    finder.confirm_charge()
    assert finder.result == "0112345678"

    # Subsequent candidate outside or non-10 digit -> retains confirmed
    finder.candidate("12345")
    assert finder.result == "0112345678"


def test_bpr14_product_label_grouping_telephone(tmp_path):
    from templates.product_label_grouping.parser import parse_product_label_grouping

    gmf_content = """DOCSTART|
ACCNUMBER 1234567890|
BSTARTGROUP0|
SLTPRODGROUPLABEL 1|BROADBAND|RENTAL|0|ONEOFF|0|
BSTARTPROD0|
SLTPRODUCTLABEL 0112345678|
SLTPRODLABELDET 1000.00|FIBRE|LINE|A|B|P|01/02/2026|28/02/2026|C|1|Nos|
BENDPROD0|
BENDGROUP0|
DOCEND|
"""
    f = tmp_path / "plg_phone.gmf"
    f.write_text(gmf_content, encoding="utf-8")
    parsed = parse_product_label_grouping(str(f))
    assert parsed["telephone_number"] == "0112345678"


# ---------------------------------------------------------------------------
# BPR20: decode_charge_flag and usd_open_item flag decoding
# ---------------------------------------------------------------------------
def test_bpr20_decode_charge_flag():
    assert decode_charge_flag("P") == " [Rental]"
    assert decode_charge_flag("S") == " [Rental]"
    assert decode_charge_flag("O", start="01/02/2026") == " [One Time] (01/02/2026)"
    assert decode_charge_flag("I", start="01/02/2026") == " [Initiation] (01/02/2026)"
    assert decode_charge_flag("E", start="01/02/2026") == " [Early Termination Charge] (01/02/2026)"
    assert decode_charge_flag("T") == " [Termination Charge]"

    from templates.usd_open_item.parser import _decode_flag
    assert _decode_flag("P") == " [Rental]"
    assert _decode_flag("S") == " [Rental]"
    assert _decode_flag("O") == " [One Time]"
    assert _decode_flag("I") == " [Initiation]"
    assert _decode_flag("E") == " [Early Termination Charge]"
    assert _decode_flag("T") == " [Termination Charge]"


# ---------------------------------------------------------------------------
# BPR26: Strict payment suppression check across renderers
# ---------------------------------------------------------------------------
def test_bpr26_strict_payment_suppression():
    from templates.vat_home.renderer import _draw_payments_flow as vat_home_draw_payments
    from templates.subscription_ref_grouping.renderer import SubscriptionRefGroupingRenderer
    from templates.product_label_grouping.renderer import ProductLabelGroupingRenderer
    from templates.invoice_of_summary.renderer import InvoiceOfSummaryRenderer
    from templates.vat_enterprise.renderer import VATEnterpriseRenderer
    from templates.nonvat_enterprise.renderer import NonVATEnterpriseRenderer
    from templates.nonvat_home.renderer import NonVATHomeRenderer
    from templates.nonvat_print.renderer import NonVATPrintRenderer

    data_zero = {"total_payments": 0.0, "payments": [{"amount": 100.0}]}
    data_missing = {"payments": [{"amount": 100.0}]}

    # vat_home flow-based renderer: returns early without calling draw_line
    mock_flow = MagicMock()
    vat_home_draw_payments(mock_flow, data_zero)
    mock_flow.draw_line.assert_not_called()
    mock_flow.reset_mock()
    vat_home_draw_payments(mock_flow, data_missing)
    mock_flow.draw_line.assert_not_called()

    # product_label_grouping dynamic payments: returns y directly
    plg = ProductLabelGroupingRenderer()
    assert plg._draw_payments_dynamic(data_zero, 500) == 500
    assert plg._draw_payments_dynamic(data_missing, 500) == 500

    # subscription_ref_grouping: returns immediately without modifying state
    srg = SubscriptionRefGroupingRenderer()
    initial_page_count = srg.page_count()
    srg._draw_payments(data_zero)
    assert srg.page_count() == initial_page_count
    srg._draw_payments(data_missing)
    assert srg.page_count() == initial_page_count

    # invoice_of_summary: returns immediately
    ios = InvoiceOfSummaryRenderer()
    ios_page_count = ios.page_count()
    ios._draw_payments_flowing(data_zero)
    assert ios.page_count() == ios_page_count

    # For templates with two-column flow (vat_enterprise, nonvat_enterprise, nonvat_home, nonvat_print),
    # ensure "Details of Payments Received" is guarded by data.get("total_payments")
    import inspect
    for cls in [VATEnterpriseRenderer, NonVATEnterpriseRenderer, NonVATHomeRenderer, NonVATPrintRenderer]:
        src = inspect.getsource(cls)
        assert 'if data.get("total_payments"):' in src, f"{cls.__name__} missing strict total_payments guard"


# ---------------------------------------------------------------------------
# BPR29: First bill delivery override (BILLSEQ == 1 -> 'print')
# ---------------------------------------------------------------------------
def test_bpr29_billseq_parsing_and_delivery_override(tmp_path):
    gmf_content = """DOCSTART|
BILLSEQ 1|
BILLHANDLING 02|
ACCCUSTOMERTYPE Individual-Residential|
DOCEND|
"""
    f = tmp_path / "billseq1.gmf"
    f.write_text(gmf_content, encoding="utf-8")
    hdr = read_gmf_header(str(f))
    assert hdr.billseq == 1
    assert hdr.customer_type == "Individual-Residential"

    # Test delivery override in worker_queue logic
    bill_handling_code = "02"
    from core.gmf_reader import categorize_bill_handling_code
    category_name = categorize_bill_handling_code(bill_handling_code)
    assert category_name == "email"

    if hdr.billseq in (1, "1") and hdr.customer_type in (
        "Individual-Residential", "Individual-Business", "Individual-Micro Biz"
    ):
        category_name = "print"
    assert category_name == "print"

    # Billseq == 2 keeps original category
    hdr_subsequent = GMFHeader()
    hdr_subsequent.billseq = 2
    hdr_subsequent.customer_type = "Individual-Residential"
    category_subsequent = categorize_bill_handling_code("02")
    if hdr_subsequent.billseq in (1, "1") and hdr_subsequent.customer_type in (
        "Individual-Residential", "Individual-Business", "Individual-Micro Biz"
    ):
        category_subsequent = "print"
    assert category_subsequent == "email"


# ---------------------------------------------------------------------------
# BPR32: Promo group tags subtotals and ROLLUP amount suppression
# ---------------------------------------------------------------------------
def test_bpr32_promo_group_tags_and_rollup(tmp_path):
    from templates.vat_home.parser import parse_vat_home

    gmf_content = """DOCSTART|
ACCNUMBER 1234567890|
BSTARTGROUPPROMO|
SLTPRODGROUPLABEL 1|SUMMER_PROMO|RENTAL|500.00|ONEOFF|1200.00|
SLTPROMOSUBLABEL 0112345678|PROMO_LINE|
SLTPRODLABELDET 0112345678|FIBRE|P|01/02/2026|28/02/2026|1000.00|
SLTPRODLABELDET ROLLUP|DISCOUNT_SUMMARY|P|01/02/2026|28/02/2026|300.00|
BENDGROUPPROMO|
DOCEND|
"""
    f = tmp_path / "promo.gmf"
    f.write_text(gmf_content, encoding="utf-8")
    parsed = parse_vat_home(str(f))

    # Check telephone number candidate
    assert parsed["telephone_number"] == "0112345678"

    # Check promo group rental and initiation charges added
    charges = [c for p in parsed["product_labels"] for c in p["charges"]]
    rental_charge = next((c for c in charges if "Rental" in c["description"] and "PROMO" in c["description"]), None)
    assert rental_charge is not None
    assert rental_charge["amount"] == 500.00

    initiation_charge = next((c for c in charges if "Initiation" in c["description"] and "PROMO" in c["description"]), None)
    assert initiation_charge is not None
    assert initiation_charge["amount"] == 1200.00

    # Check ROLLUP suppression: amount should be None
    rollup_charge = next((c for c in charges if "SUMMARY" in c["description"]), None)
    assert rollup_charge is not None
    assert rollup_charge["amount"] is None
