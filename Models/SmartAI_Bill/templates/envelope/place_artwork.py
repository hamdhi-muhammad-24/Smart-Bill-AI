"""
Reusable envelope-artwork placement system.

Given an envelope template PDF (with a placeholder box drawn on it) and a
promo image, place the image into the box at exact coordinates, with
control over rotation and fit mode (cover/contain/stretch).

Usage as a library:

    from place_artwork import find_placeholder_box, place_image

    rect = find_placeholder_box("template.pdf")          # auto-detect box
    place_image("template.pdf", "out.pdf", rect, "art.jpg",
                rotate_deg=180, fit="cover")

Usage from CLI:

    python place_artwork.py template.pdf out.pdf art.jpg \
        --rotate 180 --fit cover

    # or supply an explicit box instead of auto-detecting:
    python place_artwork.py template.pdf out.pdf art.jpg \
        --box 152.26 911.79 1040.24 1379.19 --rotate 180
"""
import argparse
import os
import sys
import tempfile
import fitz
from PIL import Image, ImageFilter


def find_placeholder_box(pdf_path, page_number=0, min_area=10000):
    """Find the largest non-white filled rectangle on the page - this is the
    placeholder box left by the designer for the promo image."""
    doc = fitz.open(pdf_path)
    page = doc[page_number]
    best = None
    best_area = 0
    for d in page.get_drawings():
        fill = d.get("fill")
        if not fill or fill == (1, 1, 1):
            continue
        r = d["rect"]
        area = r.width * r.height
        if area > best_area and area > min_area:
            best_area = area
            best = fitz.Rect(r)
    doc.close()
    return best


def _fitted_image(image_path, box_w, box_h, rotate_deg=0, fit="cover"):
    """Return a Pillow image pre-rotated and pre-cropped/padded so it can be
    dropped straight into a box of size box_w x box_h with a plain stretch."""
    im = Image.open(image_path).convert("RGB")
    if rotate_deg:
        # expand=True keeps all pixels, changing the canvas size for 90/270
        im = im.rotate(-rotate_deg, expand=True)

    img_w, img_h = im.size
    box_ratio = box_w / box_h
    img_ratio = img_w / img_h

    if fit == "stretch":
        return im.resize((int(box_w), int(box_h)), Image.LANCZOS)

    if fit == "contain":
        scale = min(box_w / img_w, box_h / img_h)
    else:  # cover (default) - fill the box, crop the overflow
        scale = max(box_w / img_w, box_h / img_h)

    new_w, new_h = int(round(img_w * scale)), int(round(img_h * scale))
    im = im.resize((new_w, new_h), Image.LANCZOS)

    if fit == "cover":
        left = (new_w - box_w) / 2
        top = (new_h - box_h) / 2
        im = im.crop((int(left), int(top), int(left + box_w), int(top + box_h)))
    elif fit == "contain":
        canvas = Image.new("RGB", (int(box_w), int(box_h)), "white")
        left = int((box_w - new_w) / 2)
        top = int((box_h - new_h) / 2)
        canvas.paste(im, (left, top))
        im = canvas

    return im


def place_image(pdf_in, pdf_out, box_rect, image_path, rotate_deg=0, fit="cover"):
    """Place image_path into box_rect on page 0 of pdf_in, saving as pdf_out."""
    box_rect = fitz.Rect(box_rect)
    fitted = _fitted_image(image_path, box_rect.width, box_rect.height,
                            rotate_deg=rotate_deg, fit=fit)

    fd, tmp_path = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    try:
        fitted.save(tmp_path, quality=95)
        doc = fitz.open(pdf_in)
        page = doc[0]
        page.insert_image(box_rect, filename=tmp_path)
        doc.save(pdf_out)
        doc.close()
    finally:
        os.remove(tmp_path)
    return pdf_out


def render_preview(pdf_path, png_path, dpi=150, page_number=0):
    doc = fitz.open(pdf_path)
    pix = doc[page_number].get_pixmap(dpi=dpi)
    pix.save(png_path)
    doc.close()
    return png_path


