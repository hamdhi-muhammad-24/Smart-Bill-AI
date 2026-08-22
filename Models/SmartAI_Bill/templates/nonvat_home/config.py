"""NonVAT Home (Sheet 19) - Coordinates."""

COORDS = {
    # Header
    "gen_id_line": (273, 590),
    "gen_id_line2": (273, 580.4),
    "telephone_number":     (175, 726),
    "account_number":       (155, 701),
    "invoice_number":       (155, 672),
    "billing_date":         (155, 643),
    "billing_period":       (150, 615),

    # Customer block
    "customer_name":        (280, 722),
    "customer_addr_start":  715,
    "customer_addr_x":      280,
    "customer_addr_line_h": 11,

    # HOME badge
    "badge_text":           (345, 612),

    # Summary boxes
    "balance_bf":           (85, 512),
    "payments_received":    (190, 512),
    "charges_period":       (295, 512),
    "total_payable":        (408, 512),
    "payment_due_date":     (510, 512),

    # Page indicators
    "page_indicator_p1":    (536, 751),
    "page_indicator_p2":    (536, 780),
    "page_invoice_no_p2":   (45, 780),


    "total_charges_label_x":  43,
    "total_charges_label_y":  220,
    "total_charges_amount_x": 553,

    "payments_header_x":      50,
    "payments_header_y":      200,
    "payments_row_x":         50,
    "payments_row_start_y":   190,
    "payments_amount_x":      288,
    "payments_line_h":        10,
    "payments_total_label":   "Total Payments Received",

    "usage_header_x":         306,
    "usage_header_y":         202,
    "usage_subsection_x":     306,
    "usage_subsection_y":     194,

    "usage_rows_start_y":     170,
    "usage_col_x":            [306, 390, 445],
    "usage_amount_x":         535,
    "usage_row_limit":        2,
    "usage_row_line_h":       9,


    # QR + Barcode
    "barcode":              (375, 638),
    "barcode_width":        100,
    "barcode_height":       20,

    "qr_code":              (511.2, 88.4),
    "qr_size":              48,
    "payonline_qr":         (498, 689),
    "payonline_qr_size":    48,

    "slip_barcode":         (309, 110),
    "slip_barcode_width":   138,
    "slip_barcode_height":  25,
    "slip_telephone":       (157, 120),
    "slip_invoice":         (157, 97),
    "slip_customer":        (157, 75),
    "slip_account":         (157, 50),
}

CHARGES_TABLE = {
    "page1_y_start":       467,
    "page1_y_min":         165.0,
    "otherpage_y_start":   740.0,
    "otherpage_y_min":     80,


    "line_h":              8,
    "font_size":           8,
    "product_label_x":     45,
    "product_label_y_gap": 12,
    "desc_x":              70,
    "desc_max_x":          500,
    "amount_x":            553,
}

FONTS = {
    "header":         {"size": 9,   "bold": False},
    "customer_name":  {"size": 9.5, "bold": True},
    "customer_addr":  {"size": 9,   "bold": True},
    "badge":          {"size": 18,  "bold": True},
    "summary_box":    {"size": 10,  "bold": False},
    "summary_total":  {"size": 10,  "bold": True},
    "product_label":  {"size": 9,   "bold": True},
    "charge_line":    {"size": 8,   "bold": False},
    "taxes":          {"size": 8,   "bold": False},
    "total":          {"size": 10,  "bold": True},
    "payments":       {"size": 8,   "bold": False},
    "slip":           {"size": 8,   "bold": False},
    "gen_id":         {"size": 7,   "bold": False},
    "page_indicator": {"size": 9,   "bold": False},
    "invoice_no_p2":  {"size": 10,  "bold": True},
}

POST_TC_COLUMNS = {
    "left":  {"x_start": 45, "x_end": 300, "amount_x": 295},
    "right": {"x_start": 315, "x_end": 555, "amount_x": 550},
    "vert_line_x": 308,
}
