# config.py - USD Open Item (BILLSTYLE=21)
#
# Bottom-origin (reportlab/BaseRenderer convention, same as vat_enterprise -
# this renderer extends core.pdf_renderer.BaseRenderer, not the fitz-based
# renderer vat_home uses). PAGE_W/H confirmed against layout.pdf.
#
# No golden reference PDF is available for this bill type (no equivalent of
# vat_enterprise's/vat_home's golden PDFs was provided) - coordinates below
# are calibrated directly against the rasterized layout.pdf template and the
# CLAUDE.md condensed rule-set (usd_open_item.xlsx itself is not present in
# this repo either). Flagged in BUILD_NOTE.md as needing recalibration if a
# golden reference ever becomes available.

PAGE_W = 595.5
PAGE_H = 842.25

COORDS = {
    # Header fields - measured directly from the raster template (300 DPI
    # crop, row-center pixel measurement); the previous values (718/697/676/
    # 656/636) sat 5-6pt too high, landing each value on the divider line
    # above its intended row instead of inside it (confirmed by rendering
    # and visually inspecting the struck-through text before this fix).
    "account_number":   (220, 708),
    "invoice_number":   (206, 688),
    "billing_date":     (220, 668),
    "bill_period":      (205, 648),
    "invoice_amount":   (220, 625),
    "payment_due_date": (462, 625),

    # Contact lines (filename string + customer segment, under the address box)
    "contact_line1":    (285, 598),
    "contact_line2":    (285, 588),

    # Main barcode (account/invoice area)
    "barcode": (450, 650),
    "barcode_width": 100,
    "barcode_height": 20,

    # Footer barcode/QR - placed in the blank space to the right of the
    # remittance box, above the dashed separator line (measured: dashed line
    # sits at approximately bottom-origin y=127).
    "bottom_barcode": (300, 95),
    "bottom_barcode_width": 150,
    "bottom_barcode_height": 20,

    "bottom_qr": (502, 60),
    "bottom_qr_size": 50,

    # Page indicator ("Page N of M") - top-right, clear of the xyntac logo,
    # matching the general vat_enterprise/vat_home footer-mechanics pattern
    # adapted to this layout's blank zone.
    "page_indicator": (555, 790),
}

# Dynamic Address Box Configuration (top-right rounded box)
ADDRESS_BOX = {
    # Box border measured directly from layout.pdf (300 DPI crop): top border
    # at bottom-origin y=~753, bottom border at y=~641 (height ~112pt). The
    # previous y=750/line_h=11 put the first line's ascent through the top
    # border (confirmed strikethrough on real GMF render, "To Goparani R").
    # y_start=740/line_h=9.5 keeps all 11 possible lines clear of both borders.
    "x": 315,         # X position for all address lines
    "y": 740,         # Starting Y position (first line)
    "line_h": 9.5,    # Vertical spacing between lines
    "font_size": 8,   # Font size
    "bold": True,     # Draw address in bold
    "max_lines": 11   # Total address lines
}

# Address field print order - CLAUDE.md's own spec text lists these in plain
# numeric order (ADDRESSNAME, POSITION, DEPARTMENT, BUSINESSNAME, ADDRESS1
# through ADDRESS5, ZIPCODE, COUNTRY) - NOT the BPR13 (5,2,3,4,1) reordering
# used by vat_enterprise/vat_home/nonvat_home. Kept as its own explicit list
# here rather than reusing core.bill_common.ADDRESS_PRINT_ORDER, since this
# bill type's own spec text is explicit about the order and it differs.
ADDRESS_FIELD_ORDER = [
    'ADDRESSNAME', 'POSITION', 'DEPARTMENT', 'BUSINESSNAME',
    'ADDRESS1', 'ADDRESS2', 'ADDRESS3', 'ADDRESS4', 'ADDRESS5',
    'ZIPCODE', 'COUNTRY',
]

# Charges / Discounts / Adjustments / Total / Alt-currency / Usage / Marketing
# / Rednotice - one shared vertical-cursor column (single-column layout per
# section 1.3 - no two-column flow needed, unlike vat_home).
CHARGES_TBL = {
    "amount_x": 540,
    "y_start": 520,
    "y_min": 175,   # just above the footer's dashed separator (~y=127) with margin
    "line_h": 10,
    "font_size": 8,
    "min_font": 7,

    "indent_l1": 38,   # "Subscription Ref: X" / section headers (Discounts, etc.)
    "indent_l2": 46,   # SLTPRODUCTLABEL sub-group
    "indent_l3": 54,   # individual charge/discount/adjustment lines

    "otherpage_y_start": 780,
    "otherpage_y_min":   80,
}

# Usage/itemization tables (EVENTHEADING_xx pattern) - column math ported
# from vat_home's generic table helpers (pure functions, reused directly per
# sub-agent C's audit), just re-targeted at this single-column layout instead
# of vat_home's two-column FLOW_COLUMNS.
USAGE_TABLE = {
    "x_start": 54,
    "amount_x": 540,
}

TOTAL_AMOUNT_X = 540
TOTAL_AMOUNT_Y = 270
