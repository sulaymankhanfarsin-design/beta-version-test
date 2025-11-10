import os
import io
import zipfile
import uuid
import tempfile
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from flask import Flask, render_template, request, send_file, redirect, url_for, flash
from werkzeug.utils import secure_filename

# -------------------------
# Config
# -------------------------
BASE_DIR = Path(__file__).resolve().parent
UPLOAD = BASE_DIR / "uploads"
PROCESSED = BASE_DIR / "processed"
UPLOAD.mkdir(exist_ok=True)
PROCESSED.mkdir(exist_ok=True)

ALLOWED_EXT = {"png", "jpg", "jpeg", "webp", "bmp", "gif"}
FORMAT_MAP = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp", "PDF": "pdf"}

app = Flask(__name__)
app.secret_key = "supersecret-change-me"


# -------------------------
# Helpers
# -------------------------
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def _safe_font(size=24):
    for name in ("arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def add_text_watermark(img: Image.Image, text: str, position: str, opacity: float, fontsize: int):
    if not text:
        return img
    base = img.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    font = _safe_font(fontsize)
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        textwidth = bbox[2] - bbox[0]
        textheight = bbox[3] - bbox[1]
    except Exception:
        textwidth, textheight = draw.textsize(text, font=font)

    margin = max(10, int(min(base.size) * 0.02))
    positions = {
        "bottom-right": (base.width - textwidth - margin, base.height - textheight - margin),
        "bottom-left": (margin, base.height - textheight - margin),
        "top-left": (margin, margin),
        "top-right": (base.width - textwidth - margin, margin),
        "center": ((base.width - textwidth) // 2, (base.height - textheight) // 2),
    }
    x, y = positions.get(position, positions["bottom-right"])
    fill = (255, 255, 255, int(255 * float(opacity)))
    draw.text((x, y), text, font=font, fill=fill)
    combined = Image.alpha_composite(base, overlay)
    return combined.convert("RGB")


def add_image_watermark(img: Image.Image, wm_path: str, position: str, opacity: float, scale: float):
    if not wm_path or not os.path.exists(wm_path):
        return img
    try:
        wm = Image.open(wm_path).convert("RGBA")
    except Exception as e:
        raise RuntimeError(f"Watermark image load failed: {e}")

    base = img.convert("RGBA")
    # scale watermark relative to base width
    target_w = max(1, int(base.width * float(scale)))
    ratio = target_w / wm.width
    target_h = int(wm.height * ratio)
    wm_resized = wm.resize((target_w, target_h), Image.LANCZOS)

    if float(opacity) < 1.0:
        alpha = wm_resized.split()[3]
        alpha = ImageEnhance.Brightness(alpha).enhance(float(opacity))
        wm_resized.putalpha(alpha)

    margin = max(10, int(min(base.size) * 0.02))
    pos_map = {
        "bottom-right": (base.width - wm_resized.width - margin, base.height - wm_resized.height - margin),
        "bottom-left": (margin, base.height - wm_resized.height - margin),
        "top-left": (margin, margin),
        "top-right": (base.width - wm_resized.width - margin, margin),
        "center": ((base.width - wm_resized.width) // 2, (base.height - wm_resized.height) // 2),
    }
    pos = pos_map.get(position, pos_map["bottom-right"])

    layer = Image.new("RGBA", base.size, (255, 255, 255, 0))
    layer.paste(wm_resized, pos, wm_resized)
    combined = Image.alpha_composite(base, layer)
    return combined.convert("RGB")


def make_pdf_from_images(pil_image_paths, out_pdf_path):
    """
    Create a PDF (A4 pages) from a list of image file paths.
    Each image is scaled to fit the A4 page while preserving aspect ratio.
    """
    c = canvas.Canvas(str(out_pdf_path), pagesize=A4)
    page_w, page_h = A4  # in points (1pt = 1/72 inch)

    for img_path in pil_image_paths:
        try:
            with Image.open(img_path) as im:
                im = im.convert("RGB")
                # compute fit size (preserve aspect ratio)
                img_w_px, img_h_px = im.size
                # ReportLab draw units are points; assume 72 dpi for sizing relative proportionally
                # We'll fit by scale ratio between image pixel dims and page points while preserving aspect.
                ratio = min(page_w / img_w_px, page_h / img_h_px)
                draw_w = img_w_px * ratio
                draw_h = img_h_px * ratio

                # center
                x = (page_w - draw_w) / 2
                y = (page_h - draw_h) / 2

                # use ImageReader on BytesIO
                b = io.BytesIO()
                im.save(b, format="PNG")
                b.seek(0)
                ir = ImageReader(b)
                c.drawImage(ir, x, y, width=draw_w, height=draw_h, preserveAspectRatio=True, anchor='c')
                c.showPage()
        except Exception as e:
            print("make_pdf_from_images: failed to add", img_path, e)
            continue

    c.save()


# -------------------------
# Routes
# -------------------------
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/process", methods=["POST"])
def process():
    files = request.files.getlist("images")
    if not files or len(files) == 0:
        flash("Please select at least one image.", "error")
        return redirect(url_for("index"))

    # form inputs
    try:
        resize_w = int(request.form.get("width") or 0)
    except ValueError:
        resize_w = 0
    try:
        resize_h = int(request.form.get("height") or 0)
    except ValueError:
        resize_h = 0

    keep_aspect = request.form.get("keep_aspect") == "on"
    watermark_text = (request.form.get("watermark_text") or "").strip()
    wm_position = request.form.get("wm_position") or "bottom-right"
    try:
        text_opacity = float(request.form.get("text_opacity") or 0.5)
    except Exception:
        text_opacity = 0.5
    try:
        img_opacity = float(request.form.get("img_opacity") or 0.5)
    except Exception:
        img_opacity = 0.5
    try:
        text_size = int(request.form.get("text_size") or 24)
    except Exception:
        text_size = 24
    try:
        image_scale = float(request.form.get("image_scale") or 0.2)
    except Exception:
        image_scale = 0.2

    output_format = (request.form.get("output_format") or "JPEG").upper()
    if output_format not in FORMAT_MAP:
        output_format = "JPEG"
    try:
        quality = int(request.form.get("quality") or 90)
        quality = max(1, min(100, quality))
    except Exception:
        quality = 90

    # optional watermark image
    wm_file = request.files.get("watermark_image")
    wm_path = None
    if wm_file and wm_file.filename:
        wm_name = secure_filename(wm_file.filename)
        wm_path = UPLOAD / f"wm_{datetime.utcnow().timestamp()}_{uuid.uuid4().hex}_{wm_name}"
        try:
            wm_file.save(wm_path)
        except Exception as e:
            print("Watermark save failed:", e)
            wm_path = None

    processed_paths = []
    errors = []

    # Save uploads first
    for f in files:
        if not f or not f.filename:
            continue
        if not allowed_file(f.filename):
            errors.append(f"{f.filename}: unsupported type")
            continue
        safe = secure_filename(f.filename)
        in_path = UPLOAD / f"{datetime.utcnow().timestamp()}_{uuid.uuid4().hex}_{safe}"
        try:
            f.save(in_path)
        except Exception as e:
            errors.append(f"{f.filename}: save failed ({e})")
            continue

        # process
        try:
            with Image.open(in_path) as im:
                im = im.convert("RGBA")
                # resizing
                if resize_w or resize_h:
                    if keep_aspect:
                        target = (resize_w or im.width, resize_h or im.height)
                        im.thumbnail(target, Image.LANCZOS)
                    else:
                        new_w = resize_w or im.width
                        new_h = resize_h or im.height
                        im = im.resize((new_w, new_h), Image.LANCZOS)

                # image watermark first
                if wm_path:
                    try:
                        im = add_image_watermark(im, str(wm_path), wm_position, img_opacity, image_scale)
                    except Exception as e:
                        errors.append(f"{safe}: watermark image failed ({e})")

                # text watermark
                if watermark_text:
                    im = add_text_watermark(im, watermark_text, wm_position, text_opacity, text_size)

                # output save
                if output_format == "PDF":
                    # save intermediary JPEG/PNG images in processed folder for PDF collate
                    out_temp = PROCESSED / f"{uuid.uuid4().hex}_pdfimg.png"
                    im.convert("RGB").save(out_temp, "PNG", quality=quality)
                    processed_paths.append(out_temp)
                else:
                    ext = FORMAT_MAP.get(output_format, "jpg")
                    out_file = PROCESSED / f"{uuid.uuid4().hex}_out.{ext}"
                    if output_format in ("JPEG", "JPG"):
                        im.convert("RGB").save(out_file, "JPEG", quality=quality)
                    else:
                        im.save(out_file, output_format)
                    processed_paths.append(out_file)
        except Exception as e:
            errors.append(f"{safe}: processing failed ({e})")

    if not processed_paths:
        flash("No images were processed. " + ("; ".join(errors[:5]) if errors else ""), "error")
        # cleanup uploaded and watermark
        for p in UPLOAD.glob("*"):
            try: p.unlink()
            except: pass
        if wm_path and wm_path.exists():
            try: wm_path.unlink()
            except: pass
        return redirect(url_for("index"))

    # If PDF requested: build PDF from processed images
    if output_format == "PDF":
        pdf_file = PROCESSED / f"batch_{uuid.uuid4().hex}.pdf"
        try:
            make_pdf_from_images(processed_paths, pdf_file)
        except Exception as e:
            flash(f"PDF generation failed: {e}", "error")
            print("PDF generation exception:", e)
            # cleanup
            for p in processed_paths:
                try: p.unlink()
                except: pass
            if wm_path and wm_path.exists():
                try: wm_path.unlink()
                except: pass
            for p in UPLOAD.glob("*"):
                try: p.unlink()
                except: pass
            return redirect(url_for("index"))

        # cleanup intermediate image files
        for p in processed_paths:
            try: p.unlink()
            except: pass

        # remove saved uploads and watermark
        for p in UPLOAD.glob("*"):
            try: p.unlink()
            except: pass
        if wm_path and wm_path.exists():
            try: wm_path.unlink()
            except: pass

        # Serve PDF
        return send_file(str(pdf_file), as_attachment=True, download_name=pdf_file.name, mimetype="application/pdf")

    # else: create ZIP of images
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in processed_paths:
            try:
                zf.write(p, arcname=p.name)
            except Exception as e:
                print("zip write failed for", p, e)
    memory.seek(0)

    # cleanup files
    for p in processed_paths:
        try: p.unlink()
        except: pass
    for p in UPLOAD.glob("*"):
        try: p.unlink()
        except: pass
    if wm_path and wm_path.exists():
        try: wm_path.unlink()
        except: pass

    return send_file(memory, as_attachment=True, download_name=f"mygizmo_images_{uuid.uuid4().hex}.zip", mimetype="application/zip")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
