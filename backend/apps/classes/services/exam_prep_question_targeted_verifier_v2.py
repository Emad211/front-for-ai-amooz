"""Cancellation-aware targeted verification with concrete-defect gating."""
from __future__ import annotations

import json
import logging
from typing import Any, Callable

from .exam_prep_page_extractor import RenderedExamPage
from .exam_prep_page_output import is_critical_page_issue
from .exam_prep_page_records import PageAssemblyResult
from .exam_prep_question_full_verifier import (
    _apply_audit,
    _final_question_issues,
    _question_number,
    _rebuild_result,
    build_question_source_crops,
)
from .exam_prep_question_targeted_verifier import (
    _attach_visual_if_needed,
    _positive_float_env,
    _positive_int_env,
    _prepare_question,
    _question_page_numbers,
    _verify_question_once,
)
from .exam_prep_question_verifier import canonical_question_issues
from .exam_prep_utils import clean_exam_markdown


logger = logging.getLogger("apps.classes.exam_prep")
CancelCheck = Callable[[], bool]
_NEW_TARGETED_CODES = {
    "serialized_option_payload",
    "missing_correct_option_label",
    "duplicate_solution_across_questions",
}
_NON_CONCRETE_FAILURE_CODES = {
    "source_verification_failed",
    "targeted_repair_failed",
    "targeted_repair_unresolved",
    "targeted_repair_no_source_page",
}


class TargetedVerificationCancelled(RuntimeError):
    pass


def _raise_if_cancelled(should_cancel: CancelCheck | None) -> None:
    if should_cancel is not None and should_cancel():
        logger.info("exam_prep.question.cancelled_before_next_call")
        raise TargetedVerificationCancelled(
            "Cancellation requested during targeted verification."
        )


def _prepare_v2(
    raw_question: dict[str, Any],
) -> tuple[dict[str, Any], bool, bool]:
    question, changed, required = _prepare_question(raw_question)
    codes = {
        clean_exam_markdown(code).strip()
        for code in (question.get("issues") or [])
        if clean_exam_markdown(code).strip()
    }
    return question, changed, required or bool(codes & _NEW_TARGETED_CODES)


def targeted_source_page_numbers(
    result: PageAssemblyResult,
    *,
    should_cancel: CancelCheck | None = None,
) -> set[int]:
    maximum = _positive_int_env(
        "EXAM_PREP_MAX_TARGETED_QUESTION_VERIFICATIONS",
        20,
    )
    selected = 0
    numbers: set[int] = set()
    for raw_question in (result.projection.get("exam_prep") or {}).get(
        "questions"
    ) or []:
        _raise_if_cancelled(should_cancel)
        if not isinstance(raw_question, dict):
            continue
        question, _changed, required = _prepare_v2(raw_question)
        if not required:
            continue
        if selected >= maximum:
            break
        selected += 1
        numbers.update(_question_page_numbers(question))
    return numbers


def _without_non_concrete_failure(issues: list[str]) -> list[str]:
    return [code for code in issues if code not in _NON_CONCRETE_FAILURE_CODES]


def _clear_recomputed_integrity_codes(question: dict[str, Any]) -> None:
    """Drop pre-audit integrity markers; the final integrity pass re-derives them."""

    question["issues"] = [
        clean_exam_markdown(code).strip()
        for code in (question.get("issues") or [])
        if clean_exam_markdown(code).strip()
        and clean_exam_markdown(code).strip() not in _NEW_TARGETED_CODES
    ]


