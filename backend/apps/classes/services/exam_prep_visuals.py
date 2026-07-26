"""Source-crop extraction and optional teacher-reviewed visual generation."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import time
from typing import Any

from django.core.files.base import ContentFile
from django.core.files.storage import storages
from core.storage_backends import delete_answer_source_file

from apps.chatbot.services.llm_client import (
    _get_gapgpt_client,
    _strip_model_prefix,
)
from apps.commons.llm_prompts import PROMPTS
from apps.commons.models import LLMUsageLog
from apps.commons.structured_llm import generate_structured
from apps.commons.token_tracker import track_llm_usage

from ..models import ExamPrepExtractionArtifact, ExamPrepVisualAsset
from .exam_prep_inventory import normalize_section_key, normalize_source_number, question_record_key
from .schemas import ExamPrepVisualDetectionOutput, ExamPrepVisualVerificationOutput


GENERATION_PROMPT_VERSION = "exam-visual-v1"
ANALYSIS_PROMPT_VERSION = "exam-visual-detection-v1"


def image_generation_enabled() -> bool:
    return (os.getenv("EXAM_PREP_IMAGE_GENERATION_ENABLED", "false") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _generation_model() -> str:
    model = (os.getenv("EXAM_PREP_IMAGE_GENERATION_MODEL") or "").strip()
    if not model:
        raise RuntimeError("EXAM_PREP_IMAGE_GENERATION_MODEL is required when image generation is enabled.")
    return _strip_model_prefix(model)


def _read_private(name: str) -> bytes:
    with storages["answer_sources"].open(name, "rb") as source:
        return source.read()


def _image_part(data: bytes, content_type: str) -> dict[str, Any]:
    encoded = base64.b64encode(data).decode("ascii")
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{content_type};base64,{encoded}"},
    }


def _question_lookup(records: list[dict[str, Any]]) -> dict[tuple[str, str], str]:
    result = {}
    for record in records:
        number = normalize_source_number(record.get("source_question_number"))
        section = normalize_section_key(record.get("section_key"))
        if number:
            result[(section, number)] = question_record_key(record)
    return result


def _detect_visuals(
    *, image: bytes, content_type: str, context: dict[str, Any], model: str
) -> ExamPrepVisualDetectionOutput:
    return generate_structured(
        schema=ExamPrepVisualDetectionOutput,
        messages=[
            {"role": "system", "content": PROMPTS["exam_prep_visual_detection"]["default"]},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "PAGE_CONTEXT:\n" + json.dumps(context, ensure_ascii=False),
                    },
                    _image_part(image, content_type),
                ],
            },
        ],
        model=model,
        feature=LLMUsageLog.Feature.EXAM_PREP_STRUCTURE,
        timeout=int(os.getenv("LLM_TIMEOUT_SECONDS", "600")),
        temperature=0,
    )


def _crop(image: bytes, bbox: list[float]) -> bytes:
    from PIL import Image

    if len(bbox) != 4:
        raise ValueError("visual bbox must contain four coordinates")
    x0, y0, x1, y1 = [max(0.0, min(1.0, float(value))) for value in bbox]
    if x1 <= x0 or y1 <= y0 or (x1 - x0) * (y1 - y0) < 0.0025:
        raise ValueError("visual bbox is empty or too small")
    with Image.open(io.BytesIO(image)) as source:
        width, height = source.size
        padding_x = max(4, int(width * 0.01))
        padding_y = max(4, int(height * 0.01))
        box = (
            max(0, int(x0 * width) - padding_x),
            max(0, int(y0 * height) - padding_y),
            min(width, int(x1 * width) + padding_x),
            min(height, int(y1 * height) + padding_y),
        )
        cropped = source.convert("RGB").crop(box)
        output = io.BytesIO()
        cropped.save(output, format="PNG", optimize=True)
        return output.getvalue()


def _generate_candidate(*, visual_spec: dict[str, Any], repair_issues: list[str] | None = None):
    model = _generation_model()
    prompt = PROMPTS["exam_prep_visual_generation"]["default"].replace(
        "{visual_spec_json}", json.dumps(visual_spec, ensure_ascii=False, sort_keys=True)
    )
    if repair_issues:
        prompt += "\nFix these verification failures exactly:\n" + "\n".join(repair_issues)
    client = _get_gapgpt_client()
    started = time.monotonic()
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": [{"type": "text", "text": prompt}]}],
        modalities=["image", "text"],
        extra_body={"generationConfig": {"imageConfig": {"aspectRatio": "4:3"}}},
        timeout=float(os.getenv("LLM_TIMEOUT_SECONDS", "600")),
    )
    track_llm_usage(
        resp=response,
        feature=LLMUsageLog.Feature.EXAM_PREP_STRUCTURE,
        provider="avalai",
        model_name=model,
        detail="exam-prep visual generation",
        duration_ms=int((time.monotonic() - started) * 1000),
    )
    images = getattr(response.choices[0].message, "images", None) or []
    if not images:
        raise RuntimeError("Avalai image response did not contain an image.")
    image_url = getattr(getattr(images[0], "image_url", None), "url", None)
    if not image_url and isinstance(images[0], dict):
        image_url = (images[0].get("image_url") or {}).get("url")
    if not image_url or not image_url.startswith("data:image/") or ";base64," not in image_url:
        raise RuntimeError("Avalai returned an unsupported image payload.")
    header, encoded = image_url.split(",", 1)
    content_type = header[5:].split(";", 1)[0]
    return base64.b64decode(encoded), content_type, model


def _verify_candidate(
    *,
    original: bytes,
    generated: bytes,
    generated_content_type: str,
    spec: dict[str, Any],
    model: str,
) -> dict[str, Any]:
    result = generate_structured(
        schema=ExamPrepVisualVerificationOutput,
        messages=[
            {"role": "system", "content": PROMPTS["exam_prep_visual_verification"]["default"]},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "VISUAL_SPEC:\n" + json.dumps(spec, ensure_ascii=False)},
                    {"type": "text", "text": "ORIGINAL:"},
                    _image_part(original, "image/png"),
                    {"type": "text", "text": "GENERATED:"},
                    _image_part(generated, generated_content_type),
                ],
            },
        ],
        model=model,
        feature=LLMUsageLog.Feature.EXAM_PREP_STRUCTURE,
        timeout=int(os.getenv("LLM_TIMEOUT_SECONDS", "600")),
        temperature=0,
    )
    return result.model_dump()


def _maybe_generate(asset: ExamPrepVisualAsset, original: bytes, verification_model: str) -> None:
    if (
        not image_generation_enabled()
        or asset.generated_file
        or asset.status in {
            ExamPrepVisualAsset.Status.NEEDS_REVIEW,
            ExamPrepVisualAsset.Status.FAILED,
        }
    ):
        return
    asset.status = ExamPrepVisualAsset.Status.GENERATING
    asset.save(update_fields=["status", "updated_at"])
    try:
        issues: list[str] | None = None
        for _attempt in range(2):
            generated, content_type, generation_model = _generate_candidate(
                visual_spec=asset.visual_spec,
                repair_issues=issues,
            )
            verification = _verify_candidate(
                original=original,
                generated=generated,
                generated_content_type=content_type,
                spec=asset.visual_spec,
                model=verification_model,
            )
            if verification["equivalent"] and float(verification["confidence"]) >= 0.85:
                digest = hashlib.sha256(generated).hexdigest()
                suffix = {
                    "image/jpeg": "jpg",
                    "image/png": "png",
                    "image/webp": "webp",
                }.get(content_type, "bin")
                asset.generated_file.save(
                    f"{digest}.{suffix}",
                    ContentFile(generated),
                    save=False,
                )
                asset.generated_content_type = content_type
                asset.generated_byte_size = len(generated)
                asset.generated_sha256 = digest
                asset.verification = verification
                asset.generation_provider = "avalai"
                asset.generation_model = generation_model
                asset.generation_prompt_version = GENERATION_PROMPT_VERSION
                asset.status = ExamPrepVisualAsset.Status.VERIFIED
                asset.save()
                return
            issues = list(verification.get("issues") or ["candidate is not equivalent"])
        asset.verification = verification
        asset.status = ExamPrepVisualAsset.Status.NEEDS_REVIEW
        asset.error_detail = "Generated candidate failed automatic equivalence verification."
    except Exception as exc:
        asset.status = ExamPrepVisualAsset.Status.NEEDS_REVIEW
        asset.error_detail = f"Generated candidate unavailable: {type(exc).__name__}"
    asset.save(update_fields=["verification", "status", "error_detail", "updated_at"])


def process_exam_prep_visuals(
    *, artifact: ExamPrepExtractionArtifact, projection: dict[str, Any], model: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Crop source visuals and attach structured references to the projection."""
    manifest = (artifact.page_manifest or {}).get("pages") or []
    manifest_by_page = {
        int(item["page_number"]): item
        for item in manifest
        if isinstance(item, dict) and item.get("page_number")
    }
    lookup = _question_lookup(artifact.question_records or [])
    questions = (projection.get("exam_prep") or {}).get("questions") or []
    projected_by_id = {question.get("question_id"): question for question in questions}
    record_by_key = {
        question_record_key(record): record for record in artifact.question_records or []
    }
    hinted_pages = {
        int(page)
        for record in [*(artifact.question_records or []), *(artifact.answer_records or [])]
        if record.get("visual_hints")
        for page in record.get("source_pages") or []
    }
    analysis_model = (
        (os.getenv("EXAM_PREP_VISUAL_ANALYSIS_MODEL") or "").strip()
        or (os.getenv("PDF_VISION_MODEL") or "").strip()
        or model
    )
    issues: list[dict[str, Any]] = []
    retained_asset_ids: set[int] = set()

    for source_block in artifact.source_blocks or []:
        storage_name = source_block.get("storageName")
        page = source_block.get("pageNumber")
        if not storage_name:
            continue
        page_manifest = manifest_by_page.get(int(page)) if page else {}
        if (
            page_manifest
            and not page_manifest.get("has_visuals")
            and int(page or 0) not in hinted_pages
        ):
            continue
        source_bytes = _read_private(storage_name)
        context = {
            "source": {
                "pageNumber": page,
                "timestampMs": source_block.get("timestampMs"),
            },
            "manifest": page_manifest or {},
        }
        detection = _detect_visuals(
            image=source_bytes,
            content_type=source_block.get("contentType") or "image/png",
            context=context,
            model=analysis_model,
        )
        for region in detection.visuals:
            section = normalize_section_key(region.section_key)
            number = normalize_source_number(region.question_number)
            key = lookup.get((section, number))
            if key is None and number:
                matches = [value for (candidate_section, candidate_number), value in lookup.items() if candidate_number == number]
                key = matches[0] if len(matches) == 1 else None
            if key is None:
                issues.append(
                    {
                        "code": "unmatched_visual",
                        "severity": "critical",
                        "sourcePage": page,
                        "sourceQuestionNumber": region.question_number,
                    }
                )
                continue
            try:
                cropped = _crop(source_bytes, region.bbox)
            except ValueError:
                issues.append(
                    {"code": "invalid_visual_bbox", "severity": "critical", "questionKey": key, "sourcePage": page}
                )
                continue
            fingerprint = hashlib.sha256(
                cropped
                + json.dumps(region.specification, sort_keys=True, ensure_ascii=False).encode()
                + analysis_model.encode()
                + ANALYSIS_PROMPT_VERSION.encode()
            ).hexdigest()
            source_kind = source_block.get("sourceKind") or "source_image"
            source_sha256 = hashlib.sha256(cropped).hexdigest()
            asset_key = hashlib.sha256(
                json.dumps(
                    {
                        "source": source_block.get("sha256"),
                        "question": key,
                        "role": region.role,
                        "option": region.option_label or "",
                        "order": region.order,
                        "bbox": region.bbox,
                    },
                    sort_keys=True,
                    ensure_ascii=False,
                ).encode()
            ).hexdigest()
            asset, created = ExamPrepVisualAsset.objects.get_or_create(
                artifact=artifact,
                asset_key=asset_key,
                defaults={
                    "question_key": key,
                    "order": region.order,
                    "role": region.role,
                    "option_label": region.option_label or "",
                    "source_kind": source_kind,
                    "source_page": page,
                    "source_timestamp_ms": source_block.get("timestampMs"),
                    "source_bbox": {"normalized": region.bbox},
                    "source_content_type": "image/png",
                    "source_byte_size": len(cropped),
                    "source_sha256": source_sha256,
                    "alt_text": region.alt_text,
                    "visual_spec": {
                        "visualType": region.visual_type,
                        "exactText": region.exact_text,
                        **region.specification,
                        "role": region.role,
                    },
                    "fingerprint": fingerprint,
                },
            )
            retained_asset_ids.add(asset.id)
            if created:
                asset.source_file.save(f"{asset.source_sha256}.png", ContentFile(cropped), save=True)
            elif asset.fingerprint != fingerprint:
                old_source_name = asset.source_file.name if asset.source_file else ""
                old_generated_name = asset.generated_file.name if asset.generated_file else ""
                asset.role = region.role
                asset.option_label = region.option_label or ""
                asset.source_kind = source_kind
                asset.source_page = page
                asset.source_timestamp_ms = source_block.get("timestampMs")
                asset.source_bbox = {"normalized": region.bbox}
                asset.source_byte_size = len(cropped)
                if asset.source_sha256 != source_sha256:
                    asset.source_file.save(
                        f"{source_sha256}.png",
                        ContentFile(cropped),
                        save=False,
                    )
                    asset.source_sha256 = source_sha256
                asset.alt_text = region.alt_text
                asset.visual_spec = {
                    "visualType": region.visual_type,
                    "exactText": region.exact_text,
                    **region.specification,
                    "role": region.role,
                }
                asset.fingerprint = fingerprint
                asset.generated_file = ""
                asset.generated_content_type = ""
                asset.generated_byte_size = 0
                asset.generated_sha256 = ""
                asset.verification = {}
                asset.teacher_approved_generated = False
                asset.selected_variant = ExamPrepVisualAsset.SelectedVariant.SOURCE
                asset.status = ExamPrepVisualAsset.Status.SOURCE_READY
                asset.error_detail = ""
                asset.save()
                if old_source_name and old_source_name != asset.source_file.name:
                    delete_answer_source_file(old_source_name)
                if old_generated_name:
                    delete_answer_source_file(old_generated_name)
            _maybe_generate(asset, cropped, analysis_model)
            record = record_by_key[key]
            projected = projected_by_id.get(record.get("question_id"))
            if projected is not None:
                projected.setdefault("visuals", []).append(
                    {
                        "id": asset.id,
                        "role": asset.role,
                        "optionLabel": asset.option_label or None,
                        "altText": asset.alt_text,
                        "selectedVariant": asset.selected_variant,
                    }
                )
    artifact.visual_assets.exclude(id__in=retained_asset_ids).delete()
    return projection, issues
