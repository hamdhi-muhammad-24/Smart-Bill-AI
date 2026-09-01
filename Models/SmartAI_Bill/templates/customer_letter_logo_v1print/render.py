"""
render.py
=========
Turns clean `Customer` records into the finished PDF letters.

How it works (per customer):
  1. Draw an in-memory "overlay" A4 page containing only the variable text
     (name, address, phone, date) plus the static English body, positioned
     with the coordinates in config.py.
  2. Stamp that overlay on top of the branded template.pdf background.
  3. Optionally append the static Sinhala/Tamil page 2 (assets/page2.pdf).

The English body text is fixed for every customer, so it is defined here
as ENGLISH_BODY. Edit it here if the wording ever changes.
"""

import io
from pathlib import Path
from typing import List, Any, Optional, Dict

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Frame, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from . import config as C
from .parser import Customer

pdfmetrics.registerFont(TTFont(C.FONT_REG, str(C.FONT_REG_PATH)))
pdfmetrics.registerFont(TTFont(C.FONT_BOLD, str(C.FONT_BOLD_PATH)))
pdfmetrics.registerFontFamily(
    C.FONT_REG, normal=C.FONT_REG, bold=C.FONT_BOLD,
    italic=C.FONT_REG, boldItalic=C.FONT_BOLD,
)

# --------------------------------------------------------------------------
# Static English letter body (same for every recipient).
# <b> = bold, blank lines separate paragraphs, "  * " lines become bullets.
# --------------------------------------------------------------------------
SUBJECT = ("Important Upgrade of Your Existing SLT Connection to "
           "Fibre / 4G LTE at No Additional Cost")

ENGLISH_BODY = [
    "Dear Valued Customer,",

    "At SLT, we greatly value your long-standing trust and loyalty. To provide "
    "you with a more reliable and future-ready service, we are upgrading the "
    "existing copper network in your area to our advanced SLT Fibre and 4G LTE "
    "networks.",

    "The copper network has served our customers for many years. However, as "
    "this technology is now reaching the end of its service life, maintaining it "
    "and ensuring reliable service have become increasingly difficult. Therefore, "
    "the existing copper-based Megaline network in your area will be gradually "
    "discontinued.",

    "To ensure that your telephone and broadband services continue without "
    "interruption, your existing connection will be migrated to SLT Fibre or "
    "4G LTE. The new connection will provide improved reliability, clearer voice "
    "services, faster internet speeds where applicable, and access to modern "
    "digital services.",

    "An SLT representative will contact you shortly to explain the process and "
    "arrange the installation at a date and time convenient to you. Our team will "
    "assist you throughout the migration to make the changeover as simple and "
    "smooth as possible.",

    "<b>Please be assured of the following:</b>",

    "  * There will be no additional charge before, during, or after the "
    "migration. All costs directly related to the migration and installation "
    "will be borne by SLT.",
    "  * Your existing package and current monthly rental will remain unchanged "
    "after the migration. Your rental will change only if you personally request "
    "a different or higher package.",
    "  * You will retain your existing telephone number when your service is "
    "migrated to SLT Fibre (FTTH) or 4G LTE.",

    "This migration is intended only to improve the reliability and quality of "
    "your service. You are not required to pay any additional migration, "
    "installation, or connection fee.",

    "<b>If you require any clarification or assistance, please contact us on "
    "1212. Our staff will be pleased to support you.</b>",

    "Thank you for your continued loyalty and for being a valued customer of "
    "Sri Lanka Telecom PLC.",
    "Best regards,",

    "Project Manager<br/>MSAN Migration Project<br/>Sri Lanka Telecom PLC",
]


# --------------------------------------------------------------------------
# overlay builder
# --------------------------------------------------------------------------
def _paragraph_styles():
    b = C.BODY_FRAME
    base = ParagraphStyle(
        "body", fontName=b["font"], fontSize=b["size"],
        leading=b["leading"], spaceAfter=b["space_after"], alignment=TA_JUSTIFY,
    )
    bullet = ParagraphStyle(
        "bullet", parent=base, leftIndent=14, bulletIndent=2, spaceAfter=3,
    )
    subject = ParagraphStyle(
        "subject", fontName=C.FONT_BOLD, fontSize=b["size"],
        leading=b["leading"], spaceAfter=b["space_after"] + 10,
    )
    return base, bullet, subject


