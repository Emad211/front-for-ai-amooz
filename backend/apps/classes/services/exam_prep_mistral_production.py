"""Stable production facade for the researched Mistral OCR4 Exam Prep engine.

Stage 2 remains frozen in ``exam_prep_mistral_stage2_core``. This facade keeps
its deterministic OCR/numbering/solution-recovery logic, adds compatibility for
disjoint booklet ranges, applies source-precise Stage 3 visual reconciliation,
uses free Stage 4 risk scoring, and finishes every source region through Stage 5.

No Exam Prep V4 module, benchmark helper, management command or broad per-page /
per-question LLM pass is a production dependency here.
"""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal, InvalidOperation
import io
import os
import re
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
    PrivateOCRCheckpointStore,
    document_root,
    fetch_ocr4_document,
)
from .exam_prep_mistral_native_answer_headings import (
    authoritative_answer_labels,
    extract_native_answer_evidence,
    overlay_native_solution_heading_blocks,
)
from .exam_prep_mistral_risk_engine import score_region_risks
from .exam_prep_mistral_solution_headings import audit_solution_headings
from .exam_prep_mistral_stage5 import finalize_stage5_regions
from .exam_prep_mistral_stage5_runtime import successful_call_cost_usd
from .exam_prep_mistral_targeted_recovery import (
    overlay_recovered_solution_regions,
    recovered_solution_layout_regions,
)
from .exam_prep_mistral_visuals import build_visual_asset_registry
from .exam_prep_mistral_visual_reconcile import (
    VISUAL_CRITICAL_ISSUE_CODES,
    reconcile_mistral_source_visuals,
)
from .exam_prep_page_output import (
    build_strict_exam_audit,
    render_strict_exam_transcript,
    review_blocking_question_keys,
)
from .exam_prep_page_records import PageAssemblyResult, assemble_page_extractions
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
PRODUCTION_ENGINE = "mistral_ocr4_document_visuals_stage5"
PRODUCTION_ENTRYPOINT = (
    "apps.classes.services.exam_prep_mistral_production."
    "run_exam_prep_mistral_pipeline"
)
_STAGE5_BLOCKER = "stage5_finalization_blocked"

