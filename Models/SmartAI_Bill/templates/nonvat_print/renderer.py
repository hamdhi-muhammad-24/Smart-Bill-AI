"""
NonVAT Print Renderer.
Handles rendering for NonVAT Home and NonVAT Enterprise print invoices
using Print_RED.pdf and Print_NONRED.pdf templates with exact coordinates.
"""
import os
from datetime import datetime
from reportlab.lib.colors import black, white

from core.pdf_renderer import BaseRenderer
from core.bill_common import is_tax_section_printable
from core.gmf_reader import is_red_notice
from templates.nonvat_print.config import COORDS, CHARGES_TABLE, FONTS, POST_TC_COLUMNS

TEMPLATES_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRINT_NONRED_PDF = os.path.join(TEMPLATES_DIR, "Print_NONRED.pdf")
PRINT_RED_PDF = os.path.join(TEMPLATES_DIR, "Print_RED.pdf")


class NonVATPrintRenderer(BaseRenderer):

    def __init__(self):
        super().__init__(PRINT_NONRED_PDF)
        self.is_red = False

    def check_red_notice(self, data):
        filename = str(data.get("source_filename") or data.get("filename") or "")
        if is_red_notice(filename):
            self.is_red = True
            if os.path.exists(PRINT_RED_PDF):
                self.set_template_pdf(PRINT_RED_PDF)
        else:
            if os.path.exists(PRINT_NONRED_PDF):
                self.set_template_pdf(PRINT_NONRED_PDF)

    def render(self, data):
        self.check_red_notice(data)
        self._draw_header(data)
        self._draw_summary_boxes(data)
        self._draw_page1_footer(data)

        y = self._draw_charges(data.get("product_labels", []))
        y = self._draw_adjustments(data, y)
        y = self._draw_top_level_discounts(data, y)
        y = self._draw_taxes_only(data, y)

        y = self._draw_total_charges_dynamic(data, y)
        self._draw_post_total_charges_flow(data, y)

        total_pages = self.page_count()
        self._draw_page_indicators(data, total_pages)

    def _draw_header(self, data):
        """Draw header information on page 1"""
        f = FONTS["header"]
        self.text(*COORDS["telephone_number"], data.get("telephone_number", ""), size=f["size"], align="left")
        self.text(*COORDS["account_number"],   data.get("account_number", ""),   size=f["size"], align="left")
        self.text(*COORDS["invoice_number"],   data.get("invoice_number", ""),   size=f["size"], align="left")
        self.text(*COORDS["billing_date"],     data.get("billing_date", ""),     size=f["size"], align="left")
        period = f"{data.get('billing_period_start', '')} - {data.get('billing_period_end', '')}"
        self.text(*COORDS["billing_period"],   period,                           size=f["size"], align="left")

        # HOME / ENTERPRISE badge in the blue box
        fb = FONTS["badge"]
        badge = data.get("badge", "")
        if badge:
            self.text(*COORDS["badge_text"], badge, size=fb["size"], bold=fb["bold"], align="center")

        # TIN numbers above the badge box
        ft = FONTS["tin"]
        customer_tin = data.get("customer_vat_reg", "")
        slt_tin      = data.get("slt_vat_reg", "")
        if customer_tin:
            self.text(*COORDS["customer_tin"], f"Customer TIN: {customer_tin}", size=ft["size"], align="left")
        if slt_tin:
            self.text(*COORDS["slt_tin"], f"SLT TIN: {slt_tin}", size=ft["size"], align="left")

    def _draw_summary_boxes(self, data):
        """Draw summary boxes on page 1"""
        f = FONTS["summary_box"]
        self.number(*COORDS["balance_bf"],             data.get("balance_bf", 0),             size=f["size"], align="center")
        self.number(*COORDS["payments_received"],      data.get("payments_received", 0),      size=f["size"], align="center")
        self.number(*COORDS["charges_for_the_period"], data.get("charges_period", 0),         size=f["size"], align="center")
        f_tot = FONTS["summary_total"]
        self.number(*COORDS["total_payable"],          data.get("total_payable", 0),          size=f_tot["size"], bold=True, align="center")
        self.text(*COORDS["payment_due_date"],         data.get("payment_due_date", ""),      size=f["size"], bold=True, align="center")

    def _draw_page1_footer(self, data):
        """Draw payment slip at bottom of page 1"""
        f = FONTS["slip"]
        self.text(*COORDS["slip_telephone"], data.get("telephone_number", ""), size=f["size"], align="left")
        self.text(*COORDS["slip_invoice"],   data.get("invoice_number", ""),   size=f["size"], align="left")
        slip_name = (
            data.get("business_name")
            if data.get("address_name_not_required")
            else (data.get("business_name") or data.get("customer_name", ""))
        )
        self.text(*COORDS["slip_customer"], slip_name or "",                  size=f["size"], align="left")
        self.text(*COORDS["slip_account"],  data.get("account_number", ""),   size=f["size"], align="left")

    def _draw_charges(self, product_labels):
        """Draw product charges table"""
        y      = CHARGES_TABLE["page1_y_start"]
        y_min  = self.get_page1_y_min(CHARGES_TABLE["page1_y_min"])
        line_h = CHARGES_TABLE["line_h"]
        lp_gap = CHARGES_TABLE["product_label_y_gap"]
        f  = FONTS["product_label"]
        fc = FONTS["charge_line"]
        prod_x = CHARGES_TABLE["product_label_x"]
        desc_x = CHARGES_TABLE["desc_x"]
        amt_x  = CHARGES_TABLE["amount_x"]

        for product in product_labels:
            space = lp_gap + len(product.get("charges", [])) * line_h
            if y - space < y_min:
                self.new_page()
                y     = CHARGES_TABLE["otherpage_y_start"]
                y_min = CHARGES_TABLE["otherpage_y_min"]

            self.text(prod_x, y, product.get("label", ""), size=f["size"], bold=f["bold"])
            y -= lp_gap

            for charge in product.get("charges", []):
                if y < y_min:
                    self.new_page()
                    y     = CHARGES_TABLE["otherpage_y_start"]
                    y_min = CHARGES_TABLE["otherpage_y_min"]
                self.text(desc_x, y, charge.get("description", ""), size=fc["size"])
                if charge.get("amount") is not None:
                    self.number(amt_x, y, charge["amount"], size=fc["size"], align="right")
                y -= line_h
        return y

    def _draw_adjustments(self, data, y):
        """Draw adjustments section"""
        if not data.get("adjustments"):
            return y
        f      = FONTS["taxes"]
        line_h = CHARGES_TABLE["line_h"]
        y_min  = self.get_page1_y_min(CHARGES_TABLE["page1_y_min"]) if self.page_count() == 1 else CHARGES_TABLE["otherpage_y_min"]
        prod_x = CHARGES_TABLE["product_label_x"]
        desc_x = CHARGES_TABLE["desc_x"]
        amt_x  = CHARGES_TABLE["amount_x"]

        if y - line_h * 2 < y_min:
            self.new_page()
            y = CHARGES_TABLE["otherpage_y_start"]
            y_min = CHARGES_TABLE["otherpage_y_min"]

        self.text(prod_x, y, "Adjustments", size=f["size"], bold=True)
        y -= line_h
        for adj in data["adjustments"]:
            if y - line_h < y_min:
                self.new_page()
                y = CHARGES_TABLE["otherpage_y_start"]
                y_min = CHARGES_TABLE["otherpage_y_min"]
            self.text(desc_x, y, adj.get("description", ""), size=f["size"])
            self.number(amt_x, y, adj.get("amount", 0), size=f["size"], align="right")
            y -= line_h
        return y

    def _draw_top_level_discounts(self, data, y):
        """Draw top level discounts section"""
        discounts = data.get("top_level_discounts", [])
        if not discounts:
            return y
        f      = FONTS["taxes"]
        line_h = CHARGES_TABLE["line_h"]
        y_min  = self.get_page1_y_min(CHARGES_TABLE["page1_y_min"]) if self.page_count() == 1 else CHARGES_TABLE["otherpage_y_min"]
        prod_x = CHARGES_TABLE["product_label_x"]
        desc_x = CHARGES_TABLE["desc_x"]
        amt_x  = CHARGES_TABLE["amount_x"]

        if y - line_h * 2 < y_min:
            self.new_page()
            y = CHARGES_TABLE["otherpage_y_start"]
            y_min = CHARGES_TABLE["otherpage_y_min"]

        self.text(prod_x, y, "Discounts", size=f["size"], bold=True)
        y -= line_h
        for d in discounts:
            if y - line_h < y_min:
                self.new_page()
                y = CHARGES_TABLE["otherpage_y_start"]
                y_min = CHARGES_TABLE["otherpage_y_min"]
            self.text(desc_x, y, d.get("description", ""), size=f["size"])
            self.number(amt_x, y, d.get("amount", 0), size=f["size"], align="right")
            y -= line_h
        return y

    def _draw_taxes_only(self, data, y):
        """Draw taxes section. NonVAT Home shows only total summation of Taxes & Levies."""
        total_tax = data.get("inv_total_tax")
        if total_tax is None:
            total_tax = data.get("taxes_total") or sum(t.get("amount", 0) for t in data.get("taxes", []))

        has_nonzero = bool(total_tax) or any(t.get('amount') for t in data.get("taxes", []))
        if not is_tax_section_printable(data.get("tax_status"), has_nonzero):
            return y
        f      = FONTS["taxes"]
        line_h = CHARGES_TABLE["line_h"]
        y_min  = self.get_page1_y_min(CHARGES_TABLE["page1_y_min"]) if self.page_count() == 1 else CHARGES_TABLE["otherpage_y_min"]
        prod_x = CHARGES_TABLE["product_label_x"]
        desc_x = CHARGES_TABLE["desc_x"]
        amt_x  = CHARGES_TABLE["amount_x"]

        if y - line_h * 2 < y_min:
            self.new_page()
            y = CHARGES_TABLE["otherpage_y_start"]
            y_min = CHARGES_TABLE["otherpage_y_min"]

        self.text(prod_x, y, "Taxes & Levies", size=f["size"], bold=True)
        y -= line_h

        is_home = (data.get("badge", "").upper() == "HOME" or data.get("template_id") == "nonvat_home")
        if is_home:
            self.text(desc_x, y, "Taxes & Levies", size=f["size"])
            self.number(amt_x, y, total_tax, size=f["size"], align="right")
            y -= line_h
        else:
            for t in data.get("taxes", []):
                if t.get("amount"):
                    if y - line_h < y_min:
                        self.new_page()
                        y = CHARGES_TABLE["otherpage_y_start"]
                        y_min = CHARGES_TABLE["otherpage_y_min"]
                    self.text(desc_x, y, t.get("name", ""), size=f["size"])
                    self.number(amt_x, y, t.get("amount", 0), size=f["size"], align="right")
                    y -= line_h
        return y

    def _draw_total_charges_dynamic(self, data, y):
        """Draw total charges line"""
        line_h = CHARGES_TABLE["line_h"]
        y_min = self.get_page1_y_min(CHARGES_TABLE["page1_y_min"]) if self.page_count() == 1 else CHARGES_TABLE["otherpage_y_min"]

        if y - line_h * 2 < y_min:
            self.new_page()
            y = CHARGES_TABLE["otherpage_y_start"]

        y -= 6
        c = self.canvas
        f = FONTS["total"]
        x = CHARGES_TABLE["total_charges_label_x"]
        ax = CHARGES_TABLE["total_charges_amount_x"]

        c.setLineWidth(0.5)
        c.setStrokeColor(black)
        c.line(x, y + 11, ax, y + 11)
        c.line(x, y - 5, ax, y - 5)

        c.setFont("Helvetica-Bold", f["size"])
        c.drawString(x, y, "Total Charges for the Period")
        c.drawRightString(ax, y, f"{data.get('total_charges', 0):,.2f}")

        return y - line_h * 2.0

    def _draw_post_total_charges_flow(self, data, y_tc):
        """Draw post-total charges flow including payments and messages"""
        left = POST_TC_COLUMNS["left"]
        right = POST_TC_COLUMNS["right"]
        vert_x = POST_TC_COLUMNS["vert_line_x"]

        line_h = 8  # Reduced from 9 for better fit
        y_start_other = CHARGES_TABLE.get("otherpage_y_start", 740.0)
        y_min_other = CHARGES_TABLE.get("otherpage_y_min", 80.0)

        first_page_idx = self.page_count() - 1
        first_col_top = y_tc - 6

        state = {"col": "left", "y": first_col_top}
        line_extents = {}

        def col_def():
            return left if state["col"] == "left" else right

        def floor_y():
            return self.get_page1_y_min(CHARGES_TABLE["page1_y_min"]) if self.page_count() == 1 else y_min_other

        def new_column_top():
            return first_col_top if self.page_count() - 1 == first_page_idx else y_start_other

        def record(y_val):
            idx = self.page_count() - 1
            ext = line_extents.setdefault(idx, {"top": y_val, "bottom": y_val})
            ext["top"] = max(ext["top"], y_val)
            ext["bottom"] = min(ext["bottom"], y_val)

        def ensure_space(height):
            if state["y"] - height >= floor_y():
                return
            if state["col"] == "left":
                state["col"] = "right"
                state["y"] = new_column_top()
            else:
                self.new_page()
                state["col"] = "left"
                state["y"] = y_start_other

        def draw_text(text, bold=False, size=7.5, x=None):  # Reduced size from 8.5
            c = self.canvas
            cd = col_def()
            c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
            c.setFillColor(black)
            c.drawString(x if x is not None else cd["x_start"], state["y"], str(text))
            record(state["y"])

        def draw_amount(value, bold=False, size=7.5, fmt="{:,.2f}"):  # Reduced size from 8.5
            c = self.canvas
            cd = col_def()
            c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
            c.drawRightString(cd["x_end"], state["y"], fmt.format(value))
            record(state["y"])

        def advance(mult=1.0):
            state["y"] -= line_h * mult

        # 1. Details of Payments Received
        payments = data.get("payments", [])
        if data.get("total_payments") or payments:
            ensure_space(line_h * (len(payments) + 2.6))
            draw_text("Details of Payments Received", bold=True, size=8.5)
            advance(1.2)
            for p in payments:
                ensure_space(line_h)
                line = f"{p.get('pay_type', 'Payment')}-{p.get('date', '')}-{p.get('location', '')}".rstrip('-')
                draw_text(line, size=7.5)
                draw_amount(p.get('amount', 0), size=7.5)
                advance()
            ensure_space(line_h * 1.4)
            draw_text("Total Payments Received", bold=True, size=8.5)
            draw_amount(data.get('total_payments', 0), bold=True, size=8.5)
            advance(1.6)

        # 2. Marketing messages / suspended notice
        messages = data.get("marketing_messages", [])
        suspended = data.get("suspended_message", "")
        if messages:
            ensure_space(line_h * 1.2)
            draw_text("Message on Bill", bold=True, size=8.5)
            advance(1.2)
            for m in messages:
                ensure_space(line_h)
                draw_text(m, size=7.5)
                advance()
        if suspended:
            ensure_space(line_h)
            draw_text(suspended, bold=True, size=8.5)
            advance()

        # Vertical divider line
        last_page_idx = self.page_count() - 1
        for idx in range(first_page_idx, last_page_idx + 1):
            c_idx = self.canvases[idx][1]
            c_idx.setLineWidth(0.5)
            c_idx.setStrokeColor(black)
            top_y = y_tc if idx == first_page_idx else y_start_other + 5
            bottom_y = line_extents[idx]["bottom"] - 5 if idx in line_extents else max(CHARGES_TABLE["page1_y_min"] if idx == 0 else y_min_other, top_y - 20)
            if top_y > bottom_y:
                c_idx.line(vert_x, top_y, vert_x, bottom_y)

    def _draw_page_indicators(self, data, total_pages):
        """Draw page numbers and invoice number on all pages"""
        f = FONTS["page_indicator"]
        inv_f = FONTS["invoice_no_p2"]
        
        for idx in range(len(self.canvases)):
            c = self.canvases[idx][1]
            
            # Page number - consistent position on all pages
            if idx == 0:
                x, y = COORDS["page_indicator_p1"]
            else:
                x, y = COORDS["page_indicator_p2"]
            
            c.setFont("Helvetica", f["size"])
            c.drawRightString(x, y, f"{idx + 1}  of  {total_pages}")
            
            # Invoice number on page 2 and beyond
            if idx > 0:
                ix, iy = COORDS["page_invoice_no_p2"]
                c.setFont("Helvetica-Bold", inv_f["size"])
                c.drawString(ix, iy, f'Invoice No.{data.get("invoice_number", "")}')