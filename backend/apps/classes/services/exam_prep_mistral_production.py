"""Stable production facade for the researched Mistral OCR4 Exam Prep engine.

Stage 2 remains frozen in ``exam_prep_mistral_stage2_core``. This facade keeps
its deterministic OCR/numbering/solution-recovery logic, applies a narrow parser
compatibility overlay discovered by regression testing, and runs the source-
precise Stage 3 visual reconciler before final integrity.

No Exam Prep V4 module, benchmark helper, management command or general LLM is
a production dependency here.
"""
from __future__ import annotations

import io
from typing import Any, Mapping, Sequence

from . import exam_prep_mistral_stage2_core as core
from .exam_prep_mistral_booklet_ranges import extract_booklet_ranges
from .exam_prep_mistral_layout_analysis import analyze_ocr_document
from .exam_prep_mistral_ocr_transport import (
    MistralOCR4Config,
    MistralOCR4Error,
    document_root,
    fetch_ocr4_document,
)
from .exam_prep_mistral_solution_headings import audit_solution_headings
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
PRODUCTION_ENGINE = "mistral_ocr4_document_visuals_v2"
PRODUCTION_ENTRYPOINT = (
    "apps.classes.services.exam_prep_mistral_production."
    "run_exam_prep_mistral_pipeline"
)

_ORIGINAL_PARSE_QUESTION_REGION = core.parse_question_region_text


def parse_question_region_text(value: Any) -> tuple[str, list[dict[str, str]], str]:
    """Stage-2-compatible parser plus one proven suffix-option correction.

    OCR4 sometimes emits a one-line form such as::

        77- جرم چند است؟ 250 (1) 500 (2) 25 (3) 50 (4)

    The frozen parser correctly recognizes value-before-label suffix options but
    treats ``جرم چند است؟ 250`` as option 1 and leaves the stem empty. Split the
    first suffix at the last question mark only when that exact failure shape is
    present; all other Stage-2 behavior remains untouched.
    """

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


# Keep the Stage-2 file frozen while ensuring its internal _question_record path
# uses the same production compatibility parser as public callers and replays.
core.parse_question_region_text = parse_question_region_text

_question_anchor_counts = core._question_anchor_counts
_question_numbers = core._question_numbers
_aligned_solutions = core._aligned_solutions
_target_crop_specs = core._target_crop_specs
_render_target_crop_pdf = core._render_target_crop_pdf
_heading_lines = core._heading_lines
_collect_crop_headings = core._collect_crop_headings
_resolve_target_headings = core._resolve_target_headings
_targeted_recovery = core._targeted_recovery
_column_bbox = core._column_bbox
_build_page_extractions = core._build_page_extractions
_booklet_contract_issues = core._booklet_contract_issues

_OWN_CRITICAL_CODES = frozenset(
    set(core._OWN_CRITICAL_CODES) | set(VISUAL_CRITICAL_ISSUE_CODES)
)


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


def run_exam_prep_mistral_pipeline(
    *,
    data: bytes,
    title: str,
    model: str | None = None,
    scope_hint: str = "default",
    on_page_complete: ProgressCallback | None = None,
    should_cancel: CancelCheck | None = None,
) -> ExamPrepPipelineResult:
    """Run deterministic OCR4 core plus source-precise Stage 3 visuals."""

    del model, scope_hint
    core._cancel(should_cancel)
    config = MistralOCR4Config.from_env()
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

    accepted, missing, invalid = _aligned_solutions(
        ocr_result,
        first_expected=min(question_numbers),
        last_expected=max(question_numbers),
    )
    recovered_targets, targeted_result = _targeted_recovery(
        data,
        accepted=accepted,
        missing=missing,
        invalid=invalid,
        config=config,
        should_cancel=should_cancel,
    )
    unresolved_targets = sorted(
        (set(missing) | set(invalid)) - set(recovered_targets)
    )

    page_extractions = _build_page_extractions(
        result=ocr_result,
        evidence=evidence,
        recovered_targets=recovered_targets,
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
                    "scopeKey": "default",
                    "questionNumber": number,
                    "sourcePages": [],
                }
            )
    for number in unresolved_targets:
        extra_issues.append(
            {
                "code": "mistral_solution_heading_unresolved",
                "severity": "critical",
                "scopeKey": "default",
                "questionNumber": number,
                "sourcePages": [],
            }
        )
    audit = _promote_own_critical(audit, extra_issues)

    targeted_calls = (
        targeted_result.provider_call_count if targeted_result else 0
    )
    targeted_retries = targeted_result.retry_count if targeted_result else 0
    audit.update(
        {
            "engine": PRODUCTION_ENGINE,
            "ocrSourcePages": ocr_result.page_count,
            "ocrSourceChunks": len(ocr_result.chunks),
            "ocrProviderCalls": ocr_result.provider_call_count,
            "ocrRetries": ocr_result.retry_count,
            "ocrCheckpointReusedChunks": ocr_result.checkpoint_reuse_count,
            "ocrRequestIds": list(ocr_result.request_ids),
            "ocrResolvedModels": list(ocr_result.resolved_models),
            "ocrEstimatedCostUnit": format(
                ocr_result.estimated_cost_unit,
                "f",
            ),
            "targetedSolutionHeadingCalls": targeted_calls,
            "targetedSolutionHeadingRetries": targeted_retries,
            "targetedSolutionHeadingRecovered": len(recovered_targets),
            "targetedSolutionHeadingUnresolved": unresolved_targets,
            "visualPipeline": visual_audit,
            "visualSourceContracts": _server_visual_source_contracts(
                assembled.projection
            ),
            "visualAssetsAttached": int(visual_stats.get("assetsAttached", 0)),
            "visualQuestionAssets": int(visual_stats.get("questionVisuals", 0)),
            "visualOptionAssets": int(visual_stats.get("optionVisuals", 0)),
            "visualSolutionAssets": int(visual_stats.get("solutionVisuals", 0)),
            "visualReviewOnlyAssets": int(visual_stats.get("reviewOnlyAssets", 0)),
            "visualWholePageFallbacks": int(visual_stats.get("wholePageFallbacks", 0)),
            "visualSanityFailures": int(visual_stats.get("sanityFailures", 0)),
            "generalLlmCalls": 0,
            "totalProviderCalls": (
                ocr_result.provider_call_count + targeted_calls
            ),
        }
    )

    transcript_stats = {
        "attempted": targeted_calls,
        "verified": len(recovered_targets),
        "repaired": len(recovered_targets),
        "retried": ocr_result.retry_count + targeted_retries,
        "unresolved": len(unresolved_targets),
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
        questions_needing_review=int(
            audit.get("questionsNeedingReview") or 0
        ),
        matched_answer_count=assembled.matched_answer_count,
        orphan_answer_count=len(assembled.orphan_answers),
        question_number_gaps=assembled.question_number_gaps,
        failed_page_numbers=[],
        non_content_page_count=max(
            0,
            ocr_result.page_count
            - sum(
                str(page.get("pageRole") or "")
                in {"question", "solution", "mixed"}
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
            "unresolved": len(unresolved_targets),
        },
        verification_stats={
            "attempted": 0,
            "verified": 0,
            "repaired": 0,
            "retried": 0,
            "unresolved": int(visual_stats.get("unresolvedRegions", 0)),
            "visuals_attached": int(visual_stats.get("assetsAttached", 0)),
            "tables_verified": int(visual_stats.get("tableVisuals", 0)),
            "skipped": 0,
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
