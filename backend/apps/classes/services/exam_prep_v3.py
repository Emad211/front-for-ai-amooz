"""Durable, quality-gated OCR primitives for exam-prep extraction V3."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import time
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
from itertools import islice
from statistics import median
from typing import Any, Callable, Iterator

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from apps.chatbot.services.llm_client import generate_text
from apps.commons.structured_llm import parse_structured
from apps.commons.llm_prompts import PROMPTS
from apps.commons.models import LLMUsageLog

from ..models import (
    ClassCreationSession,
    ExamPrepExtractionArtifact,
    ExamPrepExtractionUnit,
)
from .pdf_extraction import (
    PdfExtractionError,
    _encode_png,
    _grayscale_std,
    _select_vision_model,
)


PIPELINE_VERSION = 3
PROMPT_VERSION = "exam-ocr-v3"
QUALITY_CONTRACT_VERSION = "ocr-quality-v3.1"
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")
_DIGIT_TRANSLATION = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)


def _env_int(name: str, default: int, *, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def configured_extraction_version() -> int:
    """Resolve the version for a NEW session; existing artifacts stay frozen."""
    raw = (os.getenv("EXAM_PREP_EXTRACTION_VERSION") or "").strip()
    if raw:
        try:
            return max(1, min(3, int(raw)))
        except ValueError:
            return 1
    legacy_v2 = (os.getenv("EXAM_PREP_EXTRACTION_V2") or "").strip().lower()
    return 2 if legacy_v2 in {"1", "true", "yes", "on"} else 1


def teacher_review_required(artifact: ExamPrepExtractionArtifact | None) -> bool:
    if artifact is None or artifact.pipeline_version < 3:
        return False
    return (os.getenv("EXAM_PREP_REQUIRE_TEACHER_REVIEW", "true") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def source_retention_deadline(*, now=None):
    """Return the cleanup deadline for a published or cancelled V3 source."""
    from datetime import timedelta

    base = now or timezone.now()
    days = _env_int("EXAM_PREP_SOURCE_RETENTION_DAYS", 7)
    return base + timedelta(days=days)


def projection_fingerprint(projection: dict[str, Any] | str) -> str:
    if isinstance(projection, str):
        try:
            projection = json.loads(projection or "{}")
        except json.JSONDecodeError:
            projection = {}
    canonical = json.dumps(projection, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def clone_units_to_revision(
    *,
    artifact: ExamPrepExtractionArtifact,
    source_revision: int,
    target_revision: int,
    statuses: set[str] | None = None,
    exclude_ids: set[int] | None = None,
) -> None:
    """Copy immutable unit snapshots into a newly claimed artifact revision."""
    queryset = artifact.units.filter(revision=source_revision)
    if statuses is not None:
        queryset = queryset.filter(status__in=statuses)
    if exclude_ids:
        queryset = queryset.exclude(id__in=exclude_ids)
    fields = (
        "stage",
        "unit_key",
        "status",
        "source_page",
        "source_timestamp_ms",
        "source_segment",
        "input_fingerprint",
        "output_payload",
        "quality_report",
        "attempt_count",
        "provider",
        "model_name",
        "prompt_version",
        "response_id",
        "finish_reason",
        "input_length",
        "output_length",
        "duration_ms",
        "error_code",
        "error_detail",
        "heartbeat_at",
    )
    rows = queryset.values_list(*fields).iterator(chunk_size=100)
    while batch := list(islice(rows, 100)):
        ExamPrepExtractionUnit.objects.bulk_create(
            [
            ExamPrepExtractionUnit(
                artifact=artifact,
                revision=target_revision,
                **dict(zip(fields, values)),
            )
                for values in batch
            ],
            batch_size=100,
        )


@dataclass(frozen=True)
class OcrOutcome:
    page_number: int
    text: str
    provider: str
    model: str
    status: str
    quality_report: dict[str, Any]
    unit_id: int


class ExtractionUnitBusy(RuntimeError):
    """Raised when another worker owns a live unit lease."""


def _has_live_lease(unit: ExamPrepExtractionUnit, *, now=None) -> bool:
    if (
        unit.status != ExamPrepExtractionUnit.Status.PROCESSING
        or not unit.processing_task_id
        or unit.heartbeat_at is None
    ):
        return False
    current = now or timezone.now()
    lease_seconds = _env_int("LLM_TIMEOUT_SECONDS", 600) + 120
    return (current - unit.heartbeat_at).total_seconds() < lease_seconds


def _numbers(text: str) -> set[str]:
    normalized = (text or "").translate(_DIGIT_TRANSLATION)
    return {match.group(0).replace(",", ".") for match in _NUMBER_RE.finditer(normalized)}


def numeric_jaccard(left: str, right: str) -> float:
    a, b = _numbers(left), _numbers(right)
    if not a and not b:
        return 1.0
    return len(a & b) / max(1, len(a | b))


def duplicate_line_ratio(text: str) -> float:
    lines = [
        re.sub(r"\s+", " ", line).strip().casefold()
        for line in (text or "").splitlines()
        if line.strip()
    ]
    if len(lines) < 20:
        return 0.0
    return 1.0 - (len(set(lines)) / len(lines))


def quality_report(
    text: str,
    *,
    finish_reason: str,
    native_text_length: int = 0,
    robust_z: float = 0.0,
) -> dict[str, Any]:
    output_length = len(text or "")
    max_chars = _env_int("PDF_OCR_MAX_OUTPUT_CHARS_PER_PAGE", 24_000)
    duplicate_ratio = duplicate_line_ratio(text)
    native_ratio = (
        output_length / native_text_length
        if native_text_length >= 30
        else None
    )
    hard: list[str] = []
    soft: list[str] = []
    if not (text or "").strip():
        hard.append("empty_output")
    if (finish_reason or "").strip().casefold() != "stop":
        hard.append("incomplete_finish_reason")
    if output_length > max_chars:
        hard.append("absolute_length_limit")
    if robust_z >= _env_float("PDF_OCR_ROBUST_Z_LIMIT", 8):
        soft.append("length_outlier")
    if native_ratio is not None and native_ratio > _env_float("PDF_OCR_NATIVE_RATIO_LIMIT", 3):
        soft.append("native_text_ratio")
    if duplicate_ratio >= _env_float("PDF_OCR_DUPLICATE_LINE_RATIO_LIMIT", 0.35):
        soft.append("duplicate_lines")
    return {
        "version": QUALITY_CONTRACT_VERSION,
        "accepted": not hard and not soft,
        "hardIssues": hard,
        "softIssues": soft,
        "outputLength": output_length,
        "nativeTextLength": native_text_length,
        "nativeRatio": native_ratio,
        "duplicateLineRatio": duplicate_ratio,
        "robustZ": robust_z,
    }


def robust_z_scores(lengths: dict[int, int]) -> dict[int, float]:
    if len(lengths) < 4:
        return {key: 0.0 for key in lengths}
    center = median(lengths.values())
    deviations = [abs(value - center) for value in lengths.values()]
    mad = median(deviations)
    if mad <= 0:
        return {key: 0.0 if value == center else float("inf") for key, value in lengths.items()}
    return {
        key: abs(0.6745 * (value - center) / mad)
        for key, value in lengths.items()
    }


@contextmanager
def provider_slot(timeout_seconds: int) -> Iterator[None]:
    limit = _env_int("LLM_PROVIDER_MAX_CONCURRENCY", 8)
    lease = uuid.uuid4().hex
    acquired: str | None = None
    deadline = time.monotonic() + min(60, max(10, timeout_seconds))
    start = int(lease[:8], 16) % limit
    while acquired is None and time.monotonic() < deadline:
        for offset in range(limit):
            key = f"llm-provider-slot:{(start + offset) % limit}"
            if cache.add(key, lease, timeout=timeout_seconds + 60):
                acquired = key
                break
        if acquired is None:
            time.sleep(0.2)
    if acquired is None:
        raise RuntimeError("ظرفیت سرویس پردازش هوشمند تکمیل است؛ واحد دوباره تلاش خواهد شد.")
    try:
        yield
    finally:
        if cache.get(acquired) == lease:
            cache.delete(acquired)


def _unit_fingerprint(
    *,
    image: bytes,
    content_type: str,
    model: str,
    page_number: int,
) -> str:
    digest = hashlib.sha256()
    digest.update(image)
    digest.update(content_type.encode())
    digest.update(model.encode())
    digest.update(PROMPT_VERSION.encode())
    digest.update(QUALITY_CONTRACT_VERSION.encode())
    digest.update(str(page_number).encode())
    return digest.hexdigest()


def _claim_unit(
    *,
    artifact_id: int,
    page_number: int,
    fingerprint: str,
    lease: str,
    allow_accepted: bool = False,
) -> tuple[ExamPrepExtractionUnit, bool]:
    with transaction.atomic():
        artifact = ExamPrepExtractionArtifact.objects.select_for_update().get(id=artifact_id)
        unit, _ = ExamPrepExtractionUnit.objects.select_for_update().get_or_create(
            artifact=artifact,
            stage=ExamPrepExtractionUnit.Stage.OCR,
            unit_key=f"page:{page_number}",
            revision=artifact.revision,
            defaults={
                "source_page": page_number,
                "input_fingerprint": fingerprint,
            },
        )
        if (
            unit.status == ExamPrepExtractionUnit.Status.ACCEPTED
            and unit.input_fingerprint == fingerprint
            and not allow_accepted
        ):
            return unit, False
        if _has_live_lease(unit):
            return unit, False
        if unit.input_fingerprint != fingerprint:
            unit.input_fingerprint = fingerprint
            unit.output_payload = {}
            unit.quality_report = {}
            unit.attempt_count = 0
        if unit.attempt_count >= _env_int("PDF_OCR_MAX_ATTEMPTS", 2):
            return unit, False
        unit.status = ExamPrepExtractionUnit.Status.PROCESSING
        unit.processing_task_id = lease
        unit.attempt_count += 1
        unit.heartbeat_at = timezone.now()
        unit.error_code = ""
        unit.error_detail = ""
        unit.save()
        return unit, True


def _finalize_unit(
    *,
    unit_id: int,
    revision: int,
    lease: str,
    fields: dict[str, Any],
) -> bool:
    fields["updated_at"] = timezone.now()
    return bool(
        ExamPrepExtractionUnit.objects.filter(
            id=unit_id,
            revision=revision,
            status=ExamPrepExtractionUnit.Status.PROCESSING,
            processing_task_id=lease,
        ).update(**fields)
    )


def _ocr_call(
    *,
    image: bytes,
    content_type: str,
    page_number: int,
    model: str,
    retry: bool,
    artifact_id: int,
    unit_id: int,
) -> Any:
    prompt = PROMPTS["pdf_extraction"]["quality_retry" if retry else "default"]
    timeout = _env_int("LLM_TIMEOUT_SECONDS", 600)
    encoded = base64.b64encode(image).decode("ascii")
    with provider_slot(timeout):
        return generate_text(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{content_type};base64,{encoded}"
                            },
                        },
                    ],
                }
            ],
            timeout=timeout,
            temperature=0,
            max_output_tokens=_env_int("PDF_OCR_MAX_OUTPUT_TOKENS", 16_000),
            provider_attempts=1,
            feature=LLMUsageLog.Feature.PDF_EXTRACTION,
            detail=f"exam-v3 page {page_number}",
            tracking_context={
                "pipelineVersion": PIPELINE_VERSION,
                "artifactId": artifact_id,
                "unitId": unit_id,
                "stage": "ocr",
                "pageNumber": page_number,
                "attempt": 2 if retry else 1,
            },
        )


def run_structured_unit(
    *,
    artifact: ExamPrepExtractionArtifact,
    stage: str,
    unit_key: str,
    source_page: int | None,
    source_segment: int | None,
    input_payload: str,
    messages: list[dict[str, Any]],
    schema: Any,
    model: str,
    feature: str,
    prompt_version: str = PROMPT_VERSION,
    quality_contract_version: str = QUALITY_CONTRACT_VERSION,
) -> Any:
    """Run one persisted structured call with exactly two provider attempts."""
    fingerprint = hashlib.sha256(
        "\n".join(
            [
                input_payload,
                model,
                prompt_version,
                quality_contract_version,
                stage,
            ]
        ).encode("utf-8")
    ).hexdigest()
    lease = uuid.uuid4().hex
    max_attempts = _env_int("PDF_OCR_MAX_ATTEMPTS", 2)

    while True:
        with transaction.atomic():
            locked_artifact = ExamPrepExtractionArtifact.objects.select_for_update().get(
                id=artifact.id
            )
            unit, _ = ExamPrepExtractionUnit.objects.select_for_update().get_or_create(
                artifact=locked_artifact,
                stage=stage,
                unit_key=unit_key,
                revision=locked_artifact.revision,
                defaults={
                    "source_page": source_page,
                    "source_segment": source_segment,
                    "input_fingerprint": fingerprint,
                },
            )
            if (
                unit.status == ExamPrepExtractionUnit.Status.ACCEPTED
                and unit.input_fingerprint == fingerprint
            ):
                return schema.model_validate(unit.output_payload)
            if _has_live_lease(unit):
                raise ExtractionUnitBusy(
                    f"extraction unit {unit_key} is owned by another worker"
                )
            if unit.input_fingerprint != fingerprint:
                unit.input_fingerprint = fingerprint
                unit.output_payload = {}
                unit.attempt_count = 0
            if unit.attempt_count >= max_attempts:
                raise RuntimeError(f"extraction unit {unit_key} exhausted its retry budget")
            unit.status = ExamPrepExtractionUnit.Status.PROCESSING
            unit.processing_task_id = lease
            unit.attempt_count += 1
            unit.heartbeat_at = timezone.now()
            unit.save()

        started = time.monotonic()
        try:
            timeout = _env_int("LLM_TIMEOUT_SECONDS", 600)
            with provider_slot(timeout):
                result = generate_text(
                    messages=messages,
                    model=model,
                    feature=feature,
                    timeout=timeout,
                    temperature=0,
                    response_format={"type": "json_object"},
                    max_output_tokens=_env_int("PDF_OCR_MAX_OUTPUT_TOKENS", 16_000),
                    provider_attempts=1,
                    detail=f"exam-v3 {stage} {unit_key}"[:200],
                    tracking_context={
                        "pipelineVersion": PIPELINE_VERSION,
                        "artifactId": artifact.id,
                        "unitId": unit.id,
                        "stage": stage,
                        "attempt": unit.attempt_count,
                    },
                )
            if result.finish_reason.casefold() != "stop":
                raise RuntimeError(f"incomplete finish reason: {result.finish_reason or 'missing'}")
            parsed = parse_structured(result.text, schema)
            saved = _finalize_unit(
                unit_id=unit.id,
                revision=unit.revision,
                lease=lease,
                fields={
                    "status": ExamPrepExtractionUnit.Status.ACCEPTED,
                    "output_payload": parsed.model_dump(mode="json"),
                    "quality_report": {
                        "version": QUALITY_CONTRACT_VERSION,
                        "accepted": True,
                    },
                    "provider": result.provider,
                    "model_name": result.model,
                    "prompt_version": prompt_version,
                    "response_id": result.response_id,
                    "finish_reason": result.finish_reason,
                    "input_length": len(input_payload),
                    "output_length": len(result.text),
                    "duration_ms": int((time.monotonic() - started) * 1000),
                    "heartbeat_at": timezone.now(),
                },
            )
            if not saved:
                raise RuntimeError("stale extraction unit lease")
            return parsed
        except Exception as exc:
            next_status = (
                ExamPrepExtractionUnit.Status.RETRYABLE
                if unit.attempt_count < max_attempts
                else ExamPrepExtractionUnit.Status.FAILED
            )
            _finalize_unit(
                unit_id=unit.id,
                revision=unit.revision,
                lease=lease,
                fields={
                    "status": next_status,
                    "error_code": "structured_output_failed",
                    "error_detail": exc.__class__.__name__[:2000],
                    "duration_ms": int((time.monotonic() - started) * 1000),
                    "heartbeat_at": timezone.now(),
                },
            )
            if next_status == ExamPrepExtractionUnit.Status.FAILED:
                raise


def process_ocr_page(
    *,
    artifact_id: int,
    image: bytes,
    page_number: int,
    native_text_length: int,
    content_type: str = "image/png",
    force_retry: bool = False,
) -> OcrOutcome:
    model = _select_vision_model()
    fingerprint = _unit_fingerprint(
        image=image,
        content_type=content_type,
        model=model,
        page_number=page_number,
    )
    lease = uuid.uuid4().hex
    unit, claimed = _claim_unit(
        artifact_id=artifact_id,
        page_number=page_number,
        fingerprint=fingerprint,
        lease=lease,
        allow_accepted=force_retry,
    )
    if not claimed:
        if _has_live_lease(unit):
            raise ExtractionUnitBusy(
                f"OCR page {page_number} is owned by another worker"
            )
        payload = unit.output_payload or {}
        return OcrOutcome(
            page_number,
            str(payload.get("text") or ""),
            unit.provider,
            unit.model_name or model,
            unit.status,
            unit.quality_report or {},
            unit.id,
        )

    started = time.monotonic()
    previous_text = str((unit.output_payload or {}).get("text") or "")
    try:
        result = _ocr_call(
            image=image,
            content_type=content_type,
            page_number=page_number,
            model=model,
            retry=unit.attempt_count > 1,
            artifact_id=artifact_id,
            unit_id=unit.id,
        )
        report = quality_report(
            result.text,
            finish_reason=result.finish_reason,
            native_text_length=native_text_length,
        )
        if previous_text and not report["hardIssues"]:
            report["numericJaccard"] = numeric_jaccard(previous_text, result.text)
            if report["numericJaccard"] < 0.9:
                report["hardIssues"].append("numeric_instability")

        attempts_left = unit.attempt_count < _env_int("PDF_OCR_MAX_ATTEMPTS", 2)
        stable_retry = (
            unit.attempt_count > 1
            and previous_text
            and report.get("numericJaccard", 1.0) >= 0.9
            and not report["hardIssues"]
            and "duplicate_lines" not in report["softIssues"]
        )
        if stable_retry:
            status = ExamPrepExtractionUnit.Status.ACCEPTED
            report["accepted"] = True
            report["acceptedWithWarnings"] = bool(report["softIssues"])
        elif report["hardIssues"] or report["softIssues"]:
            status = (
                ExamPrepExtractionUnit.Status.RETRYABLE
                if attempts_left
                else ExamPrepExtractionUnit.Status.QUARANTINED
            )
        else:
            status = ExamPrepExtractionUnit.Status.ACCEPTED
        payload = {"text": result.text}
        if status == ExamPrepExtractionUnit.Status.QUARANTINED:
            payload = {}
        _finalize_unit(
            unit_id=unit.id,
            revision=unit.revision,
            lease=lease,
            fields={
                "status": status,
                "output_payload": payload,
                "quality_report": report,
                "provider": result.provider,
                "model_name": result.model,
                "prompt_version": PROMPT_VERSION,
                "response_id": result.response_id,
                "finish_reason": result.finish_reason,
                "input_length": len(image),
                "output_length": len(result.text),
                "duration_ms": int((time.monotonic() - started) * 1000),
                "heartbeat_at": timezone.now(),
            },
        )
    except Exception as exc:
        status = (
            ExamPrepExtractionUnit.Status.RETRYABLE
            if unit.attempt_count < _env_int("PDF_OCR_MAX_ATTEMPTS", 2)
            else ExamPrepExtractionUnit.Status.QUARANTINED
        )
        _finalize_unit(
            unit_id=unit.id,
            revision=unit.revision,
            lease=lease,
            fields={
                "status": status,
                "error_code": "provider_or_storage_error",
                "error_detail": exc.__class__.__name__[:2000],
                "duration_ms": int((time.monotonic() - started) * 1000),
                "heartbeat_at": timezone.now(),
            },
        )

    unit.refresh_from_db()
    if unit.status == ExamPrepExtractionUnit.Status.RETRYABLE:
        return process_ocr_page(
            artifact_id=artifact_id,
            image=image,
            page_number=page_number,
            native_text_length=native_text_length,
            content_type=content_type,
        )
    return OcrOutcome(
        page_number,
        str((unit.output_payload or {}).get("text") or ""),
        unit.provider,
        unit.model_name or model,
        unit.status,
        unit.quality_report or {},
        unit.id,
    )


def extract_pdf_v3(
    *,
    data: bytes,
    artifact: ExamPrepExtractionArtifact,
    page_sink: Callable[[int, bytes, int, int], None] | None = None,
) -> tuple[str, str, str, int]:
    """Render/OCR a PDF with at most two page images resident concurrently."""
    import pypdfium2 as pdfium
    from pypdf import PdfReader

    if not data or b"%PDF" not in data[:1024]:
        raise PdfExtractionError("فایل ارسالی یک PDF معتبر نیست.")
    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted and reader.decrypt("") == 0:
        raise PdfExtractionError("این PDF رمزگذاری‌شده است.")
    page_count = len(reader.pages)
    if page_count == 0:
        raise PdfExtractionError("این PDF هیچ صفحه‌ای ندارد.")
    if page_count > _env_int("PDF_MAX_PAGES", 200):
        raise PdfExtractionError("تعداد صفحات فایل از حداکثر مجاز بیشتر است.")

    dpi = _env_int("PDF_RENDER_DPI", 150)
    max_bytes = _env_int("PDF_MAX_IMAGE_BYTES_MB", 3) * 1024 * 1024
    concurrency = min(2, _env_int("PDF_EXTRACTION_CONCURRENCY", 2))
    blank_std = _env_float("PDF_BLANK_STD_THRESHOLD", 3.0)
    scale = max(0.5, dpi / 72)
    outcomes: dict[int, OcrOutcome] = {}
    page_inputs: dict[int, tuple[str, int]] = {}
    pending: dict[Any, int] = {}

    def drain_one() -> None:
        future = next(as_completed(tuple(pending)))
        page = pending.pop(future)
        outcomes[page] = future.result()

    pdf = pdfium.PdfDocument(data)
    try:
        with tempfile.TemporaryDirectory(prefix="exam-ocr-v3-") as tmpdir, ThreadPoolExecutor(
            max_workers=concurrency
        ) as pool:
            for index in range(page_count):
                pil = pdf[index].render(scale=scale).to_pil()
                native_text = ""
                try:
                    native_text = (reader.pages[index].extract_text() or "").strip()
                except Exception:
                    pass
                if not native_text and _grayscale_std(pil) < blank_std:
                    continue
                png = _encode_png(pil, max_bytes)
                if page_sink:
                    page_sink(index + 1, png, int(pil.width), int(pil.height))
                page_path = os.path.join(tmpdir, f"page-{index + 1}.png")
                with open(page_path, "wb") as handle:
                    handle.write(png)
                page_inputs[index + 1] = (page_path, len(native_text))
                pending[
                    pool.submit(
                        process_ocr_page,
                        artifact_id=artifact.id,
                        image=png,
                        page_number=index + 1,
                        native_text_length=len(native_text),
                    )
                ] = index + 1
                if len(pending) >= concurrency:
                    drain_one()
            while pending:
                drain_one()
            accepted_lengths = {
                page: len(outcome.text)
                for page, outcome in outcomes.items()
                if outcome.status == ExamPrepExtractionUnit.Status.ACCEPTED
            }
            z_scores = robust_z_scores(accepted_lengths)
            for page, score in z_scores.items():
                if score < _env_float("PDF_OCR_ROBUST_Z_LIMIT", 8):
                    continue
                page_path, native_length = page_inputs.get(page, ("", 0))
                if not page_path or not os.path.exists(page_path):
                    continue
                with open(page_path, "rb") as handle:
                    png = handle.read()
                outcomes[page] = process_ocr_page(
                    artifact_id=artifact.id,
                    image=png,
                    page_number=page,
                    native_text_length=native_length,
                    force_retry=True,
                )
    finally:
        pdf.close()

    pages = []
    for page in range(1, page_count + 1):
        outcome = outcomes.get(page)
        body = outcome.text.strip() if outcome and outcome.status == "accepted" else ""
        pages.append(f"## صفحه {page}\n\n{body}".rstrip())
    accepted = [item for item in outcomes.values() if item.status == "accepted"]
    provider = accepted[0].provider if accepted else "local"
    model = accepted[0].model if accepted else _select_vision_model()
    return "\n\n".join(pages).strip(), provider, model, page_count


def current_unit_issues(artifact: ExamPrepExtractionArtifact) -> list[dict[str, Any]]:
    units = artifact.units.filter(revision=artifact.revision).exclude(
        status__in=[
            ExamPrepExtractionUnit.Status.ACCEPTED,
            ExamPrepExtractionUnit.Status.SUPERSEDED,
        ]
    ).order_by("stage", "source_page", "source_timestamp_ms", "source_segment", "id")
    return [
        {
            "id": unit.id,
            "stage": unit.stage,
            "status": unit.status,
            "pageNumber": unit.source_page,
            "timestampMs": unit.source_timestamp_ms,
            "segmentIndex": unit.source_segment,
            "attemptCount": unit.attempt_count,
            "qualityReport": unit.quality_report,
            "errorCode": unit.error_code,
        }
        for unit in units
    ]
