"""Stable production entrypoint for the researched Mistral OCR4 Exam Prep engine.

This module is the only supported production-facing import for the Mistral
research pipeline. It intentionally has no Exam Prep V4, management-command,
benchmark, or general-LLM call site.

Stage 2 implements the OCR4 document core:
PDF -> <=30-page OCR4 chunks -> physical page remap -> deterministic layout /
booklet ranges / RTL ordering -> question regions -> solution-heading state
machine -> targeted heading recovery for gap/invalid answers only -> deterministic
question/answer assembly -> existing ExamPrepPipelineResult contract.

Verifier escalation and precise visual reconciliation are later stages.
"""
from __future__ import annotations

from dataclasses import dataclass
from html import unescape
import io
import re
from typing import Any, Callable, Mapping, Sequence

from PIL import Image

from .exam_prep_mistral_booklet_ranges import extract_booklet_ranges
from .exam_prep_mistral_layout_analysis import analyze_ocr_document
from .exam_prep_mistral_ocr_transport import (
    MistralOCR4Config,
    MistralOCR4Error,
    OCR4DocumentResult,
    document_root,
    fetch_ocr4_document,
)
from .exam_prep_mistral_solution_headings import (
    AlignedSolutionHeading,
    align_solution_headings,
    audit_solution_headings,
    normalize_solution_option_label,
    parse_solution_heading,
    solution_heading_candidates,
)
from .exam_prep_page_output import (
    build_strict_page_first_audit,
    render_strict_page_first_transcript,
)
from .exam_prep_page_records import PageAssemblyResult, assemble_page_extractions
from .exam_prep_page_source import SourcePageExtraction, attach_source_regions
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


ProgressCallback = Callable[[int, int], None]
CancelCheck = Callable[[], bool]

PRODUCTION_ENGINE = "mistral_ocr4_document"
PRODUCTION_ENTRYPOINT = (
    "apps.classes.services.exam_prep_mistral_production."
    "run_exam_prep_mistral_pipeline"
)

