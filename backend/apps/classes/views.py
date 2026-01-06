from __future__ import annotations

import json
import uuid
from datetime import timedelta

from django.utils import timezone
from django.conf import settings

from rest_framework import status
from rest_framework import serializers
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import extend_schema

from .models import ClassCreationSession, ClassPrerequisite
from .models import ClassInvitation
from .permissions import IsTeacherUser
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
)
from .services.transcription import transcribe_media_bytes
from .services.structure import structure_transcript_markdown
from .services.prerequisites import extract_prerequisites, generate_prerequisite_teaching
from .services.recap import generate_recap_from_structure, recap_json_to_markdown
from .services.background import run_in_background
from .services.sync_structure import sync_structure_from_session


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
        qs = ClassCreationSession.objects.filter(teacher=request.user).order_by('-created_at')
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

        if session.status != ClassCreationSession.Status.STRUCTURED or not (session.structure_json or '').strip():
            return Response({'detail': 'برای انتشار، ابتدا ساختاردهی را کامل کنید.'}, status=status.HTTP_400_BAD_REQUEST)

        if not session.is_published:
            session.is_published = True
            session.published_at = timezone.now()
            session.save(update_fields=['is_published', 'published_at', 'updated_at'])

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

            # Generate a short code; join-code flow is not wired yet.
            code = f"INV-{uuid.uuid4().hex[:10].upper()}"
            tries = 0
            while ClassInvitation.objects.filter(session=session, invite_code=code).exists() and tries < 5:
                code = f"INV-{uuid.uuid4().hex[:10].upper()}"
                tries += 1

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
                {'title': 'دانش‌آموزان', 'value': '0', 'change': '—', 'trend': 'up', 'icon': 'users'},
            ]
        )


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
