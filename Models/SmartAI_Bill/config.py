import os
import multiprocessing

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# GMF_DRIVE_PATH = os.environ.get("GMF_DRIVE_PATH", r"G:\My Drive\SLT_GMF_Uploads")
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))
GMF_DRIVE_PATH = os.environ.get("GMF_DRIVE_PATH", os.path.join(ROOT_DIR, "local_gmf_uploads"))

INBOUND_DIR   = os.path.join(BASE_DIR, "data", "inbound")
PROCESSED_DIR = os.path.join(GMF_DRIVE_PATH, "Processed")
FAILED_DIR    = os.path.join(GMF_DRIVE_PATH, "Failed")
LOGS_DIR      = os.path.join(BASE_DIR, "logs")

# ── Output — organised as Output/<date>/<Cycle_N>/Batch_N/ ────────────────────
OUTPUT_BASE_DIR = os.path.join(GMF_DRIVE_PATH, "Output")

# Legacy ZIP output dir (kept for backwards compat, not used by default)
OUTPUT_ZIP_DIR = os.path.join(GMF_DRIVE_PATH, "Output_ZIPs")

# ── Batch sizing ───────────────────────────────────────────────────────────────
# Each batch folder will contain up to this many PDF files.
# Production: 1500  |  Development/testing: 10
BATCH_FOLDER_SIZE = int(os.environ.get("BATCH_FOLDER_SIZE", "10"))

# Legacy name kept for imports that still reference ZIP_BATCH_SIZE
ZIP_BATCH_SIZE = BATCH_FOLDER_SIZE

# ── Workers ────────────────────────────────────────────────────────────────────
DEFAULT_WORKERS = max(1, multiprocessing.cpu_count() - 1)

# ── PDF output naming ──────────────────────────────────────────────────────────
OUTPUT_PDF_NAMES = {
    "nonvat_home":               "{account_number}_NONVAT_HOME.pdf",
    "nonvat_enterprise":         "{account_number}_NONVAT_ENTERPRISE.pdf",
    "vat_enterprise":            "{account_number}_VAT_ENTERPRISE.pdf",
    "vat_home":                  "{account_number}_VAT_HOME.pdf",
    "product_label_grouping":    "{account_number}_ProductLevel.pdf",
    "subscription_ref_grouping": "{account_number}_SubscriptionLevel.pdf",
    "summary_statement":         "{account_number}_SUMMARY.pdf",
    "invoice_of_summary":        "{account_number}_InvoiceOfSummary.pdf",
    "usd_open_item":             "{account_number}_USD_OPEN_Item.pdf",
    "vat_creditnote":            "CreditNote_VAT.pdf",
    "nonvat_creditnote":         "CreditNote_NONVAT.pdf",
    "lod":                       "{account_number}_LOD.pdf",
    "vat_confirmation":          "{account_number}_Vat_confirmation.pdf",
    "final_notice":              "{account_number}_Final_Notice.pdf",
    "customer_letter_logo_v1print": "{account_number}_Customer_Letter.pdf",
    "customer_migration_letter": "{account_number}_Customer_Letter.pdf",
    "customer_letter":           "{account_number}_Customer_Letter.pdf",
}

OUTPUT_PDF_NAME_DEFAULT = "SLT20eBill-{account_number}.pdf"
OUTPUT_ZIP_NAME = "SLT_BILLS_{template}_{batch_num:04d}_{timestamp}.zip"

# ── File handling ──────────────────────────────────────────────────────────────
MOVE_AFTER_PROCESS = True

# ── Performance target ─────────────────────────────────────────────────────────
TARGET_BILLS_PER_HOUR = 40_000