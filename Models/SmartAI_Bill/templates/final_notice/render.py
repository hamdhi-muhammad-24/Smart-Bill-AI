"""
render.py  -  stamp customer values onto the 2-page FINAL NOTICE template.

Entry point used by generate.py:
  render_all(customers, ...)   -> produce the letters
"""

import io
from typing import List

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from . import config as C
from .parser import Customer, load_customers


def _y(top: float) -> float:
    """Convert 'points from top' to reportlab bottom-origin y."""
    return C.PAGE_H - top


def _draw_value(c, x, top, text, font, size, align="left"):
    if not text:
        return
    c.setFont(font, size)
    if align == "right":
        c.drawRightString(x, _y(top), text)
    else:
        c.drawString(x, _y(top), text)


def _draw_barcode(c, value):
    if not (C.BARCODE_ENABLED and value):
        return
    try:
        from reportlab.graphics.barcode import code128
        b = C.BARCODE_POS
        bc = code128.Code128(value, barHeight=b["bar_height"],
                             barWidth=b["bar_width"], humanReadable=False)
        bc.drawOn(c, b["x"], _y(b["top"]) - b["bar_height"])
    except Exception as e:
        print("  [warn] barcode skipped:", e)


def _build_overlays(cust: Customer) -> List:
    """Return a list of overlay pages (one per template page)."""
    overlays = []
    template = PdfReader(str(C.TEMPLATE))
    for pidx in range(len(template.pages)):
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=(C.PAGE_W, C.PAGE_H))

        # address + sender + barcode + copy-marker live on their configured page
        a = C.ADDRESS_BLOCK
        if a["page"] == pidx:
            c.setFont(a["name_font"], a["name_size"])
            c.drawString(a["x"], _y(a["top"]), cust.name)
            c.setFont(a["addr_font"], a["addr_size"])
            for i, ln in enumerate(cust.address_lines, 1):
                c.drawString(a["x"], _y(a["top"] + i * a["line_gap"]), ln)

        s = C.SENDER_BLOCK
        if s["page"] == pidx:
            c.setFont(s["date_font"], s["date_size"])
            c.drawString(s["x"], _y(s["top"]), cust.fields["date"])
            c.setFont(s["line_font"], s["line_size"])
            for i, ln in enumerate(C.SENDER_LINES, 1):
                c.drawString(s["x"], _y(s["top"] + i * s["line_gap"]), ln)

        if C.BARCODE_POS["page"] == pidx:
            _draw_barcode(c, cust.barcode_value)

        m = C.COPY_MARKER
        if m["page"] == pidx and m.get("text"):
            _draw_value(c, m["x"], m["top"], m["text"], m["font"], m["size"])

        # single-line field placements
        for p in C.PLACEMENTS.get(pidx, []):
            val = cust.fields.get(p["field"], "")
            _draw_value(c, p["x"], p["top"], val, p["font"], p["size"],
                        p.get("align", "left"))

        c.showPage()
        c.save()
        buf.seek(0)
        overlays.append(PdfReader(buf).pages[0])
    return overlays


def _letter_pages(cust: Customer) -> List:
    template = PdfReader(str(C.TEMPLATE))
    overlays = _build_overlays(cust)
    pages = []
    for pidx, tpage in enumerate(template.pages):
        tpage.merge_page(overlays[pidx])
        pages.append(tpage)
    return pages


def render_all(customers: List[Customer]):
    renderer = FinalNoticeRenderer()
    renderer.render(customers)
    renderer.save(str(C.OUTPUT_DIR / C.COMBINED_FILENAME))
    return C.OUTPUT_DIR


class FinalNoticeRenderer:
    def __init__(self):
        self.generated_pdfs = []

    def render(self, records: List[Customer]):
        self.generated_pdfs = []
        for i, cust in enumerate(records, 1):
            writer = PdfWriter()
            for pg in _letter_pages(cust):
                writer.add_page(pg)
            buf = io.BytesIO()
            writer.write(buf)
            pdf_bytes = buf.getvalue()

            acc = str(cust.raw.get(C.FILENAME_COLUMN) or cust.fields.get("account") or f"cust_{i:04d}").strip().replace(" ", "")
            fname = f"{acc}_Final_Notice.pdf"
            self.generated_pdfs.append((fname, pdf_bytes, cust))
        return self.generated_pdfs

    def save(self, output_path: str):
        if not self.generated_pdfs:
            raise RuntimeError("No PDFs generated in render()")

        import os
        out_dir = os.path.dirname(os.path.abspath(output_path))
        os.makedirs(out_dir, exist_ok=True)

        if len(self.generated_pdfs) == 1:
            fname, pdf_bytes, _ = self.generated_pdfs[0]
            target_file = output_path if output_path.lower().endswith(".pdf") else os.path.join(out_dir, fname)
            with open(target_file, "wb") as f:
                f.write(pdf_bytes)
        else:
            for fname, pdf_bytes, _ in self.generated_pdfs:
                target_file = os.path.join(out_dir, fname)
                with open(target_file, "wb") as f:
                    f.write(pdf_bytes)
