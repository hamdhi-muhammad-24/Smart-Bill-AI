import pytest
import os
import sys
import tempfile
import json

# Add project root and Models/SmartAI_Bill to sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
smartai_dir = os.path.join(root_dir, "Models", "SmartAI_Bill")
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
if smartai_dir not in sys.path:
    sys.path.insert(0, smartai_dir)

from Models.SmartAI_Bill.core.gmf_splitter import split_gmf_documents
from app.api.routers.billing import _calculate_upload_approved_counts
from app.db.models import GmfUpload


def create_sample_multi_template_gmf():
    """Creates a temporary multi-template GMF file with 2 vat_home docs and 2 nonvat_home docs."""
    content = """DOCSTART
DOCTYPE BILL |
BILLSTYLE 1 |
CUSTOMERTYPE Individual-Residential |
CUSTOMERVATREF 123456789V |
ACCTAXSTATUS 1 |
BSTARTBFSTATEMENT
01|12345678|John Doe|Address 1
DOCEND
DOCSTART
DOCTYPE BILL |
BILLSTYLE 1 |
CUSTOMERTYPE Individual-Residential |
CUSTOMERVATREF 987654321V |
ACCTAXSTATUS 1 |
BSTARTBFSTATEMENT
01|87654321|Jane Smith|Address 2
DOCEND
DOCSTART
DOCTYPE BILL |
BILLSTYLE 1 |
CUSTOMERTYPE Individual-Residential |
CUSTOMERVATREF |
ACCTAXSTATUS 0 |
BSTARTBFSTATEMENT
01|11223344|Alice Brown|Address 3
DOCEND
DOCSTART
DOCTYPE BILL |
BILLSTYLE 1 |
CUSTOMERTYPE Individual-Residential |
CUSTOMERVATREF |
ACCTAXSTATUS 0 |
BSTARTBFSTATEMENT
01|55667788|Bob White|Address 4
DOCEND
"""
    tmp = tempfile.NamedTemporaryFile("w", delete=False, suffix=".gmf", encoding="utf-8")
    tmp.write(content)
    tmp.close()
    return tmp.name


def test_split_gmf_documents_selective_filtering():
    gmf_path = create_sample_multi_template_gmf()
    try:
        # 1. Total docs without filter
        all_docs = split_gmf_documents(gmf_path)
        assert len(all_docs) == 4

        # 2. Filter for vat_home only (or whatever identify_template returns)
        from Models.SmartAI_Bill.core.template_identifier import identify_template
        first_ident = identify_template(all_docs[0])
        tid = first_ident.template_id

        if tid:
            filtered_docs = split_gmf_documents(gmf_path, approved_templates={tid})
            assert len(filtered_docs) >= 1

        # 3. Filter for unapproved dummy template
        none_docs = split_gmf_documents(gmf_path, approved_templates={"unapproved_dummy_template"})
        assert len(none_docs) == 0

    finally:
        if os.path.exists(gmf_path):
            os.remove(gmf_path)


def test_calculate_upload_approved_counts():
    # Case 1: Bulk GMF with vat_home (40) and nonvat_home (60)
    upload = GmfUpload(
        id=1,
        filename="cycle1_bulk.gmf",
        folder_type="Cycle_1",
        total_records_count=100,
        processed_records_count=0,
        template_breakdown=json.dumps({"vat_home": 40, "nonvat_home": 60})
    )

    # When only vat_home is approved:
    app_tot, app_rem, is_fully, *_ = _calculate_upload_approved_counts(upload, {"vat_home"})
    assert app_tot == 40
    assert app_rem == 40
    assert is_fully is False

    # After 10 records are processed:
    upload.processed_records_count = 10
    app_tot, app_rem, is_fully, *_ = _calculate_upload_approved_counts(upload, {"vat_home"})
    assert app_tot == 40
    assert app_rem == 30
    assert is_fully is False

    # After all 40 vat_home records are processed:
    upload.processed_records_count = 40
    app_tot, app_rem, is_fully, *_ = _calculate_upload_approved_counts(upload, {"vat_home"})
    assert app_tot == 40
    assert app_rem == 0
    assert is_fully is False

    # When both are approved:
    app_tot, app_rem, is_fully, *_ = _calculate_upload_approved_counts(upload, {"vat_home", "nonvat_home"})
    assert app_tot == 100
    assert app_rem == 60  # 100 - 40 already processed
    assert is_fully is True

    # Case 2: Single GMF file
    single_upload = GmfUpload(
        id=2,
        filename="single_invoice.gmf",
        folder_type="Cycle_1",
        total_records_count=1,
        processed_records_count=0,
        template_detected="vat_home"
    )

    app_tot, app_rem, is_fully, *_ = _calculate_upload_approved_counts(single_upload, {"vat_home"})
    assert app_tot == 1
    assert app_rem == 1
    assert is_fully is True

    app_tot, app_rem, is_fully, *_ = _calculate_upload_approved_counts(single_upload, {"nonvat_home"})
    assert app_tot == 0
    assert app_rem == 0
    assert is_fully is False


def test_count_documents_single_gmf():
    from Models.SmartAI_Bill.core.gmf_splitter import count_documents
    # Text GMF with header tags but no DOCSTART (single invoice)
    content = """DOCTYPE BILL |
BILLSTYLE 21 |
ACCOUNT_NO 12345 |
01|12345|Customer Name|Address
"""
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".gmf", encoding="utf-8") as tf:
        tf.write(content)
        tf_name = tf.name
    try:
        count = count_documents(tf_name)
        assert count == 1
    finally:
        if os.path.exists(tf_name):
            os.remove(tf_name)


def test_batch_limit_budget_allocation():
    # Simulate a batch with 15 single-record uploads
    uploads = [
        GmfUpload(
            id=i,
            filename=f"invoice_{i}.gmf",
            folder_type="Cycle_1",
            cycle_number=1,
            total_records_count=1,
            processed_records_count=0,
            template_detected="vat_home"
        )
        for i in range(1, 16)
    ]
    
    approved_templates = {"vat_home"}
    req_limit = 10

    valid_uploads_with_limits = []
    remaining_budget = req_limit
    allocated_total = 0

    for upload in uploads:
        app_tot, app_rem, *_ = _calculate_upload_approved_counts(upload, approved_templates)
        if app_rem <= 0:
            continue

        if remaining_budget is not None:
            if remaining_budget <= 0:
                break
            file_limit = min(app_rem, remaining_budget)
            remaining_budget -= file_limit
        else:
            file_limit = None

        allocated_total += (file_limit if file_limit is not None else app_rem)
        valid_uploads_with_limits.append((upload, file_limit))

    assert len(valid_uploads_with_limits) == 10
    assert allocated_total == 10
    assert all(lim == 1 for _, lim in valid_uploads_with_limits)

