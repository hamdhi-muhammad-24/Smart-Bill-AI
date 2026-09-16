import sys
import os
import shutil
import time
from pathlib import Path

# Ensure the app module can be imported
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.db.base import SessionLocal
from app.db.models import (
    NotificationEvent,
    BillingRunItem,
    BillingRunFailure,
    Invoice,
    GmfUpload,
    BillingRun,
    InvoiceTemplate,
    TemplateApprovalStatus,
    EnvelopeArtwork,
    EnvelopeHistory,
    TemplateHistory,
)


def _force_delete(path_item):
    """Force deletes files and directories with retries for Windows file locks."""
    if not path_item.exists():
        return 0
    deleted_count = 0
    for attempt in range(5):
        try:
            if path_item.is_file():
                os.chmod(path_item, 0o777)
                path_item.unlink()
                return 1
            elif path_item.is_dir():
                for root, dirs, files in os.walk(path_item, topdown=False):
                    for name in files:
                        p = Path(root) / name
                        try:
                            os.chmod(p, 0o777)
                            p.unlink()
                            deleted_count += 1
                        except Exception:
                            pass
                    for name in dirs:
                        p = Path(root) / name
                        try:
                            os.chmod(p, 0o777)
                            p.rmdir()
                        except Exception:
                            pass
                try:
                    os.chmod(path_item, 0o777)
                    path_item.rmdir()
                except Exception:
                    pass
                return deleted_count
        except Exception:
            time.sleep(0.3)
    return deleted_count


from app.billing.super_admin_service import execute_system_reset


def reset_test_data():
    print("WARNING: This script will delete all transaction history (GMF Uploads, Invoices, Billing Runs, Notifications, Envelope Artworks, Audit History, Super Admin Test Runs).")
    print("It will NOT delete Users, Base Templates, or Billing Schedules.")
    
    if "--yes" in sys.argv or "-y" in sys.argv:
        confirm = "YES"
    else:
        confirm = input("Are you sure you want to proceed? Type 'YES' to confirm: ")
    
    if confirm != "YES":
        print("Operation cancelled.")
        return

    print("Connecting to database and executing full system reset...")
    with SessionLocal() as db:
        try:
            res = execute_system_reset(db)
            print("\nDatabase records deleted:")
            for k, v in res["deleted_counts"].items():
                print(f"  - {k}: {v}")
            print(f"\nCleaned up {res['files_deleted']} files/folders from processing queues, output, and storage.")
            print(f"\nSUCCESS: {res['message']}")
            print("You can now upload your GMF files back into the system and test fresh.")
        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    reset_test_data()
