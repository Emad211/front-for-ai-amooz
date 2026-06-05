"""LLM-only PDF → Markdown extraction (Persian-first, production-grade).

Drop-in replacement for ``transcription.transcribe_media_bytes`` at pipeline
step 1: same return contract so every downstream step (structure, prereqs,
recap, exam-prep Q&A, dashboards) runs unchanged.

Strategy (LLM-only, token-optimized):
  * Every non-blank page is transcribed by the multimodal model (one vision
    call per page). The deterministic ``pdfplumber`` text fast-path was removed
    — Persian text layers are too often reordered/glued/cid-broken to trust.
  * Tables come back as exact GitHub-Flavored Markdown from the model.
  * Embedded raster images/figures are extracted DETERMINISTICALLY from the PDF
    (``pypdf``) — no extra LLM tokens — saved to persistent storage, and woven
    into the page Markdown using ``[[IMAGE_k: caption]]`` placement markers the
    model emits. The real bitmap is shown (not an LLM redraw). Full-page scans
    are NOT treated as figures (area-ratio guard).
  * Token savers: a lower default render DPI, and blank pages are detected and
    skipped without any LLM call.
  * Vision calls (the slow, IO-bound part) run with bounded concurrency so one
    large PDF never starves other users. Image extraction stays serial + cheap.
  * Never lose a page: if a vision call fails after retries, the page falls back
    to a warning note plus any extracted images for that page.

Public entry:
    extract_pdf_to_markdown(*, data, mime_type, asset_prefix=None)
        -> (markdown, provider, model, page_count)
"""

from __future__ import annotations

import base64
import io
import logging
import os
import re
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from apps.commons.models import LLMUsageLog
from apps.chatbot.services.llm_client import generate_text
from apps.commons.llm_prompts import PROMPTS

logger = logging.getLogger(__name__)

_LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "600"))

# An embedded image covering more than this fraction of the page area is treated
# as a full-page background/scan (already OCR'd by vision), not a figure to save.
_FULLPAGE_AREA_RATIO = 0.6

# Matches the model's image placement markers: [[IMAGE_1: caption]], [[IMAGE: x]],
# or a bare [[IMAGE]]. The caption (group 1) is optional.
_MARKER_RE = re.compile(
    r"\[\[\s*IMAGE(?:[_\s]*\d+)?\s*(?::\s*([^\]]*?))?\s*\]\]",
    re.IGNORECASE,
)


class PdfExtractionError(RuntimeError):
    """Raised for unrecoverable PDF problems (encrypted, corrupt, empty)."""


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _cfg(name: str, default):
    return getattr(settings, name, default)


def _select_vision_model() -> str:
    return (
        (os.getenv("PDF_VISION_MODEL") or "").strip()
        or (os.getenv("MODEL_NAME") or "").strip()
        or (os.getenv("TRANSCRIPTION_MODEL") or "").strip()
        or "gemini-2.5-flash"
    )


# ---------------------------------------------------------------------------
# Pure helpers retained for reuse / unit-testing (no longer in the hot path)
# ---------------------------------------------------------------------------

def classify_text_quality(
    text: str,
    *,
    min_chars: int,
    force_vision: bool = False,
) -> bool:
    """Return True when a digital TEXT layer looks trustworthy for a page.

    Retained as a pure, unit-tested helper. The LLM-only content path no longer
    routes on it, but it remains useful for diagnostics and blank/quality checks.
    """
    if force_vision:
        return False

    raw = text or ""
    stripped = raw.strip()
    usable = len(stripped.replace(" ", "").replace("\n", ""))
    if usable < min_chars:
        return False
    if "(cid:" in raw:
        return False
    if stripped:
        bad = raw.count("�")
        if bad / max(1, len(stripped)) > 0.01:
            return False
    tokens = stripped.split()
    if tokens:
        mean_len = sum(len(t) for t in tokens) / len(tokens)
        if mean_len > 25:
            return False
    return True


