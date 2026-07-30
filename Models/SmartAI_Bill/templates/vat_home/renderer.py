"""VAT Home Renderer.

Overlay engine using PyMuPDF (fitz) - see CLAUDE.md section 3. Unlike
vat_enterprise (reportlab + pypdf merge), this template is a single-page raster
with no baked mid-page TEXT, so no mask-and-redraw of individual labels is
needed on page 1 (section 1.1) - that part of CLAUDE.md's claim holds.

Continuation pages (section 9.1, confirmed against golden VAT_HOME.pdf page 197)
do NOT reuse layout.pdf's background at all - they are a plain blank page with
just "Invoice No.<x>" (top-left) and "<n> of <m>" (top-right) stamped, and
content starting around y=70. An earlier version of this renderer repainted the
full front-page template on every continuation page and masked over it; that
was wrong (confirmed by extracting golden page 197's actual content, which has
no template chrome at all) and has been replaced by this simpler blank-page
approach.

The core of this build is the continuous two-column reflow (section 4): content
from "Total Charges for the Period" down through every usage table flows as ONE
stream - left column, then right column, then next page's left column - with no
per-table "repeat header on break" rule. Charge groups, adjustments/discounts,
and Taxes & Levies (everything BEFORE Total Charges) are single full-width
content instead (section 9.2) - matching vat_enterprise's pattern for this same
section - and carry no vertical divider. Every line goes through the same
draw_line()/ensure_space() pair regardless of which mode is active, so no
section can use a fixed y instead of the running cursor (the mistake that
caused vat_enterprise's original overlap bug).
"""
import os
from datetime import datetime

import fitz

from core.bill_common import is_tax_section_printable
from core.qr_generator import generate_slt_qr, generate_static_payonline_qr
from core.barcode_generator import generate_barcode, generate_slip_barcode
from core.gmf_reader import is_red_notice

from templates.vat_home.config import (
    COORDS, FONTS, FLOW_COLUMNS, FULL_WIDTH, PAGE1_CONTENT_TOP,
    CONTENT_FLOOR, CONT_PAGE_INVOICE_NO, CONT_PAGE_PAGE_INDICATOR_X,
    CONT_PAGE_PAGE_INDICATOR_Y, CONT_PAGE_CONTENT_TOP, CONT_PAGE_CONTENT_FLOOR,
    BADGE_BOX, SUMMARY_VALUE_BOX, SUMMARY_BUBBLE_SAFE_WIDTH,
    SUMMARY_BUBBLE_MIN_SIZE, CAP_HEIGHT_RATIO, LINE_HEIGHT, PAGE_W, PAGE_H,
)

TEMPLATE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PDF = os.path.join(TEMPLATE_DIR, "layout.pdf")


