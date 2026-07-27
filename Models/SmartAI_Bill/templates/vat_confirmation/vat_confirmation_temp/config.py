"""
config.py
All the stuff that does NOT change per-recipient: page geometry, fonts,
coordinates, and the fixed paragraph text. Edit THIS file to fix layout
issues -- render.py should never need hardcoded numbers.
"""

# --- Paths ---
TEMPLATE_PDF = "template.pdf"
SOURCE_CSV = "recipients.csv"
OUTPUT_DIR = "output"

# --- Page geometry (matches template.pdf's actual MediaBox, not plain A4) ---
PAGE_WIDTH = 595.5
PAGE_HEIGHT = 850.08
PAGE_BOTTOM_OFFSET = 7.83  # template's MediaBox starts at y=7.83, not 0

# --- Fonts ---
FONT_BODY = "Times-Roman"
FONT_BOLD = "Times-Bold"
FONT_ITALIC = "Times-Italic"
SIZE_BODY = 12
SIZE_FOOTER = 9
FONT_PAGE_NUMBER = "Helvetica-Bold"

# --- Layout coordinates ---
# All extracted directly from the ground-truth reference PDF
# ("VAT number confirmation Letter AmendednewADD.pdf", page 1) via
# pdfplumber word/char bounding boxes, NOT eyeballed from a screenshot.
# Confirmed against pages 2-3 that the indented column and Date position
# are FIXED (do not shift with recipient name/address length).
#
# Two distinct x-anchors -- these are NOT the same column:
#   - X_BODY: body margin used by To:/Our Reference:/VAT No./Subject/
#     salutation/paragraphs/closing.
#   - X_RECIPIENT: indented column used ONLY by the recipient name/address
#     lines, left-aligned.
#   - X_DATE: a separate fixed position for "Date:" -- confirmed NOT the
#     same as X_RECIPIENT by comparing across reference pages 1-3 (Date
#     never moves while the recipient block content does).
X_BODY = 56.7
X_RECIPIENT = 308.9
X_DATE = 447.7

RIGHT_MARGIN = 56.7  # symmetric with X_BODY; used for paragraph wrap width

# All Y values are "distance from top of page" baselines, fed through
# y_from_top() in render.py. LINE_HEIGHT values below are measured
# baseline-to-baseline gaps from the reference, not guesses.
Y_DATE = 104.7                      # "Date:" baseline
Y_RECIPIENT_START = 127.0           # first recipient line baseline
RECIPIENT_LINE_HEIGHT = 14.63       # baseline-to-baseline within recipient block
GAP_RECIPIENT_TO_TO = 42.4          # last recipient line baseline -> "To:" baseline

TO_OUR_REF_VAT_LINE_HEIGHT = 15.9   # To: / Our Reference: / VAT No. spacing
GAP_VAT_TO_SUBJECT = 31.7
GAP_SUBJECT_TO_SALUTATION = 30.8
GAP_SALUTATION_TO_BODY = 23.9

BODY_LINE_HEIGHT = 13.8             # within-paragraph line spacing
PARAGRAPH_EXTRA_GAP = 10.0          # added on top of BODY_LINE_HEIGHT between paragraphs
GAP_CLOSING_TO_SIGNOFF = 17.8       # "Yours sincerely," baseline -> "Sri Lanka Telecom PLC" baseline

# Footer disclaimer text + horizontal rule are already baked into
# template.pdf -- do NOT redraw them. Only the page number is drawn here.
Y_PAGE_NUMBER = 770.8                # page number baseline
X_PAGE_NUMBER_RIGHT = 537.2          # page number right edge (drawRightString anchor)

DATE_FORMAT = "%d.%m.%Y"  # matches "16.06.2026" style in the template

# --- Page numbering (running counter across the batch; not from CSV) ---
START_PAGE_NUMBER = 65

# --- Fixed text blocks (edit wording here, not in render.py) ---
SUBJECT_LINE = "Subject: Verification of VAT Registration Number"

SALUTATION = "Dear Valued Customer,"

BODY_PARAGRAPHS = [
    "We wish to draw your kind attention to an important matter concerning the Value Added Tax (VAT) "
    "registration details associated with your SLTMOBITEL account. As part of our commitment to "
    "ensuring the accuracy of your billing records and to facilitate your compliance obligations with the "
    "Inland Revenue Department (IRD) of Sri Lanka, we are currently undertaking a systematic review of "
    "VAT registration numbers maintained in our systems.",

    "Our records indicate that the VAT Registration Number currently reflected against your account, as "
    "referenced above. It is essential that this information is accurate and up to date, as any discrepancy "
    "may have implications on your VAT input credit claims and compliance standing with the Inland "
    "Revenue Department.",

    "We kindly request you to verify the VAT Registration Number indicated in this letter against your "
    "official VAT certificate issued by the Inland Revenue Department.",

    "Should you find that the number on record is incorrect or requires an update, please submit the "
    "corrected VAT Registration Number along with a copy of your valid VAT Certificate to the following "
    "email address on or before {deadline}.",

    "Email address: {email}",

    "Please note that if we do not hear from you by the stipulated date, we will consider the VAT "
    "Registration Number on record as confirmed. Sri Lanka Telecom PLC regrets that it cannot be held "
    "responsible for any implications arising with the Inland Revenue Department due to unnotified "
    "inaccuracies.",

    "We appreciate your prompt attention to this matter and thank you for your continued patronage of "
    "Sri Lanka Telecom PLC.",
]

CLOSING = "Yours sincerely,"
SIGN_OFF = "Sri Lanka Telecom PLC"

FOOTER_TEXT = "***This is a System Generated Letter. No signature is required. ***"

# --- Values used inside BODY_PARAGRAPHS placeholders ---
VERIFICATION_EMAIL = "shavindri@slt.com.lk"
VERIFICATION_DEADLINE = "26th June 2026"  # set per your actual campaign deadline
