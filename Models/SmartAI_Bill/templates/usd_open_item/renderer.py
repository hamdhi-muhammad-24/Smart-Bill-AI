import os
from datetime import datetime

from reportlab.lib.colors import black

from core.pdf_renderer import BaseRenderer
from templates.usd_open_item.config import (
    PAGE_H,
    COORDS,
    ADDRESS_BOX,
    ADDRESS_FIELD_ORDER,
    CHARGES_TBL,
    USAGE_TABLE,
)

TEMPLATE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PDF = os.path.join(TEMPLATE_DIR, "layout.pdf")


# ---------------------------------------------------------------------------
# Generic EVENTHEADING_xx table helpers - ported from vat_home/renderer.py
# (confirmed pure, zero Flow-state coupling, per sub-agent C's reuse audit).
# Only change from the original: text-width measurement uses reportlab's
# canvas.stringWidth() instead of fitz.get_text_length(), since this renderer
# extends BaseRenderer (reportlab), not vat_home's fitz-based renderer.
# ---------------------------------------------------------------------------

def _row_amount(row):
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


def _merge_date_time(cells, is_header=False):
    """Date/Time-shaped first two columns merge into one visual column.
    Header text reads exactly "Date &Time" (space before &, none after);
    row values (actual dates/times) stay plain-space joined."""
    if len(cells) >= 2:
        if is_header:
            merged = f"{cells[0]} &{cells[1]}"
        else:
            merged = f"{cells[0]} {cells[1]}".strip()
        return [merged] + list(cells[2:])
    return list(cells)


def _table_font_size(num_cols):
    if num_cols <= 4:
        return 7
    if num_cols == 5:
        return 6.5
    if num_cols == 6:
        return 6
    return 5  # 7+ columns


def _table_col_positions(col, num_cols):
    """Proportional column x-offsets for a heterogeneous EVENTHEADING table.
    First column gets double weight (consistently the widest across every
    EVENT family - Date, or the merged Date&Time)."""
    x_start, amount_x = col["x_start"], col["amount_x"]
    if num_cols <= 1:
        return [x_start]
    n_left = num_cols - 1
    weights = [2.0] + [1.0] * (n_left - 1) if n_left > 1 else [1.0]
    total = sum(weights)
    usable = (amount_x - x_start) * 0.92
    positions = []
    acc = 0.0
    for w in weights:
        positions.append(x_start + usable * (acc / total))
        acc += w
    return positions


def _cells_with_fit(canvas, positions, amount_x, values, last_cell_text="",
                     size=7, bold=False, pad=3.0):
    """Build (x, text, align, max_width) cells: each left-aligned cell's max
    width is the gap to the next column's start, so long values shrink to
    fit instead of overflowing. Last left cell's boundary accounts for the
    right-aligned last_cell_text's own rendered width, not raw amount_x."""
    font = "Helvetica-Bold" if bold else "Helvetica"
    last_width = (canvas.stringWidth(str(last_cell_text), font, size)
                  if last_cell_text else 0.0)
    last_boundary = amount_x - last_width - pad
    cells = []
    n = len(positions)
    for i, val in enumerate(values[:n]):
        next_x = positions[i + 1] if i + 1 < n else last_boundary
        cells.append((positions[i], val, "left", max(next_x - positions[i] - pad, 1.0)))
    return cells