_DIGIT_TRANS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)
_QUESTION_HEADING_RE = re.compile(
    r"^\s*[#«»\"'()]*\s*[0-9۰-۹٠-٩]{1,3}\s*[-–—.)]\s*"
)
_OPTION_MARKER_RE = re.compile(
    r"(?:^|\s)(?P<number>[1-4۱-۴١-٤])\s*(?:[)\].:：\-–—])"
)
_PAREN_OPTION_RE = re.compile(
    r"[(\[]\s*(?P<number>[1-4۱-۴١-٤])\s*[)\]]"
)
_HTML_BREAK_RE = re.compile(
    r"</?(?:tr|td|th|p|div|li|br)\b[^>]*>", re.IGNORECASE
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_OWN_CRITICAL_CODES = frozenset(
    {
        "mistral_question_number_unverified",
        "mistral_question_option_parse_failed",
        "mistral_solution_heading_unresolved",
        "mistral_booklet_range_mismatch",
        "mistral_duplicate_question_anchor",
    }
)


@dataclass(frozen=True, slots=True)
class MistralDocumentEvidence:
    layout: dict[str, Any]
    booklet_ranges: dict[str, Any]
    solution_headings: dict[str, Any]


def _cancel(should_cancel: CancelCheck | None) -> None:
    if should_cancel is not None and should_cancel():
        raise ExamPrepPipelineCancelled("Cancellation requested.")


def _integer(value: Any) -> int | None:
    match = re.search(r"\d+", str(value or "").translate(_DIGIT_TRANS))
    if not match:
        return None
    try:
        value = int(match.group(0))
    except ValueError:
        return None
    return value if value > 0 else None


def _normalized_bbox(value: Any) -> dict[str, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        x0, y0, x1, y1 = (float(item) for item in value)
    except (TypeError, ValueError):
        return None
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        return None
    return {"x0": x0, "y0": y0, "x1": x1, "y1": y1}


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


def _marker_sequence(
    text: str,
    pattern: re.Pattern[str],
) -> list[tuple[int, int, int]] | None:
    markers: list[tuple[int, int, int]] = []
    for match in pattern.finditer(text):
        number = _integer(match.group("number"))
        if number in {1, 2, 3, 4}:
            markers.append((int(number), match.start(), match.end()))
    if not markers:
        return None
    candidates: list[list[tuple[int, int, int]]] = []
    for expected_sequence in ((1, 2, 3, 4), (4, 3, 2, 1)):
        for start, marker in enumerate(markers):
            if marker[0] != expected_sequence[0]:
                continue
            chosen = [marker]
            cursor = start + 1
            for expected in expected_sequence[1:]:
                while cursor < len(markers) and markers[cursor][0] != expected:
                    cursor += 1
                if cursor >= len(markers):
                    break
                chosen.append(markers[cursor])
                cursor += 1
            if len(chosen) == 4:
                candidates.append(chosen)
    return min(candidates, key=lambda row: row[0][1]) if candidates else None


def _clean_option_text(value: str) -> str:
    return clean_exam_markdown(str(value or "").strip(" \t\r\n،,;؛|-–—("))


def parse_question_region_text(value: Any) -> tuple[str, list[dict[str, str]], str]:
    """Deterministically split one OCR4 question region into stem + 4 options."""

    text = clean_exam_markdown(value or "")
    if not text:
        return "", [], "missing"
    body = _QUESTION_HEADING_RE.sub("", text, count=1)

    sequence = _marker_sequence(body, _OPTION_MARKER_RE)
    if sequence is not None:
        stem = clean_exam_markdown(body[: sequence[0][1]])
        options: list[dict[str, str]] = []
        for index, marker in enumerate(sequence):
            end = sequence[index + 1][1] if index + 1 < len(sequence) else len(body)
            option_text = _clean_option_text(body[marker[2] : end])
            options.append({"label": str(marker[0]), "text_markdown": option_text})
        if all(item["text_markdown"] for item in options):
            options.sort(key=lambda item: int(item["label"]))
            return stem, options, "marker"

    sequence = _marker_sequence(body, _PAREN_OPTION_RE)
    if sequence is None:
        return body, [], "unparsed"
    line_start = body.rfind("\n", 0, sequence[0][1]) + 1
    before_first = body[line_start : sequence[0][1]].strip()
    suffix_style = bool(before_first.strip(" \t-–—•"))
    options = []
    if suffix_style:
        cursor = line_start
        for marker in sequence:
            option_text = _clean_option_text(body[cursor : marker[1]])
            options.append({"label": str(marker[0]), "text_markdown": option_text})
            cursor = marker[2]
        stem_end = line_start
        style = "parenthesized_suffix"
    else:
        for index, marker in enumerate(sequence):
            end = sequence[index + 1][1] if index + 1 < len(sequence) else len(body)
            option_text = _clean_option_text(body[marker[2] : end])
            options.append({"label": str(marker[0]), "text_markdown": option_text})
        stem_end = sequence[0][1]
        style = "parenthesized_prefix"
    if any(not item["text_markdown"] for item in options):
        return body, [], "unparsed"
    options.sort(key=lambda item: int(item["label"]))
    return clean_exam_markdown(body[:stem_end]), options, style


def _question_record(region: Mapping[str, Any]) -> dict[str, Any] | None:
    number = _integer(region.get("questionNumber"))
    raw_number = _integer(region.get("rawQuestionNumber"))
    if number is None:
        return None
    stem, options, _style = parse_question_region_text(region.get("text"))
    issues = [str(code) for code in (region.get("issues") or []) if str(code).strip()]
    if bool(region.get("numberRecoveredFromSequence")) or (
        raw_number is not None and raw_number != number
    ):
        issues.append("mistral_question_number_unverified")
    if len(options) != 4:
        issues.append("mistral_question_option_parse_failed")
    return {
        "question_number": number,
        "record_type": "question",
        "question_text_markdown": stem,
        "options": options,
        "confidence": 0.0,
        "issues": list(dict.fromkeys(issues)),
        "source_bbox": _normalized_bbox(region.get("bbox")),
    }


def _analysis_pages(evidence: MistralDocumentEvidence) -> dict[int, Mapping[str, Any]]:
    output: dict[int, Mapping[str, Any]] = {}
    for page in evidence.layout.get("pages") or []:
        if not isinstance(page, Mapping):
            continue
        number = _integer(page.get("originalPageNumber"))
        if number is not None:
            output[number] = page
    return output


def _question_anchor_counts(evidence: MistralDocumentEvidence) -> dict[int, int]:
    counts: dict[int, int] = {}
    for page in evidence.layout.get("pages") or []:
        if not isinstance(page, Mapping):
            continue
        if str(page.get("pageRole") or "") != "question":
            continue
        for region in page.get("regions") or []:
            if not isinstance(region, Mapping) or str(region.get("kind") or "") != "question":
                continue
            number = _integer(region.get("questionNumber"))
            if number is not None:
                counts[number] = counts.get(number, 0) + 1
    return counts


def _question_numbers(evidence: MistralDocumentEvidence) -> list[int]:
    numbers: set[int] = set()
    for page in evidence.layout.get("pages") or []:
        if not isinstance(page, Mapping):
            continue
        if str(page.get("pageRole") or "") != "question":
            continue
        for region in page.get("regions") or []:
            if not isinstance(region, Mapping) or str(region.get("kind") or "") != "question":
                continue
            number = _integer(region.get("questionNumber"))
            if number is not None:
                numbers.add(number)
    return sorted(numbers)


def _aligned_solutions(
    result: OCR4DocumentResult,
    *,
    first_expected: int,
    last_expected: int,
) -> tuple[list[AlignedSolutionHeading], list[int], list[int]]:
    candidates = []
    for page in result.pages:
        physical = int(page.get("sourcePhysicalPage") or int(page.get("index") or 0) + 1)
        candidates.extend(
            solution_heading_candidates(page, physical_page_number=physical)
        )
    aligned = align_solution_headings(
        candidates,
        first_expected_question=first_expected,
        last_expected_question=last_expected,
    )
    accepted = list(aligned.get("accepted") or [])
    missing = sorted(
        {
            int(value)
            for value in (aligned.get("missingQuestionNumbers") or [])
            if int(value) > 0
        }
    )
    invalid = sorted(
        {
            item.question_number
            for item in accepted
            if not item.option_label_valid
        }
    )
    return accepted, missing, invalid


def _solution_region(
    page: Mapping[str, Any] | None,
    heading: AlignedSolutionHeading,
) -> Mapping[str, Any] | None:
    if not isinstance(page, Mapping):
        return None
    regions = [
        item
        for item in (page.get("regions") or [])
        if isinstance(item, Mapping) and str(item.get("kind") or "") == "solution"
    ]
    exact = [
        item
        for item in regions
        if int(item.get("headingProviderIndex") or -1) == heading.provider_block_index
    ]
    if exact:
        return exact[0]
    same_number = [
        item
        for item in regions
        if _integer(item.get("questionNumber")) == heading.question_number
    ]
    return same_number[0] if len(same_number) == 1 else None


def _target_crop_specs(
    accepted: Sequence[AlignedSolutionHeading],
    targets: Sequence[int],
) -> list[tuple[int, str]]:
    ordered = sorted(accepted, key=lambda item: item.question_number)
    specs: list[tuple[int, str]] = []
    for target in sorted({int(value) for value in targets if int(value) > 0}):
        candidates = [item for item in ordered if item.column in {"left", "right"}]
        if not candidates:
            continue
        anchor = min(
            candidates,
            key=lambda item: (
                abs(item.question_number - target),
                0 if item.question_number >= target else 1,
            ),
        )
        spec = (anchor.physical_page_number, anchor.column)
        if spec not in specs:
            specs.append(spec)
    return specs[:12]


def _render_target_crop_pdf(
    data: bytes,
    specs: Sequence[tuple[int, str]],
    *,
    dpi: int = 250,
) -> bytes:
    if not specs:
        return b""
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:  # pragma: no cover
        raise ExamPrepPdfError("pypdfium2 is required for targeted OCR crops.") from exc
    document = pdfium.PdfDocument(data)
    images: list[Image.Image] = []
    try:
        scale = float(dpi) / 72.0
        for page_number, side in specs:
            if page_number < 1 or page_number > len(document):
                continue
            page = document[page_number - 1]
            try:
                bitmap = page.render(scale=scale)
                try:
                    image = bitmap.to_pil().convert("RGB")
                finally:
                    bitmap.close()
            finally:
                page.close()
            width, height = image.size
            x0 = int(width * (0.02 if side == "left" else 0.49))
            x1 = int(width * (0.51 if side == "left" else 0.98))
            y0 = int(height * 0.075)
            y1 = int(height * 0.965)
            crop = image.crop((x0, y0, x1, y1))
            image.close()
            images.append(crop)
        if not images:
            return b""
        output = io.BytesIO()
        first, *rest = images
        first.save(
            output,
            format="PDF",
            save_all=True,
            append_images=rest,
            resolution=float(dpi),
            creationDate="D:20000101000000Z",
            modDate="D:20000101000000Z",
        )
        return output.getvalue()
    finally:
        for image in images:
            image.close()
        document.close()


def _heading_lines(value: Any) -> list[str]:
    text = _HTML_BREAK_RE.sub("\n", str(value or ""))
    text = _HTML_TAG_RE.sub(" ", text)
    text = unescape(text)
    return [line.strip() for line in text.splitlines() if line.strip()]


def _collect_crop_headings(
    result: OCR4DocumentResult,
    specs: Sequence[tuple[int, str]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    pages = sorted(result.pages, key=lambda page: int(page.get("sourcePhysicalPage") or 0))
    for crop_index, page in enumerate(pages):
        if crop_index >= len(specs):
            continue
        physical_page, side = specs[crop_index]
        for block in page.get("blocks") or []:
            if not isinstance(block, Mapping):
                continue
            for line in _heading_lines(block.get("content")):
                parsed = parse_solution_heading(line)
                if not parsed:
                    continue
                option, _normalized, valid = normalize_solution_option_label(
                    int(parsed["rawOptionLabel"])
                )
                output.append(
                    {
                        "physicalPageNumber": physical_page,
                        "column": side,
                        "rawQuestionNumber": int(parsed["rawQuestionNumber"]),
                        "optionLabel": option,
                        "optionLabelValid": valid,
                    }
                )
    return output


def _resolve_target_headings(
    headings: Sequence[Mapping[str, Any]],
    targets: Sequence[int],
) -> dict[int, tuple[str, int, str]]:
    """Target-only merge: non-target headings can never alter persisted answers."""

    resolved: dict[int, tuple[str, int, str]] = {}
    for target in sorted({int(value) for value in targets if int(value) > 0}):
        candidates = [
            item
            for item in headings
            if int(item.get("rawQuestionNumber") or 0) == target
            and item.get("optionLabelValid") is True
            and int(item.get("optionLabel") or 0) in {1, 2, 3, 4}
        ]
        labels = {int(item["optionLabel"]) for item in candidates}
        if len(labels) != 1:
            continue
        label = next(iter(labels))
        evidence = [item for item in candidates if int(item["optionLabel"]) == label]
        pages = {int(item.get("physicalPageNumber") or 0) for item in evidence}
        columns = {str(item.get("column") or "") for item in evidence}
        if len(pages) != 1 or len(columns) != 1:
            continue
        resolved[target] = (str(label), next(iter(pages)), next(iter(columns)))
    return resolved


def _targeted_recovery(
    data: bytes,
    *,
    accepted: Sequence[AlignedSolutionHeading],
    missing: Sequence[int],
    invalid: Sequence[int],
    config: MistralOCR4Config,
    should_cancel: CancelCheck | None,
) -> tuple[dict[int, tuple[str, int, str]], OCR4DocumentResult | None]:
    targets = sorted(set(missing) | set(invalid))
    if not targets:
        return {}, None
    specs = _target_crop_specs(accepted, targets)
    if not specs:
        return {}, None
    crop_pdf = _render_target_crop_pdf(data, specs)
    if not crop_pdf:
        return {}, None
    _cancel(should_cancel)
    result = fetch_ocr4_document(
        crop_pdf,
        config=MistralOCR4Config(
            model=config.model,
            endpoint=config.endpoint,
            max_pages_per_request=min(30, max(1, len(specs))),
            max_chunk_bytes=config.max_chunk_bytes,
            max_response_bytes=config.max_response_bytes,
            timeout_seconds=config.timeout_seconds,
            max_attempts=config.max_attempts,
            retry_backoff_seconds=config.retry_backoff_seconds,
            retry_jitter_seconds=config.retry_jitter_seconds,
            word_confidence=False,
            checkpoint_enabled=config.checkpoint_enabled,
        ),
    )
    _cancel(should_cancel)
    return _resolve_target_headings(_collect_crop_headings(result, specs), targets), result


def _column_bbox(side: str) -> dict[str, float]:
    if side == "left":
        return {"x0": 0.02, "y0": 0.075, "x1": 0.51, "y1": 0.965}
    return {"x0": 0.49, "y0": 0.075, "x1": 0.98, "y1": 0.965}


def _build_page_extractions(
    *,
    result: OCR4DocumentResult,
    evidence: MistralDocumentEvidence,
    recovered_targets: Mapping[int, tuple[str, int, str]],
) -> list[SourcePageExtraction]:
    records_by_page: dict[int, list[dict[str, Any]]] = {}
    pages = _analysis_pages(evidence)
    question_numbers: list[int] = []

    for page_number, page in sorted(pages.items()):
        if str(page.get("pageRole") or "") != "question":
            continue
        for region in page.get("regions") or []:
            if not isinstance(region, Mapping) or str(region.get("kind") or "") != "question":
                continue
            record = _question_record(region)
            if record is None:
                continue
            question_numbers.append(int(record["question_number"]))
            records_by_page.setdefault(page_number, []).append(record)

    if not question_numbers:
        return []
    accepted, _missing, _invalid = _aligned_solutions(
        result,
        first_expected=min(question_numbers),
        last_expected=max(question_numbers),
    )
    accepted_numbers: set[int] = set()
    for heading in accepted:
        accepted_numbers.add(heading.question_number)
        page = pages.get(heading.physical_page_number)
        region = _solution_region(page, heading)
        recovered = recovered_targets.get(heading.question_number)
        if recovered is not None:
            label = recovered[0]
        elif heading.option_label_valid and heading.option_label in {1, 2, 3, 4}:
            label = str(heading.option_label)
        else:
            label = None
        issues = [
            str(code)
            for code in ((region.get("issues") or []) if isinstance(region, Mapping) else [])
            if str(code).strip()
        ]
        if heading.question_number_recovered:
            issues.append("solution_heading_number_recovered")
        if recovered is not None:
            issues.append("targeted_solution_heading_recovered")
        if label is None:
            issues.append("mistral_solution_heading_unresolved")
        records_by_page.setdefault(heading.physical_page_number, []).append(
            {
                "question_number": heading.question_number,
                "record_type": "solution",
                "correct_option_label": label,
                "teacher_solution_markdown": (
                    clean_exam_markdown(region.get("text") or "")
                    if isinstance(region, Mapping)
                    else ""
                ),
                "final_answer_markdown": f"گزینه {label}" if label else "",
                "confidence": 0.0,
                "issues": list(dict.fromkeys(issues)),
                "source_bbox": (
                    _normalized_bbox(region.get("bbox"))
                    if isinstance(region, Mapping)
                    else _column_bbox(heading.column)
                ),
            }
        )

    for question_number, (label, page_number, side) in recovered_targets.items():
        if question_number in accepted_numbers:
            continue
        records_by_page.setdefault(page_number, []).append(
            {
                "question_number": question_number,
                "record_type": "answer",
                "correct_option_label": label,
                "final_answer_markdown": f"گزینه {label}",
                "confidence": 0.0,
                "issues": ["targeted_solution_heading_recovered"],
                "source_bbox": _column_bbox(side),
            }
        )

    return [
        SourcePageExtraction.model_validate(
            {"page_number": page_number, "records": records}
        )
        for page_number, records in sorted(records_by_page.items())
    ]


def _booklet_contract_issues(
    evidence: MistralDocumentEvidence,
    question_numbers: Sequence[int],
) -> list[dict[str, Any]]:
    ranges = evidence.booklet_ranges.get("ranges") or []
    valid = [
        item
        for item in ranges
        if isinstance(item, Mapping) and item.get("countMatchesRange") is True
    ]
    if not valid:
        return []
    declared: set[int] = set()
    for item in valid:
        start = _integer(item.get("start"))
        end = _integer(item.get("end"))
        if start is not None and end is not None and end >= start:
            declared.update(range(start, end + 1))
    observed = {int(value) for value in question_numbers if int(value) > 0}
    if declared == observed:
        return []
    return [
        {
            "code": "mistral_booklet_range_mismatch",
            "severity": "critical",
            "scopeKey": "default",
            "questionNumber": 0,
            "sourcePages": sorted(
                {
                    int(item.get("physicalPageNumber") or 0)
                    for item in valid
                    if int(item.get("physicalPageNumber") or 0) > 0
                }
            ),
        }
    ]


def _promote_own_critical(audit: dict[str, Any], extra: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    output = dict(audit)
    issues = [dict(item) for item in (audit.get("issues") or []) if isinstance(item, Mapping)]
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
    output["status"] = "passed" if output.get("questionCount") and not critical else "needs_review"
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
    """Run the production OCR4 core without any general LLM verifier calls."""

    del model, scope_hint
    _cancel(should_cancel)
    config = MistralOCR4Config.from_env()
    completed = 0

    def chunk_done(chunk_result) -> None:
        nonlocal completed
        completed += len(chunk_result.chunk.physical_pages)
        if on_page_complete is not None:
            from pypdf import PdfReader

            total = len(PdfReader(io.BytesIO(data)).pages)
            on_page_complete(min(completed, total), total)
        _cancel(should_cancel)

    try:
        ocr_result = fetch_ocr4_document(
            data,
            config=config,
            chunk_callback=chunk_done,
        )
    except MistralOCR4Error as exc:
        raise ExamPrepPdfError(str(exc)) from exc

    _cancel(should_cancel)
    root = document_root(ocr_result)
    evidence = analyze_mistral_document_evidence(
        root,
        original_page_numbers=list(range(1, ocr_result.page_count + 1)),
    )
    question_numbers = _question_numbers(evidence)
    if not question_numbers:
        raise NoExamQuestionsFound("هیچ سؤال شماره‌داری در PDF تشخیص داده نشد.")

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
    unresolved_targets = sorted((set(missing) | set(invalid)) - set(recovered_targets))

    page_extractions = _build_page_extractions(
        result=ocr_result,
        evidence=evidence,
        recovered_targets=recovered_targets,
    )
    assembled = assemble_page_extractions(page_extractions, title=title)
    assembled = attach_source_regions(assembled, pages=page_extractions)
    assembled = rebuild_assembly_quality(assembled)
    assembled, integrity_stats = apply_projection_integrity(assembled)

    audit = build_strict_page_first_audit(assembled, failed_page_numbers=[])
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

    targeted_calls = targeted_result.provider_call_count if targeted_result else 0
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
            "ocrEstimatedCostUnit": format(ocr_result.estimated_cost_unit, "f"),
            "targetedSolutionHeadingCalls": targeted_calls,
            "targetedSolutionHeadingRetries": targeted_retries,
            "targetedSolutionHeadingRecovered": len(recovered_targets),
            "targetedSolutionHeadingUnresolved": unresolved_targets,
            "generalLlmCalls": 0,
            "totalProviderCalls": ocr_result.provider_call_count + targeted_calls,
        }
    )

    transcript = render_strict_page_first_transcript(
        assembled,
        failed_page_numbers=[],
        targeted_repair_stats={
            "attempted": targeted_calls,
            "verified": len(recovered_targets),
            "repaired": len(recovered_targets),
            "retried": ocr_result.retry_count + targeted_retries,
            "unresolved": len(unresolved_targets),
            "visuals_attached": 0,
            "tables_verified": 0,
        },
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
            "unresolved": len(unresolved_targets),
        },
        verification_stats={
            "attempted": 0,
            "verified": 0,
            "repaired": 0,
            "retried": 0,
            "unresolved": 0,
            "visuals_attached": 0,
            "tables_verified": 0,
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
