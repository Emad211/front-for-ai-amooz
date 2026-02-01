from __future__ import annotations

import json
import re
import uuid
import traceback
from datetime import timedelta
from urllib.parse import quote

from django.utils import timezone
from django.conf import settings
from django.http import HttpResponse
from django.db.models import Count, Max, Min, Q

from rest_framework import status
from rest_framework import serializers
from rest_framework.generics import GenericAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import extend_schema
from drf_spectacular.types import OpenApiTypes

from .models import ClassCreationSession, ClassInvitation, ClassPrerequisite
from .models import ClassSection, ClassSectionQuiz, ClassSectionQuizAttempt
from .models import ClassFinalExam, ClassFinalExamAttempt
from .models import StudentInviteCode
from .permissions import IsTeacherUser, IsStudentUser
from .serializers import (
    ClassCreationSessionDetailSerializer,
    ClassCreationSessionListSerializer,
    ClassCreationSessionUpdateSerializer,
    ClassInvitationCreateSerializer,
    ClassInvitationSerializer,
    TeacherAnalyticsActivitySerializer,
    TeacherAnalyticsChartPointSerializer,
    TeacherAnalyticsDistributionItemSerializer,
    TeacherAnalyticsStatSerializer,
    TeacherStudentSerializer,
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
    # Exam Prep Pipeline serializers
    ExamPrepStep1TranscribeRequestSerializer,
    ExamPrepStep1TranscribeResponseSerializer,
    ExamPrepStep2StructureRequestSerializer,
    ExamPrepStep2StructureResponseSerializer,
    ExamPrepSessionDetailSerializer,
    # Student Exam Prep serializers
    StudentExamPrepListSerializer,
    StudentExamPrepDetailSerializer,
    StudentExamPrepSubmitRequestSerializer,
    StudentExamPrepSubmitResponseSerializer,
)
from .services.transcription import transcribe_media_bytes
from .services.structure import structure_transcript_markdown
from .services.prerequisites import extract_prerequisites, generate_prerequisite_teaching
from .services.recap import generate_recap_from_structure, recap_json_to_markdown
from .services.background import run_in_background
from .services.sync_structure import sync_structure_from_session
from .services.mediana_sms import send_publish_sms_for_session
from .services.quizzes import generate_final_exam_pool, generate_section_quiz_questions, grade_open_text_answer
from .services.pdf_export import generate_course_pdf
from .services.exam_prep_structure import extract_exam_prep_structure
from .services.invite_codes import get_or_create_invite_code_for_phone

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

from .services.student_chat_history import append_message, get_or_create_thread, list_messages
from .services.student_exam_chat_history import (
    append_message as append_exam_message,
    get_or_create_thread as get_or_create_exam_thread,
    list_messages as list_exam_messages,
)


def _process_step1_transcription(session_id: int) -> None:
    session = ClassCreationSession.objects.filter(id=session_id).first()
    if session is None:
        return
    if session.status != ClassCreationSession.Status.TRANSCRIBING:
        return

    try:
        session.source_file.open('rb')
        try:
            data = session.source_file.read()
        finally:
            session.source_file.close()

        transcript, provider, model_name = transcribe_media_bytes(
            data=data,
            mime_type=session.source_mime_type or 'application/octet-stream',
        )
        session.transcript_markdown = transcript
        session.llm_provider = provider
        session.llm_model = model_name
        session.status = ClassCreationSession.Status.TRANSCRIBED
        session.save(update_fields=['transcript_markdown', 'llm_provider', 'llm_model', 'status', 'updated_at'])
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
            teaching, provider, model_name = generate_prerequisite_teaching(prerequisite_name=prereq.name)
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
    """Compute completion percent for a student in a session.

    MVP rule: each chapter quiz passed counts equally + final exam passed counts equally.
    """

    try:
        total_sections = session.sections.count()
    except Exception:
        total_sections = 0

    total_parts = total_sections + 1
    if total_parts <= 0:
        return 0

    passed_sections = (
        ClassSectionQuiz.objects.filter(session=session, student=student, last_passed=True).count()
        if total_sections > 0
        else 0
    )
    passed_final = ClassFinalExam.objects.filter(session=session, student=student, last_passed=True).exists()
    passed_parts = passed_sections + (1 if passed_final else 0)

    pct = int(round((passed_parts / total_parts) * 100))
    return max(0, min(100, pct))


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


