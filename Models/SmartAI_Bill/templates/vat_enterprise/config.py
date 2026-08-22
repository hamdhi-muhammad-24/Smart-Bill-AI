"""VAT Enterprise (Sheet 18) - Coordinates and Configuration."""

PAGE_W = 595.5
PAGE_H = 842.25

COORDS = {
    # VAT Specific Headers
    # y was accidentally written in top-origin (84.8 / 76.2 from top); corrected to bottom-origin
    "slt_vat_reg":          (273.60, 758),
    "customer_vat_reg":     (273.60, 747),

    # Standard Headers (Right side)
    "telephone_number":     (180, 735),
    "account_number":       (160, 707),   # was 615.44 (landing on billing-period row)
    "invoice_number":       (155, 680),
    "billing_date":         (160, 650),
    "billing_period":       (140, 620),

    # Customer Address
    "customer_business":    (280.8, 725),
    "customer_addr_start":  725,
    "customer_addr_x":      280.8,
    "customer_addr_line_h": 11,

    # ENTERPRISE badge
    "badge_text":           (325, 618),   # was 529.04 (80pt too low)

    # Summary Box (Horizontal layout based on PDF)
    "balance_bf":        (90, 520),
    "payments_received": (190, 520),
    "charges_period":    (300, 520),
    "total_payable":     (410, 520),
    "payment_due_date":  (510, 520),

    # Taxes & Total (positioned around TOTAL_AMOUNT_Y=243)
    "taxes_label":            (45, 230),
    "taxes_amount":           (553, 230),
    "taxes_line_h":           12,

    "total_charges_label_x":  43.20,
    "total_charges_label_y":  238.64,
    "total_charges_amount_x": 553.00,

    # Payments received details on page 1 (under the total charges)
    "payments_header_x":      50.40,
    "payments_header_y":      212.96,
    "payments_row_x":         50.40,
    "payments_row_start_y":   203.36,
    "payments_amount_x":      295,
    "payments_line_h":        9.60,
    "payments_total_label":   "Total Payments Received",

    # Generation IDs / Filename footer
    "gen_id_line":          (273.60, 598),
    "gen_id_line2":         (273.60, 588),

    # Page indicators
    # p1: x=536 (right-aligned; places "1" at x≈511 = template position), y=751.2 (top of page)
    # p1 previously had y=86.96 (top-origin → drew near bottom) and x=511.2 (gave wrong x)
    "page_indicator_p1":    (536.00, 759),
    "page_indicator_p2":    (536.00, 788.00),
    "page_invoice_no_p2":   (43.20, 784.40),

    # Barcodes & QR Codes
    "barcode":              (387, 650),
    "barcode_width":        80.16,
    "barcode_height":       14.40,

    "payonline_qr":         (500.00, 697),
    "payonline_qr_size":    48.00,

    # Lanka QR Code
    "qr_code":              (511.20, 96),
    "qr_size":              48.00,

    # Payment Slip (Bottom)
    "slip_barcode":         (309.00, 116.00),
    "slip_barcode_width":   138.00,
    "slip_barcode_height":  25.00,
    # Baselines centered inside each rounded slip box (box borders sit at
    # ~113.6/133.5, ~90.3/110.0, ~67.4/86.6, ~44.0/63.3 bottom-origin) — the old
    # values sat near each box's bottom edge, so the row below's top border cut
    # through the text (and the last row's own bottom border cut through it).
    "slip_telephone":       (157.68, 127.67),  # was 116.64 / 162.24
    "slip_invoice":         (157.68, 104.23),  # was 93.84 / 139.44
    "slip_customer":        (157.68, 81.11),   # was 71.04 / 116.64
    "slip_account":         (157.68, 57.73),   # was 48.24 / 93.84
}

CHARGES_TABLE = {
    "page1_y_start":        455.40,
    "page1_y_min":          165.00, # Band floor: mask rect ends at y_top=692 → y_bottom=842.25-692≈150
    #"page1_band_mask":      (45, 127, 560, 457),  # (x0, y0, x1, y1) bottom-origin rect to mask baked labels
    "otherpage_y_start":    770,
    "otherpage_y_min":      80.00,

    "line_h":               11.04,
    "font_size":            9,
    "product_label_x":      50.40,
    "product_label_y_gap":  11.04,
    "desc_x":               57.60,
    "desc_max_x":           480.00,
    "amount_x":             553.00,
}

# Two-column layout for everything below "Total Charges for the Period"
# (payments, cancel payments, detailed usage/CDR) - section 5D.
POST_TC_COLUMNS = {
    "left":  {"x_start": 45,  "x_end": 300},   # left of the vertical divider
    "right": {"x_start": 315, "x_end": 555},   # right of the vertical divider
    "vert_line_x": 308,
}

FONTS = {
    "header":         {"size": 8, "bold": False},
    "customer_name":  {"size": 9,  "bold": True},
    "customer_addr":  {"size": 9,  "bold": True},
    "badge":          {"size": 18, "bold": True},
    "summary_box":    {"size": 11.04, "bold": False},
    "summary_total":  {"size": 11.04, "bold": True},
    "product_label":  {"size": 9, "bold": True},
    "charge_line":    {"size": 9, "bold": False},
    "taxes":          {"size": 9, "bold": False},
    "total":          {"size": 11.04, "bold": True},
    "payments":       {"size": 8.64,  "bold": False},
    "slip":           {"size": 9.60,  "bold": False},
    "gen_id":         {"size": 7,  "bold": False},
    "page_indicator": {"size": 9,  "bold": False},
    "invoice_no_p2":  {"size": 11.04, "bold": True},
}