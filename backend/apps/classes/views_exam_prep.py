"""Teacher intake for the non-versioned exam-preparation PDF pipeline."""
from __future__ import annotations

import logging
import uuid

from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.classes.models import ClassCreationSession
from apps.classes.permissions import IsTeacherUser
from apps.classes.serializers import (
    ExamPrepStep1TranscribeRequestSerializer,
    ExamPrepStep1TranscribeResponseSerializer,
    is_pdf_upload,
)
from apps.classes.services.file_validation import is_probably_pdf
from apps.classes.services.exam_prep_mistral_production import PRODUCTION_ENGINE
from apps.classes.services.session_workflow import build_session_workflow_state
from apps.classes.tasks_exam_prep import process_exam_prep_pdf_session
from apps.classes.views import ExamPrepStep1TranscribeView


logger = logging.getLogger('apps.classes.exam_prep')
_ACTIVE_STATUSES = {
    ClassCreationSession.Status.EXAM_TRANSCRIBING,
    ClassCreationSession.Status.EXAM_STRUCTURING,
}


def _mistral_workflow_state(stage: str, *, message: str) -> dict:
    state = build_session_workflow_state(stage, message=message)
    state['engine'] = PRODUCTION_ENGINE
    return state


def _same_uploaded_source(session: ClassCreationSession, upload) -> bool:
    new_name = str(getattr(upload, 'name', '') or '').strip()
    old_name = str(session.source_original_name or '').strip()
    if new_name and old_name and new_name != old_name:
        return False

    try:
        new_size = int(getattr(upload, 'size', 0) or 0)
    except (TypeError, ValueError):
        new_size = 0
    try:
        old_size = int(session.source_file.size) if session.source_file else 0
    except Exception:
        old_size = 0
    return not (new_size and old_size and new_size != old_size)


def _valid_pdf_upload(upload) -> bool:
    if not is_pdf_upload(upload):
        return False
    try:
        header = upload.read(1024)
        upload.seek(0)
    except Exception:
        return False
    return is_probably_pdf(header)


