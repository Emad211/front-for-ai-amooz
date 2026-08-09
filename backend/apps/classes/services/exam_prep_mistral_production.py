"""Stable production facade for the researched Mistral OCR4 Exam Prep engine.

Stage 2 remains frozen in ``exam_prep_mistral_stage2_core``. This facade keeps
its deterministic OCR/numbering/solution-recovery logic, adds compatibility for
disjoint booklet ranges, applies source-precise Stage 3 visual reconciliation,
and then Stage 4 deterministic risk scoring plus source-only targeted repair.

No Exam Prep V4 module, benchmark helper, management command or broad per-page /
per-question LLM pass is a production dependency here.
"""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal, InvalidOperation
import io
import os
from typing import Any, Mapping, Sequence

from . import exam_prep_mistral_stage2_core as core
from . import exam_prep_page_output
from .exam_prep_mistral_booklet_ranges import extract_booklet_ranges
from .exam_prep_mistral_disjoint_ranges import (
    aligned_solutions_for_intervals,
    build_page_extractions_disjoint,
    declared_question_intervals,
    scope_key_for_question,
)
from .exam_prep_mistral_layout_analysis import analyze_ocr_document
from .exam_prep_mistral_ocr_transport import (
    MistralOCR4Config,
    MistralOCR4Error,
    document_root,
    fetch_ocr4_document,
)
from .exam_prep_mistral_solution_headings import audit_solution_headings
from .exam_prep_mistral_stage4_runtime import verify_and_repair_risky_regions
from .exam_prep_mistral_visual_reconcile import (
    VISUAL_CRITICAL_ISSUE_CODES,
    reconcile_mistral_source_visuals,
)
from .exam_prep_page_output import (
    build_strict_page_first_audit,
    render_strict_page_first_transcript,
)
from .exam_prep_page_records import assemble_page_extractions
from .exam_prep_page_source import attach_source_regions
from .exam_prep_pipeline import (
    ExamPrepPipelineCancelled,
    ExamPrepPipelineResult,
    ExamPrepPdfError,
    NoExamQuestionsFound,
)
from .exam_prep_projection_integrity import (
    apply_projection_integrity,
    augment_transcript_summary,
    promote_integrity_audit,
)
from .exam_prep_question_verifier import rebuild_assembly_quality
from .exam_prep_utils import clean_exam_markdown


ProgressCallback = core.ProgressCallback
CancelCheck = core.CancelCheck
MistralDocumentEvidence = core.MistralDocumentEvidence
PRODUCTION_ENGINE = "mistral_ocr4_document_visuals_risk_v4"
PRODUCTION_ENTRYPOINT = (
    "apps.classes.services.exam_prep_mistral_production."
    "run_exam_prep_mistral_pipeline"
)
_STAGE4_BLOCKER = "stage4_verification_unresolved"

exam_prep_page_output.CRITICAL_ISSUE_CODES = frozenset(
    set(exam_prep_page_output.CRITICAL_ISSUE_CODES) | {_STAGE4_BLOCKER}
)

_ORIGINAL_PARSE_QUESTION_REGION = core.parse_question_region_text


def parse_question_region_text(value: Any) -> tuple[str, list[dict[str, str]], str]:
    """Stage-2-compatible parser plus one proven suffix-option correction."""

    stem, options, style = _ORIGINAL_PARSE_QUESTION_REGION(value)
    if stem or style != "parenthesized_suffix" or len(options) != 4:
        return stem, options, style
    first = clean_exam_markdown(options[0].get("text_markdown") or "")
    split_at = max(first.rfind("؟"), first.rfind("?"))
    if split_at < 0:
        return stem, options, style
    recovered_stem = clean_exam_markdown(first[: split_at + 1])
    first_value = clean_exam_markdown(first[split_at + 1 :])
    if not recovered_stem or not first_value:
        return stem, options, style
    corrected = [dict(item) for item in options]
    corrected[0]["text_markdown"] = first_value
    return recovered_stem, corrected, style


core.parse_question_region_text = parse_question_region_text

_question_anchor_counts = core._question_anchor_counts
_question_numbers = core._question_numbers
_target_crop_specs = core._target_crop_specs
_render_target_crop_pdf = core._render_target_crop_pdf
_heading_lines = core._heading_lines
_collect_crop_headings = core._collect_crop_headings
_resolve_target_headings = core._resolve_target_headings
_targeted_recovery = core._targeted_recovery
_column_bbox = core._column_bbox
_booklet_contract_issues = core._booklet_contract_issues

