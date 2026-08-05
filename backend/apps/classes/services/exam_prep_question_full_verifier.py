"""Final source verification for every assembled exam question.

Each provider call receives exactly one question plus at most one question crop
and one answer/solution crop. A mismatch gets one bounded second pass. No whole
PDF or whole-exam prompt exists.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import io
import json
import logging
import os
from typing import Any, Iterable

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

from apps.chatbot.services.llm_client import part_from_bytes
from apps.commons.llm_prompts import PROMPTS
from apps.commons.models import LLMUsageLog
from apps.commons.structured_llm import StructuredOutputError, generate_structured

from .exam_prep_page_extractor import RenderedExamPage
from .exam_prep_page_output import is_critical_page_issue
from .exam_prep_page_records import AssemblyIssue, PageAssemblyResult, PageOption
from .exam_prep_page_source import SourceBBox
from .exam_prep_question_cleanup import cleanup_assembled_question
from .exam_prep_question_verifier import canonical_question_issues
from .exam_prep_text_quality import native_text_for_model
from .exam_prep_utils import clean_exam_markdown


logger = logging.getLogger("apps.classes.exam_prep")
_COUNT_WORDS = ("چند مورد", "چند عبارت", "چند گزینه", "تعداد موارد", "تعداد عبارت")
_STALE_AFTER_SOURCE_VERIFICATION = frozenset(
    {
        "broken_persian_text",
        "duplicate_mixed_text",
        "solution_semantic_mismatch_candidate",
        "targeted_repair_unresolved",
        "targeted_repair_failed",
        "targeted_repair_no_source_page",
        "missing_solution_text",
        "correct_option_not_in_options",
        "conflicting_correct_option",
        "conflicting_correct_option_text",
    }
)


class VerifiedQuestionAudit(BaseModel):
    model_config = ConfigDict(extra="ignore")

    question_number: int = Field(ge=1)
    source_supported: bool = False
    fields_match_source: bool = False
    question_text_markdown: str = ""
    options: list[PageOption] = Field(default_factory=list)
    correct_option_label: str | None = None
    teacher_solution_markdown: str = ""
    final_answer_markdown: str = ""
    visual_required: bool = False
    table_required: bool = False
    table_complete: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    issues: list[str] = Field(default_factory=list)


@dataclass(frozen=True, slots=True)
class SourceCrop:
    page_number: int
    role: str
    bbox: SourceBBox | None
    image: bytes
    mime_type: str
    native_text: str


@dataclass(frozen=True, slots=True)
class QuestionVerificationStats:
    attempted: int = 0
    verified: int = 0
    repaired: int = 0
    retried: int = 0
    unresolved: int = 0
    visuals_attached: int = 0
    tables_verified: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "attempted": self.attempted,
            "verified": self.verified,
            "repaired": self.repaired,
            "retried": self.retried,
            "unresolved": self.unresolved,
            "visuals_attached": self.visuals_attached,
            "tables_verified": self.tables_verified,
        }


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


def _question_number(question: dict[str, Any]) -> int:
    try:
        return int(question.get("source_question_number") or 0)
    except (TypeError, ValueError):
        return 0


def _bbox_from_region(region: dict[str, Any]) -> SourceBBox | None:
    raw = region.get("bbox")
    if not raw:
        return None
    try:
        return SourceBBox.model_validate(raw)
    except Exception:
        return None


def _union_bbox(values: Iterable[SourceBBox]) -> SourceBBox | None:
    boxes = list(values)
    if not boxes:
        return None
    return SourceBBox(
        x0=min(box.x0 for box in boxes),
        y0=min(box.y0 for box in boxes),
        x1=max(box.x1 for box in boxes),
        y1=max(box.y1 for box in boxes),
    )


def _region_candidates(question: dict[str, Any], role: str) -> list[tuple[int, SourceBBox | None, float]]:
    grouped: dict[int, list[tuple[SourceBBox | None, float]]] = {}
    for region in question.get("source_regions") or []:
        if not isinstance(region, dict) or str(region.get("role") or "") != role:
            continue
        try:
            page_number = int(region.get("page_number") or 0)
        except (TypeError, ValueError):
            continue
        if page_number < 1:
            continue
        grouped.setdefault(page_number, []).append(
            (
                _bbox_from_region(region),
                float(region.get("confidence") or 0.0),
            )
        )
    candidates: list[tuple[int, SourceBBox | None, float]] = []
    for page_number, values in grouped.items():
        bbox = _union_bbox(box for box, _confidence in values if box is not None)
        confidence = max((value[1] for value in values), default=0.0)
        candidates.append((page_number, bbox, confidence))
    return sorted(
        candidates,
        key=lambda item: (
            item[1] is not None,
            item[2],
            ((item[1].x1 - item[1].x0) * (item[1].y1 - item[1].y0)) if item[1] else 0.0,
        ),
        reverse=True,
    )


def _fallback_page(question: dict[str, Any], *, answer: bool) -> int | None:
    pages: list[int] = []
    for raw in question.get("source_pages") or []:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value > 0 and value not in pages:
            pages.append(value)
    if not pages:
        return None
    return pages[-1] if answer else pages[0]


def _crop_png(page: RenderedExamPage, bbox: SourceBBox | None) -> bytes:
    if bbox is None:
        return page.image
    padded = bbox.padded(_positive_float_env("EXAM_PREP_SOURCE_CROP_PADDING", 0.025))
    with Image.open(io.BytesIO(page.image)) as source:
        image = source.convert("RGB")
    try:
        width, height = image.size
        left = max(0, min(width - 1, int(padded.x0 * width)))
        top = max(0, min(height - 1, int(padded.y0 * height)))
        right = max(left + 1, min(width, int(padded.x1 * width)))
        bottom = max(top + 1, min(height, int(padded.y1 * height)))
        crop = image.crop((left, top, right, bottom))
        try:
            max_dimension = _positive_int_env("EXAM_PREP_VERIFY_CROP_MAX_DIMENSION", 1800)
            if max(crop.size) > max_dimension:
                scale = max_dimension / max(crop.size)
                resized = crop.resize(
                    (max(1, int(crop.width * scale)), max(1, int(crop.height * scale))),
                    Image.Resampling.LANCZOS,
                )
                crop.close()
                crop = resized
            output = io.BytesIO()
            crop.save(output, format="PNG", optimize=True)
            return output.getvalue()
        finally:
            crop.close()
    finally:
        image.close()


def _build_crop(
    question: dict[str, Any],
    *,
    role: str,
    pages: dict[int, RenderedExamPage],
) -> SourceCrop | None:
    candidates = _region_candidates(question, role)
    if candidates:
        page_number, bbox, _confidence = candidates[0]
    else:
        page_number = _fallback_page(question, answer=role == "answer")
        bbox = None
    if page_number is None or page_number not in pages:
        return None
    page = pages[page_number]
    return SourceCrop(
        page_number=page_number,
        role=role,
        bbox=bbox,
        image=_crop_png(page, bbox),
        mime_type="image/png",
        native_text=native_text_for_model(page.native_text, max_chars=8_000),
    )


def build_question_source_crops(
    question: dict[str, Any],
    *,
    pages: dict[int, RenderedExamPage],
) -> list[SourceCrop]:
    crops: list[SourceCrop] = []
    question_crop = _build_crop(question, role="question", pages=pages)
    answer_crop = _build_crop(question, role="answer", pages=pages)
    if question_crop is not None:
        crops.append(question_crop)
    if answer_crop is not None:
        duplicate = any(
            item.page_number == answer_crop.page_number
            and item.bbox == answer_crop.bbox
            for item in crops
        )
        if not duplicate:
            crops.append(answer_crop)
    return crops[:2]


def _crop_parts(crops: list[SourceCrop]) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    for crop in crops[:2]:
        bbox_json = crop.bbox.model_dump() if crop.bbox else None
        parts.append(
            {
                "type": "text",
                "text": (
                    f"SOURCE_BLOCK_ROLE: {crop.role}\n"
                    f"SOURCE_PAGE_NUMBER: {crop.page_number}\n"
                    f"SOURCE_BBOX: {json.dumps(bbox_json, separators=(',', ':'))}\n"
                    "SOURCE_NATIVE_TEXT_BEGIN\n"
                    f"{crop.native_text}\n"
                    "SOURCE_NATIVE_TEXT_END"
                ),
            }
        )
        parts.append(part_from_bytes(data=crop.image, mime_type=crop.mime_type))
    return parts


def verify_question_once(
    question: dict[str, Any],
    *,
    crops: list[SourceCrop],
    model: str,
    attempt: int,
) -> VerifiedQuestionAudit:
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
                            f"VERIFICATION_ATTEMPT: {attempt}\n"
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
        max_repair=1,
        strict_json_schema=True,
        sensitive=True,
        max_output_tokens=_positive_int_env(
            "EXAM_PREP_QUESTION_AUDIT_MAX_OUTPUT_TOKENS",
            12_000,
        ),
        detail="exam_prep_question_source_audit",
        tracking_context={
            "stage": "question_source_audit",
            "question_number": number,
            "attempt": attempt,
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


def _looks_fake_visual_option(value: Any) -> bool:
    text = clean_exam_markdown(value).strip().casefold()
    return bool(text) and (
        text.startswith("graph ")
        or text.startswith("نمودار ") and text[-1:].isdigit()
        or text in {"تصویر 1", "تصویر 2", "تصویر 3", "تصویر 4"}
    )


def _apply_audit(question: dict[str, Any], audit: VerifiedQuestionAudit) -> dict[str, Any]:
    updated = dict(question)
    if audit.question_text_markdown:
        updated["question_text_markdown"] = clean_exam_markdown(audit.question_text_markdown)
    if audit.options:
        updated["options"] = [item.model_dump() for item in audit.options]
    if audit.correct_option_label:
        updated["correct_option_label"] = clean_exam_markdown(audit.correct_option_label)
    if audit.teacher_solution_markdown:
        updated["teacher_solution_markdown"] = clean_exam_markdown(audit.teacher_solution_markdown)
    if audit.final_answer_markdown:
        updated["final_answer_markdown"] = clean_exam_markdown(audit.final_answer_markdown)
    if audit.visual_required:
        options = [item for item in (updated.get("options") or []) if isinstance(item, dict)]
        updated["options"] = [
            {
                **item,
                "text_markdown": (
                    "" if _looks_fake_visual_option(item.get("text_markdown")) else item.get("text_markdown", "")
                ),
            }
            for item in options
        ]
    updated["confidence"] = max(
        float(updated.get("confidence") or 0.0),
        audit.confidence,
    )
    updated["verification_metadata"] = {
        **dict(updated.get("verification_metadata") or {}),
        "source_supported": audit.source_supported,
        "fields_match_source": audit.fields_match_source,
        "visual_required": audit.visual_required,
        "table_required": audit.table_required,
        "table_complete": audit.table_complete,
        "confidence": audit.confidence,
        "provider_issues": list(audit.issues),
    }
    cleaned, _changed = cleanup_assembled_question(updated)
    return cleaned


def _inline_visual(crop: SourceCrop, *, question_id: str) -> dict[str, Any]:
    maximum_bytes = _positive_int_env("EXAM_PREP_INLINE_VISUAL_MAX_BYTES", 450_000)
    with Image.open(io.BytesIO(crop.image)) as source:
        image = source.convert("RGB")
    try:
        encoded = b""
        for _ in range(6):
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=82, optimize=True)
            encoded = output.getvalue()
            if len(encoded) <= maximum_bytes or min(image.size) <= 300:
                break
            resized = image.resize(
                (max(300, int(image.width * 0.78)), max(300, int(image.height * 0.78))),
                Image.Resampling.LANCZOS,
            )
            image.close()
            image = resized
    finally:
        image.close()
    data_url = "data:image/jpeg;base64," + base64.b64encode(encoded).decode("ascii")
    return {
        "id": f"inline-{question_id}",
        "role": "question",
        "optionLabel": None,
        "altText": "تصویر اصلی مرتبط با سؤال",
        "selectedVariant": "source",
        "dataUrl": data_url,
        "sourcePage": crop.page_number,
        "sourceBBox": crop.bbox.model_dump() if crop.bbox else None,
    }


def _is_count_question(question: dict[str, Any]) -> bool:
    text = clean_exam_markdown(question.get("question_text_markdown") or "")
    return any(value in text for value in _COUNT_WORDS)


def _count_answer_resolved(question: dict[str, Any]) -> bool:
    if not _is_count_question(question):
        return True
    labels = [
        clean_exam_markdown(item.get("label") or "")
        for item in (question.get("options") or [])
        if isinstance(item, dict)
    ]
    correct = clean_exam_markdown(question.get("correct_option_label") or "")
    return len(labels) >= 2 and all(label.isdigit() for label in labels) and correct in labels


def _final_question_issues(
    question: dict[str, Any],
    *,
    verified: bool,
) -> list[str]:
    metadata = dict(question.get("verification_metadata") or {})
    visual_required = bool(metadata.get("visual_required"))
    visuals = [item for item in (question.get("visuals") or []) if isinstance(item, dict)]
    issues = []
    for code in canonical_question_issues(question):
        if verified and (
            code in _STALE_AFTER_SOURCE_VERIFICATION
            or code.startswith("conflicting_option:")
        ):
            continue
        if visual_required and visuals and code in {"visual_evidence_required", "missing_option_text"}:
            continue
        if code not in issues:
            issues.append(code)
    if not verified:
        issues.append("source_verification_failed")
    if bool(metadata.get("table_required")) and not bool(metadata.get("table_complete")):
        issues.append("table_incomplete")
    if not _count_answer_resolved(question):
        issues.append("count_answer_unresolved")
    if visual_required and not visuals:
        issues.append("visual_attachment_missing")
    return list(dict.fromkeys(issues))


def _rebuild_result(
    result: PageAssemblyResult,
    *,
    questions: list[dict[str, Any]],
) -> PageAssemblyResult:
    projection = dict(result.projection)
    exam = dict(projection.get("exam_prep") or {})
    exam["questions"] = questions
    projection["exam_prep"] = exam
    issues: list[AssemblyIssue] = []
    matched_answers = 0
    for question in questions:
        number = _question_number(question)
        scope = str(question.get("scope_key") or "default")
        pages = [
            int(value)
            for value in (question.get("source_pages") or [])
            if str(value).isdigit()
        ]
        for code in question.get("issues") or []:
            issues.append(
                AssemblyIssue(
                    code=str(code),
                    scope_key=scope,
                    question_number=number,
                    source_pages=pages,
                )
            )
        if any(
            clean_exam_markdown(question.get(field) or "")
            for field in (
                "correct_option_label",
                "correct_option_text_markdown",
                "teacher_solution_markdown",
                "final_answer_markdown",
            )
        ):
            matched_answers += 1
    for scope, numbers in result.question_number_gaps.items():
        for number in numbers:
            issues.append(
                AssemblyIssue(
                    code="missing_question_number",
                    scope_key=scope,
                    question_number=number,
                    source_pages=[],
                )
            )
    publication_ready = bool(questions) and not any(
        is_critical_page_issue(issue.code) for issue in issues
    )
    return result.model_copy(
        update={
            "projection": projection,
            "issues": issues,
            "question_count": len(questions),
            "questions_needing_review": sum(bool(item.get("issues")) for item in questions),
            "matched_answer_count": matched_answers,
            "publication_ready": publication_ready,
        }
    )


def verify_all_questions(
    result: PageAssemblyResult,
    *,
    source_pages_by_number: dict[int, RenderedExamPage],
    model: str,
) -> tuple[PageAssemblyResult, dict[str, int]]:
    """Audit every question, retrying only mismatches once."""

    questions = [
        item
        for item in (result.projection.get("exam_prep") or {}).get("questions") or []
        if isinstance(item, dict)
    ]
    maximum = _positive_int_env("EXAM_PREP_MAX_QUESTION_VERIFICATIONS", 200)
    max_attempts = max(1, min(2, _positive_int_env("EXAM_PREP_QUESTION_VERIFICATION_ATTEMPTS", 2)))
    threshold = _positive_float_env("EXAM_PREP_QUESTION_VERIFICATION_CONFIDENCE", 0.78)
    attempted = verified_count = repaired = retried = unresolved = visuals_attached = tables_verified = 0
    output: list[dict[str, Any]] = []

    for index, raw_question in enumerate(questions):
        question, deterministic_changed = cleanup_assembled_question(raw_question)
        if index >= maximum:
            question["issues"] = list(
                dict.fromkeys([*canonical_question_issues(question), "source_verification_failed"])
            )
            output.append(question)
            unresolved += 1
            continue
        attempted += 1
        crops = build_question_source_crops(question, pages=source_pages_by_number)
        if not crops:
            question["verification_metadata"] = {
                "source_supported": False,
                "fields_match_source": False,
                "attempts": 0,
                "source_pages": [],
            }
            question["issues"] = _final_question_issues(question, verified=False)
            output.append(question)
            unresolved += 1
            continue

        first_snapshot = json.dumps(question, ensure_ascii=False, sort_keys=True)
        final_audit: VerifiedQuestionAudit | None = None
        final_verified = False
        attempts_used = 0
        for attempt in range(1, max_attempts + 1):
            attempts_used = attempt
            try:
                audit = verify_question_once(
                    question,
                    crops=crops,
                    model=model,
                    attempt=attempt,
                )
            except Exception as exc:
                logger.warning(
                    "exam_prep.question.audit_failed questionNumber=%s attempt=%s errorCode=%s",
                    _question_number(question),
                    attempt,
                    type(exc).__name__,
                )
                audit = None
            if audit is None:
                if attempt < max_attempts:
                    retried += 1
                    continue
                break
            final_audit = audit
            question = _apply_audit(question, audit)
            final_verified = bool(
                audit.source_supported
                and audit.fields_match_source
                and audit.confidence >= threshold
            )
            if final_verified:
                break
            if attempt < max_attempts:
                retried += 1

        metadata = dict(question.get("verification_metadata") or {})
        metadata.update(
            {
                "attempts": attempts_used,
                "source_pages": [crop.page_number for crop in crops],
                "source_bboxes": [
                    crop.bbox.model_dump() if crop.bbox else None for crop in crops
                ],
            }
        )
        question["verification_metadata"] = metadata
        if final_audit is not None and final_audit.visual_required:
            question_crop = next((crop for crop in crops if crop.role == "question"), None)
            if question_crop is not None and question_crop.bbox is not None:
                question["visuals"] = [
                    _inline_visual(
                        question_crop,
                        question_id=str(question.get("question_id") or _question_number(question)),
                    )
                ]
                visuals_attached += 1
        if final_audit is not None and final_audit.table_required and final_audit.table_complete:
            tables_verified += 1
        question["source_verified"] = final_verified
        question["issues"] = _final_question_issues(question, verified=final_verified)
        final_snapshot = json.dumps(question, ensure_ascii=False, sort_keys=True)
        changed = deterministic_changed or first_snapshot != final_snapshot
        if final_verified:
            verified_count += 1
            if changed:
                repaired += 1
        else:
            unresolved += 1
        output.append(question)

    rebuilt = _rebuild_result(result, questions=output)
    stats = QuestionVerificationStats(
        attempted=attempted,
        verified=verified_count,
        repaired=repaired,
        retried=retried,
        unresolved=unresolved,
        visuals_attached=visuals_attached,
        tables_verified=tables_verified,
    )
    return rebuilt, stats.as_dict()
