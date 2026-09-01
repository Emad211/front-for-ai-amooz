"""Authenticated source-crop streaming for projected Exam Prep V4 records."""
from __future__ import annotations

from io import BytesIO
import json
import logging

from django.http import FileResponse, Http404
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.classes.models import ClassInvitation, StudentExamPrepAttempt
from apps.classes.models_v4_projection import ExamV4Projection
from apps.classes.services.exam_prep_v4_projects import exam_prep_v4_enabled
from apps.classes.services.exam_prep_v4_source_crops import (
    SourceCropNotFound,
    render_source_crop,
    source_crop_url,
)

logger = logging.getLogger(__name__)


def _private_not_found() -> Http404:
    # Do not distinguish an unknown project, record, or private object.
    return Http404()


def _projection_contains_crop(
    *,
    projection: ExamV4Projection,
    record_kind: str,
    record_id: int,
) -> bool:
    """Allow only crops referenced by the teacher-approved projection."""

    if record_kind not in {'question', 'solution'}:
        return False
    try:
        payload = json.loads(projection.session.exam_prep_json or '')
    except (TypeError, ValueError):
        return False
    exam_prep = payload.get('exam_prep') if isinstance(payload, dict) else None
    questions = exam_prep.get('questions') if isinstance(exam_prep, dict) else None
    if not isinstance(questions, list):
        return False
    expected_url = source_crop_url(
        project_id=projection.project_id,
        record_kind=record_kind,
        record_id=record_id,
    )
    return any(
        isinstance(question, dict)
        and any(
            isinstance(visual, dict) and visual.get('url') == expected_url
            for visual in (question.get('visuals') or [])
        )
        for question in questions
    )


class ExamPrepSourceCropView(APIView):
    """Stream one evidence-bound crop without exposing storage object names.

    Teachers may inspect both question and solution crops for projects they
    own.  Students may inspect question crops after the linked legacy session
    is published and their phone has an invitation.  The session is the public
    product boundary: older teacher publish flows predate the V4 project flag
    and may leave ``ExamProject.is_published`` false.  Solution crops require
    the same gate plus that student's finalized attempt.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, project_id: int, record_kind: str, record_id: int):
        if not exam_prep_v4_enabled():
            raise _private_not_found()

        projection = (
            ExamV4Projection.objects.select_related('project', 'session')
            .filter(project_id=project_id)
            .first()
        )
        if projection is None:
            raise _private_not_found()

        project = projection.project
        user = request.user
        is_owner = (
            getattr(user, 'role', None) == User.Role.TEACHER
            and project.teacher_id == user.id
        )
        if not is_owner:
            # Deliberately use a 404 for unauthorized students so project and
            # record existence cannot be enumerated.
            if (
                getattr(user, 'role', None) != User.Role.STUDENT
                or record_kind not in {'question', 'solution'}
                or not projection.session.is_published
                or not _projection_contains_crop(
                    projection=projection,
                    record_kind=record_kind,
                    record_id=record_id,
                )
            ):
                raise _private_not_found()
            phone = (getattr(user, 'phone', None) or '').strip()
            if not phone or not ClassInvitation.objects.filter(
                session_id=projection.session_id,
                phone=phone,
            ).exists():
                raise _private_not_found()
            if record_kind == 'solution':
                # Solutions are intentionally gated by the student's own
                # finalized attempt.  This is the only student-facing result
                # gate; the active exam endpoint never returns this ref.
                if not StudentExamPrepAttempt.objects.filter(
                    session_id=projection.session_id,
                    student_id=user.id,
                    finalized=True,
                ).exists():
                    raise _private_not_found()

        try:
            data = render_source_crop(
                project_id=project.id,
                record_kind=record_kind,
                record_id=record_id,
            )
        except SourceCropNotFound:
            raise _private_not_found()
        except (OSError, ValueError):
            # A damaged/private object is indistinguishable from an absent one
            # to callers; keep storage details out of the response.
            logger.warning(
                'Unable to render Exam Prep V4 source crop project=%s kind=%s record=%s',
                project.id,
                record_kind,
                record_id,
                exc_info=True,
            )
            raise _private_not_found()

        response = FileResponse(BytesIO(data), content_type='image/jpeg')
        response['Content-Disposition'] = 'inline; filename="source-crop.jpg"'
        response['Cache-Control'] = 'private, no-store, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        response['Vary'] = 'Authorization, Cookie'
        response['X-Content-Type-Options'] = 'nosniff'
        # The dashboard may be hosted on a separate frontend origin. CORS
        # remains enforced by Django; CORP=same-origin would additionally
        # block the authenticated blob fetch in that normal deployment.
        response['Referrer-Policy'] = 'no-referrer'
        return response


__all__ = ['ExamPrepSourceCropView']
