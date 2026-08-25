"""NonVAT Enterprise Renderer (Sheet 19)."""
import os
from datetime import datetime

from reportlab.lib.colors import black, white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from core.pdf_renderer import BaseRenderer
from core.bill_common import is_tax_section_printable
from templates.nonvat_enterprise.config import COORDS, CHARGES_TABLE, FONTS, POST_TC_COLUMNS

TEMPLATE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PDF = os.path.join(TEMPLATE_DIR, "layout.pdf")

# Calibri, scoped to this template only - shared font files (not duplicated
# per template), registered under names distinct from Helvetica so no other
# template is affected.
_FONTS_DIR = os.path.join(os.path.dirname(TEMPLATE_DIR), "fonts")
if "Calibri" not in pdfmetrics.getRegisteredFontNames():
    pdfmetrics.registerFont(TTFont("Calibri", os.path.join(_FONTS_DIR, "calibri.ttf")))
    pdfmetrics.registerFont(TTFont("Calibri-Bold", os.path.join(_FONTS_DIR, "calibrib.ttf")))


class NonVATEnterpriseRenderer(BaseRenderer):
    FONT_NAME = "Calibri"

    def __init__(self):
        super().__init__(TEMPLATE_PDF)

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

        self._draw_customer(data)
        self._draw_badge()
        self._draw_generation_id(data)
        self._draw_summary_boxes(data)
        self._draw_page1_footer(data)

        y = self._draw_charges(data["product_labels"])
        y = self._draw_adjustments(data, y)
        y = self._draw_top_level_discounts(data, y)
        y = self._draw_taxes_only(data, y)

        y = self._draw_total_charges_dynamic(data, y)
        self._draw_post_total_charges_flow(data, y)

        total_pages = self.page_count()
        self._draw_page_indicators(data, total_pages)


    def _draw_header(self, data):
        f = FONTS["header"]
        x, y = COORDS["telephone_number"]
        self.text(x, y, data["telephone_number"], size=f["size"])
        x, y = COORDS["account_number"]
        self.text(x, y, data["account_number"], size=f["size"])
        x, y = COORDS["invoice_number"]
        self.text(x, y, data["invoice_number"], size=f["size"])
        x, y = COORDS["billing_date"]
        self.text(x, y, data["billing_date"], size=f["size"])
        period = (f"{data['billing_period_start']} - "
                  f"{data['billing_period_end']}")
        x, y = COORDS["billing_period"]
        self.text(x, y, period, size=f["size"])

    def _draw_customer(self, data):
        f = FONTS["customer_name"]
        if data.get("address_name_not_required"):
            top = data.get("business_name") or data.get("customer_name", "")
        else:
            top = data.get("business_name") or data.get("customer_name", "")
        x, y = COORDS["customer_business"]
        self.text(x, y, top, size=f["size"], bold=f["bold"])

        fa   = FONTS["customer_addr"]
        addr = data["address_lines"] + (
            [data["zip_code"]] if data["zip_code"] else [])
        self.multiline_block(
            float(COORDS["customer_addr_x"]), float(COORDS["customer_addr_start"]),
            addr, line_height=float(COORDS["customer_addr_line_h"]),
            size=fa["size"], bold=fa["bold"],
        )

    def _draw_badge(self):
        f = FONTS["badge"]
        x, y = COORDS["badge_text"]
        self.text(x, y, "ENTERPRISE", size=f["size"], bold=f["bold"])

    def _draw_generation_id(self, data):
        f   = FONTS["gen_id"]
        due = data.get("payment_due_date", "")
        try:
            dd, mm, yyyy = due.split("/")
            due_mmddyy   = f"{mm}{dd}{yyyy}"
        except ValueError:
            due_mmddyy = ""
        ts   = datetime.now().strftime("%H:%M:%S")

        # Clean the source filename by removing the random suffix (e.g. __sqg099w7_1.gmf)
        source_file = data.get("source_filename", "")
        if "__" in source_file:
            source_file = source_file.split("__")[0] + "_"

        line = f'{source_file}_{ts}{due_mmddyy}'
        x, y = COORDS["gen_id_line"]
        self.text(x, y, line, size=f["size"])
        if data.get("customer_segment"):
            x2, y2 = COORDS["gen_id_line2"]
            self.text(x2, y2, data["customer_segment"], size=f["size"])

    def _draw_summary_boxes(self, data):
        f = FONTS["summary_box"]
        x, y = COORDS["balance_bf"]
        self.number(x, y, data["balance_bf"], size=f["size"], align="center")
        x, y = COORDS["payments_received"]
        self.number(x, y, data["payments_received"], size=f["size"], align="center")
        x, y = COORDS["charges_period"]
        self.number(x, y, data["charges_period"], size=f["size"], align="center")
        f = FONTS["summary_total"]
        x, y = COORDS["total_payable"]
        self.number(x, y, data["total_payable"], size=f["size"], bold=True, align="center")
        x, y = COORDS["payment_due_date"]
        self.text(x, y, data["payment_due_date"], size=f["size"], bold=True, align="center")

    def _draw_page1_footer(self, data):
        px, py = COORDS["payonline_qr"]
        self.draw_static_payonline_qr(px, py, size=float(COORDS["payonline_qr_size"]))
        qx, qy = COORDS["qr_code"]
        self.draw_qr(
            qx, qy,
            account_number=data["account_number"],
            total_charges=data["total_charges"],
            size=float(COORDS["qr_size"]),
        )
        bx, by = COORDS["barcode"]
        self.draw_barcode(
            bx, by, data["account_number"],
            width=float(COORDS["barcode_width"]), height=float(COORDS["barcode_height"]),
        )
        sx, sy = COORDS["slip_barcode"]
        self.draw_slip_barcode(
            sx, sy,
            bill_ref=data["invoice_number"],
            total_charges=data["total_charges"],
            width=float(COORDS["slip_barcode_width"]),
            height=float(COORDS["slip_barcode_height"]),
        )
        f = FONTS["slip"]
        x, y = COORDS["slip_telephone"]
        self.text(x, y, data["telephone_number"], size=f["size"])
        x, y = COORDS["slip_invoice"]
        self.text(x, y, data["invoice_number"], size=f["size"])
        slip_name = (
            data.get("business_name")
            if data.get("address_name_not_required")
            else (data.get("business_name") or data.get("customer_name", ""))
        )
        x, y = COORDS["slip_customer"]
        self.text(x, y, slip_name or "", size=f["size"])
        x, y = COORDS["slip_account"]
        self.text(x, y, data["account_number"], size=f["size"])

    def _draw_charges(self, product_labels):
        y      = CHARGES_TABLE["page1_y_start"]
        y_min  = self.get_page1_y_min(CHARGES_TABLE["page1_y_min"])
        line_h = CHARGES_TABLE["line_h"]
        lp_gap = CHARGES_TABLE["product_label_y_gap"]
        f  = FONTS["product_label"]
        fc = FONTS["charge_line"]

        for product in product_labels:
            space = lp_gap + len(product["charges"]) * line_h
            if y - space < y_min:
                self.new_page()
                y     = CHARGES_TABLE["otherpage_y_start"]
                y_min = CHARGES_TABLE["otherpage_y_min"]

            self.text(CHARGES_TABLE["product_label_x"], y,
                      product["label"], size=f["size"], bold=f["bold"])
            y -= lp_gap

            for charge in product["charges"]:
                if y < y_min:
                    self.new_page()
                    y     = CHARGES_TABLE["otherpage_y_start"]
                    y_min = CHARGES_TABLE["otherpage_y_min"]
                self.text(CHARGES_TABLE["desc_x"], y,
                          charge["description"], size=fc["size"])
                if charge["amount"]:
                    self.number(CHARGES_TABLE["amount_x"], y,
                                charge["amount"], size=fc["size"],
                                align="right")
                y -= line_h
        return y

    def _draw_adjustments(self, data, y):
        if not data.get("adjustments"):
            return y
        f      = FONTS["taxes"]
        line_h = CHARGES_TABLE["line_h"]
        y_min  = self.get_page1_y_min(CHARGES_TABLE["page1_y_min"]) if self.page_count() == 1 else CHARGES_TABLE["otherpage_y_min"]
        if y - line_h * 2 < y_min:
            self.new_page()
            y = CHARGES_TABLE["otherpage_y_start"]
            y_min = CHARGES_TABLE["otherpage_y_min"]

        self.text(CHARGES_TABLE["product_label_x"], y, "Adjustments",
                  size=f["size"], bold=True)
        y -= line_h
        for adj in data["adjustments"]:
            if y - line_h < y_min:
                self.new_page()
                y = CHARGES_TABLE["otherpage_y_start"]
                y_min = CHARGES_TABLE["otherpage_y_min"]
            self.text(CHARGES_TABLE["desc_x"], y,
                      adj["description"], size=f["size"])
            self.number(CHARGES_TABLE["amount_x"], y,
                        adj["amount"], size=f["size"], align="right")
            y -= line_h
        return y

    def _draw_top_level_discounts(self, data, y):
        discounts = data.get("top_level_discounts", [])
        if not discounts:
            return y
        f      = FONTS["taxes"]
        line_h = CHARGES_TABLE["line_h"]
        y_min  = self.get_page1_y_min(CHARGES_TABLE["page1_y_min"]) if self.page_count() == 1 else CHARGES_TABLE["otherpage_y_min"]
        if y - line_h * 2 < y_min:
            self.new_page()
            y = CHARGES_TABLE["otherpage_y_start"]
            y_min = CHARGES_TABLE["otherpage_y_min"]

        self.text(CHARGES_TABLE["product_label_x"], y, "Discounts",
                  size=f["size"], bold=True)
        y -= line_h
        for d in discounts:
            if y - line_h < y_min:
                self.new_page()
                y = CHARGES_TABLE["otherpage_y_start"]
                y_min = CHARGES_TABLE["otherpage_y_min"]
            self.text(CHARGES_TABLE["desc_x"], y,
                      d["description"], size=f["size"])
            self.number(CHARGES_TABLE["amount_x"], y,
                        d["amount"], size=f["size"], align="right")
            y -= line_h
        return y

    def _draw_taxes_only(self, data, y):
        has_nonzero = any(t['amount'] for t in data.get("taxes", []))
        if not is_tax_section_printable(data.get("tax_status"), has_nonzero):
            return y
        f      = FONTS["taxes"]
        line_h = CHARGES_TABLE["line_h"]
        y_min  = self.get_page1_y_min(CHARGES_TABLE["page1_y_min"]) if self.page_count() == 1 else CHARGES_TABLE["otherpage_y_min"]
        if y - line_h * 2 < y_min:
            self.new_page()
            y = CHARGES_TABLE["otherpage_y_start"]
            y_min = CHARGES_TABLE["otherpage_y_min"]

        self.text(CHARGES_TABLE["product_label_x"], y, "Taxes & Levies",
                  size=f["size"], bold=True)
        y -= line_h
        for t in data.get("taxes", []):
            if t["amount"]:
                if y - line_h < y_min:
                    self.new_page()
                    y = CHARGES_TABLE["otherpage_y_start"]
                    y_min = CHARGES_TABLE["otherpage_y_min"]
                self.text(CHARGES_TABLE["desc_x"], y,
                          t["name"], size=f["size"])
                self.number(CHARGES_TABLE["amount_x"], y,
                            t["amount"], size=f["size"], align="right")
                y -= line_h
        return y

    def _draw_total_charges_dynamic(self, data, y):
        line_h = CHARGES_TABLE["line_h"]
        y_min = self.get_page1_y_min(CHARGES_TABLE["page1_y_min"]) if self.page_count() == 1 else CHARGES_TABLE["otherpage_y_min"]
        
        # If there isn't enough space, push to a new page
        if y - line_h * 2 < y_min:
            self.new_page()
            y = CHARGES_TABLE["otherpage_y_start"]
            
        # Push total charges text slightly down to align between background template lines
        y -= 6
        if self.page_count() == 1:
            self._payments_top_y_p1 = y
            self._total_charges_bottom_y_p1 = y - 5
            
        c = self.canvas
        f = FONTS["total"]
        x = COORDS["total_charges_label_x"]
        ax = COORDS["total_charges_amount_x"]
        
        # Draw the top and bottom horizontal black lines around the total charges row
        c.setLineWidth(0.5)
        c.setStrokeColor(black)
        c.line(x, y + 11, ax, y + 11)   # Top horizontal line
        c.line(x, y - 5, ax, y - 5)     # Bottom horizontal line
        
        c.setFont("Calibri-Bold", f["size"])
        c.drawString(x, y, "Total Charges for the Period")
        c.drawRightString(ax, y, f"{data['total_charges']:,.2f}")

        self._total_charges_page_idx = self.page_count() - 1
        self._total_charges_line_start_y = y - 5

        return y - line_h * 2.0

    def _draw_post_total_charges_flow(self, data, y_tc):
        left = POST_TC_COLUMNS["left"]
        right = POST_TC_COLUMNS["right"]
        vert_x = POST_TC_COLUMNS["vert_line_x"]

        line_h = 9
        y_start_other = CHARGES_TABLE.get("otherpage_y_start", 740.0)
        y_min_other = CHARGES_TABLE.get("otherpage_y_min", 80.0)

        first_page_idx = self.page_count() - 1
        first_col_top = y_tc - 6

        state = {"col": "left", "y": first_col_top}
        line_extents = {}   # page_idx -> {"top": y, "bottom": y}

        def col_def():
            return left if state["col"] == "left" else right

        def floor_y():
            return self.get_page1_y_min(CHARGES_TABLE["page1_y_min"]) if self.page_count() == 1 \
                else y_min_other


        def new_column_top():
            return first_col_top if self.page_count() - 1 == first_page_idx \
                else y_start_other

        def record(y_val):
            idx = self.page_count() - 1
            ext = line_extents.setdefault(idx, {"top": y_val, "bottom": y_val})
            ext["top"] = max(ext["top"], y_val)
            ext["bottom"] = min(ext["bottom"], y_val)

        def draw_cdr_header():
            c = self.canvas
            cd = col_def()
            c.setLineWidth(0.5)
            c.setStrokeColor(black)
            c.rect(cd["x_start"] - 3, state["y"] - 2,
                   (cd["x_end"] - cd["x_start"]) + 3, line_h + 2,
                   stroke=1, fill=0)
            col_width = cd["x_end"] - cd["x_start"]
            xs = [cd["x_start"], cd["x_start"] + col_width * 0.35,
                  cd["x_start"] + col_width * 0.60]
            c.setFont("Calibri-Bold", 7)
            for i, h in enumerate(["Date &Time", "Dialled No.", "Duration"]):
                c.drawString(xs[i], state["y"], h)
            c.drawRightString(cd["x_end"], state["y"], "Charge")
            record(state["y"])

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

        def draw_text(text, bold=False, size=9, x=None):
            c = self.canvas
            cd = col_def()
            c.setFont("Calibri-Bold" if bold else "Calibri", size)
            c.setFillColor(black)
            c.drawString(x if x is not None else cd["x_start"], state["y"], text)
            record(state["y"])

        def draw_amount(value, bold=False, size=9, fmt="{:,.2f}"):
            c = self.canvas
            cd = col_def()
            c.setFont("Calibri-Bold" if bold else "Calibri", size)
            c.drawRightString(cd["x_end"], state["y"], fmt.format(value))
            record(state["y"])

        def advance(mult=1.0):
            state["y"] -= line_h * mult

        def get_last_numeric(row):
            for val in reversed(row):
                if val is None:
                    continue
                s = str(val).replace(",", "").strip()
                if not s:
                    continue
                try:
                    return float(s)
                except (ValueError, TypeError):
                    continue
            return 0.0

        def sum_rows(rows):
            return sum(get_last_numeric(r) for r in rows if r)

        # ---- 1. Details of Payments Received ----
        payments = data.get("payments", [])
        if data.get("total_payments") or payments:
            ensure_space(line_h * (len(payments) + 2.6))
            draw_text("Details of Payments Received", bold=True)
            advance(1.2)
            for p in payments:
                ensure_space(line_h)
                line = (f"{p.get('pay_type', 'Payment')}-"
                        f"{p.get('date', '')}-"
                        f"{p.get('location', '')}").rstrip('-')
                draw_text(line)
                draw_amount(p['amount'])
                advance()
            ensure_space(line_h * 1.4)
            draw_text("Total Payments Received", bold=True)
            draw_amount(data.get('total_payments', 0), bold=True)
            advance(1.6)

        # ---- 2. Cancel Payment ----
        cancelled = data.get("cancelled_payments", [])
        if cancelled:
            ensure_space(line_h * (len(cancelled) + 1.4))
            draw_text("Cancel Payment", bold=True)
            advance(1.2)
            for p in cancelled:
                ensure_space(line_h)
                line = (f"{p.get('pay_type', '')}-{p.get('date', '')}"
                        f"-{p.get('location', '')}").rstrip('-')
                draw_text(line)
                draw_amount(p['amount'])
                advance()
            advance(1.2)

        # ---- 3. Detailed usage / CDR sections ----
        sections = [s for s in data.get("usage_sections", []) if s["subsections"]]
        for section in sections:
            ensure_space(line_h * 4.5)
            hdr = f'Detailed Usage Charges for {section["label"]}'
            if section.get("phone"):
                hdr += f' {section["phone"]}'
            draw_text(hdr, bold=True, size=8)
            advance(1.4)

            for sub in section["subsections"]:
                rows = sub.get("rows", [])
                if not rows:
                    continue
                sub_label = sub.get("label")
                if sub_label:
                    ensure_space(line_h * 2.7)
                    draw_text(sub_label, bold=True)
                    advance(1.2)

                ensure_space(line_h * 1.5)
                draw_cdr_header()
                advance(1.5)

                for row in rows:
                    ensure_space(line_h)
                    cd = col_def()
                    col_width = cd["x_end"] - cd["x_start"]
                    date = row[0] if len(row) > 0 else ""
                    time_ = row[1] if len(row) > 1 else ""
                    dialled = row[2] if len(row) > 2 else ""
                    duration = row[3] if len(row) > 3 else ""
                    charge = row[4] if len(row) > 4 else "0"
                    c = self.canvas
                    c.setFont("Calibri", 7)
                    c.setFillColor(black)
                    c.drawString(cd["x_start"], state["y"], f"{date} {time_}".strip())
                    c.drawString(cd["x_start"] + col_width * 0.35, state["y"], str(dialled))
                    c.drawString(cd["x_start"] + col_width * 0.60, state["y"], str(duration))
                    try:
                        val = float(str(charge).replace(",", ""))
                    except (ValueError, TypeError):
                        val = 0.0
                    c.drawRightString(cd["x_end"], state["y"], f"{val:,.3f}")
                    record(state["y"])
                    advance()

                sub_total = sum_rows(rows)
                ensure_space(line_h * 1.5)
                draw_text(f"Total for {sub_label or 'SLT-Mobile'}", bold=True, size=7)
                draw_amount(sub_total, bold=True, size=7, fmt="{:,.3f}")
                advance(1.5)

            gt = section.get("grand_total") or sum_rows(
                r for s in section["subsections"] for r in s["rows"])
            ensure_space(line_h * 2.5)
            draw_text(f"Total Usage Charges for {section['label']}", bold=True, size=8)
            draw_amount(gt, bold=True, size=8, fmt="{:,.3f}")
            advance(2.5)

        # ---- 4. Marketing messages / suspended notice ----
        messages = data.get("marketing_messages", [])
        suspended = data.get("suspended_message", "")
        if messages:
            ensure_space(line_h * 1.2)
            draw_text("Message on Bill", bold=True)
            advance(1.2)
            for m in messages:
                ensure_space(line_h)
                draw_text(m)
                advance()
        if suspended:
            ensure_space(line_h)
            draw_text(suspended, bold=True)
            advance()

        # ---- Vertical divider line, drawn per page after content is known ----
        last_page_idx = self.page_count() - 1
        for idx in range(first_page_idx, last_page_idx + 1):
            c_idx = self.canvases[idx][1]
            c_idx.setLineWidth(0.5)
            c_idx.setStrokeColor(black)

            top_y = y_tc if idx == first_page_idx else y_start_other + 5
            if idx in line_extents:
                bottom_y = line_extents[idx]["bottom"] - 5
            else:
                bottom_y = max(
                    CHARGES_TABLE["page1_y_min"] if idx == 0 else y_min_other,
                    top_y - 20,
                )
            if top_y > bottom_y:
                c_idx.line(vert_x, top_y, vert_x, bottom_y)


    def _draw_page_indicators(self, data, total_pages):
        f     = FONTS["page_indicator"]
        inv_f = FONTS["invoice_no_p2"]
        for idx in range(len(self.canvases)):
            c = self.canvases[idx][1]
            if idx == 0:
                x, y = COORDS["page_indicator_p1"]
            else:
                x, y = COORDS["page_indicator_p2"]
            c.setFont("Calibri", f["size"])
            c.drawRightString(x, y, f"{idx + 1}  of  {total_pages}")
            if idx > 0:
                ix, iy = COORDS["page_invoice_no_p2"]
                c.setFont("Calibri-Bold", inv_f["size"])
                c.drawString(ix, iy,
                             f'Invoice No.{data["invoice_number"]}')