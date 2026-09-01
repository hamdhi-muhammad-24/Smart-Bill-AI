"""Subscription Ref Grouping Renderer (Sheet 23)."""
import os
from datetime import datetime
from reportlab.lib.colors import black
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from core.pdf_renderer import BaseRenderer
from core.bill_common import is_vat_reg_printable, is_tax_section_printable
from templates.subscription_ref_grouping.config import COORDS, CHARGES_TABLE, FONTS

TEMPLATE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PDF = os.path.join(TEMPLATE_DIR, "layout.pdf")

# Calibri, scoped to this template only - shared font files (not duplicated
# per template) from templates/fonts/.
_FONTS_DIR = os.path.join(os.path.dirname(TEMPLATE_DIR), "fonts")
if "Calibri" not in pdfmetrics.getRegisteredFontNames():
    pdfmetrics.registerFont(TTFont("Calibri", os.path.join(_FONTS_DIR, "calibri.ttf")))
    pdfmetrics.registerFont(TTFont("Calibri-Bold", os.path.join(_FONTS_DIR, "calibrib.ttf")))


class SubscriptionRefGroupingRenderer(BaseRenderer):
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
        self._draw_vat_lines(data)
        self._draw_customer(data)
        self._draw_badge(data)
        self._draw_generation_id(data)
        self._draw_summary_boxes(data)
        self._draw_page1_footer(data)
        self._draw_currency_label(data)

        self._draw_hierarchy(data["subscription_refs"])
        self._draw_adjustments(data)
        self._draw_top_level_discounts(data)
        self._draw_taxes_and_total(data)
        self._draw_payments(data)
        self._draw_cancel_payments(data)
        self._draw_messages(data)

        self._draw_usage_full_from_page2(data)

        total_pages = self.page_count()
        self._draw_page_indicators(data, total_pages)


    def _draw_header(self, data):
        f = FONTS["header"]
        self.text(*COORDS["account_number"], data["account_number"],
                  size=f["size"])
        self.text(*COORDS["invoice_number"], data["invoice_number"],
                  size=f["size"])
        self.text(*COORDS["billing_date"],   data["billing_date"],
                  size=f["size"])
        period = (f"{data['billing_period_start']} - "
                  f"{data['billing_period_end']}")
        self.text(*COORDS["billing_period"], period, size=f["size"])

    def _draw_vat_lines(self, data):
        """BPR05/07."""
        if not data.get("show_vat_lines"):
            return
        if data.get("slt_vat_reg"):
            self.text(*COORDS["slt_vat_reg_label"],
                      f"SLT VAT Registration Number: {data['slt_vat_reg']}",
                      size=8)
        if data.get("customer_vat_reg"):
            self.text(*COORDS["customer_vat_reg_label"],
                      f"Customer VAT Registration Number: "
                      f"{data['customer_vat_reg']}",
                      size=8)

    def _draw_customer(self, data):
        f = FONTS["customer_name"]
        lines = []
        if data.get("address_name_not_required"):
            top = data.get("business_name") or data.get("customer_name", "")
            if top:
                lines.append(top)
        else:
            if data.get("customer_name"):
                lines.append(data["customer_name"])
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
            size=f["size"], bold=f["bold"],
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

        # Clean the source filename by removing the random suffix (e.g. __sqg099w7_1.gmf)
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
        slip_name = (
            data.get("business_name")
            if data.get("address_name_not_required")
            else (data.get("customer_name") or data.get("business_name", ""))
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
        self.text(CHARGES_TABLE["amount_x"], CHARGES_TABLE["page1_y_start"] + 6.0,
                  f"({code}.)", size=f["size"], bold=True, align="right")

    # 3-level hierarchy

    def _draw_hierarchy(self, subscription_refs):
        if not subscription_refs:
            return

        f_sub   = FONTS["subscription_ref"]
        f_prod  = FONTS["product_label"]
        f_chg   = FONTS["charge_line"]
        f_subtot = FONTS["subtotal"]

        y      = CHARGES_TABLE["page1_y_start"]
        y_min  = CHARGES_TABLE["page1_y_min"]
        line_h = CHARGES_TABLE["line_h"]
        lp_gap = CHARGES_TABLE["product_label_y_gap"]

        for sub_ref in subscription_refs:
            space = (lp_gap if sub_ref["ref"] else 0)
            for prod in sub_ref["products"]:
                space += line_h + len(prod["charges"]) * line_h
            if sub_ref.get("recurring_subtotal"):
                space += line_h
            if sub_ref.get("oneoff_subtotal"):
                space += line_h

            if y - space < y_min:
                self.new_page()
                y     = CHARGES_TABLE["otherpage_y_start"]
                y_min = CHARGES_TABLE["otherpage_y_min"]

            if sub_ref["ref"]:
                self.text(CHARGES_TABLE["subscription_ref_x"], y,
                          sub_ref["ref"],
                          size=f_sub["size"], bold=f_sub["bold"])
                y -= lp_gap

            for product in sub_ref["products"]:
                if y < y_min:
                    self.new_page()
                    y     = CHARGES_TABLE["otherpage_y_start"]
                    y_min = CHARGES_TABLE["otherpage_y_min"]
                self.text(CHARGES_TABLE["product_label_x"], y,
                          product["label"],
                          size=f_prod["size"], bold=f_prod["bold"])
                y -= line_h

                for charge in product["charges"]:
                    if y < y_min:
                        self.new_page()
                        y     = CHARGES_TABLE["otherpage_y_start"]
                        y_min = CHARGES_TABLE["otherpage_y_min"]
                    self.text(CHARGES_TABLE["desc_x"], y,
                              charge["description"], size=f_chg["size"])
                    if charge["amount"]:
                        self.number(CHARGES_TABLE["amount_x"], y,
                                    charge["amount"],
                                    size=f_chg["size"], align="right")
                    y -= line_h

            if sub_ref.get("recurring_subtotal"):
                label = (f'{sub_ref.get("detail_name","").strip()} '
                         f'Recurring Subtotal').strip()
                self.text(CHARGES_TABLE["desc_x"], y, label,
                          size=f_subtot["size"], bold=f_subtot["bold"])
                self.number(CHARGES_TABLE["amount_x"], y,
                            sub_ref["recurring_subtotal"],
                            size=f_subtot["size"], bold=f_subtot["bold"],
                            align="right")
                y -= line_h

            if sub_ref.get("oneoff_subtotal"):
                label = (f'{sub_ref.get("detail_name","").strip()} '
                         f'One-off Subtotal').strip()
                self.text(CHARGES_TABLE["desc_x"], y, label,
                          size=f_subtot["size"], bold=f_subtot["bold"])
                self.number(CHARGES_TABLE["amount_x"], y,
                            sub_ref["oneoff_subtotal"],
                            size=f_subtot["size"], bold=f_subtot["bold"],
                            align="right")
                y -= line_h

        self._flowing_y = y


    def _get_flowing_y(self):
        return getattr(self, '_flowing_y',
                       CHARGES_TABLE["page1_y_start"])

    def _flowing_write(self, text, amount=None, bold=False, x=None):
        y      = self._get_flowing_y()
        y_min  = CHARGES_TABLE["page1_y_min"]
        line_h = CHARGES_TABLE["line_h"]
        x_pos  = x if x is not None else CHARGES_TABLE["desc_x"]

        if y < y_min:
            self.new_page()
            y = CHARGES_TABLE["otherpage_y_start"]

        self.text(x_pos, y, text,
                  size=CHARGES_TABLE["font_size"], bold=bold)
        if amount is not None:
            self.number(CHARGES_TABLE["amount_x"], y, amount,
                        size=CHARGES_TABLE["font_size"], bold=bold,
                        align="right")
        self._flowing_y = y - line_h

    def _draw_adjustments(self, data):
        if not data.get("adjustments"):
            return
        self._flowing_write("Adjustments", bold=True,
                            x=CHARGES_TABLE["subscription_ref_x"])
        for adj in data["adjustments"]:
            self._flowing_write(adj["description"], amount=adj["amount"])

    def _draw_top_level_discounts(self, data):
        """BPR23."""
        discounts = data.get("top_level_discounts", [])
        if not discounts:
            return
        self._flowing_write("Discounts", bold=True,
                            x=CHARGES_TABLE["subscription_ref_x"])
        for d in discounts:
            self._flowing_write(d["description"], amount=d["amount"])

    def _draw_taxes_and_total(self, data):
        """BPR11/24: gate taxes. Always draw total. Draws right after
        subscription refs/adjustments/discounts finish, following the
        running flowing-y cursor instead of a fixed page position."""
        f = FONTS["taxes"]
        y = self._get_flowing_y()
        y_min = CHARGES_TABLE["taxes_total_y_min"] if self.page_count() == 1 else CHARGES_TABLE["otherpage_y_min"]

        has_nonzero = any(t['amount'] for t in data.get("taxes", []))
        if is_tax_section_printable(data.get("tax_status"), has_nonzero):
            if y - CHARGES_TABLE["line_h"] < y_min:
                self.new_page()
                y = CHARGES_TABLE["otherpage_y_start"]
                y_min = CHARGES_TABLE["otherpage_y_min"]

            self.text(COORDS["taxes_label"][0], y, "Taxes & Levies",
                      size=f["size"], bold=True)
            y -= COORDS["taxes_line_h"]
            for tax in data["taxes"]:
                if tax["amount"]:
                    if y < y_min:
                        self.new_page()
                        y = CHARGES_TABLE["otherpage_y_start"]
                        y_min = CHARGES_TABLE["otherpage_y_min"]
                    self.text(COORDS["taxes_label"][0], y,
                              tax["name"], size=f["size"])
                    self.number(COORDS["taxes_amount"][0], y,
                                tax["amount"], size=f["size"], align="right")
                    y -= COORDS["taxes_line_h"]

        if y - CHARGES_TABLE["line_h"] < y_min:
            self.new_page()
            y = CHARGES_TABLE["otherpage_y_start"]
        y -= 10

        f = FONTS["total"]
        c  = self.canvas
        x  = COORDS["total_charges_label"][0]
        ax = COORDS["total_charges_amount"][0]

        # Top and bottom horizontal lines framing the total charges row
        c.setLineWidth(0.5)
        c.setStrokeColor(black)
        c.line(x, y + 11, ax, y + 11)   # Top horizontal line
        c.line(x, y - 5, ax, y - 5)     # Bottom horizontal line

        self.text(x, y, "Total Charges for the Period",
                  size=f["size"], bold=True)
        self.number(ax, y, data["total_charges"],
                    size=f["size"], bold=True, align="right")

        self._flowing_y = y - COORDS["taxes_line_h"]

    def _draw_payments(self, data):
        """BPR26: suppress if zero. Draws right after Total Charges finishes,
        following the running flowing-y cursor instead of a fixed page
        position."""
        if not data.get("total_payments") and not data.get("payments"):
            return
        f      = FONTS["payments"]
        amt_x  = COORDS["payments_amount_x"]
        line_h = COORDS["payments_line_h"]
        x      = COORDS["payments_start"][0]

        y = self._get_flowing_y()
        y_min = CHARGES_TABLE["payments_y_min"] if self.page_count() == 1 else CHARGES_TABLE["otherpage_y_min"]
        rows_h = line_h * (len(data.get("payments", [])) + 2)  # header + rows + total line
        if y - rows_h < y_min:
            self.new_page()
            y = CHARGES_TABLE["otherpage_y_start"]
        y -= 3

        top_y = y + line_h * 0.5   # a touch above the header, matches the divider's top

        self.text(x, y, "Details of Payments Received",
                  size=f["size"], bold=True)
        y -= line_h
        for p in data["payments"]:
            line = (f"{p.get('pay_type', 'Payment')}-"
                    f"{p.get('date', '')}-"
                    f"{p.get('location', '')}").rstrip('-')
            self.text(x, y, line, size=f["size"])
            self.number(amt_x, y, p["amount"],
                        size=f["size"], align="right")
            y -= line_h
        self.text(x, y, "Total Payments Received",
                  size=f["size"], bold=True)
        self.number(amt_x, y, data["total_payments"],
                    size=f["size"], bold=True, align="right")

        # Vertical divider next to the payments block, sized to end exactly
        # at "Total Payments Received" - drawn last, once that y is known,
        # rather than at a fixed length.
        bottom_y = y - 3
        c = self.canvas
        c.setLineWidth(0.5)
        c.setStrokeColor(black)
        c.line(CHARGES_TABLE["vert_line_x"], top_y, CHARGES_TABLE["vert_line_x"], bottom_y)

        self._payments_end_y = y - line_h

    def _draw_cancel_payments(self, data):
        """BPR26."""
        cancelled = data.get("cancelled_payments", [])
        if not cancelled:
            return
        f      = FONTS["payments"]
        line_h = COORDS["payments_line_h"]
        x      = COORDS["payments_start"][0]
        amt_x  = COORDS["payments_amount_x"]
        y      = getattr(self, '_payments_end_y',
                         COORDS["payments_start"][1] - line_h * 2)

        self.text(x, y, "Cancel Payment", size=f["size"], bold=True)
        y -= line_h
        for p in cancelled:
            line = (f"{p.get('pay_type', '')}-{p.get('date', '')}"
                    f"-{p.get('location', '')}").rstrip('-')
            self.text(x, y, line, size=f["size"])
            self.number(amt_x, y, p["amount"],
                        size=f["size"], align="right")
            y -= line_h
        self._cancel_end_y = y

    def _draw_messages(self, data):
        """BPR28."""
        messages  = data.get("marketing_messages", [])
        suspended = data.get("suspended_message", "")
        if not messages and not suspended:
            return
        f      = FONTS["payments"]
        line_h = COORDS["payments_line_h"]
        x      = COORDS["payments_start"][0]
        y      = getattr(self, '_cancel_end_y',
                         getattr(self, '_payments_end_y',
                                 COORDS["payments_start"][1] - line_h * 2))

        if messages:
            self.text(x, y, "Message on Bill", size=f["size"], bold=True)
            y -= line_h
            for m in messages:
                self.text(x, y, m, size=f["size"])
                y -= line_h
        if suspended:
            self.text(x, y, suspended, size=f["size"], bold=True)

    # usage (page 2+)

    def _draw_usage_full_from_page2(self, data):
        """Identical logic to nonvat_enterprise / product_label_grouping."""
        sections = [s for s in data.get("usage_sections", [])
                    if s["subsections"]]
        if not sections:
            return

        self.new_page()
        y_state  = {"y": 750}
        y_min    = 60
        line_h   = 9
        col_x    = [50, 130, 190]
        amount_x = 300
        box_right      = 305
        total_label_x  = 45
        font_row         = 7
        font_header      = 7
        font_subtotal    = 7
        font_grand_total = 8
        font_section_hdr = 9

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

        def draw_table(sub, rows, print_header, show_section_hdr,
                       sec_label, sec_phone):
            if y_state["y"] < y_min:
                self.new_page()
                y_state["y"] = 780

            if show_section_hdr:
                hdr = f'Detailed Usage Charges for {sec_label}'
                if sec_phone:
                    hdr += f' {sec_phone}'
                self.text(45, y_state["y"], hdr,
                          size=font_section_hdr, bold=True)
                y_state["y"] -= line_h * 1.4

            if print_header and sub["label"]:
                self.text(45, y_state["y"], sub["label"],
                          size=font_row, bold=True)
                y_state["y"] -= line_h * 1.2

            headers = sub["headers"]
            combine = (len(headers) >= 2 and
                       headers[0] == 'Date' and headers[1] == 'Time')
            disp_h  = (['Date &Time'] + headers[2:]
                       if combine else headers)

            if print_header:
                try:
                    self.canvas.rect(
                        col_x[0] - 3, y_state["y"] - 2,
                        box_right - (col_x[0] - 3), line_h + 2,
                    )
                except AttributeError:
                    pass
                for i, h in enumerate(disp_h[:len(col_x) + 1]):
                    x = col_x[i] if i < len(col_x) else amount_x
                    self.text(x, y_state["y"], h, size=font_header,
                              bold=True,
                              align=("right"
                                     if i == len(disp_h) - 1
                                     else "left"))
                y_state["y"] -= line_h

            for row in rows:
                if y_state["y"] < y_min:
                    self.new_page()
                    y_state["y"] = 780
                disp       = ([f"{row[0]}  {row[1]}"] + row[2:]
                              if combine else list(row))
                charge_val = get_last_numeric(row)
                for i in range(min(len(disp) - 1, len(col_x))):
                    self.text(col_x[i], y_state["y"],
                              str(disp[i]), size=font_row)
                self.number(amount_x, y_state["y"], charge_val,
                            decimals=3, size=font_row, align="right")
                y_state["y"] -= line_h

            return sum_rows(rows)

        for section in sections:
            for sub_idx, sub in enumerate(section["subsections"]):
                sub_total = sum_rows(sub["rows"])
                draw_table(sub, sub["rows"],
                           print_header=True,
                           show_section_hdr=(sub_idx == 0),
                           sec_label=section["label"],
                           sec_phone=section["phone"])
                self.text(total_label_x, y_state["y"],
                          f'Total for {sub["label"]}',
                          size=font_subtotal, bold=True)
                self.number(amount_x, y_state["y"], sub_total,
                            decimals=3, size=font_subtotal,
                            bold=True, align="right")
                y_state["y"] -= line_h * 1.3

            gt = section.get("grand_total") or sum_rows(
                r for s in section["subsections"] for r in s["rows"])
            self.text(total_label_x, y_state["y"],
                      f'Total Usage Charges for {section["label"]}',
                      size=font_grand_total, bold=True)
            self.number(amount_x, y_state["y"], gt,
                        decimals=3, size=font_grand_total,
                        bold=True, align="right")
            y_state["y"] -= line_h * 2

    def _draw_page_indicators(self, data, total_pages):
        for idx in range(len(self.canvases)):
            c = self.canvases[idx][1]
            c.setFont("Calibri", 9)
            if idx == 0:
                c.drawRightString(540, 753,
                                  f"1  of  {total_pages}")
            else:
                c.setFont("Calibri-Bold", 10)
                c.drawString(45, 795,
                             f'Invoice No.{data["invoice_number"]}')
                c.setFont("Calibri", 9)
                c.drawRightString(540, 795,
                                  f"{idx + 1}  of  {total_pages}")