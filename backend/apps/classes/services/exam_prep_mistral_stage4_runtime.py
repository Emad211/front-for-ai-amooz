"""Production-safe Stage-4 facade preserving Stage-3 visual authority.

Production Stage 4 now groups all suspicious source crops from the same physical
page into one Gemini request.  This facade then re-applies the two publication
safety rules that remain independent of provider transport:

1. remove visual-only issue codes reintroduced by legacy text-quality helpers
   when the immutable Stage-3 visual contract proves the evidence is healthy;
2. recompute the Stage-4 machine blocker from all region statuses of a question
   so a successful repair cannot hide another unresolved region.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping

from .exam_prep_mistral_stage4_page_batch_runtime import (
    PageBatchStats,
    verify_and_repair_risky_regions_page_batched,
)
from .exam_prep_mistral_visual_review import (
    visual_metadata_issue_codes,
    visual_options_complete,
)
from .exam_prep_page_records import PageAssemblyResult


_STAGE4_BLOCKER = "stage4_verification_unresolved"
_VISUAL_REFERENCE_STALE = frozenset(
    {
        "visual_evidence_required",
        "visual_attachment_missing",
        "visual_reference_without_ocr_visual",
    }
)
_VISUAL_OPTION_STALE = frozenset(
    {
        "missing_options",
        "missing_option_text",
        "missing_options_text",
        "placeholder_option_text",
        "unexpected_option_count",
        "mistral_question_option_parse_failed",
    }
)
_STAGE4_FAILURE_STATUSES = frozenset(
    {
        "deferred_cost_cap",
        "provider_failed",
        "source_uncertain",
        "primary_invalid",
        "unresolved",
        "secondary_failed",
        "secondary_uncertain",
        "second_opinion_disagreement",
    }
)


def _number(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _has_usable_question_visual(question: Mapping[str, Any]) -> bool:
    return any(
        isinstance(asset, Mapping)
        and str(asset.get("role") or "") in {"question", "option"}
        and asset.get("reviewOnly") is not True
        and isinstance(asset.get("sanity"), Mapping)
        and str(asset["sanity"].get("status") or "") == "passed"
        for asset in (question.get("visuals") or [])
    )


def _failed_question_numbers(audit: Mapping[str, Any]) -> set[int]:
    statuses: dict[int, list[str]] = defaultdict(list)
    for row in audit.get("regions") or []:
        if not isinstance(row, Mapping):
            continue
        number = _number(row.get("questionNumber"))
        if number < 1:
            continue
        statuses[number].append(str(row.get("status") or ""))
    return {
        number
        for number, values in statuses.items()
        if any(value in _STAGE4_FAILURE_STATUSES or value in {"", "pending"} for value in values)
    }


def _restore_authority(
    result: PageAssemblyResult,
    *,
    audit: Mapping[str, Any],
) -> PageAssemblyResult:
    failed_numbers = _failed_question_numbers(audit)
    projection = dict(result.projection)
    exam = dict(projection.get("exam_prep") or {})
    questions: list[dict[str, Any]] = []
    for raw in exam.get("questions") or []:
        if not isinstance(raw, Mapping):
            continue
        question = dict(raw)
        number = _number(question.get("source_question_number"))
        codes = [str(code) for code in (question.get("issues") or []) if str(code)]

        if number in failed_numbers:
            if _STAGE4_BLOCKER not in codes:
                codes.append(_STAGE4_BLOCKER)
        else:
            codes = [code for code in codes if code != _STAGE4_BLOCKER]

        visual_blockers = visual_metadata_issue_codes(question)
        if _has_usable_question_visual(question) and not visual_blockers:
            codes = [code for code in codes if code not in _VISUAL_REFERENCE_STALE]
        if visual_options_complete(question) and not visual_blockers:
            codes = [code for code in codes if code not in _VISUAL_OPTION_STALE]
        question["issues"] = list(dict.fromkeys(codes))
        questions.append(question)

    exam["questions"] = questions
    projection["exam_prep"] = exam
    return result.model_copy(update={"projection": projection})


def _restore_visual_authority(result: PageAssemblyResult) -> PageAssemblyResult:
    """Compatibility helper retained for focused Stage-3/4 visual tests."""

    return _restore_authority(result, audit={"regions": []})


def verify_and_repair_risky_regions(*args, **kwargs):
    result, audit = verify_and_repair_risky_regions_page_batched(*args, **kwargs)
    return _restore_authority(result, audit=audit), audit


Stage4Stats = PageBatchStats

__all__ = ["Stage4Stats", "verify_and_repair_risky_regions"]
