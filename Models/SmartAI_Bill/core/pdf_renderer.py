import os
import io
from copy import deepcopy
from pypdf import PdfReader, PdfWriter, PageObject
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import black
from reportlab.lib.utils import ImageReader

from core.text_utils import wrap_text, format_number
from core.tables import draw_table_with_overflow
from core.qr_generator import generate_slt_qr, generate_static_payonline_qr
from core.barcode_generator import generate_barcode, generate_slip_barcode
from core.gmf_reader import is_red_notice


class BaseRenderer:
    PAGE_W, PAGE_H = A4
    FONT_NAME = "Helvetica"
    HANGING_INDENT = 5

    def __init__(self, template_pdf_path):
        self.default_template_pdf_path = template_pdf_path
        self.template_pdf_path = template_pdf_path
        self.reader = PdfReader(template_pdf_path)
        self.writer = PdfWriter()
        self.canvases = []
        self.is_red = False
        self._new_canvas()

    def set_template_pdf(self, template_pdf_path):
        """Switch background template PDF (e.g. for RED notice)."""
        if template_pdf_path and os.path.exists(template_pdf_path):
            self.template_pdf_path = template_pdf_path
            self.reader = PdfReader(template_pdf_path)

    def check_red_notice(self, data):
        """Helper to switch background to Template_RED.pdf if source_filename matches RED notice pattern."""
        filename = str(data.get("source_filename") or data.get("filename") or "")
        if is_red_notice(filename):
            self.is_red = True
            templates_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            red_pdf = os.path.join(templates_dir, "templates", "Template_RED.pdf")
            if os.path.exists(red_pdf):
                self.set_template_pdf(red_pdf)

    def get_page1_y_min(self, default=165.0):
        """Return content floor for page 1 (220.0 for RED notice, default 165.0 for non-red)."""
        return 220.0 if self.is_red else default



    def _new_canvas(self):

        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        self.canvases.append((buf, c))
        return c

    @property
    def canvas(self):
        return self.canvases[-1][1]


    def text(self, x, y, value, size=10, bold=False, align="left"):
        if value is None or value == "":
            return
        c = self.canvas
        font = "Helvetica-Bold" if bold else "Helvetica"
        c.setFont(font, size)
        c.setFillColor(black)
        text = str(value)
        if align == "right":
            c.drawRightString(x, y, text)
        elif align == "center":
            c.drawCentredString(x, y, text)
        else:
            c.drawString(x, y, text)

    def number(self, x, y, value, decimals=2, align="right", size=10, bold=False):
        formatted = format_number(value, decimals)
        self.text(x, y, formatted, size=size, bold=bold, align=align)

    def multiline_block(self, x, y, lines, line_height=11, size=9, bold=False):
        if not lines:
            return
        current_y = y
        for line in lines:
            if line:
                self.text(x, current_y, line, size=size, bold=bold)
            current_y -= line_height

    def wrapped_text(self, x, y, text, max_width, size=9,
                     hanging_indent=5, line_height=11):
        if not text:
            return y
        lines = wrap_text(self.canvas, text, self.FONT_NAME, size, max_width)
        current_y = y
        for i, line in enumerate(lines):
            draw_x = x if i == 0 else x + hanging_indent
            self.text(draw_x, current_y, line, size=size)
            current_y -= line_height
        return current_y

    def paginated_table(self, config, data):
        return draw_table_with_overflow(self, config, data)


    def new_page(self):
        self._new_canvas()

    def page_count(self):
        return len(self.canvases)


    def rect(self, x, y, width, height, line_width=0.75):
        c = self.canvas
        c.setLineWidth(line_width)
        c.rect(x, y, width, height, stroke=1, fill=0)


    def draw_static_payonline_qr(self, x, y, size=48):
        """Static payonline QR (www.slt.lk/payonline). Cached."""
        buf = generate_static_payonline_qr(size=200)
        img = ImageReader(buf)
        self.canvas.drawImage(img, x, y, width=size, height=size, mask='auto')

    def draw_qr(self, x, y, account_number, total_charges=None, size=80):
        charges = total_charges if total_charges else 0
        qr_buf, _ = generate_slt_qr(
            account_number=account_number,
            total_charges=charges,
            size=200
        )
        img = ImageReader(qr_buf)
        self.canvas.drawImage(img, x, y, width=size, height=size, mask='auto')


    def draw_barcode(self, x, y, value, width=150, height=30):
        """Address section barcode (account number only)."""
        bc_buf = generate_barcode(value)
        img = ImageReader(bc_buf)
        self.canvas.drawImage(img, x, y, width=width, height=height, mask='auto')

    def draw_slip_barcode(self, x, y, bill_ref, total_charges,
                          width=150, height=30):
        """
        Payment slip barcode (includes invoice number + total charges).
        Format: {invoice_number}{total_charges:.2f}
        Example: 0007398361-26494729.66
        """
        bc_buf = generate_slip_barcode(bill_ref, total_charges)
        img = ImageReader(bc_buf)
        self.canvas.drawImage(img, x, y, width=width, height=height, mask='auto')


    def save(self, output_path):
        for buf, c in self.canvases:
            c.save()
            buf.seek(0)

        for page_idx, (buf, c) in enumerate(self.canvases):
            overlay = PdfReader(buf)

            if page_idx < len(self.reader.pages):
                template_page = self.reader.pages[page_idx]
                page = deepcopy(template_page)
                w = float(page.mediabox.width)
                h = float(page.mediabox.height)
                if abs(w - self.PAGE_W) > 5 or abs(h - self.PAGE_H) > 5:
                    scale_x = self.PAGE_W / w
                    page.scale_by(scale_x)
            else:
                page = PageObject.create_blank_page(
                    width=self.PAGE_W, height=self.PAGE_H
                )

            page.merge_page(overlay.pages[0])
            self.writer.add_page(page)

        with open(output_path, "wb") as f:
            self.writer.write(f)


    def render(self, data):
        raise NotImplementedError("Subclass must implement render(data)")