class VATHomeRenderer:

    def __init__(self):
        self.template_doc = fitz.open(TEMPLATE_PDF)
        self.doc = fitz.open()
        self.page = None
        self._invoice_number = ""
        self.content_floor = CONTENT_FLOOR
        self._new_page()


    # ---- page / low-level draw helpers -----------------------------------

    def _new_page(self):
        is_continuation = self.doc.page_count > 0
        page = self.doc.new_page(width=PAGE_W, height=PAGE_H)
        if is_continuation:
            # Blank page - no template background at all (section 9.1).
            page.insert_text(CONT_PAGE_INVOICE_NO,
                              f"Invoice No.{self._invoice_number}",
                              fontname="hebo", fontsize=11)
        else:
            page.show_pdf_page(page.rect, self.template_doc, 0)
        self.page = page
        return page

    def page_count(self):
        return self.doc.page_count

    def text(self, x, y, value, size=9, bold=False, align="left"):
        if value is None or value == "":
            return
        font = "hebo" if bold else "helv"
        s = str(value)
        draw_x = x
        if align in ("right", "center"):
            width = fitz.get_text_length(s, fontname=font, fontsize=size)
            draw_x = x - width if align == "right" else x - width / 2
        self.page.insert_text((draw_x, y), s, fontname=font, fontsize=size)

    def number(self, x, y, value, decimals=2, align="right", size=9, bold=False):
        self.text(x, y, f"{value:,.{decimals}f}", size=size, bold=bold, align=align)

    def text_fit(self, x, y, value, max_width, size=9, bold=False, align="left",
                 min_size=3.2):
        """Like text(), but shrinks the font (down to min_size) until the
        string fits max_width - for table cells with heterogeneous, unknown-
        length content (e.g. 13-digit dialled numbers) where a fixed size
        would overflow into the next column."""
        if value is None or value == "":
            return
        font = "hebo" if bold else "helv"
        s = str(value)
        fitted_size = size
        while fitted_size > min_size:
            if fitz.get_text_length(s, fontname=font, fontsize=fitted_size) <= max_width:
                break
            fitted_size -= 0.25
        self.text(x, y, s, size=fitted_size, bold=bold, align=align)

    def number_fit(self, x, y, value, max_width, decimals=2, align="center",
                    size=9, bold=False, min_size=3.2):
        """number() + text_fit() combined - shrinks large formatted numbers
        (e.g. multi-million-rupee accounts) to fit max_width instead of
        overflowing their box, the same general mechanism text_fit already
        uses for table cells."""
        self.text_fit(x, y, f"{value:,.{decimals}f}", max_width, size=size,
                      bold=bold, align=align, min_size=min_size)

    @staticmethod
    def center_y_in_box(box, font_size, cap_height_ratio):
        """Baseline y that visually centers all-caps text or digits (neither
        has descenders) within box's vertical span - computed from the box's
        own rect every time, never a separately-stored y that can drift out
        of sync with it."""
        box_center = (box["y0"] + box["y1"]) / 2
        return box_center + (font_size * cap_height_ratio) / 2

    def multiline_block(self, x, y, lines, line_height=11, size=9, bold=False):
        cy = y
        for line in lines:
            if line:
                self.text(x, cy, line, size=size, bold=bold)
            cy += line_height  # top-origin: downward = increasing y

    def draw_qr(self, x, y, account_number, total_charges, size=48):
        buf, _ = generate_slt_qr(account_number=account_number,
                                  total_charges=total_charges or 0, size=200)
        self.page.insert_image(fitz.Rect(x, y, x + size, y + size), stream=buf.read())

    def draw_static_payonline_qr(self, x, y, size=48):
        buf = generate_static_payonline_qr(size=200)
        self.page.insert_image(fitz.Rect(x, y, x + size, y + size), stream=buf.read())

    def draw_barcode(self, x, y, value, width=80, height=14):
        buf = generate_barcode(value)
        self.page.insert_image(fitz.Rect(x, y, x + width, y + height), stream=buf.read())

    def draw_slip_barcode(self, x, y, bill_ref, total_charges, width=138, height=25):
        buf = generate_slip_barcode(bill_ref, total_charges)
        self.page.insert_image(fitz.Rect(x, y, x + width, y + height), stream=buf.read())

    def save(self, output_path):
        self.doc.save(output_path)

    # ---- top-level render --------------------------------------------------

    def render(self, data):
        filename = str(data.get("source_filename") or data.get("filename") or "")
        if is_red_notice(filename):
            self.content_floor = 622.0
            templates_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

            red_pdf = os.path.join(templates_dir, "Template_RED.pdf")
            if os.path.exists(red_pdf):
                self.template_doc = fitz.open(red_pdf)
                if self.doc.page_count > 0:
                    self.doc[0].show_pdf_page(self.doc[0].rect, self.template_doc, 0)
        else:
            self.content_floor = CONTENT_FLOOR


        self._invoice_number = data.get("invoice_number", "")
        self._draw_header(data)

        self._draw_vat_lines(data)
        self._draw_customer(data)
        self._draw_badge(data)
        self._draw_generation_id(data)
        self._draw_summary_boxes(data)
        self._draw_page1_footer(data)
        self._draw_currency_label(data)

        flow = _Flow(self)
        _draw_charges_flow(flow, data)
        _draw_adjustments_flow(flow, data)
        _draw_discounts_flow(flow, data)
        _draw_taxes_flow(flow, data)
        _draw_total_charges_flow(flow, data)
        _draw_payments_flow(flow, data)
        _draw_cancel_payments_flow(flow, data)
        _draw_usage_flow(flow, data)
        _draw_messages_flow(flow, data)
        flow.finish()

        self._draw_page_indicators(self.page_count())

    # ---- fixed-position fields (page 1 only) -------------------------------

    def _draw_header(self, data):
        f = FONTS["header"]
        self.text(*COORDS["telephone_number"], data["telephone_number"], size=f["size"])
        self.text(*COORDS["account_number"], data["account_number"], size=f["size"])
        self.text(*COORDS["invoice_number"], data["invoice_number"], size=f["size"])
        self.text(*COORDS["billing_date"], data["billing_date"], size=f["size"])
        period = f"{data['billing_period_start']} - {data['billing_period_end']}"
        self.text(*COORDS["billing_period"], period, size=f["size"])

    def _draw_vat_lines(self, data):
        if not data.get("show_vat_lines"):
            return
        f = FONTS["header"]
        if data.get("slt_vat_reg"):
            self.text(*COORDS["slt_vat_reg"],
                      f"SLT VAT Registration Number: {data['slt_vat_reg']}",
                      size=f["size"])
        if data.get("customer_vat_reg"):
            self.text(*COORDS["customer_vat_reg"],
                      f"Customer VAT Registration Number: {data['customer_vat_reg']}",
                      size=f["size"])

    def _draw_customer(self, data):
        addr_lines = []
        if data.get("position"):
            addr_lines.append(data["position"])
        if data.get("business_name"):
            addr_lines.append(data["business_name"])
        if data.get("department"):
            addr_lines.append(data["department"])
        addr_lines.extend(data.get("address_lines", []))
        if data.get("zip_code"):
            addr_lines.append(data["zip_code"])

        fa = FONTS["customer_addr"]
        self.multiline_block(
            COORDS["customer_addr_x"], COORDS["customer_addr_start"],
            addr_lines, line_height=COORDS["customer_addr_line_h"],
            size=fa["size"], bold=fa["bold"]
        )

    def _draw_badge(self, data):
        f = FONTS["badge"]
        y = self.center_y_in_box(BADGE_BOX, f["size"], CAP_HEIGHT_RATIO)
        self.text(COORDS["badge_text_x"], y, data.get("badge", "HOME"),
                  size=f["size"], bold=f["bold"])

    def _draw_generation_id(self, data):
        f = FONTS["gen_id"]
        due = data.get("payment_due_date", "")
        try:
            dd, mm, yyyy = due.split("/")
            due_mmddyy = f"{mm}{dd}{yyyy[-2:]}"
        except ValueError:
            due_mmddyy = ""
        ts = datetime.now().strftime("%H:%M:%S")
        line = f'{data["source_filename"]}_{ts}_{due_mmddyy}'
        self.text(*COORDS["gen_id_line"], line, size=f["size"])
        if data.get("customer_segment"):
            self.text(*COORDS["gen_id_line2"], data["customer_segment"], size=f["size"])

    def _draw_summary_boxes(self, data):
        # y is computed from SUMMARY_VALUE_BOX's own rect (fix pass 6), never
        # a separately-stored y that can drift out of sync with the bubbles.
        # Large values (e.g. multi-million-rupee corporate accounts) shrink
        # to fit SUMMARY_BUBBLE_SAFE_WIDTH instead of overflowing the bubble -
        # a general safeguard, not tuned to any one bill's numbers.
        f = FONTS["summary_box"]
        y = self.center_y_in_box(SUMMARY_VALUE_BOX, f["size"], CAP_HEIGHT_RATIO)
        self.number_fit(COORDS["balance_bf"], y, data["balance_bf"],
                         SUMMARY_BUBBLE_SAFE_WIDTH, size=f["size"],
                         min_size=SUMMARY_BUBBLE_MIN_SIZE)
        self.number_fit(COORDS["payments_received"], y, data["payments_received"],
                         SUMMARY_BUBBLE_SAFE_WIDTH, size=f["size"],
                         min_size=SUMMARY_BUBBLE_MIN_SIZE)
        self.number_fit(COORDS["charges_period"], y, data["charges_period"],
                         SUMMARY_BUBBLE_SAFE_WIDTH, size=f["size"],
                         min_size=SUMMARY_BUBBLE_MIN_SIZE)

        f_total = FONTS["summary_total"]
        y_total = self.center_y_in_box(SUMMARY_VALUE_BOX, f_total["size"], CAP_HEIGHT_RATIO)
        self.number_fit(COORDS["total_payable"], y_total, data["total_payable"],
                         SUMMARY_BUBBLE_SAFE_WIDTH, size=f_total["size"], bold=True,
                         min_size=SUMMARY_BUBBLE_MIN_SIZE)
        self.text_fit(COORDS["payment_due_date"], y_total, data["payment_due_date"],
                      SUMMARY_BUBBLE_SAFE_WIDTH, size=f_total["size"], bold=True,
                      align="center", min_size=SUMMARY_BUBBLE_MIN_SIZE)

    def _draw_page1_footer(self, data):
        self.draw_static_payonline_qr(*COORDS["payonline_qr"], size=COORDS["payonline_qr_size"])
        self.draw_qr(*COORDS["qr_code"], account_number=data["account_number"],
                     total_charges=data["total_charges"], size=COORDS["qr_size"])
        self.draw_barcode(*COORDS["barcode"], data["account_number"],
                           width=COORDS["barcode_width"], height=COORDS["barcode_height"])
        self.draw_slip_barcode(*COORDS["slip_barcode"], bill_ref=data["invoice_number"],
                                total_charges=data["total_charges"],
                                width=COORDS["slip_barcode_width"],
                                height=COORDS["slip_barcode_height"])
        f = FONTS["slip"]
        self.text(*COORDS["slip_telephone"], data["telephone_number"], size=f["size"])
        self.text(*COORDS["slip_invoice"], data["invoice_number"], size=f["size"])
        slip_name = (
            data.get("business_name")
            if data.get("address_name_not_required")
            else (data.get("business_name") or data.get("customer_name", ""))
        )
        self.text(*COORDS["slip_customer"], slip_name or "", size=f["size"])
        self.text(*COORDS["slip_account"], data["account_number"], size=f["size"])

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
        self.text(FULL_WIDTH["amount_x"], 362.0, f"({code}.)",
                  size=f["size"], bold=True, align="right")

    def _draw_page_indicators(self, total_pages):
        f = FONTS["page_indicator"]
        for idx in range(self.doc.page_count):
            page = self.doc[idx]
            text = f"{idx + 1}  of  {total_pages}"
            if idx == 0:
                x, y = COORDS["page_indicator"]
                page.insert_text((x, y), text, fontname="helv", fontsize=f["size"])
            else:
                # Continuation pages: right-aligned to the page margin, per
                # golden evidence (section 9.1) - a different, minimal layout
                # decoupled from page 1's badge/logo-relative position.
                width = fitz.get_text_length(text, fontname="helv", fontsize=f["size"])
                x = CONT_PAGE_PAGE_INDICATOR_X - width
                page.insert_text((x, CONT_PAGE_PAGE_INDICATOR_Y), text,
                                  fontname="helv", fontsize=f["size"])


