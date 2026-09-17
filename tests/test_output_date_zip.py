import os
import sys
import io
import zipfile
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

# Ensure Models/SmartAI_Bill is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Models", "SmartAI_Bill")))

from processing.output_manager import create_date_output_zip, list_output_dates
from app.api.main import app
from app.auth.dependencies import get_current_user, require_admin
from app.auth.schemas import UserOut


def _test_admin() -> UserOut:
    return UserOut(
        id=1,
        email="admin@slt.local",
        role="ADMIN",
        roles=["ADMIN"],
    )


@pytest.fixture
def test_client():
    app.dependency_overrides[get_current_user] = _test_admin
    app.dependency_overrides[require_admin] = _test_admin
    with patch("app.auth.dependencies.azure_scheme.openid_config.load_config"):
        with TestClient(app, headers={"Authorization": "Bearer test-token"}) as client:
            yield client
    app.dependency_overrides.clear()


def test_create_date_output_zip_structure(tmp_path):
    """Verify that create_date_output_zip maintains the exact folder structure and excludes lock files."""
    test_date = "2026-08-20"
    output_root = tmp_path / "output"
    date_dir = output_root / test_date

    # Create nested folder structure
    pdf1 = date_dir / "Cycle_1" / "Batch_1" / "Email" / "Non-Red" / "001.pdf"
    pdf1.parent.mkdir(parents=True, exist_ok=True)
    pdf1.write_bytes(b"%PDF-1.4 test content 1")

    pdf2 = date_dir / "Cycle_1" / "Batch_2" / "Print" / "RED" / "002.pdf"
    pdf2.parent.mkdir(parents=True, exist_ok=True)
    pdf2.write_bytes(b"%PDF-1.4 test content 2")

    env_pdf = date_dir / "Envelope" / "Batch_01" / "env.pdf"
    env_pdf.parent.mkdir(parents=True, exist_ok=True)
    env_pdf.write_bytes(b"%PDF-1.4 test envelope")

    summary_json = date_dir / "summary" / "CR001" / "manifest.json"
    summary_json.parent.mkdir(parents=True, exist_ok=True)
    summary_json.write_text('{"accounts": ["001"]}', encoding="utf-8")

    # Create lock and temporary files that should be ignored
    lock_file1 = date_dir / "Cycle_1" / ".batch_alloc.lock"
    lock_file1.write_text("locked", encoding="utf-8")

    lock_file2 = date_dir / "temp.lock"
    lock_file2.write_text("locked", encoding="utf-8")

    zip_out = tmp_path / "result.zip"

    with patch("processing.output_manager.get_output_roots", return_value=[str(output_root)]):
        count = create_date_output_zip(test_date, str(zip_out))

    assert count == 4
    assert zip_out.exists()

    with zipfile.ZipFile(zip_out, "r") as zf:
        namelist = zf.namelist()
        # Verify all relative paths maintain their full nested hierarchy
        assert "Cycle_1/Batch_1/Email/Non-Red/001.pdf" in namelist
        assert "Cycle_1/Batch_2/Print/RED/002.pdf" in namelist
        assert "Envelope/Batch_01/env.pdf" in namelist
        assert "summary/CR001/manifest.json" in namelist

        # Verify lock files are excluded
        assert not any(".lock" in name for name in namelist)
        assert not any(name.startswith(".") for name in namelist)

        # Check content integrity
        assert zf.read("Cycle_1/Batch_1/Email/Non-Red/001.pdf") == b"%PDF-1.4 test content 1"
        assert zf.testzip() is None


def test_create_date_output_zip_invalid_date():
    """Verify that invalid date formats are rejected."""
    with pytest.raises(ValueError):
        create_date_output_zip("../traversal", "out.zip")

    with pytest.raises(ValueError):
        create_date_output_zip("", "out.zip")


def test_download_date_output_endpoint_invalid_date(test_client):
    """Test the download endpoint returns 400 for path traversal/invalid date format."""
    res = test_client.get("/billing/output/../traversal/download")
    assert res.status_code in (400, 404)


def test_download_date_output_endpoint_not_found(test_client):
    """Test the download endpoint returns 404 for a non-existent date."""
    res = test_client.get("/billing/output/1990-01-01/download")
    assert res.status_code == 404
    assert "No output found" in res.json()["detail"]


def test_download_date_output_endpoint_success(test_client, tmp_path):
    """Test successfully downloading a date zip via the API."""
    test_date = "2026-07-10"
    output_root = tmp_path / "output"
    date_dir = output_root / test_date

    pdf = date_dir / "Cycle_1" / "Batch_1" / "bill.pdf"
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.write_bytes(b"%PDF-1.4 sample bill")

    with patch("processing.output_manager.get_output_roots", return_value=[str(output_root)]):
        with patch("app.api.routers.billing.list_output_dates", return_value=[test_date]):
            res = test_client.get(f"/billing/output/{test_date}/download")

    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"
    assert f'filename="{test_date}.zip"' in res.headers["content-disposition"]

    # Verify content is valid zip with expected folder structure
    zip_bytes = io.BytesIO(res.content)
    with zipfile.ZipFile(zip_bytes, "r") as zf:
        assert "Cycle_1/Batch_1/bill.pdf" in zf.namelist()
        assert zf.read("Cycle_1/Batch_1/bill.pdf") == b"%PDF-1.4 sample bill"


def test_list_output_dates_excludes_super_admin_reports_and_previews(tmp_path):
    """Ensure non-date and privileged folders like super_admin_reports and previews are excluded."""
    output_root = tmp_path / "output"
    (output_root / "2026-09-17").mkdir(parents=True)
    (output_root / "2026-09-16").mkdir(parents=True)
    (output_root / "super_admin_reports").mkdir(parents=True)
    (output_root / "previews").mkdir(parents=True)
    (output_root / "arbitrary_folder").mkdir(parents=True)

    with patch("processing.output_manager.get_output_roots", return_value=[str(output_root)]):
        dates = list_output_dates()

    assert "super_admin_reports" not in dates
    assert "previews" not in dates
    assert "arbitrary_folder" not in dates
    assert dates == ["2026-09-17", "2026-09-16"]


def test_super_admin_reports_not_accessible_via_billing_api(test_client, tmp_path):
    """Ensure super_admin_reports cannot be downloaded or browsed via the standard billing endpoints."""
    output_root = tmp_path / "output"
    report_dir = output_root / "super_admin_reports"
    report_dir.mkdir(parents=True)
    (report_dir / "report.pdf").write_bytes(b"%PDF-1.4 report")

    with patch("processing.output_manager.get_output_roots", return_value=[str(output_root)]):
        # Listing cycles for super_admin_reports returns 404
        res_cycles = test_client.get("/billing/output/super_admin_reports")
        assert res_cycles.status_code == 404

        # Downloading zip for super_admin_reports returns 404
        res_download = test_client.get("/billing/output/super_admin_reports/download")
        assert res_download.status_code == 404
