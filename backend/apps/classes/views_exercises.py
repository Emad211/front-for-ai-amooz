"""Exercise Hub — teacher API (create/extract/edit/publish/delete).

Kept in a dedicated module so the 195 KB ``views.py`` never grows for this
feature. All endpoints are owner-scoped: a teacher only ever sees/mutates
exercises of their own class sessions (``session__teacher=request.user``); a
non-owner gets 404 (fail-closed), a non-teacher 403, anonymous 401.

Design + permission matrix: docs/features/exercise-hub.md · ADR-0004.
"""
from __future__ import annotations

import os
import logging
import uuid
from io import BytesIO
from decimal import Decimal, InvalidOperation

from django.core.files.storage import default_storage
from django.db import IntegrityError, transaction
from django.utils import timezone
from pypdf import PdfReader
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.celery import app as celery_app
from .models import (
    ClassCreationSession,
    ClassExercise,
    ClassExerciseAsset,
    ClassExerciseQuestion,
    ClassExerciseSection,
    StudentExerciseAttempt,
    StudentExerciseSubmission,
)
from .permissions import IsStudentUser, IsTeacherUser
from .services.exercise_ingest import (
    build_reference_ingest_preview,
    compact_existing_questions,
    ingest_reference_answers_markdown,
    ocr_uploaded_files_to_markdown,
)
from .services.exercise_workflow import (
    build_workflow_state,
    normalize_source_config,
    update_workflow_state,
)
from .services.file_validation import is_probably_pdf, is_real_image, uploaded_content_type, uploaded_name
from .services.exercise_grading import build_question_snapshot, questions_from_snapshot
from .serializers_exercises import (
    ExerciseCreateSerializer,
    ExerciseDetailSerializer,
    ExerciseListSerializer,
    ExerciseUpdateSerializer,
    QuestionWriteSerializer,
    SectionUpdateSerializer,
)
from .tasks import extract_exercise_content

_NOT_FOUND = {'detail': 'تمرین پیدا نشد.'}
logger = logging.getLogger(__name__)


def _int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _decimal_env(name: str, default: str) -> Decimal:
    try:
        return Decimal(os.getenv(name, default))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


_MAX_SOURCE_FILES = _int_env('EXERCISE_MAX_SOURCE_FILES', 10)
_MAX_SOURCE_FILE_BYTES = _int_env('EXERCISE_MAX_SOURCE_FILE_BYTES', 20 * 1024 * 1024)
_MAX_REFERENCE_FILES = _int_env('EXERCISE_REFERENCE_MAX_FILES', 5)
_MAX_REFERENCE_FILE_BYTES = _int_env('EXERCISE_REFERENCE_MAX_FILE_BYTES', 8 * 1024 * 1024)
_MAX_REFERENCE_SOURCE_CHARS = _int_env('EXERCISE_REFERENCE_MAX_SOURCE_CHARS', 50_000)
_MAX_REFERENCE_PDF_PAGES = _int_env('EXERCISE_REFERENCE_MAX_PDF_PAGES', 20)
_MAX_REFERENCE_OCR_UNITS = _int_env('EXERCISE_REFERENCE_MAX_OCR_UNITS', 20)
_MAX_REFERENCE_APPLY_ITEMS = _int_env('EXERCISE_REFERENCE_MAX_APPLY_ITEMS', 100)
_MAX_REFERENCE_MARKDOWN_CHARS = _int_env('EXERCISE_REFERENCE_MAX_MARKDOWN_CHARS', 20_000)
_MAX_REFERENCE_OPTIONS = _int_env('EXERCISE_REFERENCE_MAX_OPTIONS', 12)
_MAX_REFERENCE_OPTION_CHARS = _int_env('EXERCISE_REFERENCE_MAX_OPTION_CHARS', 2_000)
_MAX_REFERENCE_POINTS = _decimal_env('EXERCISE_REFERENCE_MAX_POINTS', '1000')
_REFERENCE_MODE_HINTS = {'auto', 'full_qa', 'single_qa', 'numbered_answers', 'answer_only'}
_REFERENCE_EDITABLE_STATUSES = {
    ClassExercise.Status.DRAFT,
    ClassExercise.Status.EXTRACTED,
    ClassExercise.Status.FAILED,
}


def _owned_exercise(request, exercise_id):
    return ClassExercise.objects.filter(
        id=exercise_id, session__teacher=request.user,
    ).first()


def _read_uploaded_for_validation(uploaded, max_bytes: int):
    size = int(getattr(uploaded, 'size', 0) or 0)
    if size and size > max_bytes:
        return None, Response(
            {'detail': 'حجم فایل بیش از حد مجاز است.'},
            status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )
    data = uploaded.read()
    try:
        uploaded.seek(0)
    except Exception:
        pass
    if not data:
        return None, Response({'detail': 'فایل ارسالی خالی است.'}, status=status.HTTP_400_BAD_REQUEST)
    if len(data) > max_bytes:
        return None, Response(
            {'detail': 'حجم فایل بیش از حد مجاز است.'},
            status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )
    return data, None


def _validate_exercise_source_file(uploaded, *, max_bytes: int):
    data, error = _read_uploaded_for_validation(uploaded, max_bytes)
    if error is not None:
        return None, error
    ct = uploaded_content_type(uploaded)
    name = uploaded_name(uploaded)
    looks_pdf = 'pdf' in ct or name.endswith('.pdf')
    looks_image = ct.startswith('image/') or name.endswith(('.jpg', '.jpeg', '.png', '.webp'))
    if looks_pdf and is_probably_pdf(data):
        return ClassExerciseAsset.Kind.PDF, None
    if looks_image and is_real_image(data):
        return ClassExerciseAsset.Kind.IMAGE, None
    return None, Response(
        {'detail': 'فقط PDF یا تصویر معتبر مجاز است.'},
        status=status.HTTP_400_BAD_REQUEST,
    )


def _uploaded_sources_by_key(request) -> dict[str, object]:
    out: dict[str, object] = {}
    for field_name, uploaded in request.FILES.items():
        if not field_name.startswith('file_'):
            continue
        key = field_name.removeprefix('file_').strip()
        if key:
            out[key] = uploaded
    return out


def _reference_ocr_unit_count(uploaded, kind: str) -> int:
    if kind == ClassExerciseAsset.Kind.IMAGE:
        return 1
    data = uploaded.read()
    try:
        uploaded.seek(0)
    except Exception:
        pass
    try:
        return max(1, len(PdfReader(BytesIO(data)).pages))
    except Exception as exc:
        raise ValueError('invalid pdf') from exc


def _reference_editable_response(exercise):
    if exercise.status == ClassExercise.Status.PUBLISHED:
        return Response(
            {'detail': 'پس از انتشار، تغییر پاسخ مرجع نیازمند جریان بازنمره‌دهی است.'},
            status=status.HTTP_409_CONFLICT,
        )
    if exercise.status == ClassExercise.Status.EXTRACTING:
        return Response(
            {'detail': 'تا پایان استخراج تمرین صبر کنید.'},
            status=status.HTTP_409_CONFLICT,
        )
    if exercise.status not in _REFERENCE_EDITABLE_STATUSES:
        return Response(
            {'detail': 'در وضعیت فعلی امکان ورود پاسخ مرجع وجود ندارد.'},
            status=status.HTTP_409_CONFLICT,
        )
    return None


