"""
Envelope Portal API Router
--------------------------
Manages envelope templates, artwork uploads, composite generation, and approval workflow.
Completely isolated from existing billing/GMF/invoice logic.
"""
import io
import os
import json
import shutil
import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session as DbSession
from PIL import Image as PILImage

from app.db.base import SessionLocal
from app.db.models import (
    EnvelopeTemplate, EnvelopeArtwork, EnvelopeType,
    EnvelopeArtworkStatus,
)
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/envelope", tags=["envelope"])

# ── Dependency ────────────────────────────────────────────────────────────

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Envelope template dimension specs (from actual PDF analysis) ──────────
# Box coords extracted from output PDFs (placed artwork image rect)
# aspect ratios stored as x100 integers in DB; reference values here
ENVELOPE_SPECS = {
    EnvelopeType.LARGE: {
        "display_name": "SLT Large Envelope",
        "base_pdf": "05717-SLT Large Envelope.pdf",
        "box": (1182, 706, 2015, 1524),  # x0, y0, x1, y1 in pts
        "box_size": (834, 818),           # width x height pts
        "min_width": 700, "min_height": 700,
        "aspect_min": 70, "aspect_max": 140,  # 0.70 - 1.40 (square-ish)
        "rotation_deg": 0, "fit_mode": "stretch",
        "sample_img_size": "833x817 px",
    },
    EnvelopeType.MEDIUM: {
        "display_name": "SLT Medium Envelope",
        "base_pdf": "05717-SLT Medium Envelope.pdf",
        "box": (152, 912, 1040, 1379),
        "box_size": (888, 467),
        "min_width": 800, "min_height": 400,
        "aspect_min": 150, "aspect_max": 250,  # 1.50 - 2.50 (wide)
        "sample_img_size": "1179x618 px",
        "rotation_deg": 0, "fit_mode": "cover",
    },
    EnvelopeType.SELF_SEAL: {
        "display_name": "SLT Self-Seal A4 Envelope",
        "base_pdf": "05717-SLT Self Seal-01.pdf",
        "box": (57, 420, 865, 697),
        "box_size": (808, 276),
        "min_width": 800, "min_height": 200,
        "aspect_min": 250, "aspect_max": 450,  # 2.50 - 4.50 (very wide/flat)
        "sample_img_size": "1070x361 px",
        "rotation_deg": 0, "fit_mode": "cover",
    },
}

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}


# ── Helpers ────────────────────────────────────────────────────────────────

def _ensure_envelope_templates_seeded(db: DbSession):
    """Create the 3 envelope template DB records if they don't exist."""
    for etype, spec in ENVELOPE_SPECS.items():
        existing = db.query(EnvelopeTemplate).filter(
            EnvelopeTemplate.envelope_type == etype
        ).first()
        if not existing:
            tmpl = EnvelopeTemplate(
                envelope_type=etype,
                display_name=spec["display_name"],
                base_pdf_path=str(settings.envelope_base_dir / spec["base_pdf"]),
                box_x0=spec["box"][0], box_y0=spec["box"][1],
                box_x1=spec["box"][2], box_y1=spec["box"][3],
                rotation_deg=spec.get("rotation_deg", 0),
                fit_mode=spec.get("fit_mode", "cover"),
                min_width=spec["min_width"],
                min_height=spec["min_height"],
                aspect_min=spec["aspect_min"],
                aspect_max=spec["aspect_max"],
            )
            db.add(tmpl)
    db.commit()


def _render_pdf_page_as_png(pdf_path: str, dpi: int = 120) -> bytes:
    """Render first page of PDF as PNG bytes."""
    import fitz
    doc = fitz.open(pdf_path)
    pix = doc[0].get_pixmap(dpi=dpi)
    png_bytes = pix.tobytes("png")
    doc.close()
    return png_bytes


