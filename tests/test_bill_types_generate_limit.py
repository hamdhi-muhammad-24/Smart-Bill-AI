import os
import sys
import json
import pytest
import tempfile
from datetime import datetime, date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
smartai_dir = os.path.join(root_dir, "Models", "SmartAI_Bill")
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
if smartai_dir not in sys.path:
    sys.path.insert(0, smartai_dir)

from app.db.base import Base
from app.db.models import GmfUpload, GmfUploadStatus, BillingRun, RunStatus, InvoiceTemplate, TemplateApprovalStatus
from app.api.routers.billing import generate_batch_endpoint, GenerateBatchRequest, preview_invoice, serve_preview_pdf
from app.auth.schemas import UserOut
from app.billing.worker_queue import _update_billing_run
from processing.batch_processor import process_single_file


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database session for isolated testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed approved templates for all 11 bill types
    bill_types = [
        "usd_open_item", "nonvat_creditnote", "vat_creditnote",
        "invoice_of_summary", "summary_statement", "subscription_ref_grouping",
        "product_label_grouping", "vat_home", "vat_enterprise",
        "nonvat_enterprise", "nonvat_home"
    ]
    for idx, code in enumerate(bill_types, 1):
        session.add(InvoiceTemplate(
            id=idx,
            template_code=code,
            name=code.replace("_", " ").title(),
            approval_status=TemplateApprovalStatus.APPROVED,
            is_active=True
        ))
    session.commit()

    yield session
    session.close()


def test_process_single_file_strict_limit():
    """Verify that process_single_file with limit=10 on a 232-document GMF file generates exactly 10 PDFs."""
    sample_file = os.path.join(root_dir, "queue", "pending", "572331_1-1-02-1-LKR-101-1-BILL-RED_1.8")
    if not os.path.exists(sample_file):
        pytest.skip("Sample file 572331 not found on disk")

    with tempfile.TemporaryDirectory() as td:
        args = (sample_file, td, 1, False, None, 0, 10)
        results = process_single_file(args)

        generated_pdfs = [f for f in os.listdir(td) if f.lower().endswith(".pdf")]
        assert len(generated_pdfs) == 10, f"Expected exactly 10 PDFs, got {len(generated_pdfs)}"
        assert len(results) == 10, f"Expected exactly 10 processing results, got {len(results)}"


def test_billing_run_succeeded_cannot_exceed_total_accounts(db_session):
    """Verify that _update_billing_run strictly caps succeeded at total_accounts."""
    run = BillingRun(
        id=999,
        batch_name="Test Run Limit",
        period_start=date.today(),
        period_end=date.today(),
        status=RunStatus.RUNNING,
        total_accounts=10,
        succeeded=0,
        failed=0,
        started_at=datetime.now(),
        output_path="output/test",
    )
    db_session.add(run)
    db_session.commit()

    # Worker 1 generates 4 PDFs
    _update_billing_run(db_session, run_id=999, generated_count=4, template_counts={"vat_enterprise": 4})
    db_session.commit()
    r = db_session.query(BillingRun).filter(BillingRun.id == 999).first()
    assert r.succeeded == 4

    # Worker 2 generates 5 PDFs
    _update_billing_run(db_session, run_id=999, generated_count=5, template_counts={"nonvat_enterprise": 5})
    db_session.commit()
    r = db_session.query(BillingRun).filter(BillingRun.id == 999).first()
    assert r.succeeded == 9

    # Worker 3 attempts to add 10 PDFs (overshooting by 9)
    _update_billing_run(db_session, run_id=999, generated_count=10, template_counts={"vat_enterprise": 10})
    db_session.commit()
    r = db_session.query(BillingRun).filter(BillingRun.id == 999).first()

    # Succeeded MUST be capped at total_accounts (10)
    assert r.succeeded == 10, f"Expected succeeded to be capped at 10, got {r.succeeded}"
    assert r.status == RunStatus.DONE


