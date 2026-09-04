"""VAT Home - Coordinates and Configuration.

All y-values are TOP-ORIGIN (y=0 at the top of the page), matching fitz's native
convention. No yt() conversion helper is needed anywhere in renderer.py - every
coordinate in this file is already in the same convention fitz draws with.

layout.pdf is a single full-page raster image (confirmed: only 2 real vector text
words on it - a corner code and "Tax Invoice"). There is no golden VAT_HOME.pdf
available in this repo to calibrate against (see CLAUDE.md mission). vat_home's
header/summary/payment-slip zone is visually near-identical to vat_enterprise's
(confirmed both ways: my own independent 300 DPI measurement of this template landed
within a few points of vat_enterprise's golden-verified numbers everywhere checked),
so those coordinates are taken directly from `templates/vat_enterprise/config.py`,
converted from its bottom-origin convention via `842.25 - y_bottom`. Only the
flow-column/content-band values are vat_home-specific (vat_enterprise has no
two-column reflow of this kind).
"""

PAGE_W = 595.5
PAGE_H = 842.25

COORDS = {
    # "Tax Invoice" label, top-left, above the telephone number field - same
    # addition made to vat_enterprise. Despite this file's older comments
    # below claiming layout.pdf has "Tax Invoice" baked in as vector text,
    # a direct re-check (fitz get_text('words')) returns zero words on the
    # current layout.pdf - nothing is actually printed today, so this is
    # drawn fresh. Placed 17pt above telephone_number, mirroring the same
    # offset used for vat_enterprise's tax_invoice_label - a placement
    # estimate, not a measured value; nudge if it's off.
    "tax_invoice_label": (43.0, 97.8),

    # Header fields (left column boxes) - from vat_enterprise COORDS, converted
    # telephone_number corrected (fix pass 7) to (183.6, 112.8): x=183.6
    # matches VAT_HOME.pdf golden's measured word position (183.6, 104.2)
    # exactly, next to "Tax Invoice" - the y is NOT 104.2 directly, though:
    # fitz's insert_text() takes a BASELINE y, while get_text('words') (used
    # to measure golden) reports the glyph bbox TOP - confirmed a +8.6pt
    # baseline-to-bboxtop gap for this exact font/size (FONTS["header"],
    # helv 8) by rendering a probe at y=104.2 and re-measuring its own
    # output bbox top (landed at 95.6, not 104.2). 104.2 + 8.6 = 112.8.
    "telephone_number": (183.6, 114.8),
    "account_number":   (160.0, 141.25),
    "invoice_number":   (155.0, 169.25),
    "billing_date":     (160.0, 199.25),
    "billing_period":   (145.0, 227.25),

    # VAT registration lines
    "slt_vat_reg":      (273.60, 95.25),
    "customer_vat_reg": (273.60, 105.25),

    # Customer address block (green rounded box)
    "customer_addr_x":      280.8,
    "customer_addr_start":  122.25,
    "customer_addr_line_h": 11.0,

    # Badge x-position only (left edge of "HOME"/etc. text). The y is NOT
    # stored here - it's computed from BADGE_BOX's vertical center in
    # renderer.py, so it can never drift out of sync with the box (fix pass 6:
    # a stray unconverted y=618 here previously put "HOME" nowhere near the
    # cyan box at all).
    "badge_text_x": 350,

    # Summary bubbles - x-centers only. The y is computed from
    # SUMMARY_VALUE_BOX's vertical center, same reasoning as the badge above
    # (fix pass 6: a stray unconverted y=520 previously put every bubble value
    # far from its actual bubble).
    "balance_bf":        90.0,
    "payments_received": 190.0,
    "charges_period":    300.0,
    "total_payable":     410.0,
    "payment_due_date":  510.0,

    # Generation id / footer line
    "gen_id_line":  (273.60, 245.25),
    "gen_id_line2": (273.60, 255.25),

    # Page indicator ("N of M") on PAGE 1 ONLY - top-right, next to the badge/
    # logo area. Continuation pages use CONT_PAGE_COORDS below instead (per
    # section 9.1's golden evidence, they have their own minimal layout).
    # y=95 (fix pass 6): the banner's actual bottom edge measures at y~=80.64
    # (detected directly from the raster template - a blue-to-white pixel
    # scan at several x positions all agreed on this value); the previous
    # y=83.25 put the indicator's own text bbox (73.6-85.9) straddling that
    # edge, overlapping the banner. 95 clears it with a real margin.
    "page_indicator": (510.0, 94.0),

    # Barcodes / QR (address section)
    "barcode":       (387.0, 177.85),
    "barcode_width": 80.16,
    "barcode_height": 14.40,
    "payonline_qr":  (497, 105),
    "payonline_qr_size": 48.0,
    "qr_code": (511.20, 707),
    "qr_size": 48.0,

    # Payment slip (bottom of page)
    "slip_barcode":        (309.0, 707.25),
    "slip_barcode_width":  138.0,
    "slip_barcode_height": 25.0,
    "slip_telephone": (157.68, 723.61),
    "slip_invoice":   (157.68, 746.41),
    "slip_customer":  (157.68, 770.21),
    "slip_account":   (157.68, 795.01),
}

