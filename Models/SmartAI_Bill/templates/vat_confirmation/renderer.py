import io
import os
import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit
from pypdf import PdfReader, PdfWriter
from . import config

def wrap(text, font, size, max_width):
    return simpleSplit(text, font, size, max_width)

def draw_justified_line(c, text, font, size, x, y, width):
    words = text.split()
    if len(words) <= 1:
        c.drawString(x, y, text)
        return
    word_width_total = sum(c.stringWidth(w, font, size) for w in words)
    gap = (width - word_width_total) / (len(words) - 1)
    cx = x
    for word in words:
        c.drawString(cx, y, word)
        cx += c.stringWidth(word, font, size) + gap

def build_overlay(record, page_number, today_str):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(config.PAGE_WIDTH, config.PAGE_HEIGHT))
    max_width = config.PAGE_WIDTH - config.X_BODY - config.RIGHT_MARGIN

    def y_from_top(y_top):
        return config.PAGE_HEIGHT - y_top

    c.setFont(config.FONT_BODY, config.SIZE_BODY)
    c.drawString(config.X_DATE, y_from_top(config.Y_DATE), f"Date: {today_str}")

    c.setFont(config.FONT_BOLD, config.SIZE_BODY)
    y = config.Y_RECIPIENT_START
    address_lines = record.get("address_lines", [])
    if isinstance(address_lines, str):
        address_lines = [address_lines]

    for line in address_lines:
        c.drawString(config.X_RECIPIENT, y_from_top(y), line)
        y += config.RECIPIENT_LINE_HEIGHT

    y = (y - config.RECIPIENT_LINE_HEIGHT) + config.GAP_RECIPIENT_TO_TO
    c.setFont(config.FONT_BOLD, config.SIZE_BODY)
    c.drawString(config.X_BODY, y_from_top(y), f"To:  {record.get('recipient_name', '')}")
    y += config.TO_OUR_REF_VAT_LINE_HEIGHT
    c.drawString(config.X_BODY, y_from_top(y), f"Our Reference:  {record.get('reference', '')}")
    y += config.TO_OUR_REF_VAT_LINE_HEIGHT
    c.drawString(config.X_BODY, y_from_top(y), f"VAT No.:  {record.get('vat_no', '')}")

    y += config.GAP_VAT_TO_SUBJECT
    c.setFont(config.FONT_BOLD, config.SIZE_BODY)
    c.drawString(config.X_BODY, y_from_top(y), config.SUBJECT_LINE)

    y += config.GAP_SUBJECT_TO_SALUTATION
    c.setFont(config.FONT_BODY, config.SIZE_BODY)
    c.drawString(config.X_BODY, y_from_top(y), config.SALUTATION)
    y += config.GAP_SALUTATION_TO_BODY

    for para in config.BODY_PARAGRAPHS:
        text = para.format(
            deadline=config.VERIFICATION_DEADLINE,
            email=config.VERIFICATION_EMAIL,
        )
        bold = text.startswith("Email address:")
        font = config.FONT_BOLD if bold else config.FONT_BODY
        c.setFont(font, config.SIZE_BODY)
        lines = wrap(text, font, config.SIZE_BODY, max_width)
        for i, line in enumerate(lines):
            is_last_line = i == len(lines) - 1
            if is_last_line:
                c.drawString(config.X_BODY, y_from_top(y), line)
            else:
                draw_justified_line(c, line, font, config.SIZE_BODY, config.X_BODY, y_from_top(y), max_width)
            y += config.BODY_LINE_HEIGHT
        y += config.PARAGRAPH_EXTRA_GAP

    c.setFont(config.FONT_BODY, config.SIZE_BODY)
    c.drawString(config.X_BODY, y_from_top(y), config.CLOSING)
    y += config.GAP_CLOSING_TO_SIGNOFF
    c.setFont(config.FONT_BOLD, config.SIZE_BODY)
    c.drawString(config.X_BODY, y_from_top(y), config.SIGN_OFF)

    c.setFont(config.FONT_BOLD, config.SIZE_FOOTER)
    c.drawRightString(config.X_PAGE_NUMBER_RIGHT, y_from_top(config.Y_PAGE_NUMBER), str(page_number))

    c.save()
    buf.seek(0)
    return buf

class VATConfirmationRenderer:
    def __init__(self, template_dir=None):
        self.template_dir = template_dir or config.BASE_DIR
        self.data = None

    def render(self, data):
        self.data = data
        return self

    def save(self, output_path):
        if self.data is None:
            raise ValueError("No data passed to VATConfirmationRenderer.render() before calling save()")
        record = self.data[0] if isinstance(self.data, list) and self.data else self.data
        return self.generate_pdf(record, output_path)

    def generate_pdf(self, record, output_path):
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        today_str = datetime.date.today().strftime(config.DATE_FORMAT)
        page_number = config.START_PAGE_NUMBER
        
        overlay_buf = build_overlay(record, page_number, today_str)
        overlay_page = PdfReader(overlay_buf).pages[0]

        if os.path.exists(config.TEMPLATE_PDF):
            base = PdfReader(config.TEMPLATE_PDF)
            base_page = base.pages[0]
            base_page.merge_page(overlay_page)

            writer = PdfWriter()
            writer.add_page(base_page)
            with open(output_path, "wb") as f_out:
                writer.write(f_out)
        else:
            with open(output_path, "wb") as f_out:
                f_out.write(overlay_buf.getvalue())

        return output_path
