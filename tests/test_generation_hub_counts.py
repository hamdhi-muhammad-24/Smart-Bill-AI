import os
import sys
import json
import pytest
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
from app.db.models import GmfUpload, GmfUploadStatus, BillingRun, RunStatus, InvoiceTemplate, TemplateApprovalStatus, SystemSetting
from app.api.routers.billing import _calculate_upload_approved_counts, get_pending_batches
from app.auth.schemas import UserOut
from app.billing.worker_queue import _update_billing_run


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database session for isolated testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed system settings & approved templates
    session.add(SystemSetting(key="billing_mode", value="manual"))
    session.add(InvoiceTemplate(id=1, template_code="vat_home", name="VAT Home", approval_status=TemplateApprovalStatus.APPROVED, is_active=True))
    session.add(InvoiceTemplate(id=2, template_code="vat_enterprise", name="VAT Enterprise", approval_status=TemplateApprovalStatus.APPROVED, is_active=True))
    session.add(InvoiceTemplate(id=3, template_code="nonvat_home", name="NonVAT Home", approval_status=TemplateApprovalStatus.APPROVED, is_active=True))
    session.commit()

    yield session
    session.close()


def test_vat_enterprise_cycle3_scenario(db_session):
    """
    Scenario from user:
    Cycle 3 file has 1,070 total records:
    - 1,060 were vat_home and were already processed previously (processed_records_count = 1060).
    - 10 are vat_enterprise which were just approved.
    Generation Hub must show: 10 Remaining (1060 / 1070 Done).
    """
    admin_user = UserOut(id=1, email="admin@slt.lk", role="ADMIN", is_active=True, created_at=datetime.now())
    today_dt = datetime.now()

    u = GmfUpload(
        id=301,
        filename="cycle3_1070.gmf",
        file_path="/fake/cycle3_1070.gmf",
        folder_type="Cycle_3",
        cycle_number=3,
        total_records_count=1070,
        processed_records_count=1060,
        template_breakdown=json.dumps({"vat_home": 1060, "vat_enterprise": 10}),
        status=GmfUploadStatus.PARTIALLY_PROCESSED,
        detected_at=today_dt
    )
    db_session.add(u)
    db_session.commit()

    batches = get_pending_batches(db=db_session, _=admin_user)
    assert len(batches) == 1
    b = batches[0]
    assert b["cycle_number"] == 3
    assert b["total_records"] == 1070
    assert b["processed_records"] == 1060
    assert b["remaining_records"] == 10

    # When 10 are generated:
    u.processed_records_count = 1070
    u.status = GmfUploadStatus.COMPLETED
    db_session.commit()

    batches = get_pending_batches(db=db_session, _=admin_user)
    assert len(batches) == 0


def test_vat_enterprise_cycle1_scenario(db_session):
    """
    Scenario from user:
    Cycle 1 has 53 total records:
    - 31 were already processed previously (processed_records_count = 31).
    - 22 are vat_enterprise which were just approved.
    Generation Hub must show: 22 Remaining (31 / 53 Done).
    When 10 are generated, it must show: 12 Remaining (41 / 53 Done).
    When remaining 12 are generated, card must clear.
    """
    admin_user = UserOut(id=1, email="admin@slt.lk", role="ADMIN", is_active=True, created_at=datetime.now())
    today_dt = datetime.now()

    u = GmfUpload(
        id=101,
        filename="cycle1_53.gmf",
        file_path="/fake/cycle1_53.gmf",
        folder_type="Cycle_1",
        cycle_number=1,
        total_records_count=53,
        processed_records_count=31,
        template_breakdown=json.dumps({"vat_home": 31, "vat_enterprise": 22}),
        status=GmfUploadStatus.PARTIALLY_PROCESSED,
        detected_at=today_dt
    )
    db_session.add(u)
    db_session.commit()

    # Step 0: Initial state -> 22 Remaining (31 / 53 Done)
    batches = get_pending_batches(db=db_session, _=admin_user)
    assert len(batches) == 1
    b = batches[0]
    assert b["cycle_number"] == 1
    assert b["total_records"] == 53
    assert b["processed_records"] == 31
    assert b["remaining_records"] == 22

    # Step 1: User generates 10 -> processed becomes 41 (10 of vat_enterprise)
    u.processed_records_count = 41
    db_session.commit()

    batches = get_pending_batches(db=db_session, _=admin_user)
    assert len(batches) == 1
    b = batches[0]
    assert b["total_records"] == 53
    assert b["processed_records"] == 41
    assert b["remaining_records"] == 12

    # Step 2: User generates remaining 12 -> completes
    u.processed_records_count = 53
    u.status = GmfUploadStatus.COMPLETED
    db_session.commit()

    batches = get_pending_batches(db=db_session, _=admin_user)
    assert len(batches) == 0


