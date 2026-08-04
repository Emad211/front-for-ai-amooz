"""Compatibility endpoints that keep the existing teacher create UI unchanged."""
from __future__ import annotations

import logging
import time
import uuid

from django.db import transaction
from django.http import Http404
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.classes.models import ClassCreationSession
from apps.classes.models_v4 import ExamProject
from apps.classes.models_v4_bridge import ExamV4SessionBridge
from apps.classes.permissions import IsTeacherUser
from apps.classes.serializers import (
    Step1TranscribeRequestSerializer,
    Step1TranscribeResponseSerializer,
    is_pdf_upload,
)
from apps.classes.serializers_v4 import parse_upload_metadata
from apps.classes.services.exam_prep_v4_create_flow import (
    bridge_payload,
    sync_create_flow_session,
)
from apps.classes.services.exam_prep_v4_projects import (
    ExamPrepV4Disabled,
    ExamPrepV4IdempotencyConflict,
    InvalidExamPrepV4Source,
    exam_prep_v4_enabled,
)
from apps.classes.services.exam_prep_v4_scope import (
    ExamPrepV4ScopeError,
    resolve_exam_scope,
)
from apps.classes.services.exam_prep_v4_uploads import persist_uploaded_pdf_batch
from apps.classes.tasks_v4 import dispatch_exam_prep_v4_sources


logger = logging.getLogger('apps.classes.exam_prep_v4')


def _optional_int(value):
    if value in (None, '', 'none'):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError from exc
    return result if result > 0 else None


