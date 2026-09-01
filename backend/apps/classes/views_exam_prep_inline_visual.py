"""Compatibility visual endpoint for stored assets and lightweight source crops."""
from __future__ import annotations

import base64
import binascii
import io
import json
import re

from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ClassCreationSession, ExamPrepVisualAsset, StudentExamPrepAttempt
from .views import ExamPrepVisualAssetContentView


_DATA_URL_RE = re.compile(
    r"^data:(?P<mime>image/(?:png|jpeg|webp));base64,(?P<data>[A-Za-z0-9+/=]+)$"
)
_MAX_INLINE_BYTES = 2 * 1024 * 1024


def _source_bbox(value):
    if not isinstance(value, dict):
        return None
    try:
        x0 = float(value.get('x0'))
        y0 = float(value.get('y0'))
        x1 = float(value.get('x1'))
        y1 = float(value.get('y1'))
    except (TypeError, ValueError):
        return None
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        return None
    return x0, y0, x1, y1


def _render_dynamic_source_crop(session: ClassCreationSession, target: dict) -> bytes | None:
    try:
        page_number = int(target.get('sourcePage') or 0)
    except (TypeError, ValueError):
        return None
    bbox = _source_bbox(target.get('sourceBBox'))
    if page_number < 1 or bbox is None or not session.source_file:
        return None

    try:
        import pypdfium2 as pdfium
        from PIL import Image
    except ImportError:
        return None

    try:
        session.source_file.open('rb')
        try:
            pdf_bytes = session.source_file.read()
        finally:
            session.source_file.close()
        document = pdfium.PdfDocument(pdf_bytes)
        if page_number > len(document):
            document.close()
            return None
        page = document[page_number - 1]
        try:
            bitmap = page.render(scale=200 / 72.0)
            try:
                image = bitmap.to_pil().convert('RGB')
            finally:
                bitmap.close()
        finally:
            page.close()
            document.close()

        try:
            width, height = image.size
            x0, y0, x1, y1 = bbox
            pad_x = width * 0.018
            pad_y = height * 0.018
            left = max(0, int(x0 * width - pad_x))
            top = max(0, int(y0 * height - pad_y))
            right = min(width, max(left + 1, int(x1 * width + pad_x)))
            bottom = min(height, max(top + 1, int(y1 * height + pad_y)))
            crop = image.crop((left, top, right, bottom))
            try:
                if max(crop.size) > 2400:
                    ratio = 2400 / max(crop.size)
                    resized = crop.resize(
                        (
                            max(1, int(crop.width * ratio)),
                            max(1, int(crop.height * ratio)),
                        ),
                        Image.Resampling.LANCZOS,
                    )
                    crop.close()
                    crop = resized
                output = io.BytesIO()
                crop.save(output, format='JPEG', quality=90, optimize=True)
                payload = output.getvalue()
                return payload if 0 < len(payload) <= _MAX_INLINE_BYTES else None
            finally:
                crop.close()
        finally:
            image.close()
    except Exception:
        return None


class InlineOrStoredExamVisualContentView(APIView):
    """Serve DB assets, old data URLs, or PDF page/bbox source crops."""

    permission_classes = [IsAuthenticated]

    def get(self, request, session_id: int, asset_id: str):
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
        if target is None:
            return Response({'detail': 'تصویر یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        # Source solutions are visible to the teacher, and to an invited student
        # only after that student's own attempt has been finalized.
        if is_student and target.get('role') == 'solution':
            finalized = StudentExamPrepAttempt.objects.filter(
                session_id=session.id,
                student_id=request.user.id,
                finalized=True,
            ).exists()
            if not finalized:
                return Response({'detail': 'تصویر یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        match = _DATA_URL_RE.fullmatch(str(target.get('dataUrl') or ''))
        if match is not None:
            try:
                payload = base64.b64decode(match.group('data'), validate=True)
            except (ValueError, binascii.Error):
                payload = b''
            if payload and len(payload) <= _MAX_INLINE_BYTES:
                response = HttpResponse(payload, content_type=match.group('mime'))
                response['Cache-Control'] = 'private, no-store, max-age=0'
                response['X-Content-Type-Options'] = 'nosniff'
                return response

        payload = _render_dynamic_source_crop(session, target)
        if not payload:
            return Response({'detail': 'تصویر یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)
        response = HttpResponse(payload, content_type='image/jpeg')
        response['Cache-Control'] = 'private, no-store, max-age=0'
        response['Pragma'] = 'no-cache'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
