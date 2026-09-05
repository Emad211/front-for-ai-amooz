"""Teacher-scoped upload + protected content views for Exam Prep visuals.

Two complementary endpoints:

* ``TeacherExamPrepVisualUploadView`` — a session owner (teacher) uploads one
  image and attaches it to a question stem / option / solution of the legacy
  extracted ``exam_prep_json``.
* ``TeacherExamPrepVisualContentView`` — streams the stored private bytes back
  to the owning teacher, or to an invited student (published session only),
  without ever exposing the storage object name or path.

Image files live in the private ``answer_sources`` storage under
``exam-prep/teacher-visuals/<session_id>/...``; the public media proxy rejects
that prefix, so these endpoints are the only way the bytes leave the backend.
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.commons.phone_utils import normalize_phone

from .models import ClassCreationSession, StudentExamPrepAttempt
from .permissions import IsTeacherUser
from .services.exam_prep_teacher_visuals import (
    TEACHER_VISUAL_ID_PREFIX,
    TEACHER_VISUAL_MAX_UPLOAD_BYTES,
    TeacherVisualError,
    UnknownTeacherVisualQuestionError,
    attach_teacher_visual,
    find_teacher_visual_reference,
    remove_teacher_visual,
    teacher_visual_content_type,
    teacher_visual_storage_path,
)


def _session_or_none(session_id: int) -> ClassCreationSession | None:
    return ClassCreationSession.objects.filter(
        id=session_id,
        pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
    ).first()


class TeacherExamPrepVisualUploadView(APIView):
    """Attach an uploaded image to a question of a legacy Exam Prep session
    (POST) or detach a previously uploaded teacher image (DELETE)."""

    permission_classes = [IsAuthenticated, IsTeacherUser]
    parser_classes = [FormParser, MultiPartParser]

    def post(self, request, session_id: int):
        session = _session_or_none(session_id)
        if session is None:
            return Response(
                {'detail': 'جلسه آمادگی آزمون یافت نشد.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if session.teacher_id != request.user.id:
            return Response(
                {'detail': 'شما مالک این جلسه نیستید.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        question_id = str(request.data.get('question_id') or '').strip()
        role = str(request.data.get('role') or '').strip()
        option_label = request.data.get('option_label')
        uploaded = request.FILES.get('image')
        if uploaded is None:
            return Response(
                {'detail': 'فایل تصویر (image) ارسال نشده است.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            declared_size = int(getattr(uploaded, 'size', 0) or 0)
        except (TypeError, ValueError):
            declared_size = 0
        if declared_size > TEACHER_VISUAL_MAX_UPLOAD_BYTES:
            return Response(
                {'detail': 'حجم تصویر بیش از ۵ مگابایت است.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            image_content = uploaded.read()
        except Exception:
            return Response(
                {'detail': 'خواندن فایل تصویر ممکن نشد.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            result = attach_teacher_visual(
                session,
                question_id=question_id,
                role=role,
                image_content=image_content,
                image_name=str(getattr(uploaded, 'name', '') or ''),
                option_label=option_label,
            )
        except UnknownTeacherVisualQuestionError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except TeacherVisualError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result, status=status.HTTP_201_CREATED)

    def delete(self, request, session_id: int):
        """Detach and delete one teacher-uploaded visual (``?visual_id=…``).

        Only the owning teacher may remove a visual; the JSON reference is
        dropped and the stored private file is deleted.  OCR source-crop
        visuals are stored outside this endpoint and are never touched here.
        """
        session = _session_or_none(session_id)
        if session is None:
            return Response(
                {'detail': 'جلسه آمادگی آزمون یافت نشد.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if session.teacher_id != request.user.id:
            return Response(
                {'detail': 'شما مالک این جلسه نیستید.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        visual_id = str(
            request.query_params.get('visual_id')
            or request.data.get('visual_id')
            or ''
        ).strip()
        if not visual_id:
            return Response(
                {'detail': 'شناسه تصویر (visual_id) ارسال نشده است.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            removed = remove_teacher_visual(session, visual_id=visual_id)
        except TeacherVisualError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if not removed:
            return Response(
                {'detail': 'تصویر افزوده‌شده یافت نشد.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class TeacherExamPrepVisualContentView(APIView):
    """Stream a teacher-uploaded visual to its owner or an invited student."""

    permission_classes = [IsAuthenticated]

    def get(self, request, session_id: int, storage_name: str):
        session = _session_or_none(session_id)
        if session is None:
            return Response(
                {'detail': 'تصویر یافت نشد.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        user = request.user
        is_teacher_owner = session.teacher_id == user.id
        is_student = False
        if not is_teacher_owner and user.role == User.Role.STUDENT:
            phone = normalize_phone(getattr(user, 'phone', None))
            is_student = bool(
                session.is_published
                and phone
                and session.invites.filter(phone=phone).exists()
            )
        if not is_teacher_owner and not is_student:
            # Keep private visuals indistinguishable from absent ones.
            return Response(
                {'detail': 'تصویر یافت نشد.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        reference = find_teacher_visual_reference(session, storage_name)
        if reference is None:
            return Response(
                {'detail': 'تصویر یافت نشد.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        _question, visual = reference
        visual_id = str(visual.get('id') or '')
        if not visual_id.startswith(TEACHER_VISUAL_ID_PREFIX):
            return Response(
                {'detail': 'تصویر یافت نشد.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Source solutions are shown to an invited student only after that
        # student's own attempt has been finalized (same gate as the inline
        # visual endpoint).
        if is_student and visual.get('role') == 'solution':
            finalized = StudentExamPrepAttempt.objects.filter(
                session_id=session.id,
                student_id=user.id,
                finalized=True,
            ).exists()
            if not finalized:
                return Response(
                    {'detail': 'تصویر یافت نشد.'},
                    status=status.HTTP_404_NOT_FOUND,
                )

        content_type = teacher_visual_content_type(storage_name)
        if content_type is None:
            return Response(
                {'detail': 'تصویر یافت نشد.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        from django.core.files.storage import storages
        from django.http import FileResponse

        try:
            stream = storages['answer_sources'].open(
                teacher_visual_storage_path(session.id, storage_name),
                'rb',
            )
        except Exception:
            return Response(
                {'detail': 'فایل تصویر در دسترس نیست.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        response = FileResponse(stream, content_type=content_type)
        response['Content-Disposition'] = 'inline'
        response['Cache-Control'] = 'private, no-store, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        response['Vary'] = 'Authorization, Cookie'
        response['X-Content-Type-Options'] = 'nosniff'
        response['Referrer-Policy'] = 'no-referrer'
        return response


__all__ = [
    'TeacherExamPrepVisualUploadView',
    'TeacherExamPrepVisualContentView',
]
