import barcode
from barcode.writer import ImageWriter
from io import BytesIO


def generate_barcode(value: str):
    clean_value = value.replace(" ", "")

    Code128 = barcode.get_barcode_class('code128')
    assert Code128 is not None, "Barcode class code128 not found"
    bc = Code128(clean_value, writer=ImageWriter())

    buf = BytesIO()
    bc.write(buf, options={
        'module_width': 0.3,
        'module_height': 8,
        'font_size': 6,
        'text_distance': 2,
        'quiet_zone': 2,
        'write_text': False,
    })
    buf.seek(0)
    return buf


def generate_slip_barcode(bill_ref: str, total_charges: float):
    clean_ref = bill_ref.replace(" ", "")
    barcode_value = f"{clean_ref}{total_charges:.2f}"

    Code128 = barcode.get_barcode_class('code128')
    assert Code128 is not None, "Barcode class code128 not found"
    bc = Code128(barcode_value, writer=ImageWriter())

    buf = BytesIO()
    bc.write(buf, options={
        'module_width': 0.3,
        'module_height': 8,
        'font_size': 6,
        'text_distance': 2,
        'quiet_zone': 2,
        'write_text': False,
    })
    buf.seek(0)
    return buf