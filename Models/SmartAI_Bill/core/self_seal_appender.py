"""
self_seal_appender.py
---------------------
Post-processing utility: appends the approved Self-Seal envelope composite PDF
as a second page to any generated bill PDF that:

  1. Has exactly ONE page, AND
  2. Was produced by a template that is NOT in EXCLUDED_TEMPLATES.

If no Self-Seal artwork is currently approved in the database, or if the
composite PDF file cannot be found on disk, the function is a silent no-op so
bill generation is never blocked.

Excluded templates (never appended):
  - lod
  - vat_confirmation
  - final_notice
  - customer_letter_logo_v1print
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Templates whose output PDFs are eligible for the Self-Seal envelope.
# ONLY NonVAT Home and NonVAT Enterprise print invoices receive the Self-Seal page.
ALLOWED_TEMPLATES: frozenset[str] = frozenset({
    "nonvat_home",
    "nonvat_enterprise",
})

# Backward compatibility alias
EXCLUDED_TEMPLATES: frozenset[str] = frozenset()


def get_approved_self_seal_pdf() -> Optional[str]:
    """
    Query the application database for the most-recently approved Self-Seal
    EnvelopeArtwork record and return its composite PDF path.

    Returns None if:
    - No approved Self-Seal artwork exists.
    - The composite PDF file is missing from disk.
    - The DB is unreachable (exception is swallowed so callers are not broken).
    """
    try:
        # Import lazily so this module can be imported inside worker sub-processes
        # without requiring app-level setup at module load time.
        import sys
        import os as _os

        # Ensure the app package is importable when called from a worker process
        _app_root = _os.path.abspath(
            _os.path.join(_os.path.dirname(__file__), "../../../../")
        )
        if _app_root not in sys.path:
            sys.path.insert(0, _app_root)

        from app.db.base import SessionLocal
        from app.db.models import (
            EnvelopeArtwork,
            EnvelopeArtworkStatus,
            EnvelopeTemplate,
            EnvelopeType,
        )

        with SessionLocal() as db:
            # Find the most recently approved SELF_SEAL artwork that has a
            # valid composite PDF on disk.
            artwork = (
                db.query(EnvelopeArtwork)
                .join(EnvelopeTemplate)
                .filter(
                    EnvelopeTemplate.envelope_type == EnvelopeType.SELF_SEAL,
                    EnvelopeArtwork.status == EnvelopeArtworkStatus.APPROVED,
                    EnvelopeArtwork.output_pdf_path.isnot(None),
                )
                .order_by(EnvelopeArtwork.created_at.desc())
                .first()
            )

        if artwork is None:
            logger.debug("No approved Self-Seal artwork found in DB.")
            return None

        pdf_path = artwork.output_pdf_path
        if not pdf_path or not os.path.exists(pdf_path):
            logger.warning(
                "Approved Self-Seal artwork (id=%s) has no composite PDF on disk: %s",
                artwork.id,
                pdf_path,
            )
            return None

        logger.debug("Approved Self-Seal PDF: %s", pdf_path)
        return pdf_path

    except Exception as exc:
        logger.warning("Could not query approved Self-Seal artwork: %s", exc)
        return None


def get_pdf_page_count(pdf_path: str) -> int:
    """Return the number of pages in a PDF file. Returns 0 on error."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf_path)
        return len(reader.pages)
    except Exception as exc:
        logger.warning("Could not read page count for %s: %s", pdf_path, exc)
        return 0


def create_self_seal_address_overlay(doc_data: Optional[dict] = None):
    """
    Generate an overlay with customer/company name, address lines, and postal/zip code
    rotated 180 degrees at the letter box coordinates:
    x = 419.53, y = 657.64 (top-left) -> ReportLab y = 841.89 - 657.64 = 184.25 pt.
    """
    if not doc_data:
        return None

    import io
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import black

    PAGE_W = 595.28
    PAGE_H = 841.89

    # Extract recipient address lines
    lines = []
    top_name = (
        doc_data.get("business_name")
        if doc_data.get("address_name_not_required")
        else (doc_data.get("business_name") or doc_data.get("customer_name", ""))
    )
    if top_name:
        lines.append(top_name)
    elif doc_data.get("customer_name"):
        lines.append(doc_data["customer_name"])

    addr = doc_data.get("address_lines")
    if addr and isinstance(addr, list):
        for a in addr:
            s = str(a).strip() if a else ""
            if s and s != "-":
                lines.append(s)
    else:
        raw_addr = doc_data.get("address", "") or doc_data.get("customer_address", "")
        if raw_addr:
            if "\n" in raw_addr:
                lines.extend([l.strip() for l in raw_addr.split("\n") if l.strip() and l.strip() != "-"])
            else:
                lines.extend([p.strip() for p in raw_addr.split(",") if p.strip() and p.strip() != "-"])

    zip_code = doc_data.get("zip_code") or doc_data.get("postal_code")
    if zip_code and str(zip_code).strip() and str(zip_code).strip() != "-":
        if str(zip_code).strip() not in lines:
            lines.append(str(zip_code).strip())

    if not lines:
        return None

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(PAGE_W, PAGE_H))
    c.saveState()

    # Target address window on self-seal template (DPS 419 area, 180-deg rotated)
    # The recipient window is located at x: ~40..290 pt, y: ~580..720 pt
    box_x = 285.0
    box_y_rl = 205
    c.translate(box_x, box_y_rl)
    c.rotate(180)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(black)

    cur_y = 0
    line_height = 11
    for idx, line_text in enumerate(lines):
        if line_text:
            if idx == 0:
                c.setFont("Helvetica-Bold", 9)
            else:
                c.setFont("Helvetica-Bold", 8.5)
            c.drawString(0, cur_y, str(line_text))
            cur_y -= line_height

    c.restoreState()
    c.save()
    buf.seek(0)
    return buf


