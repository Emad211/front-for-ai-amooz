"""Feature-gated teacher API for Exam Prep V4 source intake."""
from __future__ import annotations

import logging
import os

from django.conf import settings
from django.http import Http404
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.classes.models_v4 import ExamProject, ExamSourceDocument
from apps.classes.permissions import IsTeacherUser
from apps.classes.serializers_v4 import (
    ExamPrepV4BatchUploadControlSerializer,
    parse_upload_metadata,
)
from apps.classes.services.exam_prep_v4_projects import (
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

logger = logging.getLogger(__name__)


def _max_batch_files() -> int:
    raw = getattr(
        settings,
        'EXAM_PREP_V4_MAX_FILES_PER_REQUEST',
        os.getenv('EXAM_PREP_V4_MAX_FILES_PER_REQUEST', '10'),
    )
    try:
        return min(20, max(1, int(raw)))
    except (TypeError, ValueError):
        return 10


def _mark_dispatch_failed(document_ids: list[int], exc: Exception) -> None:
    detail = str(exc)[:2000]
    documents = list(
        ExamSourceDocument.objects.filter(
            id__in=document_ids,
            classification_fingerprint='',
        ).values_list('id', 'project_id')
    )
    eligible_document_ids = [document_id for document_id, _ in documents]
    project_ids = [project_id for _, project_id in documents]
    ExamSourceDocument.objects.filter(id__in=eligible_document_ids).update(
        status=ExamSourceDocument.Status.FAILED,
        error_code='dispatch_failed',
        error_detail=detail,
    )
    ExamProject.objects.filter(id__in=project_ids).update(
        status=ExamProject.Status.FAILED,
        error_code='dispatch_failed',
        error_detail=detail,
        workflow_state={
            'stage': 'failed',
            'message': 'ارسال پردازش به صف انجام نشد؛ فایل محفوظ است و می‌توان دوباره تلاش کرد.',
            'progressPercent': 0,
        },
    )


def _control_payload(request) -> dict[str, object]:
    return {
        key: value
        for key in ('organizationId', 'studyGroupId')
        if (value := request.data.get(key)) not in (None, '')
    }


class ExamPrepV4BatchUploadView(APIView):
    """Upload several PDFs while creating one independent exam per file."""

    permission_classes = [IsAuthenticated, IsTeacherUser]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        if not exam_prep_v4_enabled():
            raise Http404

        files = request.FILES.getlist('files')
        if not files:
            return Response(
                {'files': ['حداقل یک فایل PDF لازم است.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(files) > _max_batch_files():
            return Response(
                {
                    'files': [
                        f'در هر درخواست حداکثر {_max_batch_files()} فایل پذیرفته می‌شود.'
                    ]
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        controls = ExamPrepV4BatchUploadControlSerializer(
            data=_control_payload(request)
        )
        controls.is_valid(raise_exception=True)
        metadata = parse_upload_metadata(
            request.data.get('metadata'),
            file_count=len(files),
        )

        try:
            scope = resolve_exam_scope(
                user=request.user,
                organization_id=controls.validated_data.get('organizationId'),
                study_group_id=controls.validated_data.get('studyGroupId'),
            )
            uploaded = persist_uploaded_pdf_batch(
                teacher=request.user,
                uploads=files,
                metadata=metadata,
                organization=scope.organization,
                study_group=scope.study_group,
            )
        except ExamPrepV4ScopeError:
            raise Http404
        except InvalidExamPrepV4Source as exc:
            return Response(
                {'files': [str(exc)]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ExamPrepV4IdempotencyConflict as exc:
            return Response(
                {'detail': str(exc), 'code': 'idempotency_conflict'},
                status=status.HTTP_409_CONFLICT,
            )

        pending_document_ids = [
            item.document_id
            for item in uploaded
            if not item.classification_already_available
        ]
        dispatch_id = None
        if pending_document_ids:
            try:
                dispatch_id = dispatch_exam_prep_v4_sources(pending_document_ids)
            except Exception as exc:
                logger.exception(
                    'Unable to dispatch Exam Prep V4 documents: %s',
                    pending_document_ids,
                )
                _mark_dispatch_failed(pending_document_ids, exc)
                return Response(
                    {
                        'detail': (
                            'فایل‌ها با موفقیت و به‌صورت خصوصی ذخیره شدند، اما '
                            'ارسال پردازش به صف انجام نشد. با همان شناسه‌ها دوباره تلاش کنید.'
                        ),
                        'code': 'dispatch_failed',
                        'projects': [
                            {
                                'id': item.project_id,
                                'documentId': item.document_id,
                                'clientRequestId': str(item.client_request_id),
                                'clientDocumentId': str(item.client_document_id),
                            }
                            for item in uploaded
                        ],
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

        return Response(
            {
                'dispatchId': dispatch_id,
                'projects': [
                    {
                        'id': item.project_id,
                        'documentId': item.document_id,
                        'clientRequestId': str(item.client_request_id),
                        'clientDocumentId': str(item.client_document_id),
                        'title': item.title,
                        'originalName': item.original_name,
                        'status': item.project_status,
                        'documentStatus': item.document_status,
                        'reusedSource': item.reused_source,
                        'classificationAlreadyAvailable': (
                            item.classification_already_available
                        ),
                    }
                    for item in uploaded
                ],
            },
            status=status.HTTP_202_ACCEPTED,
        )
