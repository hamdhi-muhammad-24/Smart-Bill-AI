"""
config.py
=========
Single source of truth for the SLTMOBITEL migration-letter generator.

You should almost never need to edit render.py or parser.py.
Layout tuning, column names, fonts and business rules all live here.

Coordinate system (reportlab): origin is the BOTTOM-LEFT of the page.
x grows to the right, y grows upward. Page is A4 = 595.5 x 842.2 pt.
To move a block DOWN, decrease its y. To move it RIGHT, increase its x.
"""

from pathlib import Path

# --------------------------------------------------------------------------
# 1. PATHS
# --------------------------------------------------------------------------
BASE_DIR   = Path(__file__).resolve().parent
DATA_XLSX  = BASE_DIR / "data" / "customers.xlsx"       # input spreadsheet
TEMPLATE   = BASE_DIR / "assets" / "template.pdf"        # blank branded A4 (page 1 background)
PAGE2_PDF  = BASE_DIR / "assets" / "page2.pdf"           # OPTIONAL static Sinhala/Tamil page
OUTPUT_DIR = BASE_DIR / "output"

SHEET_NAME = None      # None = first sheet; or set exact sheet name e.g. "950 cx"

# --------------------------------------------------------------------------
# 2. OUTPUT MODE
# --------------------------------------------------------------------------
# "combined"     -> one big PDF with every customer (2 pages each). Best for bulk print.
# "per_customer" -> one PDF file per customer inside output/letters/.
OUTPUT_MODE       = "per_customer"
COMBINED_FILENAME = "SLT_Migration_Letters_batch1.pdf"
# For per_customer mode, the filename is built from this column value:
FILENAME_COLUMN   = "ACCOUNT"          # e.g. output/letters/0002330115.pdf
LIMIT             = None               # None = all rows; or an int for a quick test run

# Append the static Sinhala/Tamil page 2 after each English page 1.
# Requires assets/page2.pdf to exist (see README). If False or file missing,
# only the English page is produced.
APPEND_PAGE2 = True

# --------------------------------------------------------------------------
# 3. SPREADSHEET COLUMN NAMES  (must match the header row exactly)
# --------------------------------------------------------------------------
COL_NAME          = "NAME"             # clean, mixed-case name  (preferred)
COL_NAME_FALLBACK = "CUSTOMER_NAME"    # dirty fallback if NAME is empty
COL_ADDR_FULL     = "ADDR_FULL"        # richest address string -> parsed into lines
COL_ZIPCODE       = "ZIPCODE"
COL_TELEPHONE     = "TELEPHONE"
COL_TEL_STATUS    = "TELEPHONE_STATUS" # "OK" means usable
COL_ACCOUNT       = "ACCOUNT"          # fallback identifier when phone is invalid

# --------------------------------------------------------------------------
# 4. BUSINESS RULES
# --------------------------------------------------------------------------
LETTER_DATE   = "17.07.2026"           # printed on every letter in this batch
MAX_ADDR_LINES = 5                     # hard cap on address lines under the name

# Telephone fallback when TELEPHONE is 0 / blank / status != OK:
#   "account" -> print the ACCOUNT number instead
#   "blank"   -> print nothing after the label
TEL_FALLBACK = "account"

# Tokens treated as "empty" inside ADDR_FULL and dropped.
ADDR_JUNK_TOKENS = {"", "-", ".", "N/A", "NA", "NULL", "NONE"}

# Sri Lankan admin names stripped from the tail of ADDR_FULL so the block
# matches the sample (house / street / area / city / zip only).
PROVINCES = {
    "central", "western", "southern", "northern", "eastern",
    "north western", "north central", "uva", "sabaragamuwa",
}
DISTRICTS = {
    "colombo", "gampaha", "kalutara", "kandy", "matale", "nuwaraeliya",
    "nuwara eliya", "galle", "matara", "hambantota", "jaffna", "kilinochchi",
    "mannar", "vavuniya", "mullaitivu", "batticaloa", "ampara", "trincomalee",
    "kurunegala", "puttalam", "anuradhapura", "polonnaruwa", "badulla",
    "monaragala", "moneragala", "ratnapura", "kegalle",
}
COUNTRY_TOKENS = {"sri lanka", "srilanka"}

# --------------------------------------------------------------------------
# 5. FONTS
# --------------------------------------------------------------------------
# Calibri, embedded from assets/fonts/, to match the original sample exactly.
FONT_DIR       = BASE_DIR / "assets" / "fonts"
FONT_REG_PATH  = FONT_DIR / "Calibri.ttf"
FONT_BOLD_PATH = FONT_DIR / "Calibri-Bold.ttf"
FONT_REG  = "Calibri"
FONT_BOLD = "Calibri-Bold"

# --------------------------------------------------------------------------
# 6. LAYOUT COORDINATES  (points, bottom-left origin)
# --------------------------------------------------------------------------
PAGE_W, PAGE_H = 595.5, 842.2

# --- Recipient block (upper RIGHT): name + up to 5 address lines ---
ADDR_BLOCK = dict(
    x            = 310,      # left edge of the block
    y_top        = 741.6,    # baseline of the first line (the name)
    line_gap     = 14.6,     # vertical distance between lines
    name_font    = FONT_BOLD,
    name_size    = 12,
    addr_font    = FONT_BOLD,
    addr_size    = 12,
)

# --- Telephone + date (upper LEFT) ---
TEL_LINE  = dict(x=72, y=683.9, font=FONT_REG, size=11.52, label="Your Telephone No: ")
DATE_LINE = dict(x=72, y=655.8, font=FONT_REG, size=11.52)

# --- Body frame: subject + all paragraphs (justified, auto-wrapped) ---
BODY_FRAME = dict(
    x       = 72,
    y       = 60,            # bottom of frame (leaves room for footer)
    width   = PAGE_W - 72 - 72,
    height  = 580,           # top of frame sits at y + height
    font    = FONT_REG,
    size    = 11.52,
    leading = 14.1,          # line spacing inside paragraphs
    space_after = 0,         # gap between paragraphs (original has none)
)
