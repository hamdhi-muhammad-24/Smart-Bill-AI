"""Product Label Grouping Renderer (Sheet 22)."""
import os
from datetime import datetime
from reportlab.lib.colors import black

from core.pdf_renderer import BaseRenderer
from core.bill_common import is_vat_reg_printable, is_tax_section_printable
from templates.product_label_grouping.config import COORDS, CHARGES_TABLE, FONTS

TEMPLATE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PDF = os.path.join(TEMPLATE_DIR, "layout.pdf")


class ProductLabelGroupingRenderer(BaseRenderer):

    def __init__(self):
        super().__init__(TEMPLATE_PDF)

    def render(self, data):
        self._draw_header(data)
        self._draw_vat_lines(data)
        self._draw_customer(data)
        self._draw_badge(data)
        self._draw_generation_id(data)
        self._draw_summary_boxes(data)
        self._draw_page1_footer(data)
        self._draw_currency_label(data)

        y = self._draw_charges_with_subtotals(data["product_labels"])
        y = self._draw_adjustments(data, y)
        y = self._draw_top_level_discounts(data, y)
        y = self._draw_taxes_only(data, y)

        y = self._draw_total_charges_dynamic(data, y)
        y = self._draw_payments_dynamic(data, y)
        self._draw_cancel_payments_fixed(data)
        self._draw_messages_fixed(data)

        self._draw_usage_full_from_page2(data)

        total_pages = self.page_count()
        self._draw_page_indicators(data, total_pages)


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
        """BPR05/07: only when show_vat_lines is True."""
        if not data.get("show_vat_lines"):
            return
        f = FONTS["header"]
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
        self.text(*COORDS["badge_text"], data.get("badge", "HOME"),
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
            else (data.get("business_name") or data.get("customer_name", ""))
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

    def _draw_charges_with_subtotals(self, product_labels):
        """BPR12: per-product recurring + one-off subtotals."""
        y      = CHARGES_TABLE["page1_y_start"]
        y_min  = CHARGES_TABLE["page1_y_min"]
        line_h = CHARGES_TABLE["line_h"]
        lp_gap = CHARGES_TABLE["product_label_y_gap"]
        f  = FONTS["product_label"]
        fc = FONTS["charge_line"]
        fs = FONTS["subtotal"]

        for product in product_labels:
            sub_lines = (
                (1 if product.get("recurring_subtotal") else 0) +
                (1 if product.get("oneoff_subtotal") else 0)
            )
            space = lp_gap + len(product["charges"]) * line_h + \
                sub_lines * line_h
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

            if product.get("recurring_subtotal"):
                self.text(
                    CHARGES_TABLE["desc_x"] +
                    CHARGES_TABLE["subtotal_indent"], y,
                    "Product Recurring Subtotal",
                    size=fs["size"], bold=fs["bold"])
                self.number(CHARGES_TABLE["subtotal_x"], y,
                            product["recurring_subtotal"],
                            size=fs["size"], bold=fs["bold"],
                            align="right")
                y -= line_h

            if product.get("oneoff_subtotal"):
                self.text(
                    CHARGES_TABLE["desc_x"] +
                    CHARGES_TABLE["subtotal_indent"], y,
                    "Product One-off Subtotal",
                    size=fs["size"], bold=fs["bold"])
                self.number(CHARGES_TABLE["subtotal_x"], y,
                            product["oneoff_subtotal"],
                            size=fs["size"], bold=fs["bold"],
                            align="right")
                y -= line_h

        return y

    def _draw_adjustments(self, data, y):
        if not data.get("adjustments"):
            return y
        f      = FONTS["taxes"]
        line_h = CHARGES_TABLE["line_h"]
        self.text(CHARGES_TABLE["product_label_x"], y, "Adjustments",
                  size=f["size"], bold=True)
        y -= line_h
        for adj in data["adjustments"]:
            self.text(CHARGES_TABLE["desc_x"], y,
                      adj["description"], size=f["size"])
            self.number(CHARGES_TABLE["amount_x"], y,
                        adj["amount"], size=f["size"], align="right")
            y -= line_h
        return y

    def _draw_top_level_discounts(self, data, y):
        """BPR23."""
        discounts = data.get("top_level_discounts", [])
        if not discounts:
            return y
        f      = FONTS["taxes"]
        line_h = CHARGES_TABLE["line_h"]
        self.text(CHARGES_TABLE["product_label_x"], y, "Discounts",
                  size=f["size"], bold=True)
        y -= line_h
        for d in discounts:
            self.text(CHARGES_TABLE["desc_x"], y,
                      d["description"], size=f["size"])
            self.number(CHARGES_TABLE["amount_x"], y,
                        d["amount"], size=f["size"], align="right")
            y -= line_h
        return y

    def _draw_taxes_only(self, data, y):
        """BPR11/24."""
        has_nonzero = any(t['amount'] for t in data.get("taxes", []))
        if not is_tax_section_printable(data.get("tax_status"), has_nonzero):
            return y
        f      = FONTS["taxes"]
        line_h = CHARGES_TABLE["line_h"]
        self.text(CHARGES_TABLE["product_label_x"], y, "Taxes & Levies",
                  size=f["size"], bold=True)
        y -= line_h
        for t in data.get("taxes", []):
            if t["amount"]:
                self.text(CHARGES_TABLE["desc_x"], y,
                          t["name"], size=f["size"])
                self.number(CHARGES_TABLE["amount_x"], y,
                            t["amount"], size=f["size"], align="right")
                y -= line_h
        return y


    def _draw_total_charges_dynamic(self, data, y):
        """Draws right after Taxes & Levies finishes, following the running
        y cursor instead of a fixed page position."""
        line_h = CHARGES_TABLE["line_h"]
        y_min = CHARGES_TABLE["page1_y_min"] if self.page_count() == 1 else CHARGES_TABLE["otherpage_y_min"]
        if y - line_h < y_min:
            self.new_page()
            y = CHARGES_TABLE["otherpage_y_start"]
        y -= 10

        c  = self.canvases[-1][1]
        f  = FONTS["total"]
        x  = COORDS["total_charges_label_x"]
        ax = COORDS["total_charges_amount_x"]

        # Top and bottom horizontal lines framing the total charges row
        c.setLineWidth(0.5)
        c.setStrokeColor(black)
        c.line(x, y + 11, ax, y + 11)   # Top horizontal line
        c.line(x, y - 5, ax, y - 5)     # Bottom horizontal line

        c.setFont("Helvetica-Bold", f["size"])
        c.drawString(x, y, "Total Charges for the Period")
        c.drawRightString(ax, y, f"{data['total_charges']:,.2f}")
        return y - line_h

    def _draw_payments_dynamic(self, data, y):
        """BPR26: suppress if zero. Draws right after Total Charges finishes,
        following the running y cursor instead of a fixed page position."""
        if not data.get("total_payments") and not data.get("payments"):
            return y

        line_h = COORDS["payments_line_h"]
        y_min = CHARGES_TABLE["payments_y_min"] if self.page_count() == 1 else CHARGES_TABLE["otherpage_y_min"]
        rows_h = line_h * (len(data.get("payments", [])) + 2)  # header + rows + total line
        if y - rows_h < y_min:
            self.new_page()
            y = CHARGES_TABLE["otherpage_y_start"]
        y -= 5

        c  = self.canvases[-1][1]
        f  = FONTS["payments"]
        rx = COORDS["payments_row_x"]
        ax = COORDS["payments_amount_x"]

        top_y = y + line_h * 0.5   # a touch above the header, matches the divider's top

        c.setFont("Helvetica-Bold", f["size"])
        c.drawString(rx, y, "Details of Payments Received")
        y -= line_h
        c.setFont("Helvetica", f["size"])
        for p in data.get("payments", []):
            line = (f"{p.get('pay_type', 'Payment')}-"
                    f"{p.get('date', '')}-"
                    f"{p.get('location', '')}").rstrip('-')
            c.drawString(rx, y, line)
            c.drawRightString(ax, y, f"{p['amount']:,.2f}")
            y -= line_h
        c.setFont("Helvetica-Bold", f["size"])
        c.drawString(rx, y, COORDS["payments_total_label"])
        c.drawRightString(ax, y, f"{data['total_payments']:,.2f}")

        # Vertical divider next to the payments block, sized to end exactly
        # at "Total Payments Received" - drawn last, once that y is known,
        # rather than at a fixed length.
        bottom_y = y - 3
        c.setLineWidth(0.5)
        c.setStrokeColor(black)
        c.line(CHARGES_TABLE["vert_line_x"], top_y, CHARGES_TABLE["vert_line_x"], bottom_y)

        return y - line_h

    def _draw_cancel_payments_fixed(self, data):
        """BPR26: cancelled payments."""
        cancelled = data.get("cancelled_payments", [])
        if not cancelled:
            return
        c      = self.canvases[0][1]
        f      = FONTS["payments"]
        rx     = COORDS["payments_row_x"]
        ax     = COORDS["payments_amount_x"]
        line_h = COORDS["payments_line_h"]
        y      = COORDS["payments_row_start_y"] - (
            (len(data.get("payments", [])) + 2) * line_h)

        c.setFont("Helvetica-Bold", f["size"])
        c.drawString(rx, y, "Cancel Payment")
        y -= line_h
        c.setFont("Helvetica", f["size"])
        for p in cancelled:
            line = (f"{p.get('pay_type', '')}-{p.get('date', '')}"
                    f"-{p.get('location', '')}").rstrip('-')
            c.drawString(rx, y, line)
            c.drawRightString(ax, y, f"{p['amount']:,.2f}")
            y -= line_h

    def _draw_messages_fixed(self, data):
        """BPR28."""
        messages  = data.get("marketing_messages", [])
        suspended = data.get("suspended_message", "")
        if not messages and not suspended:
            return
        c      = self.canvases[0][1]
        f      = FONTS["payments"]
        rx     = COORDS["payments_row_x"]
        line_h = COORDS["payments_line_h"]
        y      = COORDS["payments_row_start_y"] - (
            (len(data.get("payments", [])) +
             len(data.get("cancelled_payments", [])) + 3) * line_h)

        if messages:
            c.setFont("Helvetica-Bold", f["size"])
            c.drawString(rx, y, "Message on Bill")
            y -= line_h
            c.setFont("Helvetica", f["size"])
            for m in messages:
                c.drawString(rx, y, m)
                y -= line_h
        if suspended:
            c.setFont("Helvetica-Bold", f["size"])
            c.drawString(rx, y, suspended)

    # usage (page 2+)

    def _draw_usage_full_from_page2(self, data):
        """Same logic as nonvat_enterprise — full usage from new page."""
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
        f     = FONTS["page_indicator"]
        inv_f = FONTS["invoice_no_p2"]
        for idx in range(len(self.canvases)):
            c = self.canvases[idx][1]
            if idx == 0:
                x, y = COORDS["page_indicator_p1"]
            else:
                x, y = COORDS["page_indicator_p2"]
            c.setFont("Helvetica", f["size"])
            c.drawRightString(x, y, f"{idx + 1}  of  {total_pages}")
            if idx > 0:
                ix, iy = COORDS["page_invoice_no_p2"]
                c.setFont("Helvetica-Bold", inv_f["size"])
                c.drawString(ix, iy,
                             f'Invoice No.{data["invoice_number"]}')