class USDOpenItemRenderer(BaseRenderer):
    """
    Renderer for USD Open Item Bills (BILLSTYLE=21) - co-branded international
    operator invoice (SLTMOBITEL + Xyntac). Single-page raster template, no
    baked mid-page text (confirmed: 0 real text words on layout.pdf) - no
    masking step needed, unlike vat_enterprise's original template.

    Single-column vertical-cursor layout throughout (no two-column flow -
    this bill type has a plain field-box stack, no running balance, per
    CLAUDE.md section 1.3), with page breaks via BaseRenderer.new_page().
    """

    def __init__(self):
        super().__init__(TEMPLATE_PDF)

    def render(self, data):
        self._draw_system_strings(data)
        self._draw_header(data)
        self._draw_barcode(data)
        self._draw_contact(data)
        self._draw_address(data)
        self._draw_rednotice(data)

        y = CHARGES_TBL["y_start"]
        y = self._draw_charges(data, y)
        y = self._draw_usage_sections(data, y)
        y = self._draw_discounts(data, y)
        y = self._draw_adjustments(data, y)
        y = self._draw_total_charge(data, y)
        y = self._draw_alt_currency(data, y)
        self._draw_marketing_messages(data, y)

        self._draw_bottom_barcode(data)
        self._draw_bottom_qr_code(data)
        self._draw_page_indicators()

    # --------------------------------------------------
    # System Strings ($File_name (original case) + generation timestamp +
    # customer segment). The timestamp is the live moment this PDF is
    # rendered (HH:MM:SS + microseconds) - not sourced from the GMF, since
    # no tag or file-metadata value in the source data accounts for it.
    # --------------------------------------------------
    def _draw_system_strings(self, data):
        top_x = 40
        top_y = PAGE_H - 100

        timestamp = datetime.now().strftime("_%H:%M:%S%f")
        file_info = data.get("file_info_string", "") + timestamp
        self.text(top_x, top_y, file_info, size=7.5)
        self.text(top_x, top_y - 8, data.get("customer_segment", ""), size=7.5, bold=True)

    # --------------------------------------------------
    # Header
    # --------------------------------------------------
    def _draw_header(self, data):
        self.text(*COORDS["account_number"], data.get("account_number", ""))
        self.text(*COORDS["invoice_number"], data.get("invoice_number", ""))
        self.text(*COORDS["billing_date"], data.get("billing_date", ""))
        self.text(*COORDS["bill_period"], data.get("bill_period", ""), size=9)

        self.text(*COORDS["invoice_amount"], data.get("invoice_amount", ""), bold=True)
        self.text(*COORDS["payment_due_date"], data.get("payment_due_date", ""), bold=True)

    # --------------------------------------------------
    # Barcode - encodes $BILLREF (invoice number), per section 2's explicit
    # spec ("Barcode encodes $BILLREF") - NOT the account number, which an
    # earlier version of this renderer defaulted to.
    # --------------------------------------------------
    def _draw_barcode(self, data):
        barcode_value = data.get("invoice_number", "")
        if not barcode_value:
            return
        self.draw_barcode(
            *COORDS["barcode"],
            barcode_value,
            width=COORDS.get("barcode_width", 100),
            height=COORDS.get("barcode_height", 20)
        )

    # --------------------------------------------------
    # Bottom Barcode / QR - reuse the same SLT-branded generators the other
    # bill types use (core.qr_generator/core.barcode_generator via
    # BaseRenderer.draw_slip_barcode/draw_qr), not a hand-rolled JSON payload
    # or ad-hoc string format - matches CLAUDE.md's "same general footer
    # mechanics as vat_enterprise/vat_home" instruction directly.
    # --------------------------------------------------
    def _draw_bottom_barcode(self, data):
        coords = COORDS.get("bottom_barcode", (300, 100))
        self.draw_slip_barcode(
            *coords,
            bill_ref=data.get("invoice_number", ""),
            total_charges=data.get("total_charges", 0.0),
            width=COORDS.get("bottom_barcode_width", 150),
            height=COORDS.get("bottom_barcode_height", 20),
        )

    def _draw_bottom_qr_code(self, data):
        coords = COORDS.get("bottom_qr", (502, 60))
        size = COORDS.get("bottom_qr_size", 50)
        self.draw_qr(
            *coords,
            account_number=data.get("account_number", ""),
            total_charges=data.get("total_charges", 0.0),
            size=size,
        )

    # --------------------------------------------------
    # Contact
    # --------------------------------------------------
    def _draw_contact(self, data):
        self.text(*COORDS["contact_line1"], data.get("contact_line1", ""), size=8)
        self.text(*COORDS["contact_line2"], data.get("contact_line2", ""), size=8)

    # --------------------------------------------------
    # Address - print each field only if non-empty (section 2's explicit
    # rule), in the plain numeric order CLAUDE.md's own spec text uses (NOT
    # the BPR13 5,2,3,4,1 reordering other bill types apply - the sample
    # address data in the xlsx is illustrative content, not a static
    # template, but the FIELD ORDER instruction is a real spec requirement).
    # --------------------------------------------------
    def _draw_address(self, data):
        address_lines = data.get("address_lines", {})
        y = ADDRESS_BOX["y"]

        # Print page count ("1 of 1" etc.) just above the address box,
        # right-aligned to the right edge of the address box, clear of the border.
        total_pages = self.page_count()
        page_label = f"1  of  {total_pages}"
        self.text(
            555,
            y + 20 ,
            page_label,
            size=ADDRESS_BOX["font_size"],
            bold=False,
            align="right",
        )

        for field in ADDRESS_FIELD_ORDER:
            value = (address_lines.get(field) or "").strip()
            if value:
                self.text(
                    ADDRESS_BOX["x"],
                    y,
                    value,
                    size=ADDRESS_BOX["font_size"],
                    bold=ADDRESS_BOX.get("bold", True)
                )
                y -= ADDRESS_BOX["line_h"]

    # --------------------------------------------------
    # Rednotice - sourced from the GMF FILENAME (LatestCreditControlActionId),
    # not a content tag. Only shown if that segment isn't "00".
    # --------------------------------------------------
    def _draw_rednotice(self, data):
        action_id = data.get("rednotice_action_id", "")
        if not action_id or action_id == "00":
            return
        from reportlab.lib.colors import red
        c = self.canvas
        c.setFillColor(red)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(
            CHARGES_TBL["indent_l1"], CHARGES_TBL["y_start"] + 20,
            "Your account has been flagged for credit control action - "
            "please contact us immediately to avoid service interruption."
        )
        c.setFillColor(black)

    # --------------------------------------------------
    # Page-break helper (shared by every vertical-cursor section below)
    # --------------------------------------------------
    def _ensure_space(self, y, needed):
        y_min = CHARGES_TBL["y_min"] if self.page_count() == 1 else CHARGES_TBL["otherpage_y_min"]
        if y - needed < y_min:
            self.new_page()
            return CHARGES_TBL["otherpage_y_start"]
        return y

    # --------------------------------------------------
    # Details of Charges for the Period
    # --------------------------------------------------
    def _draw_charges(self, data, y):
        tbl = CHARGES_TBL
        line_h = tbl["line_h"]
        font_size = tbl["font_size"]

        # Section header: description on the left, currency bracket right-aligned
        # above the amount column so "(US$)" appears directly over the numbers.
        currency = (data.get("acc_currency_code") or "").strip()
        currency_bracket = f"({currency})" if currency else ""
        y = self._ensure_space(y, line_h * 2)
        #self.text(tbl["indent_l1"], y,
                  #"Details of Charges for the Period",
                  #size=font_size, bold=True)
        if currency_bracket:
            self.text(tbl["amount_x"], y + 5, currency_bracket,
                      size=font_size, bold=True, align="right")
        y -= line_h

        for block in data.get("charge_blocks", []):
            if block["kind"] == "subscription_ref":
                y = self._ensure_space(y, line_h * 2)
                self.text(tbl["indent_l1"], y, f"Subscription Ref: {block['ref']}",
                          size=font_size, bold=True)
                y -= line_h
                for prod in block["product_labels"]:
                    y = self._ensure_space(y, line_h * 2)
                    self.text(tbl["indent_l2"], y, prod["label"],
                              size=font_size, bold=True)
                    y -= line_h
                    for charge in prod["charges"]:
                        y = self._ensure_space(y, line_h)
                        self.text(tbl["indent_l3"], y, charge["description"], size=font_size)
                        if charge["amount"]:
                            self.number(tbl["amount_x"], y, charge["amount"],
                                        size=font_size, align="right")
                        y -= line_h
            else:  # standalone product-label block, no subscription ref
                y = self._ensure_space(y, line_h * 2)
                self.text(tbl["indent_l2"], y, block["label"], size=font_size, bold=True)
                y -= line_h
                for charge in block["charges"]:
                    y = self._ensure_space(y, line_h)
                    self.text(tbl["indent_l3"], y, charge["description"], size=font_size)
                    if charge["amount"]:
                        self.number(tbl["amount_x"], y, charge["amount"],
                                    size=font_size, align="right")
                    y -= line_h

        # Unlabeled charges (no SLTPRODUCTLABEL scope at all) render as their
        # own final block, after every labeled block - explicit ordering
        # rule from section 2, implemented as its own pass rather than left
        # to incidental GMF order.
        unlabeled = data.get("unlabeled_charges", [])
        if unlabeled:
            y = self._ensure_space(y, line_h * 2)
            self.text(tbl["indent_l1"], y, "Other Charges", size=font_size, bold=True)
            y -= line_h
            for charge in unlabeled:
                y = self._ensure_space(y, line_h)
                self.text(tbl["indent_l3"], y, charge["description"], size=font_size)
                if charge["amount"]:
                    self.number(tbl["amount_x"], y, charge["amount"],
                                size=font_size, align="right")
                y -= line_h

        return y

    # --------------------------------------------------
    # Discounts - 6 tag-family pairs (core.bill_common.TopLevelDiscountCollector,
    # reused as-is). Only printed if at least one pair actually has data.
    # --------------------------------------------------
    def _draw_discounts(self, data, y):
        discounts = data.get("top_level_discounts", [])
        if not discounts:
            return y
        tbl = CHARGES_TBL
        y = self._ensure_space(y, tbl["line_h"] * 2)
        self.text(tbl["indent_l1"], y, "Discounts", size=tbl["font_size"], bold=True)
        y -= tbl["line_h"]
        for d in discounts:
            y = self._ensure_space(y, tbl["line_h"])
            self.text(tbl["indent_l3"], y, d["description"], size=tbl["font_size"])
            self.number(tbl["amount_x"], y, d["amount"], size=tbl["font_size"], align="right")
            y -= tbl["line_h"]
        return y

    # --------------------------------------------------
    # Adjustments ($ADJ)
    # --------------------------------------------------
    def _draw_adjustments(self, data, y):
        adjustments = data.get("adjustments", [])
        if not adjustments:
            return y
        tbl = CHARGES_TBL
        y = self._ensure_space(y, tbl["line_h"] * 2)
        self.text(tbl["indent_l1"], y, "Adjustments", size=tbl["font_size"], bold=True)
        y -= tbl["line_h"]
        for adj in adjustments:
            y = self._ensure_space(y, tbl["line_h"])
            self.text(tbl["indent_l3"], y, adj["description"], size=tbl["font_size"])
            self.number(tbl["amount_x"], y, adj["amount"], size=tbl["font_size"], align="right")
            y -= tbl["line_h"]
        return y

    # --------------------------------------------------
    # Total Charge
    # --------------------------------------------------
    def _draw_total_charge(self, data, y):
        tbl = CHARGES_TBL
        line_h = tbl["line_h"]
        font_size = tbl["font_size"]
        y = self._ensure_space(y, line_h * 2)

        line_left_x = tbl["indent_l1"]
        line_right_x = tbl["amount_x"]

        y -= line_h * 0.25
        c = self.canvas
        c.setLineWidth(1)
        c.line(line_left_x, y, line_right_x, y)
        y -= line_h

        self.text(line_left_x, y, "Total charges for the period", size=font_size, bold=True)
        self.number(line_right_x, y, data.get("total_charges", 0.0),
                    size=font_size, bold=True, align="right")
        y -= line_h * 0.5
        c.line(line_left_x, y, line_right_x, y)
        y -= line_h * 1.5
        return y

    # --------------------------------------------------
    # Alternate-currency block (conditional): only if BOTH
    # ACCCURRCODE <> 'Rs' AND ACCCURRCODE <> INFOCURRCODE.
    # --------------------------------------------------
    def _draw_alt_currency(self, data, y):
        acc_curr = (data.get("acc_curr_code") or "").strip()
        info_curr = (data.get("info_curr_code") or "").strip()
        if not acc_curr or not info_curr:
            return y
        if acc_curr == 'Rs' or acc_curr == info_curr:
            return y

        tbl = CHARGES_TBL
        line_h = tbl["line_h"]
        font_size = tbl["font_size"]
        y = self._ensure_space(y, line_h * 2)

        info_total = data.get("info_inv_total_rounded", 0.0)
        acc_rate = data.get("acc_rate", "")

        self.text(tbl["indent_l1"], y,
                  f"Total charges for the period in {info_curr} {info_total:,.2f}",
                  size=font_size, bold=True)
        y -= line_h
        y = self._ensure_space(y, line_h)
        self.text(tbl["indent_l1"], y,
                  f"at Parity rate of {info_curr} = {acc_curr} {acc_rate}",
                  size=font_size)
        y -= line_h
        return y

    # --------------------------------------------------
    # Marketing messages
    # --------------------------------------------------
    def _draw_marketing_messages(self, data, y):
        messages = data.get("marketing_messages", [])
        if not messages:
            return y
        tbl = CHARGES_TBL
        for m in messages:
            y = self._ensure_space(y, tbl["line_h"])
            self.text(tbl["indent_l1"], y, m, size=tbl["font_size"])
            y -= tbl["line_h"]
        return y

    # --------------------------------------------------
    # Itemization (usage tables) - generic EVENTHEADING_xx pattern, column
    # math ported directly from vat_home's pure helper functions (confirmed
    # reusable as-is per sub-agent C's audit), just measured with reportlab's
    # stringWidth instead of fitz.get_text_length, and drawn into this bill's
    # single-column layout instead of vat_home's two-column flow.
    # --------------------------------------------------
    def _draw_usage_sections(self, data, y):
        tbl = CHARGES_TBL
        line_h = tbl["line_h"]

        for section in data.get("usage_sections", []):
            for ref in section["refs"]:
                hdr = f'Usage Charge for {section["label"]}'
                if ref.get("phone"):
                    hdr += f' {ref["phone"]}'
                y = self._ensure_space(y, line_h * 2)
                self.text(tbl["indent_l1"], y, hdr, size=tbl["font_size"], bold=True)
                y -= line_h

                for sub in ref["subsections"]:
                    rows = sub.get("rows", [])
                    if not rows:
                        continue
                    if sub.get("label"):
                        y = self._ensure_space(y, line_h * 2)
                        self.text(tbl["indent_l2"], y, sub["label"],
                                  size=tbl["font_size"], bold=True)
                        y -= line_h

                    headers = _merge_date_time(sub.get("headers", []), is_header=True)
                    font_size = _table_font_size(len(headers))
                    y = self._ensure_space(y, line_h * 2)
                    col = {"x_start": USAGE_TABLE["x_start"], "amount_x": USAGE_TABLE["amount_x"]}
                    positions = _table_col_positions(col, len(headers))
                    cells = _cells_with_fit(self.canvas, positions, col["amount_x"],
                                             headers[:-1],
                                             last_cell_text=headers[-1] if headers else "",
                                             size=font_size, bold=True)
                    if headers:
                        cells.append((col["amount_x"], headers[-1], "right"))
                    self._draw_cells(cells, y, bold=True, size=font_size)
                    y -= line_h

                    for row in rows:
                        y = self._ensure_space(y, line_h)
                        merged_row = _merge_date_time(row)
                        positions = _table_col_positions(col, len(merged_row))
                        amt = _row_amount(row)
                        row_cells = _cells_with_fit(
                            self.canvas, positions, col["amount_x"], merged_row[:-1],
                            last_cell_text=f"{amt:,.3f}", size=font_size)
                        row_cells.append((col["amount_x"], f"{amt:,.3f}", "right"))
                        self._draw_cells(row_cells, y, size=font_size)
                        y -= line_h

                    y = self._ensure_space(y, line_h)
                    self.text(tbl["indent_l2"], y, f"Total for {sub.get('label') or section['label']}",
                              size=tbl["font_size"], bold=True)
                    self.number(tbl["amount_x"], y, sub.get("subtotal", 0),
                                decimals=3, size=tbl["font_size"], bold=True, align="right")
                    y -= line_h

                gt = ref.get("grand_total") or section.get("grand_total", 0)
                y = self._ensure_space(y, line_h)
                self.text(tbl["indent_l1"], y, f"Total Usage Charges for {section['label']}",
                          size=tbl["font_size"], bold=True)
                self.number(tbl["amount_x"], y, section.get("grand_total", 0),
                            decimals=3, size=tbl["font_size"], bold=True, align="right")
                y -= line_h

        return y

    def _draw_cells(self, cells, y, bold=False, size=8):
        """cells: (x, text, align) or (x, text, align, max_width). When
        max_width is given, the text shrinks to fit rather than overflowing
        into the next column (mirrors vat_home's text_fit mechanism)."""
        for cell in cells:
            x, text_val, align = cell[0], cell[1], cell[2]
            max_width = cell[3] if len(cell) > 3 else None
            if text_val in (None, ""):
                continue
            fitted_size = size
            if max_width is not None:
                font = "Helvetica-Bold" if bold else "Helvetica"
                while fitted_size > 3.2:
                    if self.canvas.stringWidth(str(text_val), font, fitted_size) <= max_width:
                        break
                    fitted_size -= 0.25
            self.text(x, y, str(text_val), size=fitted_size, bold=bold, align=align)

    # --------------------------------------------------
    # Page indicators - "Page N of M" top-right corner removed per spec.
    # The page count ("1 of N") is now printed above the address box in
    # _draw_address() instead.
    # --------------------------------------------------
    def _draw_page_indicators(self):
        pass  # intentionally blank - page number moved above address box
