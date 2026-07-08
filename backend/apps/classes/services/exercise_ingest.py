"""Exercise Hub — ingest: extract a structured exercise from source Markdown.

The OCR step (PDF/photo → Markdown) is fully reused from ``pdf_extraction.py`` (a
photo is treated as a page); this module owns only the *structure* step: turn that
Markdown into ``{exercise_title, sections[{questions[...]}]}`` validated against the
``ExerciseStructureOutput`` Pydantic schema via ``generate_structured`` (JSON-mode +
one repair round-trip + **raise**, never a silent ``{}``).

Design: docs/features/exercise-hub.md · ADR-0004. Prompt contract:
``PROMPTS['exercise_structure']['default']`` (byte-for-byte, guarded by
``test_prompts_contract.py``). Model is ENV-only (raise when unset).
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
from difflib import SequenceMatcher
from decimal import Decimal, InvalidOperation
from typing import Any, Tuple

from apps.commons.llm_prompts import PROMPTS
from apps.commons.llm_provider import preferred_provider
from apps.commons.models import LLMUsageLog
from apps.commons.structured_llm import generate_structured
from .schemas import ExerciseReferenceIngestOutput, ExerciseStructureOutput

logger = logging.getLogger(__name__)

_VALID_QUESTION_TYPES = {"descriptive", "multiple_choice", "fill_blank"}

_LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "600"))
_REFERENCE_MATCH_THRESHOLD = float(os.getenv("EXERCISE_REFERENCE_MATCH_THRESHOLD", "0.70"))
_REFERENCE_CONTEXT_MAX_QUESTIONS = int(os.getenv("EXERCISE_REFERENCE_CONTEXT_MAX_QUESTIONS", "120"))
_REFERENCE_CONTEXT_QUESTION_CHARS = int(os.getenv("EXERCISE_REFERENCE_CONTEXT_QUESTION_CHARS", "1200"))


def _get_env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _select_model(*names: str) -> str:
    """Select the LLM model from ENV only — no hardcoded default.

    Checks each of ``names`` in order, then falls back to ``MODEL_NAME``. Raises
    when nothing is set: a misconfigured deployment must fail loudly rather than
    silently calling a hardcoded model. Mirrors ``structure.py._select_model``.
    """
    for n in names:
        val = _get_env(n)
        if val:
            return val
    fallback = _get_env("MODEL_NAME")
    if fallback:
        return fallback
    raise RuntimeError(
        f"No LLM model defined in ENV. Checked: {names} and fallback MODEL_NAME."
    )


def structure_exercise_markdown(*, ingest_markdown: str) -> Tuple[dict[str, Any], str, str]:
    """Return ``(exercise_structure_dict, provider, model_name)``.

    ``ingest_markdown`` is the OCR/extraction Markdown of the uploaded exercise.
    Raises ``RuntimeError`` on total extraction failure (never returns empty).
    """
    model = _select_model("EXERCISE_STRUCTURE_MODEL", "STRUCTURE_MODEL")
    provider = preferred_provider()

    prompt = PROMPTS["exercise_structure"]["default"]
    full_prompt = f"{prompt}\n\nEXERCISE_SOURCE_MARKDOWN:\n{ingest_markdown}"

    logger.info(
        "EXERCISE_STRUCTURE start: model=%s source_chars=%d",
        model, len(ingest_markdown or ""),
    )
    try:
        obj = generate_structured(
            schema=ExerciseStructureOutput,
            contents=full_prompt,
            feature=LLMUsageLog.Feature.EXERCISE_STRUCTURE,
            model=model,
            timeout=_LLM_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        logger.exception("Exercise structure extraction failed")
        raise RuntimeError(f"Exercise structure extraction failed: {exc}") from exc

    return obj.model_dump(), provider, model


def ingest_reference_answers_markdown(
    *,
    source_markdown: str,
    existing_questions: list[dict[str, Any]],
    mode_hint: str = "auto",
) -> Tuple[dict[str, Any], str, str]:
    """Extract teacher reference answers/questions from OCR/source Markdown.

    This is intentionally separate from ``structure_exercise_markdown``:
    the main structure task replaces all sections/questions, while this helper
    returns a mergeable patch for an existing exercise. The model may receive:
    full Q+A sheets, one Q+A, answer keys with question numbers, or answer-only
    text/images. Ambiguous matching is resolved by the API layer, not guessed.
    """
    model = _select_model(
        "EXERCISE_REFERENCE_INGEST_MODEL",
        "EXERCISE_STRUCTURE_MODEL",
        "STRUCTURE_MODEL",
    )
    provider = preferred_provider()
    prompt = (
        str(PROMPTS["exercise_reference_ingest"]["default"])
        .replace("{mode_hint}", str(mode_hint or "auto"))
        .replace(
            "{existing_questions_json}",
            json.dumps(existing_questions, ensure_ascii=False),
        )
        .replace("{source_markdown}", source_markdown or "")
    )

    logger.info(
        "EXERCISE_REFERENCE_INGEST start: model=%s source_chars=%d questions=%d",
        model, len(source_markdown or ""), len(existing_questions),
    )
    try:
        obj = generate_structured(
            schema=ExerciseReferenceIngestOutput,
            contents=prompt,
            feature=LLMUsageLog.Feature.EXERCISE_REFERENCE_INGEST,
            model=model,
            timeout=_LLM_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        logger.exception("Exercise reference-answer ingest failed")
        raise RuntimeError(f"Exercise reference-answer ingest failed: {exc}") from exc

    return obj.model_dump(), provider, model


# ---------------------------------------------------------------------------
# OCR: source assets (PDF / photos) -> Markdown. PDF reuses pdf_extraction; a
# photo is treated as one page via a single standard-shape multimodal call.
# ---------------------------------------------------------------------------


def _ocr_image_to_markdown(*, data: bytes, mime_type: str) -> str:
    """One vision OCR call for a single image, using the pdf_extraction prompt
    and the standard OpenAI multimodal shape (``image_url`` data URI)."""
    from apps.chatbot.services.llm_client import generate_text

    model = _select_model("EXERCISE_VISION_MODEL", "IMAGE_MODEL")
    prompt = str(PROMPTS["pdf_extraction"]["default"])
    b64 = base64.b64encode(data).decode()
    messages = [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
    ]}]
    resp = generate_text(
        messages=messages, model=model,
        feature=LLMUsageLog.Feature.EXERCISE_INGEST, timeout=_LLM_TIMEOUT_SECONDS,
    )
    return (resp.text if hasattr(resp, "text") else str(resp)).strip()


def ocr_assets_to_markdown(exercise, *, asset_orders: list[int] | None = None, preamble: str = "") -> str:
    """Concatenate the OCR Markdown of selected source assets of an exercise."""
    from .pdf_extraction import extract_pdf_to_markdown

    qs = exercise.assets.all().order_by("order", "id")
    if asset_orders is not None:
        qs = qs.filter(order__in=asset_orders)
    parts: list[str] = [preamble.strip()] if (preamble or "").strip() else []
    for asset in qs:
        data = asset.file.read()
        if not data:
            continue
        if asset.kind == "pdf":
            markdown, *_rest = extract_pdf_to_markdown(data=data, mime_type="application/pdf")
        else:
            markdown = _ocr_image_to_markdown(data=data, mime_type="image/jpeg")
        if markdown and markdown.strip():
            parts.append(markdown.strip())
    return "\n\n---\n\n".join(parts)


def ocr_uploaded_files_to_markdown(files) -> str:
    """OCR ad-hoc teacher uploads without adding them to exercise assets.

    Used by the reference-answer ingest panel. PDF pages reuse the normal PDF
    extractor; images are magic-byte sniffed before the vision call.
    """
    from .file_validation import is_real_image
    from .pdf_extraction import extract_pdf_to_markdown

    parts: list[str] = []
    for uploaded in files:
        data = uploaded.read()
        try:
            uploaded.seek(0)
        except Exception:
            pass
        if not data:
            continue
        content_type = (getattr(uploaded, "content_type", "") or "").lower()
        name = (getattr(uploaded, "name", "") or "").lower()
        if "pdf" in content_type or name.endswith(".pdf"):
            markdown, *_rest = extract_pdf_to_markdown(data=data, mime_type="application/pdf")
        elif content_type.startswith("image/") or name.endswith((".jpg", ".jpeg", ".png", ".webp")):
            if not is_real_image(data):
                raise ValueError("uploaded file is not a valid image")
            markdown = _ocr_image_to_markdown(
                data=data,
                mime_type=content_type if content_type.startswith("image/") else "image/jpeg",
            )
        else:
            raise ValueError("unsupported file type")
        if markdown and markdown.strip():
            parts.append(markdown.strip())
    return "\n\n---\n\n".join(parts)


# ---------------------------------------------------------------------------
# Reference ingest preview matching. The LLM extracts candidates; these helpers
# conservatively map them onto existing question rows for teacher review.
# ---------------------------------------------------------------------------


def _clip_text(value: Any, max_chars: int) -> str:
    text = str(value or "")
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n...[trimmed]"


def compact_existing_questions(exercise, *, question_ids: list[int] | None = None) -> list[dict[str, Any]]:
    """Compact question context sent to the reference-ingest prompt."""
    from ..models import ClassExerciseQuestion

    qs = (
        ClassExerciseQuestion.objects
        .filter(section__exercise=exercise)
        .select_related("section")
        .order_by("section__order", "order", "id")
    )
    if question_ids:
        qs = qs.filter(id__in=question_ids)
    out: list[dict[str, Any]] = []
    for idx, q in enumerate(qs[:_REFERENCE_CONTEXT_MAX_QUESTIONS], start=1):
        out.append({
            "id": q.id,
            "number": idx,
            "section_id": q.section_id,
            "section_title": q.section.title,
            "question_order": q.order,
            "question_markdown": _clip_text(q.question_markdown, _REFERENCE_CONTEXT_QUESTION_CHARS),
            "question_type": q.question_type,
            "has_reference_answer": bool((q.reference_answer_markdown or "").strip()),
            "max_points": str(q.max_points),
        })
    return out


def _normalize_match_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = text.translate({
        ord(a): ord(b)
        for a, b in zip("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    })
    text = re.sub(r"[`*_#>$\\{}[\]().،,:;؛!?؟\-\s]+", " ", text)
    return text.strip()


def _confidence(value: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, min(float(value), 1.0))
    except (TypeError, ValueError):
        return default


def _coerce_positive_float(value: Any) -> float | None:
    try:
        val = float(value)
    except (TypeError, ValueError):
        return None
    return val if val > 0 else None


def _question_label(q: dict[str, Any]) -> str:
    number = q.get("number")
    title = q.get("section_title") or "بخش"
    return f"سوال {number} - {title}"


def build_reference_ingest_preview(
    *,
    exercise,
    extracted: dict[str, Any],
    target_question_id: int | None = None,
) -> dict[str, Any]:
    """Build a reviewable preview from extracted reference-answer candidates."""
    existing = compact_existing_questions(exercise)
    by_number = {int(q["number"]): q for q in existing}
    by_id = {int(q["id"]): q for q in existing}
    target = by_id.get(int(target_question_id)) if target_question_id else None
    items = extracted.get("items") if isinstance(extracted, dict) else []
    if not isinstance(items, list):
        items = []

    preview_items: list[dict[str, Any]] = []
    warnings = list(extracted.get("warnings") or []) if isinstance(extracted, dict) else []

    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        confidence = _confidence(item.get("confidence"), default=0.0)
        q_text = str(item.get("question_text_markdown") or "").strip()
        ref_answer = str(item.get("reference_answer_markdown") or "").strip()
        points = _coerce_positive_float(item.get("points"))
        notes = str(item.get("notes") or "").strip()

        match_status = "unmatched"
        matched_q: dict[str, Any] | None = None
        match_notes: list[str] = []

        if target is not None:
            if len(items) == 1:
                matched_q = target
                match_status = "matched"
                confidence = max(confidence, 0.9)
            else:
                match_status = "ambiguous"
                match_notes.append("برای چند مورد نمی‌توان یک سوال هدف مشترک را خودکار اعمال کرد.")
        elif item.get("question_number") is not None:
            try:
                qn = int(item.get("question_number"))
            except (TypeError, ValueError):
                qn = 0
            matched_q = by_number.get(qn)
            if matched_q and confidence >= _REFERENCE_MATCH_THRESHOLD:
                match_status = "matched"
            elif matched_q:
                match_status = "ambiguous"
                match_notes.append("شماره سوال پیدا شد اما اطمینان استخراج پایین است.")
            else:
                match_status = "unmatched"
                match_notes.append("شماره سوال در تمرین پیدا نشد.")
        elif q_text:
            norm = _normalize_match_text(q_text)
            scored: list[tuple[float, dict[str, Any]]] = []
            for q in existing:
                score = SequenceMatcher(
                    None, norm, _normalize_match_text(q.get("question_markdown"))
                ).ratio()
                scored.append((score, q))
            scored.sort(key=lambda pair: pair[0], reverse=True)
            if scored and scored[0][0] >= 0.72:
                best_score, best_q = scored[0]
                gap = best_score - (scored[1][0] if len(scored) > 1 else 0.0)
                confidence = max(confidence, min(best_score, 0.95))
                if gap >= 0.08 and confidence >= _REFERENCE_MATCH_THRESHOLD:
                    matched_q = best_q
                    match_status = "matched"
                else:
                    match_status = "ambiguous"
                    matched_q = best_q
                    match_notes.append("چند سوال شبیه به این متن پیدا شد؛ نیاز به بررسی معلم دارد.")

        if not ref_answer:
            match_status = "ambiguous" if matched_q else "unmatched"
            match_notes.append("پاسخ مرجع صریحی در این مورد پیدا نشد.")

        target_id = int(matched_q["id"]) if matched_q else None
        preview_items.append({
            "id": f"item-{idx}",
            "itemId": item.get("item_id") or f"i{idx}",
            "matchStatus": match_status,
            "targetQuestionId": target_id,
            "targetQuestionLabel": _question_label(matched_q) if matched_q else "",
            "hasExistingReference": bool(matched_q and matched_q.get("has_reference_answer")),
            "questionNumber": item.get("question_number"),
            "questionMarkdown": q_text,
            "questionType": item.get("question_type") if item.get("question_type") in _VALID_QUESTION_TYPES else None,
            "options": item.get("options") if isinstance(item.get("options"), list) else None,
            "maxPoints": points,
            "referenceAnswerMarkdown": ref_answer,
            "confidence": round(confidence, 2),
            "notes": " ".join([notes, *match_notes]).strip(),
        })

    counts = {
        "total": len(preview_items),
        "matched": sum(1 for item in preview_items if item["matchStatus"] == "matched"),
        "ambiguous": sum(1 for item in preview_items if item["matchStatus"] == "ambiguous"),
        "unmatched": sum(1 for item in preview_items if item["matchStatus"] == "unmatched"),
    }
    return {
        "modeDetected": extracted.get("mode_detected") if isinstance(extracted, dict) else "unknown",
        "items": preview_items,
        "warnings": warnings,
        "counts": counts,
    }


def apply_reference_preview_items(
    *,
    exercise,
    preview_items: list[dict[str, Any]],
    replace_existing: bool = False,
) -> dict[str, Any]:
    """Apply matched reference-answer preview items onto question rows.

    Used by both the teacher-reviewed API flow and the automatic draft-building
    flow. The caller decides which preview items are safe enough to pass here.
    """
    from ..models import ClassExerciseQuestion

    questions = {
        q.id: q for q in ClassExerciseQuestion.objects.filter(section__exercise=exercise)
    }
    applied: list[int] = []
    skipped: list[dict[str, Any]] = []

    for item in preview_items:
        if not isinstance(item, dict):
            continue
        try:
            qid = int(item.get("targetQuestionId"))
        except (TypeError, ValueError):
            continue
        q = questions.get(qid)
        if q is None:
            continue
        if (q.reference_answer_markdown or "").strip() and not replace_existing:
            skipped.append({"targetQuestionId": q.id, "reason": "existing_reference"})
            continue

        fields: list[str] = []
        ref = str(item.get("referenceAnswerMarkdown") or item.get("reference_answer_markdown") or "").strip()
        if ref:
            q.reference_answer_markdown = ref
            fields.append("reference_answer_markdown")

        raw_points = item.get("maxPoints") if item.get("maxPoints") is not None else item.get("max_points")
        if raw_points is not None:
            points = _coerce_points(raw_points)
            if points > 0:
                q.max_points = points
                fields.append("max_points")

        question_text = str(item.get("questionMarkdown") or item.get("question_markdown") or "").strip()
        if question_text and bool(item.get("replaceQuestionText") or item.get("replace_question_text")):
            q.question_markdown = question_text
            fields.append("question_markdown")

        question_type = item.get("questionType") or item.get("question_type")
        if question_type in _VALID_QUESTION_TYPES:
            q.question_type = question_type
            fields.append("question_type")

        options = item.get("options")
        if isinstance(options, list):
            q.options = options
            fields.append("options")

        if not fields:
            skipped.append({"targetQuestionId": q.id, "reason": "empty_patch"})
            continue
        q.save(update_fields=sorted(set(fields)))
        applied.append(q.id)

    return {
        "appliedCount": len(set(applied)),
        "updatedQuestionIds": sorted(set(applied)),
        "skipped": skipped,
    }


# ---------------------------------------------------------------------------
# Persist a validated exercise-structure dict into section/question rows.
# ---------------------------------------------------------------------------


def _coerce_question_type(value: Any) -> str:
    v = str(value or "").strip().lower()
    return v if v in _VALID_QUESTION_TYPES else "descriptive"


def _coerce_points(value: Any) -> Decimal:
    if value is None:
        return Decimal("1")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("1")


def persist_exercise_structure(exercise, structure: dict) -> tuple[int, int]:
    """Replace the exercise's sections/questions from a validated structure dict.

    Idempotent for re-runs: existing sections are cleared first (CASCADE drops
    their questions). Returns ``(section_count, question_count)``.
    """
    from ..models import ClassExerciseSection, ClassExerciseQuestion

    exercise.sections.all().delete()  # cascades questions
    n_sections = n_questions = 0
    for s_idx, section in enumerate(structure.get("sections") or []):
        if not isinstance(section, dict):
            continue
        sec = ClassExerciseSection.objects.create(
            exercise=exercise, order=s_idx,
            title=str(section.get("title") or "")[:255],
        )
        n_sections += 1
        for q_idx, q in enumerate(section.get("questions") or []):
            if not isinstance(q, dict):
                continue
            options = q.get("options")
            ClassExerciseQuestion.objects.create(
                section=sec, order=q_idx,
                question_markdown=str(q.get("question_text_markdown") or ""),
                question_type=_coerce_question_type(q.get("question_type")),
                options=options if isinstance(options, list) else [],
                reference_answer_markdown=str(q.get("reference_answer_markdown") or ""),
                max_points=_coerce_points(q.get("points")),
            )
            n_questions += 1
    return n_sections, n_questions
