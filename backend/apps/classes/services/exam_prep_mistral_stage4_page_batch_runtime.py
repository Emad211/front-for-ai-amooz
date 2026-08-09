"""Small production wrapper for page-batched Stage 4 candidate comparisons.

Risk decisions carry a broad assembled candidate text.  For solution regions that
text may include ``final_answer_markdown`` in addition to the worked solution,
while the new structured Gemini payload compares only ``teacher_solution_markdown``.
An extra answer-label digit must not manufacture a numeric disagreement and buy a
GPT second opinion.  Normalize the candidate to the exact field-set being compared
before handing decisions to the page-batch orchestrator.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from . import exam_prep_mistral_stage4_page_batch as _impl
from . import exam_prep_mistral_stage4 as _legacy
from .exam_prep_mistral_risk_engine_v2 import score_region_risks as _score


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


# The orchestrator resolves the selector from its module namespace. Install the
# normalized candidate view without duplicating the page-batch implementation.
_impl.score_region_risks = _normalized_score_region_risks

verify_and_repair_risky_regions_page_batched = (
    _impl.verify_and_repair_risky_regions_page_batched
)
PageBatchStats = _impl.PageBatchStats

__all__ = [
    "PageBatchStats",
    "verify_and_repair_risky_regions_page_batched",
]
