"""Production Mistral OCR4 document engine for the simple Exam Prep flow.

This is intentionally NOT Exam Prep V4. It preserves the normal
ClassCreationSession / exam_prep_json product contract and uses the OCR4
full-document research pipeline behind the existing simple UI.

The source PDF is authoritative. OCR4 provides bounded document geometry and
candidate transcription. Question/answer matching is deterministic by printed
question number. A single targeted OCR crop request is permitted only for
missing/invalid solution headings, and its output may modify target headings
only.
"""
from __future__ import annotations

from dataclasses import replace
from html import unescape
import io
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Callable, Mapping, Sequence

from PIL import Image

from .exam_prep_mistral_solution_headings import (
    AlignedSolutionHeading,
    align_solution_headings,
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
from .exam_prep_question_full_verifier import _rebuild_result
from .exam_prep_question_verifier import rebuild_assembly_quality
from .exam_prep_source_first import (
    SourceFirstOCRConfig,
    SourceFirstProviderError,
    analyze_source_result,
    fetch_document_ocr4,
)
from .exam_prep_text_quality import has_broken_persian_text
from .exam_prep_utils import clean_exam_markdown


ProgressCallback = Callable[[int, int], None]
CancelCheck = Callable[[], bool]

_DIGIT_TRANS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)
_HEADING_RE = re.compile(r"^\s*[0-9۰-۹٠-٩]{1,3}\s*[-–—.)]\s*")
_PRIMARY_OPTION_RE = re.compile(
    r"(?<![0-9۰-۹٠-٩(\[])(?P<number>[1-4۱-۴١-٤])\s*(?:[)\].:：\-–—])"
)
_PAREN_OPTION_RE = re.compile(r"[(\[]\s*(?P<number>[1-4۱-۴١-٤])\s*[)\]]")
_HTML_BREAK_RE = re.compile(
    r"</?(?:tr|td|th|p|div|li|br)\b[^>]*>",
    re.IGNORECASE,
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_VISUAL_ISSUES = frozenset(
    {
        "visual_reference_without_ocr_visual",
        "caption_visual_count_mismatch",
        "visual_options_grouped_in_single_block",
        "table_contains_visual_or_empty_cells",
        "uncovered_graphics_in_region",
    }
)
_SOURCE_CORRUPTION_CHARS = ("\x00", "\ufffd", "□")


def _cancel(should_cancel: CancelCheck | None) -> None:
    if should_cancel is not None and should_cancel():
        raise ExamPrepPipelineCancelled("Cancellation requested.")


def _latin_digit(value: Any) -> int | None:
    raw = str(value or "").translate(_DIGIT_TRANS)
    match = re.search(r"\d+", raw)
    if not match:
        return None
    try:
        return int(match.group(0))
    except ValueError:
        return None


def _markers(text: str, pattern: re.Pattern[str]) -> list[tuple[int, int, int]]:
    result: list[tuple[int, int, int]] = []
    for match in pattern.finditer(text):
        number = _latin_digit(match.group("number"))
        if number not in {1, 2, 3, 4}:
            continue
        if match.start() < 8 and re.search(r"[-–—]\s*$", match.group(0)):
            continue
        result.append((number, match.start(), match.end()))
    return result


def _option_sequence(
    markers: Sequence[tuple[int, int, int]],
) -> list[tuple[int, int, int]] | None:
    candidates: list[list[tuple[int, int, int]]] = []
    for sequence in ((1, 2, 3, 4), (4, 3, 2, 1)):
        for start_index, marker in enumerate(markers):
            if marker[0] != sequence[0]:
                continue
            chosen = [marker]
            cursor = start_index + 1
            valid = True
            for expected in sequence[1:]:
                while cursor < len(markers) and markers[cursor][0] != expected:
                    cursor += 1
                if cursor >= len(markers):
                    valid = False
                    break
                chosen.append(markers[cursor])
                cursor += 1
            if valid:
                candidates.append(chosen)
    if not candidates:
        return None
    return min(candidates, key=lambda item: item[0][1])


def _clean_option_text(value: str) -> str:
    return clean_exam_markdown(
        str(value or "").strip().strip(" \t\r\n،,;؛|-–—(")
    )


def parse_question_region_text(
    value: Any,
) -> tuple[str, list[dict[str, str]], str]:
    """Split OCR4 region text into stem and four printed options."""

    text = clean_exam_markdown(value or "")
    if not text:
        return "", [], "missing"

    primary = _option_sequence(_markers(text, _PRIMARY_OPTION_RE))
    if primary:
        options: list[dict[str, str]] = []
        for index, marker in enumerate(primary):
            end = primary[index + 1][1] if index + 1 < len(primary) else len(text)
            options.append(
                {
                    "label": str(marker[0]),
                    "text_markdown": _clean_option_text(text[marker[2] : end]),
                }
            )
        if all(item["text_markdown"] for item in options):
            stem = _HEADING_RE.sub("", text[: primary[0][1]].strip(), count=1)
            return clean_exam_markdown(stem), sorted(
                options,
                key=lambda item: int(item["label"]),
            ), "prefix"

    parenthesized = _option_sequence(_markers(text, _PAREN_OPTION_RE))
    if parenthesized:
        line_start = text.rfind("\n", 0, parenthesized[0][1]) + 1
        before_marker = text[line_start : parenthesized[0][1]].strip()
        is_suffix = bool(before_marker.strip(" \t-–—•"))
        options = []
        if is_suffix:
            cursor = line_start
            for marker in parenthesized:
                options.append(
                    {
                        "label": str(marker[0]),
                        "text_markdown": _clean_option_text(text[cursor : marker[1]]),
                    }
                )
                cursor = marker[2]
            stem_end = line_start
            style = "suffix"
        else:
            for index, marker in enumerate(parenthesized):
                end = (
                    parenthesized[index + 1][1]
                    if index + 1 < len(parenthesized)
                    else len(text)
                )
                options.append(
                    {
                        "label": str(marker[0]),
                        "text_markdown": _clean_option_text(text[marker[2] : end]),
                    }
                )
            stem_end = parenthesized[0][1]
            style = "parenthesized_prefix"
        if all(item["text_markdown"] for item in options):
            stem = _HEADING_RE.sub("", text[:stem_end].strip(), count=1)
            return clean_exam_markdown(stem), sorted(
                options,
                key=lambda item: int(item["label"]),
            ), style

    return clean_exam_markdown(_HEADING_RE.sub("", text, count=1)), [], "unparsed"


def _question_visual_required(region: Mapping[str, Any]) -> bool:
    issues = {str(value) for value in (region.get("issues") or [])}
    return bool(
        region.get("visuals")
        or region.get("uncoveredGraphics")
        or issues.intersection(_VISUAL_ISSUES)
    )


def _visual_placeholders() -> list[dict[str, str]]:
    return [
        {
            "label": str(number),
            "text_markdown": f"گزینهٔ تصویری {number} — در تصویر منبع",
        }
        for number in range(1, 5)
    ]


def _safe_bbox(value: Any) -> dict[str, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        x0, y0, x1, y1 = (float(item) for item in value)
    except (TypeError, ValueError):
        return None
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        return None
    return {"x0": x0, "y0": y0, "x1": x1, "y1": y1}


def _question_record(region: Mapping[str, Any]) -> dict[str, Any] | None:
    number = _latin_digit(region.get("questionNumber"))
    if number is None or number < 1:
        return None
    stem, options, _style = parse_question_region_text(region.get("text"))
    visual_required = _question_visual_required(region)
    issues = [str(value) for value in (region.get("issues") or [])]
    if len(options) != 4:
        if visual_required and not options:
            options = _visual_placeholders()
            issues.append("visual_options_source_crop_authoritative")
        else:
            issues.append("unexpected_option_count")
    return {
        "question_number": number,
        "record_type": "question",
        "question_text_markdown": stem,
        "options": options,
        "confidence": 0.0,
        "issues": list(dict.fromkeys(issues)),
        "source_bbox": _safe_bbox(region.get("bbox")),
    }


def _analysis_page_map(analysis: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    return {
        int(page.get("originalPageNumber") or 0): page
        for page in (analysis.get("pages") or [])
        if isinstance(page, Mapping) and int(page.get("originalPageNumber") or 0) > 0
    }


def _solution_region(
    page: Mapping[str, Any] | None,
    heading: AlignedSolutionHeading,
) -> Mapping[str, Any] | None:
    if not isinstance(page, Mapping):
        return None
    regions = [
        region
        for region in (page.get("regions") or [])
        if isinstance(region, Mapping)
        and str(region.get("kind") or "") == "solution"
    ]
    exact = [
        region
        for region in regions
        if int(region.get("headingProviderIndex") or -1) == heading.provider_block_index
    ]
    if exact:
        return exact[0]
    same_number = [
        region
        for region in regions
        if _latin_digit(region.get("questionNumber")) == heading.question_number
    ]
    return same_number[0] if len(same_number) == 1 else None


def _aligned_solution_state(
    result: Any,
    *,
    first_expected: int,
    last_expected: int,
) -> tuple[list[AlignedSolutionHeading], list[int], list[int]]:
    candidates = []
    for page in result.pages:
        if not isinstance(page, Mapping):
            continue
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
    missing = [
        int(value)
        for value in (aligned.get("missingQuestionNumbers") or [])
        if int(value) > 0
    ]
    invalid = [
        item.question_number
        for item in accepted
        if not item.option_label_valid
    ]
    return accepted, sorted(set(missing)), sorted(set(invalid))


def _target_crop_specs(
    accepted: Sequence[AlignedSolutionHeading],
    targets: Sequence[int],
) -> list[tuple[int, str]]:
    specs: list[tuple[int, str]] = []
    ordered = sorted(accepted, key=lambda item: item.question_number)
    by_question = {item.question_number: item for item in ordered}
    for target in sorted({int(value) for value in targets if int(value) > 0}):
        anchor = by_question.get(target)
        if anchor is None:
            anchor = next((item for item in ordered if item.question_number > target), None)
        if anchor is None:
            anchor = next(
                (item for item in reversed(ordered) if item.question_number < target),
                None,
            )
        if anchor is None or anchor.column not in {"left", "right"}:
            continue
        spec = (anchor.physical_page_number, anchor.column)
        if spec not in specs:
            specs.append(spec)
    return specs[:12]


def _render_target_crop_pdf(
    pdf_path: Path,
    specs: Sequence[tuple[int, str]],
    *,
    dpi: int = 250,
) -> bytes:
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(str(pdf_path))
    images: list[Image.Image] = []
    try:
        scale = float(dpi) / 72.0
        for page_number, side in specs:
            if not (1 <= page_number <= len(document)):
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


def _collect_target_headings(
    result: Any,
    specs: Sequence[tuple[int, str]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    pages = sorted(result.pages, key=lambda page: int(page.get("index") or 0))
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


def _resolve_targets(
    headings: Sequence[Mapping[str, Any]],
    targets: Sequence[int],
) -> dict[int, tuple[str, int, str]]:
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


def _column_bbox(side: str) -> dict[str, float]:
    if side == "left":
        return {"x0": 0.02, "y0": 0.075, "x1": 0.51, "y1": 0.965}
    return {"x0": 0.49, "y0": 0.075, "x1": 0.98, "y1": 0.965}


def _ocr_config() -> SourceFirstOCRConfig:
    selected = SourceFirstOCRConfig.from_env()
    try:
        attempts = int(os.getenv("EXAM_PREP_MISTRAL_OCR_MAX_ATTEMPTS", "2"))
    except (TypeError, ValueError):
        attempts = 2
    return replace(
        selected,
        max_attempts=max(1, min(3, attempts)),
        word_confidence=False,
    )


def _targeted_recovery(
    pdf_path: Path,
    *,
    accepted: Sequence[AlignedSolutionHeading],
    missing: Sequence[int],
    invalid: Sequence[int],
    config: SourceFirstOCRConfig,
    should_cancel: CancelCheck | None,
) -> tuple[dict[int, tuple[str, int, str]], int]:
    targets = sorted(set(missing) | set(invalid))
    if not targets:
        return {}, 0
    specs = _target_crop_specs(accepted, targets)
    if not specs:
        return {}, 0
    _cancel(should_cancel)
    crop_pdf = _render_target_crop_pdf(pdf_path, specs)
    if not crop_pdf:
        return {}, 0
    with tempfile.NamedTemporaryFile(suffix=".pdf") as handle:
        handle.write(crop_pdf)
        handle.flush()
        try:
            targeted = fetch_document_ocr4(
                handle.name,
                config=replace(
                    config,
                    max_pages_per_request=max(1, min(30, len(specs))),
                ),
            )
        except SourceFirstProviderError:
            return {}, 0
    _cancel(should_cancel)
    return _resolve_targets(_collect_target_headings(targeted, specs), targets), len(targeted.chunks)


def _source_ref(
    *,
    question_number: int,
    role: str,
    region: Mapping[str, Any],
) -> dict[str, Any] | None:
    try:
        page = int(region.get("page_number") or 0)
    except (TypeError, ValueError):
        return None
    bbox = region.get("bbox")
    if page < 1 or not isinstance(bbox, Mapping):
        return None
    return {
        "id": f"inline-mistral-{question_number}-{role}",
        "role": role,
        "optionLabel": None,
        "altText": (
            "برش اصلی صورت سؤال و گزینه‌ها"
            if role == "question"
            else "برش اصلی پاسخ و راه‌حل"
        ),
        "selectedVariant": "source",
        "sourcePage": page,
        "sourceBBox": dict(bbox),
    }


def _has_source_corruption(value: Any) -> bool:
    text = str(value or "")
    return any(character in text for character in _SOURCE_CORRUPTION_CHARS)


def _question_side_broken(question: Mapping[str, Any]) -> bool:
    values = [
        question.get("question_text_markdown") or "",
        *[
            option.get("text_markdown") or ""
            for option in (question.get("options") or [])
            if isinstance(option, Mapping)
        ],
    ]
    return any(has_broken_persian_text(str(value)) for value in values)


def _apply_source_visual_policy(result: PageAssemblyResult) -> PageAssemblyResult:
    questions: list[dict[str, Any]] = []
    for raw in (result.projection.get("exam_prep") or {}).get("questions") or []:
        if not isinstance(raw, dict):
            continue
        question = dict(raw)
        number = _latin_digit(question.get("source_question_number")) or 0
        regions = [
            item
            for item in (question.get("source_regions") or [])
            if isinstance(item, Mapping)
        ]
        question_regions = [
            item for item in regions if str(item.get("role") or "") == "question"
        ]
        answer_regions = [
            item for item in regions if str(item.get("role") or "") == "answer"
        ]
        issues = [
            str(value)
            for value in (question.get("issues") or [])
            if str(value).strip()
        ]
        visuals = [
            dict(item)
            for item in (question.get("visuals") or [])
            if isinstance(item, Mapping)
        ]

        question_requires_crop = bool(
            "visual_evidence_required" in issues
            or "unexpected_option_count" in issues
            or "visual_options_source_crop_authoritative" in issues
            or any(str(code) in _VISUAL_ISSUES for code in issues)
        )
        if question_requires_crop and question_regions and number:
            ref = _source_ref(
                question_number=number,
                role="question",
                region=question_regions[0],
            )
            if ref is not None and not any(item.get("id") == ref["id"] for item in visuals):
                visuals.append(ref)

        solution_text = str(question.get("teacher_solution_markdown") or "")
        solution_requires_crop = bool(
            answer_regions
            and (
                _has_source_corruption(solution_text)
                or has_broken_persian_text(solution_text)
                or any(
                    code in issues
                    for code in (
                        "missing_solution_text",
                        "duplicate_solution_across_questions",
                        "solution_semantic_mismatch_candidate",
                        "targeted_solution_heading_recovered",
                    )
                )
            )
        )
        if solution_requires_crop and number:
            ref = _source_ref(
                question_number=number,
                role="solution",
                region=answer_regions[0],
            )
            if ref is not None and not any(item.get("id") == ref["id"] for item in visuals):
                visuals.append(ref)

        if visuals:
            question["visuals"] = visuals
        has_question_visual = any(item.get("role") == "question" for item in visuals)
        has_solution_visual = any(item.get("role") == "solution" for item in visuals)
        if has_question_visual:
            issues = [
                code
                for code in issues
                if code not in {"visual_evidence_required", "visual_attachment_missing"}
            ]
        if (
            has_solution_visual
            and not _question_side_broken(question)
            and "broken_persian_text" in issues
        ):
            issues = [code for code in issues if code != "broken_persian_text"]
            issues.append("solution_source_crop_authoritative")
        question["issues"] = list(dict.fromkeys(issues))
        questions.append(question)
    return _rebuild_result(result, questions=questions)


def _build_page_extractions(
    *,
    result: Any,
    analysis: Mapping[str, Any],
    recovered_targets: Mapping[int, tuple[str, int, str]],
) -> list[SourcePageExtraction]:
    records_by_page: dict[int, list[dict[str, Any]]] = {}
    page_map = _analysis_page_map(analysis)
    question_numbers: list[int] = []

    for page_number, page in sorted(page_map.items()):
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
    accepted, _missing, _invalid = _aligned_solution_state(
        result,
        first_expected=min(question_numbers),
        last_expected=max(question_numbers),
    )

    for heading in accepted:
        region = _solution_region(page_map.get(heading.physical_page_number), heading)
        if heading.question_number in recovered_targets:
            label = recovered_targets[heading.question_number][0]
        elif heading.option_label_valid and heading.option_label:
            label = str(heading.option_label)
        else:
            label = None
        source_bbox = (
            _safe_bbox(region.get("bbox"))
            if isinstance(region, Mapping)
            else _column_bbox(heading.column)
        )
        solution_text = str(region.get("text") or "") if isinstance(region, Mapping) else ""
        issues = [
            str(value)
            for value in ((region.get("issues") or []) if isinstance(region, Mapping) else [])
        ]
        if heading.question_number in recovered_targets:
            issues.append("targeted_solution_heading_recovered")
        records_by_page.setdefault(heading.physical_page_number, []).append(
            {
                "question_number": heading.question_number,
                "record_type": "solution",
                "correct_option_label": label,
                "teacher_solution_markdown": solution_text,
                "final_answer_markdown": f"گزینه {label}" if label else "",
                "confidence": 0.0,
                "issues": list(dict.fromkeys(issues)),
                "source_bbox": source_bbox,
            }
        )

    accepted_numbers = {item.question_number for item in accepted}
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


def run_exam_prep_mistral_document_pipeline(
    *,
    data: bytes,
    title: str,
    model: str | None = None,
    scope_hint: str = "default",
    on_page_complete: ProgressCallback | None = None,
    should_cancel: CancelCheck | None = None,
) -> ExamPrepPipelineResult:
    """Run the researched OCR4 document pipeline behind the simple product flow."""
    del model, scope_hint
    if not data or not data.lstrip().startswith(b"%PDF"):
        raise ExamPrepPdfError("فایل ارسالی یک PDF معتبر نیست.")

    _cancel(should_cancel)
    config = _ocr_config()
    with tempfile.NamedTemporaryFile(suffix=".pdf") as source_file:
        source_file.write(data)
        source_file.flush()
        pdf_path = Path(source_file.name)

        from pypdf import PdfReader

        page_count = len(PdfReader(io.BytesIO(data)).pages)
        completed_pages = 0

        def chunk_done(chunk_result: Any) -> None:
            nonlocal completed_pages
            completed_pages += len(chunk_result.chunk.physical_pages)
            if on_page_complete is not None:
                on_page_complete(min(completed_pages, page_count), page_count)
            _cancel(should_cancel)

        try:
            ocr_result = fetch_document_ocr4(
                pdf_path,
                config=config,
                chunk_callback=chunk_done,
            )
        except SourceFirstProviderError as exc:
            raise ExamPrepPdfError(
                f"OCR4 provider failed (status={exc.status_code or 'transport'})."
            ) from exc

        _cancel(should_cancel)
        analysis = analyze_source_result(ocr_result)
        question_numbers = sorted(
            {
                int(region.get("questionNumber"))
                for page in (analysis.get("pages") or [])
                if isinstance(page, Mapping)
                and str(page.get("pageRole") or "") == "question"
                for region in (page.get("regions") or [])
                if isinstance(region, Mapping)
                and str(region.get("kind") or "") == "question"
                and isinstance(region.get("questionNumber"), int)
            }
        )
        if not question_numbers:
            raise NoExamQuestionsFound("هیچ سؤال شماره‌داری در PDF تشخیص داده نشد.")

        accepted, missing, invalid = _aligned_solution_state(
            ocr_result,
            first_expected=min(question_numbers),
            last_expected=max(question_numbers),
        )
        recovered, targeted_calls = _targeted_recovery(
            pdf_path,
            accepted=accepted,
            missing=missing,
            invalid=invalid,
            config=config,
            should_cancel=should_cancel,
        )
        _cancel(should_cancel)
        page_extractions = _build_page_extractions(
            result=ocr_result,
            analysis=analysis,
            recovered_targets=recovered,
        )

    assembled = assemble_page_extractions(page_extractions, title=title)
    assembled = attach_source_regions(assembled, pages=page_extractions)
    assembled = rebuild_assembly_quality(assembled)
    assembled, integrity_stats = apply_projection_integrity(assembled)
    assembled = _apply_source_visual_policy(assembled)

    audit = build_strict_page_first_audit(assembled, failed_page_numbers=[])
    audit = promote_integrity_audit(audit, integrity_stats=integrity_stats)
    unresolved_targets = sorted((set(missing) | set(invalid)) - set(recovered))
    audit.update(
        {
            "engine": "mistral_ocr4_document",
            "ocrSourcePages": ocr_result.page_count,
            "ocrSourceChunks": len(ocr_result.chunks),
            "ocrSourceRetries": ocr_result.retry_count,
            "ocrResolvedModels": list(ocr_result.resolved_models),
            "targetedSolutionHeadingCalls": targeted_calls,
            "targetedSolutionHeadingRecovered": len(recovered),
            "targetedSolutionHeadingUnresolved": unresolved_targets,
            "totalProviderCalls": len(ocr_result.chunks) + targeted_calls,
            "estimatedOcrCostUnit": format(ocr_result.estimated_cost_unit, "f"),
        }
    )
    if unresolved_targets:
        issues = list(audit.get("issues") or [])
        existing = {
            (str(item.get("code") or ""), int(item.get("questionNumber") or 0))
            for item in issues
            if isinstance(item, Mapping)
        }
        for number in unresolved_targets:
            key = ("missing_correct_option_label", number)
            if key not in existing:
                issues.append(
                    {
                        "code": "missing_correct_option_label",
                        "severity": "critical",
                        "scopeKey": "default",
                        "questionNumber": number,
                        "sourcePages": [],
                    }
                )
        audit["issues"] = issues
        audit["criticalIssueCount"] = sum(
            item.get("severity") == "critical"
            for item in issues
            if isinstance(item, Mapping)
        )
        critical_questions = {
            int(item.get("questionNumber") or 0)
            for item in issues
            if isinstance(item, Mapping)
            and item.get("severity") == "critical"
            and int(item.get("questionNumber") or 0) > 0
        }
        audit["questionsNeedingReview"] = len(critical_questions)
        audit["usableQuestionCount"] = max(
            0,
            assembled.question_count - len(critical_questions),
        )
        audit["status"] = "needs_review"

    visuals_attached = sum(
        bool(question.get("visuals"))
        for question in (assembled.projection.get("exam_prep") or {}).get("questions") or []
        if isinstance(question, Mapping)
    )
    transcript = render_strict_page_first_transcript(
        assembled,
        failed_page_numbers=[],
        targeted_repair_stats={
            "attempted": targeted_calls,
            "verified": len(recovered),
            "repaired": len(recovered),
            "retried": ocr_result.retry_count,
            "unresolved": len(unresolved_targets),
            "visuals_attached": visuals_attached,
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
                for page in (analysis.get("pages") or [])
                if isinstance(page, Mapping)
            ),
        ),
        publication_ready=audit.get("status") == "passed",
        transcript_markdown=transcript,
        extraction_audit=audit,
        targeted_repair_stats={
            "attempted": targeted_calls,
            "repaired": len(recovered),
            "unresolved": len(unresolved_targets),
        },
        verification_stats={
            "attempted": 0,
            "verified": 0,
            "repaired": 0,
            "retried": 0,
            "unresolved": 0,
            "visuals_attached": visuals_attached,
            "tables_verified": 0,
            "skipped": 0,
            "cancelled_before_call": 0,
        },
        model=",".join(ocr_result.resolved_models) or config.model,
    )