exam_prep_page_output.CRITICAL_ISSUE_CODES = frozenset(
    set(exam_prep_page_output.CRITICAL_ISSUE_CODES) | {_STAGE5_BLOCKER}
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

_STALE_PARSE_FAILURE_CODE = "mistral_question_option_parse_failed"

# Relaxed inline-option recovery -------------------------------------------------
# The frozen Stage-2 detectors (``_OPTION_MARKER_RE`` needs trailing punctuation,
# ``_PAREN_OPTION_RE`` needs a closing bracket, ``_marker_sequence`` needs all
# four markers in strict order) split only clean ``۱)…۴)`` runs. Live 58-page
# booklets also produce three degenerate shapes the frozen path rejects:
#   A. half-open parens ``(۱ … (۲ … (۳ … (۴``  (opening bracket, no close, no punct)
#   B. an OCR-dropped internal marker ``(۱) … (۲) … (۴)``  (only 3 of 4 survive)
#   C. a flattened table ``(۱) v ۲ v ۳ v ۴ v``  (bare standalone digit markers)
# This facade-local relaxed pass recovers those without touching the frozen core:
# a marker is a digit 1..4 whose left edge is start/space/opening-bracket and
# whose right edge is a closing punct, whitespace, or end — never glued to math
# (``$``, ``_``, ``=``, ``/``) or another digit (so ``۱۰``/``۳/۴`` never anchor).
# A run must start at marker 1 and hold >= 3 strictly-increasing markers, the
# first of which is "strong" (carries a bracket or closing punct); that is what
# keeps dense math from false-firing. Internal gaps become empty labelled options
# (the teacher fixes the residual value via the edit form) so the review gate
# clears while nothing is ever blanked or dropped.
_MARKER_VALUE = {
    "1": 1, "۱": 1, "١": 1,
    "2": 2, "۲": 2, "٢": 2,
    "3": 3, "۳": 3, "٣": 3,
    "4": 4, "۴": 4, "٤": 4,
}
_MARKER_DIGIT_RE = re.compile(r"[1-4۱-۴١-٤]")
_OPEN_BRACKETS = "(["
_CLOSE_MARKER_PUNCT = ")].:：-–—"
_MIN_RELAXED_RUN = 3


def _relaxed_markers(body: str) -> list[tuple[int, int, int, bool]]:
    """Return ``(number, outer_start, content_end, strong)`` marker candidates.

    ``outer_start`` includes a leading ``(``/``[`` when present; ``content_end``
    is the index just past the marker (past a closing punct when present); a
    marker is ``strong`` when it carries a bracket or closing punctuation.
    """

    markers: list[tuple[int, int, int, bool]] = []
    length = len(body)
    for match in _MARKER_DIGIT_RE.finditer(body):
        position = match.start()
        number = _MARKER_VALUE[match.group(0)]
        # Left edge: allow one opening bracket, then require start/whitespace so a
        # marker glued to prose or math (``f(2)``, ``$x_1``) is rejected.
        outer_start = position
        has_open = False
        left = body[position - 1] if position > 0 else ""
        if left in _OPEN_BRACKETS:
            has_open = True
            outer_start = position - 1
            left = body[outer_start - 1] if outer_start > 0 else ""
        if left and not left.isspace():
            continue
        # Right edge: optionally consume one closing punct (spaces allowed before
        # it); otherwise the digit must be followed by whitespace or end so a
        # multi-digit value (``۱۰``) or a fraction (``۳/۴``) never anchors a run.
        has_close = False
        content_end = position + 1
        probe = position + 1
        while probe < length and body[probe] == " ":
            probe += 1
        if probe < length and body[probe] in _CLOSE_MARKER_PUNCT:
            has_close = True
            content_end = probe + 1
        else:
            after = body[position + 1] if position + 1 < length else ""
            if after and not after.isspace():
                continue
        markers.append((number, outer_start, content_end, has_open or has_close))
    return markers


def _relaxed_option_run(
    markers: list[tuple[int, int, int, bool]],
) -> list[tuple[int, int, int, bool]] | None:
    """Pick the first ascending run that starts at a strong marker 1 (>= 3 long).

    Gaps are tolerated (Mode B drops one internal marker) but the run must start
    at 1 and increase strictly, and its first marker must be strong so dense math
    can never seed a run.
    """

    for start_index, first in enumerate(markers):
        if first[0] != 1 or not first[3]:
            continue
        run = [first]
        for candidate in markers[start_index + 1 :]:
            if run[-1][0] < candidate[0] <= 4:
                run.append(candidate)
        if len(run) >= _MIN_RELAXED_RUN:
            return run
    return None


def _split_relaxed_inline_options(
    body: str,
) -> tuple[str, list[dict[str, str]]] | None:
    """Fallback split for OCR-mangled marker runs the frozen path can't parse."""

    run = _relaxed_option_run(_relaxed_markers(body))
    if run is None:
        return None
    recovered_stem = clean_exam_markdown(body[: run[0][1]])
    if not recovered_stem:
        return None
    texts: dict[int, str] = {}
    for index, marker in enumerate(run):
        number, _outer_start, content_end, _strong = marker
        text_end = run[index + 1][1] if index + 1 < len(run) else len(body)
        texts[number] = core._clean_option_text(body[content_end:text_end])
    highest = run[-1][0]
    options = [
        {"label": str(number), "text_markdown": texts.get(number, "")}
        for number in range(1, highest + 1)
    ]
    return recovered_stem, options


def _split_inline_stem_options(
    stem: Any,
) -> tuple[str, list[dict[str, str]]] | None:
    """Pull an OCR-inlined option run out of a question stem.

    ``mistral-ocr-4-0`` sometimes emits the four numbered options *inside* the
    question stem and leaves ``options[]`` empty (frequently with an empty
    trailing option), which used to force an otherwise-answerable question into
    the review lane with ``missing_options``. The frozen 1..4 marker run is tried
    first (proven on clean runs); a facade-local relaxed pass then recovers the
    three degenerate OCR shapes the frozen detectors reject (see the block above).
    On success this returns ``(clean_stem, options)``, keeping the label of every
    option — including empty/image-only options so they still render and only
    advisory ``missing_option_text`` applies. Returns ``None`` when there is no
    marker run or no real question text precedes it, so a genuinely option-less
    stem stays review-blocking (owner policy).
    """

    body = clean_exam_markdown(stem or "")
    if not body:
        return None
    body = core._QUESTION_HEADING_RE.sub("", body, count=1)
    sequence = core._marker_sequence(body, core._OPTION_MARKER_RE)
    if sequence is None:
        sequence = core._marker_sequence(body, core._PAREN_OPTION_RE)
    if sequence is not None:
        recovered_stem = clean_exam_markdown(body[: sequence[0][1]])
        if recovered_stem:
            options: list[dict[str, str]] = []
            for index, marker in enumerate(sequence):
                end = sequence[index + 1][1] if index + 1 < len(sequence) else len(body)
                options.append(
                    {
                        "label": str(marker[0]),
                        "text_markdown": core._clean_option_text(body[marker[2] : end]),
                    }
                )
            options.sort(key=lambda item: int(item["label"]))
            return recovered_stem, options
    return _split_relaxed_inline_options(body)


def _recover_inline_stem_options(
    result: PageAssemblyResult,
) -> PageAssemblyResult:
    """Recover inline options for assembled questions that lost their options[].

    Deterministic, provider-free, and idempotent: only questions with fewer than
    two options and a recoverable stem are touched. On success the stale
    region-level ``mistral_question_option_parse_failed`` code is dropped (the
    parse now succeeded); ``rebuild_assembly_quality`` recomputes the rest.
    """

    projection = dict(result.projection)
    exam = dict(projection.get("exam_prep") or {})
    source_questions = exam.get("questions")
    if not isinstance(source_questions, list):
        return result
    changed = False
    questions: list[Any] = []
    for question in source_questions:
        if not isinstance(question, Mapping):
            questions.append(question)
            continue
        options = [
            item
            for item in (question.get("options") or [])
            if isinstance(item, Mapping)
        ]
        if len(options) >= 2:
            questions.append(dict(question))
            continue
        recovered = _split_inline_stem_options(question.get("question_text_markdown"))
        if recovered is None:
            questions.append(dict(question))
            continue
        stem, recovered_options = recovered
        updated = dict(question)
        updated["question_text_markdown"] = stem
        updated["options"] = recovered_options
        updated["issues"] = [
            code
            for code in (question.get("issues") or [])
            if clean_exam_markdown(code).strip() != _STALE_PARSE_FAILURE_CODE
        ]
        questions.append(updated)
        changed = True
    if not changed:
        return result
    exam["questions"] = questions
    projection["exam_prep"] = exam
    return result.model_copy(update={"projection": projection})


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
    | {_STAGE5_BLOCKER}
)


