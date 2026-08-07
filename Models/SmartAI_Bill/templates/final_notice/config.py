"""
config.py  -  SLT LTE "FINAL NOTICE" letter generator
=====================================================
Single place to change paths, column mapping, business rules, and - most
importantly - the on-page COORDINATES of every field.

The template is a 2-page IMAGE (page 0 = Sinhala + Tamil, page 1 = English)
with blank slots. We stamp the customer's values on top at fixed positions.

COORDINATE SYSTEM USED IN THIS FILE
-----------------------------------
Every placement uses `x` (points from the LEFT edge) and `top`
(points from the TOP edge). render.py converts `top` to reportlab's
bottom-origin automatically.

    page size: 595.0 wide x 771.6 tall (points)
"""

from pathlib import Path

# --------------------------------------------------------------------------
# 1. PATHS
# --------------------------------------------------------------------------
BASE_DIR   = Path(__file__).resolve().parent
DATA_XLSX  = BASE_DIR / "data" / "customers.xlsx"
TEMPLATE   = BASE_DIR / "assets" / "template.pdf"      # 2-page image template
OUTPUT_DIR = BASE_DIR / "output"
SHEET_NAME = None      # None = first sheet, or exact sheet name

PAGE_W, PAGE_H = 595.0, 771.6

# --------------------------------------------------------------------------
# 2. OUTPUT MODE
# --------------------------------------------------------------------------
OUTPUT_MODE       = "per_customer"          # "combined" | "per_customer"
COMBINED_FILENAME = "FinalNotice_batch.pdf"
FILENAME_COLUMN   = "ACCOUNT_NUM"       # used to name per-customer files
LIMIT             = None           # None = all; int for test runs

# --------------------------------------------------------------------------
# 3. SPREADSHEET COLUMN NAMES  (must match header row exactly)
# --------------------------------------------------------------------------
COL_ACCOUNT   = "ACCOUNT_NUM"
COL_PRODUCT   = "PRODUCT_LABEL"          # -> telephone number (see rule below)
COL_NAME      = "NAME"
COL_ADDR      = ["ADDRESS_1", "ADDRESS_2", "ADDRESS_3", "ADDRESS_4", "ADDRESS_5"]
COL_ZIP       = "ZIPCODE"
COL_AMOUNT    = "TOTAL_ARREARS_24/06/2026"
COL_DATE      = "DATE OF THE LETTER"
COL_DUE       = "DUE DATE"
COL_CONTACT   = "CONTACT NO"

# --------------------------------------------------------------------------
# 4. BUSINESS RULES  (the choices you must confirm - see chat)
# --------------------------------------------------------------------------
# Telephone formatting from PRODUCT_LABEL:
#   "lk94"  -> strip a leading 0 and prepend "94"  (0382222697 -> 94382222697)
#   "as_is" -> print PRODUCT_LABEL unchanged
TEL_FORMAT = "lk94"

# In-body contact number:
#   "fixed"  -> always use CONTACT_FIXED (matches the provided sample)
#   "column" -> use the CONTACT NO column value per customer
CONTACT_SOURCE = "fixed"
CONTACT_FIXED  = "0112389911"

# Amount formatting: ensure thousands separators + 2 decimals even if the
# cell is a raw number. If the cell is already a formatted string, it is kept.
AMOUNT_DECIMALS = 2

# Barcode under the address box.
BARCODE_ENABLED = True
BARCODE_FIELD   = "account"      # which value to encode: "account" or "telephone"

# Static sender block printed under the logo (date is added as its first line).
SENDER_LINES = [
    "Senior Manager,",
    "Collection & Credit Control Section,",
    "Sri Lanka Telecom PLC,",
    "Lotus Road, Colombo 01.",
]

# --------------------------------------------------------------------------
# 5. FONTS
# --------------------------------------------------------------------------
FONT_REG  = "Helvetica"
FONT_BOLD = "Helvetica-Bold"

# --------------------------------------------------------------------------
# 6. COORDINATES  (x = from left, top = from top; both in points)
# --------------------------------------------------------------------------
# --- recipient address box (page 0, top-left) ---
ADDRESS_BLOCK = dict(page=0, x=60, top=40, line_gap=12,
                     name_font=FONT_BOLD, name_size=9.5,
                     addr_font=FONT_BOLD, addr_size=9.5)

# --- sender block (page 0, upper-right, under logo): date + SENDER_LINES ---
SENDER_BLOCK = dict(page=0, x=380, top=96, line_gap=13,
                    date_font=FONT_BOLD, date_size=10,
                    line_font=FONT_REG, line_size=9.5)

# --- barcode (page 0) ---
BARCODE_POS = dict(page=0, x=135, top=110, bar_height=12, bar_width=1.5)

# --- copy marker like "[1]" (page 0). Set text="" to hide. ---
COPY_MARKER = dict(page=0, x=280, top=105, text="[1]", font=FONT_REG, size=8)

# --- single-line value placements per page ---
# Each entry: dict(field=<key from parser>, x, top, font, size, align)
#   field keys available: telephone, account, amount, due_date, contact
#   align: "left" (default) or "right"
PLACEMENTS = {
    0: [   # ---------- Sinhala + Tamil page ----------
        # Sinhala field row (values sit above the underline ~top 243)
        dict(field="telephone", x=125, top=235, font=FONT_BOLD, size=9),
        dict(field="account",   x=260, top=235, font=FONT_BOLD, size=9),
        dict(field="amount",    x=470, top=235, font=FONT_BOLD, size=9, align="left"),
        # Sinhala body due-date (appears twice) + contact
        dict(field="due_date",  x=440, top=294, font=FONT_BOLD, size=9),
        dict(field="due_date",  x=120, top=316, font=FONT_BOLD, size=9),
        dict(field="contact",   x=475, top=385, font=FONT_REG,  size=9),
        # Tamil field row (values above underline ~top 488)
        dict(field="telephone", x=145, top=480, font=FONT_BOLD, size=9),
        dict(field="account",   x=285, top=480, font=FONT_BOLD, size=9),
        dict(field="amount",    x=505, top=480, font=FONT_BOLD, size=9),
        # Tamil body due-date + contact
        dict(field="due_date",  x=160, top=563, font=FONT_BOLD, size=9),
        dict(field="due_date",  x=410, top=573, font=FONT_BOLD, size=9),
        dict(field="contact",   x=195, top=668, font=FONT_REG,  size=9),
    ],
    1: [],  # ---------- English page (filled from ENGLISH_PLACEMENTS below) ----------
}

# The English page placements are defined below (kept separate for clarity so
# the dict above stays readable). Merged into PLACEMENTS[1] at import time.
ENGLISH_PLACEMENTS = [
    dict(field="telephone", x=145, top=100, font=FONT_BOLD, size=9),
    dict(field="account",   x=295, top=100, font=FONT_BOLD, size=10),
    dict(field="amount",    x=505, top=100, font=FONT_BOLD, size=10, align="left"),
    dict(field="due_date",  x=285, top=218, font=FONT_REG, size=10),
    dict(field="due_date",  x=470, top=233, font=FONT_REG, size=10),
    dict(field="contact",   x=440, top=365, font=FONT_REG,  size=10),
]
PLACEMENTS[1] = ENGLISH_PLACEMENTS