# ---------------------------------------------------------------------------
# Two-column continuous reflow engine (section 4)
# ---------------------------------------------------------------------------

class _Flow:
    """Drives one shared page cursor through the entire post-DETAILS content
    stream. Every draw goes through draw_line(); no caller may use a fixed y.
    Top-origin: y increases downward, so the floor is a MAXIMUM.

    Two modes (section 9.2):
    - "full": charge groups, adjustments/discounts, Taxes & Levies, and Total
      Charges itself - single full-width content, no column split, no divider.
    - "columns": everything from Total Charges onward - the narrow two-column
      reflow with a vertical divider. Entered via begin_columns(), called once
      Total Charges' bottom rule has been drawn.
    """

    def __init__(self, renderer):
        self.r = renderer
        self.mode = "full"
        self.column = "left"
        self.y = PAGE1_CONTENT_TOP
        self.col_top = PAGE1_CONTENT_TOP
        self.col_floor = renderer.content_floor
        self._page_top_y = {}

        self._page_max_y = {}
        self.page_dividers = []  # (page_idx, start_y, end_y)

    def col_def(self):
        return FULL_WIDTH if self.mode == "full" else FLOW_COLUMNS[self.column]

    def begin_columns(self):
        """Switch from full-width mode into the two-column reflow. Called once
        Total Charges' bottom rule has been drawn - the divider for the
        current page starts exactly here, never at PAGE1_CONTENT_TOP."""
        self.mode = "columns"
        self.column = "left"
        self.col_top = self.y
        idx = self.r.page_count() - 1
        self._page_top_y[idx] = self.y

    def _record(self, y):
        idx = self.r.page_count() - 1
        self._page_max_y[idx] = max(self._page_max_y.get(idx, y), y)

    def ensure_space(self, height):
        """height = vertical space needed before the NEXT draw. Orphan control
        (section 1.3) is implemented by callers passing height covering more
        than one line (e.g. a table header reserves header+first-row height)."""
        if self.y + height <= self.col_floor:
            return
        self._advance()

    def _advance(self):
        if self.mode == "columns" and self.column == "left":
            self.column = "right"
            self.y = self.col_top
            return
        if self.mode == "columns":
            self._finalize_current_page_divider()
        self.r._new_page()
        idx = self.r.page_count() - 1
        self.column = "left"
        self.y = CONT_PAGE_CONTENT_TOP
        self.col_top = self.y
        self.col_floor = CONT_PAGE_CONTENT_FLOOR
        if self.mode == "columns":
            self._page_top_y[idx] = self.y

    def _finalize_current_page_divider(self):
        idx = self.r.page_count() - 1
        if idx not in self._page_top_y:
            return
        start = self._page_top_y[idx]
        end = self._page_max_y.get(idx, start)
        self.page_dividers.append((idx, start, end))

    def draw_line(self, cells, bold=False, size=8):
        """cells: list of (x, text, align) or (x, text, align, max_width).
        When max_width is given, the cell shrinks to fit rather than
        overflowing into the next column (see Renderer.text_fit). Advances y
        by LINE_HEIGHT."""
        for cell in cells:
            x, text_val, align = cell[0], cell[1], cell[2]
            max_width = cell[3] if len(cell) > 3 else None
            if text_val in (None, ""):
                continue
            if max_width is not None:
                self.r.text_fit(x, self.y, str(text_val), max_width,
                                 size=size, bold=bold, align=align)
            else:
                self.r.text(x, self.y, str(text_val), size=size, bold=bold, align=align)
        self._record(self.y)
        self.y += LINE_HEIGHT

    def draw_header_box(self, col, y):
        """Frame a just-drawn table header row with an unfilled rect - the
        same box/margin vat_enterprise's draw_cdr_header() uses (there:
        cd["x_start"]-3 to cd["x_end"], 2pt below baseline / 9pt above),
        translated from reportlab's bottom-origin canvas to fitz's top-origin
        page. Callers draw this once, right after the single header draw_line
        call for a table - never on continuation, since rows after it just
        keep calling plain draw_line()."""
        rect = fitz.Rect(col["x_start"] - 3, y - 9, col["x_end"], y + 2)
        self.r.page.draw_rect(rect, color=(0, 0, 0), width=0.5)

    def finish(self):
        self._finalize_current_page_divider()
        for idx, start, end in self.page_dividers:
            page = self.r.doc[idx]
            x = FLOW_COLUMNS["vert_line_x"]
            if end > start:
                page.draw_line((x, start), (x, end + 3), width=0.5, color=(0, 0, 0))