class ExamPrepSourceAwareStep1View(APIView):
    """Use the new PDF engine behind the existing exam-preparation form."""

    permission_classes = [IsAuthenticated, IsTeacherUser]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        if not exam_prep_v4_enabled():
            raise Http404

        started_at = time.monotonic()
        serializer = Step1TranscribeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        uploaded_file = payload['file']
        if not is_pdf_upload(uploaded_file):
            return Response(
                {'file': ['برای آمادگی آزمون، فایل PDF سؤال و پاسخ را بارگذاری کنید.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            organization_id = _optional_int(request.data.get('organization'))
            study_group_id = _optional_int(request.data.get('study_group'))
            scope = resolve_exam_scope(
                user=request.user,
                organization_id=organization_id,
                study_group_id=study_group_id,
            )
        except (ValueError, ExamPrepV4ScopeError):
            raise Http404 from None

        request_id = payload.get('client_request_id') or uuid.uuid4()
        document_id = uuid.uuid5(
            uuid.NAMESPACE_URL,
            f'ai-amooz:source-aware-exam:{request.user.id}:{request_id}',
        )
        metadata = parse_upload_metadata(
            [
                {
                    'clientRequestId': str(request_id),
                    'clientDocumentId': str(document_id),
                    'title': payload['title'],
                    'description': payload.get('description', ''),
                }
            ],
            file_count=1,
        )

        persist_started_at = time.monotonic()
        logger.info(
            'exam_prep_v4.intake.persist_started userId=%s byteSize=%s',
            request.user.id,
            max(0, int(getattr(uploaded_file, 'size', 0) or 0)),
        )
        try:
            uploaded = persist_uploaded_pdf_batch(
                teacher=request.user,
                uploads=[uploaded_file],
                metadata=metadata,
                organization=scope.organization,
                study_group=scope.study_group,
            )[0]
            logger.info(
                'exam_prep_v4.intake.persist_completed userId=%s projectId=%s documentId=%s elapsedMs=%s',
                request.user.id,
                uploaded.project_id,
                uploaded.document_id,
                round((time.monotonic() - persist_started_at) * 1000, 2),
            )
        except (InvalidExamPrepV4Source, ExamPrepV4IdempotencyConflict) as exc:
            return Response(
                {'file': [str(exc)]},
                status=status.HTTP_409_CONFLICT,
            )
        except ExamPrepV4Disabled:
            raise Http404 from None

        project = ExamProject.objects.get(id=uploaded.project_id, teacher=request.user)
        with transaction.atomic():
            session = (
                ClassCreationSession.objects.select_for_update()
                .filter(teacher=request.user, client_request_id=request_id)
                .first()
            )
            if session is None:
                session = ClassCreationSession.objects.create(
                    teacher=request.user,
                    organization=scope.organization,
                    study_group=scope.study_group,
                    title=payload['title'],
                    description=payload.get('description', ''),
                    pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
                    source_type=ClassCreationSession.SourceType.PDF,
                    source_file='',
                    source_mime_type='application/pdf',
                    source_original_name=uploaded.original_name,
                    source_page_count=0,
                    status=ClassCreationSession.Status.EXAM_TRANSCRIBING,
                    client_request_id=request_id,
                    workflow_state={
                        'stage': 'reading_source',
                        'message': 'فایل دریافت شد و در حال بررسی ساختار صفحات است.',
                        'progressPercent': 10,
                        'warnings': [],
                        'readyForReview': False,
                        'sourceAwareProjectId': project.id,
                    },
                )
            elif session.pipeline_type != ClassCreationSession.PipelineType.EXAM_PREP:
                return Response(
                    {'detail': 'شناسهٔ درخواست قبلاً برای مورد دیگری استفاده شده است.'},
                    status=status.HTTP_409_CONFLICT,
                )

            bridge, created = ExamV4SessionBridge.objects.get_or_create(
                project=project,
                defaults={'session': session},
            )
            if not created and bridge.session_id != session.id:
                return Response(
                    {'detail': 'پروژه به پیش‌نویس دیگری متصل است.'},
                    status=status.HTTP_409_CONFLICT,
                )

        if not uploaded.classification_already_available:
            dispatch_started_at = time.monotonic()
            logger.info(
                'exam_prep_v4.intake.dispatch_started projectId=%s documentId=%s sessionId=%s',
                project.id,
                uploaded.document_id,
                session.id,
            )
            try:
                task_id = dispatch_exam_prep_v4_sources([uploaded.document_id])
            except Exception:
                logger.exception(
                    'exam_prep_v4.intake.dispatch_failed projectId=%s documentId=%s sessionId=%s elapsedMs=%s',
                    project.id,
                    uploaded.document_id,
                    session.id,
                    round((time.monotonic() - dispatch_started_at) * 1000, 2),
                )
                ExamProject.objects.filter(id=project.id).update(
                    status=ExamProject.Status.FAILED,
                    error_code='source_dispatch_failed',
                    error_detail='Source preparation task could not be queued.',
                    workflow_state={
                        'stage': 'failed',
                        'message': 'ارسال پردازش به صف انجام نشد. دوباره تلاش کنید.',
                        'progressPercent': 0,
                    },
                )
                ClassCreationSession.objects.filter(id=session.id).update(
                    status=ClassCreationSession.Status.FAILED,
                    error_detail='ارسال پردازش به صف انجام نشد. دوباره تلاش کنید.',
                    workflow_state={
                        'stage': 'failed',
                        'message': 'ارسال پردازش به صف انجام نشد. دوباره تلاش کنید.',
                        'progressPercent': 0,
                        'warnings': [],
                        'readyForReview': False,
                        'sourceAwareProjectId': project.id,
                    },
                )
                return Response(
                    {
                        'code': 'source_dispatch_failed',
                        'detail': 'فایل ذخیره شد، اما ارسال پردازش به صف انجام نشد. دوباره تلاش کنید.',
                        'sessionId': session.id,
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            ClassCreationSession.objects.filter(id=session.id).update(
                celery_task_id=str(task_id)[:255],
            )
            logger.info(
                'exam_prep_v4.intake.dispatch_completed projectId=%s documentId=%s sessionId=%s elapsedMs=%s',
                project.id,
                uploaded.document_id,
                session.id,
                round((time.monotonic() - dispatch_started_at) * 1000, 2),
            )

        session = sync_create_flow_session(project) or session
        logger.info(
            'exam_prep_v4.intake.response_ready projectId=%s documentId=%s sessionId=%s elapsedMs=%s',
            project.id,
            uploaded.document_id,
            session.id,
            round((time.monotonic() - started_at) * 1000, 2),
        )
        return Response(
            Step1TranscribeResponseSerializer(session).data,
            status=status.HTTP_202_ACCEPTED,
        )


class ExamPrepV4SessionProjectView(APIView):
    """Resolve the internal source-aware project for an existing create draft."""

    permission_classes = [IsAuthenticated, IsTeacherUser]

    def get(self, request, session_id: int):
        try:
            payload = bridge_payload(teacher=request.user, session_id=session_id)
        except ExamV4SessionBridge.DoesNotExist:
            raise Http404 from None
        return Response(payload, status=status.HTTP_200_OK)
