import os
from reportlab.lib.colors import black
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from core.pdf_renderer import BaseRenderer
from core.text_utils import wrap_text
from templates.summary_statement.config import (
    COORDS_HEADER, TABLE_COLS, TABLE, TOTAL_ROW, MIDDLE_PAGE, FONTS,
)

TEMPLATE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PDF = os.path.join(TEMPLATE_DIR, "layout.pdf")

# Calibri, scoped to this template only - shared font files (not duplicated
# per template) from templates/fonts/.
_FONTS_DIR = os.path.join(os.path.dirname(TEMPLATE_DIR), "fonts")
if "Calibri" not in pdfmetrics.getRegisteredFontNames():
    pdfmetrics.registerFont(TTFont("Calibri", os.path.join(_FONTS_DIR, "calibri.ttf")))
    pdfmetrics.registerFont(TTFont("Calibri-Bold", os.path.join(_FONTS_DIR, "calibrib.ttf")))


class SummaryStatementRenderer(BaseRenderer):
    """Renders Summary Statement bills."""

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
        # Split accounts across pages
        pages = self._split_accounts_into_pages(data["accounts"])

        if not pages:
            pages = [[]]

        total_pages = len(pages)
        last_page_idx = total_pages - 1

        # Draw first page (with header)
        self._draw_page1(data, pages[0], total_pages,
                          draw_total=(total_pages == 1))

        # Draw remaining pages
        for i in range(1, total_pages):
            self.new_page()
            page_num = i + 1
            is_last = (i == last_page_idx)
            self._draw_middle_page(data, pages[i], page_num, total_pages,
                                    draw_total=is_last)

    def _split_accounts_into_pages(self, accounts):
        """Split accounts across pages based on available space."""
        if not accounts:
            return []

        pages = []
        current_page = []
        current_y_used = 0
        on_first_page = True

        y_avail_p1 = TABLE["page1_y_start"] - TABLE["page1_y_min"]
        y_avail_mid = TABLE["middle_y_start"] - TABLE["middle_y_min"]
        line_h = TABLE["line_h"]

        for account in accounts:
            row_height = self._calculate_row_height(account, line_h)
            available = y_avail_p1 if on_first_page else y_avail_mid

            if current_y_used + row_height <= available:
                current_page.append(account)
                current_y_used += row_height
            else:
                pages.append(current_page)
                current_page = [account]
                current_y_used = row_height
                on_first_page = False

        if current_page:
            pages.append(current_page)

        # If totals row doesn't fit on last page, add extra page
        totals_row_height = TOTAL_ROW["gap_above"] + TOTAL_ROW["font_size"] + 5
        last_page_used = sum(
            self._calculate_row_height(a, line_h) for a in pages[-1]
        )
        y_avail = y_avail_p1 if len(pages) == 1 else y_avail_mid

        if last_page_used + totals_row_height > y_avail:
            pages.append([])

        return pages

    def _calculate_row_height(self, account, line_h):
        """Compute row height accounting for wrapped name."""
        max_width = TABLE_COLS["name_max_x"] - TABLE_COLS["account_name_x"]
        name_lines = wrap_text(self.canvas, account["account_name"],
                                self.FONT_NAME, TABLE["font_size"], max_width)
        return max(line_h, len(name_lines) * line_h)

    def _draw_page1(self, data, page_accounts, total_pages, draw_total):
        """Draw first page: header + customer + accounts table."""
        f = FONTS["header"]

        # Date of statement
        x, y = COORDS_HEADER["date_of_statement"]
        self.text(x, y, data["date_of_statement"], size=f["size"])


        # Customer Ref No
        x, y = COORDS_HEADER["customer_ref_no"]
        self.text(x, y, data["customer_ref_no"], size=f["size"])
        # Clean the source filename by removing the random suffix (e.g. __mp5l12aq_1.gmf)
        source_file = data.get("source_filename", "")
        if "__" in source_file:
            source_file = source_file.split("__")[0]
        self.text(45, 650, source_file, size=7)

        # Customer block (name, position, department, company, address)
        f = FONTS["customer"]
        customer_lines = []
        if data["contact_name"]:
            customer_lines.append(data["contact_name"])
        if data["contact_position"]:
            customer_lines.append(data["contact_position"])
        if data["contact_department"]:
            customer_lines.append(data["contact_department"])
        if data["contact_company"]:
            customer_lines.append(data["contact_company"])
        customer_lines.extend(data["contact_address"])
        if data["contact_zip"]:
            customer_lines.append(data["contact_zip"])

        self.multiline_block(
            COORDS_HEADER["customer_x"],
            COORDS_HEADER["customer_y_start"],
            customer_lines,
            line_height=COORDS_HEADER["customer_line_h"],
            size=f["size"]
        )

        # Barcode (customer ref)
        self.draw_barcode(
            *COORDS_HEADER["barcode"][:2],
            data["customer_ref_no"] or data["invoice_number"],
            width=COORDS_HEADER["barcode_width"],
            height=COORDS_HEADER["barcode_height"]
        )

        # Page number
        f = FONTS["page_num"]
        x, y = COORDS_HEADER["page_num_x"], COORDS_HEADER["page_num_y"]
        self.text(x, y, f"1  of  {total_pages}", size=f["size"], align="right")

        # Draw table rows
        y = TABLE["page1_y_start"]
        y = self._draw_table_rows(page_accounts, y)

        # Totals row if this is the only page
        if draw_total:
            total_y = y - TOTAL_ROW["gap_above"]
            self._draw_totals_row(data, total_y)

    def _draw_middle_page(self, data, page_accounts, page_num, total_pages, draw_total):
        """Draw middle/last page: invoice_of_summary number + page num + table."""
        # Invoice No at top
        f = FONTS["invoice_no"]
        self.text(MIDDLE_PAGE["invoice_no_x"], MIDDLE_PAGE["invoice_no_y"],
                   f'Invoice No.{data["invoice_number"]}',
                   size=f["size"], bold=f["bold"])

        # Page indicator
        f = FONTS["page_num"]
        self.text(MIDDLE_PAGE["page_num_x"], MIDDLE_PAGE["page_num_y"],
                   f"{page_num}  of  {total_pages}", size=f["size"], align="right")

        # Table rows
        y = TABLE["middle_y_start"]
        y = self._draw_table_rows(page_accounts, y)

        # Totals row on last page
        if draw_total:
            total_y = y - TOTAL_ROW["gap_above"]
            self._draw_totals_row(data, total_y)

    def _draw_table_rows(self, accounts, start_y):
        """Draw account rows. Returns final Y position."""
        f = FONTS["table_row"]
        line_h = TABLE["line_h"]
        max_width = TABLE_COLS["name_max_x"] - TABLE_COLS["account_name_x"]

        y = start_y
        for account in accounts:
            # Wrap account name if too long
            name_lines = wrap_text(self.canvas, account["account_name"],
                                    self.FONT_NAME, f["size"], max_width)

            # Account number (first line only)
            self.text(TABLE_COLS["account_no_x"], y,
                       account["account_no"], size=f["size"])

            # Account name (potentially wrapped)
            for i, line in enumerate(name_lines):
                self.text(TABLE_COLS["account_name_x"], y - (i * line_h),
                           line, size=f["size"])

            # Amounts (on first line, right-aligned)
            self.number(TABLE_COLS["net_amount_x"], y,
                         account["net_amount"], size=f["size"], align="right")
            self.number(TABLE_COLS["tax_amount_x"], y,
                         account["tax_amount"], size=f["size"], align="right")
            self.number(TABLE_COLS["gross_total_x"], y,
                         account["gross_total"], size=f["size"], align="right")

            row_height = len(name_lines) * line_h
            y -= row_height

        return y

    def _draw_totals_row(self, data, y):
        """Draw bold totals row at bottom of last page."""
        f = FONTS["total_row"]
        self.text(TOTAL_ROW["label_x"], y, "Total", size=f["size"], bold=True)
        self.number(TOTAL_ROW["net_amount_x"], y, data["total_net"],
                     size=f["size"], bold=True, align="right")
        self.number(TOTAL_ROW["tax_amount_x"], y, data["total_tax"],
                     size=f["size"], bold=True, align="right")
        self.number(TOTAL_ROW["gross_total_x"], y, data["total_gross"],
                     size=f["size"], bold=True, align="right")

    def new_page(self):
        """Override to reuse template page 1 as background for middle pages."""
        # For summary statement, middle/last pages use blank background
        self._new_canvas()