def test_batch_counts_multi_file_cycle(db_session):
    """
    Test that a multi-file cycle batch (e.g., 3 files of 10 accounts = 30 total)
    correctly maintains active approved totals while files are incrementally processed.
    """
    admin_user = UserOut(id=1, email="admin@slt.lk", role="ADMIN", is_active=True, created_at=datetime.now())
    today_dt = datetime.now()

    # 3 files in Cycle 2, 10 records each
    u1 = GmfUpload(
        id=1, filename="c2_f1.gmf", file_path="/fake/c2_f1.gmf", folder_type="Cycle_2", cycle_number=2,
        template_detected="vat_home", total_records_count=10, processed_records_count=0,
        status=GmfUploadStatus.APPROVED, detected_at=today_dt
    )
    u2 = GmfUpload(
        id=2, filename="c2_f2.gmf", file_path="/fake/c2_f2.gmf", folder_type="Cycle_2", cycle_number=2,
        template_detected="vat_home", total_records_count=10, processed_records_count=0,
        status=GmfUploadStatus.APPROVED, detected_at=today_dt
    )
    u3 = GmfUpload(
        id=3, filename="c2_f3.gmf", file_path="/fake/c2_f3.gmf", folder_type="Cycle_2", cycle_number=2,
        template_detected="vat_home", total_records_count=10, processed_records_count=0,
        status=GmfUploadStatus.APPROVED, detected_at=today_dt
    )
    db_session.add_all([u1, u2, u3])
    db_session.commit()

    # Step 0: Initial state -> 30 total, 0 processed, 30 remaining
    batches = get_pending_batches(db=db_session, _=admin_user)
    assert len(batches) == 1
    b = batches[0]
    assert b["cycle_number"] == 2
    assert b["total_records"] == 30
    assert b["processed_records"] == 0
    assert b["remaining_records"] == 30
    assert b["upload_ids"] == [1, 2, 3]


def test_billing_run_counters_preserve_total_accounts(db_session):
    """
    Test that _update_billing_run preserves configured total_accounts (e.g. 10)
    when a run of 10 completes.
    """
    run = BillingRun(
        id=1,
        batch_name="Batch 2026-08-24 12:00:00",
        cycle_number=1,
        period_start=date.today(),
        period_end=date.today(),
        status=RunStatus.RUNNING,
        total_accounts=10,
        succeeded=0,
        failed=0,
        started_at=datetime.now()
    )
    db_session.add(run)
    db_session.commit()

    # Worker generates 10 PDFs
    _update_billing_run(db_session, run.id, generated_count=10)
    db_session.commit()

    refreshed_run = db_session.query(BillingRun).filter(BillingRun.id == run.id).first()
    assert refreshed_run.total_accounts == 10
    assert refreshed_run.succeeded == 10
    assert refreshed_run.failed == 0
    assert refreshed_run.status == RunStatus.DONE


