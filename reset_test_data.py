import sys
import os

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
)

def reset_test_data():
    print("WARNING: This script will delete all transaction history (GMF Uploads, Invoices, Billing Runs, Notifications).")
    print("It will NOT delete Users, Templates, or Billing Schedules.")
    
    if "--yes" in sys.argv or "-y" in sys.argv:
        confirm = "YES"
    else:
        confirm = input("Are you sure you want to proceed? Type 'YES' to confirm: ")
    
    if confirm != "YES":
        print("Operation cancelled.")
        return

    print("Connecting to database...")
    with SessionLocal() as db:
        try:
            # Delete in order to avoid foreign key constraint violations
            deleted_notifs = db.query(NotificationEvent).delete()
            print(f"Deleted {deleted_notifs} NotificationEvents.")
            
            deleted_items = db.query(BillingRunItem).delete()
            print(f"Deleted {deleted_items} BillingRunItems.")
            
            deleted_failures = db.query(BillingRunFailure).delete()
            print(f"Deleted {deleted_failures} BillingRunFailures.")
            
            deleted_invoices = db.query(Invoice).delete()
            print(f"Deleted {deleted_invoices} Invoices.")
            
            # GmfUpload has a foreign key to BillingRun, so we delete it before BillingRun
            deleted_uploads = db.query(GmfUpload).delete()
            print(f"Deleted {deleted_uploads} GmfUploads.")
            
            # Now we can delete BillingRuns
            deleted_runs = db.query(BillingRun).delete()
            print(f"Deleted {deleted_runs} BillingRuns.")
            
            # Reset all template approval statuses to PENDING
            updated_templates = db.query(InvoiceTemplate).update({"approval_status": TemplateApprovalStatus.PENDING})
            print(f"Reset {updated_templates} templates to PENDING status.")
            
            db.commit()
            print("\nDatabase reset successful.")
            
            # --- CLEAR PHYSICAL FILES ---
            from app.core.config import settings
            import shutil
            from pathlib import Path

            print("\nCleaning up physical files...")
            legacy_gdrive = Path(r"G:\My Drive\SLT_GMF_Uploads")
            
            paths_to_clean = [
                settings.queue_incoming_dir,
                settings.queue_pending_dir,
                Path("./queue/completed_temp"),
                Path("./output"),
                settings.gmf_drive_path / "Test_GMFs",
                settings.gmf_drive_path / "Cycle_1",
                settings.gmf_drive_path / "Cycle_2",
                settings.gmf_drive_path / "Cycle_3",
                settings.gmf_drive_path / "Cycle_4",
                settings.gmf_drive_path / "LOD",
                settings.gmf_drive_path / "VAT_Confirmation",
                settings.gmf_drive_path / "Processed",
                settings.gmf_drive_path / "Failed",
                settings.gmf_drive_path / "Output",
                Path("./Models/SmartAI_Bill/local_gmf_uploads/Output"),
                Path("./Models/SmartAI_Bill/local_gmf_uploads/Processed"),
                Path("./Models/SmartAI_Bill/local_gmf_uploads/Failed"),
                Path("./Models/SmartAI_Bill/local_gmf_uploads/Test_GMFs"),
                Path("./Models/SmartAI_Bill/local_gmf_uploads/LOD"),
                Path("./Models/SmartAI_Bill/local_gmf_uploads/VAT_Confirmation"),
            ]

            if legacy_gdrive.exists():
                for sub in ["Test_GMFs", "Cycle_1", "Cycle_2", "Cycle_3", "Cycle_4", "Processed", "Failed", "Output"]:
                    paths_to_clean.append(legacy_gdrive / sub)

            files_deleted = 0
            for p in paths_to_clean:
                if p.exists():
                    for item in p.iterdir():
                        try:
                            if item.is_file():
                                item.unlink()
                                files_deleted += 1
                            elif item.is_dir():
                                shutil.rmtree(item)
                                files_deleted += 1
                        except Exception as file_err:
                            print(f"Warning: could not delete {item}: {file_err}")
                            
            print(f"Cleaned up {files_deleted} files/folders from processing queues and drive.")
            print("\nSUCCESS! The system has been wiped clean of transaction history and temporary files.")
            print("You can now upload your GMF files back into the system and they will be treated as brand new uploads.")
        except Exception as e:
            db.rollback()
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    reset_test_data()