def _generate_composite(template: EnvelopeTemplate, image_path: str) -> tuple:
    """Generate composite PDF + PNG preview using place_artwork engine."""
    import sys
    engine_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../Models/SmartAI_Bill/templates/envelope"))
    if engine_dir not in sys.path:
        sys.path.insert(0, engine_dir)
    from place_artwork import place_image, render_preview

    import fitz
    box = fitz.Rect(template.box_x0, template.box_y0, template.box_x1, template.box_y1)

    # Generate output paths
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_name = f"{template.envelope_type.value}_{ts}"
    out_pdf = str(settings.envelope_output_dir / f"{out_name}.pdf")
    out_png = str(settings.envelope_output_dir / f"{out_name}_preview.png")

    settings.envelope_output_dir.mkdir(parents=True, exist_ok=True)

    place_image(template.base_pdf_path, out_pdf, box, image_path,
                rotate_deg=template.rotation_deg, fit=template.fit_mode)
    render_preview(out_pdf, out_png, dpi=150)

    return out_pdf, out_png


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.get("/templates")
def list_templates(db: DbSession = Depends(get_db)):
    """List all 3 envelope types with current active artwork status."""
    _ensure_envelope_templates_seeded(db)
    templates = db.query(EnvelopeTemplate).all()
    result = []
    for t in templates:
        active_artwork = db.query(EnvelopeArtwork).filter(
            EnvelopeArtwork.envelope_template_id == t.id,
            EnvelopeArtwork.status.in_([
                EnvelopeArtworkStatus.ACTIVE,
                EnvelopeArtworkStatus.SUBMITTED,
                EnvelopeArtworkStatus.APPROVED,
            ])
        ).order_by(EnvelopeArtwork.created_at.desc()).first()

        spec = ENVELOPE_SPECS.get(t.envelope_type, {})
        result.append({
            "id": t.id,
            "envelope_type": t.envelope_type.value,
            "display_name": t.display_name,
            "box_size": f"{(t.box_x1 or 0) - (t.box_x0 or 0)}x{(t.box_y1 or 0) - (t.box_y0 or 0)} pts",
            "fit_mode": t.fit_mode,
            "min_width": t.min_width,
            "min_height": t.min_height,
            "aspect_range": f"{t.aspect_min / 100:.2f} - {t.aspect_max / 100:.2f}",
            "sample_img_size": spec.get("sample_img_size", ""),
            "has_active_artwork": active_artwork is not None,
            "active_artwork": {
                "id": active_artwork.id,
                "filename": active_artwork.original_filename,
                "status": active_artwork.status.value,
                "image_size": f"{active_artwork.image_width}x{active_artwork.image_height}",
                "created_at": active_artwork.created_at.isoformat() if active_artwork.created_at else None,
            } if active_artwork else None,
        })
    return result


@router.get("/templates/{template_id}")
def get_template(template_id: int, db: DbSession = Depends(get_db)):
    """Get single envelope template details + artwork history."""
    _ensure_envelope_templates_seeded(db)
    tmpl = db.query(EnvelopeTemplate).filter(EnvelopeTemplate.id == template_id).first()
    if not tmpl:
        raise HTTPException(404, "Envelope template not found")

    artworks = db.query(EnvelopeArtwork).filter(
        EnvelopeArtwork.envelope_template_id == tmpl.id
    ).order_by(EnvelopeArtwork.created_at.desc()).all()

    spec = ENVELOPE_SPECS.get(tmpl.envelope_type, {})
    return {
        "id": tmpl.id,
        "envelope_type": tmpl.envelope_type.value,
        "display_name": tmpl.display_name,
        "base_pdf_path": tmpl.base_pdf_path,
        "box": {"x0": tmpl.box_x0, "y0": tmpl.box_y0, "x1": tmpl.box_x1, "y1": tmpl.box_y1},
        "rotation_deg": tmpl.rotation_deg,
        "fit_mode": tmpl.fit_mode,
        "min_width": tmpl.min_width,
        "min_height": tmpl.min_height,
        "aspect_min": tmpl.aspect_min / 100,
        "aspect_max": tmpl.aspect_max / 100,
        "sample_img_size": spec.get("sample_img_size", ""),
        "artworks": [{
            "id": a.id,
            "filename": a.original_filename,
            "status": a.status.value,
            "image_size": f"{a.image_width}x{a.image_height}",
            "rejection_reason": a.rejection_reason,
            "uploaded_by": a.uploaded_by,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "replaced_at": a.replaced_at.isoformat() if a.replaced_at else None,
        } for a in artworks],
    }


