"""Deterministic exception to the RTL double-column layout classifier.

Some exam pages are visually arranged across the full page even though most OCR
blocks individually fall in the left/right halves. Treating those pages as two
independent text columns clips the question source region and loses visual answer
choices. We preserve the existing double-column classifier unless question
headings plus image/table geometry prove a cross-column question band.
"""
from __future__ import annotations

from typing import Sequence

from . import exam_prep_mistral_layout_analysis as layout


_ORIGINAL_IS_RTL_DOUBLE_COLUMN = layout.is_rtl_double_column


def _visual_sides(block) -> set[str]:
    if str(block.block_type or "") not in {"image", "table"}:
        return set()
    x0, _y0, x1, _y1 = block.bbox
    sides: set[str] = set()
    if x0 < 0.49:
        sides.add("left")
    if x1 > 0.51:
        sides.add("right")
    return sides


def has_full_width_visual_question_bands(blocks: Sequence) -> bool:
    """True only when question geometry demonstrably crosses the column boundary."""

    parsed = []
    for block in blocks:
        heading = layout._parse_heading(block)
        if heading is not None:
            parsed.append((block, heading))
    question_headings = [
        block for block, heading in parsed if str(heading.get("kind") or "") == "question"
    ]
    if not question_headings:
        return False
    if any(str(heading.get("kind") or "") == "solution" for _block, heading in parsed):
        return False

    # A spanning question heading is direct evidence that a half-page source
    # region is wrong for that question band.
    if any(block.column == "span" for block in question_headings):
        return True

    heading_columns = {block.column for block in question_headings if block.column in {"left", "right"}}
    # Ordinary true double-column pages contain question anchors in both columns.
    # Do not reinterpret them merely because unrelated graphics align vertically.
    if heading_columns == {"left", "right"}:
        return False

    ordered_headings = sorted(question_headings, key=lambda block: (block.bbox[1], block.bbox[0]))
    visuals = [
        block for block in blocks if str(block.block_type or "") in {"image", "table"}
    ]
    for index, heading in enumerate(ordered_headings):
        y0 = heading.bbox[1]
        y1 = (
            ordered_headings[index + 1].bbox[1]
            if index + 1 < len(ordered_headings)
            else 0.98
        )
        band_sides: set[str] = set()
        for visual in visuals:
            center_y = (visual.bbox[1] + visual.bbox[3]) / 2
            if y0 <= center_y < y1:
                band_sides.update(_visual_sides(visual))
        if band_sides == {"left", "right"}:
            return True
    return False


def production_is_rtl_double_column(blocks: Sequence) -> bool:
    detected = _ORIGINAL_IS_RTL_DOUBLE_COLUMN(blocks)
    if not detected:
        return False
    return not has_full_width_visual_question_bands(blocks)


def install_full_width_layout_policy() -> None:
    if layout.is_rtl_double_column is not production_is_rtl_double_column:
        layout.is_rtl_double_column = production_is_rtl_double_column


__all__ = [
    "has_full_width_visual_question_bands",
    "install_full_width_layout_policy",
    "production_is_rtl_double_column",
]