def _table_col_positions(col, num_cols):
    """Proportional column x-offsets for a heterogeneous EVENTHEADING table -
    same idea as vat_enterprise's POST_TC_COLUMNS relative offsets, generalized
    to any number of columns (section 1.2). The first column gets double
    weight: across every EVENT family it's Date (or the merged Date&Time), the
    consistently-widest cell, so an even split leaves it overlapping column 2."""
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


# ---- content-sequence drawers (section 4's exact order) -------------------

def _draw_charges_flow(flow, data):
    for product in data.get("product_labels", []):
        flow.ensure_space(LINE_HEIGHT * 2)  # orphan control: header + 1 line
        col = flow.col_def()
        flow.draw_line([(col["x_start"], product["label"], "left")], bold=True, size=9)
        for charge in product["charges"]:
            flow.ensure_space(LINE_HEIGHT)
            col = flow.col_def()
            amt = f"{charge['amount']:,.2f}" if charge["amount"] else ""
            flow.draw_line([
                (col["x_start"] + 8, charge["description"], "left"),
                (col["amount_x"], amt, "right"),
            ], size=8)


def _draw_adjustments_flow(flow, data):
    adjustments = data.get("adjustments", [])
    if not adjustments:
        return
    flow.ensure_space(LINE_HEIGHT * 2)
    col = flow.col_def()
    flow.draw_line([(col["x_start"], "Adjustments", "left")], bold=True, size=9)
    for adj in adjustments:
        flow.ensure_space(LINE_HEIGHT)
        col = flow.col_def()
        flow.draw_line([
            (col["x_start"] + 8, adj["description"], "left"),
            (col["amount_x"], f"{adj['amount']:,.2f}", "right"),
        ], size=8)