@router.get("/templates/{template_id}/base-pdf")
def serve_base_template_pdf(template_id: int, db: DbSession = Depends(get_db)):
    """Serve the empty base envelope PDF file directly with inline disposition."""
    _ensure_envelope_templates_seeded(db)
    tmpl = db.query(EnvelopeTemplate).filter(EnvelopeTemplate.id == template_id).first()
    if not tmpl:
        raise HTTPException(404, "Envelope template not found")
    if not os.path.exists(tmpl.base_pdf_path):
        raise HTTPException(404, f"Base PDF not found on disk: {tmpl.base_pdf_path}")
    return FileResponse(
        tmpl.base_pdf_path,
        media_type="application/pdf",
        content_disposition_type="inline",
        filename=f"{tmpl.envelope_type.value}_base.pdf",
    )


@router.get("/templates/{template_id}/download-base-pdf")
def download_base_template_pdf(template_id: int, db: DbSession = Depends(get_db)):
    """Download the empty base envelope PDF file directly as an attachment."""
    _ensure_envelope_templates_seeded(db)
    tmpl = db.query(EnvelopeTemplate).filter(EnvelopeTemplate.id == template_id).first()
    if not tmpl:
        raise HTTPException(404, "Envelope template not found")
    if not os.path.exists(tmpl.base_pdf_path):
        raise HTTPException(404, f"Base PDF not found on disk: {tmpl.base_pdf_path}")
    return FileResponse(
        tmpl.base_pdf_path,
        media_type="application/pdf",
        content_disposition_type="attachment",
        filename=f"{tmpl.envelope_type.value}_base.pdf",
    )


@router.get("/templates/{template_id}/preview-base")
def preview_base_template(template_id: int, db: DbSession = Depends(get_db)):
    """Render the empty base envelope PDF as a PNG image."""
    _ensure_envelope_templates_seeded(db)
    tmpl = db.query(EnvelopeTemplate).filter(EnvelopeTemplate.id == template_id).first()
    if not tmpl:
        raise HTTPException(404, "Envelope template not found")
    if not os.path.exists(tmpl.base_pdf_path):
        raise HTTPException(404, f"Base PDF not found on disk: {tmpl.base_pdf_path}")

    png_bytes = _render_pdf_page_as_png(tmpl.base_pdf_path, dpi=120)
    return StreamingResponse(io.BytesIO(png_bytes), media_type="image/png")


