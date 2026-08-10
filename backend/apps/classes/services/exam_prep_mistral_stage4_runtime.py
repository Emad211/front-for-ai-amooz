"""Production-safe Stage-4 facade preserving Stage-3 visual authority.

Production Stage 4 groups suspicious source crops by physical page, then applies
only deterministic or independent-source safety gates. Final projection metadata
is rebuilt from the post-guard audit so rollback decisions cannot leave stale
embedded verification state.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping

from .exam_prep_mistral_page_batch_transcriber_v4 import install_stage4_transport_policy
from .exam_prep_mistral_stage4_field_safety import sanitize_source_markdown
from .exam_prep_mistral_stage4_hard_question_guard import (
    enforce_hard_question_numeric_consensus,
)
from .exam_prep_mistral_stage4_page_batch_runtime import (
    PageBatchStats,
    verify_and_repair_risky_regions_page_batched,
)
from .exam_prep_mistral_stage4_pathological_guard import (
    enforce_pathological_repair_consensus,
)
from .exam_prep_mistral_stage4_source_invariant_guard import (
    enforce_source_invariants,
)
from .exam_prep_mistral_targeted_recovery_policy import (
    install_targeted_recovery_policy,
)
from .exam_prep_mistral_visual_review import (
    visual_metadata_issue_codes,
    visual_options_complete,
)
from .exam_prep_page_records import PageAssemblyResult
from .exam_prep_question_verifier import rebuild_assembly_quality


# Stage-4 transport belongs here, not in the Stage-3 visual facade. Keeping this
# installation at the Stage-4 seam avoids the risk_engine -> visual -> transport
# import cycle while preserving one production/acceptance request contract.
install_stage4_transport_policy()
install_targeted_recovery_policy()

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
        "partial_repair_source_uncertain",
        "primary_invalid",
        "unresolved",
        "secondary_failed",
        "secondary_uncertain",
        "secondary_no_vote",
        "second_opinion_disagreement",
        "source_anchor_conflict_rolled_back",
        "solution_source_invariant_rolled_back",
        "pathological_partial_repair_rolled_back",
        "pathological_unresolved",
        "pathological_consensus_unavailable",
        "pathological_consensus_failed",
        "pathological_consensus_uncertain",
        "pathological_consensus_disagreement",
        "hard_question_numeric_consensus_unavailable",
        "hard_question_numeric_consensus_failed",
        "hard_question_numeric_consensus_uncertain",
        "hard_question_numeric_consensus_disagreement",
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
    return _restore_authority(result, audit={"regions": []})


def _sanitize_final_question(question: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Apply the same deterministic sanitizer to every final canonical text field."""

    updated = dict(question)
    flags: list[str] = []
    stem, found = sanitize_source_markdown(updated.get("question_text_markdown") or "")
    updated["question_text_markdown"] = stem
    flags.extend(found)

    options: list[dict[str, Any]] = []
    for raw in updated.get("options") or []:
        if not isinstance(raw, Mapping):
            continue
        option = dict(raw)
        text, found = sanitize_source_markdown(option.get("text_markdown") or "")
        option["text_markdown"] = text
        flags.extend(found)
        options.append(option)
    updated["options"] = options

    solution, found = sanitize_source_markdown(updated.get("teacher_solution_markdown") or "")
    updated["teacher_solution_markdown"] = solution
    flags.extend(found)
    final_answer, found = sanitize_source_markdown(updated.get("final_answer_markdown") or "")
    updated["final_answer_markdown"] = final_answer
    flags.extend(found)
    return updated, list(dict.fromkeys(flags))


def _finalize_projection_and_audit(
    result: PageAssemblyResult,
    audit: Mapping[str, Any],
) -> tuple[PageAssemblyResult, dict[str, Any]]:
    """Sanitize globally and synchronize embedded verification with final guard rows."""

    rows = [dict(row) for row in (audit.get("regions") or []) if isinstance(row, Mapping)]
    rows_by_question: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        number = _number(row.get("questionNumber"))
        if number > 0:
            rows_by_question[number].append(row)

    projection = dict(result.projection)
    exam = dict(projection.get("exam_prep") or {})
    questions: list[dict[str, Any]] = []
    sanitized_questions = 0
    for raw in exam.get("questions") or []:
        if not isinstance(raw, Mapping):
            continue
        question, flags = _sanitize_final_question(raw)
        if flags:
            sanitized_questions += 1
        number = _number(question.get("source_question_number"))
        metadata = dict(question.get("stage4_verification") or {})
        metadata["regions"] = rows_by_question.get(number, [])
        metadata["hasSuspiciousRegion"] = any(
            bool(row.get("suspicious")) for row in metadata["regions"]
        )
        if flags:
            metadata["finalSanitizerFlags"] = flags
        else:
            metadata.pop("finalSanitizerFlags", None)
        question["stage4_verification"] = metadata
        questions.append(question)

    exam["questions"] = questions
    projection["exam_prep"] = exam
    final_result = result.model_copy(update={"projection": projection})
    final_result = rebuild_assembly_quality(final_result)

    output_audit = dict(audit)
    output_audit["regions"] = rows
    stats = dict(output_audit.get("stats") or {})
    stats["finalSanitizerQuestionCount"] = sanitized_questions
    output_audit["stats"] = stats
    policy = dict(output_audit.get("policy") or {})
    policy["globalFinalSanitizer"] = True
    policy["embeddedAuditSyncedAfterAllGuards"] = True
    policy["primaryVisionTransport"] = "avalai_openai_compatible_chat_completions"
    output_audit["policy"] = policy
    return final_result, output_audit


def verify_and_repair_risky_regions(*args, **kwargs):
    original = args[0] if args else kwargs.get("result")
    result, audit = verify_and_repair_risky_regions_page_batched(*args, **kwargs)
    if isinstance(original, PageAssemblyResult):
        result, audit = enforce_source_invariants(original, result, audit)
        result, audit = enforce_pathological_repair_consensus(
            original,
            result,
            audit,
            pdf_data=kwargs.get("pdf_data") or b"",
            layout=kwargs.get("layout") or {},
            recovered_solution_targets=kwargs.get("recovered_solution_targets") or (),
            unresolved_solution_targets=kwargs.get("unresolved_solution_targets") or (),
            max_cost_usd=kwargs.get("max_cost_usd"),
        )
        result, audit = enforce_hard_question_numeric_consensus(
            original,
            result,
            audit,
            pdf_data=kwargs.get("pdf_data") or b"",
            layout=kwargs.get("layout") or {},
            recovered_solution_targets=kwargs.get("recovered_solution_targets") or (),
            unresolved_solution_targets=kwargs.get("unresolved_solution_targets") or (),
            max_cost_usd=kwargs.get("max_cost_usd"),
        )
    result = _restore_authority(result, audit=audit)
    return _finalize_projection_and_audit(result, audit)


Stage4Stats = PageBatchStats

__all__ = [
    "Stage4Stats",
    "_finalize_projection_and_audit",
    "verify_and_repair_risky_regions",
]