def _cell(value) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).replace("|", "\\|")


def tables_to_markdown(tables) -> str:
    """Convert pdfplumber-style tables (rows of cells) to GFM Markdown.

    Retained as a pure helper for tests/diagnostics.
    """
    blocks = []
    for table in tables or []:
        rows = [r for r in table if r is not None]
        if not rows:
            continue
        width = max(len(r) for r in rows)
        norm = [[_cell(r[i]) if i < len(r) else "" for i in range(width)] for r in rows]
        header = norm[0]
        body = norm[1:]
        lines = ["| " + " | ".join(header) + " |",
                 "| " + " | ".join(["---"] * width) + " |"]
        for r in body:
            lines.append("| " + " | ".join(r) + " |")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


# ---------------------------------------------------------------------------
# Rendering (pypdfium2): one render per page reused for blank-check + vision
# ---------------------------------------------------------------------------

def _encode_png(pil, max_bytes: int) -> bytes:
    """Encode a PIL image to PNG, downscaling until it fits ``max_bytes``."""
    img = pil.convert("RGB")
    for _ in range(5):
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        png = buf.getvalue()
        if len(png) <= max_bytes or min(img.size) <= 320:
            return png
        w, h = img.size
        img = img.resize((max(320, int(w * 0.75)), max(320, int(h * 0.75))))
    return png


def _grayscale_std(pil) -> float:
    from PIL import ImageStat
    try:
        return float(ImageStat.Stat(pil.convert("L")).stddev[0])
    except Exception:
        return 255.0  # treat as non-blank on failure


# ---------------------------------------------------------------------------
# Deterministic embedded-image extraction (no LLM tokens)
# ---------------------------------------------------------------------------

def _extract_page_images(
    reader_page,
    *,
    page_w_px: float,
    page_h_px: float,
    min_px: int,
    min_bytes: int,
    prefix: str,
    page_no: int,
) -> "list[str]":
    """Pull meaningful embedded raster images from a page, save them, return URLs.

    Filters out tiny/decorative images and full-page background scans. Each kept
    image is saved to ``default_storage`` and its public URL returned, in page
    reading order.
    """
    urls: list[str] = []
    try:
        images = list(getattr(reader_page, "images", []) or [])
    except Exception as exc:  # pragma: no cover - depends on PDF internals
        logger.debug("image enumeration failed on page %s: %s", page_no, exc)
        return urls

    page_area = max(1.0, page_w_px * page_h_px)
    idx = 0
    for img_file in images:
        try:
            pil = img_file.image  # PIL.Image (decoded by pypdf)
            if pil is None:
                continue
            w, h = pil.size
            if w < min_px or h < min_px:
                continue  # decorative / icon
            if (w * h) / page_area > _FULLPAGE_AREA_RATIO:
                continue  # full-page scan/background — handled by vision OCR
            buf = io.BytesIO()
            pil.convert("RGB").save(buf, format="PNG", optimize=True)
            png = buf.getvalue()
            if len(png) < min_bytes:
                continue
            key = f"{prefix.rstrip('/')}/p{page_no}_{idx}.png"
            saved = default_storage.save(key, ContentFile(png))
            urls.append(default_storage.url(saved))
            idx += 1
        except Exception as exc:  # never let one bad image break the page
            logger.debug("skipping undecodable image on page %s: %s", page_no, exc)
            continue
    return urls


# ---------------------------------------------------------------------------
# Vision call + marker mapping
# ---------------------------------------------------------------------------

