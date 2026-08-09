"""Production-safe Stage-4 facade preserving Stage-3 visual authority.

The Stage-4 implementation intentionally reuses an older assembly-quality helper
for text fields. That helper predates precise Stage-3 source visuals and may
re-introduce `visual_evidence_required` / empty-option-text issues after an
otherwise valid text repair. This narrow facade removes only those stale codes
when the immutable Stage-3 visual contract proves the visual evidence is healthy.
"""
from __future__ import annotations

from typing import Any, Mapping

from . import exam_prep_mistral_stage4 as _impl
from .exam_prep_mistral_visual_review import (
    visual_metadata_issue_codes,
    visual_options_complete,
)
from .exam_prep_page_records import PageAssemblyResult


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


def _has_usable_question_visual(question: Mapping[str, Any]) -> bool:
    return any(
        isinstance(asset, Mapping)
        and str(asset.get("role") or "") in {"question", "option"}
        and asset.get("reviewOnly") is not True
        and isinstance(asset.get("sanity"), Mapping)
        and str(asset["sanity"].get("status") or "") == "passed"
        for asset in (question.get("visuals") or [])
    )


def _restore_visual_authority(result: PageAssemblyResult) -> PageAssemblyResult:
    projection = dict(result.projection)
    exam = dict(projection.get("exam_prep") or {})
    questions: list[dict[str, Any]] = []
    for raw in exam.get("questions") or []:
        if not isinstance(raw, Mapping):
            continue
        question = dict(raw)
        codes = [str(code) for code in (question.get("issues") or []) if str(code)]
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


def verify_and_repair_risky_regions(*args, **kwargs):
    result, audit = _impl.verify_and_repair_risky_regions(*args, **kwargs)
    return _restore_visual_authority(result), audit


Stage4Stats = _impl.Stage4Stats

__all__ = ["Stage4Stats", "verify_and_repair_risky_regions"]