def _resolve_scope(request):
    organization = None
    study_group = None
    organization_id = request.data.get('organization')
    study_group_id = request.data.get('study_group')

    if organization_id in (None, '', 'none'):
        if study_group_id not in (None, '', 'none'):
            return None, None, Response(
                {'detail': 'برای انتخاب گروه آموزشی ابتدا سازمان آموزشی را مشخص کنید.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return None, None, None

    try:
        organization_id = int(organization_id)
    except (TypeError, ValueError):
        return None, None, Response(
            {'detail': 'شناسه سازمان آموزشی نامعتبر است.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from apps.organizations.models import Organization, OrganizationMembership

    membership_exists = OrganizationMembership.objects.filter(
        user=request.user,
        organization_id=organization_id,
        status=OrganizationMembership.MemberStatus.ACTIVE,
    ).exists()
    if not membership_exists:
        return None, None, Response(
            {'detail': 'شما عضو فعال این سازمان آموزشی نیستید.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    organization = Organization.objects.filter(id=organization_id).first()
    if organization is None:
        return None, None, Response(
            {'detail': 'سازمان آموزشی پیدا نشد.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if study_group_id not in (None, '', 'none'):
        try:
            study_group_id = int(study_group_id)
        except (TypeError, ValueError):
            return None, None, Response(
                {'detail': 'شناسه گروه آموزشی نامعتبر است.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from apps.organizations.models import StudyGroup

        study_group = StudyGroup.objects.filter(
            id=study_group_id,
            organization_id=organization.id,
        ).first()
        if study_group is None:
            return None, None, Response(
                {'detail': 'گروه آموزشی نامعتبر است یا متعلق به این سازمان نیست.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

    return organization, study_group, None


class ExamPrepPdfStep1View(APIView):
    """Create one normal session and dispatch the production Mistral task."""

    permission_classes = [IsAuthenticated, IsTeacherUser]
    parser_classes = [FormParser, MultiPartParser]

    def post(self, request):
        serializer = ExamPrepStep1TranscribeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        upload = payload['file']
        # Route by file type: audio/video/image go to the legacy transcription
        # pipeline (ExamPrepStep1TranscribeView); only PDFs use the production
        # Mistral OCR pipeline below. The serializer already accepts all four
        # kinds, and is_pdf_upload checks content-type/name only (no byte read),
        # so the upload pointer is untouched for the delegated media path.
        if not is_pdf_upload(upload):
            return ExamPrepStep1TranscribeView().post(request)
        if not _valid_pdf_upload(upload):
            return Response(
                {'file': ['برای آمادگی آزمون یک فایل PDF معتبر بارگذاری کنید.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        title = payload['title']
        description = payload.get('description', '')
        client_request_id = payload.get('client_request_id')

        if client_request_id is not None:
            existing = ClassCreationSession.objects.filter(
                teacher=request.user,
                client_request_id=client_request_id,
            ).first()
            if existing is not None:
                if (
                    existing.pipeline_type == ClassCreationSession.PipelineType.EXAM_PREP
                    and _same_uploaded_source(existing, upload)
                ):
                    response_status = (
                        status.HTTP_202_ACCEPTED
                        if existing.status in _ACTIVE_STATUSES
                        else status.HTTP_200_OK
                    )
                    return Response(
                        ExamPrepStep1TranscribeResponseSerializer(existing).data,
                        status=response_status,
                    )
                client_request_id = None

        organization, study_group, scope_error = _resolve_scope(request)
        if scope_error is not None:
            return scope_error

        try:
            with transaction.atomic():
                active_count = ClassCreationSession.objects.select_for_update(
                    skip_locked=True
                ).filter(
                    teacher=request.user,
                    pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
                    status__in=_ACTIVE_STATUSES,
                ).count()
                if active_count >= 5:
                    return Response(
                        {'detail': 'حداکثر ۵ آزمون همزمان در حال پردازش است.'},
                        status=status.HTTP_429_TOO_MANY_REQUESTS,
                    )

                session = ClassCreationSession.objects.create(
                    teacher=request.user,
                    organization=organization,
                    study_group=study_group,
                    title=title,
                    description=description,
                    pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
                    source_type=ClassCreationSession.SourceType.PDF,
                    source_file=upload,
                    source_mime_type='application/pdf',
                    source_original_name=str(getattr(upload, 'name', '') or ''),
                    status=ClassCreationSession.Status.EXAM_TRANSCRIBING,
                    client_request_id=client_request_id,
                    workflow_state=_mistral_workflow_state(
                        'queued',
                        message='PDF در صف پردازش قرار گرفت.',
                    ),
                )
        except IntegrityError:
            if client_request_id is not None:
                existing = ClassCreationSession.objects.filter(
                    teacher=request.user,
                    client_request_id=client_request_id,
                    pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
                ).first()
                if existing is not None:
                    return Response(
                        ExamPrepStep1TranscribeResponseSerializer(existing).data,
                        status=status.HTTP_202_ACCEPTED,
                    )
            return Response(
                {'detail': 'درخواست تکراری است؛ دوباره تلاش کنید.'},
                status=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.exception(
                'exam_prep.intake.persist_failed userId=%s byteSize=%s',
                request.user.id,
                max(0, int(getattr(upload, 'size', 0) or 0)),
            )
            return Response(
                {'detail': 'ذخیرهٔ PDF کامل نشد؛ دوباره تلاش کنید.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        task_id = uuid.uuid4().hex
        session.celery_task_id = task_id
        session.save(update_fields=['celery_task_id', 'updated_at'])
        try:
            process_exam_prep_pdf_session.apply_async(
                args=[session.id],
                task_id=task_id,
                queue='pipeline',
                retry=False,
            )
        except Exception:
            logger.exception(
                'exam_prep.intake.dispatch_failed sessionId=%s taskId=%s',
                session.id,
                task_id,
            )
            session.status = ClassCreationSession.Status.FAILED
            session.celery_task_id = ''
            session.error_detail = 'ارسال پردازش به صف انجام نشد.'
            session.workflow_state = _mistral_workflow_state(
                'failed',
                message='ارسال پردازش به صف انجام نشد؛ دوباره تلاش کنید.',
            )
            session.save(
                update_fields=[
                    'status',
                    'celery_task_id',
                    'error_detail',
                    'workflow_state',
                    'updated_at',
                ]
            )
            return Response(
                {
                    'code': 'exam_prep_dispatch_failed',
                    'detail': 'فایل ذخیره شد، اما پردازش شروع نشد؛ دوباره تلاش کنید.',
                    'sessionId': session.id,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        logger.info(
            'exam_prep.intake.queued sessionId=%s taskId=%s byteSize=%s',
            session.id,
            task_id,
            max(0, int(getattr(upload, 'size', 0) or 0)),
        )
        return Response(
            ExamPrepStep1TranscribeResponseSerializer(session).data,
            status=status.HTTP_202_ACCEPTED,
        )
