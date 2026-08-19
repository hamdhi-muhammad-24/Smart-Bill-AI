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

# Templates whose output PDFs must never have the envelope appended,
# regardless of page count or approval status.
EXCLUDED_TEMPLATES: frozenset[str] = frozenset({
    "lod",
    "vat_confirmation",
    "final_notice",
    "customer_letter_logo_v1print",
})


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


def append_self_seal_if_needed(
    pdf_path: str,
    template_id: str,
    approved_self_seal_pdf: Optional[str],
) -> bool:
    """
    Append the Self-Seal envelope as page 2 of *pdf_path* **in-place** when:

      - *approved_self_seal_pdf* is not None (an approved artwork exists), AND
      - *template_id* is NOT in EXCLUDED_TEMPLATES, AND
      - *pdf_path* currently has exactly ONE page.

    Returns True if the PDF was modified, False otherwise.

    The modification is atomic: a temporary file is written first and then
    renamed over the original, so a crash mid-write does not corrupt the bill.
    """
    if not approved_self_seal_pdf:
        return False

    if template_id in EXCLUDED_TEMPLATES:
        logger.debug(
            "Skipping Self-Seal append for excluded template '%s': %s",
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

        bill_reader = PdfReader(pdf_path)
        seal_reader = PdfReader(approved_self_seal_pdf)

        writer = PdfWriter()
        # Page 1: the bill
        writer.add_page(bill_reader.pages[0])
        # Page 2: the Self-Seal envelope
        writer.add_page(seal_reader.pages[0])

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
        # Clean up temp file if it was created
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
) -> int:
    """
    Convenience helper: apply ``append_self_seal_if_needed`` to every PDF in
    *pdf_dir*.  Returns the number of PDFs that were modified.
    """
    if not approved_self_seal_pdf:
        return 0

    modified = 0
    try:
        for fname in os.listdir(pdf_dir):
            if fname.lower().endswith(".pdf"):
                fpath = os.path.join(pdf_dir, fname)
                if append_self_seal_if_needed(fpath, template_id, approved_self_seal_pdf):
                    modified += 1
    except Exception as exc:
        logger.error("Error applying Self-Seal to directory %s: %s", pdf_dir, exc)

    return modified