def _build_overlay(cust: Customer) -> PdfReader:
    """Return a single-page PdfReader containing only the variable + body text."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    # --- recipient block (name + address lines) ---
    a = C.ADDR_BLOCK
    y = a["y_top"]
    c.setFont(a["name_font"], a["name_size"])
    c.drawString(a["x"], y, cust.name)
    c.setFont(a["addr_font"], a["addr_size"])
    for line in cust.address_lines:
        y -= a["line_gap"]
        c.drawString(a["x"], y, line)

    # --- telephone + date (left) ---
    t = C.TEL_LINE
    c.setFont(t["font"], t["size"])
    c.drawString(t["x"], t["y"], f'{t["label"]}{cust.telephone}')
    d = C.DATE_LINE
    c.setFont(d["font"], d["size"])
    c.drawString(d["x"], d["y"], C.LETTER_DATE)

    # --- subject + body inside a justified frame ---
    base, bullet, subject = _paragraph_styles()
    story = [Paragraph(f"<b>Subject:</b> {SUBJECT}", subject)]
    for para in ENGLISH_BODY:
        if para.lstrip().startswith("* "):
            story.append(Paragraph(para.lstrip()[2:], bullet, bulletText="\u2022"))
            if "FTTH" in para:
                story.append(Spacer(1, 10))
        else:
            story.append(Paragraph(para, base))
            if para == "Dear Valued Customer,":
                story.append(Spacer(1, 10))
            elif para.startswith("This migration is intended"):
                story.append(Spacer(1, 10))
            elif para.startswith("<b>If you require any clarification"):
                story.append(Spacer(1, 10))
            elif para == "Best regards,":
                story.append(Spacer(1, 10))

    b = C.BODY_FRAME
    frame = Frame(b["x"], b["y"], b["width"], b["height"],
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    frame.addFromList(story, c)

    c.showPage()
    c.save()
    buf.seek(0)
    return PdfReader(buf)


# --------------------------------------------------------------------------
# page assembly
# --------------------------------------------------------------------------
def _load_static_pages():
    template_page = PdfReader(str(C.TEMPLATE)).pages[0]
    page2_reader = None
    if C.APPEND_PAGE2 and Path(C.PAGE2_PDF).exists():
        page2_reader = PdfReader(str(C.PAGE2_PDF))
    return template_page, page2_reader


def build_letter_pages(cust: Customer, template_page, page2_reader) -> List:
    """Return the list of finished pages for one customer (page 1 [+ page 2])."""
    # fresh copy of the template so overlays never accumulate
    bg = PdfReader(str(C.TEMPLATE)).pages[0]
    overlay = _build_overlay(cust).pages[0]
    bg.merge_page(overlay)          # stamp text on top of branding
    pages = [bg]
    if page2_reader is not None:
        pages.extend(page2_reader.pages)
    return pages


def render_combined(customers: List[Customer], out_path: Path):
    template_page, page2_reader = _load_static_pages()
    writer = PdfWriter()
    for cust in customers:
        for page in build_letter_pages(cust, template_page, page2_reader):
            writer.add_page(page)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        writer.write(f)
    return out_path


def render_per_customer(customers: List[Customer], out_dir: Path):
    renderer = CustomerLetterRenderer()
    renderer.render(customers)
    renderer.save(str(out_dir))
    return [out_dir / fname for fname, _, _ in renderer.generated_pdfs]


class CustomerLetterRenderer:
    def __init__(self):
        self.generated_pdfs = []

    def render(self, records: Any):
        if isinstance(records, dict) and "records" in records:
            records = records["records"]
        elif isinstance(records, dict) and "customers" in records:
            records = records["customers"]
        elif not isinstance(records, list):
            records = [records]

        template_page, page2_reader = _load_static_pages()
        self.generated_pdfs = []
        for i, cust in enumerate(records, 1):
            if isinstance(cust, dict):
                cust = Customer(
                    name=cust.get("name") or cust.get("client_name") or "",
                    address_lines=cust.get("address_lines") or cust.get("client_address_lines") or [],
                    telephone=cust.get("telephone") or cust.get("telephone_number") or "",
                    raw=cust.get("raw") or cust
                )

            writer = PdfWriter()
            for page in build_letter_pages(cust, template_page, page2_reader):
                writer.add_page(page)
            buf = io.BytesIO()
            writer.write(buf)
            pdf_bytes = buf.getvalue()

            acc = None
            if hasattr(cust, "raw") and isinstance(cust.raw, dict):
                for k in [C.FILENAME_COLUMN, "ACCOUNT", "ACCOUNT_NO", "ACC_NO", "ACCOUNT_NUMBER", "Account No", "Account", "SERIAL_NUM", "CUSTOMER_REF", "TELEPHONE"]:
                    val = cust.raw.get(k)
                    if val is not None and str(val).strip() not in ("", "None", "0"):
                        acc = str(val).strip().replace(" ", "").replace("_", "")
                        break
            if not acc and getattr(cust, "telephone", None):
                acc = str(cust.telephone).strip().replace(" ", "").replace("_", "")
            if not acc:
                acc = f"cust_{i:04d}"

            fname = f"{acc}_Customer_Letter.pdf"
            self.generated_pdfs.append((fname, pdf_bytes, cust))
        return self.generated_pdfs

    def save(self, output_path: str):
        if not self.generated_pdfs:
            raise RuntimeError("No PDFs generated in render()")

        import os
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
