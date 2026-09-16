import sys

sys.path.insert(0, "Models/SmartAI_Bill")

from core.gmf_reader import GMFHeader
from core.template_identifier import identify_template_from_header


def make_header(**values):
    header = GMFHeader()
    for key, value in values.items():
        setattr(header, key, value)
    return header


def test_foreign_currency_bill_style_23_uses_usd_template():
    result = identify_template_from_header(
        make_header(
            doctype="BILL",
            billtype=1,
            billstyle=23,
            acc_currency_code="USD",
        )
    )

    assert result.template_id == "usd_open_item"
    assert result.is_supported is True


def test_bcr_bill_type_6_is_supported():
    result = identify_template_from_header(
        make_header(
            doctype="BCR",
            billtype=6,
            billstyle=1,
            acc_currency_code="RS",
            customer_type="Government Organization",
        )
    )

    assert result.template_id == "nonvat_enterprise"
    assert result.is_supported is True


def test_unsupported_bill_type_requires_manual_review():
    result = identify_template_from_header(
        make_header(
            doctype="BILL",
            billtype=2,
            billstyle=1,
            acc_currency_code="RS",
        )
    )

    assert result.template_id is None
    assert result.is_supported is False
    assert "Manual review needed" in result.warnings


def test_svat_customer_is_not_routed_to_ordinary_vat_template():
    result = identify_template_from_header(
        make_header(
            doctype="BILL",
            billtype=1,
            billstyle=1,
            customer_vat_ref="VAT123",
            customer_type="Government Organization",
            acc_currency_code="RS",
            raw_tags={"CUST_SVAT_NUMBER": "SVAT123"},
        )
    )

    assert result.template_id is None
    assert result.is_supported is False
    assert "SVAT template is not implemented; manual review needed" in result.warnings
