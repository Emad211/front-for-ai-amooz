"""Compatibility endpoint for stored assets and inline/source OCR4 visuals."""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
from typing import Any

from django.core.files.storage import storages
from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ClassCreationSession, ExamPrepVisualAsset, StudentExamPrepAttempt
from .services.exam_prep_mistral_visuals import (
    MISTRAL_VISUAL_MAX_BYTES,
    validated_visual_asset_registry,
    visual_registry_entry_matches,
    visual_storage_path_matches_source,
)
from .views import ExamPrepVisualAssetContentView


_DATA_URL_RE = re.compile(
    r"^data:(?P<mime>image/(?:png|jpeg|webp));base64,(?P<data>[A-Za-z0-9+/=]+)$"
)
_MAX_INLINE_BYTES = 2 * 1024 * 1024
_SAFE_CONTENT_TYPES = frozenset({"image/png", "image/jpeg", "image/webp"})


def _stored_source_visual(target: dict[str, Any]) -> tuple[bytes, str] | None:
    """Read only an immutable Stage-3 crop from the private storage namespace."""

    name = str(target.get("storagePath") or "").strip()
    source_sha256 = str(target.get("sourceSha256") or "").strip().lower()
    payload_sha256 = str(target.get("sha256") or "").strip().lower()
    if (
        re.fullmatch(r"[0-9a-f]{64}", source_sha256) is None
        or re.fullmatch(r"[0-9a-f]{64}", payload_sha256) is None
        or not visual_storage_path_matches_source(
            name,
            source_sha256=source_sha256,
        )
    ):
        return None
    content_type = str(target.get("contentType") or "image/png").strip().lower()
    if content_type not in _SAFE_CONTENT_TYPES:
        return None
    try:
        declared_size = int(target.get("byteSize") or 0)
    except (TypeError, ValueError):
        declared_size = 0
    if declared_size <= 0 or declared_size > MISTRAL_VISUAL_MAX_BYTES:
        return None
    try:
        storage = storages["answer_sources"]
        with storage.open(name, "rb") as handle:
            payload = handle.read(MISTRAL_VISUAL_MAX_BYTES + 1)
    except Exception:
        return None
    if not payload or len(payload) > MISTRAL_VISUAL_MAX_BYTES:
        return None
    if declared_size != len(payload):
        return None
    if not hmac.compare_digest(hashlib.sha256(payload).hexdigest(), payload_sha256):
        return None
    return payload, content_type


def _inline_source_visual(target: dict[str, Any]) -> tuple[bytes, str] | None:
    match = _DATA_URL_RE.fullmatch(str(target.get("dataUrl") or ""))
    if match is None:
        return None
    try:
        payload = base64.b64decode(match.group("data"), validate=True)
    except (ValueError, binascii.Error):
        return None
    if not payload or len(payload) > _MAX_INLINE_BYTES:
        return None
    return payload, match.group("mime")


class InlineOrStoredExamVisualContentView(APIView):
    """Serve legacy DB assets, old inline crops, or private OCR4 source crops."""

    permission_classes = [IsAuthenticated]

    def get(self, request, session_id: int, asset_id: str):
        # Preserve complete legacy asset behavior for numeric IDs.
        if asset_id.isdigit() and ExamPrepVisualAsset.objects.filter(
            id=int(asset_id),
            artifact__session_id=session_id,
        ).exists():
            return ExamPrepVisualAssetContentView().get(
                request,
                session_id=session_id,
                asset_id=int(asset_id),
            )

        session = ClassCreationSession.objects.filter(
            id=session_id,
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        ).first()
        if session is None:
            return Response(
                {"detail": "تصویر یافت نشد."},
                status=status.HTTP_404_NOT_FOUND,
            )

        is_teacher = session.teacher_id == request.user.id
        phone = (getattr(request.user, "phone", "") or "").strip()
        is_student = bool(
            session.is_published
            and phone
            and session.invites.filter(phone=phone).exists()
        )
        if not is_teacher and not is_student:
            return Response(
                {"detail": "تصویر یافت نشد."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            parsed = json.loads(session.exam_prep_json or "{}")
        except (json.JSONDecodeError, TypeError):
            parsed = {}
        questions = (
            (parsed.get("exam_prep") or {}).get("questions")
            if isinstance(parsed, dict)
            else []
        )
        target: dict[str, Any] | None = None
        target_question_id = ""
        for question in questions or []:
            if not isinstance(question, dict):
                continue
            for visual in question.get("visuals") or []:
                if not isinstance(visual, dict):
                    continue
                if str(visual.get("id") or "") == asset_id:
                    target = visual
                    target_question_id = str(question.get("question_id") or "").strip()
                    break
            if target is not None:
                break

        if target is None:
            return Response(
                {"detail": "تصویر یافت نشد."},
                status=status.HTTP_404_NOT_FOUND,
            )

        student_can_view_solution = bool(
            is_student
            and StudentExamPrepAttempt.objects.filter(
                session=session,
                student=request.user,
                finalized=True,
            ).exists()
        )

        workflow = session.workflow_state if isinstance(session.workflow_state, dict) else {}
        extraction_audit = workflow.get("extractionAudit")
        registry = validated_visual_asset_registry(
            extraction_audit if isinstance(extraction_audit, dict) else {}
        )
        has_stored_reference = bool(str(target.get("storagePath") or "").strip())
        if has_stored_reference:
            authoritative = registry.get(asset_id)
            if authoritative is None or not visual_registry_entry_matches(
                authoritative,
                target,
                question_id=target_question_id,
            ):
                resolved = None
            elif is_student and authoritative.get("role") == "solution" and not student_can_view_solution:
                resolved = None
            else:
                resolved = _stored_source_visual(authoritative)
        elif is_student and target.get("role") == "solution" and not student_can_view_solution:
            resolved = None
        else:
            resolved = _inline_source_visual(target)
        if resolved is None:
            return Response(
                {"detail": "تصویر یافت نشد."},
                status=status.HTTP_404_NOT_FOUND,
            )
        payload, content_type = resolved
        response = HttpResponse(payload, content_type=content_type)
        response["Cache-Control"] = "private, no-store, max-age=0"
        response["Pragma"] = "no-cache"
        response["X-Content-Type-Options"] = "nosniff"
        return response
