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
    Generation Hub must show: 10 Remaining (0 / 10 Done).
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
    assert b["total_records"] == 10
    assert b["processed_records"] == 0
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
    Generation Hub must show: 22 Remaining (0 / 22 Done).
    When 10 are generated, it must show: 12 Remaining (10 / 22 Done).
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

    # Step 0: Initial state -> 22 Remaining (0 / 22 Done)
    batches = get_pending_batches(db=db_session, _=admin_user)
    assert len(batches) == 1
    b = batches[0]
    assert b["cycle_number"] == 1
    assert b["total_records"] == 22
    assert b["processed_records"] == 0
    assert b["remaining_records"] == 22

    # Step 1: User generates 10 -> processed becomes 41 (10 of vat_enterprise)
    u.processed_records_count = 41
    db_session.commit()

    batches = get_pending_batches(db=db_session, _=admin_user)
    assert len(batches) == 1
    b = batches[0]
    assert b["total_records"] == 22
    assert b["processed_records"] == 10
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