def verify_suspicious_questions(
    result: PageAssemblyResult,
    *,
    source_pages_by_number: dict[int, RenderedExamPage],
    model: str,
    should_cancel: CancelCheck | None = None,
) -> tuple[PageAssemblyResult, dict[str, int]]:
    """Audit only concrete suspicious questions and check cancel before calls."""

    questions = [
        item
        for item in (result.projection.get("exam_prep") or {}).get("questions") or []
        if isinstance(item, dict)
    ]
    maximum = _positive_int_env(
        "EXAM_PREP_MAX_TARGETED_QUESTION_VERIFICATIONS",
        20,
    )
    threshold = _positive_float_env(
        "EXAM_PREP_QUESTION_VERIFICATION_CONFIDENCE",
        0.78,
    )
    attempted = verified_count = repaired = unresolved = 0
    visuals_attached = tables_verified = skipped = selected = 0
    output: list[dict[str, Any]] = []

    for raw_question in questions:
        _raise_if_cancelled(should_cancel)
        question, deterministic_changed, required = _prepare_v2(raw_question)
        if not required:
            metadata = dict(question.get("verification_metadata") or {})
            metadata.update({"required": False, "attempts": 0})
            question["verification_metadata"] = metadata
            question["issues"] = canonical_question_issues(question)
            output.append(question)
            continue

        if selected >= maximum:
            metadata = dict(question.get("verification_metadata") or {})
            metadata.update(
                {
                    "required": True,
                    "attempts": 0,
                    "skipped_by_cost_cap": True,
                }
            )
            question["verification_metadata"] = metadata
            question["issues"] = canonical_question_issues(question)
            output.append(question)
            skipped += 1
            continue

        selected += 1
        _raise_if_cancelled(should_cancel)
        crops = build_question_source_crops(
            question,
            pages=source_pages_by_number,
        )
        _raise_if_cancelled(should_cancel)
        if not crops:
            question["verification_metadata"] = {
                "required": True,
                "source_supported": False,
                "fields_match_source": False,
                "attempts": 0,
                "source_pages": [],
            }
            question["source_verified"] = False
            question["issues"] = _without_non_concrete_failure(
                _final_question_issues(question, verified=False)
            )
            output.append(question)
            unresolved += int(
                any(is_critical_page_issue(code) for code in question["issues"])
            )
            continue

        attempted += 1
        first_snapshot = json.dumps(
            question,
            ensure_ascii=False,
            sort_keys=True,
        )
        _raise_if_cancelled(should_cancel)
        try:
            audit = _verify_question_once(
                question,
                crops=crops,
                model=model,
            )
        except Exception as exc:
            logger.warning(
                "exam_prep.question.audit_failed questionNumber=%s attempt=1 "
                "errorCode=%s",
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
                        crop.bbox.model_dump() if crop.bbox else None
                        for crop in crops
                    ],
                }
            )
            question["verification_metadata"] = metadata
            question["source_verified"] = False
            question["issues"] = _without_non_concrete_failure(
                _final_question_issues(question, verified=False)
            )
            output.append(question)
            unresolved += int(
                any(is_critical_page_issue(code) for code in question["issues"])
            )
            continue

        _raise_if_cancelled(should_cancel)
        question = _apply_audit(question, audit)
        _clear_recomputed_integrity_codes(question)
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
        question, attached = _attach_visual_if_needed(
            question,
            audit=audit,
            crops=crops,
        )
        visuals_attached += int(attached)
        tables_verified += int(audit.table_required and audit.table_complete)

        source_supported = bool(
            audit.source_supported and audit.confidence >= threshold
        )
        issues = _final_question_issues(
            question,
            verified=source_supported,
        )
        final_verified = source_supported and not any(
            is_critical_page_issue(code) for code in issues
        )
        if not final_verified:
            issues = _without_non_concrete_failure(
                _final_question_issues(question, verified=False)
            )
        question["source_verified"] = final_verified
        question["issues"] = issues

        final_snapshot = json.dumps(
            question,
            ensure_ascii=False,
            sort_keys=True,
        )
        changed = deterministic_changed or first_snapshot != final_snapshot
        if final_verified:
            verified_count += 1
            repaired += int(changed)
        else:
            unresolved += int(
                any(is_critical_page_issue(code) for code in issues)
            )
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
        "cancelled_before_call": 0,
    }