def _decimal_env(name: str, default: str, *, maximum: str = "2.00") -> Decimal:
    raw = (os.getenv(name) or default).strip()
    try:
        value = Decimal(raw)
    except (InvalidOperation, ValueError):
        value = Decimal(default)
    return max(Decimal("0"), min(Decimal(maximum), value))


def _total_budget_usd() -> Decimal:
    return _decimal_env("EXAM_PREP_TOTAL_PDF_BUDGET_USD", "1.50")


def _stage5_success_cost_usd(stage5_audit: Mapping[str, Any]) -> tuple[Decimal, bool]:
    """Estimate successful-call cost from the fixed production model prices."""

    return successful_call_cost_usd(stage5_audit)


def _targeted_ocr_reserve_per_page_usd() -> Decimal:
    return _decimal_env(
        "EXAM_PREP_TARGETED_OCR_RESERVE_PER_PAGE_USD",
        "0.0065",
        maximum="0.05",
    )


def _minimum_stage5_reserve_usd() -> Decimal:
    return _decimal_env(
        "EXAM_PREP_STAGE5_MINIMUM_RESERVE_USD",
        "0.75",
        maximum="1.50",
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
    stage5_reserve = _minimum_stage5_reserve_usd() if specs else Decimal("0")
    allowed = bool(
        specs
        and ocr_cost_usd + reserve + stage5_reserve <= total_budget_usd
    )
    return {
        "targetCount": len(targets),
        "cropPageCount": len(specs),
        "reserveUsd": reserve,
        "minimumStage5ReserveUsd": stage5_reserve,
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
    # `_OWN_CRITICAL_CODES` (Stage-5 blockers, visual-critical codes, …) stay
    # promoted to critical severity for the advisory `criticalIssueCount`, but
    # publishing is gated only by genuinely-broken questions (no stem / no
    # options) plus any unrecoverable physical page — owner policy `همیشه مجاز`.
    blocking_questions = review_blocking_question_keys(issues)
    blocked_by_failed_page = bool(output.get("failedPageNumbers"))
    output["criticalIssueCount"] = len(critical)
    output["questionsNeedingReview"] = len(blocking_questions)
    output["usableQuestionCount"] = max(
        0,
        int(output.get("questionCount") or 0) - len(blocking_questions),
    )
    output["status"] = (
        "passed"
        if output.get("questionCount")
        and not blocking_questions
        and not blocked_by_failed_page
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


def _resolved_solution_numbers(stage_audit: Mapping[str, Any]) -> set[int]:
    resolved: set[int] = set()
    for row in stage_audit.get("regions") or []:
        if not isinstance(row, Mapping) or str(row.get("kind") or "") != "solution":
            continue
        status = str(row.get("status") or "")
        if not (status.startswith("verified") or status.startswith("repaired")):
            continue
        if row.get("resolutionTargetConfirmed") is not True:
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
    on_region_complete: ProgressCallback | None = None,
    should_cancel: CancelCheck | None = None,
    asset_namespace: str | None = None,
) -> ExamPrepPipelineResult:
    """Run OCR4, deterministic assembly/visuals, and Stage-5 source verification."""

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
            checkpoint_store=(
                PrivateOCRCheckpointStore(namespace=str(asset_namespace))
                if asset_namespace
                else None
            ),
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

    native = extract_native_answer_evidence(data)
    native_trusted = native.trusted_for(question_numbers)
    native_labels = authoritative_answer_labels(
        native,
        expected_question_numbers=question_numbers,
    )
    if native_trusted:
        root = overlay_native_solution_heading_blocks(
            root,
            pdf_data=data,
            evidence=native,
            trusted=True,
        )
        ocr_result = replace(ocr_result, pages=tuple(root.get("pages") or ()))
        evidence = analyze_mistral_document_evidence(
            root,
            original_page_numbers=list(range(1, ocr_result.page_count + 1)),
        )
        question_numbers = _question_numbers(evidence)

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
        # This request only carries a handful of small cropped question/solution
        # regions (not the full document), so one bounded retry on a transient
        # provider failure (e.g. HTTP 504) is cheap and safe, unlike the main OCR
        # chunks where automatic retry is deliberately disabled to avoid
        # re-buying a large request. A persistent failure still degrades to
        # "unresolved" below instead of aborting the whole pipeline run.
        targeted_config = replace(config, max_attempts=2)
        try:
            recovered_targets, targeted_result = _targeted_recovery(
                data,
                accepted=accepted,
                missing=missing,
                invalid=invalid,
                config=targeted_config,
                should_cancel=should_cancel,
            )
        except MistralOCR4Error:
            recovered_targets, targeted_result = {}, None
    else:
        recovered_targets, targeted_result = {}, None

    unresolved_targets = sorted(
        (set(missing) | set(invalid)) - set(recovered_targets)
    )
    recovered_layout_regions: list[dict[str, Any]] = []
    if targeted_result is not None and recovered_targets:
        targets = sorted(set(missing) | set(invalid))
        specs = _target_crop_specs(accepted, targets)
        crop_specs = [
            {"physicalPageNumber": page_number, "column": side}
            for page_number, side in specs
        ]
        targeted_root = {
            "pages": [dict(page) for page in (targeted_result.pages or ())]
        }
        recovered_layout_regions = recovered_solution_layout_regions(
            targeted_root,
            crop_specs=crop_specs,
            recovered_targets=recovered_targets,
        )
        if recovered_layout_regions:
            evidence = replace(
                evidence,
                layout=overlay_recovered_solution_regions(
                    evidence.layout,
                    recovered_layout_regions,
                ),
            )

    page_extractions = build_page_extractions_disjoint(
        result=ocr_result,
        evidence=evidence,
        recovered_targets=recovered_targets,
        intervals=intervals,
        authoritative_answer_labels=native_labels if native_trusted else None,
    )
    assembled = assemble_page_extractions(page_extractions, title=title)
    assembled = attach_source_regions(assembled, pages=page_extractions)
    # Recover options that OCR left inline in the stem before quality is rebuilt,
    # so a question whose options were merely mis-placed is not sent to the
    # review lane as `missing_options` (owner policy: only a genuinely no-stem /
    # no-options question is review-blocking).
    assembled = _recover_inline_stem_options(assembled)
    assembled = rebuild_assembly_quality(assembled)

    try:
        assembled, visual_stats, visual_audit = reconcile_mistral_source_visuals(
            assembled,
            pdf_data=data,
            ocr_pages=ocr_result.pages,
            layout=evidence.layout,
            source_sha256=ocr_result.source_sha256,
            storage_namespace=str(asset_namespace or ""),
            should_cancel=should_cancel,
        )
    except RuntimeError as exc:
        if "Cancellation requested during Stage-3" in str(exc):
            raise ExamPrepPipelineCancelled(str(exc)) from exc
        raise

    targeted_cost = (
        targeted_result.estimated_cost_unit if targeted_result is not None else Decimal("0")
    )
    spent_before_stage5 = ocr_result.estimated_cost_unit + targeted_cost
    decisions = score_region_risks(
        projection=assembled.projection,
        layout=evidence.layout,
        recovered_solution_targets=set(recovered_targets),
        unresolved_solution_targets=set(unresolved_targets),
    )
    remaining_stage5_budget = max(Decimal("0"), total_budget - spent_before_stage5)

    try:
        assembled, stage5_audit = finalize_stage5_regions(
            assembled,
            pdf_data=data,
            decisions=decisions,
            max_cost_usd=remaining_stage5_budget,
            should_cancel=should_cancel,
            on_region_complete=on_region_complete,
        )
    except RuntimeError as exc:
        if "Cancellation requested during Stage-5" in str(exc):
            raise ExamPrepPipelineCancelled(str(exc)) from exc
        raise
    stage5_stats = dict(stage5_audit.get("stats") or {})
    stage5_resolved_solutions = _resolved_solution_numbers(stage5_audit)
    remaining_unresolved_targets = sorted(
        set(unresolved_targets) - stage5_resolved_solutions
    )

    assembled, integrity_stats = apply_projection_integrity(assembled)
    audit = build_strict_exam_audit(
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
    stage5_primary_calls = int(stage5_stats.get("primaryCalls") or 0)
    stage5_main_calls = int(stage5_stats.get("mainCalls") or 0)
    stage5_calls = stage5_primary_calls + stage5_main_calls
    stage5_cost, stage5_cost_complete = _stage5_success_cost_usd(stage5_audit)
    stage5_budget_audit = stage5_audit.get("budget")
    try:
        stage5_charged_cost = Decimal(
            str(
                stage5_budget_audit.get("chargedCostUsd")
                if isinstance(stage5_budget_audit, Mapping)
                else stage5_cost
            )
        )
    except (InvalidOperation, TypeError, ValueError):
        # A malformed runtime audit is not permission to under-report spend.
        stage5_charged_cost = remaining_stage5_budget
        stage5_cost_complete = False
    stage5_charged_cost = max(stage5_cost, stage5_charged_cost)
    if isinstance(stage5_budget_audit, Mapping):
        stage5_cost_complete = stage5_cost_complete and bool(
            stage5_budget_audit.get("costEstimateComplete", False)
        )
    total_estimated_cost = spent_before_stage5 + stage5_charged_cost

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
            "nativeAnswerEvidence": native.safe_dict(trusted=native_trusted),
            "nativeAnswerAuthorityCount": len(native_labels) if native_trusted else 0,
            "targetedSolutionHeadingCalls": targeted_calls,
            "targetedSolutionHeadingRetries": targeted_retries,
            "targetedSolutionHeadingRecovered": len(recovered_targets),
            "targetedSolutionPreciseRegionCount": len(recovered_layout_regions),
            "targetedSolutionHeadingUnresolved": remaining_unresolved_targets,
            "targetedSolutionHeadingSkippedBudget": targeted_skipped_budget,
            "targetedSolutionHeadingBudgetPlan": {
                "targetCount": int(targeted_budget["targetCount"]),
                "cropPageCount": int(targeted_budget["cropPageCount"]),
                "reserveUsd": format(targeted_budget["reserveUsd"], "f"),
                "minimumStage5ReserveUsd": format(
                    targeted_budget["minimumStage5ReserveUsd"], "f"
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
            "spentBeforeStage5Usd": format(spent_before_stage5, "f"),
            "stage5SuccessfulCallEstimatedCostUsd": format(stage5_cost, "f"),
            "stage5FailedCallReservedCostUsd": str(
                stage5_budget_audit.get("failedCallReservedCostUsd", "0")
                if isinstance(stage5_budget_audit, Mapping)
                else "0"
            ),
            "stage5ChargedCostUsd": format(stage5_charged_cost, "f"),
            "stage5CostEstimateComplete": stage5_cost_complete,
            "stage5CostEstimateScope": "successful_calls_plus_failed_call_reservations",
            "totalEstimatedCostUsd": format(total_estimated_cost, "f"),
            "budgetWithinLimit": total_estimated_cost <= total_budget,
            "visualPipeline": visual_audit,
            "visualSourceContracts": _server_visual_source_contracts(assembled.projection),
            "visualAssetRegistry": build_visual_asset_registry(
                assembled.projection,
                source_sha256=ocr_result.source_sha256,
            ),
            "visualAssetsAttached": int(visual_stats.get("assetsAttached", 0)),
            "visualQuestionAssets": int(visual_stats.get("questionVisuals", 0)),
            "visualOptionAssets": int(visual_stats.get("optionVisuals", 0)),
            "visualSolutionAssets": int(visual_stats.get("solutionVisuals", 0)),
            "visualReviewOnlyAssets": int(visual_stats.get("reviewOnlyAssets", 0)),
            "visualWholePageFallbacks": int(visual_stats.get("wholePageFallbacks", 0)),
            "visualSanityFailures": int(visual_stats.get("sanityFailures", 0)),
            "riskEngine": stage5_audit,
            "riskRegionCount": int(stage5_stats.get("regions") or 0),
            "riskSuspiciousRegionCount": sum(bool(item.suspicious) for item in decisions),
            "targetedRegionPrimaryCalls": stage5_primary_calls,
            "targetedRegionSecondOpinionCalls": stage5_main_calls,
            "targetedRegionLlmCalls": stage5_calls,
            "targetedRegionVerified": int(stage5_stats.get("verified") or 0),
            "targetedRegionRepaired": int(stage5_stats.get("repaired") or 0),
            "targetedRegionUnresolved": int(stage5_stats.get("blocked") or 0),
            "targetedRegionDeferred": 0,
            "generalLlmCalls": 0,
            "totalProviderCalls": (
                ocr_result.provider_call_count + targeted_calls + stage5_calls
            ),
        }
    )

    transcript_stats = {
        "attempted": stage5_primary_calls,
        "verified": int(stage5_stats.get("verified") or 0),
        "repaired": int(stage5_stats.get("repaired") or 0),
        "retried": ocr_result.retry_count + targeted_retries,
        "unresolved": (
            int(stage5_stats.get("blocked") or 0)
            + len(remaining_unresolved_targets)
        ),
        "visuals_attached": int(visual_stats.get("assetsAttached", 0)),
        "tables_verified": int(visual_stats.get("tableVisuals", 0)),
    }
    transcript = render_strict_exam_transcript(
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
            "attempted": stage5_primary_calls,
            "verified": int(stage5_stats.get("verified") or 0),
            "repaired": int(stage5_stats.get("repaired") or 0),
            "retried": 0,
            "unresolved": int(stage5_stats.get("blocked") or 0),
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