def _draw_discounts_flow(flow, data):
    discounts = data.get("top_level_discounts", [])
    if not discounts:
        return
    flow.ensure_space(LINE_HEIGHT * 2)
    col = flow.col_def()
    flow.draw_line([(col["x_start"], "Discounts", "left")], bold=True, size=9)
    for d in discounts:
        flow.ensure_space(LINE_HEIGHT)
        col = flow.col_def()
        flow.draw_line([
            (col["x_start"] + 8, d["description"], "left"),
            (col["amount_x"], f"{d['amount']:,.2f}", "right"),
        ], size=8)


def _draw_taxes_flow(flow, data):
    has_nonzero = any(t['amount'] for t in data.get("taxes", []))
    if not is_tax_section_printable(data.get("tax_status"), has_nonzero):
        return
    flow.ensure_space(LINE_HEIGHT * 2)
    col = flow.col_def()
    flow.draw_line([(col["x_start"], "Taxes & Levies", "left")], bold=True, size=9)
    for t in data.get("taxes", []):
        if not t["amount"]:
            continue
        flow.ensure_space(LINE_HEIGHT)
        col = flow.col_def()
        flow.draw_line([
            (col["x_start"] + 8, t["name"], "left"),
            (col["amount_x"], f"{t['amount']:,.2f}", "right"),
        ], size=8)


