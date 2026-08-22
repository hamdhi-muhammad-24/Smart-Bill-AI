"""Product Label Level Grouping (Sheet 22, BILLSTYLE=19) - Coordinates."""

COORDS = {
    "slt_vat_reg_label":      (273.6, 748.2),
    "customer_vat_reg_label": (273.6, 739.5),

    "gen_id_line": (273, 590),
    "gen_id_line2": (273, 580.4),
    "telephone_number":     (175, 726),
    "account_number":       (155, 701),
    "invoice_number":       (155, 672),
    "billing_date":         (155, 643),
    "billing_period":       (150, 615),

    "customer_name":        (280, 724),
    "customer_addr_start":  715,
    "customer_addr_x":      280,
    "customer_addr_line_h": 11,

    "badge_text":           (345, 612),

    "balance_bf":           (85, 512),
    "payments_received":    (190, 512),
    "charges_period":       (295, 512),
    "total_payable":        (408, 512),
    "payment_due_date":     (510, 512),

    "total_charges_label_x":  43,
    "total_charges_label_y":  254,
    "total_charges_amount_x": 553,

    "payments_header_x":      50,
    "payments_header_y":      240,
    "payments_row_x":         50,
    "payments_row_start_y":   232,
    "payments_amount_x":      288,
    "payments_line_h":        10,
    "payments_total_label":   "Total Payments Received",

    # Page indicators
    "page_indicator_p1":    (536, 751),
    "page_indicator_p2":    (536, 780),
    "page_invoice_no_p2":   (45, 780),

    "barcode":              (375, 638),
    "barcode_width":        100,
    "barcode_height":       20,

    "payonline_qr":       (498, 689),
    "payonline_qr_size":  48,

    "slip_barcode":        (309, 110),
    "slip_barcode_width":  138,
    "slip_barcode_height": 25,
    "slip_telephone":       (157, 120),
    "slip_invoice":         (157, 97),
    "slip_customer":        (157, 75),
    "slip_account":         (157, 50),
}

CHARGES_TABLE = {
    "page1_y_start":         467,
    "page1_y_min":           264,
    "otherpage_y_start":     780,
    "otherpage_y_min":       80,

    "line_h":                9,
    "font_size":             8,
    "product_label_x":       45,
    "product_label_y_gap":   10,
    "desc_x":                70,
    "desc_max_x":            500,
    "amount_x":              553,
    "subtotal_x":            553,
    "subtotal_indent":       0,
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
    "subtotal":       {"size": 9,   "bold": True},
    "taxes":          {"size": 9,   "bold": False},
    "total":          {"size": 10,  "bold": True},
    "payments":       {"size": 8,   "bold": False},
    "slip":           {"size": 8,   "bold": False},
    "gen_id":         {"size": 8,   "bold": False},
    "page_indicator": {"size": 9,   "bold": False},
    "invoice_no_p2":  {"size": 10,  "bold": True},
}