_OWN_CRITICAL_CODES = frozenset(
    set(core._OWN_CRITICAL_CODES)
    | set(VISUAL_CRITICAL_ISSUE_CODES)
    | {_STAGE4_BLOCKER}
)


def _decimal_env(name: str, default: str, *, maximum: str = "2.00") -> Decimal:
    raw = (os.getenv(name) or default).strip()
    try:
        value = Decimal(raw)
    except (InvalidOperation, ValueError):
        value = Decimal(default)
    return max(Decimal("0"), min(Decimal(maximum), value))


def _total_budget_usd() -> Decimal:
    return _decimal_env("EXAM_PREP_TOTAL_PDF_BUDGET_USD", "0.30")


def _targeted_ocr_reserve_per_page_usd() -> Decimal:
    return _decimal_env(
        "EXAM_PREP_TARGETED_OCR_RESERVE_PER_PAGE_USD",
        "0.0065",
        maximum="0.05",
    )


def _minimum_stage4_reserve_usd() -> Decimal:
    return _decimal_env(
        "EXAM_PREP_STAGE4_MINIMUM_RESERVE_USD",
        "0.0065",
        maximum="0.05",
    )


def _targeted_recovery_budget_plan(
    *,
    accepted,
    missing: Sequence[int],
    invalid: Sequence[int],
    ocr_cost_usd: Decimal,
    total_budget_usd: Decimal,
) -> dict[str, Any]:
    targets = sorted(set(int(value) for value in missing) | set(int(value) for value in invalid))
    specs = _target_crop_specs(accepted, targets) if targets else []
    reserve = _targeted_ocr_reserve_per_page_usd() * len(specs)
    stage4_reserve = _minimum_stage4_reserve_usd() if specs else Decimal("0")
    allowed = bool(
        specs
        and ocr_cost_usd + reserve + stage4_reserve <= total_budget_usd
    )
    return {
        "targetCount": len(targets),
        "cropPageCount": len(specs),
        "reserveUsd": reserve,
        "minimumStage4ReserveUsd": stage4_reserve,
        "allowed": allowed,
    }


def analyze_mistral_document_evidence(
    root: Mapping[str, Any],
    *,
    original_page_numbers: Sequence[int] | None = None,
) -> MistralDocumentEvidence:
    mapping = list(original_page_numbers or []) or None
    return MistralDocumentEvidence(
        layout=analyze_ocr_document(root, original_page_numbers=mapping),
        booklet_ranges=extract_booklet_ranges(root, original_page_numbers=mapping),
        solution_headings=audit_solution_headings(
            root,
            original_page_numbers=mapping,
        ),
    )


