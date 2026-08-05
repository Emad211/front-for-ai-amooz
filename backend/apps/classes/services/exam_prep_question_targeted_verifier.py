"""Cost-bounded source verification for suspicious exam questions only.

Clean assembled questions incur no provider call. A suspicious question receives
at most one source-crop audit request with no structured-output repair and no
outer retry. Source verification is optional evidence, not a prerequisite for
publishing an otherwise clean question.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from apps.commons.llm_prompts import PROMPTS
from apps.commons.models import LLMUsageLog
from apps.commons.structured_llm import StructuredOutputError, generate_structured

from .exam_prep_page_extractor import RenderedExamPage
from .exam_prep_page_output import is_critical_page_issue
from .exam_prep_page_records import PageAssemblyResult
from .exam_prep_question_cleanup import cleanup_assembled_question
from .exam_prep_question_full_verifier import (
    SourceCrop,
    VerifiedQuestionAudit,
    _apply_audit,
    _count_answer_resolved,
    _crop_parts,
    _final_question_issues,
    _inline_visual,
    _question_number,
    _rebuild_result,
    build_question_source_crops,
)
from .exam_prep_question_verifier import canonical_question_issues
from .exam_prep_utils import clean_exam_markdown


logger = logging.getLogger("apps.classes.exam_prep")

_TARGETED_ISSUE_CODES = frozenset(
    {
        "missing_question_text",
        "missing_options",
        "missing_option_text",
        "missing_solution_text",
        "missing_answer",
        "placeholder_option_text",
        "unexpected_option_count",
        "duplicate_option_label",
        "correct_option_not_in_options",
        "conflicting_correct_option",
        "conflicting_correct_option_text",
        "broken_persian_text",
        "duplicate_mixed_text",
        "solution_semantic_mismatch_candidate",
        "low_confidence",
        "visual_evidence_required",
        "visual_attachment_missing",
        "table_incomplete",
        "count_answer_unresolved",
        "source_verification_failed",
        "targeted_repair_unresolved",
        "targeted_repair_failed",
        "targeted_repair_no_source_page",
    }
)
_STALE_VERIFICATION_CODES = frozenset(
    {
        "source_verification_failed",
        "targeted_repair_unresolved",
        "targeted_repair_failed",
        "targeted_repair_no_source_page",
        "count_answer_unresolved",
        "visual_attachment_missing",
        "table_incomplete",
    }
)
_TABLE_REFERENCE_RE = re.compile(
    r"(?:با\s+توجه\s+به\s+جدول|مطابق\s+جدول|براساس\s+جدول|"
    r"جدول\s+(?:مقابل|زیر|بالا|نشان\s+داده\s+شده))",
    flags=re.IGNORECASE,
)


def _positive_int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _positive_float_env(name: str, default: float) -> float:
    try:
        return max(0.0, float(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _issue_codes(question: dict[str, Any]) -> list[str]:
    return [
        clean_exam_markdown(value).strip()
        for value in (question.get("issues") or [])
        if clean_exam_markdown(value).strip()
    ]


def _prepare_question(
    raw_question: dict[str, Any],
) -> tuple[dict[str, Any], bool, bool]:
    """Run free cleanup, recompute issues, and decide whether a model call is needed."""

    original_codes = set(_issue_codes(raw_question))
    question, deterministic_changed = cleanup_assembled_question(raw_question)
    question["issues"] = [
        code for code in _issue_codes(question) if code not in _STALE_VERIFICATION_CODES
    ]
    canonical = canonical_question_issues(question)
    question["issues"] = canonical

    text = clean_exam_markdown(question.get("question_text_markdown") or "")
    required = bool((original_codes | set(canonical)) & _TARGETED_ISSUE_CODES)
    required = required or not _count_answer_resolved(question)
    required = required or _TABLE_REFERENCE_RE.search(text) is not None
    return question, deterministic_changed, required


def question_requires_source_check(question: dict[str, Any]) -> bool:
    """Return true only for a question with concrete source-sensitive defects."""

    _prepared, _changed, required = _prepare_question(question)
    return required


def _question_page_numbers(question: dict[str, Any]) -> set[int]:
    numbers: set[int] = set()
    for region in question.get("source_regions") or []:
        if not isinstance(region, dict):
            continue
        try:
            value = int(region.get("page_number") or 0)
        except (TypeError, ValueError):
            continue
        if value > 0:
            numbers.add(value)
    for raw in question.get("source_pages") or []:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value > 0:
            numbers.add(value)
    return numbers


def targeted_source_page_numbers(result: PageAssemblyResult) -> set[int]:
    """Re-render only pages used by the bounded suspicious-question set."""

    maximum = _positive_int_env("EXAM_PREP_MAX_TARGETED_QUESTION_VERIFICATIONS", 20)
    numbers: set[int] = set()
    selected = 0
    questions = (result.projection.get("exam_prep") or {}).get("questions") or []
    for raw_question in questions:
        if not isinstance(raw_question, dict):
            continue
        question, _changed, required = _prepare_question(raw_question)
        if not required:
            continue
        if selected >= maximum:
            break
        selected += 1
        numbers.update(_question_page_numbers(question))
    return numbers


def _verify_question_once(
    question: dict[str, Any],
    *,
    crops: list[SourceCrop],
    model: str,
) -> VerifiedQuestionAudit:
    """Make exactly one provider request: no schema repair and no retry."""

    number = _question_number(question)
    if number < 1:
        raise ValueError("A positive question number is required.")
    current = json.dumps(question, ensure_ascii=False, separators=(",", ":"))
    result = generate_structured(
        schema=VerifiedQuestionAudit,
        messages=[
            {
                "role": "system",
                "content": PROMPTS["exam_prep_question_audit"]["default"],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"REQUESTED_QUESTION_NUMBER: {number}\n"
                            "VERIFICATION_ATTEMPT: 1\n"
                            "CURRENT_ASSEMBLED_QUESTION_BEGIN\n"
                            f"{current}\n"
                            "CURRENT_ASSEMBLED_QUESTION_END"
                        ),
                    },
                    *_crop_parts(crops),
                ],
            },
        ],
        model=model,
        feature=LLMUsageLog.Feature.PDF_EXTRACTION,
        timeout=_positive_float_env("EXAM_PREP_QUESTION_AUDIT_TIMEOUT_SECONDS", 180.0),
        temperature=0,
        max_repair=0,
        strict_json_schema=True,
        sensitive=True,
        max_output_tokens=_positive_int_env(
            "EXAM_PREP_TARGETED_QUESTION_AUDIT_MAX_OUTPUT_TOKENS",
            6_000,
        ),
        detail="exam_prep_question_source_audit",
        tracking_context={
            "stage": "question_source_audit",
            "question_number": number,
            "attempt": 1,
            "targeted": 1,
            "source_crop_count": len(crops),
        },
        provider_attempts=1,
    )
    if result.question_number != number:
        raise StructuredOutputError(
            f"Question audit returned {result.question_number}, expected {number}.",
            error_kind="question_number_mismatch",
        )
    return result


def _attach_visual_if_needed(
    question: dict[str, Any],
    *,
    audit: VerifiedQuestionAudit,
    crops: list[SourceCrop],
) -> tuple[dict[str, Any], bool]:
    if not audit.visual_required:
        return question, False
    question_crop = next((crop for crop in crops if crop.role == "question"), None)
    if question_crop is None or question_crop.bbox is None:
        return question, False
    updated = dict(question)
    updated["visuals"] = [
        _inline_visual(
            question_crop,
            question_id=str(question.get("question_id") or _question_number(question)),
        )
    ]
    return updated, True


def verify_suspicious_questions(
    result: PageAssemblyResult,
    *,
    source_pages_by_number: dict[int, RenderedExamPage],
    model: str,
) -> tuple[PageAssemblyResult, dict[str, int]]:
    """Audit only suspicious questions, at most once each."""

    questions = [
        item
        for item in (result.projection.get("exam_prep") or {}).get("questions") or []
        if isinstance(item, dict)
    ]
    maximum = _positive_int_env("EXAM_PREP_MAX_TARGETED_QUESTION_VERIFICATIONS", 20)
    threshold = _positive_float_env("EXAM_PREP_QUESTION_VERIFICATION_CONFIDENCE", 0.78)
    attempted = verified_count = repaired = unresolved = 0
    visuals_attached = tables_verified = skipped = selected = 0
    output: list[dict[str, Any]] = []

    for raw_question in questions:
        question, deterministic_changed, required = _prepare_question(raw_question)
        if not required:
            metadata = dict(question.get("verification_metadata") or {})
            metadata.update({"required": False, "attempts": 0})
            question["verification_metadata"] = metadata
            question["issues"] = canonical_question_issues(question)
            output.append(question)
            continue

        if selected >= maximum:
            metadata = dict(question.get("verification_metadata") or {})
            metadata.update({"required": True, "attempts": 0, "skipped_by_cost_cap": True})
            question["verification_metadata"] = metadata
            question["issues"] = canonical_question_issues(question)
            output.append(question)
            skipped += 1
            continue

        selected += 1
        crops = build_question_source_crops(question, pages=source_pages_by_number)
        if not crops:
            question["verification_metadata"] = {
                "required": True,
                "source_supported": False,
                "fields_match_source": False,
                "attempts": 0,
                "source_pages": [],
            }
            question["source_verified"] = False
            question["issues"] = _final_question_issues(question, verified=False)
            output.append(question)
            unresolved += 1
            continue

        attempted += 1
        first_snapshot = json.dumps(question, ensure_ascii=False, sort_keys=True)
        try:
            audit = _verify_question_once(question, crops=crops, model=model)
        except Exception as exc:
            logger.warning(
                "exam_prep.question.audit_failed questionNumber=%s attempt=1 errorCode=%s",
                _question_number(question),
                type(exc).__name__,
            )
            metadata = dict(question.get("verification_metadata") or {})
            metadata.update(
                {
                    "required": True,
                    "source_supported": False,
                    "fields_match_source": False,
                    "attempts": 1,
                    "source_pages": [crop.page_number for crop in crops],
                    "source_bboxes": [
                        crop.bbox.model_dump() if crop.bbox else None for crop in crops
                    ],
                }
            )
            question["verification_metadata"] = metadata
            question["source_verified"] = False
            question["issues"] = _final_question_issues(question, verified=False)
            output.append(question)
            unresolved += 1
            continue

        question = _apply_audit(question, audit)
        metadata = dict(question.get("verification_metadata") or {})
        metadata.update(
            {
                "required": True,
                "attempts": 1,
                "source_pages": [crop.page_number for crop in crops],
                "source_bboxes": [
                    crop.bbox.model_dump() if crop.bbox else None for crop in crops
                ],
            }
        )
        question["verification_metadata"] = metadata
        question, attached = _attach_visual_if_needed(question, audit=audit, crops=crops)
        visuals_attached += int(attached)
        tables_verified += int(audit.table_required and audit.table_complete)

        source_supported = bool(audit.source_supported and audit.confidence >= threshold)
        issues = _final_question_issues(question, verified=source_supported)
        final_verified = source_supported and not any(
            is_critical_page_issue(code) for code in issues
        )
        if not final_verified:
            issues = _final_question_issues(question, verified=False)
        question["source_verified"] = final_verified
        question["issues"] = issues

        final_snapshot = json.dumps(question, ensure_ascii=False, sort_keys=True)
        changed = deterministic_changed or first_snapshot != final_snapshot
        if final_verified:
            verified_count += 1
            repaired += int(changed)
        else:
            unresolved += 1
        output.append(question)

    rebuilt = _rebuild_result(result, questions=output)
    return rebuilt, {
        "attempted": attempted,
        "verified": verified_count,
        "repaired": repaired,
        "retried": 0,
        "unresolved": unresolved,
        "visuals_attached": visuals_attached,
        "tables_verified": tables_verified,
        "skipped": skipped,
    }