def append_self_seal_if_needed(
    pdf_path: str,
    template_id: str,
    approved_self_seal_pdf: Optional[str],
    doc_data: Optional[dict] = None,
    is_print: bool = True,
) -> bool:
    """
    Append the Self-Seal envelope as page 2 of *pdf_path* **in-place** when:

      - *approved_self_seal_pdf* is not None (an approved artwork exists), AND
      - *template_id* is in ALLOWED_TEMPLATES ('nonvat_home', 'nonvat_enterprise'), AND
      - *is_print* is True (only for print invoices), AND
      - *pdf_path* currently has exactly ONE page.

    Returns True if the PDF was modified, False otherwise.
    """
    if not approved_self_seal_pdf:
        return False

    if template_id not in ALLOWED_TEMPLATES:
        logger.debug(
            "Skipping Self-Seal append for non-eligible template '%s': %s",
            template_id, pdf_path,
        )
        return False

    if not is_print:
        logger.debug(
            "Skipping Self-Seal append for non-print invoice (%s): %s",
            template_id, pdf_path,
        )
        return False

    page_count = get_pdf_page_count(pdf_path)
    if page_count != 1:
        logger.debug(
            "Skipping Self-Seal append: '%s' has %d page(s) (need exactly 1).",
            pdf_path, page_count,
        )
        return False

    try:
        from pypdf import PdfReader, PdfWriter
        from copy import deepcopy

        bill_reader = PdfReader(pdf_path)
        seal_reader = PdfReader(approved_self_seal_pdf)

        writer = PdfWriter()
        # Page 1: the bill
        writer.add_page(bill_reader.pages[0])

        # Page 2: the Self-Seal envelope with recipient address window overlay
        seal_page = deepcopy(seal_reader.pages[0])
        overlay_buf = create_self_seal_address_overlay(doc_data)
        if overlay_buf:
            overlay_reader = PdfReader(overlay_buf)
            seal_page.merge_page(overlay_reader.pages[0])

        writer.add_page(seal_page)

        # Write to a temp file alongside the original, then rename atomically
        tmp_path = pdf_path + ".selfseal_tmp"
        with open(tmp_path, "wb") as fh:
            writer.write(fh)

        os.replace(tmp_path, pdf_path)

        logger.info(
            "Self-Seal envelope appended to 1-page bill (%s, template=%s).",
            os.path.basename(pdf_path), template_id,
        )
        return True

    except Exception as exc:
        logger.error(
            "Failed to append Self-Seal envelope to %s: %s",
            pdf_path, exc, exc_info=True,
        )
        tmp_path = pdf_path + ".selfseal_tmp"
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        return False


def apply_self_seal_to_directory(
    pdf_dir: str,
    template_id: str,
    approved_self_seal_pdf: Optional[str],
    doc_data_map: Optional[dict] = None,
    is_print: bool = True,
) -> int:
    """
    Convenience helper: apply ``append_self_seal_if_needed`` to every PDF in
    *pdf_dir*.  Returns the number of PDFs that were modified.
    """
    if not approved_self_seal_pdf or not is_print or template_id not in ALLOWED_TEMPLATES:
        return 0

    modified = 0
    try:
        for fname in os.listdir(pdf_dir):
            if fname.lower().endswith(".pdf"):
                fpath = os.path.join(pdf_dir, fname)
                doc_data = doc_data_map.get(fname) if doc_data_map else None
                if append_self_seal_if_needed(fpath, template_id, approved_self_seal_pdf, doc_data=doc_data, is_print=is_print):
                    modified += 1
    except Exception as exc:
        logger.error("Error applying Self-Seal to directory %s: %s", pdf_dir, exc)

    return modified
