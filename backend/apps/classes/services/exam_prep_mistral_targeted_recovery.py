from __future__ import annotations

from html import unescape
import re
from typing import Any, Mapping, Sequence

from .exam_prep_mistral_solution_headings import (
    normalize_solution_option_label,
    parse_solution_heading,
)

_HTML_BREAK_RE = re.compile(
    r"</?(?:tr|td|th|p|div|li|br)\b[^>]*>",
    re.IGNORECASE,
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


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
    pages.sort(key=lambda page: int(page.get("index") or 0))
    for page in pages:
        crop_index = int(page.get("index") or 0)
        if not 0 <= crop_index < len(crop_specs):
            continue
        spec = crop_specs[crop_index]
        try:
            physical_page = int(spec.get("physicalPageNumber") or 0)
        except (TypeError, ValueError):
            physical_page = 0
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
        try:
            question = int(heading.get("rawQuestionNumber") or 0)
        except (TypeError, ValueError):
            continue
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
                            int(item.get("physicalPageNumber") or 0)
                            for item in evidence
                            if int(item.get("physicalPageNumber") or 0) > 0
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
