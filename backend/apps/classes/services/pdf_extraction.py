"""LLM-only, TEXT-ONLY PDF → Markdown extraction (Persian-first).

Drop-in replacement for ``transcription.transcribe_media_bytes`` at pipeline
step 1: same return contract so every downstream step (structure, prereqs,
recap, exam-prep Q&A, dashboards) runs unchanged.

Strategy:
  * Every non-blank page is transcribed by the multimodal model (one vision
    call per page). No deterministic text fast-path (Persian text layers are too
    often reordered/glued/cid-broken to trust).
  * Tables come back as exact GitHub-Flavored Markdown from the model.
  * Figures/charts/diagrams are NOT extracted as files. The model interprets
    each figure inline as TEXT (``> [تصویر: ...]``) and pulls its data into the
    transcript. The whole PDF becomes plain text — nothing but text is produced,
    which keeps the transcript compact for the downstream structure step.
  * Token savers: a lower default render DPI, and blank pages are skipped with no
    LLM call.
  * Vision calls run with bounded concurrency so one large PDF never starves
    other users. Pages are assembled back in order.
  * Never lose a page: if a vision call fails after retries, the page falls back
    to a short warning note.

Public entry:
    extract_pdf_to_markdown(*, data, mime_type, asset_prefix=None)
        -> (markdown, provider, model, page_count)
``asset_prefix`` is accepted for backward compatibility and ignored (no assets
are saved anymore).
"""

from __future__ import annotations

import base64
import io
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from django.conf import settings

from apps.commons.models import LLMUsageLog
from apps.chatbot.services.llm_client import generate_text
from apps.commons.llm_prompts import PROMPTS

logger = logging.getLogger(__name__)

_LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "600"))


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
# Pure helpers retained for reuse / unit-testing
# ---------------------------------------------------------------------------

def classify_text_quality(text: str, *, min_chars: int, force_vision: bool = False) -> bool:
    """Return True when a digital TEXT layer looks trustworthy for a page.

    Retained as a pure, unit-tested helper / diagnostic. The content path is
    LLM-only and does not route on it.
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
    """Convert pdfplumber-style tables (rows of cells) to GFM Markdown (helper)."""
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
# Rendering + blank detection
# ---------------------------------------------------------------------------

def _encode_png(pil, max_bytes: int) -> bytes:
    """Encode a PIL image to PNG, downscaling until it fits ``max_bytes``."""
    img = pil.convert("RGB")
    png = b""
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
# Vision call (text only)
# ---------------------------------------------------------------------------

def _vision_extract_page(*, png: bytes, page_no: int, model: str) -> "tuple[str, str, str]":
    """Send one rendered page to the multimodal model. Returns (md, provider, model).

    Uses the standard OpenAI-compatible multimodal shape (a ``content`` list with
    a ``text`` part and an ``image_url`` data-URI part). The legacy ``attachments``
    shape is silently ignored by the gateway, so do not use it here.
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
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ],
            }
        ],
        timeout=_LLM_TIMEOUT_SECONDS,
        feature=LLMUsageLog.Feature.PDF_EXTRACTION,
        detail=f"pdf page {page_no}",
    )
    text = res.text if hasattr(res, "text") else str(res)
    return text.strip(), getattr(res, "provider", "gapgpt"), getattr(res, "model", model)


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------

def extract_pdf_to_markdown(
    *,
    data: bytes,
    mime_type: str = "application/pdf",
    asset_prefix: Optional[str] = None,  # accepted for back-compat; ignored
) -> "tuple[str, str, str, int]":
    """Extract a PDF to plain-text Markdown. Returns (markdown, provider, model, page_count)."""
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
                if reader.decrypt("") == 0:
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
    scale = max(0.5, dpi / 72.0)

    # --- pass 1 (serial): render once, detect & skip blank pages ---
    page_png: dict[int, bytes] = {}
    is_blank: list[bool] = [False] * page_count

    pdf = pdfium.PdfDocument(data)
    try:
        for i in range(page_count):
            try:
                pil = pdf[i].render(scale=scale).to_pil()
            except Exception as exc:
                logger.warning("render failed on page %s: %s", i + 1, exc)
                pil = None

            text_len = 0
            try:
                text_len = len((reader.pages[i].extract_text() or "").strip())
            except Exception:
                text_len = 0

            if skip_blank and pil is not None and text_len == 0 and _grayscale_std(pil) < blank_std:
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
                    vision_md[i] = md
                    used_provider = used_provider or provider
                    used_model = used_model or model
                except Exception as exc:
                    logger.warning("PDF vision failed on page %s: %s", i + 1, exc)
                    vision_md[i] = "> [هشدار: استخراج این صفحه ناموفق بود.]"

    # --- assemble in page order ---
    out_pages = []
    for i in range(page_count):
        body = "" if is_blank[i] else (vision_md.get(i) or "").strip()
        if page_count > 1:
            out_pages.append(f"## صفحه {i + 1}\n\n{body}".rstrip())
        else:
            out_pages.append(body)

    markdown = "\n\n".join(out_pages).strip()
    if not markdown:
        raise PdfExtractionError("هیچ محتوایی از این PDF استخراج نشد.")

    provider = used_provider or "local"
    model = used_model or vision_model

    # --- debug instrumentation ---
    per_page_len = {i + 1: len(vision_md.get(i, "")) for i in range(page_count) if not is_blank[i]}
    logger.info(
        "PDF extract done: pages=%d non_blank=%d total_chars=%d provider=%s model=%s per_page=%s",
        page_count, len(todo), len(markdown), provider, model, per_page_len,
    )
    logger.info("PDF transcript HEAD=%r", markdown[:1500])
    return markdown, provider, model, page_count
