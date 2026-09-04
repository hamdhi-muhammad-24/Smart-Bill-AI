COORDS = {
    "tax_invoice_label":      (43.2, 748.2),
    "slt_vat_reg_label":      (273.6, 748.2),
    "customer_vat_reg_label": (273.6, 739.5),

    "gen_id_line": (273, 592),
    "gen_id_line2": (273, 584.4),

    "account_number":       (155, 705),
    "invoice_number":       (155, 674),
    "billing_date":         (155, 646),
    "billing_period":       (150, 618),

    "customer_name":        (280, 725),
    "customer_business":    (280, 715),
    "customer_addr_start":  705,
    "customer_addr_x":      280,
    "customer_addr_line_h": 11,

    "badge_text":           (325, 614),

    "balance_bf":           (83, 514),
    "payments_received":    (188, 514),
    "charges_period":       (293, 514),
    "total_payable":        (406, 514),
    "payment_due_date":     (508, 514),

    "taxes_label":          (43.2, 300),
    "taxes_amount":         (553, 300),
    "taxes_line_h":         11,
    "total_charges_label":  (43.2, 239),
    "total_charges_amount": (553, 239),

    "payments_start":       (50, 220),
    "payments_amount_x":    288,
    "payments_line_h":      10,

    "barcode":              (372, 642),
    "barcode_width":        100,
    "barcode_height":       20,

    "qr_code":       (512, 92),
    "qr_size":       48,

    "payonline_qr":       (498, 692),
    "payonline_qr_size":  48,

    "slip_barcode": (309, 110),
    "slip_barcode_width": 138,
    "slip_barcode_height": 25,
    "slip_telephone":       (157, 122),
    "slip_invoice":         (157, 100),
    "slip_customer":        (157, 78),
    "slip_account":         (157, 52),
}

# 3-level hierarchy: subscription_ref → product_label → charges
CHARGES_TABLE = {
    "page1_y_start":            472,
    "page1_y_min":              330,
    "otherpage_y_start":        780,
    "otherpage_y_min":          80,

    "line_h":                   11,
    "font_size":                9,

    "subscription_ref_x":       43.2,
    "product_label_x":          50.4,
    "product_label_y_gap":      15,
    "desc_x":                   57.6,
    "desc_max_x":               500,
    "amount_x":                 553,
    "subtotal_indent":          65,

    # Vertical divider drawn next to the payments block - x position of the
    # rule, matching product_label_grouping's/vat_enterprise's convention.
    "vert_line_x":              308,

    # Page-1 floor for the payments block specifically - NOT the same as
    # page1_y_min (330), which is the charges/subscription-ref section's
    # floor. Payments was historically fixed at y=220, well below 330. The
    # real physical limit is the payment-slip footer (slip_customer/
    # slip_account sit at y=75/50) - 90 stays clear of that while still
    # leaving genuine room for a realistic number of payment rows (a
    # higher value like 150 was tried first but proved too conservative:
    # a normal 4-tax-line bill plus a payment row needs to reach lower
    # than that to avoid a spurious page break).
    "payments_y_min":           90,

    # Page-1 floor for Taxes & Levies / Total Charges specifically - NOT
    # page1_y_min (330) either. These were historically fixed at y=300 and
    # y=239 respectively. 200 (tried first) was still too high: a normal
    # bill with 4 tax lines (CESS, SSCL, Telecom Levy, VAT) plus Total
    # Charges needs to reach further down than that before handing off to
    # the payments block below it. 140 leaves genuine room while staying
    # clear of payments_y_min (90).
    "taxes_total_y_min":        140,
}

FONTS = {
    "header":            {"size": 9,   "bold": False},
    "customer_name":     {"size": 9.5, "bold": True},
    "customer_addr":     {"size": 9,   "bold": True},
    "badge":             {"size": 18,  "bold": True},
    "summary_box":       {"size": 10,  "bold": False},
    "summary_total":     {"size": 10,  "bold": True},
    "subscription_ref":  {"size": 10,  "bold": True},
    "product_label":     {"size": 9,   "bold": True},
    "charge_line":       {"size": 9,   "bold": False},
    "subtotal":          {"size": 9,   "bold": True},
    "top_subtotal":      {"size": 9,   "bold": True},
    "taxes":             {"size": 9,   "bold": False},
    "total":             {"size": 10,  "bold": True},
    "payments":          {"size": 8,   "bold": False},
    "slip":              {"size": 8,   "bold": False},
    "gen_id":            {"size": 8,   "bold": False},
}