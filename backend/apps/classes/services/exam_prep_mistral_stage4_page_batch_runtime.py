"""Production wrapper for page-batched Stage 4 candidate comparisons.

The underlying page-batch orchestrator is kept compact and stable. This wrapper
installs three deterministic production guards before exposing it:

* compare exactly the canonical candidate field-set rather than a flattened
  answer blob;
* do not broaden an option-only OCR disagreement into a stem replacement;
* treat absent provider fields as unavailable evidence, so a missing required
  field fails closed instead of being counted as a successful verification.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from . import exam_prep_mistral_stage4_page_batch as _impl
from . import exam_prep_mistral_stage4 as _legacy
from .exam_prep_mistral_risk_engine_v2 import score_region_risks as _score
from .exam_prep_utils import clean_exam_markdown


def _number(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _question_map(projection: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    exam = projection.get("exam_prep")
    questions = exam.get("questions") if isinstance(exam, Mapping) else []
    output: dict[int, Mapping[str, Any]] = {}
    for question in questions or []:
        if not isinstance(question, Mapping):
            continue
        number = _number(question.get("source_question_number"))
        if number > 0:
            output[number] = question
    return output


def _normalized_score_region_risks(*, projection, **kwargs):
    decisions = _score(projection=projection, **kwargs)
    questions = _question_map(projection)
    output = []
    for decision in decisions:
        question = questions.get(decision.question_number)
        if question is None:
            output.append(decision)
            continue
        if decision.kind == "question":
            candidate = _legacy._question_payload_text(question)
        else:
            candidate = _legacy._solution_payload_text(question)
        output.append(replace(decision, candidate_text=candidate))
    return output


def _needed_fields(decision, question, payload):
    """Return all fields that need source repair, even when provider omitted one."""

    issues = {str(code) for code in (question.get("issues") or []) if str(code)}
    issues.update(str(code) for code in decision.region_issues if str(code))
    signals = set(decision.signals)
    available = _impl._valid_source_fields(decision, payload)

    if decision.kind == "question":
        needed: set[str] = set()
        if (
            not clean_exam_markdown(question.get("question_text_markdown") or "")
            or issues & _impl._STEM_ISSUES
        ):
            needed.add("question_text_markdown")
        option_map = {
            str(item.get("label") or "").translate(_impl._DIGITS).strip(): clean_exam_markdown(
                item.get("text_markdown") or ""
            )
            for item in (question.get("options") or [])
            if isinstance(item, Mapping)
        }
        if issues & _impl._OPTION_ISSUES or set(option_map) != {"1", "2", "3", "4"}:
            needed.update({"option_1", "option_2", "option_3", "option_4"})
        else:
            for label in ("1", "2", "3", "4"):
                if not option_map.get(label):
                    needed.add(f"option_{label}")

        if signals & _impl._CORRUPTION_SIGNALS:
            needed.update(available)
        elif "ocr_disagreement" in signals and not (issues & _impl._OPTION_ISSUES):
            # A parser failure confined to options is not permission to replace a
            # source-clean stem. For broad OCR disagreement, all available fields
            # remain eligible.
            needed.update(available)
        return needed

    needed: set[str] = set()
    existing_label = _impl._normalize_label(question.get("correct_option_label"))
    if existing_label not in {"1", "2", "3", "4"} or issues & _impl._LABEL_ISSUES:
        needed.add("correct_option_label")
    if (
        not clean_exam_markdown(question.get("teacher_solution_markdown") or "")
        or issues & _impl._SOLUTION_BODY_ISSUES
    ):
        needed.add("teacher_solution_markdown")
    if signals & _impl._CORRUPTION_SIGNALS:
        needed.add("teacher_solution_markdown")
    if "ocr_disagreement" in signals:
        needed.update(available)
    if signals & {"missing_invalid_answer", "heading_conflict"}:
        needed.add("correct_option_label")
    return needed


_ORIGINAL_SANITIZE_ITEM = _impl._sanitize_item


def _sanitize_item_with_absence(item):
    """An omitted canonical field is unavailable source evidence, not success."""

    payload, blocked, flags = _ORIGINAL_SANITIZE_ITEM(item)
    blocked = set(blocked)
    if item.kind == "question":
        if not clean_exam_markdown(payload.get("question_text_markdown") or ""):
            blocked.add("question_text_markdown")
        labels = {
            str(raw.get("label") or "").translate(_impl._DIGITS).strip()
            for raw in (payload.get("options") or [])
            if isinstance(raw, Mapping) and clean_exam_markdown(raw.get("text_markdown") or "")
        }
        for label in ("1", "2", "3", "4"):
            if label not in labels:
                blocked.add(f"option_{label}")
    else:
        if _impl._normalize_label(payload.get("correct_option_label")) not in {"1", "2", "3", "4"}:
            blocked.add("correct_option_label")
        if not clean_exam_markdown(payload.get("teacher_solution_markdown") or ""):
            blocked.add("teacher_solution_markdown")
    return payload, blocked, flags


# The orchestrator resolves these helpers from its module namespace. Install the
# corrected deterministic views without copying its provider/cost orchestration.
_impl.score_region_risks = _normalized_score_region_risks
_impl._needed_fields = _needed_fields
_impl._sanitize_item = _sanitize_item_with_absence

verify_and_repair_risky_regions_page_batched = (
    _impl.verify_and_repair_risky_regions_page_batched
)
PageBatchStats = _impl.PageBatchStats

__all__ = [
    "PageBatchStats",
    "verify_and_repair_risky_regions_page_batched",
]
