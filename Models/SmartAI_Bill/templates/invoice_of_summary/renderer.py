"""Invoice of Summary Renderer (Sheet 18, BILLSTYLE=18)."""
import os
from datetime import datetime
from reportlab.lib.colors import black
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from core.pdf_renderer import BaseRenderer
from core.bill_common import is_vat_reg_printable, is_tax_section_printable
from templates.invoice_of_summary.config import (
    COORDS, CHARGES_TABLE, USAGE_TABLE_2COL, FONTS,
)

TEMPLATE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PDF = os.path.join(TEMPLATE_DIR, "layout.pdf")

# Calibri, scoped to this template only - shared font files (not duplicated
# per template), registered under names distinct from Helvetica so no other
# template is affected.
_FONTS_DIR = os.path.join(os.path.dirname(TEMPLATE_DIR), "fonts")
if "Calibri" not in pdfmetrics.getRegisteredFontNames():
    pdfmetrics.registerFont(TTFont("Calibri", os.path.join(_FONTS_DIR, "calibri.ttf")))
    pdfmetrics.registerFont(TTFont("Calibri-Bold", os.path.join(_FONTS_DIR, "calibrib.ttf")))


class InvoiceOfSummaryRenderer(BaseRenderer):
    FONT_NAME = "Calibri"

    def __init__(self):
        super().__init__(TEMPLATE_PDF)
        self._y        = CHARGES_TABLE["otherpage_y_start"]
        self._on_page1 = True

    def text(self, x, y, value, size=10, bold=False, align="left"):
        """Override the base Helvetica text() with Calibri, scoped to this
        template only."""
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
        self.check_red_notice(data)
        self._draw_header(data)
        self._draw_vat_lines(data)
        self._draw_customer(data)
        self._draw_badge(data)
        self._draw_generation_id(data)
        self._draw_summary_boxes(data)
        self._draw_page1_footer(data)
        self._draw_currency_label(data)

        self._draw_summary_of_invoice_dynamic(data)
        self._draw_total_charges_dynamic(data)

        self._draw_charges_in_detail_flowing(data)
        self._draw_adjustments_flowing(data)
        self._draw_top_level_discounts_flowing(data)
        self._draw_discounts_and_taxes_flowing(data)
        self._draw_payments_flowing(data)
        self._draw_cancel_payments_flowing(data)
        self._draw_messages_flowing(data)
        self._draw_usage_sections(data)

        self._stamp_all_page_indicators(data)


    def _draw_header(self, data):
        f = FONTS["header"]
        self.text(*COORDS["telephone_number"], data["telephone_number"],
                  size=f["size"])
        self.text(*COORDS["account_number"],   data["account_number"],
                  size=f["size"])
        self.text(*COORDS["invoice_number"],   data["invoice_number"],
                  size=f["size"])
        self.text(*COORDS["billing_date"],     data["billing_date"],
                  size=f["size"])
        period = (f"{data['billing_period_start']} - "
                  f"{data['billing_period_end']}")
        self.text(*COORDS["billing_period"], period, size=f["size"])

    def _draw_vat_lines(self, data):
        """BPR05/07: only when show_vat_lines is True (VATDL check)."""
        if not data.get("show_vat_lines"):
            return
        f = FONTS.get("vat_reg", FONTS["header"])
        if data.get("slt_vat_reg"):
            self.text(*COORDS["slt_vat_reg_label"],
                      f"SLT VAT Registration Number: {data['slt_vat_reg']}",
                      size=f["size"])
        if data.get("customer_vat_reg"):
            self.text(*COORDS["customer_vat_reg_label"],
                      f"Customer VAT Registration Number: "
                      f"{data['customer_vat_reg']}",
                      size=f["size"])

    def _draw_customer(self, data):
        f = FONTS["customer_name"]
        lines = []
        if data.get("address_name_not_required"):
            top = data.get("business_name") or data.get("customer_name", "")
            if top:
                lines.append(top)
        else:
            top = data.get("department") or data.get("customer_name", "")
            if top:
                lines.append(top)
            if data.get("business_name"):
                lines.append(data["business_name"])

        lines.extend(data.get("address_lines", []))
        if data.get("zip_code"):
            lines.append(data["zip_code"])

        start_y = COORDS["customer_name"][1]
        line_h = COORDS.get("customer_addr_line_h", 11)
        self.multiline_block(
            COORDS["customer_name"][0], start_y,
            lines, line_height=line_h,
            size=f["size"], bold=True,
        )

    def _draw_badge(self, data):
        f = FONTS["badge"]
        self.text(*COORDS["badge_text"], data.get("badge", "ENTERPRISE"),
                  size=f["size"], bold=f["bold"])

    def _draw_generation_id(self, data):
        f   = FONTS["gen_id"]
        due = data.get("payment_due_date", "")
        try:
            dd, mm, yyyy = due.split("/")
            due_mmddyy   = f"{mm}{dd}{yyyy}"
        except ValueError:
            due_mmddyy = ""
        ts   = datetime.now().strftime("%H:%M:%S")

        # Clean the source filename by removing the random suffix (e.g. __ugn81e1a_1.gmf)
        source_file = data.get("source_filename", "")
        if "__" in source_file:
            source_file = source_file.split("__")[0] + "_"

        line = f'{source_file}_{ts}{due_mmddyy}'
        self.text(*COORDS["gen_id_line"], line, size=f["size"])
        if data.get("customer_segment"):
            self.text(*COORDS["gen_id_line2"], data["customer_segment"],
                      size=f["size"])

    def _draw_summary_boxes(self, data):
        f = FONTS["summary_box"]
        self.number(*COORDS["balance_bf"], data["balance_bf"],
                    size=f["size"], align="center")
        self.number(*COORDS["payments_received"], data["payments_received"],
                    size=f["size"], align="center")
        self.number(*COORDS["charges_period"], data["charges_period"],
                    size=f["size"], align="center")
        f = FONTS["summary_total"]
        self.number(*COORDS["total_payable"], data["total_payable"],
                    size=f["size"], bold=True, align="center")
        self.text(*COORDS["payment_due_date"], data["payment_due_date"],
                  size=f["size"], bold=True, align="center")

    def _draw_page1_footer(self, data):
        self.draw_static_payonline_qr(
            *COORDS["payonline_qr"], size=COORDS["payonline_qr_size"])
        self.draw_qr(
            *COORDS["qr_code"],
            account_number=data["account_number"],
            total_charges=data["total_charges"],
            size=COORDS["qr_size"],
        )
        self.draw_barcode(
            *COORDS["barcode"], data["account_number"],
            width=COORDS["barcode_width"], height=COORDS["barcode_height"],
        )
        self.draw_slip_barcode(
            *COORDS["slip_barcode"],
            bill_ref=data["invoice_number"],
            total_charges=data["total_charges"],
            width=COORDS["slip_barcode_width"],
            height=COORDS["slip_barcode_height"],
        )
        f = FONTS["slip"]
        self.text(*COORDS["slip_telephone"], data["telephone_number"],
                  size=f["size"])
        self.text(*COORDS["slip_invoice"],   data["invoice_number"],
                  size=f["size"])
        # BPR13: slip name follows address_name_not_required flag
        slip_name = (
            data.get("business_name")
            if data.get("address_name_not_required")
            else data.get("customer_name", "")
        )
        self.text(*COORDS["slip_customer"], slip_name or "", size=f["size"])
        self.text(*COORDS["slip_account"],  data["account_number"],
                  size=f["size"])

    def _draw_currency_label(self, data):
        """Currency label above the charges column (e.g. "(Rs.)") - read from
        the GMF's ACCCURRENCYCODE tag (data['currency_code']), never a fixed
        string, since a different account can have a different currency.
        Must NOT be sourced from SLTACCCURRENCYCODE - that's SLT's internal
        accounting code (e.g. "LKR"), a different tag/value entirely,
        confirmed distinct in the real GMF."""
        code = data.get("currency_code", "")
        if not code:
            return
        f = FONTS["header"]
        self.text(CHARGES_TABLE["amount_x"], 480,
                  f"({code}.)", size=f["size"], bold=True, align="right")

    def _draw_summary_of_invoice_dynamic(self, data):
        """Summary block on page 1, following the running self._y cursor
        instead of a fixed page position."""
        x     = COORDS["summary_x"]
        amt_x = COORDS["summary_amount_x"]
        lh    = COORDS["summary_line_h"]
        f     = FONTS["taxes"]
        fc    = 7

        self._y = COORDS["summary_y_start"]

        # "Summary of Invoice" heading + underline, above the block
        c = self.canvas
        c.setFont("Calibri-Bold", FONTS["total"]["size"])
        c.drawString(x, self._y, "Summary of Invoice")
        c.setLineWidth(0.5)
        c.setStrokeColor(black)
        c.line(x, self._y - 3, amt_x, self._y - 3)
        self._y -= lh + 6

        def _line(text, amount=None, bold=False, size=None):
            self._ensure_space(needed=lh)
            c = self.canvas
            c.setFont("Calibri-Bold" if bold else "Calibri",
                      size if size is not None else f["size"])
            c.drawString(x, self._y, text)
            if amount is not None:
                c.drawRightString(amt_x, self._y, f"{amount:,.2f}")
            self._y -= lh

        # BPR: suppress rental/usage subtotal lines if zero
        if data['rental_subtotal']:
            _line("Subtotal Rental and Other Charges", data['rental_subtotal'])

        if data['usage_subtotal']:
            _line("Subtotal Usage charges", data['usage_subtotal'])

        if data['discounts']:
            _line("Discounts", bold=True)
            for d in data['discounts']:
                _line(d["description"], d["amount"], size=fc)

        if data.get('adjustments_subtotal'):
            _line("Subtotal Adjustment charges",
                  data['adjustments_subtotal'], bold=True)

        # BPR11/24: gate taxes
        has_nonzero = any(t['amount'] for t in data["taxes"])
        if data["taxes"] and is_tax_section_printable(
                data.get('tax_status'), has_nonzero):
            _line("Taxes & Levies", bold=True)
            for t in data["taxes"]:
                if t['amount']:
                    _line(t["name"], t['amount'], size=fc)

    def _draw_total_charges_dynamic(self, data):
        """Total, drawn right after the summary block finishes, following
        the running self._y cursor instead of a fixed page position."""
        self._ensure_space(needed=CHARGES_TABLE["line_h"] * 2)
        self._y -= 10

        f  = FONTS["total"]
        c  = self.canvas
        x  = COORDS["total_charges_label_x"]
        ax = COORDS["total_charges_amount_x"]
        y  = self._y

        # Top and bottom horizontal lines framing the total charges row
        c.setLineWidth(0.5)
        c.setStrokeColor(black)
        c.line(x, y + 11, ax, y + 11)   # Top horizontal line
        c.line(x, y - 5, ax, y - 5)     # Bottom horizontal line

        c.setFont("Calibri-Bold", f["size"])
        c.drawString(x, y, "Total Charges for the Period")
        c.drawRightString(ax, y, f"{data['total_charges']:,.2f}")

        self._y -= CHARGES_TABLE["line_h"]

    # flowing helpers

    def _ensure_space(self, needed=None):
        needed = needed if needed is not None else CHARGES_TABLE["line_h"]
        y_min  = (self.get_page1_y_min(CHARGES_TABLE["page1_y_min"]) if self._on_page1
                  else CHARGES_TABLE["otherpage_y_min"])
        if self._y - needed < y_min:
            self.new_page()
            self._on_page1 = False
            self._y        = CHARGES_TABLE["otherpage_y_start"]

    def _write_line(self, text, amount=None, bold=False,
                    x=None, size=None):
        self._ensure_space()
        fs    = size if size is not None else CHARGES_TABLE["font_size"]
        x_pos = x if x is not None else CHARGES_TABLE["desc_x"]
        self.text(x_pos, self._y, text, size=fs, bold=bold)
        if amount is not None:
            self.number(CHARGES_TABLE["amount_x"], self._y, amount,
                        size=fs, bold=bold, align="right")
        self._y -= CHARGES_TABLE["line_h"]

    # flowing sections

    def _draw_charges_in_detail_flowing(self, data):
        """Charges in Detail — starts at fixed coord, may overflow."""
        if not data["charge_groups"]:
            return
        self._y        = COORDS["charges_detail_y_start"]
        self._on_page1 = True

        # "Charges in Detail" heading + underline, aligned to the same
        # left/right margins the group/product/charge lines below use
        # (group_ref_x / amount_x), so the whole section lines up.
        x     = CHARGES_TABLE["group_ref_x"]
        amt_x = CHARGES_TABLE["amount_x"]
        c = self.canvas
        c.setFont("Calibri-Bold", FONTS["total"]["size"])
        c.drawString(x, self._y, "Charges in Detail")
        c.setLineWidth(0.5)
        c.setStrokeColor(black)
        c.line(x, self._y - 3, amt_x, self._y - 3)
        self._y -= CHARGES_TABLE["line_h"] + 6

        for group in data["charge_groups"]:
            if group["ref"]:
                self._write_line(group["ref"], bold=True,
                                 x=CHARGES_TABLE["group_ref_x"])
            if group.get("detail_name"):
                self._write_line(group["detail_name"],
                                 x=CHARGES_TABLE["group_ref_x"])
            for product in group["products"]:
                self._write_line(product["label"], bold=True,
                                 x=CHARGES_TABLE["product_label_x"])
                for charge in product["charges"]:
                    self._write_line(charge["description"],
                                     amount=charge["amount"],
                                     x=CHARGES_TABLE["desc_x"])

    def _draw_adjustments_flowing(self, data):
        """Adjustments block — $ADJ lines."""
        if not data.get("adjustments"):
            return
        grx = CHARGES_TABLE["group_ref_x"]
        self._write_line("Adjustments", bold=True, x=grx)
        for adj in data["adjustments"]:
            self._write_line(adj["description"],
                             amount=adj["amount"],
                             x=grx)
        # BPR: adjustments_subtotal line (suppress if zero)
        if data.get("adjustments_subtotal"):
            self._write_line("Subtotal Adjustment charges",
                             amount=data["adjustments_subtotal"],
                             bold=True, x=grx)

    def _draw_top_level_discounts_flowing(self, data):
        """BPR23: ACCDISCNAME etc. block."""
        discounts = data.get("top_level_discounts", [])
        if not discounts:
            return
        grx = CHARGES_TABLE["group_ref_x"]
        self._write_line("Discounts", bold=True, x=grx)
        for d in discounts:
            self._write_line(d["description"], amount=d["amount"], x=grx)

    def _draw_discounts_and_taxes_flowing(self, data):
        """SLTDISCDETAIL discounts + Taxes + Total Charges with box."""
        grx = CHARGES_TABLE["group_ref_x"]

        if data["discounts"]:
            self._write_line("Discounts", bold=True, x=grx)
            for d in data["discounts"]:
                self._write_line(d["description"],
                                 amount=d["amount"], x=grx)

        # BPR11/24: gate taxes
        has_nonzero = any(t['amount'] for t in data["taxes"])
        if data["taxes"] and is_tax_section_printable(
                data.get('tax_status'), has_nonzero):
            self._write_line("Taxes & Levies", bold=True, x=grx)
            for t in data["taxes"]:
                if t["amount"]:
                    self._write_line(t["name"],
                                     amount=t["amount"], x=grx)

        # Total Charges framed by top/bottom horizontal lines (not a box)
        self._y -= CHARGES_TABLE["line_h"] * 0.3
        self._ensure_space(CHARGES_TABLE["line_h"] * 1.5)

        try:
            c = self.canvas
            c.setLineWidth(0.5)
            c.setStrokeColor(black)
            c.line(32.5, self._y + 9, 560.5, self._y + 9)    # Top horizontal line
            c.line(32.5, self._y - 5, 560.5, self._y - 5)    # Bottom horizontal line
        except AttributeError:
            pass

        f = FONTS["total"]
        self._write_line("Total Charges for the Period",
                         amount=data["total_charges"],
                         bold=True, size=f["size"], x=grx)
        self._y -= CHARGES_TABLE["line_h"] * 0.5

    def _draw_payments_flowing(self, data):
        """BPR26: suppress entirely if total_payments is zero."""
        if not data.get("total_payments") and not data.get("payments"):
            return
        grx    = CHARGES_TABLE["group_ref_x"]
        f_size = FONTS["payments"]["size"]

        # Remember where this block starts so the usage-table vertical
        # divider can extend up to start here, instead of at its own
        # header lower down the page.
        self._ensure_space()
        self._divider_top_y   = self._y
        self._divider_top_page = self.page_count() - 1

        self._write_line("Details of Payments Received",
                         bold=True, x=grx)
        for p in data["payments"]:
            line = (f"{p.get('pay_type', '')}-{p.get('date', '')}"
                    f"-{p.get('location', '')}").rstrip('-')
            self._ensure_space()
            self.text(grx, self._y, line, size=f_size)
            self.number(290, self._y, p["amount"],
                        size=f_size, align="right")
            self._y -= CHARGES_TABLE["line_h"]

        self._ensure_space()
        self.text(grx, self._y, "Total Payments Received",
                  size=f_size, bold=True)
        self.number(290, self._y, data["total_payments"],
                    size=f_size, bold=True, align="right")
        self._y -= CHARGES_TABLE["line_h"] * 1.5

    def _draw_cancel_payments_flowing(self, data):
        """BPR26: ACCBALFPAYDET block."""
        cancelled = data.get("cancelled_payments", [])
        if not cancelled:
            return
        grx    = CHARGES_TABLE["group_ref_x"]
        f_size = FONTS["payments"]["size"]

        self._write_line("Cancel Payment", bold=True, x=grx)
        for p in cancelled:
            line = (f"{p.get('pay_type', '')}-{p.get('date', '')}"
                    f"-{p.get('location', '')}").rstrip('-')
            self._ensure_space()
            self.text(grx, self._y, line, size=f_size)
            self.number(290, self._y, p["amount"],
                        size=f_size, align="right")
            self._y -= CHARGES_TABLE["line_h"]
        self._y -= CHARGES_TABLE["line_h"] * 0.5

    def _draw_messages_flowing(self, data):
        """BPR28: marketing messages then suspended notice."""
        messages  = data.get("marketing_messages", [])
        suspended = data.get("suspended_message", "")
        if not messages and not suspended:
            return
        grx    = CHARGES_TABLE["group_ref_x"]
        f_size = FONTS["payments"]["size"]

        if messages:
            self._write_line("Message on Bill", bold=True, x=grx)
            for m in messages:
                self._ensure_space()
                self.text(grx, self._y, m, size=f_size)
                self._y -= CHARGES_TABLE["line_h"]
        if suspended:
            self._ensure_space()
            self.text(grx, self._y, suspended,
                      size=f_size, bold=True)
            self._y -= CHARGES_TABLE["line_h"]

    # usage sections

    def _draw_usage_sections(self, data):
        for section in data.get("usage_sections", []):
            self._draw_one_usage_section(section)

    def _draw_one_usage_section(self, section):
        """Only draw subsections with actual CDR rows."""
        subsections   = section.get("subsections", [])
        subs_with_rows = [s for s in subsections if s.get("rows")]
        if not subs_with_rows:
            return

        u     = USAGE_TABLE_2COL
        grx   = u["left_col_x"][0]
        amt_x = u["left_amount_x"]

        for subsection in subs_with_rows:
            self._draw_usage_subsection(subsection)
            self._ensure_space()
            self.text(grx, self._y,
                      f"Total for {subsection.get('label', '')}",
                      size=u["font_size"], bold=True)
            self.number(amt_x, self._y,
                        subsection.get("subtotal", 0),
                        decimals=3, size=u["font_size"],
                        bold=True, align="right")
            self._y -= u["line_h"]

        label = section.get("label", "")
        self._ensure_space()
        self.text(grx, self._y,
                  f"Total Usage Charges for {label}",
                  size=u["font_size"], bold=True)
        self.number(amt_x, self._y,
                    section.get("grand_total", 0),
                    decimals=3, size=u["font_size"],
                    bold=True, align="right")
        self._y -= u["line_h"] * 1.5

    def _draw_usage_subsection(self, subsection):
        """2-up left/right CDR row layout, separated by a vertical divider.
        Left and right rows are always drawn as matched pairs (same y), so
        the divider on each page just needs to run from the header box
        down to wherever content actually stopped on that page - drawn
        after the fact, once that's known, rather than at a fixed length."""
        rows = subsection.get("rows", [])
        if not rows:
            return
        u = USAGE_TABLE_2COL
        vert_x = u["vert_line_x"]

        self._ensure_space(u["line_h"] * 3)
        self._draw_usage_headers()

        top_y  = self._y + u["line_h"]
        last_y = self._y

        # First divider drawn overall: extend its top up to where "Details
        # of Payments Received" started, if that was on this same page and
        # hasn't already been used by an earlier subsection/section.
        divider_top_y = getattr(self, "_divider_top_y", None)
        divider_top_page = getattr(self, "_divider_top_page", None)
        if divider_top_y is not None and divider_top_page == self.page_count() - 1:
            top_y = divider_top_y
        self._divider_top_y = None

        i = 0
        while i < len(rows):
            page_before = self.page_count()
            self._ensure_space(u["line_h"])
            if self.page_count() != page_before:
                self._draw_usage_vert_divider(vert_x, top_y, last_y)
                top_y = self._y + u["line_h"]

            self._draw_usage_row(rows[i],   side="left")
            if i + 1 < len(rows):
                self._draw_usage_row(rows[i + 1], side="right")
            last_y = self._y
            self._y -= u["line_h"]
            i += 2

        self._draw_usage_vert_divider(vert_x, top_y, last_y)

    def _draw_usage_vert_divider(self, x, top_y, bottom_y):
        if top_y <= bottom_y:
            return
        c = self.canvas
        c.setLineWidth(0.5)
        c.setStrokeColor(black)
        c.line(x, top_y, x, bottom_y)

    def _draw_usage_headers(self):
        """Left column only: box + headers."""
        u       = USAGE_TABLE_2COL
        headers = ["Date &Time", "Dialled No.", "Duration", "Charge"]
        lx      = u["left_col_x"][0]
        try:
            self.canvas.rect(
                lx - 3, self._y - 3,
                u["left_box_right"] - lx + 3,
                u["line_h"] + 2,
            )
        except AttributeError:
            pass
        for i, h in enumerate(headers):
            if i == len(headers) - 1:
                self.text(u["left_amount_x"], self._y, h,
                          size=u["font_header"], bold=True, align="right")
            else:
                self.text(u["left_col_x"][i], self._y, h,
                          size=u["font_header"], bold=True)
        self._y -= u["line_h"]

    def _draw_usage_row(self, row, side):
        u        = USAGE_TABLE_2COL
        col_x    = u["left_col_x"]  if side == "left"  else u["right_col_x"]
        amount_x = u["left_amount_x"] if side == "left" else u["right_amount_x"]

        date     = row[0] if len(row) > 0 else ""
        time     = row[1] if len(row) > 1 else ""
        dialled  = row[2] if len(row) > 2 else ""
        duration = row[3] if len(row) > 3 else ""
        charge   = row[4] if len(row) > 4 else "0"

        self.text(col_x[0], self._y,
                  f"{date} {time}".strip(), size=u["font_size"])
        self.text(col_x[1], self._y, dialled,  size=u["font_size"])
        self.text(col_x[2], self._y, duration, size=u["font_size"])
        self.number(amount_x, self._y, _safe_float(charge),
                    size=u["font_size"], align="right")


    def _stamp_all_page_indicators(self, data):
        total = self.page_count()
        for idx in range(total):
            c = self.canvases[idx][1]
            if idx == 0:
                c.setFont("Calibri", 9)
                c.drawRightString(540, 753, f"1  of  {total}")
            else:
                c.setFont("Calibri-Bold", 10)
                c.drawString(45, 795,
                             f'Invoice No.{data["invoice_number"]}')
                c.setFont("Calibri", 9)
                c.drawRightString(540, 795,
                                  f"{idx + 1}  of  {total}")


def _safe_float(v):
    try:
        return float(str(v).replace(",", ""))
    except (ValueError, TypeError):
        return 0