def _vision_extract_page(*, png: bytes, page_no: int, model: str) -> "tuple[str, str, str]":
    """Send one rendered page to the multimodal model. Returns (md, provider, model).

    Uses the standard OpenAI-compatible multimodal shape (a ``content`` list with
    a ``text`` part and an ``image_url`` data-URI part). The Avalai/Gemini gateway
    only actually *sees* the image with this shape — the legacy ``attachments``
    shape is silently ignored (the model hallucinates), so do not use it here.
    """
    prompt = PROMPTS["pdf_extraction"]["default"]
    b64 = base64.b64encode(png).decode()
    res = generate_text(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    },
                ],
            }
        ],
        timeout=_LLM_TIMEOUT_SECONDS,
        feature=LLMUsageLog.Feature.PDF_EXTRACTION,
        detail=f"pdf page {page_no}",
    )
    text = res.text if hasattr(res, "text") else str(res)
    return text.strip(), getattr(res, "provider", "gapgpt"), getattr(res, "model", model)


def _apply_image_markers(page_md: str, urls: "list[str]") -> str:
    """Replace ``[[IMAGE_k: caption]]`` markers with real ``![caption](url)``.

    Maps markers to extracted images by order. Extra markers (model saw more
    figures than we could extract) are dropped; extra images (we extracted more
    than the model marked) are appended at the end so nothing is lost.
    """
    counter = {"i": 0}

    def _repl(m: "re.Match") -> str:
        i = counter["i"]
        counter["i"] += 1
        caption = (m.group(1) or "").strip()
        if i < len(urls):
            return f"![{caption}]({urls[i]})"
        return ""  # dangling marker — no image to back it

    new_md = _MARKER_RE.sub(_repl, page_md)
    used = counter["i"]
    if used < len(urls):
        extras = "\n\n".join(f"![]({u})" for u in urls[used:])
        new_md = (new_md.rstrip() + "\n\n" + extras).strip()
    return new_md


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------

