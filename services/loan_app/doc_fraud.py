"""
LoanFlow – Document fraud scoring ("DocGuard").

A feature-based anomaly model that scores every uploaded document for signs of
tampering or misuse. It is advisory only: the officer sees the score and the
findings next to the document and makes the final verify/reject decision.

Signals (each contributes a weight; the weighted sum is squashed to 0..1):
  * content type does not match the file extension (magic-byte check)
  * identical file already uploaded on another application
  * image edited with a known editing tool (EXIF Software tag)
  * error-level analysis (ELA): re-compression residue that differs sharply
    across the image, typical of spliced or retouched regions
  * very low resolution / suspiciously tiny or empty files
  * PDF produced by an image editor or online generator
"""
from __future__ import annotations

import io
import math
import re

try:  # Pillow is optional at import time so the service still starts without it
    from PIL import Image, ImageChops
    _HAS_PIL = True
except Exception:  # pragma: no cover
    _HAS_PIL = False

MODEL_NAME = "DocGuard v1 (feature-based anomaly model)"

EDITOR_TAGS = ("photoshop", "gimp", "canva", "pixlr", "paint.net", "snapseed", "picsart", "lightroom", "affinity")
PDF_EDITOR_TAGS = ("photoshop", "canva", "illustrator", "gimp", "pixlr", "wps", "ilovepdf", "smallpdf", "sejda")

SUSPICIOUS_AT = 0.35
HIGH_RISK_AT = 0.65


def _sniff(data: bytes) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if data[:5] == b"%PDF-":
        return "pdf"
    if data[:4] in (b"GIF8",):
        return "gif"
    if data[:2] == b"BM":
        return "bmp"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return "unknown"


_EXT_KIND = {
    "png": "png", "jpg": "jpeg", "jpeg": "jpeg", "pdf": "pdf",
    "gif": "gif", "bmp": "bmp", "webp": "webp",
}


def _ela_stats(img: "Image.Image") -> tuple[float, float]:
    """Return (mean, spread) of the error-level residue after a JPEG re-save."""
    rgb = img.convert("RGB")
    if max(rgb.size) > 1024:
        rgb.thumbnail((1024, 1024))
    buf = io.BytesIO()
    rgb.save(buf, "JPEG", quality=90)
    buf.seek(0)
    resaved = Image.open(buf).convert("RGB")
    diff = ImageChops.difference(rgb, resaved).convert("L")
    hist = diff.histogram()
    total = sum(hist) or 1
    mean = sum(i * c for i, c in enumerate(hist)) / total
    var = sum(((i - mean) ** 2) * c for i, c in enumerate(hist)) / total
    return mean, math.sqrt(var)


def analyze_document(
    data: bytes,
    file_name: str,
    mime_type: str,
    duplicate_count: int = 0,
) -> dict:
    """Score a document. Returns {score, flag, findings, model}."""
    findings: list[str] = []
    z = -2.2  # logistic bias: an unremarkable document scores low

    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    kind = _sniff(data)

    if len(data) == 0:
        findings.append("File is empty")
        z += 4.0
    elif len(data) < 2048:
        findings.append(f"File is unusually small ({len(data)} bytes)")
        z += 1.2

    expected = _EXT_KIND.get(ext)
    if expected and kind != "unknown" and expected != kind:
        findings.append(f"Content is {kind.upper()} but the file extension says .{ext}")
        z += 2.0
    elif kind == "unknown":
        findings.append("Unrecognised file format")
        z += 1.0

    if duplicate_count > 0:
        findings.append(f"Identical file already uploaded on {duplicate_count} other application(s)")
        z += 2.5

    if kind in ("png", "jpeg", "gif", "bmp", "webp") and _HAS_PIL:
        try:
            img = Image.open(io.BytesIO(data))
            w, h = img.size
            if min(w, h) < 300:
                findings.append(f"Low resolution image ({w}x{h}px)")
                z += 1.0

            software = ""
            try:
                exif = img.getexif()
                software = str(exif.get(305, "") or "")  # 305 = Software
            except Exception:
                pass
            software = (software + " " + str(img.info.get("Software", ""))).lower()
            hit = next((t for t in EDITOR_TAGS if t in software), None)
            if hit:
                findings.append(f"Image metadata shows it was edited with {hit.title()}")
                z += 1.8

            mean, spread = _ela_stats(img)
            if spread > 9.0 and kind == "jpeg":
                findings.append(
                    f"Error-level analysis shows uneven compression (spread {spread:.1f}), a sign of edited regions"
                )
                z += 1.6
            elif mean > 6.0 and kind == "jpeg":
                findings.append(f"High re-compression residue (mean {mean:.1f}); image may have been re-saved after edits")
                z += 0.8
        except Exception:
            findings.append("Image could not be decoded cleanly")
            z += 1.5
    elif kind == "pdf":
        head = data[:200000].lower()
        producer = re.search(rb"/producer\s*\((.*?)\)", head, re.S) or re.search(rb"/creator\s*\((.*?)\)", head, re.S)
        tag = producer.group(1).decode("latin-1", "ignore").lower() if producer else ""
        hit = next((t for t in PDF_EDITOR_TAGS if t in tag), None)
        if hit:
            findings.append(f"PDF was produced by {hit.title()}, which is not a typical issuer of official documents")
            z += 1.4
        if b"/javascript" in head or b"/js" in head or b"/launch" in head:
            findings.append("PDF contains active content (JavaScript/launch action)")
            z += 2.0

    score = round(1.0 / (1.0 + math.exp(-z)), 2)
    if score >= HIGH_RISK_AT:
        flag = "HIGH_RISK"
    elif score >= SUSPICIOUS_AT:
        flag = "SUSPICIOUS"
    else:
        flag = "CLEAN"
    if not findings:
        findings.append("No anomalies detected")
    return {"score": score, "flag": flag, "findings": findings, "model": MODEL_NAME}
