from __future__ import annotations

from html import unescape
import re
from typing import Any, Mapping, Sequence

from .exam_prep_mistral_layout_analysis import normalize_page_blocks
from .exam_prep_mistral_solution_headings import (
    normalize_solution_option_label,
    parse_solution_heading,
)

_HTML_BREAK_RE = re.compile(
    r"</?(?:tr|td|th|p|div|li|br)\b[^>]*>",
    re.IGNORECASE,
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_CROP_BOUNDS = {
    "left": (0.02, 0.075, 0.51, 0.965),
    "right": (0.49, 0.075, 0.98, 0.965),
}


def _int_value(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _heading_lines(value: Any) -> list[str]:
    """Return line-like OCR segments without trusting provider block boundaries.

    OCR4 can place an entire solution column into one text/equation block, or can
    label the whole column as one HTML table. Targeted recovery therefore scans
    inside block content instead of assuming one heading per provider block.
    """

    text = str(value or "")
    text = _HTML_BREAK_RE.sub("\n", text)
    text = _HTML_TAG_RE.sub(" ", text)
    text = unescape(text)
    return [line.strip() for line in text.splitlines() if line.strip()]


def scan_solution_headings(value: Any) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for ordinal, line in enumerate(_heading_lines(value)):
        parsed = parse_solution_heading(line)
        if not parsed:
            continue
        raw_option = int(parsed["rawOptionLabel"])
        option, normalized, valid = normalize_solution_option_label(raw_option)
        output.append(
            {
                "headingOrdinalInContent": ordinal,
                "rawQuestionNumber": int(parsed["rawQuestionNumber"]),
                "rawOptionLabel": raw_option,
                "optionLabel": option,
                "optionLabelNormalized": normalized,
                "optionLabelValid": valid,
                "headingFormat": str(parsed["format"]),
            }
        )
    return output


def collect_crop_headings(
    root: Mapping[str, Any],
    crop_specs: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    pages = [page for page in (root.get("pages") or []) if isinstance(page, Mapping)]
    pages.sort(key=lambda page: _int_value(page.get("index"), 0))
    for page in pages:
        crop_index = _int_value(page.get("index"), 0)
        if not 0 <= crop_index < len(crop_specs):
            continue
        spec = crop_specs[crop_index]
        physical_page = _int_value(spec.get("physicalPageNumber"), 0)
        side = str(spec.get("column") or "").strip().lower()
        for block_index, block in enumerate(page.get("blocks") or []):
            if not isinstance(block, Mapping):
                continue
            for heading in scan_solution_headings(block.get("content")):
                output.append(
                    {
                        "providerCropIndex": crop_index,
                        "physicalPageNumber": physical_page,
                        "column": side,
                        "providerBlockIndex": block_index,
                        **heading,
                    }
                )
    return output


def resolve_target_questions(
    headings: Sequence[Mapping[str, Any]],
    target_questions: Sequence[int],
) -> dict[str, Any]:
    targets = sorted({int(value) for value in target_questions if int(value) > 0})
    grouped: dict[int, list[Mapping[str, Any]]] = {}
    for heading in headings:
        question = _int_value(heading.get("rawQuestionNumber"), 0)
        grouped.setdefault(question, []).append(heading)

    recovered: list[dict[str, Any]] = []
    unresolved: list[int] = []
    conflicts: list[dict[str, Any]] = []
    for question in targets:
        candidates = grouped.get(question, [])
        valid_options = sorted(
            {
                int(item.get("optionLabel"))
                for item in candidates
                if item.get("optionLabelValid") is True
                and isinstance(item.get("optionLabel"), int)
                and 1 <= int(item.get("optionLabel")) <= 4
            }
        )
        if len(valid_options) == 1:
            option = valid_options[0]
            evidence = [
                item
                for item in candidates
                if item.get("optionLabelValid") is True
                and item.get("optionLabel") == option
            ]
            recovered.append(
                {
                    "questionNumber": question,
                    "optionLabel": option,
                    "evidenceCount": len(evidence),
                    "physicalPages": sorted(
                        {
                            _int_value(item.get("physicalPageNumber"), 0)
                            for item in evidence
                            if _int_value(item.get("physicalPageNumber"), 0) > 0
                        }
                    ),
                }
            )
        elif len(valid_options) > 1:
            conflicts.append(
                {
                    "questionNumber": question,
                    "validOptionLabels": valid_options,
                }
            )
        else:
            unresolved.append(question)

    return {
        "targetQuestionNumbers": targets,
        "recovered": recovered,
        "recoveredQuestionNumbers": [item["questionNumber"] for item in recovered],
        "unresolvedQuestionNumbers": unresolved,
        "conflicts": conflicts,
        "complete": not unresolved and not conflicts and len(recovered) == len(targets),
    }


def _mapped_crop_bbox(
    local_box: tuple[float, float, float, float],
    *,
    side: str,
) -> tuple[float, float, float, float] | None:
    crop = _CROP_BOUNDS.get(side)
    if crop is None:
        return None
    lx0, ly0, lx1, ly1 = local_box
    if not (0 <= lx0 < lx1 <= 1 and 0 <= ly0 < ly1 <= 1):
        return None
    cx0, cy0, cx1, cy1 = crop
    width = cx1 - cx0
    height = cy1 - cy0
    mapped = (
        cx0 + lx0 * width,
        cy0 + ly0 * height,
        cx0 + lx1 * width,
        cy0 + ly1 * height,
    )
    if not (0 <= mapped[0] < mapped[2] <= 1 and 0 <= mapped[1] < mapped[3] <= 1):
        return None
    return mapped


def recovered_solution_layout_regions(
    root: Mapping[str, Any],
    *,
    crop_specs: Sequence[Mapping[str, Any]],
    recovered_targets: Mapping[int, tuple[str, int, str]],
) -> list[dict[str, Any]]:
    """Derive precise original-page regions from already-paid targeted OCR.

    A region is emitted only when one recovered target maps to exactly one OCR
    heading block and that block contains no second parsed solution heading.
    The vertical boundary ends at the next heading block in the same crop. This
    avoids the broad whole-column fallback that can make Stage-5 read a neighbor.
    """

    headings = collect_crop_headings(root, crop_specs)
    pages = {
        _int_value(page.get("index"), 0): page
        for page in (root.get("pages") or [])
        if isinstance(page, Mapping)
    }
    output: list[dict[str, Any]] = []

    for raw_number, recovered in sorted(recovered_targets.items()):
        number = int(raw_number)
        try:
            label = int(recovered[0])
            physical_page = int(recovered[1])
        except (TypeError, ValueError, IndexError):
            continue
        side = str(recovered[2] if len(recovered) > 2 else "").strip().lower()
        matches = [
            item
            for item in headings
            if _int_value(item.get("rawQuestionNumber"), 0) == number
            and item.get("optionLabelValid") is True
            and _int_value(item.get("optionLabel"), 0) == label
            and _int_value(item.get("physicalPageNumber"), 0) == physical_page
            and str(item.get("column") or "").strip().lower() == side
        ]
        if len(matches) != 1:
            continue
        match = matches[0]
        crop_index = _int_value(match.get("providerCropIndex"), -1)
        block_index = _int_value(match.get("providerBlockIndex"), -1)
        page = pages.get(crop_index)
        if page is None or crop_index < 0 or block_index < 0:
            continue

        same_block = [
            item
            for item in headings
            if _int_value(item.get("providerCropIndex"), -1) == crop_index
            and _int_value(item.get("providerBlockIndex"), -1) == block_index
        ]
        if len(same_block) != 1:
            continue

        normalized = normalize_page_blocks(page)
        by_index = {block.provider_index: block for block in normalized}
        heading_block = by_index.get(block_index)
        if heading_block is None:
            continue
        next_y = min(
            (
                by_index[next_index].bbox[1]
                for item in headings
                if _int_value(item.get("providerCropIndex"), -1) == crop_index
                and (next_index := _int_value(item.get("providerBlockIndex"), -1)) in by_index
                and by_index[next_index].bbox[1] > heading_block.bbox[1]
            ),
            default=0.98,
        )
        local_box = (
            0.0,
            heading_block.bbox[1],
            1.0,
            max(heading_block.bbox[3], next_y),
        )
        mapped = _mapped_crop_bbox(local_box, side=side)
        if mapped is None:
            continue
        output.append(
            {
                "kind": "solution",
                "questionNumber": number,
                "rawQuestionNumber": number,
                "correctOptionLabel": label,
                "column": side,
                "bbox": list(mapped),
                "contentBBox": None,
                "text": "",
                "visuals": [],
                "captions": [],
                "issues": ["targeted_solution_heading_recovered"],
                "targetedRecoveryRegion": True,
                "originalPageNumber": physical_page,
            }
        )
    return output


def overlay_recovered_solution_regions(
    layout: Mapping[str, Any],
    regions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Overlay only unambiguous missing solution regions onto the base layout."""

    output = dict(layout)
    pages = [dict(page) for page in (layout.get("pages") or []) if isinstance(page, Mapping)]
    page_positions: dict[int, list[int]] = {}
    for index, page in enumerate(pages):
        number = _int_value(page.get("originalPageNumber"), 0)
        if number > 0:
            page_positions.setdefault(number, []).append(index)

    existing = {
        _int_value(region.get("questionNumber"), 0)
        for page in pages
        for region in (page.get("regions") or [])
        if isinstance(region, Mapping)
        and str(region.get("kind") or "") == "solution"
        and _int_value(region.get("questionNumber"), 0) > 0
    }
    added: list[int] = []
    for raw in regions:
        number = _int_value(raw.get("questionNumber"), 0)
        page_number = _int_value(raw.get("originalPageNumber"), 0)
        positions = page_positions.get(page_number, [])
        if number < 1 or number in existing or len(positions) != 1:
            continue
        position = positions[0]
        page = dict(pages[position])
        page_regions = [
            dict(item) for item in (page.get("regions") or []) if isinstance(item, Mapping)
        ]
        region = {key: value for key, value in raw.items() if key != "originalPageNumber"}
        page_regions.append(region)
        page["regions"] = page_regions
        pages[position] = page
        existing.add(number)
        added.append(number)

    output["pages"] = pages
    output["targetedRecoveredSolutionRegions"] = sorted(added)
    return output


__all__ = [
    "collect_crop_headings",
    "overlay_recovered_solution_regions",
    "recovered_solution_layout_regions",
    "resolve_target_questions",
    "scan_solution_headings",
]