def _draw_total_charges_flow(flow, data):
    # Still full-width mode here (section 9.2) - Total Charges itself is the
    # last full-width line; the divider/column mode begins right after it.
    #
    # Fix pass 3: the previous version anchored the top rule 11pt above the
    # Total Charges baseline, which is correct in isolation (clears Total
    # Charges' own ~9.6pt ascent) but the tax lines immediately above use
    # plain LINE_HEIGHT (10pt) spacing - so a rule 11pt above the Total
    # Charges baseline lands only 1pt above the PREVIOUS line's (e.g.
    # VAT-18%) baseline, well inside that line's own bbox. Confirmed by
    # extracting both lines' exact bboxes: VAT-18% (491.4-502.4) and Total
    # Charges (500.4-512.8) were only 10pt apart baseline-to-baseline with no
    # slack for a rule to sit strictly between them. Fixed by inserting an
    # explicit gap between the tax section and this line, so there is real
    # room for the rule on both sides - not by changing what the rule's
    # position is computed from (it was already anchored to the Total
    # Charges baseline, per fix pass 2; the bug was insufficient clearance
    # from the line above, not the wrong anchor).
    GAP_ABOVE_SECTION = 10
    TOP_GAP = 12   # clears Total Charges' own ~9.6pt ascent with margin
    BOTTOM_GAP = 5  # already verified clean in fix pass 2 - unchanged

    flow.ensure_space(LINE_HEIGHT * 2 + GAP_ABOVE_SECTION)
    flow.y += GAP_ABOVE_SECTION
    col = flow.col_def()
    page = flow.r.page
    text_y = flow.y
    page.draw_line((col["x_start"], text_y - TOP_GAP), (col["amount_x"], text_y - TOP_GAP),
                    width=0.5, color=(0, 0, 0))
    flow.draw_line([
        (col["x_start"], "Total Charges for the Period", "left"),
        (col["amount_x"], f"{data['total_charges']:,.2f}", "right"),
    ], bold=True, size=9)
    page.draw_line((col["x_start"], text_y + BOTTOM_GAP), (col["amount_x"], text_y + BOTTOM_GAP),
                    width=0.5, color=(0, 0, 0))
    flow.y = text_y + LINE_HEIGHT + BOTTOM_GAP

    # Everything from here on is the two-column reflow, per section 9.2.
    flow.begin_columns()