@router.post("/templates/{template_id}/upload-artwork")
def upload_artwork(
    template_id: int,
    file: UploadFile = File(...),
    db: DbSession = Depends(get_db),
):
    """Upload a promotional image for an envelope type with dimension validation."""
    _ensure_envelope_templates_seeded(db)
    tmpl = db.query(EnvelopeTemplate).filter(EnvelopeTemplate.id == template_id).first()
    if not tmpl:
        raise HTTPException(404, "Envelope template not found")

    # 1. Extension validation
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(422, detail={
            "error": "invalid_format",
            "message": f"File format '{ext}' is not supported. Accepted formats: {', '.join(ALLOWED_EXTENSIONS)}",
        })

    # 2. Read image and validate dimensions
    try:
        contents = file.file.read()
        img = PILImage.open(io.BytesIO(contents))
        img_w, img_h = img.size
    except Exception:
        raise HTTPException(422, detail={
            "error": "invalid_image",
            "message": "Could not read the uploaded file as a valid image.",
        })

    # 3. Dimension validation (flexible ranges)
    if img_w < tmpl.min_width:
        raise HTTPException(422, detail={
            "error": "too_small",
            "message": f"Image width {img_w}px is too small for {tmpl.display_name}. Minimum width: {tmpl.min_width}px.",
            "required_min_width": tmpl.min_width,
            "sample_size": ENVELOPE_SPECS.get(tmpl.envelope_type, {}).get("sample_img_size", ""),
        })
    if img_h < tmpl.min_height:
        raise HTTPException(422, detail={
            "error": "too_small",
            "message": f"Image height {img_h}px is too small for {tmpl.display_name}. Minimum height: {tmpl.min_height}px.",
            "required_min_height": tmpl.min_height,
            "sample_size": ENVELOPE_SPECS.get(tmpl.envelope_type, {}).get("sample_img_size", ""),
        })

    aspect = round(img_w / img_h * 100)
    if aspect < tmpl.aspect_min or aspect > tmpl.aspect_max:
        raise HTTPException(422, detail={
            "error": "wrong_aspect_ratio",
            "message": (
                f"Image aspect ratio {img_w/img_h:.2f} ({img_w}x{img_h}px) is not suitable for {tmpl.display_name}. "
                f"Required aspect ratio: {tmpl.aspect_min/100:.2f} - {tmpl.aspect_max/100:.2f}. "
                f"Sample image size: {ENVELOPE_SPECS.get(tmpl.envelope_type, {}).get('sample_img_size', 'N/A')}."
            ),
            "your_aspect": round(img_w / img_h, 2),
            "required_range": f"{tmpl.aspect_min/100:.2f} - {tmpl.aspect_max/100:.2f}",
            "sample_size": ENVELOPE_SPECS.get(tmpl.envelope_type, {}).get("sample_img_size", ""),
        })

    # 4. Save image to disk
    settings.envelope_artwork_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = f"{tmpl.envelope_type.value}_{ts}{ext}"
    save_path = settings.envelope_artwork_dir / safe_name
    with open(save_path, "wb") as f:
        f.write(contents)

    # 5. Mark any current ACTIVE artwork as REPLACED
    active = db.query(EnvelopeArtwork).filter(
        EnvelopeArtwork.envelope_template_id == tmpl.id,
        EnvelopeArtwork.status == EnvelopeArtworkStatus.ACTIVE,
    ).all()
    for a in active:
        a.status = EnvelopeArtworkStatus.REPLACED
        a.replaced_at = datetime.now()

    # 6. Generate composite PDF + preview
    try:
        out_pdf, out_png = _generate_composite(tmpl, str(save_path))
    except Exception as e:
        logger.error(f"Failed to generate composite for {tmpl.display_name}: {e}")
        out_pdf, out_png = None, None

    # 7. Create DB record
    artwork = EnvelopeArtwork(
        envelope_template_id=tmpl.id,
        original_filename=file.filename or safe_name,
        image_path=str(save_path),
        image_width=img_w,
        image_height=img_h,
        output_pdf_path=out_pdf,
        preview_png_path=out_png,
        status=EnvelopeArtworkStatus.ACTIVE,
    )
    db.add(artwork)
    db.commit()
    db.refresh(artwork)

    return {
        "id": artwork.id,
        "filename": artwork.original_filename,
        "image_size": f"{img_w}x{img_h}",
        "status": artwork.status.value,
        "output_pdf_path": artwork.output_pdf_path,
        "preview_available": artwork.preview_png_path is not None,
        "message": f"Artwork uploaded successfully for {tmpl.display_name}!",
    }


@router.get("/artworks/{artwork_id}/preview")
def preview_artwork(artwork_id: int, db: DbSession = Depends(get_db)):
    """Serve the composite preview PNG."""
    artwork = db.query(EnvelopeArtwork).filter(EnvelopeArtwork.id == artwork_id).first()
    if not artwork:
        raise HTTPException(404, "Artwork not found")
    if not artwork.preview_png_path or not os.path.exists(artwork.preview_png_path):
        raise HTTPException(404, "Preview not generated yet")
    return FileResponse(artwork.preview_png_path, media_type="image/png")


@router.get("/artworks/{artwork_id}/view-pdf")
def view_artwork_pdf(artwork_id: int, db: DbSession = Depends(get_db)):
    """Serve the generated final composite PDF inline for viewing."""
    artwork = db.query(EnvelopeArtwork).filter(EnvelopeArtwork.id == artwork_id).first()
    if not artwork:
        raise HTTPException(404, "Artwork not found")
    if not artwork.output_pdf_path or not os.path.exists(artwork.output_pdf_path):
        raise HTTPException(404, "Output PDF not generated yet")
    return FileResponse(
        artwork.output_pdf_path,
        media_type="application/pdf",
        content_disposition_type="inline",
        filename=f"{artwork.original_filename.rsplit('.', 1)[0]}_envelope.pdf",
    )


@router.get("/artworks/{artwork_id}/download")
def download_artwork_pdf(artwork_id: int, db: DbSession = Depends(get_db)):
    """Download the generated final composite PDF."""
    artwork = db.query(EnvelopeArtwork).filter(EnvelopeArtwork.id == artwork_id).first()
    if not artwork:
        raise HTTPException(404, "Artwork not found")
    if not artwork.output_pdf_path or not os.path.exists(artwork.output_pdf_path):
        raise HTTPException(404, "Output PDF not generated yet")
    return FileResponse(
        artwork.output_pdf_path,
        media_type="application/pdf",
        content_disposition_type="attachment",
        filename=f"{artwork.original_filename.rsplit('.', 1)[0]}_envelope.pdf",
    )


