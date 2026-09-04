# config.py
"""
VAT Credit Note Template Configuration
BILLSTYLE = 6
"""

# Page size (A4)
PAGE_W = 595.5
PAGE_H = 842.25


# --------------------------------------------------
# Font Configuration
# --------------------------------------------------

FONTS = {
    "header": {
        "size": 8,
        "bold": False
    },
    "title": {
        "size": 11,
        "bold": True
    },
    "summary": {
        "size": 9,
        "bold": False
    },
    "adjustment_sub_heading": {
        "size": 9,
        "bold": True
    },
    "adjustment_desc": {
        "size": 9,
        "bold": False
    },
    "adjustment": {
        "size": 9,
        "bold": False
    },
    "address": {
        "size": 9,
        "bold": False
    },
    "total_row": {
        "size": 9,
        "bold": True
    },
    "footer": {
        "size": 7,
        "bold": False
    }
}


# --------------------------------------------------
# Fixed Coordinates
# --------------------------------------------------

COORDS = {

    # Document title
    "document_title": (45, 755),


    # Header fields
    "account_number": (165, 735),
    "invoice_number": (155, 705),
    "billing_date":   (170, 677),
    "bill_period":    (145, 648),


    # VAT information below address
    "below_address_line1": (310, 600),
    "below_address_line2": (310, 590),


    # Extra information lines
    "header_extra_line1": (45, 615),
    "header_extra_line2": (45, 607),


    # Summary boxes
    "balance_bf":        (80, 522),
    "payments_received": (190, 522),
    "arrears":           (295, 522),
    "adjustment_value":  (405, 522),
    "total_payable":     (510, 522),


    # --------------------------------------------------
    # Main Barcode Configuration
    # Account Number Barcode
    # --------------------------------------------------

    "barcode": (375, 655),
    "barcode_width": 100,
    "barcode_height": 20,
}



# --------------------------------------------------
# Customer Address Box
# --------------------------------------------------

ADDRESS_BOX = {

    "x": 286,
    "y": 725,

    "line_h": 11,

    "font_size": 9
}



# --------------------------------------------------
# Adjustment Details Table
# --------------------------------------------------

ADJUSTMENT_TBL = {

    "desc_x": 50,

    "desc_max_x": 480,

    "amount_x": 550,


    "y_start": 450,

    "y_min": 100,


    "line_h": 11,


    "font_size": 9,

    "min_font": 7,


    "indent": 12
}



# --------------------------------------------------
# Charge Period Total Position
# --------------------------------------------------

CHARGE_PERIOD_X = 550
CHARGE_PERIOD_Y = 376