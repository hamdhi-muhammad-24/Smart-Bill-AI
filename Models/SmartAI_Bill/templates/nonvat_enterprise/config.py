"""NonVAT Enterprise (Sheet 19) - Coordinates."""

COORDS = {
    "gen_id_line":      (273, 593),
    "gen_id_line2":     (273, 583),
    "telephone_number":     (175, 728),
    "account_number":       (155, 701),
    "invoice_number":       (155, 672),
    "billing_date":         (155, 643),
    "billing_period":       (148, 618),

    "customer_business":    (280, 725),
    "customer_addr_start":  715,
    "customer_addr_x":      280,
    "customer_addr_line_h": 11,

    # ENTERPRISE badge
    "badge_text":           (330, 615),

    # Summary boxes
    "balance_bf":           (85, 514),
    "payments_received":    (190, 514),
    "charges_period":       (295, 514),
    "total_payable":        (408, 514),
    "payment_due_date":     (510, 514),

    # Taxes & Total
    "taxes_label":          (45, 250),
    "taxes_amount":         (553, 250),
    "taxes_line_h":         12,

    "total_charges_label_x":  43,
    "total_charges_label_y":  255,
    "total_charges_amount_x": 553,

    "payments_header_x":      50,
    "payments_header_y":      240,
    "payments_row_x":         50,
    "payments_row_start_y":   233,
    "payments_amount_x":      288,
    "payments_line_h":        10,
    "payments_total_label":   "Total Payments Received",

    # Page indicators
    "page_indicator_p1":    (542, 752),
    "page_indicator_p2":    (536, 780),
    "page_invoice_no_p2":   (45, 780),

    # Barcode
    "barcode":              (375, 645),
    "barcode_width":        100,
    "barcode_height":       20,

    "qr_code":       (511.2, 92),
    "qr_size":       48,

    "payonline_qr":       (498, 695),
    "payonline_qr_size":  48,

    "slip_barcode":        (310, 110),
    "slip_barcode_width":  138,
    "slip_barcode_height": 25,
    "slip_telephone":       (157, 120),
    "slip_invoice":         (157, 100),
    "slip_customer":        (157, 77),
    "slip_account":         (157, 54),
}

CHARGES_TABLE = {
    "page1_y_start":       464,
    "page1_y_min":         165.0,
    "otherpage_y_start":   740.0,
    "otherpage_y_min":     80,


    "line_h":              9,
    "font_size":           9,
    "product_label_x":     45,
    "product_label_y_gap": 15,
    "desc_x":              70,
    "desc_max_x":          500,
    "amount_x":            553,
}

FONTS = {
    "header":         {"size": 9,   "bold": False},
    "customer_name":  {"size": 9.5, "bold": True},
    "customer_addr":  {"size": 9,   "bold": True},
    "badge":          {"size": 15,  "bold": True},
    "summary_box":    {"size": 10,  "bold": False},
    "summary_total":  {"size": 10,  "bold": True},
    "product_label":  {"size": 9,   "bold": True},
    "charge_line":    {"size": 8,   "bold": False},
    "taxes":          {"size": 9,   "bold": False},
    "total":          {"size": 10,  "bold": True},
    "payments":       {"size": 8,   "bold": False},
    "slip":           {"size": 8,   "bold": False},
    "gen_id":         {"size": 8,   "bold": False},
    "page_indicator": {"size": 9,   "bold": False},
    "invoice_no_p2":  {"size": 10,  "bold": True},
}

POST_TC_COLUMNS = {
    "left":  {"x_start": 45, "x_end": 300, "amount_x": 295},
    "right": {"x_start": 315, "x_end": 555, "amount_x": 550},
    "vert_line_x": 308,
}