class ExerciseListCreateView(APIView):
    """List a session's exercises / create a new one (with optional assets)."""

    permission_classes = [IsAuthenticated, IsTeacherUser]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request, session_id: int):
        session = ClassCreationSession.objects.filter(
            id=session_id, teacher=request.user,
        ).first()
        if session is None:
            return Response({'detail': 'جلسه پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        qs = ClassExercise.objects.filter(session=session).order_by('-created_at')
        return Response(ExerciseListSerializer(qs, many=True).data)

    def post(self, request, session_id: int):
        session = ClassCreationSession.objects.filter(
            id=session_id, teacher=request.user,
        ).first()
        if session is None:
            return Response({'detail': 'جلسه پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ExerciseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        source_configs = serializer.validated_data['sources']
        uploaded_by_key = _uploaded_sources_by_key(request)
        if len(source_configs) > _MAX_SOURCE_FILES:
            return Response(
                {'detail': 'تعداد فایل‌های تمرین بیش از حد مجاز است.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(uploaded_by_key) != len(source_configs):
            return Response(
                {'detail': 'برای هر منبع باید فایل متناظر بارگذاری شود.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        validated_assets = []
        for source in source_configs:
            uploaded = uploaded_by_key.get(source['clientFileKey'])
            if uploaded is None:
                return Response(
                    {'detail': f"فایل منبع «{source['clientFileKey']}» پیدا نشد."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            kind, error = _validate_exercise_source_file(
                uploaded, max_bytes=_MAX_SOURCE_FILE_BYTES,
            )
            if error is not None:
                return error
            validated_assets.append((source, kind, uploaded))

        intake_sources: list[dict] = []
        exercise = ClassExercise.objects.create(
            session=session,
            title=serializer.validated_data['title'],
            description=serializer.validated_data.get('teacher_note', ''),
            deadline=serializer.validated_data['deadline'],
            allow_late=serializer.validated_data.get('allow_late', False),
            assistant_enabled=serializer.validated_data.get('assistant_enabled', True),
            workflow_state=build_workflow_state('queued'),
        )
        for idx, (source, kind, uploaded) in enumerate(validated_assets):
            ClassExerciseAsset.objects.create(
                exercise=exercise, kind=kind, file=uploaded, order=idx,
            )
            intake_sources.append(
                normalize_source_config(
                    source,
                    asset_order=idx,
                    asset_name=uploaded_name(uploaded),
                    asset_kind=kind,
                )
            )
        exercise.intake_config = {
            'v': 1,
            'mode': 'single_step',
            'autoExtract': True,
            'noDeadline': bool(serializer.validated_data['no_deadline']),
            'deadline': exercise.deadline.isoformat() if exercise.deadline else None,
            'allowLate': exercise.allow_late,
            'assistantEnabled': exercise.assistant_enabled,
            'teacherNote': exercise.description,
            'sources': intake_sources,
        }
        exercise.save(update_fields=['intake_config', 'updated_at'])
        transaction.on_commit(lambda: extract_exercise_content.delay(exercise.id))
        return Response(
            ExerciseDetailSerializer(exercise).data, status=status.HTTP_201_CREATED,
        )


class ExerciseDetailView(APIView):
    """Get / update mutable exercise settings / delete."""

    permission_classes = [IsAuthenticated, IsTeacherUser]

    def get(self, request, exercise_id: int):
        exercise = _owned_exercise(request, exercise_id)
        if exercise is None:
            return Response(_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        return Response(ExerciseDetailSerializer(exercise).data)

    def patch(self, request, exercise_id: int):
        exercise = _owned_exercise(request, exercise_id)
        if exercise is None:
            return Response(_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        serializer = ExerciseUpdateSerializer(
            data=request.data,
            partial=True,
            context={'exercise': exercise},
        )
        serializer.is_valid(raise_exception=True)
        fields: list[str] = []
        for key in ('title', 'deadline', 'allow_late', 'assistant_enabled'):
            if key in serializer.validated_data:
                setattr(exercise, key, serializer.validated_data[key])
                fields.append(key)
        if fields:
            fields.append('updated_at')
            exercise.save(update_fields=fields)
        return Response(ExerciseDetailSerializer(exercise).data)

    def delete(self, request, exercise_id: int):
        exercise = _owned_exercise(request, exercise_id)
        if exercise is None:
            return Response(_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        # GC storage objects (CASCADE drops rows, not S3/MinIO blobs — E1 db-gate).
        for asset in exercise.assets.all():
            try:
                asset.file.delete(save=False)
            except Exception:
                pass
        exercise.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ExerciseExtractView(APIView):
    """Kick off async structure extraction (E3 task on the pipeline queue)."""

    permission_classes = [IsAuthenticated, IsTeacherUser]

    def post(self, request, exercise_id: int):
        exercise = _owned_exercise(request, exercise_id)
        if exercise is None:
            return Response(_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        if exercise.status == ClassExercise.Status.EXTRACTING:
            return Response(
                {'detail': 'استخراج این تمرین در حال انجام است.'},
                status=status.HTTP_409_CONFLICT,
            )
        if exercise.status == ClassExercise.Status.PUBLISHED:
            return Response(
                {'detail': 'برای تمرین منتشرشده استخراج دوباره مجاز نیست.'},
                status=status.HTTP_409_CONFLICT,
            )
        update_workflow_state(
            exercise,
            'queued',
            message='استخراج دوبارهٔ تمرین در صف قرار گرفت.',
            warnings=[],
            ready_for_review=False,
        )
        transaction.on_commit(lambda: extract_exercise_content.delay(exercise.id))
        return Response(
            {'detail': 'استخراج دوبارهٔ تمرین آغاز شد.', 'status': ClassExercise.Status.EXTRACTING},
            status=status.HTTP_202_ACCEPTED,
        )


def _cancel_exercise_extraction(exercise: ClassExercise) -> None:
    """Stop a running exercise extraction as safely as possible.

    The DB transition happens first (cooperative stop), then Celery revoke is
    attempted as a best-effort hard stop for an in-flight OCR/LLM call.
    """
    exercise.cancel_requested = True
    exercise.status = ClassExercise.Status.CANCELLED
    exercise.workflow_state = build_workflow_state(
        'cancelled',
        message='استخراج تمرین توسط شما متوقف شد.',
        ready_for_review=False,
    )
    exercise.save(update_fields=['cancel_requested', 'status', 'workflow_state', 'updated_at'])

    task_id = (exercise.extract_task_id or '').strip()
    if task_id:
        try:
            celery_app.control.revoke(task_id, terminate=True, signal='SIGTERM')
        except Exception:
            logger.warning(
                'Failed to revoke exercise extraction task %s for exercise %s '
                '(cooperative cancel flag still set).',
                task_id,
                exercise.id,
                exc_info=True,
            )


class ExerciseCancelView(APIView):
    """Cancel a running exercise extraction (teacher, owner-only)."""

    permission_classes = [IsAuthenticated, IsTeacherUser]

    def post(self, request, exercise_id: int):
        exercise = _owned_exercise(request, exercise_id)
        if exercise is None:
            return Response(_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        raw_workflow = exercise.workflow_state if isinstance(exercise.workflow_state, dict) else {}
        workflow_stage = str(raw_workflow.get('stage') or '')
        active_stages = {
            'queued',
            'reading_sources',
            'ocr_and_transcription',
            'extracting_questions',
            'matching_reference_answers',
            'building_review_draft',
        }
        if exercise.status != ClassExercise.Status.EXTRACTING and workflow_stage not in active_stages:
            return Response(
                {'detail': 'استخراج فعالی برای لغو وجود ندارد.'},
                status=status.HTTP_409_CONFLICT,
            )

        _cancel_exercise_extraction(exercise)
        return Response(ExerciseDetailSerializer(exercise).data)


class ExercisePublishView(APIView):
    """Publish an extracted exercise after validating reference answers + points."""

    permission_classes = [IsAuthenticated, IsTeacherUser]

    def post(self, request, exercise_id: int):
        exercise = _owned_exercise(request, exercise_id)
        if exercise is None:
            return Response(_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        if exercise.status not in (
            ClassExercise.Status.EXTRACTED, ClassExercise.Status.PUBLISHED,
        ):
            return Response(
                {'detail': 'ابتدا باید سوال‌های تمرین استخراج شوند.'},
                status=status.HTTP_409_CONFLICT,
            )
        if not exercise.session.is_published:
            return Response(
                {'detail': 'ابتدا خود کلاس را منتشر کنید؛ سپس تمرین را منتشر کنید.'},
                status=status.HTTP_409_CONFLICT,
            )
        questions = ClassExerciseQuestion.objects.filter(section__exercise=exercise)
        if not questions.exists():
            return Response(
                {'detail': 'این تمرین هیچ سوالی ندارد.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        incomplete = [
            q.id for q in questions
            if not (q.reference_answer_markdown or '').strip()
            or q.max_points is None or q.max_points <= 0
        ]
        if incomplete:
            return Response(
                {
                    'detail': 'برای انتشار، هر سوال باید پاسخ مرجع و بارم داشته باشد.',
                    'incompleteQuestionIds': incomplete,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        exercise.status = ClassExercise.Status.PUBLISHED
        exercise.save(update_fields=['status', 'updated_at'])
        return Response(ExerciseDetailSerializer(exercise).data)


class ExerciseSectionDetailView(APIView):
    """Deprecated compatibility endpoint for editing a legacy section title."""

    permission_classes = [IsAuthenticated, IsTeacherUser]

    def patch(self, request, section_id: int):
        section = ClassExerciseSection.objects.filter(
            id=section_id, exercise__session__teacher=request.user,
        ).first()
        if section is None:
            return Response({'detail': 'بخش پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = SectionUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        fields: list[str] = []
        for key in ('title',):
            if key in serializer.validated_data:
                setattr(section, key, serializer.validated_data[key])
                fields.append(key)
        if fields:
            section.save(update_fields=fields)
        return Response({'id': section.id, 'assistantEnabled': section.assistant_enabled,
                         'title': section.title})


class ExerciseQuestionListCreateView(APIView):
    """Add a question to an exercise's private compatibility section."""

    permission_classes = [IsAuthenticated, IsTeacherUser]

    def post(self, request, exercise_id: int):
        exercise = _owned_exercise(request, exercise_id)
        if exercise is None:
            return Response(_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        serializer = QuestionWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        section_id = serializer.validated_data.get('section_id')
        section = None
        if section_id is not None:
            section = ClassExerciseSection.objects.filter(
                id=section_id, exercise=exercise,
            ).first()
            if section is None:
                return Response(
                    {'detail': 'بخش داخلی تمرین پیدا نشد.'}, status=status.HTTP_400_BAD_REQUEST,
                )
        if section is None:
            section = exercise.sections.order_by('order', 'id').first()
        if section is None:
            section = ClassExerciseSection.objects.create(
                exercise=exercise,
                order=0,
                title='',
                assistant_enabled=exercise.assistant_enabled,
            )
        next_order = section.questions.count()
        q = ClassExerciseQuestion.objects.create(
            section=section, order=next_order,
            question_markdown=serializer.validated_data.get('question_markdown', ''),
            question_type=serializer.validated_data.get(
                'question_type', ClassExerciseQuestion.QuestionType.DESCRIPTIVE),
            options=serializer.validated_data.get('options', []),
            reference_answer_markdown=serializer.validated_data.get('reference_answer_markdown', ''),
            max_points=serializer.validated_data.get('max_points', 1),
            grading_notes=serializer.validated_data.get('grading_notes', ''),
        )
        return Response({'id': q.id}, status=status.HTTP_201_CREATED)


class ExerciseQuestionDetailView(APIView):
    """Edit / delete a question (reference answer, points, text, type, options)."""

    permission_classes = [IsAuthenticated, IsTeacherUser]

    def _owned_question(self, request, question_id):
        return ClassExerciseQuestion.objects.filter(
            id=question_id, section__exercise__session__teacher=request.user,
        ).first()

    def patch(self, request, question_id: int):
        q = self._owned_question(request, question_id)
        if q is None:
            return Response({'detail': 'سوال پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = QuestionWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        fields: list[str] = []
        mapping = {
            'question_markdown': 'question_markdown',
            'question_type': 'question_type',
            'options': 'options',
            'reference_answer_markdown': 'reference_answer_markdown',
            'max_points': 'max_points',
            'grading_notes': 'grading_notes',
        }
        for key, attr in mapping.items():
            if key in serializer.validated_data:
                setattr(q, attr, serializer.validated_data[key])
                fields.append(attr)
        if fields:
            q.save(update_fields=fields)
        return Response({'id': q.id})

    def delete(self, request, question_id: int):
        q = self._owned_question(request, question_id)
        if q is None:
            return Response({'detail': 'سوال پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        q.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ExerciseReferenceIngestPreviewView(APIView):
    """Preview teacher-provided reference answers/questions before applying.

    This endpoint intentionally writes nothing to the database. It OCRs the
    source (text/PDF/images), asks the structured LLM for candidates, then maps
    them conservatively onto existing questions for teacher review.
    """

    permission_classes = [IsAuthenticated, IsTeacherUser]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, exercise_id: int):
        exercise = _owned_exercise(request, exercise_id)
        if exercise is None:
            return Response(_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        gate = _reference_editable_response(exercise)
        if gate is not None:
            return gate

        files = request.FILES.getlist('files')
        if len(files) > _MAX_REFERENCE_FILES:
            return Response(
                {'detail': 'تعداد فایل‌های پاسخ مرجع بیش از حد مجاز است.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        pdf_pages = 0
        ocr_units = 0
        for uploaded in files:
            kind, error = _validate_exercise_source_file(
                uploaded, max_bytes=_MAX_REFERENCE_FILE_BYTES,
            )
            if error is not None:
                return error
            try:
                units = _reference_ocr_unit_count(uploaded, kind)
            except ValueError:
                return Response(
                    {'detail': 'فایل PDF ارسالی قابل خواندن نیست.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            ocr_units += units
            if kind == ClassExerciseAsset.Kind.PDF:
                pdf_pages += units
        if pdf_pages > _MAX_REFERENCE_PDF_PAGES:
            return Response(
                {'detail': 'تعداد صفحات PDF پاسخ مرجع بیش از حد مجاز است.'},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        if ocr_units > _MAX_REFERENCE_OCR_UNITS:
            return Response(
                {'detail': 'حجم پردازش فایل‌های پاسخ مرجع بیش از حد مجاز است.'},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        source_text = (
            request.data.get('source_text')
            or request.data.get('sourceText')
            or ''
        )
        source_text = str(source_text or '')
        if len(source_text) > _MAX_REFERENCE_SOURCE_CHARS:
            return Response(
                {'detail': 'متن پاسخ مرجع بیش از حد مجاز است.'},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        mode_hint = (
            request.data.get('mode_hint')
            or request.data.get('modeHint')
            or 'auto'
        )
        mode_hint = str(mode_hint or 'auto').strip()
        if mode_hint not in _REFERENCE_MODE_HINTS:
            return Response({'detail': 'نوع ورودی پاسخ مرجع نامعتبر است.'}, status=status.HTTP_400_BAD_REQUEST)
        target_raw = request.data.get('target_question_id') or request.data.get('targetQuestionId')
        target_question_id = None
        if target_raw not in (None, '', 'all'):
            try:
                target_question_id = int(target_raw)
            except (TypeError, ValueError):
                return Response({'detail': 'سوال هدف نامعتبر است.'}, status=status.HTTP_400_BAD_REQUEST)
            exists = ClassExerciseQuestion.objects.filter(
                id=target_question_id, section__exercise=exercise,
            ).exists()
            if not exists:
                return Response({'detail': 'سوال هدف پیدا نشد.'}, status=status.HTTP_400_BAD_REQUEST)

        if not str(source_text).strip() and not files:
            return Response(
                {'detail': 'متن یا فایل پاسخ مرجع را وارد کنید.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            ocr_markdown = ocr_uploaded_files_to_markdown(files) if files else ''
        except ValueError:
            return Response(
                {'detail': 'فایل ارسالی قابل خواندن نیست.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            return Response(
                {'detail': 'استخراج فایل کامل نشد. دوباره تلاش کنید یا متن را دستی وارد کنید.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        source_markdown = "\n\n---\n\n".join(
            part.strip() for part in [source_text, ocr_markdown] if part and part.strip()
        )
        if not source_markdown.strip():
            return Response(
                {'detail': 'متنی از فایل یا ورودی شما استخراج نشد.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(source_markdown) > _MAX_REFERENCE_SOURCE_CHARS:
            return Response(
                {'detail': 'متن استخراج‌شدهٔ پاسخ مرجع بیش از حد مجاز است.'},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        existing = compact_existing_questions(
            exercise,
            question_ids=[target_question_id] if target_question_id is not None else None,
        )
        try:
            extracted, _provider, _model = ingest_reference_answers_markdown(
                source_markdown=source_markdown,
                existing_questions=existing,
                mode_hint=mode_hint,
            )
        except RuntimeError:
            return Response(
                {'detail': 'استخراج پاسخ مرجع کامل نشد. دوباره تلاش کنید یا دستی وارد کنید.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        preview = build_reference_ingest_preview(
            exercise=exercise,
            extracted=extracted,
            target_question_id=target_question_id,
        )
        return Response(preview)


class ExerciseReferenceIngestApplyView(APIView):
    """Apply teacher-reviewed reference-answer patches to existing questions."""

    permission_classes = [IsAuthenticated, IsTeacherUser]

    def post(self, request, exercise_id: int):
        raw_items = request.data.get('items') if isinstance(request.data, dict) else None
        if not isinstance(raw_items, list) or not raw_items:
            return Response({'detail': 'هیچ موردی برای اعمال ارسال نشده است.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if len(raw_items) > _MAX_REFERENCE_APPLY_ITEMS:
            return Response(
                {'detail': 'تعداد موارد ارسالی بیش از حد مجاز است.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            exercise = ClassExercise.objects.select_for_update().filter(
                id=exercise_id, session__teacher=request.user,
            ).first()
            if exercise is None:
                return Response(_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
            gate = _reference_editable_response(exercise)
            if gate is not None:
                return gate
            questions = {
                q.id: q for q in ClassExerciseQuestion.objects.select_for_update().filter(
                    section__exercise=exercise,
                )
            }
            applied: list[int] = []
            skipped: list[dict] = []
            errors: list[dict] = []

            for idx, item in enumerate(raw_items, start=1):
                if not isinstance(item, dict):
                    errors.append({'index': idx, 'detail': 'مورد ارسالی نامعتبر است.'})
                    continue
                qid_raw = item.get('targetQuestionId') or item.get('target_question_id')
                try:
                    qid = int(qid_raw)
                except (TypeError, ValueError):
                    errors.append({'index': idx, 'detail': 'سوال هدف نامعتبر است.'})
                    continue
                q = questions.get(qid)
                if q is None:
                    errors.append({'index': idx, 'detail': 'سوال هدف پیدا نشد.'})
                    continue

                replace_existing = bool(
                    item.get('replaceExisting') or item.get('replace_existing')
                )
                replace_question_text = bool(
                    item.get('replaceQuestionText') or item.get('replace_question_text')
                )
                fields: list[str] = []
                if (q.reference_answer_markdown or '').strip() and not replace_existing:
                    skipped.append({
                        'targetQuestionId': q.id,
                        'reason': 'existing_reference',
                    })
                    continue

                ref = str(
                    item.get('referenceAnswerMarkdown')
                    or item.get('reference_answer_markdown')
                    or ''
                ).strip()
                if len(ref) > _MAX_REFERENCE_MARKDOWN_CHARS:
                    errors.append({'index': idx, 'detail': 'پاسخ مرجع بیش از حد طولانی است.'})
                    continue
                if ref:
                    q.reference_answer_markdown = ref
                    fields.append('reference_answer_markdown')

                if item.get('maxPoints') is not None or item.get('max_points') is not None:
                    raw_points = item.get('maxPoints') if item.get('maxPoints') is not None else item.get('max_points')
                    try:
                        points = Decimal(str(raw_points))
                    except (InvalidOperation, TypeError, ValueError):
                        errors.append({'index': idx, 'detail': 'بارم نامعتبر است.'})
                        continue
                    if points <= 0:
                        errors.append({'index': idx, 'detail': 'بارم باید بزرگ‌تر از صفر باشد.'})
                        continue
                    if points > _MAX_REFERENCE_POINTS:
                        errors.append({'index': idx, 'detail': 'بارم بیش از حد مجاز است.'})
                        continue
                    q.max_points = points
                    fields.append('max_points')

                question_text = str(
                    item.get('questionMarkdown') or item.get('question_markdown') or ''
                ).strip()
                if len(question_text) > _MAX_REFERENCE_MARKDOWN_CHARS:
                    errors.append({'index': idx, 'detail': 'متن سوال بیش از حد طولانی است.'})
                    continue
                if question_text and replace_question_text:
                    q.question_markdown = question_text
                    fields.append('question_markdown')

                question_type = item.get('questionType') or item.get('question_type')
                if question_type in dict(ClassExerciseQuestion.QuestionType.choices):
                    q.question_type = question_type
                    fields.append('question_type')
                options = item.get('options')
                if isinstance(options, list):
                    if len(options) > _MAX_REFERENCE_OPTIONS:
                        errors.append({'index': idx, 'detail': 'تعداد گزینه‌ها بیش از حد مجاز است.'})
                        continue
                    if any(len(str(opt)) > _MAX_REFERENCE_OPTION_CHARS for opt in options):
                        errors.append({'index': idx, 'detail': 'متن گزینه بیش از حد طولانی است.'})
                        continue
                    q.options = options
                    fields.append('options')

                if fields:
                    q.save(update_fields=sorted(set(fields)))
                    applied.append(q.id)
                elif not any(s.get('targetQuestionId') == q.id for s in skipped):
                    skipped.append({'targetQuestionId': q.id, 'reason': 'empty_patch'})

            if errors:
                transaction.set_rollback(True)
                return Response(
                    {'detail': 'برخی موارد قابل اعمال نیستند.', 'errors': errors},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        return Response({
            'appliedCount': len(set(applied)),
            'updatedQuestionIds': sorted(set(applied)),
            'skipped': skipped,
        })


# ═══════════════════════════════════════════════════════════════════════════
# Student API — phone-scoped. A student only ever reaches a PUBLISHED exercise
# of a published class they were invited to (via phone). No phone -> 400.
# Reference answers are withheld until the reveal condition holds (deadline
# passed, or no-deadline + own GRADED) — a single helper decides that.
# ═══════════════════════════════════════════════════════════════════════════

_NO_PHONE = {'detail': 'شماره موبایل برای حساب کاربری ثبت نشده است.'}
_EX_NOT_FOUND = {'detail': 'تمرین پیدا نشد.'}

_MAX_IMAGE_BYTES = int(os.getenv('EXERCISE_MAX_IMAGE_BYTES', str(8 * 1024 * 1024)))
_MAX_IMAGES_PER_QUESTION = _int_env('EXERCISE_MAX_IMAGES_PER_QUESTION', 3)


def _student_phone(request):
    return (getattr(request.user, 'phone', None) or '').strip()


def _answer_image_prefix(exercise_id: int, student_id: int, question_id: int) -> str:
    return f'exercises/answers/{exercise_id}/{student_id}/{question_id}_'


def _owned_answer_images(answers: dict, exercise_id: int, student_id: int, question_id: int) -> list[str]:
    entry = answers.get(str(question_id)) if isinstance(answers, dict) else None
    if not isinstance(entry, dict):
        return []
    images = entry.get('images')
    if not isinstance(images, list):
        return []
    prefix = _answer_image_prefix(exercise_id, student_id, question_id)
    return [
        path for path in images
        if isinstance(path, str) and path.startswith(prefix)
    ][:_MAX_IMAGES_PER_QUESTION]


def _sanitize_student_answers(exercise, student, incoming_answers, existing_answers=None) -> dict:
    """Keep answer text from JSON; keep images only if the server recorded them."""
    incoming = incoming_answers if isinstance(incoming_answers, dict) else {}
    existing = existing_answers if isinstance(existing_answers, dict) else {}
    question_ids = set(
        ClassExerciseQuestion.objects.filter(section__exercise=exercise)
        .values_list('id', flat=True)
    )
    sanitized: dict[str, dict] = {}
    for key, value in incoming.items():
        try:
            qid = int(key)
        except (TypeError, ValueError):
            continue
        if qid not in question_ids:
            continue
        entry: dict = {}
        if isinstance(value, dict) and 'text' in value:
            entry['text'] = str(value.get('text') or '')
        elif isinstance(value, str):
            entry['text'] = value
        images = _owned_answer_images(existing, exercise.id, student.id, qid)
        if images:
            entry['images'] = images
        if entry:
            sanitized[str(qid)] = entry

    # Preserve photo-only answers uploaded through the server endpoint even if
    # the final submit body omits that question.
    for qid in question_ids:
        key = str(qid)
        if key in sanitized:
            continue
        images = _owned_answer_images(existing, exercise.id, student.id, qid)
        if images:
            sanitized[key] = {'images': images}
    return sanitized


def _published_exercise_for_student(phone, session_id, exercise_id):
    return (
        ClassExercise.objects.filter(
            id=exercise_id,
            session_id=session_id,
            status=ClassExercise.Status.PUBLISHED,
            session__is_published=True,
            session__invites__phone=phone,
        )
        .prefetch_related('sections__questions')
        .first()
    )


def _reveal_open(exercise, submission) -> bool:
    """THE single reveal rule: reference answers may be shown only when the
    deadline has passed, or (no deadline) when the student's own submission is
    graded. Never before — an early submitter must not see the answers while
    classmates are still within the deadline (owner decision 2026-07-05)."""
    if exercise.deadline_passed():
        return True
    if exercise.deadline is None and submission is not None:
        return submission.status == StudentExerciseSubmission.Status.GRADED
    return False


# Keys that must never reach a student before reveal, even if a future grader
# (E6) accidentally persists them into result['per_question']. Defense-in-depth
# so the reveal gate holds regardless of what the grading payload contains
# (security-auditor E5 Low-1).
_REVEAL_ONLY_RESULT_KEYS = {
    'reference_answer', 'reference_answer_markdown', 'grading_notes',
    'feedback', 'missing_points',
}

_SAFE_PRE_REVEAL_FEEDBACK = {
    'correct': 'پاسخ شما صحیح ارزیابی شد.',
    'partially_correct': 'پاسخ شما بخشی از معیارهای سؤال را پوشش می‌دهد.',
    'incorrect': 'پاسخ شما نیاز به بازبینی دارد.',
    'unanswered': 'برای این سؤال پاسخی ثبت نشده است.',
}


def _result_for_student(result, *, reveal: bool):
    """Return ``result`` with any reference-answer-ish keys stripped from each
    ``per_question`` entry when the reveal condition is not yet open."""
    if reveal or not isinstance(result, dict):
        return result
    per_q = result.get('per_question')
    if not isinstance(per_q, list):
        return result
    cleaned = []
    for pq in per_q:
        if not isinstance(pq, dict):
            cleaned.append(pq)
            continue
        item = {k: v for k, v in pq.items() if k not in _REVEAL_ONLY_RESULT_KEYS}
        item['feedback'] = _SAFE_PRE_REVEAL_FEEDBACK.get(
            str(pq.get('label')),
            'نتیجه این سؤال ثبت شد.',
        )
        cleaned.append(item)
    return {**result, 'per_question': cleaned}


def _attempt_summary(attempt) -> dict:
    return {
        'attemptId': attempt.id,
        'attemptNumber': attempt.attempt_number,
        'status': attempt.status,
        'scorePoints': str(attempt.score_points) if attempt.score_points is not None else None,
        'maxPoints': str(attempt.max_points) if attempt.max_points is not None else None,
        'submittedAt': attempt.submitted_at.isoformat() if attempt.submitted_at else None,
        'gradedAt': attempt.graded_at.isoformat() if attempt.graded_at else None,
    }


def _teacher_attempt_result(attempt):
    result = attempt.result if isinstance(attempt.result, dict) else {}
    question_meta = (
        attempt.grader_metadata.get('questions', {})
        if isinstance(attempt.grader_metadata, dict) else {}
    )
    rows = result.get('per_question')
    if not isinstance(rows, list):
        return result
    return {
        **result,
        'per_question': [
            {
                **row,
                'grading_source': (
                    'reused'
                    if isinstance(question_meta.get(str(row.get('question_id'))), dict)
                    and question_meta[str(row.get('question_id'))].get('reused')
                    else 'regraded'
                ),
            }
            if isinstance(row, dict) else row
            for row in rows
        ],
    }


def _requested_attempt(request, submission):
    attempts = list(submission.attempts.order_by('attempt_number'))
    if not attempts:
        return None, attempts
    raw_id = request.query_params.get('attemptId')
    if raw_id is None:
        return attempts[-1], attempts
    try:
        attempt_id = int(raw_id)
    except (TypeError, ValueError):
        return False, attempts
    return next((attempt for attempt in attempts if attempt.id == attempt_id), False), attempts


def _q_for_solving(q) -> dict:
    """Solving-view question shape — NEVER contains the reference answer."""
    return {
        'id': q.id, 'order': q.order,
        'questionMarkdown': q.question_markdown,
        'questionType': q.question_type,
        'options': q.options,
        'maxPoints': str(q.max_points),
    }


def _q_with_answer(q) -> dict:
    """Reveal-view question shape — adds the reference answer. Only ever used
    once ``_reveal_open`` returned True."""
    d = _q_for_solving(q)
    d['referenceAnswerMarkdown'] = q.reference_answer_markdown
    return d


def _serialize_exercise(exercise, *, reveal: bool, question_snapshot: list | None = None) -> dict:
    q_fn = _q_with_answer if reveal else _q_for_solving
    if question_snapshot is not None:
        snapshot_questions = questions_from_snapshot(
            question_snapshot,
            exercise_id=exercise.id,
        )
        questions = [q_fn(question) for question in snapshot_questions]
        sections = [{
            'id': None,
            'order': 0,
            'title': '',
            'assistantEnabled': exercise.assistant_enabled,
            'questions': questions,
        }]
    else:
        questions = [
            q_fn(question)
            for section in exercise.sections.all()
            for question in section.questions.all()
        ]
        sections = [
            {
                'id': s.id, 'order': s.order, 'title': s.title,
                'assistantEnabled': s.assistant_enabled,
                'questions': [q_fn(q) for q in s.questions.all()],
            }
            for s in exercise.sections.all()
        ]
    return {
        'id': exercise.id,
        'title': exercise.title,
        'description': exercise.description,
        'status': exercise.status,
        'deadline': exercise.deadline.isoformat() if exercise.deadline else None,
        'assistantEnabled': exercise.assistant_enabled,
        'questions': questions,
        # Deprecated compatibility shape. New clients consume top-level questions.
        'sections': sections,
    }


class StudentExerciseListView(APIView):
    """List the PUBLISHED exercises of an enrolled class (+ own submission state)."""

    permission_classes = [IsAuthenticated, IsStudentUser]

    def get(self, request, session_id: int):
        phone = _student_phone(request)
        if not phone:
            return Response(_NO_PHONE, status=status.HTTP_400_BAD_REQUEST)
        session = ClassCreationSession.objects.filter(
            id=session_id, is_published=True, invites__phone=phone,
        ).first()
        if session is None:
            return Response({'detail': 'کلاس پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        exercises = ClassExercise.objects.filter(
            session=session, status=ClassExercise.Status.PUBLISHED,
        ).order_by('-created_at')
        subs = {
            s.exercise_id: s.status
            for s in StudentExerciseSubmission.objects.filter(
                exercise__in=exercises, student=request.user,
            )
        }
        now = timezone.now()
        return Response([
            {
                'id': ex.id, 'title': ex.title, 'status': ex.status,
                'deadline': ex.deadline.isoformat() if ex.deadline else None,
                'deadlinePassed': ex.deadline is not None and ex.deadline < now,
                'allowLate': ex.allow_late,
                'submissionStatus': subs.get(ex.id),
            }
            for ex in exercises
        ])


class StudentExerciseDetailView(APIView):
    """The solving view — sections/questions WITHOUT reference answers, plus the
    student's own draft/submission answers to resume."""

    permission_classes = [IsAuthenticated, IsStudentUser]

    def get(self, request, session_id: int, exercise_id: int):
        phone = _student_phone(request)
        if not phone:
            return Response(_NO_PHONE, status=status.HTTP_400_BAD_REQUEST)
        exercise = _published_exercise_for_student(phone, session_id, exercise_id)
        if exercise is None:
            return Response(_EX_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        submission = StudentExerciseSubmission.objects.filter(
            exercise=exercise, student=request.user,
        ).first()
        data = _serialize_exercise(exercise, reveal=False)  # solving = never reveal
        data['myAnswers'] = (
            _sanitize_student_answers(exercise, request.user, submission.answers, submission.answers)
            if submission else {}
        )
        data['submissionStatus'] = submission.status if submission else None
        data['attemptCount'] = submission.attempts.count() if submission else 0
        return Response(data)


class StudentExerciseDraftView(APIView):
    """Autosave the student's in-progress answers (upsert a DRAFT submission)."""

    permission_classes = [IsAuthenticated, IsStudentUser]

    def put(self, request, session_id: int, exercise_id: int):
        phone = _student_phone(request)
        if not phone:
            return Response(_NO_PHONE, status=status.HTTP_400_BAD_REQUEST)
        exercise = _published_exercise_for_student(phone, session_id, exercise_id)
        if exercise is None:
            return Response(_EX_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        submission = StudentExerciseSubmission.objects.filter(
            exercise=exercise, student=request.user,
        ).first()
        if submission and submission.status != StudentExerciseSubmission.Status.DRAFT:
            return Response(
                {'detail': 'این تمرین قبلاً ارسال شده است.'}, status=status.HTTP_409_CONFLICT,
            )
        answers = request.data.get('answers') if isinstance(request.data, dict) else None
        existing_answers = submission.answers if submission else {}
        answers = _sanitize_student_answers(exercise, request.user, answers, existing_answers)
        if submission is None:
            submission = StudentExerciseSubmission.objects.create(
                exercise=exercise, student=request.user,
                status=StudentExerciseSubmission.Status.DRAFT, answers=answers,
            )
        else:
            submission.answers = answers
            submission.save(update_fields=['answers', 'updated_at'])
        return Response({'status': submission.status, 'saved': True})


class StudentExerciseImageView(APIView):
    """Upload one handwriting/photo answer image for a question (server-side
    type + size validation), recorded on the DRAFT submission."""

    permission_classes = [IsAuthenticated, IsStudentUser]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, session_id: int, exercise_id: int, question_id: int):
        phone = _student_phone(request)
        if not phone:
            return Response(_NO_PHONE, status=status.HTTP_400_BAD_REQUEST)
        exercise = _published_exercise_for_student(phone, session_id, exercise_id)
        if exercise is None:
            return Response(_EX_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        question = ClassExerciseQuestion.objects.filter(
            id=question_id, section__exercise=exercise,
        ).first()
        if question is None:
            return Response({'detail': 'سوال پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        up = request.FILES.get('file')
        if up is None:
            return Response({'detail': 'فایل ارسال نشده است.'}, status=status.HTTP_400_BAD_REQUEST)
        content_type = (getattr(up, 'content_type', '') or '').lower()
        if not content_type.startswith('image/'):
            return Response(
                {'detail': 'فقط تصویر مجاز است.'}, status=status.HTTP_400_BAD_REQUEST,
            )
        if up.size and up.size > _MAX_IMAGE_BYTES:
            return Response(
                {'detail': 'حجم تصویر بیش از حد مجاز است.'},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        # Low-2: content_type is client-controlled — sniff the actual bytes
        # (Pillow verify) before persisting anything the grader will later
        # feed to the vision model.
        image_bytes = up.read()
        if not is_real_image(image_bytes):
            return Response(
                {'detail': 'فایل ارسالی تصویر معتبر نیست.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        up.seek(0)  # reset after the sniff read so the full bytes get saved
        submission, _created = StudentExerciseSubmission.objects.get_or_create(
            exercise=exercise, student=request.user,
            defaults={'status': StudentExerciseSubmission.Status.DRAFT},
        )
        if submission.status != StudentExerciseSubmission.Status.DRAFT:
            return Response(
                {'detail': 'این تمرین قبلاً ارسال شده است.'}, status=status.HTTP_409_CONFLICT,
            )
        answers = submission.answers if isinstance(submission.answers, dict) else {}
        qkey = str(question_id)
        entry = answers.get(qkey) if isinstance(answers.get(qkey), dict) else {}
        images = _owned_answer_images(answers, exercise.id, request.user.id, question_id)
        if len(images) >= _MAX_IMAGES_PER_QUESTION:
            return Response(
                {'detail': 'تعداد تصاویر این پاسخ بیش از حد مجاز است.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        extension = os.path.splitext(up.name or '')[1].lower()
        if not extension or len(extension) > 10:
            extension = '.jpg'
        path = default_storage.save(
            f'{_answer_image_prefix(exercise.id, request.user.id, question_id)}'
            f'{uuid.uuid4().hex}{extension}',
            up,
        )
        images.append(path)
        entry['images'] = images
        answers[qkey] = entry
        submission.answers = answers
        submission.save(update_fields=['answers', 'updated_at'])
        return Response({'path': path}, status=status.HTTP_201_CREATED)


class StudentExerciseSubmitView(APIView):
    """Finalize the submission. 409 after the deadline (unless allow_late) and on
    a duplicate final submission. (Grading dispatch is wired at E6.)"""

    permission_classes = [IsAuthenticated, IsStudentUser]

    def post(self, request, session_id: int, exercise_id: int):
        phone = _student_phone(request)
        if not phone:
            return Response(_NO_PHONE, status=status.HTTP_400_BAD_REQUEST)
        exercise = _published_exercise_for_student(phone, session_id, exercise_id)
        if exercise is None:
            return Response(_EX_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)

        past_deadline = exercise.deadline is not None and exercise.deadline < timezone.now()
        if past_deadline and not exercise.allow_late:
            return Response(
                {'detail': 'مهلت ارسال این تمرین گذشته است.'}, status=status.HTTP_409_CONFLICT,
            )

        answers = request.data.get('answers') if isinstance(request.data, dict) else None
        from .tasks import grade_exercise_submission
        try:
            with transaction.atomic():
                submission = StudentExerciseSubmission.objects.select_for_update().filter(
                    exercise=exercise, student=request.user,
                ).first()
                if submission and submission.status != StudentExerciseSubmission.Status.DRAFT:
                    return Response(
                        {'detail': 'شما قبلاً پاسخ این تمرین را ارسال کرده‌اید.'},
                        status=status.HTTP_409_CONFLICT,
                    )
                sanitized_answers = _sanitize_student_answers(
                    exercise,
                    request.user,
                    answers,
                    submission.answers if submission else None,
                )
                if submission is None:
                    submission = StudentExerciseSubmission.objects.create(
                        exercise=exercise,
                        student=request.user,
                        status=StudentExerciseSubmission.Status.DRAFT,
                        answers=sanitized_answers,
                    )
                latest = submission.attempts.order_by('-attempt_number').first()
                attempt = StudentExerciseAttempt.objects.create(
                    submission=submission,
                    attempt_number=(latest.attempt_number + 1) if latest else 1,
                    status=StudentExerciseAttempt.Status.SUBMITTED,
                    answers=sanitized_answers,
                    question_snapshot=build_question_snapshot(exercise),
                    is_late=bool(past_deadline),
                )
                submission.status = StudentExerciseSubmission.Status.SUBMITTED
                submission.answers = sanitized_answers
                submission.result = {}
                submission.score_points = None
                submission.max_points = None
                submission.is_late = bool(past_deadline)
                submission.grading_task_id = ''
                submission.graded_at = None
                submission.overridden_at = None
                submission.current_attempt = attempt
                submission.save(update_fields=[
                    'status', 'answers', 'result', 'score_points', 'max_points',
                    'is_late', 'grading_task_id', 'graded_at', 'overridden_at',
                    'current_attempt', 'updated_at',
                ])
                sid = submission.id
                aid = attempt.id
                transaction.on_commit(lambda: grade_exercise_submission.delay(sid, aid))
        except IntegrityError:
            return Response(
                {'detail': 'ارسال هم‌زمان دیگری ثبت شده است. صفحه را تازه‌سازی کنید.'},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(
            {
                'status': submission.status,
                'isLate': submission.is_late,
                'attemptId': attempt.id,
                'attemptNumber': attempt.attempt_number,
            },
            status=status.HTTP_201_CREATED,
        )


class StudentExerciseResultView(APIView):
    """The student's own graded result. Reference answers appear ONLY when the
    reveal condition holds (deadline passed, or no-deadline + own GRADED)."""

    permission_classes = [IsAuthenticated, IsStudentUser]

    def get(self, request, session_id: int, exercise_id: int):
        phone = _student_phone(request)
        if not phone:
            return Response(_NO_PHONE, status=status.HTTP_400_BAD_REQUEST)
        exercise = _published_exercise_for_student(phone, session_id, exercise_id)
        if exercise is None:
            return Response(_EX_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        submission = StudentExerciseSubmission.objects.filter(
            exercise=exercise, student=request.user,
        ).first()
        if submission is None:
            return Response({'detail': 'هنوز پاسخی ارسال نکرده‌اید.'}, status=status.HTTP_404_NOT_FOUND)
        attempt, attempts = _requested_attempt(request, submission)
        if attempt is False:
            return Response({'detail': 'ارسال پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        selected = attempt or submission
        if selected.status != StudentExerciseSubmission.Status.GRADED:
            # Failure-specific copy — a generic "wait for grading" would contradict
            # the «خطا در نمره‌دهی» badge the hub shows for GRADING_FAILED.
            if selected.status == StudentExerciseSubmission.Status.GRADING_FAILED:
                detail = 'نمره‌دهی خودکار با خطا مواجه شد. پاسخ شما محفوظ است و پس از بررسی، نتیجه ثبت می‌شود.'
            else:
                detail = 'پاسخ شما ارسال شد. نتیجه پس از نمره‌دهی نمایش داده می‌شود.'
            return Response({
                'status': selected.status,
                'detail': detail,
                'attempts': [_attempt_summary(item) for item in attempts],
                'attemptId': attempt.id if attempt else None,
                'attemptNumber': attempt.attempt_number if attempt else 1,
                'answers': selected.answers,
            })
        # Reveal follows the live submission state. A historical graded attempt
        # must not expose the answer key while a teacher-authorized redo is open.
        reveal = _reveal_open(exercise, submission)
        return Response({
            'status': selected.status,
            'scorePoints': str(selected.score_points) if selected.score_points is not None else None,
            'maxPoints': str(selected.max_points) if selected.max_points is not None else None,
            'result': _result_for_student(selected.result, reveal=reveal),
            'answers': selected.answers,
            'answersRevealed': reveal,
            'exercise': _serialize_exercise(
                exercise,
                reveal=reveal,
                question_snapshot=(attempt.question_snapshot or None) if attempt else None,
            ),
            'attempts': [_attempt_summary(item) for item in attempts],
            'attemptId': attempt.id if attempt else None,
            'attemptNumber': attempt.attempt_number if attempt else 1,
        })


class StudentFinishedAnswersView(APIView):
    """«پاسخ تمرین‌های تمام‌شده» — browse the reference answers of past
    (deadline-passed) exercises of the student's enrolled classes."""

    permission_classes = [IsAuthenticated, IsStudentUser]

    def get(self, request):
        phone = _student_phone(request)
        if not phone:
            return Response(_NO_PHONE, status=status.HTTP_400_BAD_REQUEST)
        now = timezone.now()
        exercises = (
            ClassExercise.objects.filter(
                status=ClassExercise.Status.PUBLISHED,
                session__is_published=True,
                session__invites__phone=phone,
                deadline__isnull=False,
                deadline__lt=now,  # reveal is open
            )
            .prefetch_related('sections__questions')
            .select_related('session')
            .order_by('-deadline')
            .distinct()
        )
        return Response([
            {
                'sessionId': ex.session_id,
                'courseTitle': ex.session.title,
                **_serialize_exercise(ex, reveal=True),  # deadline passed -> reveal
            }
            for ex in exercises
        ])


# ═══════════════════════════════════════════════════════════════════════════
# E7 — Report cards + teacher override + allow-redo.
# Override writes teacher_score/teacher_feedback beside an IMMUTABLE llm_score
# (audit); the effective score_points is recomputed = teacher_score if set else
# llm_score. Report cards = simple average of the student's GRADED exercises'
# percentages (past-deadline no-submission exercises are excluded, not zeroed).
# ═══════════════════════════════════════════════════════════════════════════

from decimal import Decimal as _Decimal, InvalidOperation as _InvalidOperation  # noqa: E402


def _owned_submission(request, submission_id):
    return StudentExerciseSubmission.objects.filter(
        id=submission_id, exercise__session__teacher=request.user,
    ).select_related('exercise', 'student').first()


def _effective(pq: dict):
    ts = pq.get('teacher_score')
    raw_score = ts if ts is not None else pq.get('llm_score')
    if raw_score is None:
        raw_score = pq.get('score_points') or 0
    try:
        score = _Decimal(str(raw_score))
        max_points = _Decimal(str(pq.get('max_points')))
    except (_InvalidOperation, TypeError, ValueError):
        return 0.0
    if not score.is_finite() or not max_points.is_finite() or max_points < 0:
        return 0.0
    return float(min(max(score, _Decimal('0')), max_points))


def _recompute_submission_score(submission) -> None:
    result = submission.result if isinstance(submission.result, dict) else {}
    per_q = result.get('per_question') if isinstance(result.get('per_question'), list) else []
    for pq in per_q:
        if isinstance(pq, dict):
            pq['score_points'] = round(_effective(pq), 2)
    total = sum(_effective(pq) for pq in per_q if isinstance(pq, dict))
    submission.result = {'per_question': per_q}
    submission.score_points = _Decimal(str(round(total, 2)))


class TeacherSubmissionListView(APIView):
    """List every student submission for one owned exercise (gradebook column)."""

    permission_classes = [IsAuthenticated, IsTeacherUser]

    def get(self, request, exercise_id: int):
        exercise = _owned_exercise(request, exercise_id)
        if exercise is None:
            return Response(_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        from django.db.models import Q
        subs = StudentExerciseSubmission.objects.filter(
            exercise=exercise,
        ).filter(
            Q(attempts__isnull=False) | ~Q(status=StudentExerciseSubmission.Status.DRAFT),
        ).select_related('student').prefetch_related('attempts').distinct()
        rows = []
        for submission in subs:
            attempts = list(submission.attempts.all())
            latest = attempts[-1] if attempts else submission
            rows.append({
                'id': submission.id,
                'studentId': submission.student_id,
                'studentName': (submission.student.get_full_name() or submission.student.username),
                'status': submission.status,
                'isLate': latest.is_late,
                'scorePoints': str(latest.score_points) if latest.score_points is not None else None,
                'maxPoints': str(latest.max_points) if latest.max_points is not None else None,
                'overridden': latest.overridden_at is not None,
                'attemptCount': len(attempts),
            })
        return Response(rows)


class TeacherSubmissionDetailView(APIView):
    """Full detail of one owned submission (teacher sees answers + result)."""

    permission_classes = [IsAuthenticated, IsTeacherUser]

    def get(self, request, submission_id: int):
        submission = _owned_submission(request, submission_id)
        if submission is None:
            return Response({'detail': 'ارسال پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        attempt, attempts = _requested_attempt(request, submission)
        if attempt is False:
            return Response({'detail': 'ارسال پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        selected = attempt or submission
        latest_id = attempts[-1].id if attempts else None
        return Response({
            'id': submission.id,
            'studentId': submission.student_id,
            'studentName': (submission.student.get_full_name() or submission.student.username),
            'status': selected.status,
            'isLate': selected.is_late,
            'answers': selected.answers,
            'result': _teacher_attempt_result(attempt) if attempt else selected.result,
            'scorePoints': str(selected.score_points) if selected.score_points is not None else None,
            'maxPoints': str(selected.max_points) if selected.max_points is not None else None,
            'overriddenAt': selected.overridden_at.isoformat() if selected.overridden_at else None,
            'attempts': [_attempt_summary(item) for item in attempts],
            'attemptId': attempt.id if attempt else None,
            'attemptNumber': attempt.attempt_number if attempt else 1,
            'isLatestAttempt': attempt is None or attempt.id == latest_id,
        })


class TeacherSubmissionOverrideView(APIView):
    """Override per-question scores/feedback. llm_score is NEVER overwritten."""

    permission_classes = [IsAuthenticated, IsTeacherUser]

    def patch(self, request, submission_id: int):
        submission = _owned_submission(request, submission_id)
        if submission is None:
            return Response({'detail': 'ارسال پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        raw = request.data.get('overrides') if isinstance(request.data, dict) else None
        overrides = {}
        if isinstance(raw, list):
            for o in raw:
                if isinstance(o, dict) and o.get('question_id') is not None:
                    overrides[str(o['question_id'])] = o
        with transaction.atomic():
            locked_submission = StudentExerciseSubmission.objects.select_for_update().get(
                id=submission.id,
            )
            locked_attempt = locked_submission.attempts.select_for_update().order_by(
                '-attempt_number',
            ).first()
            if (
                locked_attempt is None
                or locked_attempt.status != StudentExerciseAttempt.Status.GRADED
                or locked_submission.status != StudentExerciseSubmission.Status.GRADED
                or locked_submission.current_attempt_id != locked_attempt.id
            ):
                return Response(
                    {'detail': 'این ارسال دیگر آخرین نتیجه قابل ویرایش نیست.'},
                    status=status.HTTP_409_CONFLICT,
                )

            source_result = locked_attempt.result if isinstance(locked_attempt.result, dict) else {}
            source_rows = source_result.get('per_question')
            per_q = [dict(row) for row in source_rows if isinstance(row, dict)] \
                if isinstance(source_rows, list) else []
            validated_scores = {}
            for pq in per_q:
                question_id = str(pq.get('question_id'))
                override = overrides.get(question_id)
                if not override or override.get('teacher_score') is None:
                    continue
                try:
                    teacher_score = _Decimal(str(override['teacher_score']))
                    max_points = _Decimal(str(pq.get('max_points')))
                except (_InvalidOperation, TypeError, ValueError):
                    return Response(
                        {'detail': 'نمره واردشده معتبر نیست.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if (
                    not teacher_score.is_finite()
                    or not max_points.is_finite()
                    or max_points < 0
                    or teacher_score < 0
                    or teacher_score > max_points
                ):
                    return Response(
                        {
                            'detail': f'نمره این سؤال باید بین صفر و {max_points} باشد.',
                            'questionId': question_id,
                            'maxPoints': str(max_points),
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                validated_scores[question_id] = float(teacher_score)

            for pq in per_q:
                question_id = str(pq.get('question_id'))
                override = overrides.get(question_id)
                if not override:
                    continue
                if 'teacher_score' in override:
                    pq['teacher_score'] = (
                        None
                        if override['teacher_score'] is None
                        else validated_scores[question_id]
                    )  # llm_score untouched
                if 'teacher_feedback' in override:
                    pq['teacher_feedback'] = str(override['teacher_feedback'] or '')

            locked_submission.result = {'per_question': per_q}
            _recompute_submission_score(locked_submission)
            has_teacher_override = any(
                pq.get('teacher_score') is not None or bool(pq.get('teacher_feedback'))
                for pq in per_q
            )
            locked_submission.overridden_at = timezone.now() if has_teacher_override else None
            locked_submission.save(update_fields=[
                'result', 'score_points', 'overridden_at', 'updated_at',
            ])
            locked_attempt.result = locked_submission.result
            locked_attempt.score_points = locked_submission.score_points
            locked_attempt.overridden_at = locked_submission.overridden_at
            locked_attempt.save(update_fields=[
                'result', 'score_points', 'overridden_at', 'updated_at',
            ])
            submission = locked_submission
        return Response({
            'id': submission.id,
            'scorePoints': str(submission.score_points),
            'result': submission.result,
        })


class TeacherSubmissionAllowRedoView(APIView):
    """Open a new draft while preserving every finalized attempt."""

    permission_classes = [IsAuthenticated, IsTeacherUser]

    def post(self, request, submission_id: int):
        redoable_statuses = {
            StudentExerciseAttempt.Status.GRADED,
            StudentExerciseAttempt.Status.GRADING_FAILED,
        }
        submission = _owned_submission(request, submission_id)
        if submission is None:
            return Response({'detail': 'ارسال پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        if submission.status == StudentExerciseSubmission.Status.DRAFT:
            return Response(
                {'detail': 'اجازه ارسال مجدد قبلاً فعال شده است.'},
                status=status.HTTP_409_CONFLICT,
            )
        latest_attempt = submission.attempts.order_by('-attempt_number').first()
        if latest_attempt and latest_attempt.status not in redoable_statuses:
            return Response(
                {'detail': 'ارسال فعلی هنوز نمره‌دهی نشده است.'},
                status=status.HTTP_409_CONFLICT,
            )
        with transaction.atomic():
            submission = StudentExerciseSubmission.objects.select_for_update().get(
                id=submission.id,
            )
            if submission.status == StudentExerciseSubmission.Status.DRAFT:
                return Response(
                    {'detail': 'اجازه ارسال مجدد قبلاً فعال شده است.'},
                    status=status.HTTP_409_CONFLICT,
                )
            latest_attempt = submission.attempts.select_for_update().order_by(
                '-attempt_number',
            ).first()
            if latest_attempt and latest_attempt.status not in redoable_statuses:
                return Response(
                    {'detail': 'ارسال فعلی هنوز نمره‌دهی نشده است.'},
                    status=status.HTTP_409_CONFLICT,
                )
            submission.status = StudentExerciseSubmission.Status.DRAFT
            submission.grading_task_id = ''
            submission.current_attempt = None
            submission.save(update_fields=[
                'status', 'grading_task_id', 'current_attempt', 'updated_at',
            ])
            next_number = (latest_attempt.attempt_number + 1) if latest_attempt else 1
        return Response({'status': submission.status, 'nextAttemptNumber': next_number})


def _course_report(student, session_id=None):
    """Build the student's graded-exercise percentages (optionally one course)."""
    phone = (getattr(student, 'phone', '') or '').strip()
    from django.db.models import OuterRef, Subquery
    latest_graded_id = StudentExerciseAttempt.objects.filter(
        submission_id=OuterRef('submission_id'),
        status=StudentExerciseAttempt.Status.GRADED,
    ).order_by('-attempt_number').values('id')[:1]
    qs = StudentExerciseAttempt.objects.filter(
        id=Subquery(latest_graded_id),
        submission__student=student,
        submission__exercise__session__is_published=True,
        submission__exercise__session__invites__phone=phone,
    ).select_related('submission__exercise')
    if session_id is not None:
        qs = qs.filter(submission__exercise__session_id=session_id)
    rows = []
    for s in qs:
        mx = float(s.max_points or 0)
        pct = round(float(s.score_points or 0) / mx * 100, 1) if mx > 0 else 0.0
        rows.append({
            'exerciseId': s.submission.exercise_id,
            'exerciseTitle': s.submission.exercise.title,
            'scorePoints': str(s.score_points) if s.score_points is not None else None,
            'maxPoints': str(s.max_points) if s.max_points is not None else None,
            'percent': pct,
        })
    avg = round(sum(r['percent'] for r in rows) / len(rows), 1) if rows else None
    return rows, avg


class StudentCourseReportCardView(APIView):
    """The student's report card for one enrolled course (per-exercise + average)."""

    permission_classes = [IsAuthenticated, IsStudentUser]

    def get(self, request, session_id: int):
        phone = _student_phone(request)
        if not phone:
            return Response(_NO_PHONE, status=status.HTTP_400_BAD_REQUEST)
        session = ClassCreationSession.objects.filter(
            id=session_id, is_published=True, invites__phone=phone,
        ).first()
        if session is None:
            return Response({'detail': 'کلاس پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        rows, avg = _course_report(request.user, session_id=session_id)
        return Response({'average': avg, 'exercises': rows})


class StudentOverallReportCardView(APIView):
    """The student's overall report card across all enrolled courses."""

    permission_classes = [IsAuthenticated, IsStudentUser]

    def get(self, request):
        phone = _student_phone(request)
        if not phone:
            return Response(_NO_PHONE, status=status.HTTP_400_BAD_REQUEST)
        rows, avg = _course_report(request.user)
        return Response({'average': avg, 'exercises': rows})


class StudentCalendarView(APIView):
    """Aggregate calendar for a student: published exercise deadlines of enrolled
    classes + scheduled (timed) exam-prep sessions they were invited to. Returns
    Tehran-tz ISO datetimes; the frontend does the Jalali conversion."""

    permission_classes = [IsAuthenticated, IsStudentUser]

    def get(self, request):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from django.utils.dateparse import parse_datetime
        from .models import StudentExamPrepAttempt

        phone = _student_phone(request)
        if not phone:
            return Response(_NO_PHONE, status=status.HTTP_400_BAD_REQUEST)

        tehran = ZoneInfo('Asia/Tehran')

        def _parse(raw):
            if not raw:
                return None
            dt = parse_datetime(raw)
            if dt is None:
                try:
                    dt = datetime.fromisoformat(raw)
                except (ValueError, TypeError):
                    return None
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, tehran)
            return dt

        dt_from = _parse(request.query_params.get('from'))
        dt_to = _parse(request.query_params.get('to'))

        def _iso(dt):
            return timezone.localtime(dt, tehran).isoformat() if dt else None

        # Exercise deadlines of enrolled (invited + published) classes.
        exercises = ClassExercise.objects.filter(
            status=ClassExercise.Status.PUBLISHED,
            session__is_published=True,
            session__invites__phone=phone,
            deadline__isnull=False,
        ).select_related('session').distinct()
        if dt_from:
            exercises = exercises.filter(deadline__gte=dt_from)
        if dt_to:
            exercises = exercises.filter(deadline__lte=dt_to)

        submitted_ex = set(
            StudentExerciseSubmission.objects.filter(
                student=request.user, exercise__in=exercises,
            ).exclude(status=StudentExerciseSubmission.Status.DRAFT)
            .values_list('exercise_id', flat=True)
        )

        # Scheduled (timed) exam-prep sessions the student was invited to.
        exam_preps = ClassCreationSession.objects.filter(
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
            is_published=True,
            invites__phone=phone,
            scheduled_at__isnull=False,
        ).distinct()
        if dt_from:
            exam_preps = exam_preps.filter(scheduled_at__gte=dt_from)
        if dt_to:
            exam_preps = exam_preps.filter(scheduled_at__lte=dt_to)

        finalized_sessions = set(
            StudentExamPrepAttempt.objects.filter(
                student=request.user, session__in=exam_preps, finalized=True,
            ).values_list('session_id', flat=True)
        )

        events = []
        for ex in exercises:
            events.append({
                'id': f'exercise-{ex.id}',
                'kind': 'exercise_deadline',
                'title': ex.title,
                'courseTitle': ex.session.title,
                'datetime': _iso(ex.deadline),
                'sessionId': ex.session_id,
                'exerciseId': ex.id,
                'isCompleted': ex.id in submitted_ex,
            })
        for s in exam_preps:
            events.append({
                'id': f'exam_prep-{s.id}',
                'kind': 'exam_prep',
                'title': s.title,
                'courseTitle': s.title,
                'datetime': _iso(s.scheduled_at),
                'sessionId': s.id,
                'isCompleted': s.id in finalized_sessions,
            })
        events.sort(key=lambda e: e['datetime'] or '')
        return Response(events)


class StudentExerciseAssistantView(APIView):
    """In-exercise assistant chat with an exercise-level server guard.

    Disabled exercises return 403 `assistant_disabled`. Reference answers enter
    the model context only after reveal (structural leak guard in the service).
    """

    permission_classes = [IsAuthenticated, IsStudentUser]

    def post(self, request, session_id: int, exercise_id: int):
        phone = _student_phone(request)
        if not phone:
            return Response(_NO_PHONE, status=status.HTTP_400_BAD_REQUEST)
        exercise = _published_exercise_for_student(phone, session_id, exercise_id)
        if exercise is None:
            return Response(_EX_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)

        question_id = request.data.get('question_id') if isinstance(request.data, dict) else None
        question = ClassExerciseQuestion.objects.filter(
            id=question_id, section__exercise=exercise,
        ).select_related('section').first()
        if question is None:
            return Response({'detail': 'سوال پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        if not exercise.assistant_enabled:
            return Response(
                {'detail': 'دستیار این تمرین غیرفعال است.', 'code': 'assistant_disabled'},
                status=status.HTTP_403_FORBIDDEN,
            )

        submission = StudentExerciseSubmission.objects.filter(
            exercise=exercise, student=request.user,
        ).first()
        reveal = _reveal_open(exercise, submission)  # gates reference-answer teaching
        student_work = ''
        if submission and isinstance(submission.answers, dict):
            entry = submission.answers.get(str(question.id))
            if isinstance(entry, dict):
                student_work = str(entry.get('text') or '')

        from .services.exercise_assistant import handle_assistant_message
        reply = handle_assistant_message(
            exercise_id=exercise.id, question=question,
            student_id=request.user.id,
            user_message=str(request.data.get('message') or ''),
            student_work=student_work, reveal=reveal,
        )
        return Response(reply)
