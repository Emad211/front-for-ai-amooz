"""Owner-scoped, content-free V4 typed-record and match summary API."""
from __future__ import annotations

from django.http import Http404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.classes.models_v4 import ExamProject
from apps.classes.permissions import IsTeacherUser
from apps.classes.services.exam_prep_v4_projects import exam_prep_v4_enabled
from apps.classes.services.exam_prep_v4_records import get_teacher_record_summary


class ExamPrepV4RecordSummaryView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    def get(self, request, project_id: int):
        if not exam_prep_v4_enabled():
            raise Http404
        try:
            payload = get_teacher_record_summary(
                teacher=request.user,
                project_id=project_id,
            )
        except ExamProject.DoesNotExist:
            raise Http404
        return Response(payload, status=status.HTTP_200_OK)
