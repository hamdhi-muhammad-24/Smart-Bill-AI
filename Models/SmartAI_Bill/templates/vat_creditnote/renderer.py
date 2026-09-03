import os

from reportlab.lib.colors import black
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from core.pdf_renderer import BaseRenderer

from templates.vat_creditnote.config import (
    COORDS,
    ADDRESS_BOX,
    ADJUSTMENT_TBL,
    CHARGE_PERIOD_X,
    CHARGE_PERIOD_Y,
    FONTS
)

TEMPLATE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PDF = os.path.join(TEMPLATE_DIR, "layout.pdf")

# Calibri, scoped to this template only - shared font files (not duplicated
# per template) from templates/fonts/.
_FONTS_DIR = os.path.join(os.path.dirname(TEMPLATE_DIR), "fonts")
if "Calibri" not in pdfmetrics.getRegisteredFontNames():
    pdfmetrics.registerFont(TTFont("Calibri", os.path.join(_FONTS_DIR, "calibri.ttf")))
    pdfmetrics.registerFont(TTFont("Calibri-Bold", os.path.join(_FONTS_DIR, "calibrib.ttf")))

class VATCreditNoteRenderer(BaseRenderer):
    FONT_NAME = "Calibri"

    def __init__(self):
        super().__init__(TEMPLATE_PDF)

    def text(self, x, y, value, size=10, bold=False, align="left"):
        """Override the base Helvetica text() with Calibri, scoped to this
        template only - the shared BaseRenderer.text() (used by every other
        template) is untouched."""
        if value is None or value == "":
            return
        c = self.canvas
        font = "Calibri-Bold" if bold else "Calibri"
        c.setFont(font, size)
        c.setFillColor(black)
        text = str(value)
        if align == "right":
            c.drawRightString(x, y, text)
        elif align == "center":
            c.drawCentredString(x, y, text)
        else:
            c.drawString(x, y, text)

    def render(self, data):
        self._draw_header(data)
        self._draw_barcode(data)
        self._draw_address(data)
        self._draw_vat_lines(data)
        self._draw_extra_lines(data)
        self._draw_summary(data)
        y = self._draw_adjustments(data)
        self._draw_charge_period(data, y)
        self._draw_page_indicator()

    def _draw_page_indicator(self):
        total = len(self.canvases)
        for idx in range(total):
            c = self.canvases[idx][1]
            c.setFont("Calibri", FONTS["header"]["size"])
            c.drawRightString(550, 750, f"{idx + 1}  of  {total}")

    def _draw_header(self, data):
        self.text(*COORDS["document_title"], "Tax Credit Note", size=FONTS["title"]["size"])
        self.text(*COORDS["account_number"], data.get("account_number", ""), size=FONTS["header"]["size"])
        self.text(*COORDS["invoice_number"], data.get("invoice_number", ""), size=FONTS["header"]["size"])
        self.text(*COORDS["billing_date"], data.get("billing_date", ""), size=FONTS["header"]["size"])
        self.text(*COORDS["bill_period"], data.get("bill_period", ""), size=FONTS["header"]["size"])

    def _draw_barcode(self, data):
        account_number = data.get("account_number", "")
        if account_number:
            self.draw_barcode(*COORDS["barcode"], account_number, width=COORDS["barcode_width"], height=COORDS["barcode_height"])

    def _draw_address(self, data):
        y = ADDRESS_BOX["y"]
        lines = [data.get(f"address_line{i}") for i in range(1, 11)]
        for line in lines:
            if line:
                self.text(ADDRESS_BOX["x"], y, line, size=ADDRESS_BOX["font_size"])
                y -= ADDRESS_BOX["line_h"]

    def _draw_vat_lines(self, data):
        self.text(*COORDS["below_address_line1"], data.get("below_address_line1", ""), size=FONTS["footer"]["size"])
        self.text(*COORDS["below_address_line2"], data.get("below_address_line2", ""), size=FONTS["footer"]["size"])

    def _draw_extra_lines(self, data):
        self.text(*COORDS["header_extra_line1"], data.get("header_extra_line1", ""), size=FONTS["footer"]["size"])
        self.text(*COORDS["header_extra_line2"], data.get("header_extra_line2", ""), size=FONTS["footer"]["size"])

    def _draw_summary(self, data):
        summary = data.get("summary", {})
        self.number(*COORDS["balance_bf"], summary.get("balance_bf", 0), align="center")
        self.number(*COORDS["payments_received"], summary.get("payments_received", 0), align="center")
        self.number(*COORDS["arrears"], summary.get("arrears", 0), align="center")
        self.number(*COORDS["adjustment_value"], summary.get("adjustment_value", 0), align="center")
        self.number(*COORDS["total_payable"], summary.get("total_payable", 0), bold=True, align="center")

    def _draw_adjustments(self, data):
        adjustments = data.get("adjustments", [])
        taxes = data.get("taxes_levies", [])
        y = ADJUSTMENT_TBL["y_start"]

        if adjustments:
            y = self._draw_section("ADJUSTMENTS", adjustments, y, data)
        
        if taxes:
            # Add a small buffer before new section if needed
            y -= ADJUSTMENT_TBL["line_h"] 
            y = self._draw_section("TAXES & LEVIES", taxes, y, data)

        return y

    def _draw_section(self, title, items, y, data):
        # Initial heading for the section
        self.text(ADJUSTMENT_TBL["desc_x"], y, title, bold=True)
        if title == "ADJUSTMENTS":
            currency = data.get("acc_currency_code", "Rs").strip()
            currency_str = "(Rs.)" if currency.upper() == "RS" else f"({currency})"
            self.text(ADJUSTMENT_TBL["amount_x"], y + 3, currency_str, size=ADJUSTMENT_TBL["font_size"], bold=True, align="right")
        y -= ADJUSTMENT_TBL["line_h"]

        for item in items:
            # Page break logic
            if y <= ADJUSTMENT_TBL["y_min"]:
                self.new_page()
                y = ADJUSTMENT_TBL["y_start"]
                # Re-draw the title at the top of the new page
                self.text(ADJUSTMENT_TBL["desc_x"], y, title, bold=True)
                if title == "ADJUSTMENTS":
                    currency = data.get("acc_currency_code", "Rs").strip()
                    currency_str = "(Rs.)" if currency.upper() == "RS" else f"({currency})"
                    self.text(ADJUSTMENT_TBL["amount_x"], y + 15, currency_str, size=ADJUSTMENT_TBL["font_size"], bold=True, align="right")
                y -= ADJUSTMENT_TBL["line_h"]

            self.text(ADJUSTMENT_TBL["desc_x"] + ADJUSTMENT_TBL["indent"], y, item.get("description", ""), size=ADJUSTMENT_TBL["font_size"])
            self.number(ADJUSTMENT_TBL["amount_x"], y, item.get("amount", 0), size=ADJUSTMENT_TBL["font_size"], align="right")
            y -= ADJUSTMENT_TBL["line_h"]
        
        return y

    def _draw_charge_period(self, data, y):
        # Position it dynamically below the last line
        y -= ADJUSTMENT_TBL["line_h"] * 1.5

        # Check for page break if it exceeds page limits
        if y <= ADJUSTMENT_TBL["y_min"]:
            self.new_page()
            y = ADJUSTMENT_TBL["y_start"]

        desc_x = ADJUSTMENT_TBL["desc_x"]
        amount_x = CHARGE_PERIOD_X

        self.canvas.setLineWidth(0.5)
        self.canvas.setStrokeColorRGB(0, 0, 0)
        self.canvas.line(desc_x, y + 11, amount_x, y + 11)

        self.text(desc_x, y, "Charge of the period", size=9, bold=True)
        self.number(amount_x, y, data.get("charge_for_period", 0), size=9, bold=True, align="right")

        self.canvas.line(desc_x, y - 5, amount_x, y - 5)