"""Independent safety gate for the proven pathological-repetition failure family.

The first full PDF validation showed that direct Gemini repairs of pathological
OCR repetition can become fluent but source-invented prose. This guard therefore
runs only after the normal page-batch merge and only for a primary repair whose
risk signals include ``pathological_repetition``. It asks the already-configured
secondary source transcriber for an independent read of the same crop.

If the second read is absent, uncertain, over budget, or materially disagrees,
the primary repair is rolled back to the pre-Stage4 question and the region stays
machine-blocked. Other corruption families are unchanged.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from . import exam_prep_mistral_stage4 as legacy
from . import exam_prep_mistral_stage4_page_batch as impl
from .exam_prep_mistral_risk_engine_v2 import score_region_risks
from .exam_prep_mistral_stage4_field_safety import (
    candidate_fields,
    compare_field_maps,
    comparisons_safe_dict,
    payload_fields,
)
from .exam_prep_page_records import PageAssemblyResult
from .exam_prep_question_verifier import rebuild_assembly_quality


_TEXT_CONSENSUS_MIN = 0.62


def _number(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _question_map(result: PageAssemblyResult) -> dict[int, dict[str, Any]]:
    output: dict[int, dict[str, Any]] = {}
    for raw in (result.projection.get("exam_prep") or {}).get("questions") or []:
        if not isinstance(raw, Mapping):
            continue
        number = _number(raw.get("source_question_number"))
        if number > 0:
            output[number] = dict(raw)
    return output


def _agreement_is_strong(field: str, agreement) -> bool:
    if agreement.critical_conflict:
        return False
    if field == "correct_option_label":
        return True
    # Literal source transcribers need not choose identical Persian punctuation,
    # but a low prose overlap is not independent confirmation of the same source.
    return float(agreement.text_similarity) >= _TEXT_CONSENSUS_MIN


def _restore_question(
    original: Mapping[str, Any],
    current: Mapping[str, Any],
) -> dict[str, Any]:
    restored = dict(original)
    if isinstance(current.get("stage4_verification"), Mapping):
        restored["stage4_verification"] = dict(current["stage4_verification"])
    return legacy._mark_unresolved(restored)


def enforce_pathological_repair_consensus(
    original: PageAssemblyResult,
    updated: PageAssemblyResult,
    audit: Mapping[str, Any],
    *,
    pdf_data: bytes,
    layout: Mapping[str, Any],
    recovered_solution_targets: Sequence[int] | set[int] = (),
    unresolved_solution_targets: Sequence[int] | set[int] = (),
    max_cost_usd: float | None = None,
) -> tuple[PageAssemblyResult, dict[str, Any]]:
    """Validate direct pathological repairs with one independent source read."""

    output_audit = dict(audit)
    rows = [dict(row) for row in (audit.get("regions") or []) if isinstance(row, Mapping)]
    by_target = {str(row.get("targetId") or ""): row for row in rows}
    stats = dict(audit.get("stats") or {})

    decisions = score_region_risks(
        projection=original.projection,
        layout=layout,
        recovered_solution_targets=recovered_solution_targets,
        unresolved_solution_targets=unresolved_solution_targets,
    )
    guarded = [
        decision
        for decision in decisions
        if decision.suspicious and "pathological_repetition" in decision.signals
    ]
    if not guarded:
        output_audit["regions"] = rows
        return updated, output_audit

    original_questions = _question_map(original)
    current_questions = _question_map(updated)
    secondary_calls = int(stats.get("secondaryCalls") or 0)
    secondary_cost = float(stats.get("secondaryCostUsd") or 0)
    total_cost = float(stats.get("totalLlmCostUsd") or 0)
    maximum_secondary = impl._secondary_cap()
    repaired = int(stats.get("repaired") or 0)
    verified = int(stats.get("verified") or 0)
    unresolved = int(stats.get("unresolved") or 0)
    partial_repairs = int(stats.get("partialRepairs") or 0)

    for decision in guarded:
        row = by_target.get(decision.target_id)
        current = current_questions.get(decision.question_number)
        original_question = original_questions.get(decision.question_number)
        if row is None or current is None or original_question is None:
            continue
        status = str(row.get("status") or "")

        if status == "partial_repair_source_uncertain":
            current_questions[decision.question_number] = _restore_question(original_question, current)
            repaired = max(0, repaired - 1)
            partial_repairs = max(0, partial_repairs - 1)
            row["status"] = "pathological_partial_repair_rolled_back"
            row["reason"] = "independent_consensus_required"
            continue
        if status != "repaired_primary_fields":
            # A pathological candidate that was not actually repaired is never
            # promoted to a clean machine result by this guard.
            if status.startswith("verified"):
                current_questions[decision.question_number] = _restore_question(original_question, current)
                verified = max(0, verified - 1)
                unresolved += 1
                row["status"] = "pathological_unresolved"
                row["reason"] = "primary_did_not_produce_safe_repair"
            continue

        if secondary_calls >= maximum_secondary or not impl._budget_allows(
            total_cost, max_cost_usd, "secondary"
        ):
            current_questions[decision.question_number] = _restore_question(original_question, current)
            repaired = max(0, repaired - 1)
            verified = max(0, verified - 1)
            unresolved += 1
            row["status"] = "pathological_consensus_unavailable"
            row["reason"] = (
                "secondary_cap" if secondary_calls >= maximum_secondary else "total_cost_budget"
            )
            continue

        try:
            crop = legacy._render_crop(pdf_data, decision)
            secondary, second_payload, sanitizer_flags = impl._secondary_payload(decision, crop)
            secondary_calls += 1
            delta = impl._secondary_cost(secondary)
            secondary_cost += delta
            total_cost += delta
            row["pathologicalSecondary"] = secondary.safe_dict()
            if sanitizer_flags:
                row["pathologicalSecondarySanitizerFlags"] = list(sanitizer_flags)
        except Exception as exc:
            current_questions[decision.question_number] = _restore_question(original_question, current)
            repaired = max(0, repaired - 1)
            verified = max(0, verified - 1)
            unresolved += 1
            row["status"] = "pathological_consensus_failed"
            row["reason"] = type(exc).__name__
            continue

        if second_payload is None or bool(
            getattr(secondary, "transcript", {}).get("transcriptionUncertain")
        ):
            current_questions[decision.question_number] = _restore_question(original_question, current)
            repaired = max(0, repaired - 1)
            verified = max(0, verified - 1)
            unresolved += 1
            row["status"] = "pathological_consensus_uncertain"
            row["reason"] = "secondary_no_vote"
            continue

        primary_fields = candidate_fields(current, kind=decision.kind)
        second_fields = payload_fields(second_payload, kind=decision.kind)
        requested_fields = {
            str(field) for field in (row.get("neededFields") or []) if str(field)
        }
        compare_fields = requested_fields & set(primary_fields) & set(second_fields)
        if not compare_fields:
            current_questions[decision.question_number] = _restore_question(original_question, current)
            repaired = max(0, repaired - 1)
            verified = max(0, verified - 1)
            unresolved += 1
            row["status"] = "pathological_consensus_failed"
            row["reason"] = "no_comparable_repaired_field"
            continue

        comparison = compare_field_maps(primary_fields, second_fields)
        row["pathologicalConsensusAgreement"] = comparisons_safe_dict(comparison)
        agrees = all(
            field in comparison and _agreement_is_strong(field, comparison[field])
            for field in compare_fields
        )
        if agrees:
            row["status"] = "repaired_pathological_two_model_consensus"
            row["independentConsensusFields"] = sorted(compare_fields)
            continue

        current_questions[decision.question_number] = _restore_question(original_question, current)
        repaired = max(0, repaired - 1)
        verified = max(0, verified - 1)
        unresolved += 1
        row["status"] = "pathological_consensus_disagreement"
        row["reason"] = "independent_source_transcriptions_differ"

    projection = dict(updated.projection)
    exam = dict(projection.get("exam_prep") or {})
    rebuilt_questions: list[dict[str, Any]] = []
    for raw in exam.get("questions") or []:
        if not isinstance(raw, Mapping):
            continue
        number = _number(raw.get("source_question_number"))
        rebuilt_questions.append(dict(current_questions.get(number, raw)))
    exam["questions"] = rebuilt_questions
    projection["exam_prep"] = exam
    guarded_result = updated.model_copy(update={"projection": projection})
    guarded_result = rebuild_assembly_quality(guarded_result)

    stats.update(
        {
            "secondaryCalls": secondary_calls,
            "secondaryCostUsd": round(secondary_cost, 8),
            "totalLlmCostUsd": round(
                float(stats.get("primaryCostUsd") or 0) + secondary_cost, 8
            ),
            "verified": verified,
            "repaired": repaired,
            "partialRepairs": partial_repairs,
            "unresolved": unresolved,
            "pathologicalGuardedTargets": len(guarded),
        }
    )
    output_audit["stats"] = stats
    output_audit["regions"] = rows
    policy = dict(output_audit.get("policy") or {})
    policy["pathologicalRepetitionRequiresIndependentConsensus"] = True
    output_audit["policy"] = policy
    return guarded_result, output_audit


__all__ = ["enforce_pathological_repair_consensus"]
