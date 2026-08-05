"""Conservative Persian/Arabic text quality helpers for exam extraction.

The goal is not to transliterate or guess broken text. Native PDF text that is
stored in visual order or Presentation Forms is excluded from model evidence so
it cannot poison a good vision read. Model output with the same defect remains
visible but is marked critical and routed to a targeted repair pass.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

from .exam_prep_utils import clean_exam_markdown


_PRESENTATION_FORM_RE = re.compile(r"[\uFB50-\uFDFF\uFE70-\uFEFF]")
_ARABIC_LETTER_RE = re.compile(r"[\u0600-\u06FF]")
_VISUAL_ORDER_TOKEN_RE = re.compile(
    r"(?:^|\s)(?:تسا|دشاب(?:یم)?|دوش(?:یم)?|دناوت(?:یم)?|دناه(?:یم)?|"
    r"تسردان|حیحص|هنیزگ|لاوس|خساپ)(?:\s|$)",
    flags=re.IGNORECASE,
)
_LEADING_RTL_PUNCTUATION_RE = re.compile(r"^\s*[؟?!؛،:.]\s*[\u0600-\u06FF]")
_DUPLICATE_MIXED_TEXT_RE = re.compile(
    r"(?P<clean>[\u0600-\u06FF][^\n]{18,})\n+[^\n]*[\uFB50-\uFDFF\uFE70-\uFEFF]",
    flags=re.MULTILINE,
)


def normalize_unicode_text(value: Any) -> str:
    """Apply compatibility normalization without attempting bidi repair."""

    return unicodedata.normalize("NFKC", str(value or ""))


def contains_presentation_forms(value: Any) -> bool:
    return _PRESENTATION_FORM_RE.search(str(value or "")) is not None


def looks_like_visual_order_persian(value: Any) -> bool:
    """Detect common visual-order Persian output without broad guesswork."""

    text = normalize_unicode_text(value)
    if not text or _ARABIC_LETTER_RE.search(text) is None:
        return False
    if _LEADING_RTL_PUNCTUATION_RE.search(text):
        return True
    tokens = _VISUAL_ORDER_TOKEN_RE.findall(" ".join(text.split()))
    return len(tokens) >= 2


def has_broken_persian_text(value: Any) -> bool:
    return contains_presentation_forms(value) or looks_like_visual_order_persian(value)


def has_duplicate_clean_and_broken_text(value: Any) -> bool:
    text = str(value or "")
    return _DUPLICATE_MIXED_TEXT_RE.search(text) is not None


def native_text_for_model(value: Any, *, max_chars: int = 30_000) -> str:
    """Return trustworthy native evidence or an empty string.

    Presentation Forms and visual-order text are deliberately rejected. The
    page image remains available to the model, which is safer than copying a
    poisoned PDF text layer into otherwise good Persian output.
    """

    raw = str(value or "")
    if not raw:
        return ""
    if contains_presentation_forms(raw) or looks_like_visual_order_persian(raw):
        return ""
    normalized = clean_exam_markdown(normalize_unicode_text(raw))
    return normalized[: max(1, int(max_chars))]


def context_tail(value: Any, *, max_chars: int = 1_500) -> str:
    text = native_text_for_model(value, max_chars=max_chars * 2)
    return text[-max_chars:] if text else ""


def context_head(value: Any, *, max_chars: int = 1_500) -> str:
    text = native_text_for_model(value, max_chars=max_chars * 2)
    return text[:max_chars] if text else ""
