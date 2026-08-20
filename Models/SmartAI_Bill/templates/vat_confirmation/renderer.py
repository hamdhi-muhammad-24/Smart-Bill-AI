"""
VAT Confirmation Renderer.
Generates standalone PDF letters by drawing ReportLab text overlays onto template.pdf.
"""
import io
import os
import re
import datetime

from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit
from pypdf import PdfReader, PdfWriter

from templates.vat_confirmation import config

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PDF_PATH = os.path.join(BASE_DIR, config.TEMPLATE_PDF)


def safe_filename(text):
    text = re.sub(r"[^A-Za-z0-9_-]+", "_", str(text).strip())
    return text.strip("_")[:80]


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

    # Date
    c.setFont(config.FONT_BODY, config.SIZE_BODY)
    c.drawString(config.X_DATE, y_from_top(config.Y_DATE), f"Date: {today_str}")

    # Recipient block
    c.setFont(config.FONT_BOLD, config.SIZE_BODY)
    y = config.Y_RECIPIENT_START
    address_lines = record.get("address_lines", [])
    for line in address_lines:
        c.drawString(config.X_RECIPIENT, y_from_top(y), line)
        y += config.RECIPIENT_LINE_HEIGHT

    # To / Reference / VAT No
    y = (y - config.RECIPIENT_LINE_HEIGHT) + config.GAP_RECIPIENT_TO_TO
    c.setFont(config.FONT_BOLD, config.SIZE_BODY)
    c.drawString(config.X_BODY, y_from_top(y), f"To:  {record.get('recipient_name', '')}")
    y += config.TO_OUR_REF_VAT_LINE_HEIGHT
    c.drawString(config.X_BODY, y_from_top(y), f"Our Reference:  {record.get('reference', '')}")
    y += config.TO_OUR_REF_VAT_LINE_HEIGHT
    c.drawString(config.X_BODY, y_from_top(y), f"VAT No.:  {record.get('vat_no', '')}")

    # Subject
    y += config.GAP_VAT_TO_SUBJECT
    c.setFont(config.FONT_BOLD, config.SIZE_BODY)
    c.drawString(config.X_BODY, y_from_top(y), config.SUBJECT_LINE)

    # Salutation
    y += config.GAP_SUBJECT_TO_SALUTATION
    c.setFont(config.FONT_BODY, config.SIZE_BODY)
    c.drawString(config.X_BODY, y_from_top(y), config.SALUTATION)
    y += config.GAP_SALUTATION_TO_BODY

    # Body paragraphs
    record_content = record.get("content")
    paragraphs = record_content.split('\n') if record_content else config.BODY_PARAGRAPHS
    
    for para in paragraphs:
        if not para.strip():
            continue
            
        # Support placeholders in dynamic content as well
        text = para.replace("{deadline}", config.VERIFICATION_DEADLINE).replace("{email}", config.VERIFICATION_EMAIL)
        
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

    # Closing
    c.setFont(config.FONT_BODY, config.SIZE_BODY)
    c.drawString(config.X_BODY, y_from_top(y), config.CLOSING)
    y += config.GAP_CLOSING_TO_SIGNOFF
    c.setFont(config.FONT_BOLD, config.SIZE_BODY)
    c.drawString(config.X_BODY, y_from_top(y), config.SIGN_OFF)

    # Page number
    c.setFont(config.FONT_PAGE_NUMBER, config.SIZE_FOOTER)
    c.drawRightString(config.X_PAGE_NUMBER_RIGHT, y_from_top(config.Y_PAGE_NUMBER), str(page_number))

    c.save()
    buf.seek(0)
    return buf


class VATConfirmationRenderer:
    """
    Renderer class conforming to SmartAI_Bill BaseRenderer interface.
    """
    def __init__(self):
        self.generated_pdfs = [] # list of (output_filename, pdf_bytes, record)

    def render(self, data):
        if isinstance(data, list):
            records = data
        else:
            records = data.get("records", [])
            if not records and "reference" in data:
                records = [data]

        today_str = datetime.date.today().strftime(config.DATE_FORMAT)
        page_number = config.START_PAGE_NUMBER

        self.generated_pdfs = []

        template_path = TEMPLATE_PDF_PATH
        if not os.path.exists(template_path):
            template_path = os.path.join(BASE_DIR, "template.pdf")

        used_filenames = set()
        for record in records:
            overlay_buf = build_overlay(record, page_number, today_str)
            overlay_page = PdfReader(overlay_buf).pages[0]

            base = PdfReader(template_path)
            base_page = base.pages[0]
            base_page.merge_page(overlay_page)

            writer = PdfWriter()
            writer.add_page(base_page)

            pdf_buf = io.BytesIO()
            writer.write(pdf_buf)
            pdf_bytes = pdf_buf.getvalue()

            identifier = (record.get("account_number") or record.get("reference") or record.get("vat_no") or record.get("recipient_name") or "unknown").strip()
            ref_clean = safe_filename(identifier) or "unknown"
            
            fname = f"{ref_clean}_Vat_confirmation.pdf"
            counter = 1
            while fname in used_filenames:
                counter += 1
                fname = f"{ref_clean}_{counter}_Vat_confirmation.pdf"
            used_filenames.add(fname)

            self.generated_pdfs.append((fname, pdf_bytes, record))
            page_number += 1

    def save(self, output_path):
        """
        Save all generated PDFs in self.generated_pdfs to the directory containing output_path.
        """
        if not self.generated_pdfs:
            raise RuntimeError("No PDFs generated in render()")

        out_dir = os.path.dirname(os.path.abspath(output_path))
        os.makedirs(out_dir, exist_ok=True)

        if len(self.generated_pdfs) == 1:
            fname, pdf_bytes, _ = self.generated_pdfs[0]
            target_file = output_path if output_path.lower().endswith(".pdf") else os.path.join(out_dir, fname)
            with open(target_file, "wb") as f:
                f.write(pdf_bytes)
        else:
            for fname, pdf_bytes, _ in self.generated_pdfs:
                target_file = os.path.join(out_dir, fname)
                with open(target_file, "wb") as f:
                    f.write(pdf_bytes)