@router.delete("/artworks/{artwork_id}")
def remove_artwork(artwork_id: int, db: DbSession = Depends(get_db)):
    """Remove/soft-delete an artwork (reverts envelope to empty template)."""
    artwork = db.query(EnvelopeArtwork).filter(EnvelopeArtwork.id == artwork_id).first()
    if not artwork:
        raise HTTPException(404, "Artwork not found")
    artwork.status = EnvelopeArtworkStatus.REMOVED
    artwork.replaced_at = datetime.now()
    db.commit()
    return {"message": "Artwork removed successfully", "id": artwork_id}


@router.post("/artworks/{artwork_id}/submit")
def submit_for_approval(artwork_id: int, db: DbSession = Depends(get_db)):
    """Submit artwork for admin review/approval."""
    artwork = db.query(EnvelopeArtwork).filter(EnvelopeArtwork.id == artwork_id).first()
    if not artwork:
        raise HTTPException(404, "Artwork not found")
    if artwork.status != EnvelopeArtworkStatus.ACTIVE:
        raise HTTPException(400, f"Can only submit ACTIVE artwork. Current status: {artwork.status.value}")
    artwork.status = EnvelopeArtworkStatus.SUBMITTED
    db.commit()
    return {"message": "Artwork submitted for admin approval", "id": artwork_id, "status": "SUBMITTED"}


@router.post("/artworks/{artwork_id}/approve")
def approve_artwork(artwork_id: int, db: DbSession = Depends(get_db)):
    """Admin approves submitted artwork."""
    artwork = db.query(EnvelopeArtwork).filter(EnvelopeArtwork.id == artwork_id).first()
    if not artwork:
        raise HTTPException(404, "Artwork not found")
    if artwork.status != EnvelopeArtworkStatus.SUBMITTED:
        raise HTTPException(400, f"Can only approve SUBMITTED artwork. Current status: {artwork.status.value}")
    artwork.status = EnvelopeArtworkStatus.APPROVED
    db.commit()

    # Copy approved output to main output archive
    if artwork.output_pdf_path and os.path.exists(artwork.output_pdf_path):
        archive_dir = settings.output_dir / datetime.now().strftime("%Y-%m-%d") / "Envelope"
        archive_dir.mkdir(parents=True, exist_ok=True)
        dest = archive_dir / Path(artwork.output_pdf_path).name
        shutil.copy2(artwork.output_pdf_path, dest)

    return {"message": "Artwork approved!", "id": artwork_id, "status": "APPROVED"}


@router.post("/artworks/{artwork_id}/reject")
def reject_artwork(
    artwork_id: int,
    reason: str = Query("", description="Rejection reason"),
    db: DbSession = Depends(get_db),
):
    """Admin rejects submitted artwork."""
    artwork = db.query(EnvelopeArtwork).filter(EnvelopeArtwork.id == artwork_id).first()
    if not artwork:
        raise HTTPException(404, "Artwork not found")
    if artwork.status != EnvelopeArtworkStatus.SUBMITTED:
        raise HTTPException(400, f"Can only reject SUBMITTED artwork. Current status: {artwork.status.value}")
    artwork.status = EnvelopeArtworkStatus.REJECTED
    artwork.rejection_reason = reason or "Rejected by admin"
    db.commit()
    return {"message": "Artwork rejected", "id": artwork_id, "status": "REJECTED", "reason": artwork.rejection_reason}


@router.get("/size-guide")
def size_guide():
    """Return image size requirements for all 3 envelope types."""
    guide = []
    for etype, spec in ENVELOPE_SPECS.items():
        guide.append({
            "envelope_type": etype.value,
            "display_name": spec["display_name"],
            "min_width": spec["min_width"],
            "min_height": spec["min_height"],
            "aspect_ratio_range": f"{spec['aspect_min']/100:.2f} - {spec['aspect_max']/100:.2f}",
            "sample_image_size": spec.get("sample_img_size", ""),
            "box_size_pts": f"{spec['box_size'][0]}x{spec['box_size'][1]}",
            "fit_mode": spec.get("fit_mode", "cover"),
        })
    return guide
