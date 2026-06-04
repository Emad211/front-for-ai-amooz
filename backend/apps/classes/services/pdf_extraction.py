"""Hybrid PDF → Markdown extraction (Persian-first, production-grade).

Drop-in replacement for ``transcription.transcribe_media_bytes`` at pipeline
step 1: same return contract so every downstream step (structure, prereqs,
recap, exam-prep Q&A, dashboards) runs unchanged.

Strategy (confirmed design):
  * Per page, a quality gate decides TEXT vs VISION.
  * TEXT path: deterministic ``pdfplumber`` text + tables → Markdown. Fast,
    cheap, exact for clean digital PDFs.
  * VISION path: render the page with ``pypdfium2`` and send the image to the
    multimodal model (Gemini/Avalai) with a Persian-first prompt. Used for
    scanned/image/complex pages and any page whose text layer looks broken —
    which is common for Persian (RTL reordering, glued words, cid glyphs).
  * Vision calls (the slow, IO-bound part) run with bounded concurrency so one
    large PDF never starves other users. Text/table extraction stays serial
    and cheap.
  * Never lose a page: if vision fails after retries, fall back to that page's
    text layer and flag it.

Public entry:
    extract_pdf_to_markdown(*, data, mime_type) -> (markdown, provider, model, page_count)
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
# Quality gate (pure, unit-testable)
# ---------------------------------------------------------------------------

def classify_text_quality(
    text: str,
    *,
    min_chars: int,
    force_vision: bool = False,
) -> bool:
    """Return True when the digital TEXT layer is trustworthy for this page.

    False → route the page through the VISION model. Conservative toward
    accuracy: Persian text layers frequently come out reordered/glued/with
    ``(cid:NN)`` glyphs, so any such signal forces vision.
    """
    if force_vision:
        return False

    raw = text or ""
    stripped = raw.strip()
    usable = len(stripped.replace(" ", "").replace("\n", ""))
    if usable < min_chars:
        return False  # likely scanned / image-only page

    # Unmapped font glyphs — pdfminer emits "(cid:NN)" tokens.
    if "(cid:" in raw:
        return False

    # Unicode replacement char ratio (mojibake / undecodable glyphs).
    if stripped:
        bad = raw.count("�")
        if bad / max(1, len(stripped)) > 0.01:
            return False

    # Glued text: Persian extraction often drops spaces, producing very long
    # "words". If the mean token length is implausible, trust vision instead.
    tokens = stripped.split()
    if tokens:
        mean_len = sum(len(t) for t in tokens) / len(tokens)
        if mean_len > 25:
            return False

    return True


# ---------------------------------------------------------------------------
# Tables → Markdown
# ---------------------------------------------------------------------------

def _cell(value) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).replace("|", "\\|")


def tables_to_markdown(tables) -> str:
    """Convert pdfplumber tables (list of rows of cells) to GFM Markdown."""
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
# Vision rendering + call
# ---------------------------------------------------------------------------

def _render_page_png(data: bytes, index: int, dpi: int, max_bytes: int) -> bytes:
    """Render one PDF page to PNG bytes, downscaling to honour ``max_bytes``."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(data)
    try:
        page = pdf[index]
        scale = max(0.5, dpi / 72.0)
        for _ in range(5):
            bitmap = page.render(scale=scale)
            pil = bitmap.to_pil()
            buf = io.BytesIO()
            pil.convert("RGB").save(buf, format="PNG", optimize=True)
            png = buf.getvalue()
            if len(png) <= max_bytes or scale <= 0.5:
                return png
            scale *= 0.75  # too big — render smaller and retry
        return png
    finally:
        pdf.close()


