"""Owner-scoped projection and publication endpoints."""
from __future__ import annotations

from django.http import Http404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.classes.models_v4 import ExamProject
from apps.classes.permissions import IsTeacherUser
from apps.classes.services.exam_prep_v4_create_flow import (
    CreateFlowProjectionConflict,
    adopt_create_flow_projection,
)
from apps.classes.services.exam_prep_v4_projection import (
    ProjectionIntegrityError,
    ProjectionNotReady,
    StaleProjection,
    build_legacy_projection,
    publish_legacy_projection,
)
from apps.classes.services.exam_prep_v4_projects import exam_prep_v4_enabled


def _require_v4() -> None:
    if not exam_prep_v4_enabled():
        raise Http404


def _run(action, *, teacher, project_id: int):
    try:
        return action(teacher=teacher, project_id=project_id)
    except ExamProject.DoesNotExist:
        raise Http404
    except ProjectionNotReady:
        return Response(
            {
                'code': 'projection_not_ready',
                'detail': 'ابتدا استخراج و بازبینی موارد نیازمند توجه را کامل کنید.',
            },
            status=status.HTTP_409_CONFLICT,
        )
    except StaleProjection:
        return Response(
            {
                'code': 'stale_projection',
                'detail': 'رکوردهای مبنا تغییر کرده‌اند؛ نسخهٔ نهایی را دوباره بسازید.',
            },
            status=status.HTTP_409_CONFLICT,
        )
    except ProjectionIntegrityError as exc:
        return Response(
            {
                'code': 'projection_integrity_error',
                'detail': str(exc),
            },
            status=status.HTTP_409_CONFLICT,
        )


class ExamPrepV4ProjectionView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    def post(self, request, project_id: int):
        _require_v4()
        result = _run(
            build_legacy_projection,
            teacher=request.user,
            project_id=project_id,
        )
        if isinstance(result, Response):
            return result
        try:
            result = adopt_create_flow_projection(
                project_id=project_id,
                projection_payload=result,
            )
        except CreateFlowProjectionConflict as exc:
            return Response(
                {
                    'code': 'projection_session_conflict',
                    'detail': str(exc),
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(result, status=status.HTTP_200_OK)


class ExamPrepV4PublishView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    def post(self, request, project_id: int):
        _require_v4()
        prepared = _run(
            build_legacy_projection,
            teacher=request.user,
            project_id=project_id,
        )
        if isinstance(prepared, Response):
            return prepared
        try:
            adopt_create_flow_projection(
                project_id=project_id,
                projection_payload=prepared,
            )
        except CreateFlowProjectionConflict as exc:
            return Response(
                {
                    'code': 'projection_session_conflict',
                    'detail': str(exc),
                },
                status=status.HTTP_409_CONFLICT,
            )
        result = _run(
            publish_legacy_projection,
            teacher=request.user,
            project_id=project_id,
        )
        if isinstance(result, Response):
            return result
        try:
            result = adopt_create_flow_projection(
                project_id=project_id,
                projection_payload=result,
            )
        except CreateFlowProjectionConflict as exc:
            return Response(
                {
                    'code': 'projection_session_conflict',
                    'detail': str(exc),
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(result, status=status.HTTP_200_OK)
