"""
NonVAT Print Template Coordinates & Configuration.
Based on the coordinate specifications for Print_RED.pdf and Print_NONRED.pdf (A4: 595.28 x 841.89 pt).
Coordinate mapping: Top-left origin in JSON converted to ReportLab bottom-left origin (y_rl = 841.89 - y_topleft).
"""

PAGE_W = 595.28
PAGE_H = 841.89

# Exact coordinates provided by the specification
COORDS = {
    # Header Section (Row 1: Telephone Number, Row 2: Account Number & Billing Date, Row 3: Invoice Number & Billing Period)
    "telephone_number": (180.0, 728.0),
    "account_number":   (140.0, 696.0),
    "billing_date":     (355.0, 696.0),
    "invoice_number":   (140.0, 670.0),
    "billing_period":   (355.0, 670.0),

    # Badge box (HOME / ENTERPRISE) and TIN numbers above it
    "badge_text":       (410.0, 723.0),   # centre of the blue badge box
    "customer_tin":     (355.0, 752.0),   # Customer TIN: above the badge
    "slt_tin":          (355.0, 742.0),   # SLT TIN: between customer TIN and badge

    # Summary Section (5 horizontal boxes)
    "balance_bf":             (80.0, 593.0),
    "payments_received":      (170.0, 593.0),
    "charges_for_the_period": (260.0, 593.0),
    "total_payable":          (350.0, 593.0),
    "payment_due_date":       (437.0, 593.0),

    # Payment Slip Section (Bottom of Page 1)
    "slip_telephone": (158.0, 121.0),
    "slip_invoice":   (158.0, 97.0),
    "slip_customer":  (158.0, 74.0),
    "slip_account":   (158.0, 51.0),

    # Page 2 Address Block (Envelope Window)
    "address_block_x": 90.0,    # Left margin for address
    "address_block_y": 184.25,  # 841.89 - 657.64
    "address_line_height": 12,  # Spacing between address lines

    # Page indicators - Consistent positioning
    "page_indicator_p1":  (542.0, 753.0),   # Top-right corner of header
    "page_indicator_p2":  (542.0, 780.0),   # Top-right corner of continuation page
    "page_invoice_no_p2": (45.0, 780.0),    # Top-left corner of continuation page
    
    # Page 2 Customer Name (for top of page 2)
    "page2_customer_name": (45.0, 780.0),   # Top-left area
}

CHARGES_TABLE = {
    "page1_y_start":       548.0,  # Below 'DETAILS OF CHARGES FOR THE PERIOD' header
    "page1_y_min":         150.0,  # Buffer before payment slip on non-red
    "otherpage_y_start":   750.0,
    "otherpage_y_min":     80.0,
    "line_h":              9,
    "font_size":           8.5,
    "product_label_x":     45.0,
    "product_label_y_gap": 12,
    "desc_x":              65.0,
    "desc_max_x":          490.0,
    "amount_x":            545.0,
    "total_charges_label_x": 45.0,
    "total_charges_amount_x": 545.0,
}

FONTS = {
    "header":         {"size": 9,   "bold": False},
    "badge":          {"size": 14,  "bold": True},
    "tin":            {"size": 7.5, "bold": False},
    "customer_name":  {"size": 9,   "bold": True},
    "summary_box":    {"size": 9,   "bold": False},
    "summary_total":  {"size": 9.5, "bold": True},
    "product_label":  {"size": 9,   "bold": True},
    "charge_line":    {"size": 8.5, "bold": False},
    "taxes":          {"size": 7.5, "bold": False},  # Reduced from 8.5
    "total":          {"size": 9,   "bold": True},
    "payments":       {"size": 7.5, "bold": False},  # Reduced from 8
    "slip":           {"size": 8,   "bold": False},  # Reduced from 9
    "page_indicator": {"size": 9,   "bold": False},
    "invoice_no_p2":  {"size": 9,   "bold": True},   # Reduced from 10
    "address":        {"size": 9,   "bold": False},
    "page2_header":   {"size": 10,  "bold": True},
}

POST_TC_COLUMNS = {
    "left": {
        "x_start": 56.69,
        "x_end":   288.0,
    },
    "right": {
        "x_start": 306.0,
        "x_end":   538.58,
    },
    "vert_line_x": 297.0,
}