def _promote_own_critical(
    audit: dict[str, Any],
    extra: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    output = dict(audit)
    issues = [
        dict(item)
        for item in (audit.get("issues") or [])
        if isinstance(item, Mapping)
    ]
    issues.extend(dict(item) for item in extra)
    for issue in issues:
        if str(issue.get("code") or "") in _OWN_CRITICAL_CODES:
            issue["severity"] = "critical"
    output["issues"] = issues
    critical = [item for item in issues if item.get("severity") == "critical"]
    critical_questions = {
        int(item.get("questionNumber") or 0)
        for item in critical
        if int(item.get("questionNumber") or 0) > 0
    }
    output["criticalIssueCount"] = len(critical)
    output["questionsNeedingReview"] = len(critical_questions)
    output["usableQuestionCount"] = max(
        0,
        int(output.get("questionCount") or 0) - len(critical_questions),
    )
    output["status"] = (
        "passed"
        if output.get("questionCount") and not critical
        else "needs_review"
    )
    return output


def _server_visual_source_contracts(
    projection: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    exam = projection.get("exam_prep")
    questions = exam.get("questions") if isinstance(exam, Mapping) else []
    output: dict[str, dict[str, Any]] = {}
    for question in questions or []:
        if not isinstance(question, Mapping):
            continue
        question_id = str(question.get("question_id") or "").strip()
        contract = question.get("visualSourceContract")
        if question_id and isinstance(contract, Mapping):
            output[question_id] = dict(contract)
    return output


def _stage4_resolved_solution_numbers(stage4_audit: Mapping[str, Any]) -> set[int]:
    resolved: set[int] = set()
    for row in stage4_audit.get("regions") or []:
        if not isinstance(row, Mapping) or str(row.get("kind") or "") != "solution":
            continue
        status = str(row.get("status") or "")
        if not (status.startswith("verified") or status.startswith("repaired")):
            continue
        try:
            number = int(row.get("questionNumber") or 0)
        except (TypeError, ValueError):
            continue
        if number > 0:
            resolved.add(number)
    return resolved


def run_exam_prep_mistral_pipeline(
    *,
    data: bytes,
    title: str,
    model: str | None = None,
    scope_hint: str = "default",
    on_page_complete: ProgressCallback | None = None,
    should_cancel: CancelCheck | None = None,
) -> ExamPrepPipelineResult:
    """Run OCR4 + precise visuals + risk-gated source verification."""

    del model, scope_hint
    core._cancel(should_cancel)
    # Paid OCR retries are disabled in the production path. A transient provider
    # failure is cheaper and safer to surface than silently buying a second large
    # OCR chunk and breaking the per-PDF budget.
    config = replace(MistralOCR4Config.from_env(), max_attempts=1)
    completed = 0

    def chunk_done(chunk_result) -> None:
        nonlocal completed
        completed += len(chunk_result.chunk.physical_pages)
        if on_page_complete is not None:
            from pypdf import PdfReader

            total = len(PdfReader(io.BytesIO(data)).pages)
            on_page_complete(min(completed, total), total)
        core._cancel(should_cancel)

    try:
        ocr_result = fetch_ocr4_document(
            data,
            config=config,
            chunk_callback=chunk_done,
        )
    except MistralOCR4Error as exc:
        raise ExamPrepPdfError(str(exc)) from exc

    core._cancel(should_cancel)
    root = document_root(ocr_result)
    evidence = analyze_mistral_document_evidence(
        root,
        original_page_numbers=list(range(1, ocr_result.page_count + 1)),
    )
    question_numbers = _question_numbers(evidence)
    if not question_numbers:
        raise NoExamQuestionsFound(
            "هیچ سؤال شماره‌داری در PDF تشخیص داده نشد."
        )

    total_budget = _total_budget_usd()
    intervals = declared_question_intervals(evidence, question_numbers)
    accepted, missing, invalid = aligned_solutions_for_intervals(
        ocr_result,
        intervals,
    )
    targeted_budget = _targeted_recovery_budget_plan(
        accepted=accepted,
        missing=missing,
        invalid=invalid,
        ocr_cost_usd=ocr_result.estimated_cost_unit,
        total_budget_usd=total_budget,
    )
    targeted_skipped_budget = bool(
        targeted_budget["cropPageCount"] and not targeted_budget["allowed"]
    )
    if targeted_budget["allowed"]:
        targeted_config = replace(config, max_attempts=1)
        recovered_targets, targeted_result = _targeted_recovery(
            data,
            accepted=accepted,
            missing=missing,
            invalid=invalid,
            config=targeted_config,
            should_cancel=should_cancel,
        )
    else:
        recovered_targets, targeted_result = {}, None

    unresolved_targets = sorted(
        (set(missing) | set(invalid)) - set(recovered_targets)
    )

    page_extractions = build_page_extractions_disjoint(
        result=ocr_result,
        evidence=evidence,
        recovered_targets=recovered_targets,
        intervals=intervals,
    )
    assembled = assemble_page_extractions(page_extractions, title=title)
    assembled = attach_source_regions(assembled, pages=page_extractions)
    assembled = rebuild_assembly_quality(assembled)

    assembled, visual_stats, visual_audit = reconcile_mistral_source_visuals(
        assembled,
        pdf_data=data,
        ocr_pages=ocr_result.pages,
        layout=evidence.layout,
        source_sha256=ocr_result.source_sha256,
    )

    targeted_cost = (
        targeted_result.estimated_cost_unit if targeted_result is not None else Decimal("0")
    )
    spent_before_stage4 = ocr_result.estimated_cost_unit + targeted_cost
    remaining_stage4 = max(Decimal("0"), total_budget - spent_before_stage4)

    assembled, stage4_audit = verify_and_repair_risky_regions(
        assembled,
        pdf_data=data,
        layout=evidence.layout,
        recovered_solution_targets=set(recovered_targets),
        unresolved_solution_targets=set(unresolved_targets),
        should_cancel=should_cancel,
        max_cost_usd=float(remaining_stage4),
    )
    stage4_stats = dict(stage4_audit.get("stats") or {})
    stage4_resolved_solutions = _stage4_resolved_solution_numbers(stage4_audit)
    remaining_unresolved_targets = sorted(
        set(unresolved_targets) - stage4_resolved_solutions
    )

    assembled, integrity_stats = apply_projection_integrity(assembled)
    audit = build_strict_page_first_audit(
        assembled,
        failed_page_numbers=[],
    )
    audit = promote_integrity_audit(audit, integrity_stats=integrity_stats)

    extra_issues = _booklet_contract_issues(evidence, question_numbers)
    for number, count in _question_anchor_counts(evidence).items():
        if count > 1:
            extra_issues.append(
                {
                    "code": "mistral_duplicate_question_anchor",
                    "severity": "critical",
                    "scopeKey": scope_key_for_question(intervals, number),
                    "questionNumber": number,
                    "sourcePages": [],
                }
            )
    for number in remaining_unresolved_targets:
        extra_issues.append(
            {
                "code": "mistral_solution_heading_unresolved",
                "severity": "critical",
                "scopeKey": scope_key_for_question(intervals, number),
                "questionNumber": number,
                "sourcePages": [],
            }
        )
    audit = _promote_own_critical(audit, extra_issues)

    targeted_calls = targeted_result.provider_call_count if targeted_result else 0
    targeted_retries = targeted_result.retry_count if targeted_result else 0
    stage4_primary_calls = int(stage4_stats.get("primaryCalls") or 0)
    stage4_secondary_calls = int(stage4_stats.get("secondaryCalls") or 0)
    stage4_calls = stage4_primary_calls + stage4_secondary_calls
    stage4_cost = Decimal(str(stage4_stats.get("totalLlmCostUsd") or "0"))
    total_estimated_cost = spent_before_stage4 + stage4_cost

    audit.update(
        {
            "engine": PRODUCTION_ENGINE,
            "ocrSourcePages": ocr_result.page_count,
            "ocrSourceChunks": len(ocr_result.chunks),
            "ocrProviderCalls": ocr_result.provider_call_count,
            "ocrRetries": ocr_result.retry_count,
            "ocrAutomaticPaidRetryAllowed": False,
            "ocrCheckpointReusedChunks": ocr_result.checkpoint_reuse_count,
            "ocrRequestIds": list(ocr_result.request_ids),
            "ocrResolvedModels": list(ocr_result.resolved_models),
            "ocrEstimatedCostUnit": format(ocr_result.estimated_cost_unit, "f"),
            "targetedSolutionHeadingCalls": targeted_calls,
            "targetedSolutionHeadingRetries": targeted_retries,
            "targetedSolutionHeadingRecovered": len(recovered_targets),
            "targetedSolutionHeadingUnresolved": remaining_unresolved_targets,
            "targetedSolutionHeadingSkippedBudget": targeted_skipped_budget,
            "targetedSolutionHeadingBudgetPlan": {
                "targetCount": int(targeted_budget["targetCount"]),
                "cropPageCount": int(targeted_budget["cropPageCount"]),
                "reserveUsd": format(targeted_budget["reserveUsd"], "f"),
                "minimumStage4ReserveUsd": format(
                    targeted_budget["minimumStage4ReserveUsd"], "f"
                ),
                "allowed": bool(targeted_budget["allowed"]),
            },
            "questionIntervals": [
                {
                    "start": start,
                    "end": end,
                    "scopeKey": scope_key_for_question(intervals, start),
                }
                for start, end in intervals
            ],
            "totalPdfBudgetUsd": format(total_budget, "f"),
            "spentBeforeStage4Usd": format(spent_before_stage4, "f"),
            "stage4BudgetUsd": format(remaining_stage4, "f"),
            "stage4EstimatedCostUsd": format(stage4_cost, "f"),
            "totalEstimatedCostUsd": format(total_estimated_cost, "f"),
            "budgetWithinLimit": total_estimated_cost <= total_budget,
            "visualPipeline": visual_audit,
            "visualSourceContracts": _server_visual_source_contracts(assembled.projection),
            "visualAssetsAttached": int(visual_stats.get("assetsAttached", 0)),
            "visualQuestionAssets": int(visual_stats.get("questionVisuals", 0)),
            "visualOptionAssets": int(visual_stats.get("optionVisuals", 0)),
            "visualSolutionAssets": int(visual_stats.get("solutionVisuals", 0)),
            "visualReviewOnlyAssets": int(visual_stats.get("reviewOnlyAssets", 0)),
            "visualWholePageFallbacks": int(visual_stats.get("wholePageFallbacks", 0)),
            "visualSanityFailures": int(visual_stats.get("sanityFailures", 0)),
            "riskEngine": stage4_audit,
            "riskRegionCount": int(stage4_stats.get("regions") or 0),
            "riskSuspiciousRegionCount": int(stage4_stats.get("suspicious") or 0),
            "targetedRegionPrimaryCalls": stage4_primary_calls,
            "targetedRegionSecondOpinionCalls": stage4_secondary_calls,
            "targetedRegionLlmCalls": stage4_calls,
            "targetedRegionVerified": int(stage4_stats.get("verified") or 0),
            "targetedRegionRepaired": int(stage4_stats.get("repaired") or 0),
            "targetedRegionUnresolved": int(stage4_stats.get("unresolved") or 0),
            "targetedRegionDeferred": int(stage4_stats.get("deferred") or 0),
            "generalLlmCalls": 0,
            "totalProviderCalls": (
                ocr_result.provider_call_count + targeted_calls + stage4_calls
            ),
        }
    )

    transcript_stats = {
        "attempted": stage4_primary_calls,
        "verified": int(stage4_stats.get("verified") or 0),
        "repaired": int(stage4_stats.get("repaired") or 0),
        "retried": ocr_result.retry_count + targeted_retries,
        "unresolved": (
            int(stage4_stats.get("unresolved") or 0)
            + int(stage4_stats.get("deferred") or 0)
            + len(remaining_unresolved_targets)
        ),
        "visuals_attached": int(visual_stats.get("assetsAttached", 0)),
        "tables_verified": int(visual_stats.get("tableVisuals", 0)),
    }
    transcript = render_strict_page_first_transcript(
        assembled,
        failed_page_numbers=[],
        targeted_repair_stats=transcript_stats,
    )
    transcript = augment_transcript_summary(transcript, integrity_stats)

    return ExamPrepPipelineResult(
        projection=assembled.projection,
        issues=assembled.issues,
        page_count=ocr_result.page_count,
        question_count=assembled.question_count,
        questions_needing_review=int(audit.get("questionsNeedingReview") or 0),
        matched_answer_count=assembled.matched_answer_count,
        orphan_answer_count=len(assembled.orphan_answers),
        question_number_gaps=assembled.question_number_gaps,
        failed_page_numbers=[],
        non_content_page_count=max(
            0,
            ocr_result.page_count
            - sum(
                str(page.get("pageRole") or "") in {"question", "solution", "mixed"}
                for page in (evidence.layout.get("pages") or [])
                if isinstance(page, Mapping)
            ),
        ),
        publication_ready=audit.get("status") == "passed",
        transcript_markdown=transcript,
        extraction_audit=audit,
        targeted_repair_stats={
            "attempted": targeted_calls,
            "repaired": len(recovered_targets),
            "unresolved": len(remaining_unresolved_targets),
        },
        verification_stats={
            "attempted": stage4_primary_calls,
            "verified": int(stage4_stats.get("verified") or 0),
            "repaired": int(stage4_stats.get("repaired") or 0),
            "retried": int(stage4_stats.get("splitCalls") or 0),
            "unresolved": int(stage4_stats.get("unresolved") or 0),
            "visuals_attached": int(visual_stats.get("assetsAttached", 0)),
            "tables_verified": int(visual_stats.get("tableVisuals", 0)),
            "skipped": int(stage4_stats.get("deferred") or 0),
            "cancelled_before_call": 0,
        },
        model=",".join(ocr_result.resolved_models) or config.model,
    )


__all__ = [
    "MistralDocumentEvidence",
    "PRODUCTION_ENGINE",
    "PRODUCTION_ENTRYPOINT",
    "analyze_mistral_document_evidence",
    "parse_question_region_text",
    "run_exam_prep_mistral_pipeline",
]