# RED-flagged bills use layout_RED.pdf as page 1's background instead of
# layout_NONRED.pdf (see renderer.py's render()) - the arrears/credit-control
# notice is baked directly into that artwork (not drawn by this code), sitting
# just above the payment slip. RED_PAGE1_FLOOR is that notice box's measured
# top edge (pixel-scanned off layout_RED.pdf, converted to this file's point
# system: 638.3, with a small margin) - page 1's charges/usage content must
# stop above this floor for RED bills instead of the usual CONTENT_FLOOR
# (which assumes the NONRED background's empty space all the way to the
# slip); whatever doesn't fit spills onto page 2+ via the normal overflow
# path, same mechanism as any other page break.
RED_PAGE1_FLOOR = 630.0

# Cyan badge box and summary-bubble value area, measured directly off the
# raster template (fix pass 6) via a pixel color-transition scan - not
# estimated. Text in both is vertically centered using CAP_HEIGHT_RATIO
# (renderer.py), never a separately-stored, driftable y.
BADGE_BOX = {"x0": 266.2, "y0": 213.6, "x1": 478.8, "y1": 237.2}

# The value half of each summary bubble (below the trilingual label / divider
# line, above the bubble's own bottom border) - same y-band for all 5
# bubbles, only x differs (see COORDS above).
SUMMARY_VALUE_BOX = {"y0": 314.9, "y1": 339.15}

# Measured inner width of one summary bubble (border-to-border). Used to
# auto-shrink large values (e.g. multi-million-rupee corporate accounts)
# instead of letting them overflow - general fix, not a one-off font size.
SUMMARY_BUBBLE_WIDTH = 84.5
SUMMARY_BUBBLE_SAFE_WIDTH = 76.0  # inner width minus a small margin each side
SUMMARY_BUBBLE_MIN_SIZE = 7.0

# Helvetica-Bold's standard CapHeight-to-em ratio (AFM metrics: 718/1000).
# Digits align to cap height in this font, so this also centers numeric
# bubble values correctly, not just all-caps badge text.
CAP_HEIGHT_RATIO = 0.718

FONTS = {
    "header":          {"size": 11,  "bold": True},
    "account_details": {"size": 9,   "bold": False},
    "customer_name":   {"size": 9.5, "bold": True},
    "customer_addr":   {"size": 9.5, "bold": True},
    "badge":           {"size": 15,  "bold": True},
    "summary_box":     {"size": 9,   "bold": False},
    "summary_total":   {"size": 9,   "bold": True},
    "product_label":   {"size": 9.5, "bold": True},
    "charge_line":     {"size": 9,   "bold": False},
    "taxes_header":    {"size": 9.5, "bold": True},
    "taxes_line":      {"size": 9,   "bold": False},
    "taxes":           {"size": 9,   "bold": False},
    "total":           {"size": 9.5, "bold": True},
    "payments_header": {"size": 7.5, "bold": True},
    "payments_line":   {"size": 7,   "bold": False},
    "payments":        {"size": 7,   "bold": False},
    "slip":            {"size": 8,   "bold": False},
    "gen_id":          {"size": 7,   "bold": False},
    "page_indicator":  {"size": 9,   "bold": False},
    "invoice_no_p2":   {"size": 10,  "bold": True},
}

# Charge groups, adjustments/discounts, and Taxes & Levies (everything BEFORE
# "Total Charges for the Period") are single full-width content, matching
# vat_enterprise's pattern for this same section - section 9.2's fix. Only the
# content AFTER Total Charges uses the narrow two-column reflow below.
FULL_WIDTH = {"x_start": 43.0, "x_end": 553.0, "amount_x": 553.0}

# Two-column continuous reflow (section 4) - vat_home-specific, vat_enterprise
# has no equivalent (its post-total-charges flow is a different, simpler shape).
# Only used from "Total Charges for the Period" onward (section 9.2).
FLOW_COLUMNS = {
    "left":  {"x_start": 43.0,  "x_end": 290.0, "amount_x": 285.0},
    "right": {"x_start": 313.0, "x_end": 555.0, "amount_x": 550.0},
    "vert_line_x": 300.0,
}

# Content-area y bounds. PAGE1_CONTENT_TOP matches the measured bottom edge of
# "DETAILS OF CHARGES FOR THE PERIOD" on this template (~y=358-368, independently
# confirmed against the doc's own golden-derived estimate of y=370).
# CONTENT_FLOOR is the y just above the legal disclaimer on page 1 ("This
# electric form...", measured at y~=691.7).
PAGE1_CONTENT_TOP = 395.0
CONTENT_FLOOR = 685.0

# Continuation pages (section 9.1, golden evidence from VAT_HOME.pdf page 197):
# a PLAIN WHITE PAGE - do NOT repaint layout.pdf's background at all. Only
# "Invoice No.<x>" (top-left) and "<n> of <m>" (top-right, right-aligned to the
# page margin) are stamped; content starts below that. These coordinates are
# decoupled from layout.pdf entirely, per the golden page 197 extraction:
#   x=43.2,  y=47.7  -> "Invoice No.<invoice_number>"
#   x=511.2, y=45.4  -> "<n>" ... "of" ... "<m>" (right-aligned to x=553)
#   first content line on golden page 197 sits at y~=98.1
CONT_PAGE_INVOICE_NO = (43.2, 47.7)
CONT_PAGE_PAGE_INDICATOR_X = 553.0
CONT_PAGE_PAGE_INDICATOR_Y = 45.4
CONT_PAGE_CONTENT_TOP = 70.0
CONT_PAGE_CONTENT_FLOOR = 800.0

LINE_HEIGHT = 10.0