class Step1TranscribeView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

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

        if client_request_id is not None:
            existing = ClassCreationSession.objects.filter(
                teacher=request.user,
                client_request_id=client_request_id,
            ).first()
            if existing is not None:
                # Idempotency: return the same session on retries.
                payload = Step1TranscribeResponseSerializer(existing).data
                http_status = (
                    status.HTTP_202_ACCEPTED
                    if getattr(settings, 'CLASS_PIPELINE_ASYNC', False) and existing.status == ClassCreationSession.Status.TRANSCRIBING
                    else status.HTTP_200_OK
                )
                return Response(payload, status=http_status)

        session = ClassCreationSession.objects.create(
            teacher=request.user,
            title=title,
            description=description,
            source_file=upload,
            source_mime_type=getattr(upload, 'content_type', '') or '',
            source_original_name=getattr(upload, 'name', '') or '',
            status=ClassCreationSession.Status.TRANSCRIBING,
            client_request_id=client_request_id,
        )

        if run_full_pipeline:
            run_in_background(lambda: _process_full_pipeline(session.id), name=f'class-pipeline-1to5-{session.id}')
            return Response(Step1TranscribeResponseSerializer(session).data, status=status.HTTP_202_ACCEPTED)

        if getattr(settings, 'CLASS_PIPELINE_ASYNC', False):
            # Run in background so the teacher can navigate away without breaking the pipeline.
            run_in_background(lambda: _process_step1_transcription(session.id), name=f'class-step1-{session.id}')
            return Response(Step1TranscribeResponseSerializer(session).data, status=status.HTTP_202_ACCEPTED)

        try:
            session.source_file.open('rb')
            try:
                data = session.source_file.read()
            finally:
                session.source_file.close()

            transcript, provider, model_name = transcribe_media_bytes(
                data=data,
                mime_type=session.source_mime_type or 'application/octet-stream',
            )
            session.transcript_markdown = transcript
            session.llm_provider = provider
            session.llm_model = model_name
            session.status = ClassCreationSession.Status.TRANSCRIBED
            session.save(update_fields=['transcript_markdown', 'llm_provider', 'llm_model', 'status', 'updated_at'])
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
                    'error_detail': session.error_detail,
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

        if not session.transcript_markdown.strip():
            return Response({'detail': 'برای این جلسه هنوز متن درس آماده نیست.'}, status=status.HTTP_400_BAD_REQUEST)

        session.status = ClassCreationSession.Status.STRUCTURING
        session.save(update_fields=['status', 'updated_at'])

        if getattr(settings, 'CLASS_PIPELINE_ASYNC', False):
            run_in_background(lambda: _process_step2_structure(session.id), name=f'class-step2-{session.id}')
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
                    'error_detail': session.error_detail,
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

        if not (session.transcript_markdown or '').strip():
            return Response({'detail': 'برای این جلسه هنوز متن درس آماده نیست.'}, status=status.HTTP_400_BAD_REQUEST)

        session.status = ClassCreationSession.Status.PREREQ_EXTRACTING
        session.save(update_fields=['status', 'updated_at'])

        if getattr(settings, 'CLASS_PIPELINE_ASYNC', False):
            run_in_background(lambda: _process_step3_prerequisites(session.id), name=f'class-step3-{session.id}')
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

        if session.status == ClassCreationSession.Status.PREREQ_TEACHING:
            return Response(Step4PrerequisiteTeachingResponseSerializer(session).data, status=status.HTTP_202_ACCEPTED)

        if not session.prerequisites.exists():
            return Response({'detail': 'ابتدا مرحله پیش نیازها را اجرا کنید.'}, status=status.HTTP_400_BAD_REQUEST)

        session.status = ClassCreationSession.Status.PREREQ_TEACHING
        session.save(update_fields=['status', 'updated_at'])

        if getattr(settings, 'CLASS_PIPELINE_ASYNC', False):
            run_in_background(
                lambda: _process_step4_prereq_teaching(session.id, prerequisite_name),
                name=f'class-step4-{session.id}',
            )
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

        if not (session.structure_json or '').strip():
            return Response({'detail': 'برای این جلسه هنوز ساختار مرحله ۲ آماده نیست.'}, status=status.HTTP_400_BAD_REQUEST)

        session.status = ClassCreationSession.Status.RECAPPING
        session.save(update_fields=['status', 'updated_at'])

        if getattr(settings, 'CLASS_PIPELINE_ASYNC', False):
            run_in_background(lambda: _process_step5_recap(session.id), name=f'class-step5-{session.id}')
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
        responses={200: ClassCreationSessionListSerializer(many=True)},
    )
    def get(self, request):
        qs = ClassCreationSession.objects.filter(
            teacher=request.user,
            pipeline_type=ClassCreationSession.PipelineType.CLASS,
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

        if session.status == ClassCreationSession.Status.FAILED:
            return Response({'detail': 'این جلسه با خطا متوقف شده است.'}, status=status.HTTP_400_BAD_REQUEST)

        if not (session.structure_json or '').strip():
            return Response({'detail': 'برای انتشار، ابتدا ساختاردهی را کامل کنید.'}, status=status.HTTP_400_BAD_REQUEST)

        if not session.is_published:
            session.is_published = True
            session.published_at = timezone.now()
            session.save(update_fields=['is_published', 'published_at', 'updated_at'])

            def _send_sms() -> None:
                send_publish_sms_for_session(session.id)

            run_in_background(lambda: _send_sms(), name=f'class-publish-sms-{session.id}')

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

        serializer = ClassInvitationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phones: list[str] = serializer.validated_data['phones']

        for phone in phones:
            existing = ClassInvitation.objects.filter(session=session, phone=phone).first()
            if existing is not None:
                continue

            code = get_or_create_invite_code_for_phone(phone)
            ClassInvitation.objects.create(session=session, phone=phone, invite_code=code)

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
        invite = ClassInvitation.objects.filter(id=invite_id, session=session).first()
        if invite is None:
            return Response({'detail': 'دعوت نامه پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        invite.delete()
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
        now = timezone.now()
        start_7 = now - timedelta(days=7)
        start_14 = now - timedelta(days=14)

        qs = ClassCreationSession.objects.filter(teacher=request.user)
        total = qs.count()
        transcribed = qs.filter(status=ClassCreationSession.Status.TRANSCRIBED).count()
        structured = qs.filter(status=ClassCreationSession.Status.STRUCTURED).count()

        students_count = (
            ClassInvitation.objects.filter(session__teacher=request.user)
            .values('phone')
            .distinct()
            .count()
        )

        last7 = qs.filter(created_at__gte=start_7).count()
        prev7 = qs.filter(created_at__gte=start_14, created_at__lt=start_7).count()

        def _pct_change(cur: int, prev: int) -> str:
            if prev <= 0:
                return '—' if cur == 0 else '+100%'
            return f"{round(((cur - prev) / prev) * 100)}%"

        change = _pct_change(last7, prev7)
        trend = 'up' if last7 >= prev7 else 'down'

        return Response(
            [
                {'title': 'کل جلسات ساخت کلاس', 'value': str(total), 'change': change, 'trend': trend, 'icon': 'book'},
                {'title': 'تبدیل به متن موفق', 'value': str(transcribed), 'change': '—', 'trend': 'up', 'icon': 'trending'},
                {'title': 'ساختاردهی شده', 'value': str(structured), 'change': '—', 'trend': 'up', 'icon': 'graduation'},
                {'title': 'دانش‌آموزان', 'value': str(students_count), 'change': '—', 'trend': 'up', 'icon': 'users'},
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
        # We currently treat "students" as unique invited phone numbers across the teacher's sessions.
        # If/when an enrollment model is added, this should be updated.

        base_qs = ClassInvitation.objects.filter(session__teacher=request.user)
        teacher_phone = (getattr(request.user, 'phone', '') or '').strip()
        if teacher_phone:
            base_qs = base_qs.exclude(phone=teacher_phone)

        rows = (
            base_qs.values('phone')
            .annotate(
                enrolled_classes=Count('session', filter=Q(session__is_published=True), distinct=True),
                join_date=Min('created_at'),
                last_activity=Max('session__updated_at'),
            )
            .order_by('-last_activity', 'phone')
        )

        # Resolve known users by phone (best-effort). We only expose minimal info.
        from django.contrib.auth import get_user_model

        User = get_user_model()
        phones = [r['phone'] for r in rows]
        users_by_phone: dict[str, object] = {}
        if phones:
            user_qs = User.objects.filter(phone__in=phones).only('id', 'first_name', 'last_name', 'username', 'email', 'phone')
            for u in user_qs:
                p = (getattr(u, 'phone', None) or '').strip()
                if p:
                    users_by_phone[p] = u

        invite_codes_by_phone: dict[str, str] = {}
        if phones:
            for obj in StudentInviteCode.objects.filter(phone__in=phones).only('phone', 'code'):
                invite_codes_by_phone[obj.phone] = obj.code

        for phone in phones:
            normalized = (phone or '').strip()
            if not normalized:
                continue
            if normalized in invite_codes_by_phone:
                continue
            invite_codes_by_phone[normalized] = get_or_create_invite_code_for_phone(normalized)

        out: list[dict] = []
        for r in rows:
            phone = (r.get('phone') or '').strip()
            user = users_by_phone.get(phone)

            name = phone
            email = ''
            avatar = ''
            status_value = 'inactive'

            if user is not None:
                first = (getattr(user, 'first_name', '') or '').strip()
                last = (getattr(user, 'last_name', '') or '').strip()
                full = f"{first} {last}".strip()
                name = full or (getattr(user, 'username', '') or '').strip() or phone
                email = (getattr(user, 'email', '') or '').strip()
                status_value = 'active'

            enrolled_classes = int(r.get('enrolled_classes') or 0)
            join_dt = r.get('join_date')
            last_dt = r.get('last_activity')
            join_date = (join_dt.date().isoformat() if join_dt else timezone.localdate().isoformat())
            last_activity = (last_dt.date().isoformat() if last_dt else join_date)

            average_score = 0
            if average_score >= 85:
                performance = 'excellent'
            elif average_score >= 70:
                performance = 'good'
            else:
                performance = 'needs-improvement'

            out.append(
                {
                    'id': f"phone:{phone}",
                    'name': name,
                    'email': email,
                    'phone': phone,
                    'inviteCode': invite_codes_by_phone.get(phone, ''),
                    'avatar': avatar,
                    'enrolledClasses': enrolled_classes,
                    'completedLessons': 0,
                    'totalLessons': 0,
                    'averageScore': average_score,
                    'status': status_value,
                    'joinDate': join_date,
                    'lastActivity': last_activity,
                    'performance': performance,
                }
            )

        return Response(TeacherStudentSerializer(out, many=True).data, status=status.HTTP_200_OK)


class TeacherAnalyticsChartView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    @extend_schema(
        tags=['Classes'],
        summary='Teacher analytics: chart data (last 7 days)',
        operation_id='teacher_analytics_chart',
        responses={200: TeacherAnalyticsChartPointSerializer(many=True)},
    )
    def get(self, request):
        # No enrollment model yet; keep it real (0). Chart keys must exist.
        today = timezone.localdate()
        data = []
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            data.append({'name': d.strftime('%m/%d'), 'students': 0})
        return Response(data)


class TeacherAnalyticsDistributionView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    @extend_schema(
        tags=['Classes'],
        summary='Teacher analytics: distribution data',
        operation_id='teacher_analytics_distribution',
        responses={200: TeacherAnalyticsDistributionItemSerializer(many=True)},
    )
    def get(self, request):
        qs = ClassCreationSession.objects.filter(teacher=request.user)
        return Response(
            [
                {'name': 'Transcribed', 'value': qs.filter(status=ClassCreationSession.Status.TRANSCRIBED).count()},
                {'name': 'Structured', 'value': qs.filter(status=ClassCreationSession.Status.STRUCTURED).count()},
                {'name': 'Failed', 'value': qs.filter(status=ClassCreationSession.Status.FAILED).count()},
                {'name': 'In progress', 'value': qs.filter(status__in=[ClassCreationSession.Status.TRANSCRIBING, ClassCreationSession.Status.STRUCTURING]).count()},
            ]
        )


class TeacherAnalyticsActivitiesView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    @extend_schema(
        tags=['Classes'],
        summary='Teacher analytics: recent activity',
        operation_id='teacher_analytics_activities',
        responses={200: TeacherAnalyticsActivitySerializer(many=True)},
    )
    def get(self, request):
        qs = ClassCreationSession.objects.filter(teacher=request.user).order_by('-created_at')[:10]
        items = []
        for s in qs:
            items.append(
                {
                    'id': s.id,
                    'type': 'class_creation',
                    'user': request.user.first_name or request.user.username,
                    'action': f"Session {s.id}: {s.status}",
                    'time': s.created_at.isoformat(),
                    'icon': 'book',
                    'color': 'text-primary',
                    'bg': 'bg-primary/10',
                }
            )
        return Response(items)


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
            .distinct()
            .order_by('-published_at', '-updated_at')
        )

        out: list[dict] = []
        for session in qs:
            teacher = session.teacher
            instructor = ''
            if teacher is not None:
                instructor = (teacher.get_full_name() or getattr(teacher, 'username', '') or '').strip()

            lessons_count = 0
            try:
                lessons_count = sum(s.units.count() for s in session.sections.all())
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
                    'studentsCount': session.invites.count(),
                    'lessonsCount': lessons_count,
                    'status': 'active',
                    'createdAt': (session.published_at or session.created_at).date().isoformat(),
                    'lastActivity': (session.updated_at or session.created_at).date().isoformat(),
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
            error_trace = traceback.format_exc()
            print(
                '[CHATBOT][ERROR] handle_student_message failed'
                f' session_id={session_id} lesson_id={lesson_id!r} student_id={getattr(user, "id", None)!r}'
                f' message={message[:200]!r}'
            )
            print(error_trace)
            
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
            transcript, _provider, _model = transcribe_media_bytes(data=data, mime_type=mime_type)

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
                print(
                    '[CHATBOT][ERROR] handle_student_audio_upload failed'
                    f' session_id={session_id} lesson_id={lesson_id!r} student_id={getattr(user, "id", None)!r}'
                    f' mime_type={mime_type!r} message={message[:200]!r}'
                )
                print(traceback.format_exc())
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
                print(
                    '[CHATBOT][ERROR] handle_student_image_upload failed'
                    f' session_id={session_id} lesson_id={lesson_id!r} student_id={getattr(user, "id", None)!r}'
                    f' mime_type={mime_type!r} message={message[:200]!r}'
                )
                print(traceback.format_exc())
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
                    'correct_answer': correct,
                    'score_0_100': score,
                    'label': label,
                    'feedback': feedback,
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

        payload = {
            'score_0_100': final_score,
            'passed': passed,
            'passing_score': passing_score,
            'per_question': per_question,
            'course_progress': _compute_student_course_progress(session=session, student=user),
        }
        return Response(StudentChapterQuizSubmitResponseSerializer(payload).data, status=status.HTTP_200_OK)


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
                    feedback = 'پاسخ درست نبود.'
                    if expl:
                        feedback = f"{feedback} {expl}".strip()
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

        payload = {
            'score_0_100': score_0_100,
            'passed': passed,
            'passing_score': passing_score,
            'per_question': per_question,
            'course_progress': _compute_student_course_progress(session=session, student=user),
        }
        return Response(StudentFinalExamSubmitResponseSerializer(payload).data, status=status.HTTP_200_OK)


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

    try:
        session.source_file.open('rb')
        try:
            data = session.source_file.read()
        finally:
            session.source_file.close()

        transcript, provider, model_name = transcribe_media_bytes(
            data=data,
            mime_type=session.source_mime_type or 'application/octet-stream',
        )
        session.transcript_markdown = transcript
        session.llm_provider = provider
        session.llm_model = model_name
        session.status = ClassCreationSession.Status.EXAM_TRANSCRIBED
        session.save(update_fields=['transcript_markdown', 'llm_provider', 'llm_model', 'status', 'updated_at'])
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

    try:
        exam_prep_obj, provider, model_name = extract_exam_prep_structure(
            transcript_markdown=session.transcript_markdown,
        )
        session.exam_prep_json = json.dumps(exam_prep_obj, ensure_ascii=False)
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

        # Idempotency check
        if client_request_id is not None:
            existing = ClassCreationSession.objects.filter(
                teacher=request.user,
                client_request_id=client_request_id,
            ).first()
            if existing is not None:
                payload = ExamPrepStep1TranscribeResponseSerializer(existing).data
                http_status = (
                    status.HTTP_202_ACCEPTED
                    if existing.status == ClassCreationSession.Status.EXAM_TRANSCRIBING
                    else status.HTTP_200_OK
                )
                return Response(payload, status=http_status)

        session = ClassCreationSession.objects.create(
            teacher=request.user,
            title=title,
            description=description,
            source_file=upload,
            source_mime_type=getattr(upload, 'content_type', '') or '',
            source_original_name=getattr(upload, 'name', '') or '',
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
            status=ClassCreationSession.Status.EXAM_TRANSCRIBING,
            client_request_id=client_request_id,
        )

        if run_full_pipeline:
            run_in_background(
                lambda: _process_exam_prep_full_pipeline(session.id),
                name=f'exam-prep-pipeline-1to2-{session.id}',
            )
            return Response(ExamPrepStep1TranscribeResponseSerializer(session).data, status=status.HTTP_202_ACCEPTED)

        # Run step 1 in background
        run_in_background(
            lambda: _process_exam_prep_step1_transcription(session.id),
            name=f'exam-prep-step1-{session.id}',
        )
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

        session = ClassCreationSession.objects.filter(
            id=session_id,
            teacher=request.user,
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        ).first()

        if session is None:
            return Response({'detail': 'جلسه آمادگی آزمون یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        if session.status != ClassCreationSession.Status.EXAM_TRANSCRIBED:
            return Response(
                {'detail': f'این جلسه در وضعیت {session.status} است و قابل اجرای مرحله ۲ نیست.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        session.status = ClassCreationSession.Status.EXAM_STRUCTURING
        session.save(update_fields=['status', 'updated_at'])

        run_in_background(
            lambda: _process_exam_prep_step2_structure(session.id),
            name=f'exam-prep-step2-{session.id}',
        )
        return Response(ExamPrepStep2StructureResponseSerializer(session).data, status=status.HTTP_202_ACCEPTED)


class ExamPrepSessionDetailView(APIView):
    """Get details of an exam prep session (for polling status)."""
    permission_classes = [IsAuthenticated, IsTeacherUser]

    @extend_schema(
        tags=['Exam Prep'],
        summary='Get Exam Prep Session Detail',
        responses={200: ExamPrepSessionDetailSerializer, 404: OpenApiTypes.OBJECT},
    )
    def get(self, request, session_id: int):
        session = ClassCreationSession.objects.filter(
            id=session_id,
            teacher=request.user,
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        ).first()

        if session is None:
            return Response({'detail': 'جلسه آمادگی آزمون یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        return Response(ExamPrepSessionDetailSerializer(session).data)

    @extend_schema(
        tags=['Exam Prep'],
        summary='Delete Exam Prep Session',
        responses={204: None, 404: OpenApiTypes.OBJECT},
    )
    def delete(self, request, session_id: int):
        session = ClassCreationSession.objects.filter(
            id=session_id,
            teacher=request.user,
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        ).first()

        if session is None:
            return Response({'detail': 'جلسه آمادگی آزمون یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        session.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ExamPrepSessionListView(APIView):
    """List all exam prep sessions for the teacher."""
    permission_classes = [IsAuthenticated, IsTeacherUser]

    @extend_schema(
        tags=['Exam Prep'],
        summary='List Exam Prep Sessions',
        responses={200: ExamPrepSessionDetailSerializer(many=True)},
    )
    def get(self, request):
        sessions = ClassCreationSession.objects.filter(
            teacher=request.user,
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        ).order_by('-created_at')

        return Response(ExamPrepSessionDetailSerializer(sessions, many=True).data)


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
        session = ClassCreationSession.objects.filter(
            id=session_id,
            teacher=request.user,
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        ).first()

        if session is None:
            return Response({'detail': 'جلسه آمادگی آزمون یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        if session.status != ClassCreationSession.Status.EXAM_STRUCTURED:
            return Response(
                {'detail': f'فقط جلسه‌های با وضعیت exam_structured قابل انتشار هستند. وضعیت فعلی: {session.status}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        session.is_published = True
        session.published_at = timezone.now()
        session.save(update_fields=['is_published', 'published_at', 'updated_at'])

        # Send SMS to invited students
        def _send_sms() -> None:
            send_publish_sms_for_session(session.id)

        run_in_background(lambda: _send_sms(), name=f'exam-prep-publish-sms-{session.id}')

        return Response(ExamPrepSessionDetailSerializer(session).data)


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

        serializer = ClassInvitationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phones: list[str] = serializer.validated_data['phones']

        for phone in phones:
            existing = ClassInvitation.objects.filter(session=session, phone=phone).first()
            if existing is not None:
                continue

            code = get_or_create_invite_code_for_phone(phone)
            ClassInvitation.objects.create(session=session, phone=phone, invite_code=code)

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
        invite = ClassInvitation.objects.filter(id=invite_id, session=session).first()
        if invite is None:
            return Response({'detail': 'دعوت نامه پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        invite.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ==========================================================================
# STUDENT EXAM PREP ENDPOINTS
# ==========================================================================


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
                safe_questions.append(
                    {
                        'question_id': qid,
                        'question_text_markdown': qtext,
                        'options': opts,
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
                    exam_prep = data.get('exam_prep', {})
                    raw_questions = exam_prep.get('questions', [])
                    if isinstance(raw_questions, list):
                        questions_list = raw_questions
        except (json.JSONDecodeError, TypeError):
            questions_list = []

        correct_map: dict[str, str] = {}
        for q in questions_list:
            qid = str(q.get('question_id') or '').strip()
            label = str(q.get('correct_option_label') or '').strip()
            if qid:
                correct_map[qid] = label

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
            merged_answers.update(attempt.answers)

        for k, v in answers.items():
            key = str(k).strip()
            if not key:
                continue
            merged_answers[key] = str(v).strip()

        # Save draft answers without scoring. Only compute score when finalized.
        correct_count = 0
        score_0_100 = 0

        attempt.answers = merged_answers
        attempt.total_questions = total_questions

        update_fields = ['answers', 'total_questions', 'updated_at']

        if finalize:
            for qid, correct_label in correct_map.items():
                selected = (merged_answers.get(qid) or '').strip()
                if selected and correct_label and selected == correct_label:
                    correct_count += 1

            score_0_100 = int(round((correct_count / total_questions) * 100)) if total_questions > 0 else 0
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

        # Never trust/accept correctness from client.
        # Compute it server-side (and still do not expose the correct answer).
        computed_is_correct = False
        if question_id and is_checked and student_selected:
            try:
                questions_list = []
                if session.exam_prep_json:
                    parsed = json.loads(session.exam_prep_json)
                    if isinstance(parsed, dict):
                        raw_questions = (parsed.get('exam_prep') or {}).get('questions', [])
                        if isinstance(raw_questions, list):
                            questions_list = raw_questions

                correct_label = ''
                for q in questions_list:
                    if not isinstance(q, dict):
                        continue
                    qid = str(q.get('question_id') or '').strip()
                    if qid == question_id:
                        correct_label = str(q.get('correct_option_label') or '').strip()
                        break

                computed_is_correct = bool(correct_label) and student_selected == correct_label
            except Exception:
                computed_is_correct = False

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
            error_trace = traceback.format_exc()
            print(
                '[CHATBOT][ERROR] handle_exam_prep_message failed'
                f' session_id={session_id} question_id={question_id!r} student_id={getattr(user, "id", None)!r}'
                f' message={message[:200]!r}'
            )
            print(error_trace)

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
                    exam_prep = data.get('exam_prep', {})
                    raw_questions = exam_prep.get('questions', [])
                    if isinstance(raw_questions, list):
                        questions_list = raw_questions
        except (json.JSONDecodeError, TypeError):
            questions_list = []

        correct_map: dict[str, str] = {}
        for q in questions_list:
            qid = str(q.get('question_id') or '').strip()
            label = str(q.get('correct_option_label') or '').strip()
            if qid:
                correct_map[qid] = label

        answers = attempt.answers if isinstance(attempt.answers, dict) else {}
        total_questions = len(correct_map)

        items = []
        correct_count = 0
        for qid, correct_label in correct_map.items():
            selected = str(answers.get(qid) or '').strip()
            ok = bool(selected) and bool(correct_label) and selected == correct_label
            if attempt.finalized and ok:
                correct_count += 1
            items.append(
                {
                    'question_id': qid,
                    'selected_label': selected,
                    'is_correct': bool(ok) if attempt.finalized else False,
                }
            )

        score_0_100 = int(round((correct_count / total_questions) * 100)) if (attempt.finalized and total_questions > 0) else 0

        payload = {
            'finalized': bool(attempt.finalized),
            'score_0_100': score_0_100,
            'correct_count': correct_count,
            'total_questions': total_questions,
            'answers': {str(k): str(v) for k, v in answers.items()},
            'items': items,
        }
        return Response(StudentExamPrepResultResponseSerializer(payload).data, status=status.HTTP_200_OK)


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
        is_correct = _as_bool(request.data.get('is_correct'))

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
            transcript, _provider, _model = transcribe_media_bytes(data=data, mime_type=mime_type)
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

            resp = handle_exam_prep_message(
                session=session,
                student_id=int(getattr(user, 'id', 0) or 0),
                question_id=question_id,
                user_message=combined,
                student_selected=student_selected,
                is_checked=is_checked,
                is_correct=is_correct,
            )

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
