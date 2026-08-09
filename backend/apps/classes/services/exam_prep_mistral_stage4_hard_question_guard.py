"""Independent guard for numeric overwrites in hard-math question repairs.

A prior live validation caught a dangerous primary-only repair where a visible
``1/33`` quantity became ``33``. This guard is intentionally much narrower than
a blanket two-model policy: it runs only when a hard-math QUESTION was repaired,
a repaired canonical field was already non-empty before Stage 4, and the primary
repair changed that field's numeric signature. Filling a genuinely absent option
or stem does not trigger this guard.
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
from .exam_prep_utils import clean_exam_markdown


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


def _restore(original: Mapping[str, Any], current: Mapping[str, Any]) -> dict[str, Any]:
    restored = dict(original)
    if isinstance(current.get("stage4_verification"), Mapping):
        restored["stage4_verification"] = dict(current["stage4_verification"])
    return legacy._mark_unresolved(restored)


def enforce_hard_question_numeric_consensus(
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
    candidates = [
        decision
        for decision in decisions
        if decision.suspicious
        and decision.kind == "question"
        and decision.hard_math
        and "pathological_repetition" not in decision.signals
    ]
    if not candidates:
        output_audit["regions"] = rows
        return updated, output_audit

    originals = _question_map(original)
    currents = _question_map(updated)
    secondary_calls = int(stats.get("secondaryCalls") or 0)
    secondary_cost = float(stats.get("secondaryCostUsd") or 0)
    total_cost = float(stats.get("totalLlmCostUsd") or 0)
    maximum_secondary = impl._secondary_cap()
    repaired = int(stats.get("repaired") or 0)
    verified = int(stats.get("verified") or 0)
    unresolved = int(stats.get("unresolved") or 0)
    guarded_count = 0

    for decision in candidates:
        row = by_target.get(decision.target_id)
        original_question = originals.get(decision.question_number)
        current = currents.get(decision.question_number)
        if row is None or original_question is None or current is None:
            continue
        status = str(row.get("status") or "")
        if not status.startswith("repaired"):
            continue

        original_fields = candidate_fields(original_question, kind="question")
        current_fields = candidate_fields(current, kind="question")
        needed = {str(field) for field in (row.get("neededFields") or []) if str(field)}
        changed_numeric_fields: set[str] = set()
        comparison = compare_field_maps(original_fields, current_fields)
        for field in needed:
            before = clean_exam_markdown(original_fields.get(field) or "")
            after = clean_exam_markdown(current_fields.get(field) or "")
            agreement = comparison.get(field)
            if not before or not after or agreement is None:
                continue
            if not agreement.numeric_equal:
                changed_numeric_fields.add(field)
        if not changed_numeric_fields:
            continue

        guarded_count += 1
        row["hardQuestionNumericOverwriteFields"] = sorted(changed_numeric_fields)
        row["hardQuestionOriginalPrimaryAgreement"] = comparisons_safe_dict(comparison)

        if secondary_calls >= maximum_secondary or not impl._budget_allows(
            total_cost, max_cost_usd, "secondary"
        ):
            currents[decision.question_number] = _restore(original_question, current)
            repaired = max(0, repaired - 1)
            verified = max(0, verified - 1)
            unresolved += 1
            row["status"] = "hard_question_numeric_consensus_unavailable"
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
            row["hardQuestionSecondary"] = secondary.safe_dict()
            if sanitizer_flags:
                row["hardQuestionSecondarySanitizerFlags"] = list(sanitizer_flags)
        except Exception as exc:
            currents[decision.question_number] = _restore(original_question, current)
            repaired = max(0, repaired - 1)
            verified = max(0, verified - 1)
            unresolved += 1
            row["status"] = "hard_question_numeric_consensus_failed"
            row["reason"] = type(exc).__name__
            continue

        if second_payload is None or bool(
            getattr(secondary, "transcript", {}).get("transcriptionUncertain")
        ):
            currents[decision.question_number] = _restore(original_question, current)
            repaired = max(0, repaired - 1)
            verified = max(0, verified - 1)
            unresolved += 1
            row["status"] = "hard_question_numeric_consensus_uncertain"
            row["reason"] = "secondary_no_vote"
            continue

        second_fields = payload_fields(second_payload, kind="question")
        primary_second = compare_field_maps(current_fields, second_fields)
        row["hardQuestionPrimarySecondaryAgreement"] = comparisons_safe_dict(primary_second)
        agrees = all(
            field in primary_second
            and primary_second[field].numeric_equal
            and not primary_second[field].critical_conflict
            for field in changed_numeric_fields
        )
        if agrees:
            row["status"] = "repaired_hard_question_numeric_consensus"
            continue

        currents[decision.question_number] = _restore(original_question, current)
        repaired = max(0, repaired - 1)
        verified = max(0, verified - 1)
        unresolved += 1
        row["status"] = "hard_question_numeric_consensus_disagreement"
        row["reason"] = "secondary_does_not_confirm_numeric_overwrite"

    projection = dict(updated.projection)
    exam = dict(projection.get("exam_prep") or {})
    rebuilt: list[dict[str, Any]] = []
    for raw in exam.get("questions") or []:
        if not isinstance(raw, Mapping):
            continue
        number = _number(raw.get("source_question_number"))
        rebuilt.append(dict(currents.get(number, raw)))
    exam["questions"] = rebuilt
    projection["exam_prep"] = exam
    guarded_result = updated.model_copy(update={"projection": projection})
    guarded_result = rebuild_assembly_quality(guarded_result)

    stats.update(
        {
            "secondaryCalls": secondary_calls,
            "secondaryCostUsd": round(secondary_cost, 8),
            "totalLlmCostUsd": round(float(stats.get("primaryCostUsd") or 0) + secondary_cost, 8),
            "verified": verified,
            "repaired": repaired,
            "unresolved": unresolved,
            "hardQuestionNumericGuardedTargets": guarded_count,
        }
    )
    output_audit["stats"] = stats
    output_audit["regions"] = rows
    policy = dict(output_audit.get("policy") or {})
    policy["hardMathQuestionNumericOverwriteRequiresIndependentConsensus"] = True
    output_audit["policy"] = policy
    return guarded_result, output_audit


__all__ = ["enforce_hard_question_numeric_consensus"]
