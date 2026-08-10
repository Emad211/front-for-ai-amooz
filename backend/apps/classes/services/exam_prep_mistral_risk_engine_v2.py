"""Calibrated Stage-4 risk scoring with deterministic structural blockers.

Ordinary scientific/math content must not trigger paid verification by itself,
but explicit projection defects are source-sensitive evidence and can never be
classified as clean. This layer therefore combines the existing calibrated OCR
signals with hard structural defects such as missing stems/options/solutions and
unresolved visual-source contracts.
"""
from __future__ import annotations

from collections import Counter
import os
import re
from typing import Any, Mapping, Sequence

from . import exam_prep_mistral_risk_engine as base
from .exam_prep_utils import clean_exam_markdown


RegionRiskDecision = base.RegionRiskDecision
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_PERSIAN_RE = re.compile(r"[\u0600-\u06FF]")
_NUMBER_RE = re.compile(r"[0-9۰-۹٠-٩]")
_TOKEN_RE = re.compile(
    r"[0-9۰-۹٠-٩]+(?:[-/][0-9۰-۹٠-٩]+)?|[\u0600-\u06FF]+|[A-Za-z]+"
)
_SUSPICIOUS_GREEK_RE = re.compile(r"\\(?:tau|gamma)\b")
_VISUAL_STRUCTURAL_ISSUES = frozenset(
    {
        "visual_precise_crop_unresolved",
        "visual_reference_without_ocr_visual",
        "visual_attachment_missing",
    }
)


def _threshold() -> int:
    try:
        value = int(os.getenv("EXAM_PREP_STAGE4_RISK_THRESHOLD", "50"))
    except (TypeError, ValueError):
        value = 50
    return max(40, min(80, value))


def _number(value: Any) -> int:
    match = re.search(r"\d+", str(value or "").translate(_DIGITS))
    return int(match.group(0)) if match else 0