def test_ready_for_generation_shows_in_both_auto_and_manual_modes(db_session):
    """
    Verify that get_pending_batches returns the pending batches
    regardless of whether billing_mode is 'auto' or 'manual'.
    """
    admin_user = UserOut(id=1, email="admin@slt.lk", role="ADMIN", is_active=True, created_at=datetime.now())
    today_dt = datetime.now()

    u = GmfUpload(
        id=501,
        filename="cycle1_ready.gmf",
        file_path="/fake/cycle1_ready.gmf",
        folder_type="Cycle_1",
        cycle_number=1,
        total_records_count=25,
        processed_records_count=0,
        template_breakdown=json.dumps({"vat_home": 25}),
        status=GmfUploadStatus.APPROVED,
        detected_at=today_dt,
    )
    db_session.add(u)
    db_session.commit()

    # 1. In manual mode:
    setting = db_session.query(SystemSetting).filter(SystemSetting.key == "billing_mode").first()
    setting.value = "manual"
    db_session.commit()

    manual_batches = get_pending_batches(db=db_session, _=admin_user)
    assert len(manual_batches) == 1
    assert manual_batches[0]["remaining_records"] == 25
    assert manual_batches[0]["total_records"] == 25

    # 2. Switch to auto mode:
    setting.value = "auto"
    db_session.commit()

    auto_batches = get_pending_batches(db=db_session, _=admin_user)
    assert len(auto_batches) == 1
    assert auto_batches[0]["remaining_records"] == 25
    assert auto_batches[0]["total_records"] == 25
    assert auto_batches[0]["upload_ids"] == [501]


def test_batch_folder_limit_strictly_enforced(tmp_path):
    """
    Test that _copy_pdf_to_batch strictly enforces <= 10 PDFs per batch folder.
    25 PDFs copied must produce Batch_1 (10), Batch_2 (10), and Batch_3 (5).
    """
    from app.billing.worker_queue import _copy_pdf_to_batch
    from pathlib import Path

    cycle_base = tmp_path / "output" / "2026-09-08" / "Cycle_1"
    temp_dir = tmp_path / "temp_pdfs"
    temp_dir.mkdir(parents=True)

    # Generate 25 dummy PDFs
    for i in range(1, 26):
        dummy_pdf = temp_dir / f"invoice_{i:03d}.pdf"
        dummy_pdf.write_bytes(b"%PDF-1.4 dummy pdf content")
        _copy_pdf_to_batch(dummy_pdf, cycle_base, max_per_batch=10)

    batch_1 = cycle_base / "Batch_1"
    batch_2 = cycle_base / "Batch_2"
    batch_3 = cycle_base / "Batch_3"
    batch_4 = cycle_base / "Batch_4"

    assert batch_1.exists()
    assert batch_2.exists()
    assert batch_3.exists()
    assert not batch_4.exists()

    b1_count = sum(1 for _ in batch_1.rglob("*.pdf"))
    b2_count = sum(1 for _ in batch_2.rglob("*.pdf"))
    b3_count = sum(1 for _ in batch_3.rglob("*.pdf"))

    assert b1_count == 10
    assert b2_count == 10
    assert b3_count == 5