def extract_pdf_to_markdown(
    *,
    data: bytes,
    mime_type: str = "application/pdf",
    asset_prefix: Optional[str] = None,
) -> "tuple[str, str, str, int]":
    """Extract a PDF to Markdown. Returns (markdown, provider, model, page_count).

    ``asset_prefix`` is the storage folder for extracted figure images
    (e.g. ``class_creation/extracted/<session_id>``). When omitted, a unique
    throwaway prefix is used so callers without a session (benchmarks) still work.
    """
    import pypdfium2 as pdfium
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    if not data or b"%PDF" not in data[:1024]:
        raise PdfExtractionError("فایل ارسالی یک PDF معتبر نیست.")

    # --- validate: encryption, corruption, page count ---
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                if reader.decrypt("") == 0:  # 0 = failed
                    raise PdfExtractionError(
                        "این PDF رمزگذاری‌شده است. لطفاً نسخه‌ی بدون رمز را بارگذاری کنید."
                    )
            except PdfExtractionError:
                raise
            except Exception:
                raise PdfExtractionError(
                    "این PDF رمزگذاری‌شده است. لطفاً نسخه‌ی بدون رمز را بارگذاری کنید."
                )
        page_count = len(reader.pages)
    except PdfExtractionError:
        raise
    except (PdfReadError, Exception) as exc:
        raise PdfExtractionError(f"خواندن PDF ناموفق بود: {exc}") from exc

    if page_count == 0:
        raise PdfExtractionError("این PDF هیچ صفحه‌ای ندارد.")

    max_pages = int(_cfg("PDF_MAX_PAGES", 200))
    if page_count > max_pages:
        raise PdfExtractionError(
            f"تعداد صفحات ({page_count}) از حداکثر مجاز ({max_pages}) بیشتر است."
        )

    dpi = int(_cfg("PDF_RENDER_DPI", 150))
    max_img_bytes = int(_cfg("PDF_MAX_IMAGE_BYTES_MB", 3)) * 1024 * 1024
    concurrency = max(1, int(_cfg("PDF_EXTRACTION_CONCURRENCY", 4)))
    skip_blank = bool(_cfg("PDF_SKIP_BLANK_PAGES", True))
    blank_std = float(_cfg("PDF_BLANK_STD_THRESHOLD", 3.0))
    img_min_px = int(_cfg("PDF_IMAGE_MIN_PX", 64))
    img_min_bytes = int(_cfg("PDF_IMAGE_MIN_BYTES", 3000))
    prefix = asset_prefix or f"class_creation/extracted/nosession-{uuid.uuid4().hex}"

    scale = max(0.5, dpi / 72.0)

    # --- pass 1 (serial): render once, detect blanks, extract figure images ---
    page_png: dict[int, bytes] = {}
    images_by_page: dict[int, list[str]] = {}
    is_blank: list[bool] = [False] * page_count

    pdf = pdfium.PdfDocument(data)
    try:
        for i in range(page_count):
            # Embedded figures (deterministic, no tokens).
            try:
                rp = reader.pages[i]
                mb = rp.mediabox
                page_w_px = float(mb.width) / 72.0 * dpi
                page_h_px = float(mb.height) / 72.0 * dpi
            except Exception:
                rp = None
                page_w_px = page_h_px = float(dpi) * 8.0
            if rp is not None:
                images_by_page[i] = _extract_page_images(
                    rp,
                    page_w_px=page_w_px,
                    page_h_px=page_h_px,
                    min_px=img_min_px,
                    min_bytes=img_min_bytes,
                    prefix=prefix,
                    page_no=i + 1,
                )

            # Render the page once (reused for blank-check + vision).
            try:
                pil = pdf[i].render(scale=scale).to_pil()
            except Exception as exc:
                logger.warning("render failed on page %s: %s", i + 1, exc)
                pil = None

            has_images = bool(images_by_page.get(i))
            text_len = 0
            if rp is not None:
                try:
                    text_len = len((rp.extract_text() or "").strip())
                except Exception:
                    text_len = 0

            if (
                skip_blank
                and pil is not None
                and not has_images
                and text_len == 0
                and _grayscale_std(pil) < blank_std
            ):
                is_blank[i] = True
                continue

            if pil is not None:
                page_png[i] = _encode_png(pil, max_img_bytes)
    finally:
        pdf.close()

    # --- pass 2 (bounded parallel): vision for every non-blank page ---
    vision_model = _select_vision_model()
    vision_md: dict[int, str] = {}
    used_provider: Optional[str] = None
    used_model: Optional[str] = None

    def _worker(index: int):
        return _vision_extract_page(png=page_png[index], page_no=index + 1, model=vision_model)

    todo = [i for i in range(page_count) if i in page_png]
    if todo:
        with ThreadPoolExecutor(max_workers=min(concurrency, len(todo))) as pool:
            futures = {pool.submit(_worker, i): i for i in todo}
            for fut in as_completed(futures):
                i = futures[fut]
                try:
                    md, provider, model = fut.result()
                    if not md:
                        raise ValueError("empty vision output")
                    vision_md[i] = _apply_image_markers(md, images_by_page.get(i, []))
                    used_provider = used_provider or provider
                    used_model = used_model or model
                except Exception as exc:
                    logger.warning("PDF vision failed on page %s: %s", i + 1, exc)
                    urls = images_by_page.get(i, [])
                    imgs = "\n\n".join(f"![]({u})" for u in urls)
                    note = "> [هشدار: استخراج این صفحه ناموفق بود.]"
                    vision_md[i] = (imgs + "\n\n" + note).strip() if imgs else note

    # --- assemble in page order ---
    out_pages = []
    for i in range(page_count):
        if is_blank[i]:
            body = ""
        else:
            body = (vision_md.get(i) or "").strip()
        if page_count > 1:
            out_pages.append(f"## صفحه {i + 1}\n\n{body}".rstrip())
        else:
            out_pages.append(body)

    markdown = "\n\n".join(p for p in out_pages).strip()
    if not markdown:
        raise PdfExtractionError("هیچ محتوایی از این PDF استخراج نشد.")

    provider = used_provider or "local"
    model = used_model or vision_model
    return markdown, provider, model, page_count
