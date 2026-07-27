import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PDF = os.path.join(BASE_DIR, "template.pdf")

# Fallback template PDF location if asset is stored in upper folder
if not os.path.exists(TEMPLATE_PDF):
    UPPER_PDF = os.path.join(os.path.dirname(BASE_DIR), "VAT-Number-Confirmation", "template.pdf")
    if os.path.exists(UPPER_PDF):
        TEMPLATE_PDF = UPPER_PDF

PAGE_WIDTH = 595.5
PAGE_HEIGHT = 850.08

FONT_BODY = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
SIZE_BODY = 10
SIZE_FOOTER = 8

X_BODY = 56.7
X_RECIPIENT = 308.9
X_DATE = 447.7
RIGHT_MARGIN = 56.7

Y_DATE = 104.7
Y_RECIPIENT_START = 127.0
RECIPIENT_LINE_HEIGHT = 14.63
GAP_RECIPIENT_TO_TO = 42.4

TO_OUR_REF_VAT_LINE_HEIGHT = 15.9
GAP_VAT_TO_SUBJECT = 31.7
GAP_SUBJECT_TO_SALUTATION = 30.8
GAP_SALUTATION_TO_BODY = 23.9

BODY_LINE_HEIGHT = 13.8
PARAGRAPH_EXTRA_GAP = 10.0
GAP_CLOSING_TO_SIGNOFF = 17.8

Y_PAGE_NUMBER = 770.8
X_PAGE_NUMBER_RIGHT = 537.2
START_PAGE_NUMBER = 1

DATE_FORMAT = "%d.%m.%Y"

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
VERIFICATION_EMAIL = "shavindri@slt.com.lk"
VERIFICATION_DEADLINE = "26th June 2026"
