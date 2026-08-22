"""Invoice of Summary (Sheet 18, BILLSTYLE=18) - Coordinates."""

COORDS = {
    "slt_vat_reg_label":      (273.6, 748.2),
    "customer_vat_reg_label": (273.6, 739.5),

    "gen_id_line":  (273, 590),
    "gen_id_line2": (273, 580.4),

    "telephone_number":     (175, 726),
    "account_number":       (155, 701),
    "invoice_number":       (155, 672),
    "billing_date":         (155, 643),
    "billing_period":       (150, 615),

    "customer_name":        (280, 725),
    "customer_business_y":  715,
    "customer_addr_start":  705,
    "customer_addr_x":      280,
    "customer_addr_line_h": 11,

    "badge_text": (330, 612),

    "balance_bf":        (85, 512),
    "payments_received": (190, 512),
    "charges_period":    (295, 512),
    "total_payable":     (408, 512),
    "payment_due_date":  (510, 512),

    "summary_x":              45,
    "summary_amount_x":       553,
    "summary_y_start":        459,
    "summary_line_h":         9,

    "total_charges_label_x":  45,
    "total_charges_label_y":  332,
    "total_charges_amount_x": 553,


    "charges_detail_y_start": 280,
    "payments_line_h": 11,

    # Barcode + QR
    "barcode":       (375, 638),
    "barcode_width": 100,
    "barcode_height": 20,

    "qr_code": (511.2, 88.4),
    "qr_size": 48,

    "payonline_qr":      (498, 689),
    "payonline_qr_size": 48,

    "slip_barcode":        (309, 110),
    "slip_barcode_width":  138,
    "slip_barcode_height": 25,
    "slip_telephone":      (157, 120),
    "slip_invoice":        (157, 97),
    "slip_customer":       (157, 75),
    "slip_account":        (157, 50),

    "usage_preview_x":         306,
    "usage_preview_y":         245,
    "usage_preview_col_x":     [306, 385, 445],
    "usage_preview_amount_x":  555,
    "usage_preview_row_limit": 3,
    "usage_preview_line_h":    9,
}

CHARGES_TABLE = {
    "page1_y_min":         150,
    "otherpage_y_start":   750,
    "otherpage_y_min":     80,

    "line_h":              12,
    "font_size":           9,

    "group_ref_x":         35,
    "product_label_x":     55,
    "product_label_y_gap": 15,
    "desc_x":              80,
    "desc_max_x":          500,
    "amount_x":            553,
}

USAGE_TABLE_2COL = {
    "left_col_x":       [45, 130, 195, 260],
    "left_amount_x":    290,
    "left_box_right":   295,

    "right_col_x":      [310, 395, 460, 525],
    "right_amount_x":   555,
    "right_box_right":  560,

    "line_h":           9,
    "font_size":        7,
    "font_header":      7,
    "page_top":         770,
    "page_bottom":      50,
}

FONTS = {
    "header":        {"size": 9,   "bold": False},
    "vat_reg":       {"size": 7.5, "bold": False},
    "customer_name": {"size": 9.5, "bold": True},
    "customer_addr": {"size": 9,   "bold": True},
    "badge":         {"size": 13,  "bold": True},
    "summary_box":   {"size": 10,  "bold": False},
    "summary_total": {"size": 10,  "bold": True},
    "group_ref":     {"size": 10,  "bold": True},
    "product_label": {"size": 9,   "bold": True},
    "charge_line":   {"size": 9,   "bold": False},
    "taxes":         {"size": 8,   "bold": False},
    "total":         {"size": 10,  "bold": True},
    "payments":      {"size": 8,   "bold": False},
    "slip":          {"size": 8,   "bold": False},
    "gen_id":        {"size": 8,   "bold": False},
}