def _vision_extract_page(*, png: bytes, page_no: int, model: str) -> "tuple[str, str, str]":
    """Send one rendered page to the multimodal model. Returns (md, provider, model)."""
    prompt = PROMPTS["pdf_extraction"]["default"]
    b64 = base64.b64encode(png).decode()
    res = generate_text(
        model=model,
        messages=[
            {
                "role": "user",
                "content": prompt,
                "attachments": [
                    {
                        "type": "input_media",
                        "mime_type": "image/png",
                        "data_base64": b64,
                    }
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
# Page text/table extraction (serial, cheap)
# ---------------------------------------------------------------------------

def _build_text_markdown(page_text: str, tables_md: str) -> str:
    parts = []
    if (page_text or "").strip():
        parts.append(page_text.strip())
    if tables_md.strip():
        parts.append(tables_md.strip())
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------

def extract_pdf_to_markdown(*, data: bytes, mime_type: str = "application/pdf") -> "tuple[str, str, str, int]":
    """Extract a PDF to Markdown. Returns (markdown, provider, model, page_count).

    Mirrors ``transcribe_media_bytes`` so step 1 can dispatch by source type
    with zero downstream change.
    """
    import pdfplumber
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    if not data or b"%PDF" not in data[:1024]:
        raise PdfExtractionError("فایل ارسالی یک PDF معتبر نیست.")

    # --- validate: encryption, corruption, page count ---
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            # Try empty-password decrypt; if it fails, give a clear error.
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

    min_chars = int(_cfg("PDF_TEXT_LAYER_MIN_CHARS", 80))
    force_vision = bool(_cfg("PDF_FORCE_VISION", False))
    dpi = int(_cfg("PDF_RENDER_DPI", 170))
    max_img_bytes = int(_cfg("PDF_MAX_IMAGE_BYTES_MB", 3)) * 1024 * 1024
    concurrency = max(1, int(_cfg("PDF_EXTRACTION_CONCURRENCY", 4)))

    # --- pass 1 (serial): per-page text + tables + routing decision ---
    page_text_md: list[str] = [""] * page_count
    vision_pages: list[int] = []
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for i, page in enumerate(pdf.pages):
                try:
                    txt = page.extract_text() or ""
                except Exception:
                    txt = ""
                try:
                    tables = page.extract_tables() or []
                except Exception:
                    tables = []
                page_text_md[i] = _build_text_markdown(txt, tables_to_markdown(tables))
                if not classify_text_quality(txt, min_chars=min_chars, force_vision=force_vision):
                    vision_pages.append(i)
    except Exception as exc:
        raise PdfExtractionError(f"تحلیل ساختار PDF ناموفق بود: {exc}") from exc

    # --- pass 2 (bounded parallel): vision for flagged pages ---
    vision_model = _select_vision_model()
    vision_md: dict[int, str] = {}
    used_provider: Optional[str] = None
    used_model: Optional[str] = None

    def _worker(index: int):
        png = _render_page_png(data, index, dpi, max_img_bytes)
        return _vision_extract_page(png=png, page_no=index + 1, model=vision_model)

    if vision_pages:
        with ThreadPoolExecutor(max_workers=min(concurrency, len(vision_pages))) as pool:
            futures = {pool.submit(_worker, i): i for i in vision_pages}
            for fut in as_completed(futures):
                i = futures[fut]
                try:
                    md, provider, model = fut.result()
                    if md:
                        vision_md[i] = md
                        used_provider = used_provider or provider
                        used_model = used_model or model
                    else:
                        raise ValueError("empty vision output")
                except Exception as exc:
                    # Never drop a page — fall back to its text layer.
                    logger.warning("PDF vision failed on page %s: %s", i + 1, exc)
                    fallback = page_text_md[i].strip()
                    vision_md[i] = (
                        (fallback + "\n\n" if fallback else "")
                        + "> [هشدار: استخراج تصویری این صفحه ناموفق بود؛ متن خام نمایش داده شد.]"
                    )

    # --- assemble in page order ---
    out_pages = []
    for i in range(page_count):
        body = vision_md.get(i) if i in vision_md else page_text_md[i]
        body = (body or "").strip()
        if page_count > 1:
            out_pages.append(f"## صفحه {i + 1}\n\n{body}".rstrip())
        else:
            out_pages.append(body)

    markdown = "\n\n".join(p for p in out_pages).strip()
    if not markdown:
        raise PdfExtractionError("هیچ محتوایی از این PDF استخراج نشد.")

    provider = used_provider or "local"
    model = used_model or "pdfplumber"
    return markdown, provider, model, page_count
