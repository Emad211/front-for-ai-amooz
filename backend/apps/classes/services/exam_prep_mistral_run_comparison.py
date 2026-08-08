from __future__ import annotations

from difflib import SequenceMatcher
import re
from statistics import mean, median
from typing import Any, Mapping, Sequence

_LATEX_RE = re.compile(
    r"\$\$.*?\$\$|(?<!\$)\$(?!\$).*?(?<!\$)\$(?!\$)",
    re.DOTALL,
)


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if 0.0 <= number <= 1.0 else None


def _word_rows(page: Mapping[str, Any]) -> list[dict[str, Any]]:
    confidence = page.get("confidence_scores")
    confidence = confidence if isinstance(confidence, Mapping) else {}
    rows: list[dict[str, Any]] = []
    for raw in confidence.get("word_confidence_scores") or []:
        if not isinstance(raw, Mapping):
            continue
        score = _number(raw.get("confidence"))
        start = raw.get("start_index")
        text = raw.get("text")
        if score is None or isinstance(start, bool) or not isinstance(start, int):
            continue
        if not isinstance(text, str):
            continue
        rows.append(
            {
                "start": max(0, start),
                "end": max(0, start) + len(text),
                "confidence": score,
            }
        )
    return rows


def _changed_ranges(first: str, second: str) -> list[tuple[int, int]]:
    matcher = SequenceMatcher(None, first, second, autojunk=False)
    ranges: list[tuple[int, int]] = []
    for tag, _i1, _i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            ranges.append((j1, j2))
    return ranges


def _overlaps(start: int, end: int, ranges: Sequence[tuple[int, int]]) -> bool:
    for left, right in ranges:
        if left == right:
            if start <= left <= end:
                return True
        elif max(start, left) < min(end, right):
            return True
    return False


def _latex_ranges(markdown: str) -> list[tuple[int, int]]:
    return [match.span() for match in _LATEX_RE.finditer(markdown or "")]


def _score_summary(values: Sequence[float]) -> dict[str, Any]:
    scores = list(values)
    if not scores:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "below60": 0,
            "below80": 0,
            "below95": 0,
            "atLeast95": 0,
        }
    return {
        "count": len(scores),
        "mean": round(mean(scores), 6),
        "median": round(median(scores), 6),
        "below60": sum(score < 0.60 for score in scores),
        "below80": sum(score < 0.80 for score in scores),
        "below95": sum(score < 0.95 for score in scores),
        "atLeast95": sum(score >= 0.95 for score in scores),
    }


def _block_type_counts(page: Mapping[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for raw in page.get("blocks") or []:
        if not isinstance(raw, Mapping):
            continue
        kind = str(
            raw.get("type")
            or raw.get("block_type")
            or raw.get("label")
            or "unknown"
        ).strip().lower() or "unknown"
        counts[kind] = counts.get(kind, 0) + 1
    return dict(sorted(counts.items()))


def compare_page_runs(
    first_page: Mapping[str, Any],
    second_page: Mapping[str, Any],
) -> dict[str, Any]:
    first_markdown = str(first_page.get("markdown") or "")
    second_markdown = str(second_page.get("markdown") or "")
    changed = _changed_ranges(first_markdown, second_markdown)
    latex = _latex_ranges(second_markdown)
    rows = _word_rows(second_page)

    changed_scores: list[float] = []
    stable_scores: list[float] = []
    changed_formula_scores: list[float] = []
    stable_formula_scores: list[float] = []
    for row in rows:
        is_changed = _overlaps(row["start"], row["end"], changed)
        in_formula = _overlaps(row["start"], row["end"], latex)
        (changed_scores if is_changed else stable_scores).append(row["confidence"])
        if in_formula:
            (changed_formula_scores if is_changed else stable_formula_scores).append(
                row["confidence"]
            )

    similarity = SequenceMatcher(
        None,
        first_markdown,
        second_markdown,
        autojunk=False,
    ).ratio()
    first_blocks = _block_type_counts(first_page)
    second_blocks = _block_type_counts(second_page)
    changed_summary = _score_summary(changed_scores)
    changed_formula_summary = _score_summary(changed_formula_scores)
    risk_codes: list[str] = []
    if similarity < 0.995:
        risk_codes.append("markdown_instability")
    if changed_formula_summary["count"]:
        risk_codes.append("formula_instability")
    if changed_summary["atLeast95"]:
        risk_codes.append("high_confidence_instability")
    if first_blocks != second_blocks:
        risk_codes.append("block_structure_instability")

    return {
        "markdownSimilarity": round(similarity, 6),
        "firstMarkdownCharacters": len(first_markdown),
        "secondMarkdownCharacters": len(second_markdown),
        "firstBlockTypeCounts": first_blocks,
        "secondBlockTypeCounts": second_blocks,
        "changedWordConfidence": changed_summary,
        "stableWordConfidence": _score_summary(stable_scores),
        "changedFormulaWordConfidence": changed_formula_summary,
        "stableFormulaWordConfidence": _score_summary(stable_formula_scores),
        "riskCodes": risk_codes,
    }


def _page_map(root: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    output: dict[int, Mapping[str, Any]] = {}
    for raw in root.get("pages") or []:
        if not isinstance(raw, Mapping):
            continue
        index = raw.get("index")
        if isinstance(index, bool) or not isinstance(index, int):
            continue
        output[index] = raw
    return output


def compare_ocr_runs(
    first_root: Mapping[str, Any],
    second_root: Mapping[str, Any],
    *,
    original_pages: Sequence[int] | None = None,
) -> dict[str, Any]:
    first_pages = _page_map(first_root)
    second_pages = _page_map(second_root)
    common = sorted(set(first_pages) & set(second_pages))
    if set(first_pages) != set(second_pages):
        raise ValueError("OCR runs do not contain identical provider page indexes.")
    if original_pages is not None and len(original_pages) != len(common):
        raise ValueError("Original-page mapping does not match provider page count.")

    pages: list[dict[str, Any]] = []
    total_high_confidence_changed = 0
    formula_instability_pages = 0
    for position, provider_index in enumerate(common):
        comparison = compare_page_runs(
            first_pages[provider_index],
            second_pages[provider_index],
        )
        total_high_confidence_changed += int(
            comparison["changedWordConfidence"]["atLeast95"] or 0
        )
        formula_instability_pages += int(
            "formula_instability" in comparison["riskCodes"]
        )
        pages.append(
            {
                "providerPageIndex": provider_index,
                "originalPageNumber": (
                    int(original_pages[position]) if original_pages is not None else None
                ),
                **comparison,
            }
        )

    similarities = [float(page["markdownSimilarity"]) for page in pages]
    return {
        "schemaVersion": 1,
        "contentFree": True,
        "pageCount": len(pages),
        "minimumMarkdownSimilarity": min(similarities) if similarities else None,
        "averageMarkdownSimilarity": (
            round(mean(similarities), 6) if similarities else None
        ),
        "pagesWithFormulaInstability": formula_instability_pages,
        "highConfidenceChangedWordCount": total_high_confidence_changed,
        "pages": pages,
    }