def _question_map(projection: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    exam = projection.get("exam_prep")
    questions = exam.get("questions") if isinstance(exam, Mapping) else []
    output: dict[int, Mapping[str, Any]] = {}
    for raw in questions or []:
        if not isinstance(raw, Mapping):
            continue
        number = _number(raw.get("source_question_number"))
        if number > 0:
            output[number] = raw
    return output


def _question_source_text(question: Mapping[str, Any]) -> str:
    values = [clean_exam_markdown(question.get("question_text_markdown") or "")]
    for option in question.get("options") or []:
        if not isinstance(option, Mapping):
            continue
        values.append(clean_exam_markdown(option.get("text_markdown") or ""))
    return "\n".join(value for value in values if value)


def _options_complete(question: Mapping[str, Any]) -> bool:
    observed: dict[str, str] = {}
    for raw in question.get("options") or []:
        if not isinstance(raw, Mapping):
            continue
        label = str(raw.get("label") or "").translate(_DIGITS).strip()
        if label in {"1", "2", "3", "4"}:
            observed[label] = clean_exam_markdown(raw.get("text_markdown") or "")
    return set(observed) == {"1", "2", "3", "4"} and all(observed.values())


def _structural_signals(
    decision: RegionRiskDecision,
    question: Mapping[str, Any],
) -> tuple[str, ...]:
    """Return explicit projection defects that may never be scored as clean."""

    issues = {str(code) for code in (question.get("issues") or []) if str(code)}
    issues.update(str(code) for code in decision.region_issues if str(code))
    signals: list[str] = []

    if decision.kind == "question":
        if (
            not clean_exam_markdown(question.get("question_text_markdown") or "")
            or "missing_question_text" in issues
        ):
            signals.append("structural_missing_question_text")
        if not _options_complete(question):
            signals.append("structural_options_incomplete")
        if issues & _VISUAL_STRUCTURAL_ISSUES:
            signals.append("structural_visual_source_unresolved")
    else:
        if not clean_exam_markdown(question.get("teacher_solution_markdown") or ""):
            signals.append("structural_missing_solution_body")
        if "mistral_solution_heading_unresolved" in issues:
            signals.append("structural_solution_heading_unresolved")
    return tuple(signals)


def _unexpected_symbol_substitution(
    decision: RegionRiskDecision,
    question: Mapping[str, Any],
) -> bool:
    if decision.kind != "solution":
        return False
    solution_hits = len(_SUSPICIOUS_GREEK_RE.findall(decision.candidate_text))
    if solution_hits < 2:
        return False
    question_hits = len(_SUSPICIOUS_GREEK_RE.findall(_question_source_text(question)))
    return question_hits == 0


def _pathological_repetition(text: str) -> bool:
    tokens = _TOKEN_RE.findall(clean_exam_markdown(text))
    if len(tokens) < 24:
        return False
    counts = Counter(zip(tokens, tokens[1:]))
    for (left, right), count in counts.items():
        if count < 12:
            continue
        joined = f"{left} {right}"
        if _PERSIAN_RE.search(joined) and _NUMBER_RE.search(joined):
            return True
    return False


def _page_roles(layout: Mapping[str, Any]) -> dict[int, str]:
    output: dict[int, str] = {}
    for page in layout.get("pages") or []:
        if not isinstance(page, Mapping):
            continue
        number = _number(page.get("originalPageNumber"))
        if number > 0:
            output[number] = str(page.get("pageRole") or "")
    return output


def _recalibrated_score(
    decision: RegionRiskDecision,
    *,
    question: Mapping[str, Any],
) -> tuple[int, tuple[str, ...]]:
    signals = list(decision.signals)
    selected = set(signals)
    score = 0

    # Difficulty features are prioritization hints, not evidence of an OCR defect.
    if "formula_math" in selected:
        score += 15 if decision.hard_math else 8
    if "digits_units" in selected:
        score += 5
    if "scientific_terminology" in selected:
        score += 2

    # Concrete source-sensitive evidence.
    if "visual_anomaly" in selected:
        score += 50
    if "missing_invalid_answer" in selected:
        score += 55
    if "heading_conflict" in selected:
        score += 45
    if "ocr_disagreement" in selected:
        score += 40
    if "source_corruption" in selected:
        score += 60

    structural = _structural_signals(decision, question)
    if structural:
        # Structural failure is itself sufficient to cross the default threshold.
        score += 70
        signals.extend(structural)

    if _unexpected_symbol_substitution(decision, question):
        score += 60
        signals.append("symbol_substitution_proxy")
    if _pathological_repetition(decision.candidate_text):
        score += 55
        signals.append("pathological_repetition")

    return min(100, score), tuple(dict.fromkeys(signals))


def _duplicate_quality(item: RegionRiskDecision) -> tuple[int, int, float]:
    heading_unstable = (
        "heading_conflict" in item.signals
        or "heading_sequence_gap" in item.region_issues
        or "mistral_question_number_unverified" in item.region_issues
    )
    area = (item.bbox[2] - item.bbox[0]) * (item.bbox[3] - item.bbox[1])
    return (0 if heading_unstable else 1, item.score, area)


def score_region_risks(
    *,
    projection: Mapping[str, Any],
    layout: Mapping[str, Any],
    recovered_solution_targets: Sequence[int] | set[int] = (),
    unresolved_solution_targets: Sequence[int] | set[int] = (),
) -> list[RegionRiskDecision]:
    """Return corruption- and structure-focused suspicious source regions."""

    original = base.score_region_risks(
        projection=projection,
        layout=layout,
        recovered_solution_targets=recovered_solution_targets,
        unresolved_solution_targets=unresolved_solution_targets,
    )
    questions = _question_map(projection)
    roles = _page_roles(layout)
    threshold = _threshold()
    output: list[RegionRiskDecision] = []

    for decision in original:
        if decision.kind == "question" and roles.get(decision.page_number) != "question":
            continue
        question = questions.get(decision.question_number)
        if question is None:
            continue
        score, signals = _recalibrated_score(decision, question=question)
        output.append(
            RegionRiskDecision(
                question_number=decision.question_number,
                kind=decision.kind,
                page_number=decision.page_number,
                bbox=decision.bbox,
                score=score,
                suspicious=score >= threshold,
                hard_math=decision.hard_math,
                signals=signals,
                region_issues=decision.region_issues,
                candidate_text=decision.candidate_text,
            )
        )

    deduped: dict[str, RegionRiskDecision] = {}
    for item in output:
        previous = deduped.get(item.target_id)
        if previous is None or _duplicate_quality(item) > _duplicate_quality(previous):
            deduped[item.target_id] = item

    return sorted(
        deduped.values(),
        key=lambda item: (
            -item.score,
            item.page_number,
            item.question_number,
            0 if item.kind == "question" else 1,
        ),
    )


__all__ = [
    "RegionRiskDecision",
    "_options_complete",
    "_structural_signals",
    "score_region_risks",
]
