"""Interactive OCR for student exercise answers.

This module transcribes and conservatively matches answers. It never receives
reference answers, grading notes, scores, or correctness feedback.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import mimetypes
import os
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from itertools import islice

from django.db import transaction
from django.utils import timezone

from apps.commons.llm_prompts import PROMPTS
from apps.commons.models import LLMUsageLog
from apps.commons.structured_llm import generate_structured
from .file_validation import is_real_image, is_probably_pdf
from .schemas import (
    AnswerPageTranscriptionOutput,
    ExerciseAnswerBundleOutput,
    HandwritingTranscriptionOutput,
)

_ALGORITHM_VERSION = "student-answer-ocr-v1"
_TIMEOUT_SECONDS = int(os.getenv("EXERCISE_ANSWER_OCR_TIMEOUT_SECONDS", "180"))


class StaleAnswerSource(RuntimeError):
    pass


class AnswerSourcePending(RuntimeError):
    pass


class AnswerSourceFailed(RuntimeError):
    pass


def preview_enabled() -> bool:
    return (os.getenv("EXERCISE_ANSWER_OCR_PREVIEW_ENABLED", "0") or "0").lower() in {
        "1", "true", "yes", "on",
    }


def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def max_pages() -> int:
    return _env_int("EXERCISE_ANSWER_OCR_MAX_PAGES", 20)


def max_bytes() -> int:
    return _env_int("EXERCISE_ANSWER_OCR_MAX_BYTES", 30 * 1024 * 1024)


def pages_per_call() -> int:
    return _env_int("EXERCISE_ANSWER_OCR_PAGES_PER_CALL", 4)


def settle_seconds() -> int:
    return _env_int("EXERCISE_ANSWER_OCR_SETTLE_SECONDS", 2)


def image_max_bytes() -> int:
    return _env_int("EXERCISE_ANSWER_OCR_IMAGE_MAX_BYTES", 3 * 1024 * 1024)


def image_max_dimension() -> int:
    return _env_int("EXERCISE_ANSWER_OCR_IMAGE_MAX_DIMENSION", 2400)


def image_max_pixels() -> int:
    return _env_int("EXERCISE_ANSWER_OCR_IMAGE_MAX_PIXELS", 30_000_000)


def _model(*names: str) -> str:
    for name in (*names, "MODEL_NAME"):
        value = (os.getenv(name) or "").strip()
        if value:
            return value
    raise RuntimeError(f"No LLM model defined in ENV. Checked: {names} and MODEL_NAME.")


def _sha256_json(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"


def _prompt_version(key: str) -> str:
    return _sha256_json(str(PROMPTS[key]["default"]))


def _workflow(stage: str, progress: int, message: str) -> dict:
    return {"stage": stage, "progressPercent": progress, "message": message}


def _assert_revision(source_id: int, revision: int):
    from ..models import StudentExerciseAnswerSource

    source = StudentExerciseAnswerSource.objects.select_related(
        "submission__exercise", "target_question",
    ).filter(id=source_id, revision=revision).first()
    if source is None or source.status == StudentExerciseAnswerSource.Status.SUPERSEDED:
        raise StaleAnswerSource()
    return source


def _set_state(source_id: int, revision: int, status: str, stage: str,
               progress: int, message: str) -> None:
    from ..models import StudentExerciseAnswerSource

    updated = StudentExerciseAnswerSource.objects.filter(
        id=source_id, revision=revision,
    ).exclude(status=StudentExerciseAnswerSource.Status.SUPERSEDED).update(
        status=status,
        workflow_state=_workflow(stage, progress, message),
        error_code="",
        updated_at=timezone.now(),
    )
    if not updated:
        raise StaleAnswerSource()


def serialize_source(source, *, include_raw: bool = False) -> dict:
    result = source.reviewed_result or source.raw_result or {}
    assets = []
    prefetched = getattr(source, "_prefetched_objects_cache", {}).get("assets")
    active_assets = (
        sorted((asset for asset in prefetched if asset.is_active), key=lambda asset: (asset.order, asset.id))
        if prefetched is not None
        else source.assets.filter(is_active=True).order_by("order", "id")
    )
    for asset in active_assets:
        assets.append({
            "id": asset.id,
            "order": asset.order,
            "contentType": asset.content_type,
            "byteSize": asset.byte_size,
            "url": f"/api/classes/exercise-answer-assets/{asset.id}/content/",
        })
    payload = {
        "id": source.id,
        "scope": source.scope,
        "questionId": source.target_question_id,
        "status": source.status,
        "revision": source.revision,
        "workflowStage": (source.workflow_state or {}).get("stage", source.status),
        "workflowMessage": (source.workflow_state or {}).get("message", ""),
        "progressPercent": int((source.workflow_state or {}).get("progressPercent", 0) or 0),
        "answers": result.get("answers", []),
        "unmatchedFragments": result.get("unmatched_fragments", []),
        "missingQuestionIds": result.get("missing_question_ids", []),
        "appliedAt": source.applied_at.isoformat() if source.applied_at else None,
        "assets": assets,
    }
    if include_raw:
        payload["rawAnswers"] = (source.raw_result or {}).get("answers", [])
    return payload


def serialize_source_status(source) -> dict:
    """Return only workflow fields needed by the polling endpoint."""
    return {
        "id": source.id,
        "scope": source.scope,
        "questionId": source.target_question_id,
        "status": source.status,
        "revision": source.revision,
        "workflowStage": (source.workflow_state or {}).get("stage", source.status),
        "workflowMessage": (source.workflow_state or {}).get("message", ""),
        "progressPercent": int(
            (source.workflow_state or {}).get("progressPercent", 0) or 0
        ),
    }


@dataclass(frozen=True)
class Page:
    number: int
    name: str
    data: bytes


def _normalize_pil_page(source, number: int) -> Page:
    """Bound decoded pixels and encoded bytes for one vision page."""
    from PIL import Image, ImageOps

    if source.width * source.height > image_max_pixels():
        raise ValueError("image_pixel_limit_exceeded")
    transposed = ImageOps.exif_transpose(source)
    try:
        image = transposed.convert("RGB")
    finally:
        if transposed is not source:
            transposed.close()
    try:
        max_dimension = image_max_dimension()
        image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
        for scale in (1.0, 0.8, 0.65):
            candidate = image if scale == 1.0 else image.resize(
                (max(1, int(image.width * scale)), max(1, int(image.height * scale))),
                Image.Resampling.LANCZOS,
            )
            try:
                for quality in (90, 82, 74):
                    output = io.BytesIO()
                    candidate.save(output, format="JPEG", quality=quality, optimize=True)
                    encoded = output.getvalue()
                    if len(encoded) <= image_max_bytes():
                        return Page(number, f"page-{number}.jpg", encoded)
            finally:
                if candidate is not image:
                    candidate.close()
        raise ValueError("image_too_large_after_normalization")
    finally:
        image.close()


def _normalize_image_page(data: bytes, number: int) -> Page:
    from PIL import Image

    with Image.open(io.BytesIO(data)) as source:
        return _normalize_pil_page(source, number)


def _read_asset(asset) -> bytes:
    from core.storage_backends import open_answer_source_file

    with open_answer_source_file(asset.file) as fh:
        return fh.read()


def _iter_pdf_pages(data: bytes, start_number: int) -> Iterator[Page]:
    import math
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(data)
    try:
        if len(pdf) > max_pages():
            raise ValueError("too_many_pages")
        for index in range(len(pdf)):
            page = pdf[index]
            try:
                width, height = page.get_size()
                if width <= 0 or height <= 0:
                    raise ValueError("invalid_pdf_page_size")
                scale = min(
                    150 / 72,
                    image_max_dimension() / width,
                    image_max_dimension() / height,
                    math.sqrt(image_max_pixels() / (width * height)),
                )
                bitmap = page.render(scale=scale)
                try:
                    image = bitmap.to_pil()
                    try:
                        normalized = _normalize_pil_page(image, start_number + index)
                    finally:
                        image.close()
                finally:
                    bitmap.close()
            finally:
                page.close()
            yield normalized
    finally:
        pdf.close()


def _render_pdf(data: bytes, start_number: int) -> list[Page]:
    """Compatibility wrapper for focused rendering tests."""
    return list(_iter_pdf_pages(data, start_number))


def _iter_pages(assets) -> Iterator[Page]:
    page_count = 0
    total_bytes = 0
    for asset in assets:
        data = _read_asset(asset)
        total_bytes += len(data)
        if total_bytes > max_bytes():
            raise ValueError("too_many_bytes")
        if is_probably_pdf(data):
            asset_pages = _iter_pdf_pages(data, page_count + 1)
        elif is_real_image(data):
            asset_pages = iter([_normalize_image_page(data, page_count + 1)])
        else:
            raise ValueError("invalid_asset")
        for page in asset_pages:
            page_count += 1
            if page_count > max_pages():
                raise ValueError("too_many_pages")
            yield page
    if page_count == 0:
        raise ValueError("no_pages")


def _load_pages(assets) -> list[Page]:
    return list(_iter_pages(assets))


def _data_url(page: Page) -> str:
    mime = mimetypes.guess_type(page.name)[0] or "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(page.data).decode('ascii')}"


def _vision_call(pages: list[Page], *, prompt: str, schema):
    content = [{"type": "text", "text": prompt}]
    content.extend({"type": "image_url", "image_url": {"url": _data_url(page)}} for page in pages)
    return generate_structured(
        schema=schema,
        messages=[{"role": "user", "content": content}],
        feature=LLMUsageLog.Feature.EXERCISE_HANDWRITING_VISION,
        model=_model("EXERCISE_ANSWER_OCR_MODEL", "EXERCISE_VISION_MODEL", "IMAGE_MODEL"),
        timeout=_TIMEOUT_SECONDS,
        temperature=0,
        sensitive=True,
    )


def _question_result(source, pages: list[Page]) -> dict:
    prompt = str(PROMPTS["exercise_handwriting_vision"]["default"]).replace(
        "{question_text}", str(source.target_question.question_markdown or ""),
    )
    output = _vision_call(pages, prompt=prompt, schema=HandwritingTranscriptionOutput)
    return {
        "answers": [{
            "question_id": source.target_question_id,
            "text": (output.text or "").strip(),
            "match_status": "matched" if output.quality == "clear" else "needs_review",
            "quality": output.quality,
            "unclear_parts": [item.model_dump() for item in output.unclear_parts],
        }],
        "unmatched_fragments": [],
        "missing_question_ids": [],
    }


def _bundle_result(
    source,
    pages: Iterable[Page],
    revision: int,
    fingerprint: str,
    question_contract: list[tuple[int, str]] | None = None,
) -> dict:
    transcripts = []
    cache = (source.processor_metadata or {}).get("transcriptionCache") or {}
    cached_chunks = cache.get("chunks", {}) if cache.get("fingerprint") == fingerprint else {}
    page_iterator = iter(pages)
    transcription_started = False
    while True:
        _assert_revision(source.id, revision)
        chunk = list(islice(page_iterator, pages_per_call()))
        if not chunk:
            break
        if not transcription_started:
            _set_state(
                source.id, revision, source.Status.SEGMENTING, "segmenting", 35,
                "در حال تشخیص متن و فرمول‌ها",
            )
            transcription_started = True
        chunk_key = ",".join(str(page.number) for page in chunk)
        cached = cached_chunks.get(chunk_key)
        if isinstance(cached, dict):
            transcripts.append(cached)
            continue
        prompt = str(PROMPTS["exercise_answer_bundle_vision"]["default"]).replace(
            "{page_numbers}", ", ".join(str(page.number) for page in chunk),
        )
        output = _vision_call(chunk, prompt=prompt, schema=AnswerPageTranscriptionOutput)
        transcript = {
            "pages": [page.number for page in chunk],
            "text": output.text,
            "quality": output.quality,
            "unclear_parts": [item.model_dump() for item in output.unclear_parts],
        }
        transcripts.append(transcript)
        cached_chunks[chunk_key] = transcript
        updated = source.__class__.objects.filter(id=source.id, revision=revision).update(
            processor_metadata={
                **(source.processor_metadata or {}),
                "transcriptionCache": {"fingerprint": fingerprint, "chunks": cached_chunks},
            },
            updated_at=timezone.now(),
        )
        if not updated:
            raise StaleAnswerSource()

    _set_state(source.id, revision, source.Status.MATCHING, "matching", 75,
               "در حال تطبیق پاسخ‌ها با سوال‌ها")
    question_rows = question_contract or list(
        source.submission.exercise.sections.values_list(
            "questions__id", "questions__question_markdown",
        ).order_by("order", "questions__order", "questions__id")
    )
    catalog = [{"question_id": qid, "question_text": text or ""} for qid, text in question_rows if qid]
    prompt = str(PROMPTS["exercise_answer_bundle_mapping"]["default"])
    prompt = prompt.replace("{questions_json}", json.dumps(catalog, ensure_ascii=False))
    prompt = prompt.replace("{transcript_json}", json.dumps(transcripts, ensure_ascii=False))
    mapped = generate_structured(
        schema=ExerciseAnswerBundleOutput,
        contents=prompt,
        feature=LLMUsageLog.Feature.EXERCISE_HANDWRITING_VISION,
        model=_model("EXERCISE_ANSWER_MAPPING_MODEL", "EXERCISE_ANSWER_OCR_MODEL", "EXERCISE_VISION_MODEL", "IMAGE_MODEL"),
        timeout=_TIMEOUT_SECONDS,
        temperature=0,
        sensitive=True,
    ).model_dump()
    valid_ids = {item["question_id"] for item in catalog}
    seen = set()
    normalized = []
    for answer in mapped.get("answers", []):
        qid = answer.get("question_id")
        if qid not in valid_ids or qid in seen:
            answer["question_id"] = None
            answer["match_status"] = "unmatched" if qid not in valid_ids else "needs_review"
        elif qid is not None:
            seen.add(qid)
        normalized.append(answer)
    mapped["answers"] = normalized
    mapped["missing_question_ids"] = sorted(valid_ids - seen)
    mapped["page_transcripts"] = transcripts
    return mapped


def _has_review_flags(result: dict) -> bool:
    if result.get("unmatched_fragments") or result.get("missing_question_ids"):
        return True
    return any(
        item.get("match_status") != "matched" or item.get("unclear_parts")
        for item in result.get("answers", []) if isinstance(item, dict)
    )


def _projection(answer: dict, source, answer_index: int | None = None) -> dict:
    raw_answers = source.raw_result.get("answers", []) if isinstance(source.raw_result, dict) else []
    raw_fragments = (
        source.raw_result.get("unmatched_fragments", [])
        if isinstance(source.raw_result, dict) else []
    )
    raw = next(
        (row for row in raw_answers if row.get("question_id") == answer.get("question_id")),
        {},
    )
    if answer_index is not None:
        if answer_index < len(raw_answers):
            raw = raw_answers[answer_index]
        elif answer_index - len(raw_answers) < len(raw_fragments):
            raw = {"text": str(raw_fragments[answer_index - len(raw_answers)])}
    return {
        "sourceId": source.id,
        "revision": source.revision,
        "rawText": str(raw.get("text") or ""),
        "text": str(answer.get("text") or ""),
        "quality": answer.get("quality") or (
            "clear" if answer.get("match_status") == "matched" else "review_recommended"
        ),
        "unclearParts": answer.get("unclear_parts") or [],
        "sourceFingerprint": source.source_fingerprint,
        "correctedByStudent": str(raw.get("text") or "") != str(answer.get("text") or ""),
    }


def apply_source(source, *, use_raw: bool = False) -> None:
    """Project OCR into draft answers without overwriting the typed channel."""
    from ..models import StudentExerciseSubmission

    with transaction.atomic():
        submission = StudentExerciseSubmission.objects.select_for_update().get(id=source.submission_id)
        if submission.status != StudentExerciseSubmission.Status.DRAFT:
            raise ValueError("submission_locked")
        locked_source = source.__class__.objects.select_for_update().filter(
            id=source.id,
            submission_id=submission.id,
            revision=source.revision,
            status__in=[source.Status.READY, source.Status.NEEDS_REVIEW],
        ).first()
        if locked_source is None:
            raise StaleAnswerSource()
        result = (
            locked_source.raw_result
            if use_raw else (locked_source.reviewed_result or locked_source.raw_result)
        )
        if locked_source.scope == locked_source.Scope.EXERCISE and (
            (result or {}).get("unmatched_fragments")
            or any(
                not item.get("question_id")
                for item in (result or {}).get("answers", [])
                if isinstance(item, dict)
            )
        ):
            raise ValueError("unresolved_answers")
        answers = dict(submission.answers or {})
        for answer_index, answer in enumerate(
            result.get("answers", []) if isinstance(result, dict) else [],
        ):
            qid = answer.get("question_id")
            if not qid:
                continue
            entry = dict(answers.get(str(qid)) or {})
            entry["ocr"] = _projection(answer, locked_source, answer_index)
            answers[str(qid)] = entry
        submission.answers = answers
        submission.save(update_fields=["answers", "updated_at"])
        locked_source.applied_at = timezone.now()
        locked_source.save(update_fields=["applied_at", "updated_at"])


def process_source(source_id: int, revision: int) -> dict:
    source = _assert_revision(source_id, revision)
    assets = list(source.assets.filter(is_active=True).order_by("order", "id"))
    identity = [{
        "order": asset.order,
        "sha256": asset.sha256,
        "byte_size": asset.byte_size,
        "content_type": asset.content_type,
    } for asset in assets]
    prompt_keys = ["exercise_handwriting_vision"] if source.scope == source.Scope.QUESTION else [
        "exercise_answer_bundle_vision", "exercise_answer_bundle_mapping",
    ]
    vision_model = _model(
        "EXERCISE_ANSWER_OCR_MODEL", "EXERCISE_VISION_MODEL", "IMAGE_MODEL",
    )
    mapping_model = (
        _model(
            "EXERCISE_ANSWER_MAPPING_MODEL", "EXERCISE_ANSWER_OCR_MODEL",
            "EXERCISE_VISION_MODEL", "IMAGE_MODEL",
        )
        if source.scope == source.Scope.EXERCISE else None
    )
    prompt_versions = {key: _prompt_version(key) for key in prompt_keys}
    question_contract = list(
        source.submission.exercise.sections.values_list(
            "questions__id", "questions__question_markdown",
        ).order_by("order", "questions__order", "questions__id")
    )
    fingerprint = _sha256_json({
        "algorithm": _ALGORITHM_VERSION,
        "assets": identity,
        "scope": source.scope,
        "targetQuestionId": source.target_question_id,
        "exerciseId": source.submission.exercise_id,
        "questionContract": question_contract,
        "models": {"vision": vision_model, "mapping": mapping_model},
        "prompts": prompt_versions,
    })
    if source.source_fingerprint == fingerprint and source.raw_result:
        result = source.reviewed_result or source.raw_result
        needs_review = _has_review_flags(result)
        final_status = source.Status.NEEDS_REVIEW if needs_review else source.Status.READY
        updated = source.__class__.objects.filter(id=source_id, revision=revision).update(
            status=final_status,
            workflow_state=_workflow(
                "needs_review" if needs_review else "ready", 100,
                "خوانش آماده بررسی است" if needs_review else "خوانش پاسخ آماده است",
            ),
            updated_at=timezone.now(),
        )
        if not updated:
            raise StaleAnswerSource()
        return {"status": final_status, "source_id": source.id, "reused": True}

    _set_state(source_id, revision, source.Status.READING, "reading", 15, "در حال خواندن فایل‌ها")
    source = _assert_revision(source_id, revision)
    if source.scope == source.Scope.QUESTION:
        pages = _load_pages(assets)
        _set_state(source_id, revision, source.Status.SEGMENTING, "segmenting", 35,
                   "در حال تشخیص متن و فرمول‌ها")
        result = _question_result(source, pages)
        page_count = len(pages)
    else:
        result = _bundle_result(
            source, _iter_pages(assets), revision, fingerprint, question_contract,
        )
        page_count = sum(
            len(item.get("pages") or [])
            for item in result.get("page_transcripts", [])
            if isinstance(item, dict)
        )
    _assert_revision(source_id, revision)
    needs_review = _has_review_flags(result)
    final_status = source.Status.NEEDS_REVIEW if needs_review else source.Status.READY
    updated = source.__class__.objects.filter(id=source_id, revision=revision).update(
        status=final_status,
        workflow_state=_workflow(
            "needs_review" if needs_review else "ready", 100,
            "خوانش آماده بررسی است" if needs_review else "خوانش پاسخ آماده است",
        ),
        source_fingerprint=fingerprint,
        raw_result=result,
        reviewed_result=result,
        processor_metadata={
            **(source.processor_metadata or {}),
            "algorithmVersion": _ALGORITHM_VERSION,
            "model": vision_model,
            "mappingModel": mapping_model,
            "promptVersions": prompt_versions,
            "pageCount": page_count,
        },
        error_code="",
        updated_at=timezone.now(),
    )
    if not updated:
        raise StaleAnswerSource()
    source = _assert_revision(source_id, revision)
    if (
        source.scope == source.Scope.QUESTION
        and source.submission.status == source.submission.Status.DRAFT
    ):
        try:
            apply_source(source)
        except ValueError as exc:
            # Submit may commit after OCR becomes READY but before this optional
            # draft projection. The frozen source remains valid for grading.
            if str(exc) != "submission_locked":
                raise
    return {"status": final_status, "source_id": source.id, "reused": False}


def mark_failed(source_id: int, revision: int, code: str = "processing_failed") -> None:
    from ..models import StudentExerciseAnswerSource

    StudentExerciseAnswerSource.objects.filter(id=source_id, revision=revision).update(
        status=StudentExerciseAnswerSource.Status.FAILED,
        workflow_state=_workflow("failed", 100, "خواندن پاسخ کامل نشد؛ تصویر اصلی محفوظ است"),
        error_code=code,
        updated_at=timezone.now(),
    )


def freeze_sources(submission, *, include_unapplied: bool) -> list[dict]:
    from ..models import StudentExerciseAnswerSource

    refs = []
    sources = submission.answer_sources.exclude(
        status=StudentExerciseAnswerSource.Status.SUPERSEDED,
    ).prefetch_related("assets")
    for source in sources.order_by("id"):
        refs.append({
            "sourceId": source.id,
            "revision": source.revision,
            "scope": source.scope,
            "includeUnapplied": bool(include_unapplied and source.scope == source.Scope.EXERCISE),
            "assetIds": [
                asset.id for asset in source.assets.all() if asset.is_active
            ],
        })
    return refs


def prepare_attempt_ocr(attempt) -> str:
    """Materialize frozen source results into an attempt before grading."""
    from ..models import StudentExerciseAnswerSource

    metadata = dict(attempt.grader_metadata or {})
    refs = metadata.get("answerSources") if isinstance(metadata.get("answerSources"), list) else []
    answers = dict(attempt.answers or {})
    source_ids = {
        ref.get("sourceId") for ref in refs
        if isinstance(ref, dict) and isinstance(ref.get("sourceId"), int)
    }
    sources_by_id = StudentExerciseAnswerSource.objects.filter(
        id__in=source_ids,
        submission_id=attempt.submission_id,
    ).in_bulk()
    for ref in refs:
        source = sources_by_id.get(ref.get("sourceId"))
        if (
            source is None
            or source.revision != ref.get("revision")
            or source.status == StudentExerciseAnswerSource.Status.SUPERSEDED
        ):
            raise AnswerSourceFailed()
        if source.status in {
            StudentExerciseAnswerSource.Status.QUEUED,
            StudentExerciseAnswerSource.Status.READING,
            StudentExerciseAnswerSource.Status.SEGMENTING,
            StudentExerciseAnswerSource.Status.MATCHING,
        }:
            raise AnswerSourcePending()
        if source.status == StudentExerciseAnswerSource.Status.FAILED:
            raise AnswerSourceFailed()
        should_include = source.scope == source.Scope.QUESTION or source.applied_at or ref.get("includeUnapplied")
        if not should_include:
            continue
        result = source.reviewed_result or source.raw_result
        for answer_index, item in enumerate(
            result.get("answers", []) if isinstance(result, dict) else [],
        ):
            qid = item.get("question_id")
            if not qid:
                continue
            entry = dict(answers.get(str(qid)) or {})
            entry["ocr"] = _projection(item, source, answer_index)
            answers[str(qid)] = entry
    attempt.answers = answers
    attempt.save(update_fields=["answers", "updated_at"])
    return "ready"
