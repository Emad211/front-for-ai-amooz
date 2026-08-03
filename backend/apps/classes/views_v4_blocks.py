"""Owner-scoped, content-free inspection API for current V4 source blocks."""
from __future__ import annotations

from django.http import Http404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.classes.models_v4 import ExamSourceDocument
from apps.classes.permissions import IsTeacherUser
from apps.classes.services.exam_prep_v4_blocks import get_teacher_source_blocks
from apps.classes.services.exam_prep_v4_projects import exam_prep_v4_enabled


class ExamPrepV4BlockListView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    def get(self, request, project_id: int, document_id: int):
        if not exam_prep_v4_enabled():
            raise Http404
        try:
            payload = get_teacher_source_blocks(
                teacher=request.user,
                project_id=project_id,
                document_id=document_id,
            )
        except ExamSourceDocument.DoesNotExist:
            raise Http404
        return Response(payload, status=status.HTTP_200_OK)
