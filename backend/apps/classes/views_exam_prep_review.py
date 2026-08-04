"""Teacher detail view for reviewable page-first exam-prep drafts.

The public URL remains unchanged. This narrow override preserves the legacy
view's GET/DELETE behavior and only relaxes PATCH for a page-first session that
has finished processing and is explicitly ready for review. Other active
pipelines remain protected by the existing conflict guard.
"""
from __future__ import annotations

import json

from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response

from .models import ClassCreationSession, ExamPrepExtractionArtifact
from .serializers import (
    ExamPrepSessionDetailSerializer,
    ExamPrepSessionUpdateSerializer,
)
from .services.exam_prep_utils import normalize_exam_prep_json
from .views import (
    ExamPrepSessionDetailView,
    _teacher_exam_prep_sessions,
)
from .services.exam_prep_inventory_pipeline import rebuild_audit_after_teacher_review


def _is_reviewable_page_first_session(session: ClassCreationSession) -> bool:
    workflow = session.workflow_state if isinstance(session.workflow_state, dict) else {}
    return bool(
        session.pipeline_type == ClassCreationSession.PipelineType.EXAM_PREP
        and session.status == ClassCreationSession.Status.EXAM_TRANSCRIBED
        and workflow.get('engine') == 'page_first'
        and workflow.get('readyForReview') is True
        and not session.celery_task_id
        and not session.cancel_requested
    )


class PageFirstExamPrepSessionDetailView(ExamPrepSessionDetailView):
    """Keep the existing endpoint while permitting completed blocked drafts."""

    @extend_schema(
        tags=['Exam Prep'],
        summary='Update Exam Prep Session',
        request=ExamPrepSessionUpdateSerializer,
        responses={200: ExamPrepSessionDetailSerializer},
    )
    def patch(self, request, session_id: int):
        session = _teacher_exam_prep_sessions(request.user).filter(id=session_id).first()
        if session is None:
            return Response(
                {'detail': 'جلسه آمادگی آزمون یافت نشد.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ExamPrepSessionUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        normalized_json = None
        if 'exam_prep_json' in data:
            normalized_json, _changed = normalize_exam_prep_json(data['exam_prep_json'])

        updated_fields = [
            field_name
            for field_name in ('title', 'description', 'level', 'duration', 'exam_prep_json')
            if field_name in data
        ]
        if not updated_fields:
            return Response(ExamPrepSessionDetailSerializer(session).data)

        with transaction.atomic():
            session = ClassCreationSession.objects.select_for_update().get(
                id=session.id,
                teacher=request.user,
            )
            if 'exam_prep_json' in data and (
                session.is_published
                or (
                    session.is_active_pipeline
                    and not _is_reviewable_page_first_session(session)
                )
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

            # Preserve the existing V2/V3 review behavior. Page-first sessions
            # have no artifact and are revalidated by the dedicated post-save
            # signal after this save.
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
                    artifact.save(
                        update_fields=[
                            'audit',
                            'revision',
                            'teacher_reviewed_at',
                            'teacher_reviewed_by',
                            'reviewed_revision',
                            'reviewed_projection_fingerprint',
                            'updated_at',
                        ]
                    )
                else:
                    artifact.audit['teacherReviewedAt'] = timezone.now().isoformat()
                    artifact.save(update_fields=['audit', 'updated_at'])

        return Response(ExamPrepSessionDetailSerializer(session).data)
