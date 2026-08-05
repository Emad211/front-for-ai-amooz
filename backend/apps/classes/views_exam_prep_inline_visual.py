"""Compatibility visual endpoint for stored assets and inline source crops."""
from __future__ import annotations

import base64
import binascii
import json
import re

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


class InlineOrStoredExamVisualContentView(APIView):
    """Serve legacy DB assets or a verified crop stored in canonical JSON."""

    permission_classes = [IsAuthenticated]

    def get(self, request, session_id: int, asset_id: str):
        # Preserve the complete legacy asset behavior for numeric IDs.
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
            return Response({'detail': 'تصویر یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)
        is_teacher = session.teacher_id == request.user.id
        phone = (getattr(request.user, 'phone', '') or '').strip()
        is_student = bool(
            session.is_published
            and phone
            and session.invites.filter(phone=phone).exists()
        )
        if not is_teacher and not is_student:
            return Response({'detail': 'تصویر یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            parsed = json.loads(session.exam_prep_json or '{}')
        except (json.JSONDecodeError, TypeError):
            parsed = {}
        questions = (
            (parsed.get('exam_prep') or {}).get('questions')
            if isinstance(parsed, dict)
            else []
        )
        target = None
        for question in questions or []:
            if not isinstance(question, dict):
                continue
            for visual in question.get('visuals') or []:
                if not isinstance(visual, dict):
                    continue
                if str(visual.get('id') or '') == asset_id:
                    target = visual
                    break
            if target is not None:
                break
        if target is None or (is_student and target.get('role') == 'solution'):
            return Response({'detail': 'تصویر یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        match = _DATA_URL_RE.fullmatch(str(target.get('dataUrl') or ''))
        if match is None:
            return Response({'detail': 'تصویر یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            payload = base64.b64decode(match.group('data'), validate=True)
        except (ValueError, binascii.Error):
            return Response({'detail': 'تصویر نامعتبر است.'}, status=status.HTTP_404_NOT_FOUND)
        if not payload or len(payload) > _MAX_INLINE_BYTES:
            return Response({'detail': 'تصویر نامعتبر است.'}, status=status.HTTP_404_NOT_FOUND)
        response = HttpResponse(payload, content_type=match.group('mime'))
        response['Cache-Control'] = 'private, max-age=3600'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