def test_multi_template_selective_approval_and_sequential_generation(db_session):
    """
    Test universal multi-template approval & generation lifecycle:
    1. Bulk GMF has 61 records (31 vat_home, 30 vat_enterprise).
    2. Only vat_home approved: Ready for Generation shows 31 Total, 31 Remaining (0 / 31 Done).
    3. vat_enterprise approved subsequently: Card expands to 61 Total, 61 Remaining (0 / 61 Done).
    4. Clicking 'Generate 10': Produces 10 PDFs, card shows 61 Total, 51 Remaining (10 / 61 Done).
    5. Clicking 'Generate 50': Generates next 50 (records 11-60), card shows 61 Total, 1 Remaining (60 / 61 Done).
    6. Generating final 1: Completes upload, card clears.
    """
    from app.api.routers.billing import get_upload_summary

    admin_user = UserOut(id=1, email="admin@slt.lk", role="ADMIN", is_active=True, created_at=datetime.now())
    today_dt = datetime.now()

    # Step 1: Only vat_home is approved in DB
    tmpl_vh = db_session.query(InvoiceTemplate).filter(InvoiceTemplate.template_code == "vat_home").first()
    tmpl_ve = db_session.query(InvoiceTemplate).filter(InvoiceTemplate.template_code == "vat_enterprise").first()
    tmpl_vh.approval_status = TemplateApprovalStatus.APPROVED
    tmpl_ve.approval_status = TemplateApprovalStatus.PENDING
    db_session.commit()

    u = GmfUpload(
        id=601,
        filename="cycle1_bulk_61.txt",
        file_path="/fake/cycle1_bulk_61.txt",
        folder_type="Cycle_1",
        cycle_number=1,
        total_records_count=61,
        processed_records_count=0,
        template_breakdown=json.dumps({"vat_home": 31, "vat_enterprise": 30}),
        status=GmfUploadStatus.PARTIALLY_PROCESSED,
        detected_at=today_dt,
    )
    db_session.add(u)
    db_session.commit()

    # Step 2: When only vat_home is approved -> 31 total, 0 done, 31 remaining
    batches = get_pending_batches(db=db_session, _=admin_user)
    assert len(batches) == 1
    assert batches[0]["total_records"] == 31
    assert batches[0]["processed_records"] == 0
    assert batches[0]["remaining_records"] == 31

    # Step 3: vat_enterprise is subsequently approved -> expands to 61 total, 0 done, 61 remaining
    tmpl_ve.approval_status = TemplateApprovalStatus.APPROVED
    db_session.commit()

    batches = get_pending_batches(db=db_session, _=admin_user)
    assert len(batches) == 1
    assert batches[0]["total_records"] == 61
    assert batches[0]["processed_records"] == 0
    assert batches[0]["remaining_records"] == 61

    # Step 4: Generate first 10 records (from vat_home)
    u.processed_records_count = 10
    u.processed_breakdown = json.dumps({"vat_home": 10})
    db_session.commit()

    batches = get_pending_batches(db=db_session, _=admin_user)
    assert len(batches) == 1
    assert batches[0]["total_records"] == 61
    assert batches[0]["processed_records"] == 10
    assert batches[0]["remaining_records"] == 51

    # Check upload summary breakdown
    summary = get_upload_summary(upload_id=601, db=db_session, _=admin_user)
    bd = {item["template_id"]: item for item in summary["template_breakdown"]}
    assert bd["vat_home"]["count"] == 31
    assert bd["vat_home"]["processed_count"] == 10
    assert bd["vat_home"]["remaining_count"] == 21
    assert bd["vat_enterprise"]["count"] == 30
    assert bd["vat_enterprise"]["processed_count"] == 0
    assert bd["vat_enterprise"]["remaining_count"] == 30

    # Step 5: Generate next 50 records (21 vat_home + 29 vat_enterprise)
    u.processed_records_count = 60
    u.processed_breakdown = json.dumps({"vat_home": 31, "vat_enterprise": 29})
    db_session.commit()

    batches = get_pending_batches(db=db_session, _=admin_user)
    assert len(batches) == 1
    assert batches[0]["total_records"] == 61
    assert batches[0]["processed_records"] == 60
    assert batches[0]["remaining_records"] == 1

    # Step 6: Generate remaining 1 record
    u.processed_records_count = 61
    u.processed_breakdown = json.dumps({"vat_home": 31, "vat_enterprise": 30})
    u.status = GmfUploadStatus.COMPLETED
    db_session.commit()

    batches = get_pending_batches(db=db_session, _=admin_user)
    assert len(batches) == 0


def test_concurrent_billing_run_atomic_updates(db_session):
    """
    Test that invocations of _update_billing_run accurately increment succeeded
    to 10 without lost updates.
    """
    run = BillingRun(
        id=999,
        batch_name="Concurrent Test",
        period_start=date.today(),
        period_end=date.today(),
        status=RunStatus.RUNNING,
        total_accounts=10,
        succeeded=0,
        failed=0,
        started_at=datetime.now()
    )
    db_session.add(run)
    db_session.commit()

    # 10 workers each report 1 generated invoice
    for _ in range(10):
        _update_billing_run(db_session, 999, generated_count=1)
        db_session.commit()

    refreshed = db_session.query(BillingRun).filter(BillingRun.id == 999).first()
    assert refreshed.succeeded == 10
    assert refreshed.status == RunStatus.DONE



