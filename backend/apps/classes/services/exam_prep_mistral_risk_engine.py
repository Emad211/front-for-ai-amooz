"""Free deterministic risk scoring for OCR4 question/solution regions.

Stage 4 never asks a model to decide what is risky. This module inspects only
local/OCR evidence already produced by Stages 2 and 3, assigns every numbered
question/solution region a bounded score, and marks only materially suspicious
regions for source-only transcription.

Confidence values from OCR or later LLMs are deliberately not part of the score.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import re
from typing import Any, Mapping, Sequence

from .exam_prep_mistral_visual_reconcile import VISUAL_CRITICAL_ISSUE_CODES
from .exam_prep_text_quality import (
    has_broken_persian_text,
    has_duplicate_clean_and_broken_text,
)
from .exam_prep_utils import clean_exam_markdown


_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_FORMULA_RE = re.compile(
    r"(?:\\(?:frac|sqrt|sin|cos|tan|log|ln|lim|sum|int|vec|overline|begin|left|right)\b"
    r"|\$|\^|_[{0-9A-Za-z]|[=±×÷<>≤≥≈∑∫√∞]|(?:^|\s)[A-Za-z]\s*=)",
    flags=re.IGNORECASE,
)
_UNIT_RE = re.compile(
    r"(?:\b(?:kg|mg|g|mol|mmol|m|cm|mm|nm|km|s|ms|hz|khz|mhz|n|pa|kpa|j|kj|w|kw|v|mv|a|ma|ohm|rpm|c)\b"
    r"|m/s|m/s\^?2|m\.s|kg/m|g/mol|°\s*c|℃|Ω|µm|μm|ph\b)",
    flags=re.IGNORECASE,
)
_DIGIT_RE = re.compile(r"\d", re.UNICODE)
_SOURCE_CORRUPTION_RE = re.compile(r"[\uFFFD□■▯]|(?:\?{3,})")
_SCIENTIFIC_RE = re.compile(
    r"(?:ژن|کروموزوم|آنزیم|پروتئین|یاخته|سلول|DNA|RNA|مولکول|اتم|یون|مول|اسید|باز|"
    r"واکنش|ساختار|آلکان|آلکن|فشار|چگالی|دما|نیرو|شتاب|سرعت|انرژی|توان|مقاومت|"
    r"ولتاژ|جریان|مدار|میدان|بردار|تابع|مشتق|انتگرال|حد|زاویه|مثلث|دایره|نمودار|"
    r"سنگ|کانی|گسل|زمین|لایه)",
    flags=re.IGNORECASE,
)
_HEADING_ISSUES = frozenset(
    {
        "heading_sequence_gap",
        "mistral_question_number_unverified",
        "mistral_duplicate_question_anchor",
        "mistral_solution_heading_unresolved",
    }
)
_QUESTION_DISAGREEMENT_ISSUES = frozenset(
    {
        "mistral_question_option_parse_failed",
        "duplicate_mixed_text",
        "serialized_option_payload",
    }
)
_SOLUTION_DISAGREEMENT_ISSUES = frozenset(
    {
        "conflicting_correct_option",
        "conflicting_correct_option_text",
        "correct_option_not_in_options",
    }
)
_MISSING_ANSWER_ISSUES = frozenset(
    {
        "missing_answer",
        "missing_correct_option_label",
        "missing_solution_text",
        "count_answer_unresolved",
    }
)


def _threshold() -> int:
    try:
        value = int(os.getenv("EXAM_PREP_STAGE4_RISK_THRESHOLD", "40"))
    except (TypeError, ValueError):
        value = 40
    return max(25, min(80, value))


def _number(value: Any) -> int:
    match = re.search(r"\d+", str(value or "").translate(_DIGITS))
    return int(match.group(0)) if match else 0


def _bbox(value: Any) -> tuple[float, float, float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        x0, y0, x1, y1 = (float(item) for item in value)
    except (TypeError, ValueError):
        return None
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        return None
    return x0, y0, x1, y1


def _codes(values: Sequence[Any]) -> set[str]:
    return {
        clean_exam_markdown(code).strip()
        for code in values
        if clean_exam_markdown(code).strip()
    }


def _question_map(projection: Mapping[str, Any]) -> dict[int, dict[str, Any]]:
    exam = projection.get("exam_prep")
    questions = exam.get("questions") if isinstance(exam, Mapping) else []
    output: dict[int, dict[str, Any]] = {}
    for raw in questions or []:
        if not isinstance(raw, Mapping):
            continue
        number = _number(raw.get("source_question_number"))
        if number > 0:
            output[number] = dict(raw)
    return output


def _candidate_text(question: Mapping[str, Any], kind: str) -> str:
    if kind == "question":
        values = [clean_exam_markdown(question.get("question_text_markdown") or "")]
        for option in question.get("options") or []:
            if not isinstance(option, Mapping):
                continue
            label = clean_exam_markdown(option.get("label") or "")
            text = clean_exam_markdown(option.get("text_markdown") or "")
            values.append(f"{label}) {text}".strip())
        return "\n".join(value for value in values if value)
    return clean_exam_markdown(question.get("teacher_solution_markdown") or "")


def _visual_critical_for_kind(question: Mapping[str, Any], kind: str) -> bool:
    desired_roles = {"solution"} if kind == "solution" else {"question", "option"}
    for asset in question.get("visuals") or []:
        if not isinstance(asset, Mapping) or str(asset.get("role") or "") not in desired_roles:
            continue
        if asset.get("reviewOnly") is True:
            return True
        sanity = asset.get("sanity")
        if isinstance(sanity, Mapping):
            if str(sanity.get("status") or "") == "needs_review":
                return True
            if any(str(code) in VISUAL_CRITICAL_ISSUE_CODES for code in (sanity.get("issues") or [])):
                return True
    return False


def _hard_math_score(text: str) -> tuple[bool, int]:
    formula_hits = len(_FORMULA_RE.findall(text))
    if formula_hits <= 0:
        return False, 0
    if formula_hits >= 4 or text.count("=") >= 3 or "\\frac" in text or "\\sqrt" in text:
        return True, 32
    if formula_hits >= 2:
        return True, 26
    return False, 14


@dataclass(frozen=True, slots=True)
class RegionRiskDecision:
    question_number: int
    kind: str
    page_number: int
    bbox: tuple[float, float, float, float]
    score: int
    suspicious: bool
    hard_math: bool
    signals: tuple[str, ...]
    region_issues: tuple[str, ...]
    candidate_text: str

    @property
    def target_id(self) -> str:
        prefix = "q" if self.kind == "question" else "s"
        return f"{prefix}-{self.question_number:03d}-p{self.page_number:03d}"

    def safe_dict(self) -> dict[str, Any]:
        return {
            "targetId": self.target_id,
            "questionNumber": self.question_number,
            "kind": self.kind,
            "pageNumber": self.page_number,
            "bbox": list(self.bbox),
            "score": self.score,
            "suspicious": self.suspicious,
            "hardMath": self.hard_math,
            "signals": list(self.signals),
            "regionIssues": list(self.region_issues),
        }


def score_region_risks(
    *,
    projection: Mapping[str, Any],
    layout: Mapping[str, Any],
    recovered_solution_targets: Sequence[int] | set[int] = (),
    unresolved_solution_targets: Sequence[int] | set[int] = (),
) -> list[RegionRiskDecision]:
    """Assign a score to every numbered question/solution region.

    Formula/digit/scientific signals alone stay below threshold unless the math
    is genuinely dense. Strong defects are region-specific so a question option
    parse issue cannot accidentally trigger a second call for its clean solution.
    """

    questions = _question_map(projection)
    recovered = {int(value) for value in recovered_solution_targets}
    unresolved = {int(value) for value in unresolved_solution_targets}
    threshold = _threshold()
    decisions: list[RegionRiskDecision] = []

    for page in layout.get("pages") or []:
        if not isinstance(page, Mapping):
            continue
        page_number = _number(page.get("originalPageNumber"))
        for region in page.get("regions") or []:
            if not isinstance(region, Mapping):
                continue
            kind = str(region.get("kind") or "")
            if kind not in {"question", "solution"}:
                continue
            number = _number(region.get("questionNumber"))
            box = _bbox(region.get("bbox"))
            question = questions.get(number)
            if page_number < 1 or number < 1 or box is None or question is None:
                continue

            raw_text = clean_exam_markdown(region.get("text") or "")
            candidate = _candidate_text(question, kind)
            combined = "\n".join(value for value in (raw_text, candidate) if value)
            region_codes = _codes(list(region.get("issues") or []))
            question_codes = _codes(list(question.get("issues") or []))
            signals: list[str] = []
            score = 0

            hard_math, formula_score = _hard_math_score(combined)
            if formula_score:
                score += formula_score
                signals.append("formula_math")
            if _DIGIT_RE.search(combined.translate(_DIGITS)) and _UNIT_RE.search(combined):
                score += 8
                signals.append("digits_units")
            if _SCIENTIFIC_RE.search(combined):
                score += 5
                signals.append("scientific_terminology")

            if bool(region_codes & VISUAL_CRITICAL_ISSUE_CODES) or _visual_critical_for_kind(question, kind):
                score += 50
                signals.append("visual_anomaly")

            if kind == "solution":
                label = clean_exam_markdown(question.get("correct_option_label") or "").translate(_DIGITS)
                if label not in {"1", "2", "3", "4"} or bool(question_codes & _MISSING_ANSWER_ISSUES):
                    score += 55
                    signals.append("missing_invalid_answer")
            elif len([item for item in (question.get("options") or []) if isinstance(item, Mapping)]) != 4:
                score += 45
                signals.append("missing_invalid_answer")

            heading_conflict = (
                bool(region_codes & _HEADING_ISSUES)
                or bool(region.get("numberRecoveredFromSequence"))
                or number in recovered
                or number in unresolved
            )
            if heading_conflict:
                score += 50 if number in unresolved else 40
                signals.append("heading_conflict")

            if kind == "question":
                disagreement = bool(question_codes & _QUESTION_DISAGREEMENT_ISSUES)
            else:
                disagreement = bool(question_codes & _SOLUTION_DISAGREEMENT_ISSUES)
            if disagreement:
                score += 35
                signals.append("ocr_disagreement")

            corruption_text = "\n".join(value for value in (raw_text, candidate) if value)
            corrupted = (
                has_broken_persian_text(corruption_text)
                or has_duplicate_clean_and_broken_text(corruption_text)
                or _SOURCE_CORRUPTION_RE.search(corruption_text) is not None
            )
            if corrupted:
                score += 50
                signals.append("source_corruption")

            score = min(100, score)
            decisions.append(
                RegionRiskDecision(
                    question_number=number,
                    kind=kind,
                    page_number=page_number,
                    bbox=box,
                    score=score,
                    suspicious=score >= threshold,
                    hard_math=hard_math,
                    signals=tuple(dict.fromkeys(signals)),
                    region_issues=tuple(sorted(region_codes)),
                    candidate_text=candidate,
                )
            )

    return sorted(
        decisions,
        key=lambda item: (
            -item.score,
            item.page_number,
            item.question_number,
            0 if item.kind == "question" else 1,
        ),
    )


__all__ = ["RegionRiskDecision", "score_region_risks"]