def _draw_payments_flow(flow, data):
    payments = data.get("payments", [])
    if not (data.get("total_payments") or payments):
        return
    flow.ensure_space(LINE_HEIGHT * 2)
    col = flow.col_def()
    flow.draw_line([(col["x_start"], "Details of Payments Received", "left")], bold=True, size=8)
    for p in payments:
        flow.ensure_space(LINE_HEIGHT)
        col = flow.col_def()
        line = (f"{p.get('pay_type', 'Payment')}-{p.get('date', '')}-"
                f"{p.get('location', '')}").rstrip('-')
        flow.draw_line([
            (col["x_start"], line, "left"),
            (col["amount_x"], f"{p['amount']:,.2f}", "right"),
        ], size=8)
    flow.ensure_space(LINE_HEIGHT)
    col = flow.col_def()
    flow.draw_line([
        (col["x_start"], "Total Payments Received", "left"),
        (col["amount_x"], f"{data.get('total_payments', 0):,.2f}", "right"),
    ], bold=True, size=8)


def _draw_cancel_payments_flow(flow, data):
    cancelled = data.get("cancelled_payments", [])
    if not cancelled:
        return
    flow.ensure_space(LINE_HEIGHT * 2)
    col = flow.col_def()
    flow.draw_line([(col["x_start"], "Cancel Payment", "left")], bold=True, size=8)
    for p in cancelled:
        flow.ensure_space(LINE_HEIGHT)
        col = flow.col_def()
        line = (f"{p.get('pay_type', '')}-{p.get('date', '')}-"
                f"{p.get('location', '')}").rstrip('-')
        flow.draw_line([
            (col["x_start"], line, "left"),
            (col["amount_x"], f"{p['amount']:,.2f}", "right"),
        ], size=8)


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
    """If the first two columns are Date/Time-shaped, merge them into one
    visual column (confirmed against CLAUDE.md's EVENTHEADING_33 evidence:
    5 raw columns render as 4 visible ones, Date&Time combined).

    Header text specifically must read exactly "Date &Time" (space before
    &, none after - confirmed against golden's exact literal string, not
    "Date & Time" symmetric spacing). Row VALUES (actual dates/times, e.g.
    "04/09/2025 13:24:54") must stay plain-space-joined - the & only belongs
    on the header, so this is a separate branch, not a global format change."""
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


def _cells_with_fit(positions, amount_x, values, last_cell_text="", size=7,
                     bold=False, pad=3.0):
    """Build draw_line cells for a table row/header: each left-aligned cell's
    max_width is the gap to the next column's start, so long values (e.g.
    13-digit dialled numbers) shrink to fit instead of overflowing into the
    next column. For the LAST left-aligned cell, the boundary is not raw
    amount_x but amount_x minus the actual rendered width of the final
    right-aligned cell (last_cell_text) - that text is right-aligned AT
    amount_x, so its own left edge is well before amount_x, and treating
    amount_x itself as the boundary let long last-cells (e.g. "List Price")
    overlap the last left column (e.g. "Subscription Type")."""
    font = "hebo" if bold else "helv"
    last_width = (fitz.get_text_length(str(last_cell_text), fontname=font,
                                        fontsize=size)
                  if last_cell_text else 0.0)
    last_boundary = amount_x - last_width - pad
    cells = []
    n = len(positions)
    for i, val in enumerate(values[:n]):
        next_x = positions[i + 1] if i + 1 < n else last_boundary
        cells.append((positions[i], val, "left", max(next_x - positions[i] - pad, 1.0)))
    return cells


