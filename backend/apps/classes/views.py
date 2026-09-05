from __future__ import annotations

import csv
import json
import logging
import re
import uuid
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.core.files.base import File
from django.core.files.storage import default_storage, storages
from django.db import IntegrityError, transaction
from django.utils import timezone

logger = logging.getLogger(__name__)
from django.http import FileResponse, HttpResponse
from django.db.models import Count, F, Max, Min, Prefetch, Q

from rest_framework import status
from rest_framework import serializers
from rest_framework.generics import GenericAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from .models import (
    ClassAnnouncement,
    ClassCreationSession,
    ClassInvitation,
    ClassPrerequisite,
    ExamPrepExtractionArtifact,
    ExamPrepExtractionUnit,
    ExamPrepVisualAsset,
)
from .models import ClassSection, ClassSectionQuiz, ClassSectionQuizAttempt
from .models import ClassFinalExam, ClassFinalExamAttempt
from .models import Enrollment, StudentInviteCode
from apps.notification.models import AdminNotification
from .permissions import IsTeacherUser, IsStudentUser
from .serializers import (
    is_pdf_upload,
    ClassCreationSessionDetailSerializer,
    ClassCreationSessionListSerializer,
    ClassCreationSessionUpdateSerializer,
    ClassInvitationCreateSerializer,
    ClassInvitationSerializer,
    ClassAnnouncementSerializer,
    ClassAnnouncementCreateSerializer,
    ClassAnnouncementUpdateSerializer,
    TeacherAnalyticsActivitySerializer,
    TeacherAnalyticsChartPointSerializer,
    TeacherAnalyticsDistributionItemSerializer,
    TeacherAnalyticsStatSerializer,
    TeacherStudentSerializer,
    ClassSessionStudentSerializer,
    Step1TranscribeRequestSerializer,
    Step1TranscribeResponseSerializer,
    Step2StructureRequestSerializer,
    Step2StructureResponseSerializer,
    Step3PrerequisitesRequestSerializer,
    Step3PrerequisitesResponseSerializer,
    Step4PrerequisiteTeachingRequestSerializer,
    Step4PrerequisiteTeachingResponseSerializer,
    Step5RecapRequestSerializer,
    Step5RecapResponseSerializer,
    PrerequisiteSerializer,
    StudentCourseSerializer,
    StudentCourseContentSerializer,
    StudentChapterQuizResponseSerializer,
    StudentChapterQuizSubmitRequestSerializer,
    StudentChapterQuizSubmitResponseSerializer,
    StudentFinalExamResponseSerializer,
    StudentFinalExamSubmitRequestSerializer,
    StudentFinalExamSubmitResponseSerializer,
    InviteCodeVerifySerializer,
    InviteCodeVerifyResponseSerializer,
    StudentNotificationSerializer,
    # Exam Prep Pipeline serializers
    ExamPrepStep1TranscribeRequestSerializer,
    ExamPrepStep1TranscribeResponseSerializer,
    ExamPrepStep2StructureRequestSerializer,
    ExamPrepStep2StructureResponseSerializer,
    ExamPrepSessionUpdateSerializer,
    ExamPrepSessionDetailSerializer,
    # Student Exam Prep serializers
    StudentExamPrepListSerializer,
    StudentExamPrepDetailSerializer,
    StudentExamPrepSubmitRequestSerializer,
    StudentExamPrepSubmitResponseSerializer,
    StudentExamPrepCheckAnswerRequestSerializer,
    StudentExamPrepCheckAnswerResponseSerializer,
    StudentExamPrepResultResponseSerializer,
)
from .services.transcription import transcribe_media_bytes
from .services.pdf_extraction import extract_pdf_to_markdown
from .services.structure import structure_transcript_markdown
from .services.prerequisites import extract_prerequisites, generate_prerequisite_teaching
from .services.recap import generate_recap_from_structure, recap_json_to_markdown
from .services.sync_structure import sync_structure_from_session
from .services.quizzes import generate_answer_hint, generate_final_exam_pool, generate_section_quiz_questions, generate_adaptive_section_quiz, generate_adaptive_final_exam, grade_open_text_answer
from .services.adaptive_quiz import compute_weak_points, compute_weak_points_from
from .services.pdf_export import generate_course_pdf
from .services.exam_prep_structure import extract_exam_prep_structure
from .services.invite_codes import get_or_create_invite_code_for_phone
from .services.exercise_workflow import normalize_source_config
from .services.session_workflow import (
    build_session_workflow_state,
    serialize_session_workflow_fields,
)
from .services.file_validation import is_probably_pdf, is_real_image, uploaded_content_type, uploaded_name

from .tasks import (
    process_class_step1_transcription,
    process_class_step2_structure,
    process_class_step3_prerequisites,
    process_class_step4_prereq_teaching,
    process_class_step5_recap,
    process_class_full_pipeline,
    process_exam_prep_step1_transcription,
    process_exam_prep_step2_structure,
    process_exam_prep_full_pipeline,
    send_publish_sms_task,
    send_new_invites_sms_task,
)


def _teacher_student_invites(teacher):
    """Return the teacher's student invitations, excluding the teacher's own phone."""
    invites = ClassInvitation.objects.filter(session__teacher=teacher)
    teacher_phone = (getattr(teacher, 'phone', '') or '').strip()
    return invites.exclude(phone=teacher_phone) if teacher_phone else invites


def _dispatch_pipeline_task(session, task) -> None:
    """Dispatch a pipeline task with a pre-generated, persisted Celery id.

    Generating the task id ourselves (instead of reading ``AsyncResult.id``
    after ``.delay()``) lets us persist ``celery_task_id`` BEFORE the worker
    can pick the task up — eliminating the race where a cancel arrives before
    the id is stored. A later cancel revokes exactly this id, and the
    cooperative ``cancel_requested`` flag is the safety net if revoke can't
    kill an in-flight step.
    """
    task_id = uuid.uuid4().hex
    session.celery_task_id = task_id
    session.save(update_fields=['celery_task_id', 'updated_at'])
    transaction.on_commit(
        lambda: task.apply_async(args=[session.id], task_id=task_id)
    )


_MAX_PENDING_EXERCISE_SOURCE_BYTES = 20 * 1024 * 1024


def _pending_exercise_uploads_by_key(request) -> dict[tuple[str, str], object]:
    out: dict[tuple[str, str], object] = {}
    for field_name, uploaded in request.FILES.items():
        if not field_name.startswith('exercise_') or '__file_' not in field_name:
            continue
        exercise_part, source_part = field_name.split('__file_', 1)
        exercise_key = exercise_part.removeprefix('exercise_').strip()
        source_key = source_part.strip()
        if exercise_key and source_key:
            out[(exercise_key, source_key)] = uploaded
    return out


def _pending_exercises_signature(pending_exercises: list[dict], uploads: dict[tuple[str, str], object] | None = None) -> list[dict]:
    uploads = uploads or {}
    signature: list[dict] = []
    for ex_idx, exercise in enumerate(pending_exercises, start=1):
        if not isinstance(exercise, dict):
            continue
        exercise_key = str(exercise.get('clientExerciseKey') or '').strip() or f'pending-exercise-{ex_idx}'
        sources_signature: list[dict] = []
        for src_idx, source in enumerate(exercise.get('sources') or [], start=1):
            if not isinstance(source, dict):
                continue
            client_file_key = str(source.get('clientFileKey') or '').strip()
            uploaded = uploads.get((exercise_key, client_file_key))
            sources_signature.append({
                'clientFileKey': client_file_key,
                'assetName': str(
                    source.get('assetName')
                    or getattr(uploaded, 'name', '')
                    or f'source-{src_idx}'
                ),
                'assetBytes': int(
                    source.get('assetBytes')
                    or getattr(uploaded, 'size', 0)
                    or 0
                ),
                'role': str(source.get('role') or 'auto'),
                'writingMode': str(source.get('writingMode') or 'auto'),
                'answerLayout': str(source.get('answerLayout') or 'auto'),
            })
        signature.append({
            'clientExerciseKey': exercise_key,
            'title': str(exercise.get('title') or '').strip(),
            'noDeadline': bool(exercise.get('noDeadline', False)),
            'deadline': exercise.get('deadline'),
            'allowLate': bool(exercise.get('allowLate', False)),
            'assistantEnabled': bool(exercise.get('assistantEnabled', True)),
            'teacherNote': str(exercise.get('teacherNote', '') or '').strip(),
            'sources': sources_signature,
        })
    return signature


def _same_pending_exercise_payload(existing, request, pending_exercises: list[dict]) -> bool:
    existing_snapshot = getattr(existing, 'pending_exercises', None)
    if not isinstance(existing_snapshot, list):
        existing_snapshot = []
    uploads = _pending_exercise_uploads_by_key(request)
    return _pending_exercises_signature(existing_snapshot) == _pending_exercises_signature(
        pending_exercises,
        uploads,
    )


def _validate_pending_exercise_source_file(uploaded):
    size = int(getattr(uploaded, 'size', 0) or 0)
    if size and size > _MAX_PENDING_EXERCISE_SOURCE_BYTES:
        raise serializers.ValidationError('حجم فایل منبع تمرین بیش از حد مجاز است.')
    data = uploaded.read()
    try:
        uploaded.seek(0)
    except Exception:
        pass
    if not data:
        raise serializers.ValidationError('فایل منبع تمرین خالی است.')
    if len(data) > _MAX_PENDING_EXERCISE_SOURCE_BYTES:
        raise serializers.ValidationError('حجم فایل منبع تمرین بیش از حد مجاز است.')
    ct = uploaded_content_type(uploaded)
    name = uploaded_name(uploaded)
    looks_pdf = 'pdf' in ct or name.endswith('.pdf')
    looks_image = ct.startswith('image/') or name.endswith(('.jpg', '.jpeg', '.png', '.webp'))
    if looks_pdf and is_probably_pdf(data):
        return 'pdf'
    if looks_image and is_real_image(data):
        return 'image'
    raise serializers.ValidationError('منبع تمرین باید PDF یا تصویر معتبر باشد.')


def _delete_pending_exercise_snapshot_files(pending_snapshot: list[dict]) -> None:
    for exercise in pending_snapshot:
        if not isinstance(exercise, dict):
            continue
        for source in exercise.get('sources') or []:
            if not isinstance(source, dict):
                continue
            storage_path = str(source.get('storagePath') or '').strip()
            if not storage_path:
                continue
            try:
                default_storage.delete(storage_path)
            except Exception:
                logger.warning('Failed to cleanup pending exercise source %s', storage_path, exc_info=True)


def _store_pending_exercises_snapshot(request, pending_exercises: list[dict]) -> list[dict]:
    uploads = _pending_exercise_uploads_by_key(request)
    out: list[dict] = []
    try:
        for ex_idx, exercise in enumerate(pending_exercises, start=1):
            exercise_key = str(exercise.get('clientExerciseKey') or '').strip() or f'pending-exercise-{ex_idx}'
            stored_sources: list[dict] = []
            for src_idx, source in enumerate(exercise.get('sources') or [], start=1):
                client_file_key = str(source.get('clientFileKey') or '').strip()
                uploaded = uploads.get((exercise_key, client_file_key))
                if uploaded is None:
                    raise serializers.ValidationError(
                        {'pending_exercises': f'فایل منبع {src_idx} برای تمرین {ex_idx} ارسال نشده است.'}
                    )
                kind = _validate_pending_exercise_source_file(uploaded)
                ext = Path(getattr(uploaded, 'name', '') or '').suffix or ('.pdf' if kind == 'pdf' else '.bin')
                stored_path = default_storage.save(
                    f'class_creation/pending_exercises/{uuid.uuid4().hex}{ext}',
                    File(uploaded),
                )
                stored_sources.append({
                    **normalize_source_config(
                        source,
                        asset_order=src_idx - 1,
                        asset_name=getattr(uploaded, 'name', '') or f'source-{src_idx}',
                        asset_kind=kind,
                    ),
                    'assetBytes': int(getattr(uploaded, 'size', 0) or 0),
                    'storagePath': stored_path,
                })
            out.append({
                'clientExerciseKey': exercise_key,
                'title': exercise['title'],
                'noDeadline': bool(exercise.get('noDeadline', False)),
                'deadline': exercise.get('deadline'),
                'allowLate': bool(exercise.get('allowLate', False)),
                'assistantEnabled': bool(exercise.get('assistantEnabled', True)),
                'teacherNote': str(exercise.get('teacherNote', '') or '').strip(),
                'sources': stored_sources,
                'status': 'pending',
            })
        return out
    except Exception:
        _delete_pending_exercise_snapshot_files(out)
        raise


from apps.chatbot.services.student_course_chat import (
    handle_student_audio_upload,
    handle_student_image_upload,
    handle_student_message,
)

from apps.chatbot.services.student_exam_prep_chat import (
    build_exam_question_context,
    describe_exam_prep_handwriting,
    handle_exam_prep_message,
)

from .services.exam_prep_utils import (
    normalize_exam_prep_questions as _normalize_exam_prep_questions,
    normalize_exam_prep_json as _normalize_exam_prep_json,
)
from .services.exam_prep_inventory import rebuild_audit_after_teacher_review

from .services.student_chat_history import append_message, get_or_create_thread, list_messages
from .services.student_exam_chat_history import (
    append_message as append_exam_message,
    get_or_create_thread as get_or_create_exam_thread,
    list_messages as list_exam_messages,
)

from apps.commons.token_tracker import set_current_user


def _ingest_for_session(session, data):
    """Step-1 ingestion dispatch: branch on ``source_type``.

    Returns ``(markdown, provider, model, page_count)``. PDF sources go through
    the hybrid PDF engine; everything else through media transcription. Both
    ``transcribe_media_bytes`` and ``extract_pdf_to_markdown`` are module-level
    names so tests can monkeypatch them at ``apps.classes.views.*``.
    """
    mime = session.source_mime_type or ''
    if session.source_type == ClassCreationSession.SourceType.PDF:
        markdown, provider, model_name, page_count = extract_pdf_to_markdown(
            data=data, mime_type=mime or 'application/pdf',
            asset_prefix=f'class_creation/extracted/{session.id}',
        )
        return markdown, provider, model_name, page_count
    markdown, provider, model_name = transcribe_media_bytes(
        data=data, mime_type=mime or 'application/octet-stream',
    )
    return markdown, provider, model_name, 0


def _process_step1_transcription(session_id: int) -> None:
    session = ClassCreationSession.objects.filter(id=session_id).first()
    if session is None:
        return
    if session.status != ClassCreationSession.Status.TRANSCRIBING:
        return
    set_current_user(session.teacher)

    try:
        session.source_file.open('rb')
        try:
            data = session.source_file.read()
        finally:
            session.source_file.close()

        transcript, provider, model_name, page_count = _ingest_for_session(session, data)
        session.transcript_markdown = transcript
        session.llm_provider = provider
        session.llm_model = model_name
        session.source_page_count = page_count
        session.status = ClassCreationSession.Status.TRANSCRIBED
        session.save(update_fields=['transcript_markdown', 'llm_provider', 'llm_model', 'source_page_count', 'status', 'updated_at'])
    except Exception as exc:
        session.status = ClassCreationSession.Status.FAILED
        session.error_detail = str(exc)
        session.save(update_fields=['status', 'error_detail', 'updated_at'])


def _process_step2_structure(session_id: int) -> None:
    session = ClassCreationSession.objects.filter(id=session_id).first()
    if session is None:
        return
    if session.status != ClassCreationSession.Status.STRUCTURING:
        return
    if not (session.transcript_markdown or '').strip():
        session.status = ClassCreationSession.Status.FAILED
        session.error_detail = 'برای این جلسه هنوز متن درس آماده نیست.'
        session.save(update_fields=['status', 'error_detail', 'updated_at'])
        return
    set_current_user(session.teacher)

    try:
        structure_obj, provider, model_name = structure_transcript_markdown(
            transcript_markdown=session.transcript_markdown,
        )
        session.structure_json = json.dumps(structure_obj, ensure_ascii=False)
        session.llm_provider = provider
        session.llm_model = model_name
        session.status = ClassCreationSession.Status.STRUCTURED
        session.save(update_fields=['structure_json', 'llm_provider', 'llm_model', 'status', 'updated_at'])
        sync_structure_from_session(session=session)
    except Exception as exc:
        session.status = ClassCreationSession.Status.FAILED
        session.error_detail = str(exc)
        session.save(update_fields=['status', 'error_detail', 'updated_at'])


def _upsert_prerequisites(*, session: ClassCreationSession, prerequisites: list[str]) -> None:
    keep_ids: list[int] = []
    for idx, name in enumerate(prerequisites):
        s = (name or '').strip()
        if not s:
            continue
        obj, _ = ClassPrerequisite.objects.update_or_create(
            session=session,
            order=idx + 1,
            defaults={'name': s},
        )
        keep_ids.append(obj.id)

    ClassPrerequisite.objects.filter(session=session).exclude(id__in=keep_ids).delete()


def _process_step3_prerequisites(session_id: int) -> None:
    session = ClassCreationSession.objects.filter(id=session_id).first()
    if session is None:
        return
    if session.status != ClassCreationSession.Status.PREREQ_EXTRACTING:
        return
    if not (session.transcript_markdown or '').strip():
        session.status = ClassCreationSession.Status.FAILED
        session.error_detail = 'برای این جلسه هنوز متن درس آماده نیست.'
        session.save(update_fields=['status', 'error_detail', 'updated_at'])
        return
    set_current_user(session.teacher)

    try:
        prereq_obj, provider, model_name = extract_prerequisites(transcript_markdown=session.transcript_markdown)
        raw_list = prereq_obj.get('prerequisites') if isinstance(prereq_obj, dict) else None
        prereqs = [str(x).strip() for x in (raw_list or []) if str(x).strip()]
        _upsert_prerequisites(session=session, prerequisites=prereqs)

        session.llm_provider = provider
        session.llm_model = model_name
        session.status = ClassCreationSession.Status.PREREQ_EXTRACTED
        session.save(update_fields=['llm_provider', 'llm_model', 'status', 'updated_at'])
    except Exception as exc:
        session.status = ClassCreationSession.Status.FAILED
        session.error_detail = str(exc)
        session.save(update_fields=['status', 'error_detail', 'updated_at'])


def _process_step4_prereq_teaching(session_id: int, prerequisite_name: str | None = None) -> None:
    session = ClassCreationSession.objects.filter(id=session_id).first()
    if session is None:
        return
    if session.status != ClassCreationSession.Status.PREREQ_TEACHING:
        return
    set_current_user(session.teacher)

    qs = ClassPrerequisite.objects.filter(session=session).order_by('order')
    if prerequisite_name:
        qs = qs.filter(name=prerequisite_name)

    if not qs.exists():
        session.status = ClassCreationSession.Status.FAILED
        session.error_detail = 'پیش نیازها یافت نشدند. ابتدا مرحله پیش نیازها را اجرا کنید.'
        session.save(update_fields=['status', 'error_detail', 'updated_at'])
        return

    try:
        provider: str = ''
        model_name: str = ''
        for prereq in qs:
            teaching, provider, model_name = generate_prerequisite_teaching(
                prerequisite_name=prereq.name,
                source_markdown=session.transcript_markdown,
            )
            prereq.teaching_text = teaching
            prereq.save(update_fields=['teaching_text'])

        if provider:
            session.llm_provider = provider
        if model_name:
            session.llm_model = model_name
        session.status = ClassCreationSession.Status.PREREQ_TAUGHT
        session.save(update_fields=['llm_provider', 'llm_model', 'status', 'updated_at'])
    except Exception as exc:
        session.status = ClassCreationSession.Status.FAILED
        session.error_detail = str(exc)
        session.save(update_fields=['status', 'error_detail', 'updated_at'])


def _process_step5_recap(session_id: int) -> None:
    session = ClassCreationSession.objects.filter(id=session_id).first()
    if session is None:
        return
    if session.status != ClassCreationSession.Status.RECAPPING:
        return
    if not (session.structure_json or '').strip():
        session.status = ClassCreationSession.Status.FAILED
        session.error_detail = 'برای این جلسه هنوز ساختار مرحله ۲ آماده نیست.'
        session.save(update_fields=['status', 'error_detail', 'updated_at'])
        return
    set_current_user(session.teacher)

    try:
        recap_obj, provider, model_name = generate_recap_from_structure(structure_json=session.structure_json)
        session.recap_markdown = recap_json_to_markdown(recap_obj)
        session.llm_provider = provider
        session.llm_model = model_name
        session.status = ClassCreationSession.Status.RECAPPED
        session.save(update_fields=['recap_markdown', 'llm_provider', 'llm_model', 'status', 'updated_at'])
    except Exception as exc:
        session.status = ClassCreationSession.Status.FAILED
        session.error_detail = str(exc)
        session.save(update_fields=['status', 'error_detail', 'updated_at'])


def _compute_student_course_progress(*, session: ClassCreationSession, student) -> int:
    """Completion percent for a student in a session.

    Delegates to ``services.progress.course_progress_percent`` which is now
    lesson-completion based (completed units / total units) with a fallback to
    the legacy quiz/exam measure when a session has no normalized units.
    """
    from .services.progress import course_progress_percent

    return course_progress_percent(session=session, student=student)


def _process_full_pipeline(session_id: int) -> None:
    """Run steps 1..5 sequentially.

    Intended for the one-click "run pipeline" action.
    """

    session = ClassCreationSession.objects.filter(id=session_id).first()
    if session is None:
        return

    # Step 1
    if session.status == ClassCreationSession.Status.TRANSCRIBING:
        _process_step1_transcription(session_id)

    session.refresh_from_db()
    if session.status == ClassCreationSession.Status.FAILED:
        return

    # Step 2
    if session.status == ClassCreationSession.Status.TRANSCRIBED:
        session.status = ClassCreationSession.Status.STRUCTURING
        session.save(update_fields=['status', 'updated_at'])
        _process_step2_structure(session_id)

    session.refresh_from_db()
    if session.status == ClassCreationSession.Status.FAILED:
        return

    # Step 3
    if session.status == ClassCreationSession.Status.STRUCTURED:
        session.status = ClassCreationSession.Status.PREREQ_EXTRACTING
        session.save(update_fields=['status', 'updated_at'])
        _process_step3_prerequisites(session_id)

    session.refresh_from_db()
    if session.status == ClassCreationSession.Status.FAILED:
        return

    # Step 4
    if session.status == ClassCreationSession.Status.PREREQ_EXTRACTED:
        session.status = ClassCreationSession.Status.PREREQ_TEACHING
        session.save(update_fields=['status', 'updated_at'])
        _process_step4_prereq_teaching(session_id)

    session.refresh_from_db()
    if session.status == ClassCreationSession.Status.FAILED:
        return

    # Step 5
    if session.status == ClassCreationSession.Status.PREREQ_TAUGHT:
        session.status = ClassCreationSession.Status.RECAPPING
        session.save(update_fields=['status', 'updated_at'])
        _process_step5_recap(session_id)


def _is_same_uploaded_source(existing, upload) -> bool:
    """Whether ``upload`` looks like the SAME file already stored on ``existing``.

    This keeps ``client_request_id`` idempotency honest. A genuine retry resubmits
    the SAME file and should dedupe to the existing session. But if the SAME key
    arrives with a DIFFERENT file, returning the old session would emit the OLD
    media's transcript/output for a brand-new upload (the "new input, stale output"
    bug). We compare original filename and byte size; when a signal is unavailable
    (e.g. a completed session whose source_file was already deleted) we err toward
    "same" so legitimate retries still dedupe.
    """
    new_name = (getattr(upload, 'name', '') or '').strip()
    existing_name = (getattr(existing, 'source_original_name', '') or '').strip()
    if new_name and existing_name and new_name != existing_name:
        return False

    new_size = getattr(upload, 'size', None)
    existing_size = None
    try:
        source_file = getattr(existing, 'source_file', None)
        if source_file:
            existing_size = source_file.size
    except Exception:
        existing_size = None
    if isinstance(new_size, int) and isinstance(existing_size, int) and new_size != existing_size:
        return False

    return True