def test_generate_batch_budget_allocation_and_run_limit(db_session, tmp_path, monkeypatch):
    """
    Verify generate_batch_endpoint with limit=10:
    - Sets BillingRun.total_accounts = 10
    - Allocates budget across multiple files without exceeding 10
    """
    admin_user = UserOut(id=1, email="admin@slt.lk", role="ADMIN", is_active=True, created_at=datetime.now())

    # Create 3 dummy files
    f1 = tmp_path / "file1.gmf"
    f2 = tmp_path / "file2.gmf"
    f3 = tmp_path / "file3.gmf"
    for f in (f1, f2, f3):
        f.write_text("DOCSTART\nDOCEND\n")

    u1 = GmfUpload(
        id=101, filename="file1.gmf", file_path=str(f1), folder_type="Cycle_1", cycle_number=1,
        total_records_count=4, processed_records_count=0, template_detected="vat_enterprise",
        status=GmfUploadStatus.APPROVED, template_breakdown=json.dumps({"vat_enterprise": 4})
    )
    u2 = GmfUpload(
        id=102, filename="file2.gmf", file_path=str(f2), folder_type="Cycle_1", cycle_number=1,
        total_records_count=5, processed_records_count=0, template_detected="nonvat_enterprise",
        status=GmfUploadStatus.APPROVED, template_breakdown=json.dumps({"nonvat_enterprise": 5})
    )
    u3 = GmfUpload(
        id=103, filename="file3.gmf", file_path=str(f3), folder_type="Cycle_1", cycle_number=1,
        total_records_count=20, processed_records_count=0, template_detected="vat_home",
        status=GmfUploadStatus.APPROVED, template_breakdown=json.dumps({"vat_home": 20})
    )
    db_session.add_all([u1, u2, u3])
    db_session.commit()

    # Monkeypatch queue_incoming_dir
    incoming_dir = tmp_path / "incoming"
    incoming_dir.mkdir()
    from app.core.config import settings
    monkeypatch.setattr(settings, "queue_incoming_dir", incoming_dir)

    req = GenerateBatchRequest(upload_ids=[101, 102, 103], limit=10)
    res = generate_batch_endpoint(req=req, db=db_session, _=admin_user)
    assert "queued for generation" in res["message"]

    run = db_session.query(BillingRun).order_by(BillingRun.id.desc()).first()
    assert run is not None
    # Verify run.total_accounts is capped at 10
    assert run.total_accounts == 10, f"Expected total_accounts=10, got {run.total_accounts}"

    # Verify sidecar meta.json limits
    meta1 = json.loads((incoming_dir / "file1.gmf.meta.json").read_text())
    meta2 = json.loads((incoming_dir / "file2.gmf.meta.json").read_text())
    meta3 = json.loads((incoming_dir / "file3.gmf.meta.json").read_text())

    assert meta1["limit"] == 4
    assert meta2["limit"] == 5
    assert meta3["limit"] == 1
    assert meta1["limit"] + meta2["limit"] + meta3["limit"] == 10


def test_consecutive_invoice_previews_do_not_delete_each_other(db_session, tmp_path, monkeypatch):
    """
    Verify that generating a preview for template 1 (e.g. VAT confirmation) and then
    generating a preview for template 2 (e.g. VAT enterprise) keeps BOTH preview PDFs
    in settings.output_dir / 'previews' and serve_preview_pdf serves both without 404.
    """
    admin_user = UserOut(id=1, email="admin@slt.lk", role="ADMIN", is_active=True, created_at=datetime.now())

    # Set up isolated output/previews directory
    previews_dir = tmp_path / "output" / "previews"
    previews_dir.mkdir(parents=True, exist_ok=True)
    from app.core.config import settings
    monkeypatch.setattr(settings, "output_dir", tmp_path / "output")

    # Real test files
    real_vat_conf = os.path.join(root_dir, "local_gmf_uploads", "Test_GMFs", "VAT Customer List_ Upt(002).xlsx")
    real_bill_file = os.path.join(smartai_dir, "data", "processed", "326150_1-19-02-1-LKR-101-00-BILL_1.7")

    u1 = GmfUpload(
        id=201, filename=os.path.basename(real_vat_conf), file_path=real_vat_conf, folder_type="Test_GMFs",
        total_records_count=1, processed_records_count=0, template_detected="vat_confirmation",
        status=GmfUploadStatus.PENDING_APPROVAL
    )

    u2 = GmfUpload(
        id=202, filename=os.path.basename(real_bill_file), file_path=real_bill_file, folder_type="Test_GMFs",
        total_records_count=232, processed_records_count=0, template_detected="nonvat_enterprise",
        status=GmfUploadStatus.PENDING_APPROVAL
    )

    db_session.add_all([u1, u2])
    db_session.commit()

    # Step 1: Generate preview for GMF 1
    res1 = preview_invoice(upload_id=201, db=db_session, _=admin_user)
    pdf1_filename = os.path.basename(res1["pdf_url"])
    file1_path = previews_dir / pdf1_filename
    assert file1_path.exists(), f"Preview 1 not found on disk: {file1_path}"

    # Step 2: Simulate approving Template 1
    u1.status = GmfUploadStatus.APPROVED
    db_session.commit()

    # Step 3: Generate preview for GMF 2 (another template)
    res2 = preview_invoice(upload_id=202, db=db_session, _=admin_user)
    pdf2_filename = os.path.basename(res2["pdf_url"])
    file2_path = previews_dir / pdf2_filename

    # Step 4: Verify BOTH preview PDFs exist on disk and serve_preview_pdf does not raise 404
    assert file1_path.exists(), f"Preview 1 was deleted: {file1_path}"
    assert file2_path.exists(), f"Preview 2 was deleted: {file2_path}"

    resp1 = serve_preview_pdf(filename=pdf1_filename, _=admin_user)
    assert resp1.status_code == 200

    resp2 = serve_preview_pdf(filename=pdf2_filename, _=admin_user)
    assert resp2.status_code == 200

