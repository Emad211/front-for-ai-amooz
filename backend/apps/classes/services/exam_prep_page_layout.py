"""Deterministic page-content and column-layout routing for exam PDFs.

The classifier is deliberately conservative: it only skips a page when local
PDF/image evidence strongly says that it is a cover, separator, instructions,
or blank page. Ambiguous pages still go to the multimodal extractor.
"""
from __future__ import annotations

from dataclasses import dataclass
import io
import re
from typing import Literal

from PIL import Image

from .exam_prep_utils import clean_exam_markdown


PageContentClass = Literal["non_content", "content"]
PageLayout = Literal["none", "single", "double", "uncertain"]

_NUMBER = r"[0-9۰-۹٠-٩]{1,3}"
_CONTENT_MARKER_RE = re.compile(
    rf"(?:^|\n)\s*(?:س[ؤو]ال\s*)?{_NUMBER}\s*[)\].:：\-–—]"
    rf"|(?:^|\n)\s*(?:پاسخ|راه\s*حل|گزین(?:ه\u0654?|ۀ))\s*(?:س[ؤو]ال\s*)?{_NUMBER}",
    flags=re.IGNORECASE,
)
_OPTION_MARKER_RE = re.compile(
    r"(?:^|\n)\s*[1-6۱-۶١-٦الفبجده]\s*[)\].:：\-–—]",
    flags=re.IGNORECASE,
)
_COVER_HINT_RE = re.compile(
    r"(?:دفترچه|آزمون|پاسخنامه|پاسخ\s*نامه|نام\s*و\s*نام\s*خانوادگی|"
    r"شماره\s*داوطلب|رشته|پایه|مدت\s*پاسخگویی|تعداد\s*سوال|کانون|قلم\s*چی|"
    r"راهنما|دستورالعمل|فهرست)",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class PageLayoutDecision:
    content_class: PageContentClass
    layout: PageLayout
    confidence: float
    reasons: tuple[str, ...]
    ink_ratio: float = 0.0
    center_whitespace_ratio: float = 0.0

    @property
    def skipped_non_content(self) -> bool:
        return self.content_class == "non_content"


def _image_metrics(image_bytes: bytes) -> tuple[float, float, float, float]:
    """Return ink ratio, center whiteness, right ink, and left ink."""

    try:
        with Image.open(io.BytesIO(image_bytes)) as source:
            gray = source.convert("L")
    except Exception:
        return 0.0, 0.0, 0.0, 0.0
    try:
        # Small deterministic thumbnail keeps classification cheap.
        width = 480
        height = max(320, int(gray.height * width / max(1, gray.width)))
        sample = gray.resize((width, height), Image.Resampling.BILINEAR)
        try:
            pixels = list(sample.getdata())
            threshold = 215
            ink = sum(value < threshold for value in pixels)
            ink_ratio = ink / max(1, len(pixels))

            center_start = int(width * 0.46)
            center_end = int(width * 0.54)
            right_start = int(width * 0.55)
            left_end = int(width * 0.45)

            def region_ink(x0: int, x1: int) -> float:
                crop = sample.crop((x0, 0, x1, height))
                try:
                    values = list(crop.getdata())
                    return sum(value < threshold for value in values) / max(1, len(values))
                finally:
                    crop.close()

            center_ink = region_ink(center_start, center_end)
            center_whitespace = 1.0 - center_ink
            right_ink = region_ink(right_start, width)
            left_ink = region_ink(0, left_end)
            return ink_ratio, center_whitespace, right_ink, left_ink
        finally:
            sample.close()
    finally:
        gray.close()


def classify_exam_page(
    *,
    image: bytes,
    native_text: str = "",
    right_native_text: str = "",
    left_native_text: str = "",
) -> PageLayoutDecision:
    """Classify content and layout without a model/API request."""

    text = clean_exam_markdown(native_text or "")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    has_numbered_content = bool(_CONTENT_MARKER_RE.search(text))
    option_markers = len(_OPTION_MARKER_RE.findall(text))
    cover_hint = bool(_COVER_HINT_RE.search(text))
    ink_ratio, center_white, right_ink, left_ink = _image_metrics(image)

    reasons: list[str] = []
    if ink_ratio < 0.0015:
        return PageLayoutDecision(
            content_class="non_content",
            layout="none",
            confidence=0.99,
            reasons=("visually_blank",),
            ink_ratio=ink_ratio,
            center_whitespace_ratio=center_white,
        )

    # Skip only with positive local evidence. Scanned pages with no native text
    # remain content/uncertain so a real question page is never silently lost.
    if text and not has_numbered_content and option_markers < 2:
        title_like = len(lines) <= 16 and len(text) <= 1800
        if cover_hint and title_like:
            reasons.extend(("cover_or_instruction_terms", "no_numbered_exam_records"))
            return PageLayoutDecision(
                content_class="non_content",
                layout="none",
                confidence=0.96,
                reasons=tuple(reasons),
                ink_ratio=ink_ratio,
                center_whitespace_ratio=center_white,
            )
        if len(text) <= 180 and len(lines) <= 5:
            reasons.extend(("very_low_text_content", "no_numbered_exam_records"))
            return PageLayoutDecision(
                content_class="non_content",
                layout="none",
                confidence=0.90,
                reasons=tuple(reasons),
                ink_ratio=ink_ratio,
                center_whitespace_ratio=center_white,
            )

    right_chars = len(clean_exam_markdown(right_native_text or ""))
    left_chars = len(clean_exam_markdown(left_native_text or ""))
    both_text_sides = right_chars >= 100 and left_chars >= 100
    both_visual_sides = right_ink >= 0.012 and left_ink >= 0.012

    if center_white >= 0.965 and both_visual_sides and both_text_sides:
        return PageLayoutDecision(
            content_class="content",
            layout="double",
            confidence=0.94,
            reasons=("strong_vertical_gutter", "content_on_both_sides"),
            ink_ratio=ink_ratio,
            center_whitespace_ratio=center_white,
        )

    if center_white <= 0.90 or min(right_ink, left_ink) < 0.006:
        return PageLayoutDecision(
            content_class="content",
            layout="single",
            confidence=0.88,
            reasons=("no_stable_center_gutter",),
            ink_ratio=ink_ratio,
            center_whitespace_ratio=center_white,
        )

    return PageLayoutDecision(
        content_class="content",
        layout="uncertain",
        confidence=0.62,
        reasons=("mixed_layout_signals",),
        ink_ratio=ink_ratio,
        center_whitespace_ratio=center_white,
    )
