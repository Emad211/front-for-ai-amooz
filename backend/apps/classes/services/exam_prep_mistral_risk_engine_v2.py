"""Calibrated Stage-4 risk scoring from the first full 55-page dry run.

The first production-shaped risk plan proved two opposite failures in v1:

* ordinary scientific/math regions accumulated enough low-value signals to
  become suspicious (125/303 regions);
* obvious OCR corruption inside the assembled candidate (pathological repeated
  phrases and repeated tau/gamma glyph substitutions) could remain below the
  threshold.

This layer keeps the v1 evidence extraction but recalibrates only the final
selection policy.  It is intentionally simple and deterministic.
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


def _unexpected_symbol_substitution(
    decision: RegionRiskDecision,
    question: Mapping[str, Any],
) -> bool:
    """Catch a proven OCR4 glyph-substitution family without subject solving.

    In the full replay, repeated ``\\tau`` / ``\\gamma`` appeared where printed
    digits/operators had been corrupted (S120/S122/S125/S133 and neighbors).
    Do not flag legitimate notation when the same symbol is already present in
    the source question; require repetition in the solution candidate.
    """

    if decision.kind != "solution":
        return False
    solution_hits = len(_SUSPICIOUS_GREEK_RE.findall(decision.candidate_text))
    if solution_hits < 2:
        return False
    question_hits = len(_SUSPICIOUS_GREEK_RE.findall(_question_source_text(question)))
    return question_hits == 0


def _pathological_repetition(text: str) -> bool:
    """Detect long OCR repetition, not ordinary repeated math notation."""

    tokens = _TOKEN_RE.findall(clean_exam_markdown(text))
    if len(tokens) < 24:
        return False
    counts = Counter(zip(tokens, tokens[1:]))
    for (left, right), count in counts.items():
        if count < 12:
            continue
        joined = f"{left} {right}"
        # Repeated Persian/number phrases such as ``۲-۲ ذره`` or ``۲۰۰ و``
        # are strong corruption evidence. Pure x/x or LaTeX control repetition
        # is intentionally ignored.
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

    # Low-value content features describe *difficulty*, not evidence of an OCR
    # defect. They remain useful for prioritization and hard-math eligibility but
    # do not trigger a call on their own.
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

    if _unexpected_symbol_substitution(decision, question):
        score += 60
        signals.append("symbol_substitution_proxy")
    if _pathological_repetition(decision.candidate_text):
        score += 55
        signals.append("pathological_repetition")

    return min(100, score), tuple(dict.fromkeys(signals))


def score_region_risks(
    *,
    projection: Mapping[str, Any],
    layout: Mapping[str, Any],
    recovered_solution_targets: Sequence[int] | set[int] = (),
    unresolved_solution_targets: Sequence[int] | set[int] = (),
) -> list[RegionRiskDecision]:
    """Return a small, corruption-focused set of suspicious source regions."""

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
        # Stage 2 only accepts question anchors from true question pages. The
        # first dry run exposed six fake question regions inside answer pages;
        # never buy verification calls for those layout artifacts.
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

    # Provider target IDs must be unique. Duplicate OCR headings on the same
    # physical page are layout evidence, not justification for duplicate paid
    # calls. Keep the higher-risk/larger source region deterministically.
    deduped: dict[str, RegionRiskDecision] = {}
    for item in output:
        previous = deduped.get(item.target_id)
        if previous is None:
            deduped[item.target_id] = item
            continue
        area = (item.bbox[2] - item.bbox[0]) * (item.bbox[3] - item.bbox[1])
        old_area = (previous.bbox[2] - previous.bbox[0]) * (previous.bbox[3] - previous.bbox[1])
        if (item.score, area) > (previous.score, old_area):
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


__all__ = ["RegionRiskDecision", "score_region_risks"]