def _cover_crop(im, target_w, target_h):
    w, h = im.size
    scale = max(target_w / w, target_h / h)
    nw, nh = int(round(w * scale)), int(round(h * scale))
    im = im.resize((nw, nh), Image.LANCZOS)
    left = (nw - target_w) / 2
    top = (nh - target_h) / 2
    return im.crop((int(left), int(top), int(left + target_w), int(top + target_h)))


def build_large_envelope_square(src_path, box_w, box_h, scale=2.0):
    """Recompose the wide SLTMOBITEL Connect creative into a square panel:
    family photo on top, title block on bottom, fine print rotated along the
    left edge. Built from known crop coordinates in the 1179x618 source."""
    src = Image.open(src_path).convert("RGB").rotate(180)  # raw file is upside-down

    canvas_w, canvas_h = int(box_w * scale), int(box_h * scale)
    strip_w = int(canvas_w * 0.055)
    main_w = canvas_w - strip_w
    photo_h = int(canvas_h * 0.60)
    title_h = canvas_h - photo_h

    canvas = Image.new("RGB", (canvas_w, canvas_h), (12, 24, 40))

    photo_fit = _cover_crop(src.crop((0, 0, 610, 555)), main_w, photo_h)
    canvas.paste(photo_fit, (strip_w, 0))

    title_src = src.crop((605, 0, 1179, 618))
    tw, th = title_src.size
    fit_scale = (title_h * 0.92) / th
    title_fit = title_src.resize((int(tw * fit_scale), int(th * fit_scale)), Image.LANCZOS)

    bg = Image.new("RGB", (main_w, title_h))
    top_rgb, bottom_rgb = (28, 30, 100), (14, 133, 129)
    for y in range(title_h):
        t = y / max(title_h - 1, 1)
        bg.paste(tuple(int(top_rgb[c] + (bottom_rgb[c] - top_rgb[c]) * t) for c in range(3)),
                 (0, y, main_w, y + 1))
    bg.paste(title_fit, (0, (title_h - title_fit.height) // 2))
    canvas.paste(bg, (strip_w, photo_h))

    seam = canvas.crop((strip_w, photo_h - 18, canvas_w, photo_h + 18)).filter(ImageFilter.GaussianBlur(6))
    canvas.paste(seam, (strip_w, photo_h - 18))

    fine_rot = src.crop((0, 560, 465, 605)).rotate(90, expand=True)
    canvas.paste(_cover_crop(fine_rot, strip_w, canvas_h), (0, 0))

    return canvas


def build_wide_extended(src_path, box_w, box_h, scale=3.0, upright=True):
    """Fit the whole source image to the box height (no cropping) and extend
    the background gradient sideways to fill a much wider/flatter box, so
    no text or badge gets cut off."""
    src = Image.open(src_path).convert("RGB")
    if upright:
        src = src.rotate(180)  # raw file is upside-down

    target_w, target_h = int(box_w * scale), int(box_h * scale)
    fit_scale = target_h / src.height
    new_w, new_h = int(src.width * fit_scale), target_h
    main = src.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGB", (target_w, target_h))
    left_margin = (target_w - new_w) // 2
    right_margin = target_w - new_w - left_margin
    edge_w = max(20, new_w // 40)

    if left_margin > 0:
        strip = main.crop((0, 0, edge_w, new_h)).resize((left_margin, new_h))
        canvas.paste(strip.filter(ImageFilter.GaussianBlur(left_margin * 0.15)), (0, 0))
    if right_margin > 0:
        strip = main.crop((new_w - edge_w, 0, new_w, new_h)).resize((right_margin, new_h))
        canvas.paste(strip.filter(ImageFilter.GaussianBlur(right_margin * 0.15)), (left_margin + new_w, 0))

    canvas.paste(main, (left_margin, 0))
    return canvas


# ---------------------------------------------------------------------------
# Batch mode: running "python place_artwork.py" with no arguments regenerates
# every known output for this project in one go. Add/edit entries here as
# new envelopes or artwork variants come in.
# ---------------------------------------------------------------------------

def _job_medium_envelope():
    pdf_in = "05717-SLT Medium Envelope.pdf"
    box = find_placeholder_box(pdf_in)
    place_image(pdf_in, "05717-SLT Medium Envelope - FINAL.pdf", box,
                "05717-SLT Medium Envelope Image.jpg", rotate_deg=0, fit="cover")


def _job_large_envelope():
    pdf_in = "05717-SLT Large Envelope.pdf"
    box = find_placeholder_box(pdf_in)
    composite = build_large_envelope_square("05717-SLT Medium Envelope Image.jpg",
                                             box.width, box.height)
    tmp = "_tmp_large_composite.jpg"
    composite.save(tmp, quality=95)
    try:
        place_image(pdf_in, "05717-SLT Large Envelope - FINAL.pdf", box, tmp,
                    rotate_deg=0, fit="stretch")
    finally:
        os.remove(tmp)


def _job_selfseal_connect():
    pdf_in = "05717-SLT Self Seal-01.pdf"
    box = find_placeholder_box(pdf_in)
    composite = build_wide_extended("05717-SLT Medium Envelope Image.jpg",
                                     box.width, box.height, upright=True)
    tmp = "_tmp_selfseal_connect.jpg"
    composite.save(tmp, quality=95)
    try:
        place_image(pdf_in, "05717-SLT Self Seal-01 - SLTMOBITEL CONNECT.pdf", box, tmp,
                    rotate_deg=0, fit="stretch")
    finally:
        os.remove(tmp)


def _job_selfseal_databowan():
    pdf_in = "05717-SLT Self Seal-01.pdf"
    box = find_placeholder_box(pdf_in)
    place_image(pdf_in, "05717-SLT Self Seal-01 - DATA BOWAN.pdf", box,
                "A4 Self Envelope-02 (Common for both red & non red).jpg",
                rotate_deg=0, fit="cover")


JOBS = [
    ("Medium Envelope", _job_medium_envelope),
    ("Large Envelope", _job_large_envelope),
    ("Self Seal - SLTMOBITEL Connect", _job_selfseal_connect),
    ("Self Seal - Data Bowan", _job_selfseal_databowan),
]


def _run_all_jobs():
    print(f"No arguments given - regenerating all {len(JOBS)} known outputs.\n")
    for name, job in JOBS:
        try:
            job()
            print(f"[ok]   {name}")
        except FileNotFoundError as e:
            print(f"[skip] {name}: missing file - {e.filename}")
        except Exception as e:
            print(f"[fail] {name}: {e}")


def _main():
    if len(sys.argv) == 1:
        _run_all_jobs()
        return
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf_in")
    ap.add_argument("pdf_out")
    ap.add_argument("image")
    ap.add_argument("--box", type=float, nargs=4, metavar=("X0", "Y0", "X1", "Y1"),
                     help="explicit box coords; auto-detected if omitted")
    ap.add_argument("--rotate", type=float, default=0,
                     help="degrees to rotate the source image before placing")
    ap.add_argument("--fit", choices=["cover", "contain", "stretch"], default="cover")
    ap.add_argument("--preview", metavar="PNG", help="also render a PNG preview")
    args = ap.parse_args()

    box = tuple(args.box) if args.box else find_placeholder_box(args.pdf_in)
    if box is None:
        raise SystemExit("Could not auto-detect a placeholder box; pass --box explicitly.")

    place_image(args.pdf_in, args.pdf_out, box, args.image,
                rotate_deg=args.rotate, fit=args.fit)
    print(f"Wrote {args.pdf_out}  (box used: {box})")

    if args.preview:
        render_preview(args.pdf_out, args.preview)
        print(f"Preview: {args.preview}")


if __name__ == "__main__":
    _main()
