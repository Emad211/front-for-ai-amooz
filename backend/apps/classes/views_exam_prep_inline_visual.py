"""Compatibility endpoint for stored assets and inline/source OCR4 visuals."""
from __future__ import annotations

import base64
import binascii
import json
import re
from typing import Any

from django.core.files.storage import storages
from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ClassCreationSession, ExamPrepVisualAsset
from .views import ExamPrepVisualAssetContentView


_DATA_URL_RE = re.compile(
    r"^data:(?P<mime>image/(?:png|jpeg|webp));base64,(?P<data>[A-Za-z0-9+/=]+)$"
)
_MAX_INLINE_BYTES = 2 * 1024 * 1024
_MAX_STORED_BYTES = 8 * 1024 * 1024
_MISTRAL_VISUAL_PREFIX = "exam-prep/source/visuals/v1/"
_SAFE_CONTENT_TYPES = frozenset({"image/png", "image/jpeg", "image/webp"})


def _stored_source_visual(target: dict[str, Any]) -> tuple[bytes, str] | None:
    """Read only an immutable Stage-3 crop from the private storage namespace."""

    name = str(target.get("storagePath") or "").strip()
    if (
        not name.startswith(_MISTRAL_VISUAL_PREFIX)
        or name.startswith("/")
        or ".." in name.split("/")
        or "\\" in name
    ):
        return None
    content_type = str(target.get("contentType") or "image/png").strip().lower()
    if content_type not in _SAFE_CONTENT_TYPES:
        return None
    try:
        declared_size = int(target.get("byteSize") or 0)
    except (TypeError, ValueError):
        declared_size = 0
    if declared_size < 0 or declared_size > _MAX_STORED_BYTES:
        return None
    try:
        storage = storages["answer_sources"]
        with storage.open(name, "rb") as handle:
            payload = handle.read(_MAX_STORED_BYTES + 1)
    except Exception:
        return None
    if not payload or len(payload) > _MAX_STORED_BYTES:
        return None
    if declared_size and declared_size != len(payload):
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
        for question in questions or []:
            if not isinstance(question, dict):
                continue
            for visual in question.get("visuals") or []:
                if not isinstance(visual, dict):
                    continue
                if str(visual.get("id") or "") == asset_id:
                    target = visual
                    break
            if target is not None:
                break

        # Students never receive solution-only source images before grading.
        if target is None or (is_student and target.get("role") == "solution"):
            return Response(
                {"detail": "تصویر یافت نشد."},
                status=status.HTTP_404_NOT_FOUND,
            )

        resolved = _stored_source_visual(target) or _inline_source_visual(target)
        if resolved is None:
            return Response(
                {"detail": "تصویر یافت نشد."},
                status=status.HTTP_404_NOT_FOUND,
            )
        payload, content_type = resolved
        response = HttpResponse(payload, content_type=content_type)
        response["Cache-Control"] = "private, max-age=3600"
        response["X-Content-Type-Options"] = "nosniff"
        return response
