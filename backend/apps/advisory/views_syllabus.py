"""Wave 7 (2026-08-31): the official syllabus tree browse — درخت بودجه‌بندی.

One route: ``GET /api/advisory/subjects/<id>/syllabus/`` serving the konkur
budgeting tree of one catalog subject (chapters with their topics, ordered,
each topic carrying its approximate konkur weight).

The permission is plain ``IsAuthenticated`` — any role — on purpose: both
sides of the pair need the same tree (the advisor plans against it, the
student picks from it), and the tree itself is national reference data that
names no student, so there is nothing to scope. The per-student writes live
in ``views_growth.StudentTopicsView`` and go through ``services/topics``.
"""

from __future__ import annotations

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Subject
from .services import syllabus as syllabus_service


class SubjectSyllabusView(APIView):
    """The konkur syllabus tree of one subject — read-only catalog browse."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['advisory'],
        summary='درخت بودجه‌بندی یک درس',
        description=(
            'فصل‌ها و مباحث رسمی کنکورِ یک درس، مرتب‌شده، هر مبحث با وزن '
            'تقریبی کنکوری‌اش. برای دانش‌آموز و مشاور هر دو باز است — درخت '
            'مرجع ملی است، نه داده‌ی شخصی. درس ناموجود ۴۰۴.'
        ),
        responses={
            200: OpenApiResponse(description='{subject, chapters}'),
            404: OpenApiResponse(description='درس پیدا نشد'),
        },
    )
    def get(self, request, subject_id: int):
        subject = Subject.objects.filter(pk=subject_id).first()
        if subject is None:
            return Response(
                {'detail': 'درس پیدا نشد.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(syllabus_service.list_syllabus(subject))
