"""
render.py
For each recipient record: draws the date/recipient block/reference/VAT
number/fixed body text as a text overlay, merges it onto a fresh copy of
template.pdf's background, and writes one standalone PDF per recipient.

Usage: python render.py
"""

import io
import os
import re
import datetime

from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit
from pypdf import PdfReader, PdfWriter

import config
from parser import load_recipients


def safe_filename(text):
    text = re.sub(r"[^A-Za-z0-9_-]+", "_", text.strip())
    return text.strip("_")[:80]


def wrap(text, font, size, max_width):
    return simpleSplit(text, font, size, max_width)


def draw_justified_line(c, text, font, size, x, y, width):
    """Stretches inter-word spacing so the line's right edge lands on x+width.
    Matches the reference PDF, which is genuinely full-justified (confirmed
    by pdfplumber word x1 coordinates lining up across wrapped lines)."""
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
    """Draws all variable + fixed text and returns a single-page PDF (BytesIO)."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(config.PAGE_WIDTH, config.PAGE_HEIGHT))
    max_width = config.PAGE_WIDTH - config.X_BODY - config.RIGHT_MARGIN

    def y_from_top(y_top):
        # convert a "distance from top of page" into PDF's bottom-left origin y
        return config.PAGE_HEIGHT - y_top

    # --- Date (fixed position, left-aligned -- NOT the same column as the
    #     recipient block, confirmed by cross-checking the reference pages) ---
    c.setFont(config.FONT_BODY, config.SIZE_BODY)
    c.drawString(config.X_DATE, y_from_top(config.Y_DATE), f"Date: {today_str}")

    # --- Recipient block (name + address lines, bold, left-aligned in the
    #     indented column) ---
    c.setFont(config.FONT_BOLD, config.SIZE_BODY)
    y = config.Y_RECIPIENT_START
    for line in record["address_lines"]:
        c.drawString(config.X_RECIPIENT, y_from_top(y), line)
        y += config.RECIPIENT_LINE_HEIGHT

    # --- To: / Our Reference: / VAT No. ---
    y = (y - config.RECIPIENT_LINE_HEIGHT) + config.GAP_RECIPIENT_TO_TO
    c.setFont(config.FONT_BOLD, config.SIZE_BODY)
    c.drawString(config.X_BODY, y_from_top(y), f"To:  {record['recipient_name']}")
    y += config.TO_OUR_REF_VAT_LINE_HEIGHT
    c.drawString(config.X_BODY, y_from_top(y), f"Our Reference:  {record['reference']}")
    y += config.TO_OUR_REF_VAT_LINE_HEIGHT
    c.drawString(config.X_BODY, y_from_top(y), f"VAT No.:  {record['vat_no']}")

    # --- Subject ---
    y += config.GAP_VAT_TO_SUBJECT
    c.setFont(config.FONT_BOLD, config.SIZE_BODY)
    c.drawString(config.X_BODY, y_from_top(y), config.SUBJECT_LINE)

    # --- Salutation ---
    y += config.GAP_SUBJECT_TO_SALUTATION
    c.setFont(config.FONT_BODY, config.SIZE_BODY)
    c.drawString(config.X_BODY, y_from_top(y), config.SALUTATION)
    y += config.GAP_SALUTATION_TO_BODY

    # --- Body paragraphs (with placeholder substitution) ---
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

    # --- Closing ---
    c.setFont(config.FONT_BODY, config.SIZE_BODY)
    c.drawString(config.X_BODY, y_from_top(y), config.CLOSING)
    y += config.GAP_CLOSING_TO_SIGNOFF
    c.setFont(config.FONT_BOLD, config.SIZE_BODY)
    c.drawString(config.X_BODY, y_from_top(y), config.SIGN_OFF)

    # --- Page number (footer disclaimer text/rule already baked into
    #     template.pdf -- only the running page number is drawn here) ---
    c.setFont(config.FONT_PAGE_NUMBER, config.SIZE_FOOTER)
    c.drawRightString(config.X_PAGE_NUMBER_RIGHT, y_from_top(config.Y_PAGE_NUMBER), str(page_number))

    c.save()
    buf.seek(0)
    return buf


def render_all():
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    records = load_recipients(config.SOURCE_CSV)
    today_str = datetime.date.today().strftime(config.DATE_FORMAT)

    page_number = config.START_PAGE_NUMBER
    written = []

    for record in records:
        overlay_buf = build_overlay(record, page_number, today_str)
        overlay_page = PdfReader(overlay_buf).pages[0]

        base = PdfReader(config.TEMPLATE_PDF)
        base_page = base.pages[0]
        base_page.merge_page(overlay_page)

        writer = PdfWriter()
        writer.add_page(base_page)

        fname = f"VAT_Letter_{safe_filename(record['reference'])}.pdf"
        out_path = os.path.join(config.OUTPUT_DIR, fname)
        with open(out_path, "wb") as f:
            writer.write(f)

        written.append(out_path)
        page_number += 1

    print(f"Wrote {len(written)} letter(s) to {config.OUTPUT_DIR}/")
    return written


if __name__ == "__main__":
    render_all()