class Step1TranscribeView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]
    parser_classes = [FormParser, MultiPartParser]

    @extend_schema(
        tags=['Classes'],
        summary='Step 1: Transcription & Vision (Gemini/AvalAI)',
        request=Step1TranscribeRequestSerializer,
        responses={202: Step1TranscribeResponseSerializer, 200: Step1TranscribeResponseSerializer},
    )
    def post(self, request):
        serializer = Step1TranscribeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        upload = serializer.validated_data['file']
        title = serializer.validated_data['title']
        description = serializer.validated_data.get('description', '')
        client_request_id = serializer.validated_data.get('client_request_id')
        run_full_pipeline = bool(serializer.validated_data.get('run_full_pipeline', False))
        pending_exercises = serializer.validated_data.get('pending_exercises') or []

        # Limit concurrent in-progress sessions per teacher to prevent resource abuse.
        _ACTIVE_STATUSES = [
            ClassCreationSession.Status.TRANSCRIBING,
            ClassCreationSession.Status.STRUCTURING,
            ClassCreationSession.Status.PREREQ_EXTRACTING,
            ClassCreationSession.Status.PREREQ_TEACHING,
            ClassCreationSession.Status.RECAPPING,
        ]

        logger.info(
            "STEP1 upload: teacher=%s file=%r size=%s content_type=%s client_request_id=%s",
            request.user.id,
            getattr(upload, 'name', '?'),
            getattr(upload, 'size', '?'),
            getattr(upload, 'content_type', '?'),
            client_request_id,
        )

        # Idempotency: a genuine retry resubmits the SAME file -> dedupe to the
        # existing session. But if the SAME client_request_id arrives with a
        # DIFFERENT file, returning the old session would emit the OLD media's
        # output for a NEW upload (the "new input, stale output" bug). In that case
        # we must NOT return the stale session and must NOT silently drop the new
        # file: mint a fresh key and fall through to process the new upload.
        if client_request_id is not None:
            existing = ClassCreationSession.objects.filter(
                teacher=request.user,
                client_request_id=client_request_id,
            ).first()
            if existing is not None:
                same_source = _is_same_uploaded_source(existing, upload)
                same_pending_payload = _same_pending_exercise_payload(existing, request, pending_exercises)
                if same_source and same_pending_payload:
                    logger.info(
                        "STEP1 IDEMPOTENT HIT: same file and same embedded exercise payload; "
                        "returning EXISTING session=%s (status=%s) for client_request_id=%s.",
                        existing.id,
                        existing.status,
                        client_request_id,
                    )
                    payload = Step1TranscribeResponseSerializer(existing).data
                    http_status = (
                        status.HTTP_202_ACCEPTED
                        if getattr(settings, 'CLASS_PIPELINE_ASYNC', False) and existing.status == ClassCreationSession.Status.TRANSCRIBING
                        else status.HTTP_200_OK
                    )
                    return Response(payload, status=http_status)
                logger.warning(
                    "STEP1 IDEMPOTENT KEY REUSED with changed payload (session=%s same_source=%s "
                    "same_pending=%s existing_name=%r new_name=%r) — NOT returning stale output; "
                    "processing the new upload as a fresh session.",
                    existing.id,
                    same_source,
                    same_pending_payload,
                    existing.source_original_name,
                    getattr(upload, 'name', '?'),
                )
                client_request_id = None

        # Atomic check + create to prevent TOCTOU race on concurrent limit.
        try:
            with transaction.atomic():
                active_count = ClassCreationSession.objects.select_for_update(skip_locked=True).filter(
                    teacher=request.user,
                    pipeline_type=ClassCreationSession.PipelineType.CLASS,
                    status__in=_ACTIVE_STATUSES,
                ).count()
                if active_count >= 5:
                    return Response(
                        {'detail': 'حداکثر ۵ کلاس همزمان در حال پردازش است. لطفاً صبر کنید.'},
                        status=status.HTTP_429_TOO_MANY_REQUESTS,
                    )

                # Resolve optional organization from request data.
                org_id = request.data.get('organization')
                organization = None
                if org_id:
                    from apps.organizations.models import Organization, OrganizationMembership
                    try:
                        org_id_int = int(org_id)
                    except (ValueError, TypeError):
                        return Response(
                            {'detail': 'شناسه سازمان آموزشی نامعتبر است.'},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    # Verify user is an active member of the organization.
                    if not OrganizationMembership.objects.filter(
                        user=request.user,
                        organization_id=org_id_int,
                        status=OrganizationMembership.MemberStatus.ACTIVE,
                    ).exists():
                        return Response(
                            {'detail': 'شما عضو فعال این سازمان آموزشی نیستید.'},
                            status=status.HTTP_403_FORBIDDEN,
                        )
                    organization = Organization.objects.filter(id=org_id_int).first()

                # Resolve optional study group (must belong to the chosen org).
                study_group = None
                sg_id = request.data.get('study_group')
                if sg_id:
                    if organization is None:
                        return Response(
                            {'detail': 'برای انتخاب گروه آموزشی ابتدا سازمان آموزشی را مشخص کنید.'},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    from apps.organizations.models import StudyGroup
                    study_group = StudyGroup.objects.filter(
                        id=sg_id, organization_id=organization.id,
                    ).first()
                    if study_group is None:
                        return Response(
                            {'detail': 'گروه آموزشی نامعتبر است یا متعلق به این سازمان آموزشی نیست.'},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                pending_exercise_snapshot = _store_pending_exercises_snapshot(request, pending_exercises)

                session = ClassCreationSession.objects.create(
                    teacher=request.user,
                    title=title,
                    description=description,
                    source_type=(
                        ClassCreationSession.SourceType.PDF if is_pdf_upload(upload)
                        else ClassCreationSession.SourceType.MEDIA
                    ),
                    source_file=upload,
                    source_mime_type=getattr(upload, 'content_type', '') or '',
                    source_original_name=getattr(upload, 'name', '') or '',
                    status=ClassCreationSession.Status.TRANSCRIBING,
                    client_request_id=client_request_id,
                    organization=organization,
                    study_group=study_group,
                    pending_exercises=pending_exercise_snapshot,
                    workflow_state=build_session_workflow_state(
                        'queued',
                        pending_exercises=pending_exercise_snapshot,
                    ),
                )
        except IntegrityError:
            _delete_pending_exercise_snapshot_files(locals().get('pending_exercise_snapshot', []))
            # Double-submit race: another request already created the session.
            if client_request_id is not None:
                existing = ClassCreationSession.objects.filter(
                    teacher=request.user, client_request_id=client_request_id,
                ).first()
                if existing is not None:
                    return Response(
                        Step1TranscribeResponseSerializer(existing).data,
                        status=status.HTTP_202_ACCEPTED,
                    )
            return Response(
                {'detail': 'درخواست تکراری. لطفاً دوباره تلاش کنید.'},
                status=status.HTTP_409_CONFLICT,
            )
        except Exception as exc:
            _delete_pending_exercise_snapshot_files(locals().get('pending_exercise_snapshot', []))
            logger.exception(
                'Failed to create session (file upload to storage failed): %s', exc,
            )
            return Response(
                {'detail': 'فایل آپلود نشد. لطفاً دوباره تلاش کنید.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        logger.info(
            "STEP1 CREATED session=%s source_type=%s stored_file=%r async=%s full=%s",
            session.id, session.source_type, session.source_file.name,
            getattr(settings, 'CLASS_PIPELINE_ASYNC', False), run_full_pipeline,
        )

        if run_full_pipeline:
            _dispatch_pipeline_task(session, process_class_full_pipeline)
            return Response(Step1TranscribeResponseSerializer(session).data, status=status.HTTP_202_ACCEPTED)

        if getattr(settings, 'CLASS_PIPELINE_ASYNC', False):
            # Dispatch to Celery so the teacher can navigate away without breaking the pipeline.
            _dispatch_pipeline_task(session, process_class_step1_transcription)
            return Response(Step1TranscribeResponseSerializer(session).data, status=status.HTTP_202_ACCEPTED)

        try:
            session.source_file.open('rb')
            try:
                data = session.source_file.read()
            finally:
                session.source_file.close()

            transcript, provider, model_name, page_count = _ingest_for_session(session, data)
            session.transcript_markdown = transcript
            session.llm_provider = provider
            session.llm_model = model_name
            session.source_page_count = page_count
            session.status = ClassCreationSession.Status.TRANSCRIBED
            session.save(update_fields=['transcript_markdown', 'llm_provider', 'llm_model', 'source_page_count', 'status', 'updated_at'])

            # Delete uploaded file — only transcript text is needed from now on.
            try:
                if session.source_file:
                    session.source_file.delete(save=False)
                    session.source_file = None
                    session.save(update_fields=['source_file', 'updated_at'])
            except Exception:
                logger.warning('Failed to cleanup source file for session %s', session.id)

            return Response(Step1TranscribeResponseSerializer(session).data, status=status.HTTP_201_CREATED)
        except Exception as exc:
            session.status = ClassCreationSession.Status.FAILED
            session.error_detail = str(exc)
            session.save(update_fields=['status', 'error_detail', 'updated_at'])
            return Response(
                {
                    'detail': 'Transcription provider failed.',
                    'session_id': session.id,
                    'status': session.status,
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )


class Step2StructureView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    @extend_schema(
        tags=['Classes'],
        summary='Step 2: Structure (outline/units) from transcript',
        request=Step2StructureRequestSerializer,
        responses={202: Step2StructureResponseSerializer, 200: Step2StructureResponseSerializer},
    )
    def post(self, request):
        serializer = Step2StructureRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session_id = serializer.validated_data['session_id']
        session = ClassCreationSession.objects.filter(id=session_id, teacher=request.user).first()
        if session is None:
            return Response({'detail': 'جلسه پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        if session.status == ClassCreationSession.Status.STRUCTURED and (session.structure_json or '').strip():
            return Response(Step2StructureResponseSerializer(session).data, status=status.HTTP_200_OK)

        if session.status == ClassCreationSession.Status.STRUCTURING:
            return Response(Step2StructureResponseSerializer(session).data, status=status.HTTP_202_ACCEPTED)

        # Only allow transition from TRANSCRIBED (step-1 completed).
        if session.status != ClassCreationSession.Status.TRANSCRIBED:
            return Response(
                {'detail': f'مرحله ۲ فقط بعد از تکمیل مرحله ۱ قابل اجراست. وضعیت فعلی: {session.get_status_display()}'},
                status=status.HTTP_409_CONFLICT,
            )

        if not (session.transcript_markdown or '').strip():
            return Response({'detail': 'برای این جلسه هنوز متن درس آماده نیست.'}, status=status.HTTP_400_BAD_REQUEST)

        # Atomic status transition with row-level lock to prevent races.
        with transaction.atomic():
            locked = ClassCreationSession.objects.select_for_update().filter(
                id=session_id, status=ClassCreationSession.Status.TRANSCRIBED,
            ).first()
            if locked is None:
                session.refresh_from_db()
                return Response(Step2StructureResponseSerializer(session).data, status=status.HTTP_202_ACCEPTED)
            locked.status = ClassCreationSession.Status.STRUCTURING
            locked.save(update_fields=['status', 'updated_at'])
            session = locked

        if getattr(settings, 'CLASS_PIPELINE_ASYNC', False):
            transaction.on_commit(lambda: process_class_step2_structure.delay(session.id))
            return Response(Step2StructureResponseSerializer(session).data, status=status.HTTP_202_ACCEPTED)

        try:
            structure_obj, provider, model_name = structure_transcript_markdown(
                transcript_markdown=session.transcript_markdown,
            )
            session.structure_json = json.dumps(structure_obj, ensure_ascii=False)
            session.llm_provider = provider
            session.llm_model = model_name
            session.status = ClassCreationSession.Status.STRUCTURED
            session.save(update_fields=['structure_json', 'llm_provider', 'llm_model', 'status', 'updated_at'])
            sync_structure_from_session(session=session)
            return Response(Step2StructureResponseSerializer(session).data, status=status.HTTP_200_OK)
        except Exception as exc:
            session.status = ClassCreationSession.Status.FAILED
            session.error_detail = str(exc)
            session.save(update_fields=['status', 'error_detail', 'updated_at'])
            return Response(
                {
                    'detail': 'Structuring provider failed.',
                    'session_id': session.id,
                    'status': session.status,
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )


class Step3PrerequisitesView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    @extend_schema(
        tags=['Classes'],
        summary='Step 3: Build prerequisites from transcript',
        request=Step3PrerequisitesRequestSerializer,
        responses={202: Step3PrerequisitesResponseSerializer, 200: Step3PrerequisitesResponseSerializer},
    )
    def post(self, request):
        serializer = Step3PrerequisitesRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session_id = serializer.validated_data['session_id']
        session = ClassCreationSession.objects.filter(id=session_id, teacher=request.user).first()
        if session is None:
            return Response({'detail': 'جلسه پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        if session.status == ClassCreationSession.Status.PREREQ_EXTRACTED and session.prerequisites.exists():
            return Response(Step3PrerequisitesResponseSerializer(session).data, status=status.HTTP_200_OK)

        if session.status == ClassCreationSession.Status.PREREQ_EXTRACTING:
            return Response(Step3PrerequisitesResponseSerializer(session).data, status=status.HTTP_202_ACCEPTED)

        # Only allow transition from STRUCTURED (step-2 completed).
        if session.status != ClassCreationSession.Status.STRUCTURED:
            return Response(
                {'detail': f'مرحله ۳ فقط بعد از تکمیل مرحله ۲ قابل اجراست. وضعیت فعلی: {session.get_status_display()}'},
                status=status.HTTP_409_CONFLICT,
            )

        if not (session.transcript_markdown or '').strip():
            return Response({'detail': 'برای این جلسه هنوز متن درس آماده نیست.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            locked = ClassCreationSession.objects.select_for_update().filter(
                id=session_id, status=ClassCreationSession.Status.STRUCTURED,
            ).first()
            if locked is None:
                session.refresh_from_db()
                return Response(Step3PrerequisitesResponseSerializer(session).data, status=status.HTTP_202_ACCEPTED)
            locked.status = ClassCreationSession.Status.PREREQ_EXTRACTING
            locked.save(update_fields=['status', 'updated_at'])
            session = locked

        if getattr(settings, 'CLASS_PIPELINE_ASYNC', False):
            transaction.on_commit(lambda: process_class_step3_prerequisites.delay(session.id))
            return Response(Step3PrerequisitesResponseSerializer(session).data, status=status.HTTP_202_ACCEPTED)

        _process_step3_prerequisites(session.id)
        session.refresh_from_db()
        return Response(Step3PrerequisitesResponseSerializer(session).data, status=status.HTTP_200_OK)


class Step4PrerequisiteTeachingView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    @extend_schema(
        tags=['Classes'],
        summary='Step 4: Build teaching notes for each prerequisite',
        request=Step4PrerequisiteTeachingRequestSerializer,
        responses={202: Step4PrerequisiteTeachingResponseSerializer, 200: Step4PrerequisiteTeachingResponseSerializer},
    )
    def post(self, request):
        serializer = Step4PrerequisiteTeachingRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session_id = serializer.validated_data['session_id']
        prerequisite_name = (serializer.validated_data.get('prerequisite_name') or '').strip() or None

        session = ClassCreationSession.objects.filter(id=session_id, teacher=request.user).first()
        if session is None:
            return Response({'detail': 'جلسه پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        if session.status == ClassCreationSession.Status.PREREQ_TAUGHT:
            return Response(Step4PrerequisiteTeachingResponseSerializer(session).data, status=status.HTTP_200_OK)

        if session.status == ClassCreationSession.Status.PREREQ_TEACHING:
            return Response(Step4PrerequisiteTeachingResponseSerializer(session).data, status=status.HTTP_202_ACCEPTED)

        # Only allow transition from PREREQ_EXTRACTED (step-3 completed).
        if session.status != ClassCreationSession.Status.PREREQ_EXTRACTED:
            return Response(
                {'detail': f'مرحله ۴ فقط بعد از تکمیل مرحله ۳ قابل اجراست. وضعیت فعلی: {session.get_status_display()}'},
                status=status.HTTP_409_CONFLICT,
            )

        if not session.prerequisites.exists():
            return Response({'detail': 'ابتدا مرحله پیش نیازها را اجرا کنید.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            locked = ClassCreationSession.objects.select_for_update().filter(
                id=session_id, status=ClassCreationSession.Status.PREREQ_EXTRACTED,
            ).first()
            if locked is None:
                session.refresh_from_db()
                return Response(Step4PrerequisiteTeachingResponseSerializer(session).data, status=status.HTTP_202_ACCEPTED)
            locked.status = ClassCreationSession.Status.PREREQ_TEACHING
            locked.save(update_fields=['status', 'updated_at'])
            session = locked

        if getattr(settings, 'CLASS_PIPELINE_ASYNC', False):
            transaction.on_commit(lambda: process_class_step4_prereq_teaching.delay(session.id, prerequisite_name))
            return Response(Step4PrerequisiteTeachingResponseSerializer(session).data, status=status.HTTP_202_ACCEPTED)

        _process_step4_prereq_teaching(session.id, prerequisite_name)
        session.refresh_from_db()
        return Response(Step4PrerequisiteTeachingResponseSerializer(session).data, status=status.HTTP_200_OK)


class Step5RecapView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    @extend_schema(
        tags=['Classes'],
        summary='Step 5: Build end-of-course recap from structured content',
        request=Step5RecapRequestSerializer,
        responses={202: Step5RecapResponseSerializer, 200: Step5RecapResponseSerializer},
    )
    def post(self, request):
        serializer = Step5RecapRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session_id = serializer.validated_data['session_id']
        session = ClassCreationSession.objects.filter(id=session_id, teacher=request.user).first()
        if session is None:
            return Response({'detail': 'جلسه پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        if session.status == ClassCreationSession.Status.RECAPPED and (session.recap_markdown or '').strip():
            return Response(Step5RecapResponseSerializer(session).data, status=status.HTTP_200_OK)

        if session.status == ClassCreationSession.Status.RECAPPING:
            return Response(Step5RecapResponseSerializer(session).data, status=status.HTTP_202_ACCEPTED)

        # Only allow transition from PREREQ_TAUGHT (step-4 completed).
        if session.status != ClassCreationSession.Status.PREREQ_TAUGHT:
            return Response(
                {'detail': f'مرحله ۵ فقط بعد از تکمیل مرحله ۴ قابل اجراست. وضعیت فعلی: {session.get_status_display()}'},
                status=status.HTTP_409_CONFLICT,
            )

        if not (session.structure_json or '').strip():
            return Response({'detail': 'برای این جلسه هنوز ساختار مرحله ۲ آماده نیست.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            locked = ClassCreationSession.objects.select_for_update().filter(
                id=session_id, status=ClassCreationSession.Status.PREREQ_TAUGHT,
            ).first()
            if locked is None:
                session.refresh_from_db()
                return Response(Step5RecapResponseSerializer(session).data, status=status.HTTP_202_ACCEPTED)
            locked.status = ClassCreationSession.Status.RECAPPING
            locked.save(update_fields=['status', 'updated_at'])
            session = locked

        if getattr(settings, 'CLASS_PIPELINE_ASYNC', False):
            transaction.on_commit(lambda: process_class_step5_recap.delay(session.id))
            return Response(Step5RecapResponseSerializer(session).data, status=status.HTTP_202_ACCEPTED)

        _process_step5_recap(session.id)
        session.refresh_from_db()
        return Response(Step5RecapResponseSerializer(session).data, status=status.HTTP_200_OK)


class ClassPrerequisiteListView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    @extend_schema(
        tags=['Classes'],
        summary='List prerequisites for a session (teacher)',
        responses={200: PrerequisiteSerializer(many=True)},
    )
    def get(self, request, session_id: int):
        session = ClassCreationSession.objects.filter(id=session_id, teacher=request.user).first()
        if session is None:
            return Response({'detail': 'جلسه پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        qs = session.prerequisites.order_by('order')
        return Response(PrerequisiteSerializer(qs, many=True).data)


class ClassCreationSessionListView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    @extend_schema(
        tags=['Classes'],
        summary='List class creation sessions (teacher)',
        operation_id='classes_creation_sessions_list',
        parameters=[
            OpenApiParameter(
                name='organization',
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Filter by organization ID, or "personal" for classes without an organization.',
            ),
        ],
        responses={200: ClassCreationSessionListSerializer(many=True)},
    )
    def get(self, request):
        qs = ClassCreationSession.objects.filter(
            teacher=request.user,
            pipeline_type=ClassCreationSession.PipelineType.CLASS,
        )

        org_param = request.query_params.get('organization')
        if org_param == 'personal':
            qs = qs.filter(organization__isnull=True)
        elif org_param and org_param.isdigit():
            qs = qs.filter(organization_id=int(org_param))
        # If no param given, return all classes (backward compatible)

        qs = qs.annotate(
            _students_count=Count('enrollments__student_id', distinct=True),
            _invites_count=Count('enrollments__student_id', distinct=True),
            _lessons_count=Count('units', distinct=True),
        ).order_by('-created_at')
        return Response(ClassCreationSessionListSerializer(qs, many=True).data)


class ClassCreationSessionDetailView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    @extend_schema(
        tags=['Classes'],
        summary='Get class creation session detail (teacher)',
        operation_id='classes_creation_sessions_detail',
        responses={200: ClassCreationSessionDetailSerializer},
    )
    def get(self, request, session_id: int):
        session = ClassCreationSession.objects.filter(id=session_id, teacher=request.user).first()
        if session is None:
            return Response({'detail': 'جلسه پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(ClassCreationSessionDetailSerializer(session).data)

    @extend_schema(
        tags=['Classes'],
        summary='Update a class creation session (teacher)',
        operation_id='classes_creation_sessions_update',
        request=ClassCreationSessionUpdateSerializer,
        responses={200: ClassCreationSessionDetailSerializer},
    )
    def patch(self, request, session_id: int):
        session = ClassCreationSession.objects.filter(id=session_id, teacher=request.user).first()
        if session is None:
            return Response({'detail': 'جلسه پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ClassCreationSessionUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        updated_fields: list[str] = []
        if 'title' in serializer.validated_data:
            session.title = serializer.validated_data['title']
            updated_fields.append('title')
        if 'description' in serializer.validated_data:
            session.description = serializer.validated_data['description']
            updated_fields.append('description')
        if 'level' in serializer.validated_data:
            session.level = serializer.validated_data['level']
            updated_fields.append('level')
        if 'duration' in serializer.validated_data:
            session.duration = serializer.validated_data['duration']
            updated_fields.append('duration')
        if 'structure_json' in serializer.validated_data:
            session.structure_json = serializer.validated_data['structure_json']
            updated_fields.append('structure_json')

        if updated_fields:
            updated_fields.append('updated_at')
            session.save(update_fields=updated_fields)

        if 'structure_json' in serializer.validated_data:
            sync_structure_from_session(session=session)

        return Response(ClassCreationSessionDetailSerializer(session).data)

    @extend_schema(
        tags=['Classes'],
        summary='Delete a class creation session (teacher)',
        operation_id='classes_creation_sessions_delete',
        responses={204: None},
    )
    def delete(self, request, session_id: int):
        session = ClassCreationSession.objects.filter(id=session_id, teacher=request.user).first()
        if session is None:
            return Response({'detail': 'جلسه پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        session.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def _cancel_session_pipeline(session) -> None:
    """Stop a running pipeline for ``session`` as precisely as possible.

    Two complementary mechanisms run together:

    1. **Cooperative flag** — set ``cancel_requested`` and move the row to the
       terminal ``CANCELLED`` status *first*, in one ``update_fields`` save.
       The full-pipeline tasks check this at every step boundary, so even a
       step that survives revoke (or a task re-queued by ``acks_late``) stops
       at the next checkpoint instead of running to completion.
    2. **Hard revoke** — ``app.control.revoke(..., terminate=True)`` sends
       SIGTERM to the worker child currently executing the task, killing an
       in-flight step (e.g. a long LLM call) immediately.

    Revoke is best-effort: a broker hiccup must never block the DB transition,
    because the cooperative flag already guarantees the pipeline will stop.
    Idempotent — calling it on an already-cancelled session is a harmless no-op.
    """
    session.cancel_requested = True
    session.status = ClassCreationSession.Status.CANCELLED
    session.save(update_fields=['cancel_requested', 'status', 'updated_at'])
    artifact = ExamPrepExtractionArtifact.objects.filter(
        session_id=session.id,
        pipeline_version__gte=3,
    ).first()
    if artifact is not None:
        from .services.exam_prep_v3 import source_retention_deadline

        artifact.source_retain_until = source_retention_deadline()
        artifact.active_task_id = ''
        artifact.save(
            update_fields=['source_retain_until', 'active_task_id', 'updated_at']
        )

    task_id = (session.celery_task_id or '').strip()
    if task_id:
        try:
            from core.celery import app as celery_app
            celery_app.control.revoke(task_id, terminate=True, signal='SIGTERM')
        except Exception:
            logger.warning(
                'Failed to revoke Celery task %s for session %s (cooperative '
                'cancel flag still set).', task_id, session.id, exc_info=True,
            )


class ClassCreationSessionCancelView(APIView):
    """Cancel a running class-creation pipeline (teacher, owner-only)."""
    permission_classes = [IsAuthenticated, IsTeacherUser]

    @extend_schema(
        tags=['Classes'],
        summary='Cancel a running class creation pipeline (teacher)',
        operation_id='classes_creation_sessions_cancel',
        request=None,
        responses={200: ClassCreationSessionDetailSerializer, 404: OpenApiTypes.OBJECT, 409: OpenApiTypes.OBJECT},
    )
    def post(self, request, session_id: int):
        session = ClassCreationSession.objects.filter(
            id=session_id,
            teacher=request.user,
            pipeline_type=ClassCreationSession.PipelineType.CLASS,
        ).first()
        if session is None:
            return Response({'detail': 'جلسه پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        if not session.is_active_pipeline:
            return Response(
                {'detail': f'این جلسه در وضعیت «{session.get_status_display()}» است و قابل لغو نیست.'},
                status=status.HTTP_409_CONFLICT,
            )

        _cancel_session_pipeline(session)
        return Response(ClassCreationSessionDetailSerializer(session).data, status=status.HTTP_200_OK)


class ClassCreationSessionPublishView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]
    serializer_class = ClassCreationSessionDetailSerializer

    @extend_schema(
        tags=['Classes'],
        summary='Publish a class creation session (teacher)',
        operation_id='classes_creation_sessions_publish',
        request=None,
        responses={200: ClassCreationSessionDetailSerializer},
    )
    def post(self, request, session_id: int):
        session = ClassCreationSession.objects.filter(id=session_id, teacher=request.user).first()
        if session is None:
            return Response({'detail': 'جلسه پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        if session.is_published:
            return Response(ClassCreationSessionDetailSerializer(session).data)

        if session.status == ClassCreationSession.Status.FAILED:
            return Response({'detail': 'این جلسه با خطا متوقف شده است.'}, status=status.HTTP_400_BAD_REQUEST)

        if session.status != ClassCreationSession.Status.RECAPPED:
            return Response({'detail': 'برای انتشار، ابتدا پردازش کلاس را کامل کنید.'}, status=status.HTTP_409_CONFLICT)

        if not (session.structure_json or '').strip():
            return Response({'detail': 'برای انتشار، ابتدا ساختاردهی را کامل کنید.'}, status=status.HTTP_400_BAD_REQUEST)

        # Atomic update to prevent double publish from concurrent requests.
        now = timezone.now()
        updated = ClassCreationSession.objects.filter(
            id=session.id, is_published=False,
        ).update(is_published=True, published_at=now, updated_at=now)

        if updated:
            session.is_published = True
            session.published_at = now
            # Org class → its roster is the linked study group. Enroll the
            # group's active students now (idempotent) so they see the class
            # on publish; manual invites are blocked for org classes.
            try:
                from .services.org_roster import sync_org_class_roster
                sync_org_class_roster(session)
            except Exception:
                logger.warning('org roster sync on publish failed session=%s', session.id, exc_info=True)
            def _dispatch_publish_sms():
                logger.info('[SMS] Dispatching send_publish_sms_task for session=%s', session.id)
                send_publish_sms_task.delay(session.id)
            transaction.on_commit(_dispatch_publish_sms)

        return Response(ClassCreationSessionDetailSerializer(session).data)


class ClassInvitationListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    @extend_schema(
        tags=['Classes'],
        summary='List class invitations for a session (teacher)',
        operation_id='classes_creation_sessions_invites_list',
        responses={200: ClassInvitationSerializer(many=True)},
    )
    def get(self, request, session_id: int):
        session = ClassCreationSession.objects.filter(id=session_id, teacher=request.user).first()
        if session is None:
            return Response({'detail': 'جلسه پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        qs = ClassInvitation.objects.filter(session=session).order_by('-created_at')
        return Response(ClassInvitationSerializer(qs, many=True).data)

    @extend_schema(
        tags=['Classes'],
        summary='Create class invitations for a session (teacher)',
        operation_id='classes_creation_sessions_invites_create',
        request=ClassInvitationCreateSerializer,
        responses={200: ClassInvitationSerializer(many=True)},
    )
    def post(self, request, session_id: int):
        session = ClassCreationSession.objects.filter(id=session_id, teacher=request.user).first()
        if session is None:
            return Response({'detail': 'جلسه پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        # Org classes get their roster from the linked study group (manager-owned);
        # a teacher may not hand-invite arbitrary students into them.
        if session.organization_id is not None:
            return Response(
                {'detail': 'دانش‌آموزانِ کلاس‌های سازمان آموزشی از طریق «گروه آموزشی» توسط مدیر سازمان آموزشی تعیین می‌شوند.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ClassInvitationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phones: list[str] = serializer.validated_data['phones']

        # Bulk check existing invitations (1 query instead of N).
        existing_phones = set(
            ClassInvitation.objects.filter(
                session=session, phone__in=phones,
            ).values_list('phone', flat=True)
        )
        new_invites = []
        new_phones = []
        for phone in phones:
            if phone in existing_phones:
                continue
            code = get_or_create_invite_code_for_phone(phone)
            new_invites.append(ClassInvitation(session=session, phone=phone, invite_code=code))
            new_phones.append(phone)
        if new_invites:
            ClassInvitation.objects.bulk_create(new_invites, ignore_conflicts=True)

        # If session is already published, send SMS to newly added students.
        if new_phones and session.is_published:
            invite_ids = list(
                ClassInvitation.objects.filter(
                    session=session, phone__in=new_phones,
                ).values_list('id', flat=True)
            )
            if invite_ids:
                _sid = session.id
                def _dispatch_class_invite_sms(ids=invite_ids, sid=_sid):
                    logger.info('[SMS] Dispatching send_new_invites_sms_task session=%s invites=%d', sid, len(ids))
                    send_new_invites_sms_task.delay(sid, ids)
                transaction.on_commit(_dispatch_class_invite_sms)

        qs = ClassInvitation.objects.filter(session=session).order_by('-created_at')
        return Response(ClassInvitationSerializer(qs, many=True).data)


class ClassInvitationDetailView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    @extend_schema(
        tags=['Classes'],
        summary='Delete a class invitation (teacher)',
        operation_id='classes_creation_sessions_invites_delete',
        responses={204: None},
    )
    def delete(self, request, session_id: int, invite_id: int):
        session = ClassCreationSession.objects.filter(id=session_id, teacher=request.user).first()
        if session is None:
            return Response({'detail': 'جلسه پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        # Org class rosters are managed by the org (via study groups), not the teacher.
        if session.organization_id is not None:
            return Response(
                {'detail': 'دانش‌آموزانِ کلاس‌های سازمان آموزشی از طریق «گروه آموزشی» توسط مدیر سازمان آموزشی تعیین می‌شوند.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        invite = ClassInvitation.objects.filter(id=invite_id, session=session).first()
        if invite is None:
            return Response({'detail': 'دعوت نامه پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        invite.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ClassSessionStudentsView(APIView):
    """Real per-session student roster for the teacher (name, progress, score, status).

    Unlike ``.../invites/`` (pending invite rows), this starts from Enrollment
    and reports real per-session progress
    (completed units), average quiz/exam score, and active/inactive status.
    """

    permission_classes = [IsAuthenticated, IsTeacherUser]

    @extend_schema(
        tags=['Classes'],
        summary='Real per-session student roster (teacher)',
        operation_id='classes_creation_sessions_students',
        responses={200: ClassSessionStudentSerializer(many=True)},
    )
    def get(self, request, session_id: int):
        session = ClassCreationSession.objects.filter(id=session_id, teacher=request.user).first()
        if session is None:
            return Response({'detail': 'جلسه پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        from .services.teacher_students import serialize_session_students
        rows = serialize_session_students(session=session)
        return Response(ClassSessionStudentSerializer(rows, many=True).data, status=status.HTTP_200_OK)


class ClassAnnouncementListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    @extend_schema(
        tags=['Classes'],
        summary='List class announcements for a session (teacher)',
        operation_id='classes_creation_sessions_announcements_list',
        responses={200: ClassAnnouncementSerializer(many=True)},
    )
    def get(self, request, session_id: int):
        session = ClassCreationSession.objects.filter(id=session_id, teacher=request.user).first()
        if session is None:
            return Response({'detail': 'جلسه پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        qs = ClassAnnouncement.objects.filter(session=session).order_by('-created_at')
        return Response(ClassAnnouncementSerializer(qs, many=True).data)

    @extend_schema(
        tags=['Classes'],
        summary='Create class announcement for a session (teacher)',
        operation_id='classes_creation_sessions_announcements_create',
        request=ClassAnnouncementCreateSerializer,
        responses={201: ClassAnnouncementSerializer},
    )
    def post(self, request, session_id: int):
        session = ClassCreationSession.objects.filter(id=session_id, teacher=request.user).first()
        if session is None:
            return Response({'detail': 'جلسه پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ClassAnnouncementCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        announcement = ClassAnnouncement.objects.create(
            session=session,
            title=serializer.validated_data['title'],
            content=serializer.validated_data['content'],
            priority=serializer.validated_data.get('priority', ClassAnnouncement.Priority.MEDIUM),
        )
        return Response(ClassAnnouncementSerializer(announcement).data, status=status.HTTP_201_CREATED)


class ClassAnnouncementDetailView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    @extend_schema(
        tags=['Classes'],
        summary='Update class announcement (teacher)',
        operation_id='classes_creation_sessions_announcements_update',
        request=ClassAnnouncementUpdateSerializer,
        responses={200: ClassAnnouncementSerializer},
    )
    def patch(self, request, session_id: int, announcement_id: int):
        session = ClassCreationSession.objects.filter(id=session_id, teacher=request.user).first()
        if session is None:
            return Response({'detail': 'جلسه پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        announcement = ClassAnnouncement.objects.filter(id=announcement_id, session=session).first()
        if announcement is None:
            return Response({'detail': 'اطلاعیه پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ClassAnnouncementUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        updated_fields = []
        if 'title' in data:
            announcement.title = data['title']
            updated_fields.append('title')
        if 'content' in data:
            announcement.content = data['content']
            updated_fields.append('content')
        if 'priority' in data:
            announcement.priority = data['priority']
            updated_fields.append('priority')
        if updated_fields:
            updated_fields.append('updated_at')
            announcement.save(update_fields=updated_fields)
        return Response(ClassAnnouncementSerializer(announcement).data)

    @extend_schema(
        tags=['Classes'],
        summary='Delete class announcement (teacher)',
        operation_id='classes_creation_sessions_announcements_delete',
        responses={204: None},
    )
    def delete(self, request, session_id: int, announcement_id: int):
        session = ClassCreationSession.objects.filter(id=session_id, teacher=request.user).first()
        if session is None:
            return Response({'detail': 'جلسه پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        announcement = ClassAnnouncement.objects.filter(id=announcement_id, session=session).first()
        if announcement is None:
            return Response({'detail': 'اطلاعیه پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        announcement.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TeacherAnalyticsStatsView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    @extend_schema(
        tags=['Classes'],
        summary='Teacher analytics: overview stats',
        operation_id='teacher_analytics_stats',
        responses={200: TeacherAnalyticsStatSerializer(many=True)},
    )
    def get(self, request):
        qs = ClassCreationSession.objects.filter(teacher=request.user)
        total_classes = qs.filter(pipeline_type='class').count()
        total_exams = qs.filter(pipeline_type='exam_prep').count()
        
        # This is an all-time roster total. The selected chart window must not
        # make the dashboard's "total students" disagree with /teacher/students.
        students_count = Enrollment.objects.filter(
            session__teacher=request.user,
            session__pipeline_type=ClassCreationSession.PipelineType.CLASS,
        ).values('student_id').distinct().count()

        return Response(
            [
                {'title': 'کل کلاس‌های ساخته شده', 'value': str(total_classes), 'icon': 'book', 'change': '—', 'trend': 'up'},
                {'title': 'آمادگی آزمون‌های فعال', 'value': str(total_exams), 'icon': 'graduation', 'change': '—', 'trend': 'up'},
                {'title': 'کل دانش‌آموزان', 'value': str(students_count), 'icon': 'users', 'change': '—', 'trend': 'up'},
            ]
        )


class TeacherStudentsListView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    @extend_schema(
        tags=['Classes'],
        summary='Teacher students list',
        operation_id='teacher_students_list',
        responses={200: TeacherStudentSerializer(many=True)},
    )
    def get(self, request):
        from .services.teacher_students import serialize_teacher_students

        out = serialize_teacher_students(teacher=request.user)
        return Response(TeacherStudentSerializer(out, many=True).data, status=status.HTTP_200_OK)


class TeacherAnalyticsChartView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    @extend_schema(
        tags=['Classes'],
        summary='Teacher analytics: chart data',
        operation_id='teacher_analytics_chart',
        responses={200: TeacherAnalyticsChartPointSerializer(many=True)},
    )
    def get(self, request):
        try:
            days = int(request.query_params.get('days', 7))
        except (TypeError, ValueError):
            days = 7
        days = max(1, min(days, 365))
        today = timezone.localdate()
        start_date = today - timedelta(days=days-1)
        
        count_map: dict = {}
        first_enrollments = (
            Enrollment.objects.filter(
                session__teacher=request.user,
                session__pipeline_type=ClassCreationSession.PipelineType.CLASS,
            )
            .values('student_id')
            .annotate(first_joined_at=Min('joined_at'))
        )
        for item in first_enrollments:
            first_joined_at = item['first_joined_at']
            if first_joined_at is None:
                continue
            joined_date = timezone.localtime(first_joined_at).date()
            if start_date <= joined_date <= today:
                count_map[joined_date] = count_map.get(joined_date, 0) + 1
        
        data = []
        for i in range(days - 1, -1, -1):
            d = today - timedelta(days=i)
            data.append({
                'name': d.isoformat(), 
                'students': count_map.get(d, 0)
            })
            
        return Response(data)


class TeacherAnalyticsExportCSVView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    @extend_schema(
        tags=['Classes'],
        summary='Teacher analytics: export report (CSV)',
        operation_id='teacher_analytics_export_csv',
    )
    def get(self, request):
        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = 'attachment; filename="teacher_analytics_report.csv"'
        
        writer = csv.writer(response)
        
        # Summary Header
        writer.writerow(['گزارش تحلیلی معلم - پلتفرم AI_AMOOZ'])
        writer.writerow(['تاریخ گزارش', timezone.now().strftime('%Y/%m/%d %H:%M')])
        writer.writerow([])
        
        writer.writerow(['عنوان شاخص', 'مقدار'])
        
        # Stats
        qs = ClassCreationSession.objects.filter(teacher=request.user)
        total_classes = qs.filter(pipeline_type='class').count()
        total_exams = qs.filter(pipeline_type='exam_prep').count()
        
        students_count = Enrollment.objects.filter(
            session__teacher=request.user,
            session__pipeline_type=ClassCreationSession.PipelineType.CLASS,
        ).values('student_id').distinct().count()
        
        writer.writerow(['کل کلاس‌های ساخته شده', total_classes])
        writer.writerow(['آمادگی آزمون‌های فعال', total_exams])
        writer.writerow(['کل دانش‌آموزان', students_count])
        writer.writerow([])
        
        # Detailed activity summary (Last 30 days)
        writer.writerow(['روند ثبت‌نام‌ها در ۳۰ روز اخیر'])
        writer.writerow(['تاریخ', 'تعداد ثبت‌نام'])
        
        from django.db.models.functions import TruncDate
        start_date = timezone.localdate() - timedelta(days=29)
        chart_counts = (
            Enrollment.objects.filter(
                session__teacher=request.user,
                session__pipeline_type=ClassCreationSession.PipelineType.CLASS,
                joined_at__date__gte=start_date,
            )
            .annotate(date=TruncDate('joined_at'))
            .values('date')
            .annotate(count=Count('student_id', distinct=True))
            .order_by('date')
        )
        for c in chart_counts:
            writer.writerow([c['date'], c['count']])
            
        return response


class TeacherAnalyticsDistributionView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    @extend_schema(
        tags=['Classes'],
        summary='Teacher analytics: distribution data',
        operation_id='teacher_analytics_distribution',
        responses={200: TeacherAnalyticsDistributionItemSerializer(many=True)},
    )
    def get(self, request):
        from django.db.models import Count
        
        # This panel is class-only and uses the same unique-student definition
        # as the class roster and class cards.
        sessions = (
            ClassCreationSession.objects.filter(
                teacher=request.user,
                pipeline_type=ClassCreationSession.PipelineType.CLASS,
            )
            .annotate(
                students_count=Count('enrollments__student_id', distinct=True)
            )
            .filter(students_count__gt=0)
            .order_by('-students_count')[:5]
        )
        
        data = []
        for s in sessions:
            data.append({'name': s.title, 'value': s.students_count})
            
        if not data:
            # Fallback for empty state to avoid empty chart display issues if any
            return Response([{'name': 'هنوز موردی ثبت نشده', 'value': 0}])
            
        return Response(data)


class TeacherAnalyticsActivitiesView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    @extend_schema(
        tags=['Classes'],
        summary='Teacher analytics: recent activity',
        operation_id='teacher_analytics_activities',
        responses={200: TeacherAnalyticsActivitySerializer(many=True)},
    )
    def get(self, request):
        # Combine recent sessions and recent invites for a better activity feed
        sessions = ClassCreationSession.objects.filter(teacher=request.user).order_by('-created_at')[:5]
        invites = _teacher_student_invites(request.user).select_related('session').order_by('-created_at')[:5]
        
        items = []
        for s in sessions:
            type_label = "کلاس" if s.pipeline_type == 'class' else "آزمون"
            items.append({
                'id': f"session-{s.id}",
                'type': 'class_creation',
                'user': request.user.first_name or request.user.username,
                'action': f"ایجاد {type_label}: {s.title}",
                'time': s.created_at.isoformat(),
                'icon': 'book' if s.pipeline_type == 'class' else 'graduation',
                'color': 'text-primary' if s.pipeline_type == 'class' else 'text-emerald-500',
                'bg': 'bg-primary/10' if s.pipeline_type == 'class' else 'bg-emerald-500/10',
            })
            
        for inv in invites:
            items.append({
                'id': f"invite-{inv.id}",
                'type': 'enrollment',
                'user': inv.phone,
                'action': f"دانش‌آموز با شماره {inv.phone} به «{inv.session.title}» دعوت شد.",
                'time': inv.created_at.isoformat(),
                'icon': 'users',
                'color': 'text-blue-500',
                'bg': 'bg-blue-500/10',
            })
            
        # Re-sort by time and take top 10
        items.sort(key=lambda x: x['time'], reverse=True)
        return Response(items[:10])


class StudentCourseListView(APIView):
    permission_classes = [IsAuthenticated, IsStudentUser]

    @extend_schema(
        tags=['Classes'],
        summary='List student courses (published classes accessible to the student)',
        operation_id='student_courses_list',
        responses={200: StudentCourseSerializer(many=True)},
    )
    def get(self, request):
        user = request.user
        phone = (getattr(user, 'phone', None) or '').strip()
        if not phone:
            return Response([], status=status.HTTP_200_OK)

        qs = (
            ClassCreationSession.objects.filter(
                is_published=True,
                pipeline_type=ClassCreationSession.PipelineType.CLASS,
                invites__phone=phone,
            )
            .select_related('teacher')
            .prefetch_related('sections__units', 'invites')
            .annotate(
                _students_count=Count('enrollments__student_id', distinct=True),
            )
            .distinct()
            .order_by('-published_at', '-updated_at')
        )

        out: list[dict] = []
        for session in qs:
            teacher = session.teacher
            instructor = ''
            if teacher is not None:
                instructor = (teacher.get_full_name() or getattr(teacher, 'username', '') or '').strip()

            # Use prefetched data — len() hits the cache, .count() would issue a new query.
            lessons_count = 0
            try:
                lessons_count = sum(len(s.units.all()) for s in session.sections.all())
            except Exception:
                lessons_count = 0

            out.append(
                {
                    'id': session.id,
                    'title': session.title,
                    'description': session.description or '',
                    'tags': [],
                    'instructor': instructor,
                    'progress': _compute_student_course_progress(session=session, student=user),
                    'studentsCount': session._students_count,
                    'lessonsCount': lessons_count,
                    'status': 'active',
                    'createdAt': (session.published_at or session.created_at).date().isoformat(),
                    'lastActivity': (session.updated_at or session.created_at).date().isoformat(),
                    'sourceType': session.source_type,
                }
            )

        return Response(StudentCourseSerializer(out, many=True).data)


class StudentCourseContentView(APIView):
    permission_classes = [IsAuthenticated, IsStudentUser]

    @extend_schema(
        tags=['Classes'],
        summary='Get student course content (chapters/lessons) for a published class',
        operation_id='student_course_content',
        responses={200: StudentCourseContentSerializer},
    )
    def get(self, request, session_id: int):
        user = request.user
        phone = (getattr(user, 'phone', None) or '').strip()
        if not phone:
            return Response({'detail': 'شماره موبایل برای حساب کاربری ثبت نشده است.'}, status=status.HTTP_400_BAD_REQUEST)

        session = (
            ClassCreationSession.objects.filter(
                id=session_id,
                is_published=True,
                pipeline_type=ClassCreationSession.PipelineType.CLASS,
                invites__phone=phone,
            )
            .prefetch_related('sections__units', 'learning_objectives', 'prerequisites')
            .first()
        )
        if session is None:
            return Response({'detail': 'کلاس پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        # Opening course content enrolls the student (lazily) and counts as activity.
        from .services.progress import completed_unit_ids, touch_enrollment

        touch_enrollment(session=session, student=user)
        done_units = completed_unit_ids(session=session, student=user)

        # First entry into the class → pre-build every chapter quiz + the final
        # exam in the background so the student never waits on first quiz access.
        # Dispatched once: only when no quiz exists yet, de-duped by a short-lived
        # cache flag. The task is idempotent and on-demand generation is the
        # fallback, so a missing worker (or this never firing) is harmless.
        try:
            from django.core.cache import cache
            from . import tasks as _classes_tasks

            pregen_flag = f'pregen_assess_{session.id}_{user.id}'
            already_has_quiz = ClassSectionQuiz.objects.filter(session=session, student=user).exists()
            if not already_has_quiz and cache.add(pregen_flag, '1', 600):
                transaction.on_commit(
                    lambda: _classes_tasks.pregenerate_student_assessments.delay(session.id, user.id)
                )
        except Exception:
            logger.warning('pre-generation dispatch failed (non-fatal)', exc_info=True)

        chapters: list[dict] = []
        first_lesson_marked = False
        for section in session.sections.order_by('order'):
            lessons: list[dict] = []
            for unit in section.units.order_by('order'):
                lesson_content = (unit.content_markdown or unit.source_markdown or '').strip()
                is_active = False
                if not first_lesson_marked:
                    is_active = True
                    first_lesson_marked = True

                lessons.append(
                    {
                        'id': str(unit.id),
                        'title': unit.title,
                        'type': 'text',
                        'isActive': is_active,
                        'isCompleted': unit.external_id in done_units,
                        'content': lesson_content,
                    }
                )

            chapters.append(
                {
                    'id': section.external_id or str(section.id),
                    'title': section.title,
                    'lessons': lessons,
                }
            )

        payload = {
            'id': str(session.id),
            'title': session.title,
            'description': session.description or '',
            'progress': _compute_student_course_progress(session=session, student=user),
            'level': (session.level or '').strip() or '—',
            'duration': (session.duration or '').strip() or '—',
            'recapMarkdown': (session.recap_markdown or '').strip(),
            'learningObjectives': [o.text for o in session.learning_objectives.order_by('order')],
            'prerequisites': PrerequisiteSerializer(session.prerequisites.order_by('order'), many=True).data,
            'chapters': chapters,
        }

        return Response(StudentCourseContentSerializer(payload).data)


class StudentLessonCompleteView(APIView):
    """Mark a single lesson/unit complete for the current student.

    Powers real course progress (completed units / total units) and the
    teacher roster's ``completedLessons``. Idempotent: re-marking is a no-op.
    """

    permission_classes = [IsAuthenticated, IsStudentUser]

    @extend_schema(
        tags=['Classes'],
        summary='Mark a lesson complete for the current student',
        operation_id='student_lesson_complete',
        request=None,
        responses={200: OpenApiTypes.OBJECT},
    )
    def post(self, request, session_id: int, lesson_id: str):
        user = request.user
        phone = (getattr(user, 'phone', None) or '').strip()
        if not phone:
            return Response({'detail': 'شماره موبایل برای حساب کاربری ثبت نشده است.'}, status=status.HTTP_400_BAD_REQUEST)

        session = (
            ClassCreationSession.objects.filter(
                id=session_id,
                is_published=True,
                pipeline_type=ClassCreationSession.PipelineType.CLASS,
                invites__phone=phone,
            )
            .first()
        )
        if session is None:
            return Response({'detail': 'کلاس پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        from .services.progress import lesson_progress_percent, mark_unit_complete, resolve_unit

        unit = resolve_unit(session=session, lesson_id=lesson_id)
        if unit is None:
            return Response({'detail': 'درس پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        mark_unit_complete(session=session, student=user, unit=unit)

        return Response(
            {
                'lessonId': lesson_id,
                'isCompleted': True,
                'progress': lesson_progress_percent(session=session, student=user),
            },
            status=status.HTTP_200_OK,
        )


class StudentCoursePdfExportView(APIView):
    permission_classes = [IsAuthenticated, IsStudentUser]

    @extend_schema(
        tags=['Classes'],
        summary='Export the full course as a PDF handout',
        operation_id='student_course_export_pdf',
        responses={200: OpenApiTypes.BINARY},
    )
    def get(self, request, session_id: int):
        user = request.user
        phone = (getattr(user, 'phone', None) or '').strip()
        if not phone:
            return Response({'detail': 'شماره موبایل برای حساب کاربری ثبت نشده است.'}, status=status.HTTP_400_BAD_REQUEST)

        session = (
            ClassCreationSession.objects.filter(id=session_id, is_published=True, invites__phone=phone)
            .prefetch_related('sections__units')
            .first()
        )
        if session is None:
            return Response({'detail': 'کلاس پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        def _safe_filename(value: str) -> str:
            value = (value or '').strip() or 'course'
            value = re.sub(r"[\\/:*?\"<>|]+", '_', value)
            value = re.sub(r"\s+", ' ', value)
            return (value[:120] or 'course').strip()

        # Build a structure similar to the legacy Flask exporter.
        outline: list[dict] = []

        image_re = re.compile(r'!\[[^\]]*\]\(([^)]+)\)')
        for section in session.sections.order_by('order'):
            units: list[dict] = []
            for unit in section.units.order_by('order'):
                content_md = (unit.content_markdown or unit.source_markdown or '').strip()
                images = []
                for m in image_re.finditer(content_md):
                    img_src = (m.group(1) or '').strip()
                    if not img_src:
                        continue
                    images.append(img_src)

                units.append(
                    {
                        'title': unit.title,
                        'content_markdown': content_md,
                        'images': images,
                    }
                )
            outline.append({'title': section.title, 'units': units})

        structure = {
            'root_object': {'summary': (session.description or '').strip()},
            'outline': outline,
        }
        meta = {
            'title': session.title,
            'description': (session.description or '').strip(),
        }

        base_url = request.build_absolute_uri('/')
        pdf_bytes = generate_course_pdf(structure=structure, meta=meta, base_url=base_url)
        if not pdf_bytes:
            return Response({'detail': 'ساخت PDF با خطا مواجه شد.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        filename = f"{_safe_filename(session.title)}_جزوه.pdf"
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(filename)}"
        resp['Cache-Control'] = 'no-store'
        return resp


class StudentCourseChatView(APIView):
    permission_classes = [IsAuthenticated, IsStudentUser]

    @extend_schema(
        tags=['Classes'],
        summary='Chat with Amooz AI tutor for a course/lesson',
        operation_id='student_course_chat',
        request=OpenApiTypes.OBJECT,
        responses={200: OpenApiTypes.OBJECT},
    )
    def post(self, request, session_id: int):
        user = request.user
        phone = (getattr(user, 'phone', None) or '').strip()
        if not phone:
            return Response({'detail': 'شماره موبایل برای حساب کاربری ثبت نشده است.'}, status=status.HTTP_400_BAD_REQUEST)

        session = (
            ClassCreationSession.objects.filter(id=session_id, is_published=True, invites__phone=phone)
            .prefetch_related('sections__units')
            .first()
        )
        if session is None:
            return Response({'detail': 'کلاس پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        data = request.data if isinstance(request.data, dict) else {}
        message = str(data.get('message') or '').strip()
        lesson_id = str(data.get('lesson_id') or '').strip() or None
        page_context = str(data.get('page_context') or '').strip()
        page_material = str(data.get('page_material') or '').strip()
        # Student name for personalized chat (from profile or frontend)
        student_name = str(data.get('student_name') or '').strip()
        if not student_name:
            first = str(getattr(user, 'first_name', '') or '').strip()
            last = str(getattr(user, 'last_name', '') or '').strip()
            student_name = f'{first} {last}'.strip() or str(getattr(user, 'username', '') or '').strip()

        thread = get_or_create_thread(session=session, student_id=int(getattr(user, 'id', 0) or 0), lesson_id=lesson_id)
        
        is_protocol = message.startswith('SYSTEM_') or message.startswith('ACTIVATION_')
        if not is_protocol:
            append_message(
                thread=thread,
                role='user',
                message_type='text',
                content=message,
                payload={'page_context': page_context, 'page_material': page_material},
                suggestions=[],
                lesson_id=lesson_id,
            )

        try:
            resp = handle_student_message(
                session=session,
                student_id=int(getattr(user, 'id', 0) or 0),
                lesson_id=lesson_id,
                user_message=message,
                page_context=page_context,
                page_material=page_material,
                student_name=student_name,
            )
        except Exception as exc:
            logger.exception(
                'handle_student_message failed session_id=%s lesson_id=%r student_id=%r',
                session_id, lesson_id, getattr(user, 'id', None),
            )
            
            # Identify the error for the user in a friendly way but keep technical info in logs
            error_msg = 'الان در پاسخگویی مشکلی پیش آمده. لطفاً یک بار دیگر تلاش کن.'
            if settings.DEBUG:
                error_msg += f"\nDEBUG INFO: {str(exc)}"

            resp = {
                'type': 'text',
                'content': error_msg,
                'suggestions': [],
            }

        if isinstance(resp, dict) and resp.get('type') == 'text':
            append_message(
                thread=thread,
                role='assistant',
                message_type='text',
                content=str(resp.get('content') or ''),
                payload={},
                suggestions=list(resp.get('suggestions') or []),
                lesson_id=lesson_id,
            )
        elif isinstance(resp, dict) and resp.get('type') == 'widget':
            append_message(
                thread=thread,
                role='assistant',
                message_type='widget',
                content=str(resp.get('text') or ''),
                payload=resp,
                suggestions=list(resp.get('suggestions') or []),
                lesson_id=lesson_id,
            )
        return Response(resp, status=status.HTTP_200_OK)


class StudentCourseChatHistoryView(APIView):
    permission_classes = [IsAuthenticated, IsStudentUser]

    @extend_schema(
        tags=['Classes'],
        summary='Get previous chat messages for a student in a course (and optional lesson)',
        operation_id='student_course_chat_history',
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request, session_id: int):
        user = request.user
        phone = (getattr(user, 'phone', None) or '').strip()
        if not phone:
            return Response({'detail': 'شماره موبایل برای حساب کاربری ثبت نشده است.'}, status=status.HTTP_400_BAD_REQUEST)

        session = ClassCreationSession.objects.filter(id=session_id, is_published=True, invites__phone=phone).first()
        if session is None:
            return Response({'detail': 'کلاس پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        lesson_id = str(request.query_params.get('lesson_id') or '').strip() or None
        items = list_messages(session_id=session.id, student_id=int(getattr(user, 'id', 0) or 0), lesson_id=lesson_id)
        return Response({'items': items}, status=status.HTTP_200_OK)


class StudentCourseChatMediaView(APIView):
    permission_classes = [IsAuthenticated, IsStudentUser]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        tags=['Classes'],
        summary='Chat media upload (image/audio) for Amooz AI tutor',
        operation_id='student_course_chat_media',
        request=OpenApiTypes.OBJECT,
        responses={200: OpenApiTypes.OBJECT},
    )
    def post(self, request, session_id: int):
        user = request.user
        phone = (getattr(user, 'phone', None) or '').strip()
        if not phone:
            return Response({'detail': 'شماره موبایل برای حساب کاربری ثبت نشده است.'}, status=status.HTTP_400_BAD_REQUEST)

        session = (
            ClassCreationSession.objects.filter(id=session_id, is_published=True, invites__phone=phone)
            .prefetch_related('sections__units')
            .first()
        )
        if session is None:
            return Response({'detail': 'کلاس پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        up = request.FILES.get('file')
        if up is None:
            return Response({'detail': 'فایل ارسال نشده است.'}, status=status.HTTP_400_BAD_REQUEST)

        message = str(request.data.get('message') or '').strip()
        lesson_id = str(request.data.get('lesson_id') or '').strip() or None
        page_context = str(request.data.get('page_context') or '').strip()
        page_material = str(request.data.get('page_material') or '').strip()

        thread = get_or_create_thread(session=session, student_id=int(getattr(user, 'id', 0) or 0), lesson_id=lesson_id)

        mime_type = (getattr(up, 'content_type', None) or '').strip() or 'application/octet-stream'
        try:
            data = up.read()
        except Exception:
            data = b''

        if not data:
            return Response({'detail': 'فایل خالی است.'}, status=status.HTTP_400_BAD_REQUEST)

        if mime_type.startswith('audio/'):
            try:
                transcript, _provider, _model = transcribe_media_bytes(data=data, mime_type=mime_type)
            except Exception as e:
                logger.error(f"Failed to transcribe course media: {str(e)}")
                transcript = ""

            combined = (message or '').strip()
            if (transcript or '').strip():
                combined = (combined + '\n\n[VOICE_TRANSCRIPT]\n' + transcript.strip()).strip()
            append_message(
                thread=thread,
                role='user',
                message_type='text',
                content=combined or '[VOICE]',
                payload={
                    'mime_type': mime_type,
                    'original_name': getattr(up, 'name', '') or '',
                    'page_context': page_context,
                    'page_material': page_material,
                },
                suggestions=[],
                lesson_id=lesson_id,
            )

            try:
                resp = handle_student_audio_upload(
                    session=session,
                    student_id=int(getattr(user, 'id', 0) or 0),
                    lesson_id=lesson_id,
                    user_message=message,
                    page_context=page_context,
                    page_material=page_material,
                    transcript_markdown=transcript,
                )
            except Exception:
                logger.exception(
                    'handle_student_audio_upload failed session_id=%s lesson_id=%r student_id=%r',
                    session_id, lesson_id, getattr(user, 'id', None),
                )
                resp = {
                    'type': 'text',
                    'content': 'الان در پردازش فایل صوتی مشکلی پیش آمده. لطفاً دوباره تلاش کن.',
                    'suggestions': [],
                }

            if isinstance(resp, dict) and resp.get('type') == 'text':
                append_message(
                    thread=thread,
                    role='assistant',
                    message_type='text',
                    content=str(resp.get('content') or ''),
                    payload={},
                    suggestions=list(resp.get('suggestions') or []),
                    lesson_id=lesson_id,
                )
            elif isinstance(resp, dict) and resp.get('type') == 'widget':
                append_message(
                    thread=thread,
                    role='assistant',
                    message_type='widget',
                    content=str(resp.get('text') or ''),
                    payload=resp,
                    suggestions=list(resp.get('suggestions') or []),
                    lesson_id=lesson_id,
                )
            return Response(resp, status=status.HTTP_200_OK)

        if mime_type.startswith('image/'):

            append_message(
                thread=thread,
                role='user',
                message_type='text',
                content=(message or '').strip() or '[IMAGE]',
                payload={
                    'mime_type': mime_type,
                    'original_name': getattr(up, 'name', '') or '',
                    'page_context': page_context,
                    'page_material': page_material,
                },
                suggestions=[],
                lesson_id=lesson_id,
            )

            try:
                resp = handle_student_image_upload(
                    session=session,
                    student_id=int(getattr(user, 'id', 0) or 0),
                    lesson_id=lesson_id,
                    user_message=message,
                    page_context=page_context,
                    page_material=page_material,
                    image_bytes=data,
                    mime_type=mime_type,
                )
            except Exception:
                logger.exception(
                    'handle_student_image_upload failed session_id=%s lesson_id=%r student_id=%r',
                    session_id, lesson_id, getattr(user, 'id', None),
                )
                resp = {
                    'type': 'text',
                    'content': 'الان در پردازش تصویر مشکلی پیش آمده. لطفاً دوباره تلاش کن.',
                    'suggestions': [],
                }

            if isinstance(resp, dict) and resp.get('type') == 'text':
                append_message(
                    thread=thread,
                    role='assistant',
                    message_type='text',
                    content=str(resp.get('content') or ''),
                    payload={},
                    suggestions=list(resp.get('suggestions') or []),
                    lesson_id=lesson_id,
                )
            return Response(resp, status=status.HTTP_200_OK)

        return Response({'detail': 'فقط فایل تصویر یا صوت پشتیبانی می‌شود.'}, status=status.HTTP_400_BAD_REQUEST)


class StudentChapterQuizView(APIView):
    permission_classes = [IsAuthenticated, IsStudentUser]

    @extend_schema(
        tags=['Classes'],
        summary='Get a chapter-end quiz for a published class chapter (section)',
        operation_id='student_chapter_quiz_get',
        responses={200: StudentChapterQuizResponseSerializer},
    )
    def get(self, request, session_id: int, chapter_id: str):
        user = request.user
        phone = (getattr(user, 'phone', None) or '').strip()
        if not phone:
            return Response({'detail': 'شماره موبایل برای حساب کاربری ثبت نشده است.'}, status=status.HTTP_400_BAD_REQUEST)

        session = (
            ClassCreationSession.objects.filter(id=session_id, is_published=True, invites__phone=phone)
            .prefetch_related('sections__units')
            .first()
        )
        if session is None:
            return Response({'detail': 'کلاس پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        chapter_key = (chapter_id or '').strip()
        if not chapter_key:
            return Response({'detail': 'شناسه فصل نامعتبر است.'}, status=status.HTTP_400_BAD_REQUEST)

        section = session.sections.filter(external_id=chapter_key).first()
        if section is None:
            try:
                section_id_int = int(chapter_key)
            except Exception:
                section_id_int = None
            if section_id_int:
                section = session.sections.filter(id=section_id_int).first()

        if section is None:
            return Response({'detail': 'فصل پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        quiz = ClassSectionQuiz.objects.filter(session=session, section=section, student=user).first()
        if quiz is None or not isinstance(quiz.questions, dict) or not quiz.questions.get('questions'):
            units = list(section.units.order_by('order'))
            combined = "\n\n".join(
                [
                    (u.content_markdown or u.source_markdown or '').strip()
                    for u in units
                    if (u.content_markdown or u.source_markdown or '').strip()
                ]
            ).strip()
            # Keep prompt payload bounded to avoid runaway token usage.
            combined = combined[:8000]

            quiz_obj, _provider, _model = generate_section_quiz_questions(section_content=combined, count=5)
            quiz, _created = ClassSectionQuiz.objects.update_or_create(
                session=session,
                section=section,
                student=user,
                defaults={'questions': quiz_obj},
            )

        raw_questions = quiz.questions.get('questions') if isinstance(quiz.questions, dict) else None
        if not isinstance(raw_questions, list):
            raw_questions = []

        sanitized: list[dict] = []
        for q in raw_questions:
            if not isinstance(q, dict):
                continue
            qid = str(q.get('id') or '').strip()
            qtype = str(q.get('type') or '').strip()
            qtext = str(q.get('question') or '').strip()
            if not qid or not qtype or not qtext:
                continue
            options = q.get('options')
            if not isinstance(options, list):
                options = []
            sanitized.append(
                {
                    'id': qid,
                    'type': qtype,
                    'question': qtext,
                    'options': [str(o) for o in options if str(o).strip()],
                    'difficulty': str(q.get('difficulty') or '').strip(),
                }
            )

        payload = {
            'quiz_id': quiz.id,
            'session_id': session.id,
            'chapter_id': section.external_id or str(section.id),
            'chapter_title': section.title,
            'passing_score': 70,
            'questions': sanitized,
            'last_score_0_100': quiz.last_score_0_100,
            'last_passed': quiz.last_passed,
        }
        return Response(StudentChapterQuizResponseSerializer(payload).data)

    @extend_schema(
        tags=['Classes'],
        summary='Submit answers for a chapter-end quiz and get score',
        operation_id='student_chapter_quiz_submit',
        request=StudentChapterQuizSubmitRequestSerializer,
        responses={200: StudentChapterQuizSubmitResponseSerializer},
    )
    def post(self, request, session_id: int, chapter_id: str):
        user = request.user
        phone = (getattr(user, 'phone', None) or '').strip()
        if not phone:
            return Response({'detail': 'شماره موبایل برای حساب کاربری ثبت نشده است.'}, status=status.HTTP_400_BAD_REQUEST)

        session = (
            ClassCreationSession.objects.filter(id=session_id, is_published=True, invites__phone=phone)
            .prefetch_related('sections__units')
            .first()
        )
        if session is None:
            return Response({'detail': 'کلاس پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        chapter_key = (chapter_id or '').strip()
        section = session.sections.filter(external_id=chapter_key).first()
        if section is None:
            try:
                section_id_int = int(chapter_key)
            except Exception:
                section_id_int = None
            if section_id_int:
                section = session.sections.filter(id=section_id_int).first()

        if section is None:
            return Response({'detail': 'فصل پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = StudentChapterQuizSubmitRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        answers = serializer.validated_data['answers']

        quiz = ClassSectionQuiz.objects.filter(session=session, section=section, student=user).first()
        if quiz is None or not isinstance(quiz.questions, dict) or not quiz.questions.get('questions'):
            return Response({'detail': 'ابتدا آزمون را دریافت کنید.'}, status=status.HTTP_400_BAD_REQUEST)

        raw_questions = quiz.questions.get('questions')
        if not isinstance(raw_questions, list) or not raw_questions:
            return Response({'detail': 'ساختار آزمون نامعتبر است.'}, status=status.HTTP_400_BAD_REQUEST)

        per_question: list[dict] = []
        total = 0
        count = 0

        for q in raw_questions:
            if not isinstance(q, dict):
                continue
            qid = str(q.get('id') or '').strip()
            qtype = str(q.get('type') or '').strip()
            qtext = str(q.get('question') or '').strip()
            correct = q.get('correct_answer')
            if not qid or not qtype or not qtext:
                continue

            student_answer = str(answers.get(qid, '') or '').strip()
            score = 0
            feedback = ''
            label = ''

            if qtype in ('multiple_choice', 'fill_blank', 'true_false'):
                expected = str(correct).strip()
                if qtype == 'true_false':
                    expected = 'true' if bool(correct) else 'false'
                    sa = student_answer.lower().strip()
                    if sa in ('true', '1', 'yes', 'درست', 'صحیح'):
                        sa_norm = 'true'
                    elif sa in ('false', '0', 'no', 'نادرست', 'غلط'):
                        sa_norm = 'false'
                    else:
                        sa_norm = sa
                    is_ok = sa_norm == expected
                else:
                    is_ok = student_answer == expected
                score = 100 if is_ok else 0
                label = 'correct' if is_ok else 'incorrect'
                feedback = 'آفرین! درست بود.' if is_ok else 'هنوز دقیق نیست. دوباره مرور کن.'
            else:
                grading_obj, _provider, _model = grade_open_text_answer(
                    question=qtext,
                    reference_answer=str(correct or ''),
                    student_answer=student_answer,
                )
                try:
                    score = int(grading_obj.get('score_0_100') or 0)
                except Exception:
                    score = 0
                label = str(grading_obj.get('label') or '').strip()
                feedback = str(grading_obj.get('feedback') or '').strip()

            score = max(0, min(100, score))
            total += score
            count += 1

            per_question.append(
                {
                    'id': qid,
                    'type': qtype,
                    'question': qtext,
                    'student_answer': student_answer,
                    'score_0_100': score,
                    'label': label,
                    'feedback': feedback,
                    # Correct answer IS revealed after submission: the student
                    # learns from every question and (on a fail) gets a brand-new
                    # adaptive quiz next, so the old answers can't be reused.
                    'correct_answer': correct,
                }
            )

        if count == 0:
            return Response({'detail': 'سوالی برای نمره‌دهی پیدا نشد.'}, status=status.HTTP_400_BAD_REQUEST)

        final_score = int(round(total / count))
        passing_score = 70
        passed = final_score >= passing_score

        quiz.last_score_0_100 = final_score
        quiz.last_passed = passed
        quiz.save(update_fields=['last_score_0_100', 'last_passed', 'updated_at'])

        attempt_result = {
            'per_question': per_question,
            'passing_score': passing_score,
        }
        ClassSectionQuizAttempt.objects.create(
            quiz=quiz,
            answers=answers,
            result=attempt_result,
            score_0_100=final_score,
            passed=passed,
        )

        # Submitting a quiz is activity; passing it completes the section's units.
        from .services.progress import mark_section_units_complete, touch_enrollment

        touch_enrollment(session=session, student=user)
        if passed:
            mark_section_units_complete(session=session, student=user, section=section)

        payload = {
            'score_0_100': final_score,
            'passed': passed,
            'passing_score': passing_score,
            'per_question': per_question,
            'course_progress': _compute_student_course_progress(session=session, student=user),
        }
        return Response(StudentChapterQuizSubmitResponseSerializer(payload).data, status=status.HTTP_200_OK)


class StudentChapterQuizRegenerateView(APIView):
    """Build a NEW chapter quiz that targets the concepts the student missed.

    This is the back half of the learning loop: after the student fails, they
    see the correct answers (the submit response now reveals them) and then call
    this to get a fresh, harder-to-game quiz focused on their weak points.

    Only allowed when the latest state is a FAIL (``last_passed is False``).
    That single rule rate-limits the loop on its own: regenerating resets
    ``last_passed`` to NULL, so the student must take (and fail) the new quiz
    before they can regenerate again. Pass → blocked (no need). One LLM call.
    """

    permission_classes = [IsAuthenticated, IsStudentUser]

    @extend_schema(
        tags=['Classes'],
        summary='Regenerate a chapter quiz focused on the student weak points (after a fail)',
        operation_id='student_chapter_quiz_regenerate',
        responses={200: StudentChapterQuizResponseSerializer},
    )
    def post(self, request, session_id: int, chapter_id: str):
        user = request.user
        phone = (getattr(user, 'phone', None) or '').strip()
        if not phone:
            return Response({'detail': 'شماره موبایل برای حساب کاربری ثبت نشده است.'}, status=status.HTTP_400_BAD_REQUEST)

        session = (
            ClassCreationSession.objects.filter(id=session_id, is_published=True, invites__phone=phone)
            .prefetch_related('sections__units')
            .first()
        )
        if session is None:
            return Response({'detail': 'کلاس پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        chapter_key = (chapter_id or '').strip()
        section = session.sections.filter(external_id=chapter_key).first()
        if section is None:
            try:
                section_id_int = int(chapter_key)
            except Exception:
                section_id_int = None
            if section_id_int:
                section = session.sections.filter(id=section_id_int).first()
        if section is None:
            return Response({'detail': 'فصل پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        quiz = ClassSectionQuiz.objects.filter(session=session, section=section, student=user).first()
        if quiz is None or not isinstance(quiz.questions, dict) or not quiz.questions.get('questions'):
            return Response({'detail': 'ابتدا در آزمون این فصل شرکت کنید.'}, status=status.HTTP_400_BAD_REQUEST)
        if quiz.last_passed is not False:
            return Response(
                {'detail': 'آزمون جدید فقط پس از مردود شدن در آزمون فعلی ساخته می‌شود.'},
                status=status.HTTP_409_CONFLICT,
            )

        weak_points = compute_weak_points(quiz)

        units = list(section.units.order_by('order'))
        combined = "\n\n".join(
            [
                (u.content_markdown or u.source_markdown or '').strip()
                for u in units
                if (u.content_markdown or u.source_markdown or '').strip()
            ]
        ).strip()[:8000]

        try:
            if weak_points:
                quiz_obj, _provider, _model = generate_adaptive_section_quiz(
                    section_content=combined, weak_points=weak_points, count=5, review_count=1,
                )
            else:
                # Failed but no per-question weak signal (e.g. all open-ended,
                # mid scores) → still give a fresh quiz.
                quiz_obj, _provider, _model = generate_section_quiz_questions(section_content=combined, count=5)
        except Exception as exc:
            logger.exception('Adaptive quiz regeneration failed: session=%s section=%s', session.id, section.id)
            return Response(
                {'detail': 'ساخت آزمون جدید با خطا مواجه شد. کمی بعد دوباره تلاش کنید.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        latest_attempt = quiz.attempts.order_by('-created_at').first()
        new_questions = dict(quiz_obj) if isinstance(quiz_obj, dict) else {'questions': []}
        new_questions['adaptive'] = bool(weak_points)
        new_questions['based_on_attempt_id'] = latest_attempt.id if latest_attempt else None
        quiz.questions = new_questions
        quiz.last_score_0_100 = None
        quiz.last_passed = None
        quiz.save(update_fields=['questions', 'last_score_0_100', 'last_passed', 'updated_at'])

        raw_questions = quiz.questions.get('questions') if isinstance(quiz.questions, dict) else []
        if not isinstance(raw_questions, list):
            raw_questions = []
        sanitized: list[dict] = []
        for q in raw_questions:
            if not isinstance(q, dict):
                continue
            qid = str(q.get('id') or '').strip()
            qtype = str(q.get('type') or '').strip()
            qtext = str(q.get('question') or '').strip()
            if not qid or not qtype or not qtext:
                continue
            options = q.get('options')
            if not isinstance(options, list):
                options = []
            sanitized.append(
                {
                    'id': qid,
                    'type': qtype,
                    'question': qtext,
                    'options': [str(o) for o in options if str(o).strip()],
                    'difficulty': str(q.get('difficulty') or '').strip(),
                }
            )

        payload = {
            'quiz_id': quiz.id,
            'session_id': session.id,
            'chapter_id': section.external_id or str(section.id),
            'chapter_title': section.title,
            'passing_score': 70,
            'questions': sanitized,
            'last_score_0_100': None,
            'last_passed': None,
        }
        return Response(StudentChapterQuizResponseSerializer(payload).data)


class StudentFinalExamView(APIView):
    permission_classes = [IsAuthenticated, IsStudentUser]

    @extend_schema(
        tags=['Classes'],
        summary='Get final exam for a published class (per-student)',
        operation_id='student_final_exam_get',
        responses={200: StudentFinalExamResponseSerializer},
    )
    def get(self, request, session_id: int):
        user = request.user
        phone = (getattr(user, 'phone', None) or '').strip()
        if not phone:
            return Response({'detail': 'شماره موبایل برای حساب کاربری ثبت نشده است.'}, status=status.HTTP_400_BAD_REQUEST)

        session = (
            ClassCreationSession.objects.filter(id=session_id, is_published=True, invites__phone=phone)
            .prefetch_related('sections__units')
            .first()
        )
        if session is None:
            return Response({'detail': 'کلاس پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        exam = ClassFinalExam.objects.filter(session=session, student=user).first()
        if exam is None or not isinstance(exam.exam, dict) or not exam.exam.get('questions'):
            combined_parts: list[str] = []
            for section in session.sections.order_by('order'):
                combined_parts.append(str(section.title or '').strip())
                for unit in section.units.order_by('order'):
                    txt = (unit.content_markdown or unit.source_markdown or '').strip()
                    if txt:
                        combined_parts.append(txt)

            combined = "\n\n".join([p for p in combined_parts if p]).strip()
            combined = combined[:12000]

            exam_obj, _provider, _model = generate_final_exam_pool(combined_content=combined, pool_size=12)
            exam, _created = ClassFinalExam.objects.update_or_create(
                session=session,
                student=user,
                defaults={'exam': exam_obj},
            )

        raw_questions = exam.exam.get('questions') if isinstance(exam.exam, dict) else None
        if not isinstance(raw_questions, list):
            raw_questions = []

        sanitized: list[dict] = []
        for q in raw_questions:
            if not isinstance(q, dict):
                continue
            qid = str(q.get('id') or '').strip()
            qtype = str(q.get('type') or '').strip()
            qtext = str(q.get('question') or '').strip()
            if not qid or not qtype or not qtext:
                continue

            options = q.get('options')
            if not isinstance(options, list):
                options = []

            pts_raw = q.get('points')
            try:
                pts = int(pts_raw) if pts_raw is not None else 5
            except Exception:
                pts = 5
            pts = max(1, min(100, pts))

            sanitized.append(
                {
                    'id': qid,
                    'type': qtype,
                    'question': qtext,
                    'options': [str(o) for o in options if str(o).strip()],
                    'points': pts,
                    'chapter': str(q.get('chapter') or '').strip(),
                }
            )

        exam_title = str(exam.exam.get('exam_title') or 'آزمون نهایی')
        try:
            time_limit = int(exam.exam.get('time_limit') or 45)
        except Exception:
            time_limit = 45

        try:
            passing_score = int(exam.exam.get('passing_score') or 70)
        except Exception:
            passing_score = 70
        passing_score = max(0, min(100, passing_score))

        payload = {
            'exam_id': exam.id,
            'session_id': session.id,
            'exam_title': exam_title,
            'time_limit': time_limit,
            'passing_score': passing_score,
            'questions': sanitized,
            'last_score_0_100': exam.last_score_0_100,
            'last_passed': exam.last_passed,
        }
        return Response(StudentFinalExamResponseSerializer(payload).data)

    @extend_schema(
        tags=['Classes'],
        summary='Submit final exam answers and get score',
        operation_id='student_final_exam_submit',
        request=StudentFinalExamSubmitRequestSerializer,
        responses={200: StudentFinalExamSubmitResponseSerializer},
    )
    def post(self, request, session_id: int):
        user = request.user
        phone = (getattr(user, 'phone', None) or '').strip()
        if not phone:
            return Response({'detail': 'شماره موبایل برای حساب کاربری ثبت نشده است.'}, status=status.HTTP_400_BAD_REQUEST)

        session = (
            ClassCreationSession.objects.filter(id=session_id, is_published=True, invites__phone=phone)
            .prefetch_related('sections__units')
            .first()
        )
        if session is None:
            return Response({'detail': 'کلاس پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = StudentFinalExamSubmitRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        answers = serializer.validated_data['answers']

        exam = ClassFinalExam.objects.filter(session=session, student=user).first()
        if exam is None or not isinstance(exam.exam, dict) or not exam.exam.get('questions'):
            return Response({'detail': 'ابتدا آزمون را دریافت کنید.'}, status=status.HTTP_400_BAD_REQUEST)

        raw_questions = exam.exam.get('questions')
        if not isinstance(raw_questions, list) or not raw_questions:
            return Response({'detail': 'ساختار آزمون نامعتبر است.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            passing_score = int(exam.exam.get('passing_score') or 70)
        except Exception:
            passing_score = 70
        passing_score = max(0, min(100, passing_score))

        earned_points = 0
        total_points = 0
        per_question: list[dict] = []

        for q in raw_questions:
            if not isinstance(q, dict):
                continue
            qid = str(q.get('id') or '').strip()
            qtype = str(q.get('type') or '').strip()
            qtext = str(q.get('question') or '').strip()
            correct = q.get('correct_answer')
            expl = str(q.get('explanation') or '').strip()

            pts_raw = q.get('points')
            try:
                pts = int(pts_raw) if pts_raw is not None else 5
            except Exception:
                pts = 5
            pts = max(1, min(100, pts))

            if not qid or not qtype or not qtext:
                continue

            total_points += pts
            student_answer = str(answers.get(qid, '') or '').strip()

            got = 0
            label = ''
            feedback = ''

            if qtype in ('multiple_choice', 'fill_blank', 'true_false'):
                expected = str(correct).strip()
                if qtype == 'true_false':
                    expected = 'true' if bool(correct) else 'false'
                    sa = student_answer.lower().strip()
                    if sa in ('true', '1', 'yes', 'درست', 'صحیح'):
                        sa_norm = 'true'
                    elif sa in ('false', '0', 'no', 'نادرست', 'غلط'):
                        sa_norm = 'false'
                    else:
                        sa_norm = sa
                    is_ok = sa_norm == expected
                else:
                    is_ok = student_answer == expected

                if is_ok:
                    got = pts
                    label = 'correct'
                    feedback = 'آفرین! درست بود.'
                else:
                    got = 0
                    label = 'incorrect'
                    feedback = 'پاسخ درست نبود. دوباره مرور کن و مطالب درس رو مرور کن.'
            else:
                grading_obj, _provider, _model = grade_open_text_answer(
                    question=qtext,
                    reference_answer=str(correct or ''),
                    student_answer=student_answer,
                )
                try:
                    score_0_100 = int(grading_obj.get('score_0_100') or 0)
                except Exception:
                    score_0_100 = 0
                score_0_100 = max(0, min(100, score_0_100))

                got = int(round((score_0_100 / 100) * pts))
                label = str(grading_obj.get('label') or '').strip()
                feedback = str(grading_obj.get('feedback') or '').strip()

            earned_points += max(0, min(pts, got))

            per_question.append(
                {
                    'id': qid,
                    'type': qtype,
                    'question': qtext,
                    'student_answer': student_answer,
                    'score_points': got,
                    'max_points': pts,
                    'label': label,
                    'feedback': feedback,
                    # Revealed after submission (see chapter-quiz rationale): the
                    # student always sees the right answer + explanation to learn.
                    'correct_answer': correct,
                    'explanation': expl,
                }
            )

        if total_points <= 0:
            return Response({'detail': 'سوالی برای نمره‌دهی پیدا نشد.'}, status=status.HTTP_400_BAD_REQUEST)

        score_0_100 = int(round((earned_points / total_points) * 100))
        score_0_100 = max(0, min(100, score_0_100))
        passed = score_0_100 >= passing_score

        exam.last_score_0_100 = score_0_100
        exam.last_passed = passed
        exam.save(update_fields=['last_score_0_100', 'last_passed', 'updated_at'])

        attempt_result = {
            'per_question': per_question,
            'passing_score': passing_score,
        }
        ClassFinalExamAttempt.objects.create(
            exam=exam,
            answers=answers,
            result=attempt_result,
            score_0_100=score_0_100,
            passed=passed,
        )

        # Submitting the final exam counts as activity.
        from .services.progress import touch_enrollment

        touch_enrollment(session=session, student=user)

        payload = {
            'score_0_100': score_0_100,
            'passed': passed,
            'passing_score': passing_score,
            'per_question': per_question,
            'course_progress': _compute_student_course_progress(session=session, student=user),
        }
        return Response(StudentFinalExamSubmitResponseSerializer(payload).data, status=status.HTTP_200_OK)


class StudentFinalExamRegenerateView(APIView):
    """Build a NEW final exam focused on the concepts the student missed.

    Mirrors ``StudentChapterQuizRegenerateView`` for the course-wide final exam:
    only allowed after a fail (``exam.last_passed is False``); resetting
    ``last_passed`` to NULL rate-limits the loop (must retake before regenerating).
    """

    permission_classes = [IsAuthenticated, IsStudentUser]

    @extend_schema(
        tags=['Classes'],
        summary='Regenerate the final exam focused on the student weak points (after a fail)',
        operation_id='student_final_exam_regenerate',
        responses={200: StudentFinalExamResponseSerializer},
    )
    def post(self, request, session_id: int):
        user = request.user
        phone = (getattr(user, 'phone', None) or '').strip()
        if not phone:
            return Response({'detail': 'شماره موبایل برای حساب کاربری ثبت نشده است.'}, status=status.HTTP_400_BAD_REQUEST)

        session = (
            ClassCreationSession.objects.filter(id=session_id, is_published=True, invites__phone=phone)
            .prefetch_related('sections__units')
            .first()
        )
        if session is None:
            return Response({'detail': 'کلاس پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        exam = ClassFinalExam.objects.filter(session=session, student=user).first()
        if exam is None or not isinstance(exam.exam, dict) or not exam.exam.get('questions'):
            return Response({'detail': 'ابتدا در آزمون نهایی شرکت کنید.'}, status=status.HTTP_400_BAD_REQUEST)
        if exam.last_passed is not False:
            return Response(
                {'detail': 'آزمون جدید فقط پس از مردود شدن در آزمون نهایی ساخته می‌شود.'},
                status=status.HTTP_409_CONFLICT,
            )

        attempts = list(exam.attempts.order_by('-created_at')[:3])
        weak_points = compute_weak_points_from(exam.exam, attempts)

        combined_parts: list[str] = []
        for section in session.sections.order_by('order'):
            combined_parts.append(str(section.title or '').strip())
            for unit in section.units.order_by('order'):
                txt = (unit.content_markdown or unit.source_markdown or '').strip()
                if txt:
                    combined_parts.append(txt)
        combined = "\n\n".join([p for p in combined_parts if p]).strip()[:12000]

        try:
            if weak_points:
                exam_obj, _provider, _model = generate_adaptive_final_exam(
                    combined_content=combined, weak_points=weak_points, pool_size=12, review_count=2,
                )
            else:
                exam_obj, _provider, _model = generate_final_exam_pool(combined_content=combined, pool_size=12)
        except Exception:
            logger.exception('Adaptive final exam regeneration failed: session=%s', session.id)
            return Response(
                {'detail': 'ساخت آزمون جدید با خطا مواجه شد. کمی بعد دوباره تلاش کنید.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        latest_attempt = exam.attempts.order_by('-created_at').first()
        new_exam = dict(exam_obj) if isinstance(exam_obj, dict) else {'questions': []}
        new_exam['adaptive'] = bool(weak_points)
        new_exam['based_on_attempt_id'] = latest_attempt.id if latest_attempt else None
        exam.exam = new_exam
        exam.last_score_0_100 = None
        exam.last_passed = None
        exam.save(update_fields=['exam', 'last_score_0_100', 'last_passed', 'updated_at'])

        raw_questions = exam.exam.get('questions') if isinstance(exam.exam, dict) else []
        if not isinstance(raw_questions, list):
            raw_questions = []
        sanitized: list[dict] = []
        for q in raw_questions:
            if not isinstance(q, dict):
                continue
            qid = str(q.get('id') or '').strip()
            qtype = str(q.get('type') or '').strip()
            qtext = str(q.get('question') or '').strip()
            if not qid or not qtype or not qtext:
                continue
            options = q.get('options')
            if not isinstance(options, list):
                options = []
            try:
                pts = int(q.get('points')) if q.get('points') is not None else 5
            except Exception:
                pts = 5
            sanitized.append(
                {
                    'id': qid,
                    'type': qtype,
                    'question': qtext,
                    'options': [str(o) for o in options if str(o).strip()],
                    'points': max(1, min(100, pts)),
                    'chapter': str(q.get('chapter') or '').strip(),
                }
            )

        try:
            time_limit = int(exam.exam.get('time_limit') or 45)
        except Exception:
            time_limit = 45
        try:
            passing_score = max(0, min(100, int(exam.exam.get('passing_score') or 70)))
        except Exception:
            passing_score = 70

        payload = {
            'exam_id': exam.id,
            'session_id': session.id,
            'exam_title': str(exam.exam.get('exam_title') or 'آزمون نهایی'),
            'time_limit': time_limit,
            'passing_score': passing_score,
            'questions': sanitized,
            'last_score_0_100': None,
            'last_passed': None,
        }
        return Response(StudentFinalExamResponseSerializer(payload).data)


class InviteCodeVerifyView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Classes'],
        summary='Verify invite code (public)',
        operation_id='invite_code_verify',
        request=InviteCodeVerifySerializer,
        responses={200: InviteCodeVerifyResponseSerializer},
    )
    def post(self, request):
        serializer = InviteCodeVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data['code']

        # Prefer global per-phone codes.
        global_entry = StudentInviteCode.objects.filter(code=code).only('phone').first()
        if global_entry is not None:
            inv = (
                ClassInvitation.objects.filter(
                    phone=global_entry.phone,
                    session__is_published=True,
                )
                .select_related('session')
                .order_by('-session__published_at', '-session__updated_at', '-created_at')
                .first()
            )
            if inv is None or inv.session is None:
                return Response({'valid': False}, status=status.HTTP_200_OK)

            return Response(
                {
                    'valid': True,
                    'session_id': inv.session_id,
                    'title': inv.session.title,
                },
                status=status.HTTP_200_OK,
            )

        # Backward compatibility: accept legacy codes attached to invitations.
        inv = (
            ClassInvitation.objects.filter(invite_code=code, session__is_published=True)
            .select_related('session')
            .order_by('-session__published_at', '-session__updated_at', '-created_at')
            .first()
        )
        if inv is None or inv.session is None:
            return Response({'valid': False}, status=status.HTTP_200_OK)

        return Response(
            {
                'valid': True,
                'session_id': inv.session_id,
                'title': inv.session.title,
            },
            status=status.HTTP_200_OK,
        )


class StudentNotificationListView(APIView):
    """List notifications for the logged-in student (from class announcements)."""

    permission_classes = [IsAuthenticated, IsStudentUser]

    @extend_schema(
        tags=['Notifications'],
        summary='List student notifications (from class announcements)',
        operation_id='student_notifications_list',
        responses={200: StudentNotificationSerializer(many=True)},
    )
    def get(self, request):
        user = request.user
        phone = (getattr(user, 'phone', None) or '').strip()
        sessions = []
        if phone:
            # Get all published sessions (Classes and Exam Preps) that this student is invited to.
            sessions = (
                ClassCreationSession.objects.filter(
                    is_published=True,
                    invites__phone=phone,
                )
                .prefetch_related('announcements')
                .distinct()
            )

        from apps.notification.models import NotificationReadReceipt
        read_ids = set(
            NotificationReadReceipt.objects.filter(user=user).values_list('notification_id', flat=True)
        )

        out: list[dict] = []

        admin_qs = AdminNotification.objects.filter(
            audience__in=[AdminNotification.Audience.ALL, AdminNotification.Audience.STUDENTS],
        ).order_by('-created_at')

        for item in admin_qs:
            item_id = f'admin-{item.id}'
            out.append(
                {
                    'id': item_id,
                    'title': item.title,
                    'message': item.message,
                    'type': item.notification_type,
                    'isRead': item_id in read_ids,
                    'createdAt': item.created_at.isoformat(),
                    'link': '/notifications',
                }
            )

        # Teacher messages addressed to this student.
        if phone:
            from apps.notification.models import TeacherNotification
            from apps.notification.services import student_teacher_ids

            teacher_msgs = (
                TeacherNotification.objects.filter(
                    recipients__phone=phone,
                    teacher_id__in=student_teacher_ids(student=user),
                )
                .select_related('teacher')
                .distinct()
                .order_by('-created_at')
            )
            for msg in teacher_msgs:
                item_id = f'teacher-{msg.id}'
                out.append(
                    {
                        'id': item_id,
                        'title': msg.title,
                        'message': msg.message,
                        'type': msg.notification_type,
                        'isRead': item_id in read_ids,
                        'createdAt': msg.created_at.isoformat(),
                        'link': '/notifications',
                        'senderName': msg.teacher.get_full_name().strip() or msg.teacher.username,
                    }
                )

        for session in sessions:
            for announcement in session.announcements.all():
                # Map priority to notification type
                ntype = 'info'
                if announcement.priority == ClassAnnouncement.Priority.HIGH:
                    ntype = 'warning'
                elif announcement.priority == ClassAnnouncement.Priority.MEDIUM:
                    ntype = 'info'

                # Define link based on session type
                link = None
                if session.pipeline_type == ClassCreationSession.PipelineType.CLASS:
                    link = f'/dashboard/courses/{session.id}'
                else:
                    link = f'/dashboard/exam-prep/{session.id}'

                item_id = f'announcement-{announcement.id}'
                out.append(
                    {
                        'id': item_id,
                        'title': announcement.title,
                        'message': announcement.content,
                        'type': ntype,
                        'isRead': item_id in read_ids,
                        'createdAt': announcement.created_at.isoformat(),
                        'link': link,
                    }
                )

        # Sort by latest first
        out.sort(key=lambda x: x['createdAt'], reverse=True)

        return Response(StudentNotificationSerializer(out, many=True).data)


# ==========================================================================
# EXAM PREP PIPELINE VIEWS (2 Steps: Transcribe + Q&A Extraction)
# ==========================================================================


def _process_exam_prep_step1_transcription(session_id: int) -> None:
    """Background process: Transcribe audio/video for exam prep pipeline."""
    session = ClassCreationSession.objects.filter(id=session_id).first()
    if session is None:
        return
    if session.status != ClassCreationSession.Status.EXAM_TRANSCRIBING:
        return
    set_current_user(session.teacher)

    try:
        session.source_file.open('rb')
        try:
            data = session.source_file.read()
        finally:
            session.source_file.close()

        transcript, provider, model_name, page_count = _ingest_for_session(session, data)
        session.transcript_markdown = transcript
        session.llm_provider = provider
        session.llm_model = model_name
        session.source_page_count = page_count
        session.status = ClassCreationSession.Status.EXAM_TRANSCRIBED
        session.save(update_fields=['transcript_markdown', 'llm_provider', 'llm_model', 'source_page_count', 'status', 'updated_at'])
    except Exception as exc:
        session.status = ClassCreationSession.Status.FAILED
        session.error_detail = str(exc)
        session.save(update_fields=['status', 'error_detail', 'updated_at'])


def _process_exam_prep_step2_structure(session_id: int) -> None:
    """Background process: Extract Q&A structure from transcript."""
    session = ClassCreationSession.objects.filter(id=session_id).first()
    if session is None:
        return
    if session.status != ClassCreationSession.Status.EXAM_STRUCTURING:
        return
    if not (session.transcript_markdown or '').strip():
        session.status = ClassCreationSession.Status.FAILED
        session.error_detail = 'برای این جلسه هنوز ترنسکریپت مرحله ۱ آماده نیست.'
        session.save(update_fields=['status', 'error_detail', 'updated_at'])
        return
    set_current_user(session.teacher)

    try:
        exam_prep_obj, provider, model_name = extract_exam_prep_structure(
            transcript_markdown=session.transcript_markdown,
        )
        normalized, _changed = _normalize_exam_prep_questions(exam_prep_obj)
        session.exam_prep_json = json.dumps(normalized, ensure_ascii=False)
        session.llm_provider = provider
        session.llm_model = model_name
        session.status = ClassCreationSession.Status.EXAM_STRUCTURED
        session.save(update_fields=['exam_prep_json', 'llm_provider', 'llm_model', 'status', 'updated_at'])
    except Exception as exc:
        session.status = ClassCreationSession.Status.FAILED
        session.error_detail = str(exc)
        session.save(update_fields=['status', 'error_detail', 'updated_at'])


def _process_exam_prep_full_pipeline(session_id: int) -> None:
    """Run exam prep steps 1..2 sequentially (one-click pipeline)."""
    session = ClassCreationSession.objects.filter(id=session_id).first()
    if session is None:
        return

    # Step 1: Transcription
    if session.status == ClassCreationSession.Status.EXAM_TRANSCRIBING:
        _process_exam_prep_step1_transcription(session_id)

    session.refresh_from_db()
    if session.status == ClassCreationSession.Status.FAILED:
        return

    # Step 2: Q&A Extraction
    if session.status == ClassCreationSession.Status.EXAM_TRANSCRIBED:
        session.status = ClassCreationSession.Status.EXAM_STRUCTURING
        session.save(update_fields=['status', 'updated_at'])
        _process_exam_prep_step2_structure(session_id)


class ExamPrepStep1TranscribeView(APIView):
    """Step 1 of Exam Prep Pipeline: Upload and transcribe media."""
    permission_classes = [IsAuthenticated, IsTeacherUser]
    parser_classes = [FormParser, MultiPartParser]

    @extend_schema(
        tags=['Exam Prep'],
        summary='Exam Prep Step 1: Transcription (Gemini/AvalAI)',
        request=ExamPrepStep1TranscribeRequestSerializer,
        responses={202: ExamPrepStep1TranscribeResponseSerializer, 200: ExamPrepStep1TranscribeResponseSerializer},
    )
    def post(self, request):
        serializer = ExamPrepStep1TranscribeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        upload = serializer.validated_data['file']
        title = serializer.validated_data['title']
        description = serializer.validated_data.get('description', '')
        client_request_id = serializer.validated_data.get('client_request_id')
        run_full_pipeline = bool(serializer.validated_data.get('run_full_pipeline', False))

        # Limit concurrent in-progress exam prep sessions per teacher.
        _ACTIVE_EXAM_STATUSES = [
            ClassCreationSession.Status.EXAM_TRANSCRIBING,
            ClassCreationSession.Status.EXAM_STRUCTURING,
        ]

        # Idempotency: same as the class Step-1 path. A genuine retry (same file)
        # dedupes to the existing session; a reused key with a DIFFERENT file must
        # NOT return the old session's stale output, so we process the new upload.
        if client_request_id is not None:
            existing = ClassCreationSession.objects.filter(
                teacher=request.user,
                client_request_id=client_request_id,
            ).first()
            if existing is not None:
                if _is_same_uploaded_source(existing, upload):
                    logger.info(
                        "EXAM STEP1 IDEMPOTENT HIT: same file resubmitted; returning "
                        "EXISTING session=%s (status=%s) for client_request_id=%s.",
                        existing.id, existing.status, client_request_id,
                    )
                    payload = ExamPrepStep1TranscribeResponseSerializer(existing).data
                    http_status = (
                        status.HTTP_202_ACCEPTED
                        if existing.status == ClassCreationSession.Status.EXAM_TRANSCRIBING
                        else status.HTTP_200_OK
                    )
                    return Response(payload, status=http_status)
                logger.warning(
                    "EXAM STEP1 IDEMPOTENT KEY REUSED for a DIFFERENT file (existing "
                    "session=%s name=%r vs new upload name=%r) — NOT returning stale "
                    "output; processing the new upload as a fresh session.",
                    existing.id, existing.source_original_name, getattr(upload, 'name', '?'),
                )
                client_request_id = None

        # Atomic check + create to prevent TOCTOU race.
        try:
            with transaction.atomic():
                active_count = ClassCreationSession.objects.select_for_update(skip_locked=True).filter(
                    teacher=request.user,
                    pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
                    status__in=_ACTIVE_EXAM_STATUSES,
                ).count()
                if active_count >= 5:
                    return Response(
                        {'detail': 'حداکثر ۵ آزمون همزمان در حال پردازش است. لطفاً صبر کنید.'},
                        status=status.HTTP_429_TOO_MANY_REQUESTS,
                    )

                # Resolve optional organization from request data.
                org_id = request.data.get('organization')
                organization = None
                if org_id:
                    from apps.organizations.models import Organization, OrganizationMembership
                    try:
                        org_id_int = int(org_id)
                    except (ValueError, TypeError):
                        return Response(
                            {'detail': 'شناسه سازمان آموزشی نامعتبر است.'},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    if not OrganizationMembership.objects.filter(
                        user=request.user,
                        organization_id=org_id_int,
                        status=OrganizationMembership.MemberStatus.ACTIVE,
                    ).exists():
                        return Response(
                            {'detail': 'شما عضو فعال این سازمان آموزشی نیستید.'},
                            status=status.HTTP_403_FORBIDDEN,
                        )
                    organization = Organization.objects.filter(id=org_id_int).first()

                # Resolve optional study group (must belong to the chosen org).
                study_group = None
                sg_id = request.data.get('study_group')
                if sg_id:
                    if organization is None:
                        return Response(
                            {'detail': 'برای انتخاب گروه آموزشی ابتدا سازمان آموزشی را مشخص کنید.'},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    from apps.organizations.models import StudyGroup
                    study_group = StudyGroup.objects.filter(
                        id=sg_id, organization_id=organization.id,
                    ).first()
                    if study_group is None:
                        return Response(
                            {'detail': 'گروه آموزشی نامعتبر است یا متعلق به این سازمان آموزشی نیست.'},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                session = ClassCreationSession.objects.create(
                    teacher=request.user,
                    title=title,
                    description=description,
                    source_type=(
                        ClassCreationSession.SourceType.PDF if is_pdf_upload(upload)
                        else ClassCreationSession.SourceType.MEDIA
                    ),
                    source_file=upload,
                    source_mime_type=getattr(upload, 'content_type', '') or '',
                    source_original_name=getattr(upload, 'name', '') or '',
                    pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
                    status=ClassCreationSession.Status.EXAM_TRANSCRIBING,
                    client_request_id=client_request_id,
                    organization=organization,
                    study_group=study_group,
                    workflow_state=build_session_workflow_state('queued'),
                )
                from .services.exam_prep_v3 import configured_extraction_version
                ExamPrepExtractionArtifact.objects.create(
                    session=session,
                    pipeline_version=configured_extraction_version(),
                )
        except IntegrityError:
            if client_request_id is not None:
                existing = ClassCreationSession.objects.filter(
                    teacher=request.user, client_request_id=client_request_id,
                ).first()
                if existing is not None:
                    return Response(
                        ExamPrepStep1TranscribeResponseSerializer(existing).data,
                        status=status.HTTP_202_ACCEPTED,
                    )
            return Response(
                {'detail': 'درخواست تکراری. لطفاً دوباره تلاش کنید.'},
                status=status.HTTP_409_CONFLICT,
            )
        except Exception as exc:
            logger.exception(
                'Failed to create exam prep session (file upload to storage failed): %s', exc,
            )
            return Response(
                {'detail': 'فایل آپلود نشد. لطفاً دوباره تلاش کنید.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if run_full_pipeline:
            _dispatch_pipeline_task(session, process_exam_prep_full_pipeline)
            return Response(ExamPrepStep1TranscribeResponseSerializer(session).data, status=status.HTTP_202_ACCEPTED)

        # Dispatch step 1 to Celery
        _dispatch_pipeline_task(session, process_exam_prep_step1_transcription)
        return Response(ExamPrepStep1TranscribeResponseSerializer(session).data, status=status.HTTP_202_ACCEPTED)


class ExamPrepStep2StructureView(APIView):
    """Step 2 of Exam Prep Pipeline: Extract Q&A structure from transcript."""
    permission_classes = [IsAuthenticated, IsTeacherUser]

    @extend_schema(
        tags=['Exam Prep'],
        summary='Exam Prep Step 2: Extract Q&A Structure',
        request=ExamPrepStep2StructureRequestSerializer,
        responses={202: ExamPrepStep2StructureResponseSerializer, 400: OpenApiTypes.OBJECT},
    )
    def post(self, request):
        serializer = ExamPrepStep2StructureRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session_id = serializer.validated_data['session_id']

        with transaction.atomic():
            locked = ClassCreationSession.objects.select_for_update().filter(
                id=session_id,
                teacher=request.user,
                pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
            ).first()
            if locked is None:
                return Response(
                    {'detail': 'جلسه آمادگی آزمون یافت نشد.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            if locked.status == ClassCreationSession.Status.EXAM_STRUCTURING:
                session = locked
                should_dispatch = False
            else:
                artifact = ExamPrepExtractionArtifact.objects.select_for_update().filter(
                    session_id=locked.id,
                ).first()
                is_v2_retry = bool(
                    locked.status == ClassCreationSession.Status.EXAM_STRUCTURED
                    and not locked.is_published
                    and artifact
                    and artifact.pipeline_version >= 2
                    and (artifact.audit or {}).get('status') != 'passed'
                )
                if (
                    locked.status != ClassCreationSession.Status.EXAM_TRANSCRIBED
                    and not is_v2_retry
                ):
                    return Response(
                        {
                            'detail': (
                                f'این جلسه در وضعیت {locked.get_status_display()} است '
                                'و قابل اجرای مرحله ۲ نیست.'
                            )
                        },
                        status=status.HTTP_409_CONFLICT,
                    )
                locked.status = ClassCreationSession.Status.EXAM_STRUCTURING
                locked.save(update_fields=['status', 'updated_at'])
                session = locked
                should_dispatch = True

        if should_dispatch:
            _dispatch_pipeline_task(session, process_exam_prep_step2_structure)
        return Response(
            ExamPrepSessionDetailSerializer(session).data,
            status=status.HTTP_202_ACCEPTED,
        )


def _teacher_exam_prep_sessions(user, *, include_extraction_details=True):
    sessions = (
        ClassCreationSession.objects.filter(
            teacher=user,
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        )
        .select_related('teacher', 'exam_extraction_artifact')
    )
    if include_extraction_details:
        return sessions.prefetch_related(
            Prefetch(
                'exam_extraction_artifact__visual_assets',
                queryset=ExamPrepVisualAsset.objects.order_by('question_key', 'order'),
            ),
            'exam_extraction_artifact__units',
        )
    return sessions.defer(
        'exam_extraction_artifact__source_blocks',
        'exam_extraction_artifact__page_manifest',
        'exam_extraction_artifact__question_records',
        'exam_extraction_artifact__answer_records',
        'exam_extraction_artifact__failed_chunks',
        'exam_extraction_artifact__error_detail',
    )


class ExamPrepSessionDetailView(APIView):
    """Get details of an exam prep session (for polling status)."""
    permission_classes = [IsAuthenticated, IsTeacherUser]

    @extend_schema(
        tags=['Exam Prep'],
        summary='Get Exam Prep Session Detail',
        responses={200: ExamPrepSessionDetailSerializer, 404: OpenApiTypes.OBJECT},
    )
    def get(self, request, session_id: int):
        session = _teacher_exam_prep_sessions(request.user).filter(id=session_id).first()

        if session is None:
            return Response({'detail': 'جلسه آمادگی آزمون یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        return Response(ExamPrepSessionDetailSerializer(session).data)

    @extend_schema(
        tags=['Exam Prep'],
        summary='Update Exam Prep Session',
        request=ExamPrepSessionUpdateSerializer,
        responses={200: ExamPrepSessionDetailSerializer, 404: OpenApiTypes.OBJECT},
    )
    def patch(self, request, session_id: int):
        session = _teacher_exam_prep_sessions(request.user).filter(id=session_id).first()

        if session is None:
            return Response({'detail': 'جلسه آمادگی آزمون یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ExamPrepSessionUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        updated_fields: list[str] = []
        data = serializer.validated_data
        if 'title' in data:
            session.title = data['title']
            updated_fields.append('title')
        if 'description' in data:
            session.description = data['description']
            updated_fields.append('description')
        if 'level' in data:
            session.level = data['level']
            updated_fields.append('level')
        if 'duration' in data:
            session.duration = data['duration']
            updated_fields.append('duration')
        if 'exam_prep_json' in data:
            normalized_json, _changed = _normalize_exam_prep_json(data['exam_prep_json'])
            session.exam_prep_json = normalized_json or ''
            updated_fields.append('exam_prep_json')

        if updated_fields:
            with transaction.atomic():
                session = ClassCreationSession.objects.select_for_update().get(
                    id=session.id,
                    teacher=request.user,
                )
                if 'exam_prep_json' in data and (
                    session.is_published or session.is_active_pipeline
                ):
                    return Response(
                        {
                            'detail': (
                                'ویرایش محتوای آزمون هنگام پردازش یا پس از انتشار '
                                'امکان‌پذیر نیست.'
                            )
                        },
                        status=status.HTTP_409_CONFLICT,
                    )
                for field_name in ('title', 'description', 'level', 'duration'):
                    if field_name in data:
                        setattr(session, field_name, data[field_name])
                if 'exam_prep_json' in data:
                    session.exam_prep_json = normalized_json or ''
                session.save(update_fields=[*updated_fields, 'updated_at'])
                artifact = ExamPrepExtractionArtifact.objects.select_for_update().filter(
                    session=session
                ).first()
                if 'exam_prep_json' in data and artifact and artifact.pipeline_version >= 2:
                    parsed_projection = json.loads(session.exam_prep_json or '{}')
                    projection = parsed_projection if isinstance(parsed_projection, dict) else {}
                    artifact.audit = rebuild_audit_after_teacher_review(
                        projection=projection,
                        previous_audit=artifact.audit or {},
                        available_visual_ids={
                            visual.id for visual in artifact.visual_assets.all()
                        },
                    )
                    if artifact.pipeline_version >= 3:
                        from .services.exam_prep_v3 import clone_units_to_revision

                        previous_revision = artifact.revision
                        artifact.revision += 1
                        clone_units_to_revision(
                            artifact=artifact,
                            source_revision=previous_revision,
                            target_revision=artifact.revision,
                        )
                        artifact.teacher_reviewed_at = None
                        artifact.teacher_reviewed_by = None
                        artifact.reviewed_revision = None
                        artifact.reviewed_projection_fingerprint = ''
                        artifact.save(update_fields=[
                            'audit',
                            'revision',
                            'teacher_reviewed_at',
                            'teacher_reviewed_by',
                            'reviewed_revision',
                            'reviewed_projection_fingerprint',
                            'updated_at',
                        ])
                    else:
                        artifact.audit['teacherReviewedAt'] = timezone.now().isoformat()
                        artifact.save(update_fields=['audit', 'updated_at'])

        return Response(ExamPrepSessionDetailSerializer(session).data)

    @extend_schema(
        tags=['Exam Prep'],
        summary='Delete Exam Prep Session',
        responses={204: None, 404: OpenApiTypes.OBJECT},
    )
    def delete(self, request, session_id: int):
        session = _teacher_exam_prep_sessions(request.user).filter(id=session_id).first()

        if session is None:
            return Response({'detail': 'جلسه آمادگی آزمون یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        if session.is_active_pipeline:
            _cancel_session_pipeline(session)
        artifact = ExamPrepExtractionArtifact.objects.filter(session=session).first()
        if artifact is not None and artifact.pipeline_version >= 2:
            from core.storage_backends import delete_answer_source_file
            from .services.exam_prep_visuals import delete_visual_assets

            storage_names = {
                str(block.get('storageName'))
                for block in artifact.source_blocks or []
                if isinstance(block, dict) and block.get('storageName')
            }
            if not delete_visual_assets(artifact.visual_assets.all()):
                return Response(
                    {'detail': 'حذف فایل‌های تصویری کامل نشد. دوباره تلاش کنید.'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            deletion_results = [
                delete_answer_source_file(storage_name)
                for storage_name in storage_names
            ]
            if not all(deletion_results):
                return Response(
                    {
                        'detail': (
                            'حذف فایل‌های منبع کامل نشد. برای جلوگیری از باقی‌ماندن '
                            'فایل خصوصی، دوباره تلاش کنید.'
                        )
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            artifact.source_blocks = []
            artifact.save(update_fields=['source_blocks', 'updated_at'])
            if session.source_file:
                try:
                    session.source_file.delete(save=False)
                except Exception:
                    logger.warning(
                        'Failed to delete exam-prep upload before session deletion session=%s.',
                        session.id,
                        exc_info=True,
                    )
                    return Response(
                        {'detail': 'حذف فایل اصلی کامل نشد. دوباره تلاش کنید.'},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE,
                    )
        session.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ExamPrepSessionCancelView(APIView):
    """Cancel a running exam-prep pipeline (teacher, owner-only)."""
    permission_classes = [IsAuthenticated, IsTeacherUser]

    @extend_schema(
        tags=['Exam Prep'],
        summary='Cancel a running exam prep pipeline (teacher)',
        operation_id='exam_prep_sessions_cancel',
        request=None,
        responses={200: ExamPrepSessionDetailSerializer, 404: OpenApiTypes.OBJECT, 409: OpenApiTypes.OBJECT},
    )
    def post(self, request, session_id: int):
        session = _teacher_exam_prep_sessions(request.user).filter(id=session_id).first()
        if session is None:
            return Response({'detail': 'جلسه آمادگی آزمون یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        if not session.is_active_pipeline:
            return Response(
                {'detail': f'این جلسه در وضعیت «{session.get_status_display()}» است و قابل لغو نیست.'},
                status=status.HTTP_409_CONFLICT,
            )

        _cancel_session_pipeline(session)
        return Response(ExamPrepSessionDetailSerializer(session).data, status=status.HTTP_200_OK)


class ExamPrepSessionListView(APIView):
    """List all exam prep sessions for the teacher."""
    permission_classes = [IsAuthenticated, IsTeacherUser]

    @extend_schema(
        tags=['Exam Prep'],
        summary='List Exam Prep Sessions',
        parameters=[
            OpenApiParameter(
                name='organization',
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Filter by organization ID, or "personal" for exams without an organization.',
            ),
        ],
        responses={200: ExamPrepSessionDetailSerializer(many=True)},
    )
    def get(self, request):
        sessions = _teacher_exam_prep_sessions(
            request.user,
            include_extraction_details=False,
        )

        org_param = request.query_params.get('organization')
        if org_param == 'personal':
            sessions = sessions.filter(organization__isnull=True)
        elif org_param and org_param.isdigit():
            sessions = sessions.filter(organization_id=int(org_param))

        sessions = sessions.annotate(
            _invites_count=Count(
                'invites__phone',
                distinct=True,
                filter=~Q(invites__phone=F('teacher__phone')),
            ),
        ).order_by('-created_at')

        return Response(
            ExamPrepSessionDetailSerializer(
                sessions,
                many=True,
                context={'includeExtractionDetails': False},
            ).data
        )


class ExamPrepSessionPublishView(APIView):
    """Publish an exam prep session."""
    permission_classes = [IsAuthenticated, IsTeacherUser]
    serializer_class = ExamPrepSessionDetailSerializer

    @extend_schema(
        tags=['Exam Prep'],
        summary='Publish Exam Prep Session',
        responses={200: ExamPrepSessionDetailSerializer, 400: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT},
    )
    def post(self, request, session_id: int):
        published_now = False
        with transaction.atomic():
            session = ClassCreationSession.objects.select_for_update().filter(
                id=session_id,
                teacher=request.user,
                pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
            ).first()
            if session is None:
                return Response(
                    {'detail': 'جلسه آمادگی آزمون یافت نشد.'},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # V4 source-aware sessions are also visible from the legacy
            # teacher page.  Delegate that button to the canonical V4
            # publication service before legacy status/artifact checks; the
            # bridge may legitimately be ``exam_transcribed`` rather than
            # ``exam_structured``.  This keeps project, projection and
            # session publication flags atomic and makes crop URLs usable.
            from .models_v4_bridge import ExamV4SessionBridge
            from .models_v4_projection import ExamV4Projection
            from .services.exam_prep_v4_create_flow import (
                CreateFlowProjectionConflict,
                adopt_create_flow_projection,
            )
            from .services.exam_prep_v4_projection import (
                ProjectionIntegrityError,
                ProjectionNotReady,
                StaleProjection,
                build_legacy_projection,
                publish_legacy_projection,
            )

            bridge_project_id = (
                ExamV4SessionBridge.objects.filter(
                    session_id=session.id,
                    project__teacher=request.user,
                )
                .values_list('project_id', flat=True)
                .first()
            )
            v4_projection = (
                ExamV4Projection.objects.select_related('project')
                .filter(session=session, project__teacher=request.user)
                .first()
            )
            v4_project_id = bridge_project_id or (
                v4_projection.project_id if v4_projection is not None else None
            )
            if v4_project_id is not None:
                try:
                    prepared = build_legacy_projection(
                        teacher=request.user,
                        project_id=v4_project_id,
                    )
                    adopt_create_flow_projection(
                        project_id=v4_project_id,
                        projection_payload=prepared,
                    )
                    publish_legacy_projection(
                        teacher=request.user,
                        project_id=v4_project_id,
                    )
                    # Publication may create/rebind a projection in the
                    # compatibility path; keep the bridge session as the
                    # response/publication target.
                    adopt_create_flow_projection(
                        project_id=v4_project_id,
                        projection_payload=prepared,
                    )
                except ProjectionNotReady as exc:
                    return Response(
                        {'detail': str(exc), 'code': 'projection_not_ready'},
                        status=status.HTTP_409_CONFLICT,
                    )
                except StaleProjection as exc:
                    return Response(
                        {'detail': str(exc), 'code': 'stale_projection'},
                        status=status.HTTP_409_CONFLICT,
                    )
                except ProjectionIntegrityError as exc:
                    return Response(
                        {'detail': str(exc), 'code': 'projection_integrity_error'},
                        status=status.HTTP_409_CONFLICT,
                    )
                except CreateFlowProjectionConflict as exc:
                    return Response(
                        {'detail': str(exc), 'code': 'projection_session_conflict'},
                        status=status.HTTP_409_CONFLICT,
                    )
                session.refresh_from_db()
                return Response(ExamPrepSessionDetailSerializer(session).data)

            if session.is_published:
                return Response(ExamPrepSessionDetailSerializer(session).data)
            if session.status != ClassCreationSession.Status.EXAM_STRUCTURED:
                return Response(
                    {
                        'detail': (
                            'فقط جلسه‌های با وضعیت exam_structured قابل انتشار هستند. '
                            f'وضعیت فعلی: {session.status}'
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            artifact = ExamPrepExtractionArtifact.objects.select_for_update().filter(
                session=session
            ).first()
            if artifact is not None and artifact.pipeline_version >= 2:
                audit = artifact.audit or {}
                if (
                    audit.get('status') != 'passed'
                    or int(audit.get('criticalIssueCount') or 0) > 0
                ):
                    return Response(
                        {
                            'detail': (
                                'پیش از انتشار، خطاهای بحرانی استخراج را در بخش '
                                'بازبینی برطرف کنید.'
                            ),
                            'code': 'extraction_review_required',
                            'audit': audit,
                        },
                        status=status.HTTP_409_CONFLICT,
                    )
                if artifact.visual_assets.filter(
                    selected_variant=ExamPrepVisualAsset.SelectedVariant.GENERATED,
                    teacher_approved_generated=False,
                ).exists():
                    return Response(
                        {
                            'detail': (
                                'نسخه بازطراحی‌شده تصویر باید پیش از انتشار توسط '
                                'معلم تأیید شود.'
                            ),
                            'code': 'visual_approval_required',
                        },
                        status=status.HTTP_409_CONFLICT,
                    )
                if artifact.pipeline_version >= 3:
                    from .services.exam_prep_v3 import (
                        projection_fingerprint,
                        teacher_review_required,
                    )

                    current_fingerprint = projection_fingerprint(
                        session.exam_prep_json
                    )
                    if teacher_review_required(artifact) and (
                        artifact.reviewed_revision != artifact.revision
                        or artifact.reviewed_projection_fingerprint
                        != current_fingerprint
                    ):
                        return Response(
                            {
                                'detail': (
                                    'پیش از انتشار، بازبینی نهایی استخراج را '
                                    'تأیید کنید.'
                                ),
                                'code': 'teacher_extraction_confirmation_required',
                            },
                            status=status.HTTP_409_CONFLICT,
                        )

            now = timezone.now()
            session.is_published = True
            session.published_at = now
            session.save(
                update_fields=['is_published', 'published_at', 'updated_at']
            )
            if artifact is not None and artifact.pipeline_version >= 3:
                from .services.exam_prep_v3 import source_retention_deadline

                artifact.source_retain_until = source_retention_deadline(now=now)
                artifact.save(update_fields=['source_retain_until', 'updated_at'])
            published_now = True

        if published_now:
            try:
                from .services.org_roster import sync_org_class_roster
                sync_org_class_roster(session)
            except Exception:
                logger.warning('org roster sync on exam-prep publish failed session=%s', session.id, exc_info=True)
            def _dispatch_exam_publish_sms():
                logger.info('[SMS] Dispatching send_publish_sms_task for exam-prep session=%s', session.id)
                send_publish_sms_task.delay(session.id)
            transaction.on_commit(_dispatch_exam_publish_sms)

        return Response(ExamPrepSessionDetailSerializer(session).data)


class ExamPrepExtractionReviewConfirmView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    def post(self, request, session_id: int):
        try:
            requested_revision = int(request.data.get('artifactRevision'))
        except (TypeError, ValueError):
            return Response(
                {'detail': 'نسخه استخراج نامعتبر است.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        requested_fingerprint = str(
            request.data.get('projectionFingerprint') or ''
        ).strip()
        with transaction.atomic():
            artifact = ExamPrepExtractionArtifact.objects.select_for_update().select_related(
                'session'
            ).filter(
                session_id=session_id,
                session__teacher=request.user,
                session__is_published=False,
            ).first()
            if artifact is None:
                return Response(
                    {'detail': 'جلسه آمادگی آزمون یافت نشد.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            from .services.exam_prep_v3 import projection_fingerprint
            current_fingerprint = projection_fingerprint(
                artifact.session.exam_prep_json
            )
            audit = artifact.audit or {}
            if (
                artifact.revision != requested_revision
                or requested_fingerprint != current_fingerprint
            ):
                return Response(
                    {'detail': 'خروجی استخراج تغییر کرده است. صفحه را به‌روزرسانی کنید.'},
                    status=status.HTTP_409_CONFLICT,
                )
            if (
                audit.get('status') != 'passed'
                or int(audit.get('criticalIssueCount') or 0) > 0
            ):
                return Response(
                    {'detail': 'تا رفع خطاهای بحرانی، تأیید بازبینی ممکن نیست.'},
                    status=status.HTTP_409_CONFLICT,
                )
            artifact.teacher_reviewed_at = timezone.now()
            artifact.teacher_reviewed_by = request.user
            artifact.reviewed_revision = artifact.revision
            artifact.reviewed_projection_fingerprint = current_fingerprint
            artifact.save(update_fields=[
                'teacher_reviewed_at',
                'teacher_reviewed_by',
                'reviewed_revision',
                'reviewed_projection_fingerprint',
                'updated_at',
            ])
        return Response(ExamPrepSessionDetailSerializer(artifact.session).data)


class ExamPrepExtractionUnitSourceView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    def get(self, request, session_id: int, unit_id: int):
        unit = ExamPrepExtractionUnit.objects.select_related(
            'artifact__session'
        ).filter(
            id=unit_id,
            artifact__session_id=session_id,
            artifact__session__teacher=request.user,
        ).first()
        if unit is None:
            return Response(
                {'detail': 'واحد استخراج یافت نشد.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        block = next(
            (
                value
                for value in unit.artifact.source_blocks or []
                if isinstance(value, dict)
                and value.get('pageNumber') == unit.source_page
                and value.get('storageName')
            ),
            None,
        )
        if block is None:
            return Response(
                {'detail': 'منبع این واحد در دسترس نیست.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        storage = storages['answer_sources']
        try:
            handle = storage.open(block['storageName'], 'rb')
        except FileNotFoundError:
            return Response(
                {'detail': 'فایل منبع یافت نشد.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        response = FileResponse(
            handle,
            content_type=block.get('contentType') or 'application/octet-stream',
        )
        response['Cache-Control'] = 'private, no-store'
        return response


class ExamPrepExtractionUnitRetryView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    def post(self, request, session_id: int, unit_id: int):
        try:
            requested_revision = int(request.data.get('artifactRevision'))
        except (TypeError, ValueError):
            return Response(
                {'detail': 'نسخه استخراج نامعتبر است.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            artifact = ExamPrepExtractionArtifact.objects.select_for_update().select_related(
                'session'
            ).filter(
                session_id=session_id,
                session__teacher=request.user,
                session__is_published=False,
                pipeline_version__gte=3,
            ).first()
            if artifact is None:
                return Response(
                    {'detail': 'جلسه آمادگی آزمون یافت نشد.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            if artifact.revision != requested_revision:
                return Response(
                    {'detail': 'نسخه استخراج تغییر کرده است.'},
                    status=status.HTTP_409_CONFLICT,
                )
            target = artifact.units.select_for_update().filter(
                id=unit_id,
                revision=artifact.revision,
                status__in=[
                    ExamPrepExtractionUnit.Status.RETRYABLE,
                    ExamPrepExtractionUnit.Status.QUARANTINED,
                    ExamPrepExtractionUnit.Status.FAILED,
                ],
            ).first()
            if target is None:
                return Response(
                    {'detail': 'این واحد قابل تلاش مجدد نیست.'},
                    status=status.HTTP_409_CONFLICT,
                )
            old_revision = artifact.revision
            artifact.revision += 1
            artifact.teacher_reviewed_at = None
            artifact.teacher_reviewed_by = None
            artifact.reviewed_revision = None
            artifact.reviewed_projection_fingerprint = ''
            artifact.audit = {}
            artifact.status = (
                ExamPrepExtractionArtifact.Status.COLLECTING_PAGES
                if target.stage == ExamPrepExtractionUnit.Stage.OCR
                else ExamPrepExtractionArtifact.Status.INVENTORY
            )
            artifact.save()
            from .services.exam_prep_v3 import clone_units_to_revision

            clone_units_to_revision(
                artifact=artifact,
                source_revision=old_revision,
                target_revision=artifact.revision,
                statuses={ExamPrepExtractionUnit.Status.ACCEPTED},
                exclude_ids={target.id},
            )
            replacement = ExamPrepExtractionUnit.objects.create(
                artifact=artifact,
                stage=target.stage,
                unit_key=target.unit_key,
                revision=artifact.revision,
                status=ExamPrepExtractionUnit.Status.PENDING,
                source_page=target.source_page,
                source_timestamp_ms=target.source_timestamp_ms,
                source_segment=target.source_segment,
                input_fingerprint=target.input_fingerprint,
            )
            session = artifact.session
            session.status = ClassCreationSession.Status.EXAM_STRUCTURING
            session.save(update_fields=['status', 'updated_at'])
            from .tasks import retry_exam_prep_extraction_unit
            _dispatch_pipeline_task(session, retry_exam_prep_extraction_unit)
        return Response(
            {
                'artifactRevision': artifact.revision,
                'unitId': replacement.id,
                'status': 'queued',
            },
            status=status.HTTP_202_ACCEPTED,
        )


class ExamPrepVisualAssetView(APIView):
    """Select the original crop or an automatically verified generated candidate."""

    permission_classes = [IsAuthenticated, IsTeacherUser]

    def patch(self, request, session_id: int, asset_id: int):
        variant = str(request.data.get('selectedVariant') or '').strip()
        if variant not in {
            ExamPrepVisualAsset.SelectedVariant.SOURCE,
            ExamPrepVisualAsset.SelectedVariant.GENERATED,
        }:
            return Response({'detail': 'نسخه تصویر نامعتبر است.'}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            asset = ExamPrepVisualAsset.objects.select_for_update().select_related(
                'artifact__session'
            ).filter(
                id=asset_id,
                artifact__session_id=session_id,
                artifact__session__teacher=request.user,
                artifact__session__is_published=False,
            ).first()
            if asset is None:
                return Response({'detail': 'تصویر یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)
            if asset.artifact.session.is_active_pipeline:
                return Response(
                    {'detail': 'تغییر تصویر هنگام پردازش امکان‌پذیر نیست.'},
                    status=status.HTTP_409_CONFLICT,
                )
            if variant == ExamPrepVisualAsset.SelectedVariant.GENERATED:
                if not asset.generated_file or asset.status != ExamPrepVisualAsset.Status.VERIFIED:
                    return Response(
                        {'detail': 'نسخه بازطراحی‌شده هنوز تأیید خودکار نشده است.'},
                        status=status.HTTP_409_CONFLICT,
                    )
                approved_generated = True
            else:
                approved_generated = False
            changed = (
                asset.selected_variant != variant
                or asset.teacher_approved_generated != approved_generated
            )
            asset.selected_variant = variant
            asset.teacher_approved_generated = approved_generated
            asset.save(update_fields=[
                'selected_variant',
                'teacher_approved_generated',
                'updated_at',
            ])
            if changed and asset.artifact.pipeline_version >= 3:
                from .services.exam_prep_v3 import clone_units_to_revision

                artifact = ExamPrepExtractionArtifact.objects.select_for_update().get(
                    id=asset.artifact_id
                )
                previous_revision = artifact.revision
                artifact.revision += 1
                clone_units_to_revision(
                    artifact=artifact,
                    source_revision=previous_revision,
                    target_revision=artifact.revision,
                )
                artifact.teacher_reviewed_at = None
                artifact.teacher_reviewed_by = None
                artifact.reviewed_revision = None
                artifact.reviewed_projection_fingerprint = ''
                artifact.save(update_fields=[
                    'revision',
                    'teacher_reviewed_at',
                    'teacher_reviewed_by',
                    'reviewed_revision',
                    'reviewed_projection_fingerprint',
                    'updated_at',
                ])
        return Response({
            'id': asset.id,
            'selectedVariant': asset.selected_variant,
            'teacherApprovedGenerated': asset.teacher_approved_generated,
        })


class ExamPrepVisualAssetContentView(APIView):
    """Stream a private visual to its owner or an invited student."""

    permission_classes = [IsAuthenticated]

    def get(self, request, session_id: int, asset_id: int):
        asset = ExamPrepVisualAsset.objects.select_related(
            'artifact__session'
        ).filter(id=asset_id, artifact__session_id=session_id).first()
        if asset is None:
            return Response({'detail': 'تصویر یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)
        session = asset.artifact.session
        is_teacher = session.teacher_id == request.user.id
        phone = (getattr(request.user, 'phone', '') or '').strip()
        is_student = bool(
            session.is_published and phone and session.invites.filter(phone=phone).exists()
        )
        if not is_teacher and not is_student:
            return Response({'detail': 'تصویر یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)
        if is_student and asset.role == ExamPrepVisualAsset.Role.SOLUTION:
            return Response({'detail': 'تصویر یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        variant = request.query_params.get('variant')
        if variant not in {None, 'source', 'generated'}:
            return Response(
                {'detail': 'نسخه تصویر نامعتبر است.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if variant is None:
            variant = (
                asset.selected_variant
                if asset.selected_variant == ExamPrepVisualAsset.SelectedVariant.GENERATED
                and asset.teacher_approved_generated
                else ExamPrepVisualAsset.SelectedVariant.SOURCE
            )
        if variant == 'generated':
            if not is_teacher and not (
                asset.selected_variant == ExamPrepVisualAsset.SelectedVariant.GENERATED
                and asset.teacher_approved_generated
            ):
                return Response({'detail': 'تصویر یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)
            field = asset.generated_file
            content_type = asset.generated_content_type or 'image/png'
        else:
            field = asset.source_file
            content_type = asset.source_content_type or 'image/png'
        if not field:
            return Response({'detail': 'تصویر یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)
        from core.storage_backends import open_answer_source_file
        try:
            stream = open_answer_source_file(field)
        except Exception:
            return Response({'detail': 'فایل تصویر در دسترس نیست.'}, status=status.HTTP_404_NOT_FOUND)
        return FileResponse(stream, content_type=content_type)


# ==========================================================================
# EXAM PREP INVITATIONS
# ==========================================================================


class ExamPrepInvitationListCreateView(APIView):
    """List and create invitations for an exam prep session."""
    permission_classes = [IsAuthenticated, IsTeacherUser]

    @extend_schema(
        tags=['Exam Prep'],
        summary='List exam prep invitations for a session (teacher)',
        operation_id='exam_prep_sessions_invites_list',
        responses={200: ClassInvitationSerializer(many=True)},
    )
    def get(self, request, session_id: int):
        session = ClassCreationSession.objects.filter(
            id=session_id,
            teacher=request.user,
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        ).first()
        if session is None:
            return Response({'detail': 'جلسه آمادگی آزمون یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)
        qs = ClassInvitation.objects.filter(session=session).order_by('-created_at')
        return Response(ClassInvitationSerializer(qs, many=True).data)

    @extend_schema(
        tags=['Exam Prep'],
        summary='Create exam prep invitations for a session (teacher)',
        operation_id='exam_prep_sessions_invites_create',
        request=ClassInvitationCreateSerializer,
        responses={200: ClassInvitationSerializer(many=True)},
    )
    def post(self, request, session_id: int):
        session = ClassCreationSession.objects.filter(
            id=session_id,
            teacher=request.user,
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        ).first()
        if session is None:
            return Response({'detail': 'جلسه آمادگی آزمون یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        # Org sessions get their roster from the linked study group (manager-owned);
        # a teacher may not hand-invite arbitrary students into them.
        if session.organization_id is not None:
            return Response(
                {'detail': 'دانش‌آموزانِ آزمون‌های سازمان آموزشی از طریق «گروه آموزشی» توسط مدیر سازمان آموزشی تعیین می‌شوند.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ClassInvitationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phones: list[str] = serializer.validated_data['phones']

        # Bulk check existing invitations (1 query instead of N).
        existing_phones = set(
            ClassInvitation.objects.filter(
                session=session, phone__in=phones,
            ).values_list('phone', flat=True)
        )
        new_invites = []
        new_phones = []
        for phone in phones:
            if phone in existing_phones:
                continue
            code = get_or_create_invite_code_for_phone(phone)
            new_invites.append(ClassInvitation(session=session, phone=phone, invite_code=code))
            new_phones.append(phone)
        if new_invites:
            ClassInvitation.objects.bulk_create(new_invites, ignore_conflicts=True)

        # If session is already published, send SMS to newly added students.
        if new_phones and session.is_published:
            invite_ids = list(
                ClassInvitation.objects.filter(
                    session=session, phone__in=new_phones,
                ).values_list('id', flat=True)
            )
            if invite_ids:
                _sid = session.id
                def _dispatch_exam_invite_sms(ids=invite_ids, sid=_sid):
                    logger.info('[SMS] Dispatching send_new_invites_sms_task session=%s invites=%d', sid, len(ids))
                    send_new_invites_sms_task.delay(sid, ids)
                transaction.on_commit(_dispatch_exam_invite_sms)

        qs = ClassInvitation.objects.filter(session=session).order_by('-created_at')
        return Response(ClassInvitationSerializer(qs, many=True).data)


class ExamPrepInvitationDetailView(APIView):
    """Delete an invitation from an exam prep session."""
    permission_classes = [IsAuthenticated, IsTeacherUser]

    @extend_schema(
        tags=['Exam Prep'],
        summary='Delete an exam prep invitation (teacher)',
        operation_id='exam_prep_sessions_invites_delete',
        responses={204: None},
    )
    def delete(self, request, session_id: int, invite_id: int):
        session = ClassCreationSession.objects.filter(
            id=session_id,
            teacher=request.user,
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        ).first()
        if session is None:
            return Response({'detail': 'جلسه آمادگی آزمون یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)
        if session.organization_id is not None:
            return Response(
                {'detail': 'دانش‌آموزانِ آزمون‌های سازمان آموزشی از طریق «گروه آموزشی» توسط مدیر سازمان آموزشی تعیین می‌شوند.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        invite = ClassInvitation.objects.filter(id=invite_id, session=session).first()
        if invite is None:
            return Response({'detail': 'دعوت نامه پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        invite.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ExamPrepAnnouncementListCreateView(APIView):
    """List and create announcements for an exam prep session."""
    permission_classes = [IsAuthenticated, IsTeacherUser]

    @extend_schema(
        tags=['Exam Prep'],
        summary='List exam prep announcements (teacher)',
        operation_id='exam_prep_sessions_announcements_list',
        responses={200: ClassAnnouncementSerializer(many=True)},
    )
    def get(self, request, session_id: int):
        session = ClassCreationSession.objects.filter(
            id=session_id,
            teacher=request.user,
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        ).first()
        if session is None:
            return Response({'detail': 'جلسه آمادگی آزمون یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)
        qs = ClassAnnouncement.objects.filter(session=session).order_by('-created_at')
        return Response(ClassAnnouncementSerializer(qs, many=True).data)

    @extend_schema(
        tags=['Exam Prep'],
        summary='Create exam prep announcement (teacher)',
        operation_id='exam_prep_sessions_announcements_create',
        request=ClassAnnouncementCreateSerializer,
        responses={201: ClassAnnouncementSerializer},
    )
    def post(self, request, session_id: int):
        session = ClassCreationSession.objects.filter(
            id=session_id,
            teacher=request.user,
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        ).first()
        if session is None:
            return Response({'detail': 'جلسه آمادگی آزمون یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ClassAnnouncementCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        announcement = ClassAnnouncement.objects.create(
            session=session,
            title=serializer.validated_data['title'],
            content=serializer.validated_data['content'],
            priority=serializer.validated_data.get('priority', ClassAnnouncement.Priority.MEDIUM),
        )
        return Response(ClassAnnouncementSerializer(announcement).data, status=status.HTTP_201_CREATED)


class ExamPrepAnnouncementDetailView(APIView):
    """Update/delete announcements for an exam prep session."""
    permission_classes = [IsAuthenticated, IsTeacherUser]

    @extend_schema(
        tags=['Exam Prep'],
        summary='Update exam prep announcement (teacher)',
        operation_id='exam_prep_sessions_announcements_update',
        request=ClassAnnouncementUpdateSerializer,
        responses={200: ClassAnnouncementSerializer},
    )
    def patch(self, request, session_id: int, announcement_id: int):
        session = ClassCreationSession.objects.filter(
            id=session_id,
            teacher=request.user,
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        ).first()
        if session is None:
            return Response({'detail': 'جلسه آمادگی آزمون یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)
        announcement = ClassAnnouncement.objects.filter(id=announcement_id, session=session).first()
        if announcement is None:
            return Response({'detail': 'اطلاعیه پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ClassAnnouncementUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        updated_fields = []
        if 'title' in data:
            announcement.title = data['title']
            updated_fields.append('title')
        if 'content' in data:
            announcement.content = data['content']
            updated_fields.append('content')
        if 'priority' in data:
            announcement.priority = data['priority']
            updated_fields.append('priority')
        if updated_fields:
            updated_fields.append('updated_at')
            announcement.save(update_fields=updated_fields)
        return Response(ClassAnnouncementSerializer(announcement).data)

    @extend_schema(
        tags=['Exam Prep'],
        summary='Delete exam prep announcement (teacher)',
        operation_id='exam_prep_sessions_announcements_delete',
        responses={204: None},
    )
    def delete(self, request, session_id: int, announcement_id: int):
        session = ClassCreationSession.objects.filter(
            id=session_id,
            teacher=request.user,
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        ).first()
        if session is None:
            return Response({'detail': 'جلسه آمادگی آزمون یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)
        announcement = ClassAnnouncement.objects.filter(id=announcement_id, session=session).first()
        if announcement is None:
            return Response({'detail': 'اطلاعیه پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        announcement.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ==========================================================================
# STUDENT EXAM PREP ENDPOINTS
# ==========================================================================


# ---------------------------------------------------------------------------
# Helpers for exam-prep question type inference & true/false normalization
# ---------------------------------------------------------------------------

_TRUE_FALSE_LABELS = frozenset({'صحیح', 'غلط', 'درست', 'نادرست', 'true', 'false'})


def _infer_exam_prep_question_type(q: dict) -> str:
    """Infer the question type from the question dict.

    Checks explicit ``type`` field first; falls back to heuristic detection.
    Returns one of: ``multiple_choice``, ``true_false``, ``fill_blank``, ``short_answer``.
    """
    explicit = str(q.get('type') or '').strip().lower()
    if explicit in ('multiple_choice', 'true_false', 'fill_blank', 'short_answer'):
        return explicit

    qtext = str(q.get('question_text_markdown') or q.get('question') or '').strip()
    opts_raw = q.get('options')
    opts = opts_raw if isinstance(opts_raw, list) else []

    # Fill-blank: question text contains a blank placeholder
    blank_markers = ('{{blank}}', '{blank}', '\\{blank\\}', '____', '…', '...', '___')
    qtext_lower = qtext.lower()
    for marker in blank_markers:
        if marker in qtext_lower:
            return 'fill_blank'

    # True/false: exactly 2 options whose labels/text are true/false variants
    if len(opts) == 2:
        labels = set()
        for opt in opts:
            if isinstance(opt, dict):
                labels.add(str(opt.get('text_markdown') or opt.get('label') or '').strip().lower())
            elif isinstance(opt, str):
                labels.add(opt.strip().lower())
        if labels & {'صحیح', 'غلط', 'درست', 'نادرست', 'true', 'false'}:
            return 'true_false'
        # Persian labels الف/ب only → still check text content
        for opt in opts:
            txt = (str(opt.get('text_markdown') or '') if isinstance(opt, dict) else str(opt)).strip().lower()
            if txt in _TRUE_FALSE_LABELS:
                return 'true_false'

    # Multiple choice: has 3+ options
    if len(opts) >= 3:
        return 'multiple_choice'

    # No options → short answer (or 1-2 options that aren't T/F)
    if len(opts) == 0:
        return 'short_answer'

    return 'multiple_choice'


def _normalize_true_false_value(value: str) -> str:
    """Normalize Persian/English true-false answers to 'true' or 'false'."""
    v = value.strip().lower()
    if v in ('true', '1', 'yes', 'درست', 'صحیح'):
        return 'true'
    if v in ('false', '0', 'no', 'نادرست', 'غلط'):
        return 'false'
    return v


class StudentExamPrepListView(APIView):
    """List exam prep sessions available to the student."""
    permission_classes = [IsAuthenticated, IsStudentUser]

    @extend_schema(
        tags=['Student Exam Prep'],
        summary='List exam preps available to the student',
        operation_id='student_exam_prep_list',
        responses={200: StudentExamPrepListSerializer(many=True)},
    )
    def get(self, request):
        user = request.user
        phone = (getattr(user, 'phone', None) or '').strip()
        if not phone:
            return Response([], status=status.HTTP_200_OK)

        qs = (
            ClassCreationSession.objects.filter(
                is_published=True,
                pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
                invites__phone=phone,
            )
            .select_related('teacher')
            .prefetch_related('invites')
            .distinct()
            .order_by('-published_at', '-updated_at')
        )

        out: list[dict] = []
        for session in qs:
            teacher = session.teacher
            instructor = ''
            if teacher is not None:
                instructor = (teacher.get_full_name() or getattr(teacher, 'username', '') or '').strip()

            # Parse exam_prep_json to count questions
            questions_count = 0
            try:
                if session.exam_prep_json:
                    data = json.loads(session.exam_prep_json)
                    if isinstance(data, dict):
                        exam_prep = data.get('exam_prep', {})
                        questions_list = exam_prep.get('questions', [])
                        if isinstance(questions_list, list):
                            questions_count = len(questions_list)
            except (json.JSONDecodeError, TypeError):
                questions_count = 0

            out.append(
                {
                    'id': session.id,
                    'title': session.title,
                    'description': session.description or '',
                    'tags': [],
                    'questions': questions_count,
                    'createdAt': (session.published_at or session.created_at).date().isoformat(),
                    'instructor': instructor,
                    'sourceType': session.source_type,
                }
            )

        return Response(StudentExamPrepListSerializer(out, many=True).data)


class StudentExamPrepDetailView(APIView):
    """Get exam prep detail including questions for the student."""
    permission_classes = [IsAuthenticated, IsStudentUser]

    @extend_schema(
        tags=['Student Exam Prep'],
        summary='Get exam prep detail with questions',
        operation_id='student_exam_prep_detail',
        responses={200: StudentExamPrepDetailSerializer, 404: OpenApiTypes.OBJECT},
    )
    def get(self, request, session_id: int):
        user = request.user
        phone = (getattr(user, 'phone', None) or '').strip()
        if not phone:
            return Response({'detail': 'شماره موبایل برای حساب کاربری ثبت نشده است.'}, status=status.HTTP_400_BAD_REQUEST)

        session = ClassCreationSession.objects.filter(
            id=session_id,
            is_published=True,
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
            invites__phone=phone,
        ).first()

        if session is None:
            return Response({'detail': 'آزمون آمادگی پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        # Parse exam_prep_json
        questions_list = []
        subject = ''
        try:
            if session.exam_prep_json:
                data = json.loads(session.exam_prep_json)
                if isinstance(data, dict):
                    normalized, changed = _normalize_exam_prep_questions(data)
                    if changed:
                        session.exam_prep_json = json.dumps(normalized, ensure_ascii=False)
                        session.save(update_fields=['exam_prep_json', 'updated_at'])
                    data = normalized
                    exam_prep = data.get('exam_prep', {})
                    subject = exam_prep.get('title', '')
                    raw_questions = exam_prep.get('questions', [])
                    if isinstance(raw_questions, list):
                        questions_list = raw_questions
        except (json.JSONDecodeError, TypeError):
            questions_list = []

        # IMPORTANT: Never expose correct answers or solutions to students.
        safe_questions: list[dict] = []
        for q in questions_list:
            if not isinstance(q, dict):
                continue

            qid = str(q.get('question_id') or '').strip()
            qtext = str(q.get('question_text_markdown') or '').strip()
            qtype = _infer_exam_prep_question_type(q)
            opts_raw = q.get('options')
            opts: list[dict] = []
            if isinstance(opts_raw, list):
                for opt in opts_raw:
                    if not isinstance(opt, dict):
                        continue
                    label = str(opt.get('label') or '').strip()
                    text_md = str(opt.get('text_markdown') or '').strip()
                    if label:
                        opts.append({'label': label, 'text_markdown': text_md})

            if qid:
                visuals = []
                workflow_state = session.workflow_state
                v4_project_id = (
                    workflow_state.get('v4ProjectId')
                    if isinstance(workflow_state, dict)
                    else None
                )
                v4_project_id_text = str(v4_project_id or '').strip()
                v4_url_prefix = (
                    f'/api/classes/exam-prep-source-crops/{v4_project_id_text}/'
                    if v4_project_id_text.isdigit() and len(v4_project_id_text) <= 12
                    else ''
                )
                for visual in q.get('visuals') or []:
                    if not isinstance(visual, dict) or visual.get('role') == 'solution':
                        continue
                    visual_id = visual.get('id')
                    if visual_id:
                        visual_url = str(visual.get('url') or '').strip()
                        # V4 source-first projections carry an authenticated
                        # crop URL.  Preserve it; only legacy numeric assets
                        # need the session visual endpoint fallback.
                        if visual_url.startswith('/api/classes/exam-prep-source-crops/'):
                            # Never downgrade an opaque V4 ref to the legacy
                            # integer endpoint when the bridge binding is
                            # missing or does not match this session.
                            if (
                                not v4_url_prefix
                                or not visual_url.startswith(f'{v4_url_prefix}question/')
                            ):
                                continue
                        elif (
                            visual_url.startswith('/api/classes/exam-prep-sessions/')
                            and f'/exam-prep-sessions/{session.id}/' in visual_url
                        ):
                            pass
                        else:
                            visual_url = (
                                f'/api/classes/exam-prep-sessions/{session.id}/'
                                f'visuals/{visual_id}/content/'
                            )
                        visuals.append({
                            'id': visual_id,
                            'role': visual.get('role'),
                            'optionLabel': visual.get('optionLabel'),
                            'altText': visual.get('altText') or '',
                            'url': visual_url,
                        })
                safe_questions.append(
                    {
                        'question_id': qid,
                        'question_text_markdown': qtext,
                        'type': qtype,
                        'options': opts,
                        'visuals': visuals,
                    }
                )

        out = {
            'id': session.id,
            'title': session.title,
            'description': session.description or '',
            'questions': safe_questions,
            'totalQuestions': len(safe_questions),
            'subject': subject,
        }

        return Response(StudentExamPrepDetailSerializer(out).data)


class StudentExamPrepSubmitView(APIView):
    """Submit exam prep answers (student)."""
    permission_classes = [IsAuthenticated, IsStudentUser]

    @extend_schema(
        tags=['Student Exam Prep'],
        summary='Submit exam prep answers',
        operation_id='student_exam_prep_submit',
        request=StudentExamPrepSubmitRequestSerializer,
        responses={200: StudentExamPrepSubmitResponseSerializer, 400: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT},
    )
    def post(self, request, session_id: int):
        user = request.user
        phone = (getattr(user, 'phone', None) or '').strip()
        if not phone:
            return Response({'detail': 'شماره موبایل برای حساب کاربری ثبت نشده است.'}, status=status.HTTP_400_BAD_REQUEST)

        session = ClassCreationSession.objects.filter(
            id=session_id,
            is_published=True,
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
            invites__phone=phone,
        ).first()

        if session is None:
            return Response({'detail': 'آزمون آمادگی پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = StudentExamPrepSubmitRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        answers = serializer.validated_data.get('answers') or {}
        finalize = bool(serializer.validated_data.get('finalize'))

        # Parse exam_prep_json
        questions_list = []
        try:
            if session.exam_prep_json:
                data = json.loads(session.exam_prep_json)
                if isinstance(data, dict):
                    normalized, changed = _normalize_exam_prep_questions(data)
                    if changed:
                        session.exam_prep_json = json.dumps(normalized, ensure_ascii=False)
                        session.save(update_fields=['exam_prep_json', 'updated_at'])
                    data = normalized
                    exam_prep = data.get('exam_prep', {})
                    raw_questions = exam_prep.get('questions', [])
                    if isinstance(raw_questions, list):
                        questions_list = raw_questions
        except (json.JSONDecodeError, TypeError):
            questions_list = []

        correct_map: dict[str, str] = {}
        question_type_map: dict[str, str] = {}
        question_text_map: dict[str, str] = {}
        question_solution_map: dict[str, str] = {}
        for q in questions_list:
            qid = str(q.get('question_id') or '').strip()
            label = str(q.get('correct_option_label') or '').strip()
            qtype = _infer_exam_prep_question_type(q)
            qtext = str(q.get('question_text_markdown') or '').strip()
            solution = str(
                q.get('teacher_solution_markdown')
                or q.get('final_answer_markdown')
                or q.get('correct_option_text_markdown')
                or label
            ).strip()
            if qid:
                correct_map[qid] = label
                question_type_map[qid] = qtype
                question_text_map[qid] = qtext
                question_solution_map[qid] = solution

        total_questions = len(correct_map)
        merged_answers: dict[str, str] = {}

        from apps.classes.models import StudentExamPrepAttempt

        attempt, _created = StudentExamPrepAttempt.objects.get_or_create(
            session=session,
            student=user,
            defaults={'answers': {}, 'score_0_100': 0, 'total_questions': total_questions, 'correct_count': 0},
        )

        if attempt.finalized:
            return Response({'detail': 'این آزمون قبلاً ثبت نهایی شده است.'}, status=status.HTTP_400_BAD_REQUEST)

        if isinstance(attempt.answers, dict):
            # Normalize existing JSONField keys to trimmed strings.
            for k, v in attempt.answers.items():
                key = str(k).strip()
                if not key:
                    continue
                # Preserve dict-format data from check-answer flow
                if isinstance(v, dict):
                    merged_answers[key] = v
                else:
                    merged_answers[key] = str(v).strip()

        for k, v in answers.items():
            key = str(k).strip()
            if not key:
                continue
            existing = merged_answers.get(key)
            if isinstance(existing, dict):
                # Update current_answer in structured data (check-answer flow)
                existing['current_answer'] = str(v).strip()
                merged_answers[key] = existing
            else:
                merged_answers[key] = str(v).strip()

        # Save draft answers without scoring. Only compute score when finalized.
        correct_count = 0
        score_0_100 = 0

        attempt.answers = merged_answers
        attempt.total_questions = total_questions

        update_fields = ['answers', 'total_questions', 'updated_at']

        if finalize:
            score_total = 0
            score_count = 0
            for qid, correct_label in correct_map.items():
                q_data = merged_answers.get(qid)
                qtype = question_type_map.get(qid, 'multiple_choice')

                # Check-answer flow: data is a dict with attempts/is_correct/score
                if isinstance(q_data, dict):
                    q_attempts = int(q_data.get('attempts', 0))
                    q_is_correct = bool(q_data.get('is_correct', False))
                    q_score = int(q_data.get('score', 0))
                    if q_attempts == 0:
                        # Question was never checked — score it now as legacy
                        selected = str(q_data.get('current_answer') or '').strip()
                        q_is_correct, q_score = _finalize_legacy_answer(
                            selected, correct_label, qtype, qid,
                            question_text_map, question_solution_map,
                        )
                    if q_is_correct:
                        correct_count += 1
                    score_total += q_score
                    score_count += 1
                else:
                    # Legacy flow: plain string answer
                    selected = str(q_data or '').strip() if q_data else ''
                    q_is_correct, q_score = _finalize_legacy_answer(
                        selected, correct_label, qtype, qid,
                        question_text_map, question_solution_map,
                    )
                    if q_is_correct:
                        correct_count += 1
                    score_total += q_score
                    score_count += 1

            score_0_100 = int(round(score_total / score_count)) if score_count > 0 else 0
            attempt.correct_count = correct_count
            attempt.score_0_100 = score_0_100
            attempt.finalized = True
            update_fields.extend(['correct_count', 'score_0_100', 'finalized'])

        attempt.save(update_fields=update_fields)

        payload = {
            'score_0_100': int(score_0_100),
            'correct_count': int(correct_count),
            'total_questions': total_questions,
            'finalized': attempt.finalized,
        }
        return Response(StudentExamPrepSubmitResponseSerializer(payload).data)


# ---------------------------------------------------------------------------
# Per-question check-answer endpoint (exam prep)
# ---------------------------------------------------------------------------

def _score_for_attempts(attempts: int, is_correct: bool) -> int:
    """Compute score for a single question based on how many attempts it took."""
    if not is_correct:
        return 0
    if attempts <= 1:
        return 100
    if attempts == 2:
        return 75
    if attempts == 3:
        return 50
    return 25


def _finalize_legacy_answer(
    selected: str,
    correct_label: str,
    qtype: str,
    qid: str,
    question_text_map: dict[str, str],
    question_solution_map: dict[str, str],
) -> tuple[bool, int]:
    """Grade a single answer that wasn't checked via the check-answer flow.

    Returns (is_correct, score_0_100).
    """
    if not selected:
        return False, 0

    if qtype == 'multiple_choice':
        ok = bool(correct_label and selected == correct_label)
        return ok, 100 if ok else 0

    if qtype == 'true_false':
        norm_selected = _normalize_true_false_value(selected)
        norm_correct = _normalize_true_false_value(correct_label)
        ok = bool(norm_selected and norm_correct and norm_selected == norm_correct)
        return ok, 100 if ok else 0

    if qtype in ('fill_blank', 'short_answer'):
        reference = question_solution_map.get(qid) or correct_label
        qtext = question_text_map.get(qid, '')
        try:
            grading_obj, _prov, _model = grade_open_text_answer(
                question=qtext,
                reference_answer=reference,
                student_answer=selected,
            )
            q_score = max(0, min(100, int(grading_obj.get('score_0_100') or 0)))
        except Exception:
            logger.warning('LLM grading failed for exam-prep qid=%s, falling back to exact match', qid)
            q_score = 100 if selected == correct_label else 0
        return q_score >= 60, q_score

    # Unknown type → exact label match
    ok = bool(correct_label and selected == correct_label)
    return ok, 100 if ok else 0


class StudentExamPrepCheckAnswerView(APIView):
    """Check a single answer for an exam-prep question and return feedback/hint."""

    permission_classes = [IsAuthenticated, IsStudentUser]

    @extend_schema(
        tags=['Student Exam Prep'],
        summary='Check a single exam prep answer',
        operation_id='student_exam_prep_check_answer',
        request=StudentExamPrepCheckAnswerRequestSerializer,
        responses={200: StudentExamPrepCheckAnswerResponseSerializer, 400: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT},
    )
    def post(self, request, session_id: int):
        user = request.user
        phone = (getattr(user, 'phone', None) or '').strip()
        if not phone:
            return Response({'detail': 'شماره موبایل برای حساب کاربری ثبت نشده است.'}, status=status.HTTP_400_BAD_REQUEST)

        session = ClassCreationSession.objects.filter(
            id=session_id,
            is_published=True,
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
            invites__phone=phone,
        ).first()

        if session is None:
            return Response({'detail': 'آزمون آمادگی پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = StudentExamPrepCheckAnswerRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question_id = serializer.validated_data['question_id'].strip()
        student_answer = serializer.validated_data['answer'].strip()

        if not question_id:
            return Response({'detail': 'question_id الزامی است.'}, status=status.HTTP_400_BAD_REQUEST)

        # Parse questions from session
        questions_list = []
        try:
            if session.exam_prep_json:
                data = json.loads(session.exam_prep_json)
                if isinstance(data, dict):
                    normalized, changed = _normalize_exam_prep_questions(data)
                    if changed:
                        session.exam_prep_json = json.dumps(normalized, ensure_ascii=False)
                        session.save(update_fields=['exam_prep_json', 'updated_at'])
                    data = normalized
                    exam_prep = data.get('exam_prep', {})
                    raw_questions = exam_prep.get('questions', [])
                    if isinstance(raw_questions, list):
                        questions_list = raw_questions
        except (json.JSONDecodeError, TypeError):
            questions_list = []

        # Find the target question
        target_q = None
        for q in questions_list:
            if not isinstance(q, dict):
                continue
            qid = str(q.get('question_id') or '').strip()
            if qid == question_id:
                target_q = q
                break

        if target_q is None:
            return Response({'detail': 'سوال مورد نظر پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        qtype = _infer_exam_prep_question_type(target_q)
        correct_label = str(target_q.get('correct_option_label') or '').strip()
        question_text = str(target_q.get('question_text_markdown') or '').strip()
        reference_answer = str(
            target_q.get('teacher_solution_markdown')
            or target_q.get('final_answer_markdown')
            or target_q.get('correct_option_text_markdown')
            or correct_label
        ).strip()

        # Get or create attempt record
        from apps.classes.models import StudentExamPrepAttempt

        total_questions = sum(1 for q in questions_list if isinstance(q, dict) and str(q.get('question_id') or '').strip())
        attempt, _created = StudentExamPrepAttempt.objects.get_or_create(
            session=session,
            student=user,
            defaults={'answers': {}, 'score_0_100': 0, 'total_questions': total_questions, 'correct_count': 0},
        )

        if attempt.finalized:
            return Response({'detail': 'این آزمون قبلاً ثبت نهایی شده است.'}, status=status.HTTP_400_BAD_REQUEST)

        # Read current answer data for this question
        answers_data = attempt.answers if isinstance(attempt.answers, dict) else {}
        q_data = answers_data.get(question_id, {})
        if not isinstance(q_data, dict):
            # Legacy format: plain string answer — reset to new format
            q_data = {}

        prev_attempts = int(q_data.get('attempts', 0))
        already_correct = bool(q_data.get('is_correct', False))

        # If already answered correctly, don't allow further attempts
        if already_correct:
            return Response(StudentExamPrepCheckAnswerResponseSerializer({
                'is_correct': True,
                'attempts': prev_attempts,
                'hint': '',
                'encouragement': 'شما قبلاً به این سوال پاسخ صحیح داده‌اید.',
                'score_for_question': _score_for_attempts(prev_attempts, True),
            }).data)

        # Determine correctness
        is_correct = False

        if not student_answer:
            return Response({'detail': 'پاسخ خالی است.'}, status=status.HTTP_400_BAD_REQUEST)

        if qtype == 'multiple_choice':
            is_correct = bool(correct_label and student_answer == correct_label)
        elif qtype == 'true_false':
            norm_selected = _normalize_true_false_value(student_answer)
            norm_correct = _normalize_true_false_value(correct_label)
            is_correct = bool(norm_selected and norm_correct and norm_selected == norm_correct)
        elif qtype in ('fill_blank', 'short_answer'):
            try:
                grading_obj, _prov, _model = grade_open_text_answer(
                    question=question_text,
                    reference_answer=reference_answer,
                    student_answer=student_answer,
                )
                q_score = max(0, min(100, int(grading_obj.get('score_0_100') or 0)))
                is_correct = q_score >= 60
            except Exception:
                logger.warning('LLM grading failed for check-answer qid=%s, falling back to exact match', question_id)
                is_correct = student_answer == correct_label
        else:
            is_correct = bool(correct_label and student_answer == correct_label)

        new_attempts = prev_attempts + 1

        # Update answer data in attempt record
        q_data['current_answer'] = student_answer
        q_data['attempts'] = new_attempts
        q_data['is_correct'] = is_correct

        hint_text = ''
        encouragement_text = ''

        if is_correct:
            q_data['score'] = _score_for_attempts(new_attempts, True)
        else:
            q_data['score'] = 0
            # Generate hint via LLM
            try:
                hint_obj, _prov, _model = generate_answer_hint(
                    question=question_text,
                    reference_answer=reference_answer,
                    student_answer=student_answer,
                    attempt_number=new_attempts,
                )
                hint_text = str(hint_obj.get('hint') or '').strip()
                encouragement_text = str(hint_obj.get('encouragement') or '').strip()
            except Exception:
                logger.warning('LLM hint generation failed for qid=%s', question_id)
                hint_text = 'پاسخ شما صحیح نیست. دوباره تلاش کنید!'
                encouragement_text = 'اگر به کمک بیشتری نیاز دارید، می‌توانید با دستیار هوشمند صحبت کنید.'

            q_data['last_hint'] = hint_text

        answers_data[question_id] = q_data
        attempt.answers = answers_data
        attempt.total_questions = total_questions
        attempt.save(update_fields=['answers', 'total_questions', 'updated_at'])

        payload = {
            'is_correct': is_correct,
            'attempts': new_attempts,
            'hint': hint_text,
            'encouragement': encouragement_text,
            'score_for_question': _score_for_attempts(new_attempts, is_correct),
        }
        return Response(StudentExamPrepCheckAnswerResponseSerializer(payload).data)


# ---------------------------------------------------------------------------
# Helpers – exam-prep chat correctness
# ---------------------------------------------------------------------------

def _compute_is_correct(session, question_id: str | None, student_selected: str, is_checked: bool) -> bool:
    """Compute correctness server-side; never trust the client."""
    if not (question_id and is_checked and student_selected):
        return False
    try:
        questions_list: list = []
        if session.exam_prep_json:
            parsed = json.loads(session.exam_prep_json)
            if isinstance(parsed, dict):
                raw_questions = (parsed.get('exam_prep') or {}).get('questions', [])
                if isinstance(raw_questions, list):
                    questions_list = raw_questions

        for q in questions_list:
            if not isinstance(q, dict):
                continue
            qid = str(q.get('question_id') or '').strip()
            if qid == question_id:
                correct_label = str(q.get('correct_option_label') or '').strip()
                qtype = _infer_exam_prep_question_type(q)
                if qtype == 'true_false':
                    return (
                        bool(correct_label)
                        and _normalize_true_false_value(student_selected)
                        == _normalize_true_false_value(correct_label)
                    )
                return bool(correct_label) and student_selected == correct_label
    except Exception:
        pass
    return False


class StudentExamPrepChatView(APIView):
    permission_classes = [IsAuthenticated, IsStudentUser]

    @extend_schema(
        tags=['Student Exam Prep'],
        summary='Chat with Amooz AI tutor for an exam prep question',
        operation_id='student_exam_prep_chat',
        request=OpenApiTypes.OBJECT,
        responses={200: OpenApiTypes.OBJECT},
    )
    def post(self, request, session_id: int):
        user = request.user
        phone = (getattr(user, 'phone', None) or '').strip()
        if not phone:
            return Response({'detail': 'شماره موبایل برای حساب کاربری ثبت نشده است.'}, status=status.HTTP_400_BAD_REQUEST)

        session = ClassCreationSession.objects.filter(
            id=session_id,
            is_published=True,
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
            invites__phone=phone,
        ).first()

        if session is None:
            return Response({'detail': 'آزمون آمادگی پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        data = request.data if isinstance(request.data, dict) else {}
        message = str(data.get('message') or '').strip()
        question_id = str(data.get('question_id') or '').strip() or None
        student_selected = str(data.get('student_selected') or '').strip()

        def _as_bool(value: object) -> bool:
            if isinstance(value, bool):
                return value
            if value is None:
                return False
            s = str(value).strip().lower()
            return s in {'1', 'true', 'yes', 'y', 'ok'}

        is_checked = _as_bool(data.get('is_checked'))

        computed_is_correct = _compute_is_correct(session, question_id, student_selected, is_checked)

        thread = get_or_create_exam_thread(
            session=session,
            student_id=int(getattr(user, 'id', 0) or 0),
            question_id=question_id,
        )

        is_protocol = message.startswith('SYSTEM_') or message.startswith('ACTIVATION_')
        if not is_protocol:
            append_exam_message(
                thread=thread,
                role='user',
                message_type='text',
                content=message,
                payload={},
                suggestions=[],
                question_id=question_id,
            )

        try:
            resp = handle_exam_prep_message(
                session=session,
                student_id=int(getattr(user, 'id', 0) or 0),
                question_id=question_id,
                user_message=message,
                student_selected=student_selected,
                is_checked=is_checked,
                is_correct=computed_is_correct,
            )
        except Exception as exc:
            logger.exception(
                'handle_exam_prep_message failed session_id=%s question_id=%r student_id=%r',
                session_id, question_id, getattr(user, 'id', None),
            )

            error_msg = 'الان در پاسخگویی مشکلی پیش آمده. لطفاً یک بار دیگر تلاش کن.'
            if settings.DEBUG:
                error_msg += f"\nDEBUG INFO: {str(exc)}"

            resp = {
                'type': 'text',
                'content': error_msg,
                'suggestions': [],
            }

        if isinstance(resp, dict) and resp.get('type') == 'text':
            append_exam_message(
                thread=thread,
                role='assistant',
                message_type='text',
                content=str(resp.get('content') or ''),
                payload={},
                suggestions=list(resp.get('suggestions') or []),
                question_id=question_id,
            )

        return Response(resp, status=status.HTTP_200_OK)


class StudentExamPrepResultView(APIView):
    """Get exam prep result for a student (score + per-question correctness)."""

    permission_classes = [IsAuthenticated, IsStudentUser]

    @extend_schema(
        tags=['Student Exam Prep'],
        summary='Get exam prep result',
        operation_id='student_exam_prep_result',
        responses={200: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT},
    )
    def get(self, request, session_id: int):
        user = request.user
        phone = (getattr(user, 'phone', None) or '').strip()
        if not phone:
            return Response({'detail': 'شماره موبایل برای حساب کاربری ثبت نشده است.'}, status=status.HTTP_400_BAD_REQUEST)

        session = ClassCreationSession.objects.filter(
            id=session_id,
            is_published=True,
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
            invites__phone=phone,
        ).first()

        if session is None:
            return Response({'detail': 'آزمون آمادگی پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        from apps.classes.models import StudentExamPrepAttempt
        from apps.classes.serializers import StudentExamPrepResultResponseSerializer

        attempt = StudentExamPrepAttempt.objects.filter(session=session, student=user).first()
        if attempt is None:
            return Response({'detail': 'هنوز نتیجه‌ای برای این آزمون ثبت نشده است.'}, status=status.HTTP_404_NOT_FOUND)

        # Parse exam_prep_json to build correct map.
        questions_list = []
        try:
            if session.exam_prep_json:
                data = json.loads(session.exam_prep_json)
                if isinstance(data, dict):
                    normalized, changed = _normalize_exam_prep_questions(data)
                    if changed:
                        session.exam_prep_json = json.dumps(normalized, ensure_ascii=False)
                        session.save(update_fields=['exam_prep_json', 'updated_at'])
                    data = normalized
                    exam_prep = data.get('exam_prep', {})
                    raw_questions = exam_prep.get('questions', [])
                    if isinstance(raw_questions, list):
                        questions_list = raw_questions
        except (json.JSONDecodeError, TypeError):
            questions_list = []

        correct_map: dict[str, str] = {}
        question_by_id: dict[str, dict] = {}
        for q in questions_list:
            if not isinstance(q, dict):
                continue
            qid = str(q.get('question_id') or '').strip()
            label = str(q.get('correct_option_label') or '').strip()
            if qid:
                correct_map[qid] = label
                question_by_id[qid] = q

        answers_raw = attempt.answers if isinstance(attempt.answers, dict) else {}
        total_questions = len(correct_map)

        workflow_state = session.workflow_state
        v4_project_id = (
            workflow_state.get('v4ProjectId')
            if isinstance(workflow_state, dict)
            else None
        )
        v4_project_id_text = str(v4_project_id or '').strip()
        v4_url_prefix = (
            f'/api/classes/exam-prep-source-crops/{v4_project_id_text}/'
            if v4_project_id_text.isdigit() and len(v4_project_id_text) <= 12
            else ''
        )

        items = []
        correct_count = 0
        score_total = 0
        for qid, correct_label in correct_map.items():
            q_data = answers_raw.get(qid)
            if isinstance(q_data, dict):
                # New check-answer flow data
                selected = str(q_data.get('current_answer') or '').strip()
                q_attempts = int(q_data.get('attempts', 0))
                q_is_correct = bool(q_data.get('is_correct', False))
                q_score = int(q_data.get('score', 0))
            else:
                # Legacy plain-string answer
                selected = str(q_data or '').strip() if q_data else ''
                q_attempts = 0
                q_is_correct = bool(selected) and bool(correct_label) and selected == correct_label
                q_score = 100 if q_is_correct else 0

            if attempt.finalized and q_is_correct:
                correct_count += 1
            if attempt.finalized:
                score_total += q_score

            item_payload = {
                'question_id': qid,
                'selected_label': selected,
                'is_correct': bool(q_is_correct) if attempt.finalized else False,
                'attempts': q_attempts,
                'score_for_question': q_score if attempt.finalized else 0,
            }
            if attempt.finalized:
                question = question_by_id.get(qid) or {}
                safe_solution_visuals = []
                for visual in question.get('visuals') or []:
                    if not isinstance(visual, dict) or visual.get('role') != 'solution':
                        continue
                    visual_id = visual.get('id')
                    visual_url = str(visual.get('url') or '').strip()
                    # Only the V4 endpoint is student-readable after
                    # finalization.  Do not forward arbitrary JSON fields or
                    # legacy storage/object URLs.
                    if (
                        not visual_id
                        or not v4_url_prefix
                        or not visual_url.startswith(f'{v4_url_prefix}solution/')
                    ):
                        continue
                    safe_solution_visuals.append(
                        {
                            'id': visual_id,
                            'role': 'solution',
                            'optionLabel': visual.get('optionLabel'),
                            'altText': str(visual.get('altText') or '')[:500],
                            'selectedVariant': visual.get('selectedVariant') or 'source',
                            'url': visual_url,
                        }
                    )
                item_payload.update(
                    {
                        'solution_markdown': str(
                            question.get('teacher_solution_markdown')
                            or question.get('final_answer_markdown')
                            or question.get('correct_option_text_markdown')
                            or ''
                        ).strip(),
                        'teacher_solution_markdown': str(
                            question.get('teacher_solution_markdown') or ''
                        ).strip(),
                        'solution_visuals': safe_solution_visuals,
                    }
                )
            items.append(item_payload)

        score_0_100 = int(round(score_total / total_questions)) if (attempt.finalized and total_questions > 0) else 0

        # Build a flat answers dict for backward compatibility
        flat_answers: dict[str, str] = {}
        for qid in correct_map:
            q_data = answers_raw.get(qid)
            if isinstance(q_data, dict):
                flat_answers[qid] = str(q_data.get('current_answer') or '')
            else:
                flat_answers[qid] = str(q_data or '') if q_data else ''

        payload = {
            'finalized': bool(attempt.finalized),
            'score_0_100': score_0_100,
            'correct_count': correct_count,
            'total_questions': total_questions,
            'answers': flat_answers,
            'items': items,
        }
        return Response(StudentExamPrepResultResponseSerializer(payload).data, status=status.HTTP_200_OK)


class StudentExamPrepResetView(APIView):
    """Reset an exam prep attempt for a student so they can retake the exam."""

    permission_classes = [IsAuthenticated, IsStudentUser]

    @extend_schema(
        tags=['Student Exam Prep'],
        summary='Reset exam prep attempt (retake)',
        operation_id='student_exam_prep_reset',
        request=None,
        responses={200: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT},
    )
    def post(self, request, session_id: int):
        user = request.user
        phone = (getattr(user, 'phone', None) or '').strip()
        if not phone:
            return Response({'detail': 'شماره موبایل برای حساب کاربری ثبت نشده است.'}, status=status.HTTP_400_BAD_REQUEST)

        session = ClassCreationSession.objects.filter(
            id=session_id,
            is_published=True,
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
            invites__phone=phone,
        ).first()

        if session is None:
            return Response({'detail': 'آزمون آمادگی پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        from apps.classes.models import StudentExamPrepAttempt

        attempt = StudentExamPrepAttempt.objects.filter(session=session, student=user).first()
        if attempt is None:
            return Response({'detail': 'هنوز آزمونی برای ریست کردن ثبت نشده است.'}, status=status.HTTP_404_NOT_FOUND)

        # Recompute total questions from current exam JSON.
        questions_list = []
        try:
            if session.exam_prep_json:
                data = json.loads(session.exam_prep_json)
                if isinstance(data, dict):
                    exam_prep = data.get('exam_prep', {})
                    raw_questions = exam_prep.get('questions', [])
                    if isinstance(raw_questions, list):
                        questions_list = raw_questions
        except (json.JSONDecodeError, TypeError):
            questions_list = []

        total_questions = 0
        for q in questions_list:
            qid = str((q or {}).get('question_id') or '').strip() if isinstance(q, dict) else ''
            if qid:
                total_questions += 1

        attempt.answers = {}
        attempt.score_0_100 = 0
        attempt.correct_count = 0
        attempt.total_questions = total_questions
        attempt.finalized = False
        attempt.save(update_fields=['answers', 'score_0_100', 'correct_count', 'total_questions', 'finalized', 'updated_at'])

        return Response(
            {
                'finalized': False,
                'score_0_100': 0,
                'correct_count': 0,
                'total_questions': total_questions,
            },
            status=status.HTTP_200_OK,
        )


class StudentExamPrepChatHistoryView(APIView):
    permission_classes = [IsAuthenticated, IsStudentUser]

    @extend_schema(
        tags=['Student Exam Prep'],
        summary='Get previous chat messages for a student in an exam prep question',
        operation_id='student_exam_prep_chat_history',
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request, session_id: int):
        user = request.user
        phone = (getattr(user, 'phone', None) or '').strip()
        if not phone:
            return Response({'detail': 'شماره موبایل برای حساب کاربری ثبت نشده است.'}, status=status.HTTP_400_BAD_REQUEST)

        session = ClassCreationSession.objects.filter(
            id=session_id,
            is_published=True,
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
            invites__phone=phone,
        ).first()
        if session is None:
            return Response({'detail': 'آزمون آمادگی پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        question_id = str(request.query_params.get('question_id') or '').strip() or None
        items = list_exam_messages(session_id=session.id, student_id=int(getattr(user, 'id', 0) or 0), question_id=question_id)
        return Response({'items': items}, status=status.HTTP_200_OK)


class StudentExamPrepChatMediaView(APIView):
    permission_classes = [IsAuthenticated, IsStudentUser]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        tags=['Student Exam Prep'],
        summary='Chat media upload (image/audio) for exam prep tutor',
        operation_id='student_exam_prep_chat_media',
        request=OpenApiTypes.OBJECT,
        responses={200: OpenApiTypes.OBJECT},
    )
    def post(self, request, session_id: int):
        user = request.user
        phone = (getattr(user, 'phone', None) or '').strip()
        if not phone:
            return Response({'detail': 'شماره موبایل برای حساب کاربری ثبت نشده است.'}, status=status.HTTP_400_BAD_REQUEST)

        session = ClassCreationSession.objects.filter(
            id=session_id,
            is_published=True,
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
            invites__phone=phone,
        ).first()

        if session is None:
            return Response({'detail': 'آزمون آمادگی پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)

        up = request.FILES.get('file')
        if up is None:
            return Response({'detail': 'فایل ارسال نشده است.'}, status=status.HTTP_400_BAD_REQUEST)

        message = str(request.data.get('message') or '').strip()
        question_id = str(request.data.get('question_id') or '').strip() or None
        student_selected = str(request.data.get('student_selected') or '').strip()

        def _as_bool(value: object) -> bool:
            if isinstance(value, bool):
                return value
            if value is None:
                return False
            s = str(value).strip().lower()
            return s in {'1', 'true', 'yes', 'y', 'ok'}

        is_checked = _as_bool(request.data.get('is_checked'))
        # Compute correctness server-side — never trust the client.
        is_correct = _compute_is_correct(session, question_id, student_selected, is_checked)

        thread = get_or_create_exam_thread(
            session=session,
            student_id=int(getattr(user, 'id', 0) or 0),
            question_id=question_id,
        )

        mime_type = (getattr(up, 'content_type', None) or '').strip() or 'application/octet-stream'
        try:
            data = up.read()
        except Exception:
            data = b''

        if not data:
            return Response({'detail': 'فایل خالی است.'}, status=status.HTTP_400_BAD_REQUEST)

        if mime_type.startswith('audio/'):
            try:
                transcript, _provider, _model = transcribe_media_bytes(data=data, mime_type=mime_type)
            except Exception as e:
                logger.error(f"Failed to transcribe exam prep media: {str(e)}")
                transcript = ""

            combined = (message or '').strip()
            if (transcript or '').strip():
                combined = (combined + '\n\n[VOICE_TRANSCRIPT]\n' + transcript.strip()).strip()

            append_exam_message(
                thread=thread,
                role='user',
                message_type='text',
                content=combined or '[VOICE]',
                payload={'mime_type': mime_type, 'original_name': getattr(up, 'name', '') or ''},
                suggestions=[],
                question_id=question_id,
            )

            resp = None
            try:
                resp = handle_exam_prep_message(
                    session=session,
                    student_id=int(getattr(user, 'id', 0) or 0),
                    question_id=question_id,
                    user_message=combined,
                    student_selected=student_selected,
                    is_checked=is_checked,
                    is_correct=is_correct,
                )
            except Exception:
                logger.exception(
                    'handle_exam_prep_message (audio) failed session_id=%s question_id=%r',
                    session_id, question_id,
                )
                resp = {
                    'type': 'text',
                    'content': 'الان در پردازش فایل صوتی مشکلی پیش آمده. لطفاً دوباره تلاش کن.',
                    'suggestions': [],
                }

            if isinstance(resp, dict) and resp.get('type') == 'text':
                append_exam_message(
                    thread=thread,
                    role='assistant',
                    message_type='text',
                    content=str(resp.get('content') or ''),
                    payload={},
                    suggestions=list(resp.get('suggestions') or []),
                    question_id=question_id,
                )

            return Response(resp, status=status.HTTP_200_OK)

        if mime_type.startswith('image/'):
            append_exam_message(
                thread=thread,
                role='user',
                message_type='text',
                content=(message or '').strip() or '[IMAGE]',
                payload={'mime_type': mime_type, 'original_name': getattr(up, 'name', '') or ''},
                suggestions=[],
                question_id=question_id,
            )

            resp = None
            try:
                question_context = build_exam_question_context(session=session, question_id=question_id, is_checked=is_checked)
                description = describe_exam_prep_handwriting(
                    question_context=question_context,
                    user_message=message,
                    image_bytes=data,
                    mime_type=mime_type,
                )

                resp = handle_exam_prep_message(
                    session=session,
                    student_id=int(getattr(user, 'id', 0) or 0),
                    question_id=question_id,
                    user_message=message or '[IMAGE]',
                    student_selected=student_selected,
                    is_checked=is_checked,
                    is_correct=is_correct,
                    image_description=description,
                )
            except Exception:
                logger.exception(
                    'handle_exam_prep_message (image) failed session_id=%s question_id=%r',
                    session_id, question_id,
                )
                resp = {
                    'type': 'text',
                    'content': 'الان در پردازش تصویر مشکلی پیش آمده. لطفاً دوباره تلاش کن.',
                    'suggestions': [],
                }

            if isinstance(resp, dict) and resp.get('type') == 'text':
                append_exam_message(
                    thread=thread,
                    role='assistant',
                    message_type='text',
                    content=str(resp.get('content') or ''),
                    payload={},
                    suggestions=list(resp.get('suggestions') or []),
                    question_id=question_id,
                )

            return Response(resp, status=status.HTTP_200_OK)

        return Response({'detail': 'فقط فایل تصویر یا صوت پشتیبانی می‌شود.'}, status=status.HTTP_400_BAD_REQUEST)