def _draw_usage_flow(flow, data):
    # One section per ref, in GMF-native order (see parser.py's usage_entries
    # comment) - NOT grouped by usage type. `section["ref"]` is singular, not
    # a list: each entry here already IS one ref's section.
    for section in data.get("usage_sections", []):
        ref = section["ref"]
        hdr = f'Detailed Usage Charges for {section["label"]}'
        if ref.get("phone"):
            hdr += f' {ref["phone"]}'
        flow.ensure_space(LINE_HEIGHT * 2)  # orphan control
        col = flow.col_def()
        flow.draw_line([(col["x_start"], hdr, "left")], bold=True, size=8)

        ref_total = 0
        for sub in ref["subsections"]:
            rows = sub.get("rows", [])
            ref_total += sub.get("subtotal", 0)

            if sub.get("label"):
                flow.ensure_space(LINE_HEIGHT * 2)
                col = flow.col_def()
                flow.draw_line([(col["x_start"], sub["label"], "left")], bold=True, size=7)

            # Some subsections (confirmed against golden, e.g. ref
            # 0252280222's Off Net/On Net) legitimately have zero
            # itemized rows but a real nonzero total - just the label and
            # "Total for X" line, no table at all. Only draw the
            # header/box/rows when there IS real event data.
            if rows:
                headers = _merge_date_time(sub.get("headers", []), is_header=True)
                font_size = _table_font_size(len(headers))

                # Orphan control (section 1.3): reserve header + first row
                # together so the column header never lands alone at a break.
                flow.ensure_space(LINE_HEIGHT * 2)
                col = flow.col_def()
                positions = _table_col_positions(col, len(headers))
                cells = _cells_with_fit(positions, col["amount_x"], headers[:-1],
                                         last_cell_text=headers[-1] if headers else "",
                                         size=font_size, bold=True)
                if headers:
                    cells.append((col["amount_x"], headers[-1], "right"))
                header_y = flow.y
                flow.draw_line(cells, bold=True, size=font_size)
                flow.draw_header_box(col, header_y)

                for row in rows:
                    flow.ensure_space(LINE_HEIGHT)
                    col = flow.col_def()
                    merged_row = _merge_date_time(row)
                    positions = _table_col_positions(col, len(merged_row))
                    amt_preview = f"{_row_amount(row):,.3f}"
                    row_cells = _cells_with_fit(
                        positions, col["amount_x"], merged_row[:-1],
                        last_cell_text=amt_preview, size=font_size)
                    amt = _row_amount(row)
                    row_cells.append((col["amount_x"], f"{amt:,.3f}", "right"))
                    flow.draw_line(row_cells, size=font_size)

            sub_label = sub.get("label") or section["label"]
            flow.ensure_space(LINE_HEIGHT)
            col = flow.col_def()
            flow.draw_line([
                (col["x_start"], f"Total for {sub_label}", "left"),
                (col["amount_x"], f"{sub.get('subtotal', 0):,.3f}", "right"),
            ], bold=True, size=7)

        # Closing total is per-REF (confirmed against golden: 13 separate
        # "Total Usage Charges for P_Domestic Voice Usage" lines, each
        # with that ref's own amount - not one combined total per family).
        # Summed here from this ref's own drawn subsections rather than
        # `section['grand_total']`, since that field is family-level and
        # gets overwritten by whichever ref's SLTITEMGRANDTOTAL the parser
        # saw last when a family has multiple refs.
        flow.ensure_space(LINE_HEIGHT)
        col = flow.col_def()
        flow.draw_line([
            (col["x_start"], f"Total Usage Charges for {section['label']}", "left"),
            (col["amount_x"], f"{ref_total:,.3f}", "right"),
        ], bold=True, size=8)


def _draw_messages_flow(flow, data):
    messages = data.get("marketing_messages", [])
    suspended = data.get("suspended_message", "")
    if messages:
        flow.ensure_space(LINE_HEIGHT * 2)
        col = flow.col_def()
        flow.draw_line([(col["x_start"], "Message on Bill", "left")], bold=True, size=8)
        for m in messages:
            flow.ensure_space(LINE_HEIGHT)
            col = flow.col_def()
            flow.draw_line([(col["x_start"], m, "left")], size=8)
    if suspended:
        flow.ensure_space(LINE_HEIGHT)
        col = flow.col_def()
        flow.draw_line([(col["x_start"], suspended, "left")], bold=True, size=8)
