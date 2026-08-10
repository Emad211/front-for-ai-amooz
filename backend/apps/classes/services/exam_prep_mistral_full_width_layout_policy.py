"""Deterministic full-width question policy for OCR4 layout evidence.

Some exam pages are visually arranged across the full page even though most OCR
blocks individually fall in the left/right halves. Treating those pages as two
independent text columns clips source regions and loses visual answer choices.

For a second proven pattern, a full-width question contains at least one source
image plus a bottom row of exactly four option images. Persian exam options are
laid out RTL, so the four image boxes are bound right-to-left to labels 1..4.
No model or image similarity heuristic is used.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from . import exam_prep_mistral_layout_analysis as layout


_ORIGINAL_IS_RTL_DOUBLE_COLUMN = layout.is_rtl_double_column
_ORIGINAL_BUILD_REGIONS = layout.build_regions


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

    if any(block.column == "span" for block in question_headings):
        return True

    heading_columns = {block.column for block in question_headings if block.column in {"left", "right"}}
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


def _box(value: Any) -> tuple[float, float, float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        x0, y0, x1, y1 = (float(item) for item in value)
    except (TypeError, ValueError):
        return None
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        return None
    return x0, y0, x1, y1


def _rows(visuals: Sequence[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Group image boxes into horizontal rows using geometry only."""

    ordered = sorted(
        visuals,
        key=lambda raw: ((_box(raw.get("bbox")) or (0, 0, 0, 0))[1],
                         (_box(raw.get("bbox")) or (0, 0, 0, 0))[0]),
    )
    rows: list[list[dict[str, Any]]] = []
    centers: list[float] = []
    for raw in ordered:
        box = _box(raw.get("bbox"))
        if box is None:
            continue
        cy = (box[1] + box[3]) / 2
        height = box[3] - box[1]
        tolerance = max(0.022, min(0.050, height * 0.55))
        match = next(
            (index for index, center in enumerate(centers) if abs(cy - center) <= tolerance),
            None,
        )
        if match is None:
            rows.append([raw])
            centers.append(cy)
        else:
            rows[match].append(raw)
            centers[match] = sum(
                ((_box(item.get("bbox")) or (0, 0, 0, 0))[1]
                 + (_box(item.get("bbox")) or (0, 0, 0, 0))[3]) / 2
                for item in rows[match]
            ) / len(rows[match])
    return [row for _center, row in sorted(zip(centers, rows), key=lambda item: item[0])]


def _bind_full_width_option_row(region: dict[str, Any]) -> bool:
    if str(region.get("kind") or "") != "question":
        return False
    region_box = _box(region.get("bbox"))
    if region_box is None or region_box[2] - region_box[0] < 0.90:
        return False

    images = [
        raw for raw in (region.get("visuals") or [])
        if isinstance(raw, dict)
        and str(raw.get("type") or "") == "image"
        and _box(raw.get("bbox")) is not None
    ]
    # Proven family: at least one question-side image plus four answer images.
    if len(images) < 5:
        return False
    rows = _rows(images)
    if not rows or len(rows[-1]) != 4:
        return False
    option_row = rows[-1]
    boxes = [_box(raw.get("bbox")) for raw in option_row]
    if any(box is None for box in boxes):
        return False
    typed_boxes = [box for box in boxes if box is not None]
    if min(box[0] for box in typed_boxes) > 0.30 or max(box[2] for box in typed_boxes) < 0.70:
        return False

    option_ids = {id(raw) for raw in option_row}
    for raw in images:
        if id(raw) not in option_ids:
            raw["role"] = "question"
            raw.pop("optionLabel", None)
    rtl = sorted(
        option_row,
        key=lambda raw: sum((_box(raw.get("bbox")) or (0, 0, 0, 0))[::2]) / 2,
        reverse=True,
    )
    for label, raw in zip(("1", "2", "3", "4"), rtl):
        raw["role"] = "option"
        raw["optionLabel"] = label

    region["visualOptionMode"] = "separate_candidates"
    region["fullWidthVisualOptionBinding"] = "rtl_bottom_row_exact4"
    return True


def production_build_regions(*args, **kwargs):
    regions, last = _ORIGINAL_BUILD_REGIONS(*args, **kwargs)
    for region in regions:
        if isinstance(region, dict):
            _bind_full_width_option_row(region)
    return regions, last


def install_full_width_layout_policy() -> None:
    if layout.is_rtl_double_column is not production_is_rtl_double_column:
        layout.is_rtl_double_column = production_is_rtl_double_column
    if layout.build_regions is not production_build_regions:
        layout.build_regions = production_build_regions


__all__ = [
    "_bind_full_width_option_row",
    "has_full_width_visual_question_bands",
    "install_full_width_layout_policy",
    "production_build_regions",
    "production_is_rtl_double_column",
]
