"""Advisory exam-score and exam-analysis endpoints (restart steps 5+6, گام ۵/۶)
— ق۱۱: new module, not views.py.

Six routes over two resources:

* ``AdvisorExamScoresView`` — ``GET|POST /api/advisory/students/<pk>/exam-scores/``;
* ``AdvisorExamScoreDetailView`` — ``PATCH|DELETE .../exam-scores/<score_id>/``;
* ``StudentExamScoresView`` — ``GET /api/advisory/me/exam-scores/`` (quiet mirror);
* ``AdvisorExamAnalysesView`` — ``GET|POST /api/advisory/students/<pk>/exam-analyses/``;
* ``AdvisorExamAnalysisDetailView`` — ``GET|PUT|DELETE .../exam-analyses/<analysis_id>/``;
* ``StudentExamAnalysesView`` — ``GET /api/advisory/me/exam-analyses/`` (quiet mirror).

All are thin shells: role gate → tenancy resolve through ``scope.py`` →
``services.exam_records`` for every rule that needs the database. Score lists
are newest-exam-first; PATCH is partial (only provided keys change); an
analysis PUT replaces the document wholesale; both student sides are
read-only by design.
"""

from __future__ import annotations

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdvisorUser, IsStudentRole

from .serializers import (
    ExamAnalysisItemSerializer,
    ExamAnalysisWriteSerializer,
    ExamScoreItemSerializer,
    ExamScorePatchSerializer,
    ExamScoreWriteSerializer,
)
from .services import exam_records as exam_service
from .services.scope import student_active_engagement
from .views import _resolve_engagement_or_404


class AdvisorExamScoresView(APIView):
    """The advisor's «نمرات کسب‌شده» table for one student."""

    permission_classes = [IsAuthenticated, IsAdvisorUser]

    @extend_schema(
        tags=['advisory'],
        summary='نمرات آزمون‌های یک دانش‌آموز',
        description=(
            '`pk` شناسه‌ی همکاری است؛ همکاریِ ناموجود یا متعلق به مشاورِ دیگر ۴۰۴. '
            'لیست نزولی بر تاریخ آزمون است و سقف ۴۰ ردیف به‌ازای هر همکاری دارد.'
        ),
        responses={
            200: ExamScoreItemSerializer(many=True),
            404: OpenApiResponse(description='همکاری پیدا نشد'),
        },
    )
    def get(self, request, pk: int):
        engagement, error = _resolve_engagement_or_404(request, pk)
        if error is not None:
            return error
        rows = exam_service.list_exam_scores(engagement)
        return Response(ExamScoreItemSerializer(rows, many=True).data)

    @extend_schema(
        tags=['advisory'],
        summary='ثبت نمرۀ یک آزمون',
        description=(
            '`title`، `examKind`، `examDate` و `scorePercent` الزامی‌اند؛ '
            '`subjectId` پیوند اختیاری به کاتالوگ درس است. درصد باید بین ۰ تا '
            '۱۰۰ باشد و عبور از سقف ۴۰ ردیف ۴۰۰ با پیام فارسی می‌دهد.'
        ),
        request=ExamScoreWriteSerializer,
        responses={
            201: ExamScoreItemSerializer,
            400: OpenApiResponse(description='اعتبارسنجی نمره'),
            404: OpenApiResponse(description='همکاری پیدا نشد'),
        },
    )
    def post(self, request, pk: int):
        engagement, error = _resolve_engagement_or_404(request, pk)
        if error is not None:
            return error

        serializer = ExamScoreWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            score = exam_service.create_exam_score(
                engagement, serializer.validated_data, request.user,
            )
        except exam_service.ExamRecordError as exc:
            # The base class on purpose: any rule the door adds later must fail
            # as an actionable 400, never as a 500.
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            ExamScoreItemSerializer(score).data,
            status=status.HTTP_201_CREATED,
        )


class AdvisorExamScoreDetailView(APIView):
    """One score row of one student — partial edit and delete."""

    permission_classes = [IsAuthenticated, IsAdvisorUser]

    @extend_schema(
        tags=['advisory'],
        summary='ویرایش جزئی یک نمره',
        description=(
            'فقط کلیدهای ارسالی تغییر می‌کنند؛ کلید نیامده سرِ جای خود می‌ماند. '
            'نمره‌ای که به این همکاری تعلق ندارد ۴۰۴ است.'
        ),
        request=ExamScorePatchSerializer,
        responses={
            200: ExamScoreItemSerializer,
            400: OpenApiResponse(description='اعتبارسنجی نمره'),
            404: OpenApiResponse(description='همکاری یا نمره پیدا نشد'),
        },
    )
    def patch(self, request, pk: int, score_id: int):
        engagement, error = _resolve_engagement_or_404(request, pk)
        if error is not None:
            return error
        score = exam_service.get_exam_score(engagement, score_id)
        if score is None:
            return Response(
                {'detail': 'نمره پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ExamScorePatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            score = exam_service.update_exam_score(score, serializer.validated_data)
        except exam_service.ExamRecordError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ExamScoreItemSerializer(score).data)

    @extend_schema(
        tags=['advisory'],
        summary='حذف یک نمره',
        description=('حذف قطعی ردیف نمره؛ فقط برای همکاریِ خودِ مشاور.'),
        responses={
            204: OpenApiResponse(description='حذف شد'),
            404: OpenApiResponse(description='همکاری یا نمره پیدا نشد'),
        },
    )
    def delete(self, request, pk: int, score_id: int):
        engagement, error = _resolve_engagement_or_404(request, pk)
        if error is not None:
            return error
        score = exam_service.get_exam_score(engagement, score_id)
        if score is None:
            return Response(
                {'detail': 'نمره پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND,
            )
        exam_service.delete_exam_score(score)
        return Response(status=status.HTTP_204_NO_CONTENT)


class StudentExamScoresView(APIView):
    """The student's read-only mirror of their own exam scores."""

    permission_classes = [IsAuthenticated, IsStudentRole]

    @extend_schema(
        tags=['advisory'],
        summary='نمرات آزمون‌های خودِ دانش‌آموز',
        description=(
            'بدون مشاور فعال `200 {"active": false, "scores": []}` — خطا نیست. '
            'با مشاور فعال، همان لیستی که مشاور می‌بیند؛ فقط خواندنی.'
        ),
        responses={
            200: OpenApiResponse(description='{active, scores}'),
        },
    )
    def get(self, request):
        engagement = student_active_engagement(request.user)
        if engagement is None:
            return Response({'active': False, 'scores': []})
        rows = exam_service.list_exam_scores(engagement)
        return Response({
            'active': True,
            'scores': ExamScoreItemSerializer(rows, many=True).data,
        })


# ── step 6: exam analyses ────────────────────────────────────────────────────

class AdvisorExamAnalysesView(APIView):
    """The advisor's report-card analyses for one student."""

    permission_classes = [IsAuthenticated, IsAdvisorUser]

    @extend_schema(
        tags=['advisory'],
        summary='تحلیل‌های آزمون یک دانش‌آموز',
        description=(
            '`pk` شناسه‌ی همکاری است؛ همکاریِ ناموجود یا متعلق به مشاورِ دیگر ۴۰۴. '
            'لیست نزولی بر تاریخ آزمون است و تحلیل‌های بی‌تاریخ در انتها می‌آیند.'
        ),
        responses={
            200: ExamAnalysisItemSerializer(many=True),
            404: OpenApiResponse(description='همکاری پیدا نشد'),
        },
    )
    def get(self, request, pk: int):
        engagement, error = _resolve_engagement_or_404(request, pk)
        if error is not None:
            return error
        rows = exam_service.list_exam_analyses(engagement)
        return Response(ExamAnalysisItemSerializer(rows, many=True).data)

    @extend_schema(
        tags=['advisory'],
        summary='ثبت تحلیل یک آزمون (با ردیف‌ها و نکات)',
        description=(
            'بدنه، کلِ سند است: متریک‌های کارنامه + `rows` + `notes`. شمارنده‌های '
            'شک‌دار هر ردیف نباید از `doubtfulTotal` بگذرند؛ شمارۀ سؤال بین ۱ تا '
            '۳۰۰ و بدون تکرار است؛ درصدها بین ۰ تا ۱۰۰ — تخطی از هرکدام ۴۰۰ با '
            'پیام فارسی.'
        ),
        request=ExamAnalysisWriteSerializer,
        responses={
            201: ExamAnalysisItemSerializer,
            400: OpenApiResponse(description='اعتبارسنجی تحلیل'),
            404: OpenApiResponse(description='همکاری پیدا نشد'),
        },
    )
    def post(self, request, pk: int):
        engagement, error = _resolve_engagement_or_404(request, pk)
        if error is not None:
            return error

        serializer = ExamAnalysisWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            analysis = exam_service.create_analysis(
                engagement, serializer.validated_data,
            )
        except exam_service.ExamRecordError as exc:
            # The base class on purpose: any rule the door adds later must fail
            # as an actionable 400, never as a 500.
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            ExamAnalysisItemSerializer(analysis).data,
            status=status.HTTP_201_CREATED,
        )


class AdvisorExamAnalysisDetailView(APIView):
    """One analysis of one student — read, wholesale replace, delete.

    PUT is a **set-replace of the whole document**: scalars overwritten and
    rows+notes rebuilt in one transaction, so an omitted key means «cleared»,
    never «unchanged».
    """

    permission_classes = [IsAuthenticated, IsAdvisorUser]

    @extend_schema(
        tags=['advisory'],
        summary='خواندن یک تحلیل',
        description=('تحلیلی که به این همکاری تعلق ندارد ۴۰۴ است.'),
        responses={
            200: ExamAnalysisItemSerializer,
            404: OpenApiResponse(description='همکاری یا تحلیل پیدا نشد'),
        },
    )
    def get(self, request, pk: int, analysis_id: int):
        engagement, error = _resolve_engagement_or_404(request, pk)
        if error is not None:
            return error
        analysis = exam_service.get_analysis(engagement, analysis_id)
        if analysis is None:
            return Response(
                {'detail': 'تحلیل پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND,
            )
        return Response(ExamAnalysisItemSerializer(analysis).data)

    @extend_schema(
        tags=['advisory'],
        summary='جایگزینی کامل یک تحلیل',
        description=(
            'کلِ سند جایگزین می‌شود: متریک‌ها بازنویسی و `rows`/`notes` از نو '
            'ساخته می‌شوند — کلید نیامده یعنی خالی، نه «بدون تغییر». همان '
            'اعتبارسنجی POST.'
        ),
        request=ExamAnalysisWriteSerializer,
        responses={
            200: ExamAnalysisItemSerializer,
            400: OpenApiResponse(description='اعتبارسنجی تحلیل'),
            404: OpenApiResponse(description='همکاری یا تحلیل پیدا نشد'),
        },
    )
    def put(self, request, pk: int, analysis_id: int):
        engagement, error = _resolve_engagement_or_404(request, pk)
        if error is not None:
            return error
        analysis = exam_service.get_analysis(engagement, analysis_id)
        if analysis is None:
            return Response(
                {'detail': 'تحلیل پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ExamAnalysisWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            analysis = exam_service.replace_analysis(
                analysis, serializer.validated_data,
            )
        except exam_service.ExamRecordError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ExamAnalysisItemSerializer(analysis).data)

    @extend_schema(
        tags=['advisory'],
        summary='حذف یک تحلیل',
        description=('حذف قطعی سند به‌همراه ردیف‌ها و نکاتش؛ فقط برای همکاریِ خودِ مشاور.'),
        responses={
            204: OpenApiResponse(description='حذف شد'),
            404: OpenApiResponse(description='همکاری یا تحلیل پیدا نشد'),
        },
    )
    def delete(self, request, pk: int, analysis_id: int):
        engagement, error = _resolve_engagement_or_404(request, pk)
        if error is not None:
            return error
        analysis = exam_service.get_analysis(engagement, analysis_id)
        if analysis is None:
            return Response(
                {'detail': 'تحلیل پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND,
            )
        exam_service.delete_analysis(analysis)
        return Response(status=status.HTTP_204_NO_CONTENT)


class StudentExamAnalysesView(APIView):
    """The student's read-only mirror of their advisor's analyses."""

    permission_classes = [IsAuthenticated, IsStudentRole]

    @extend_schema(
        tags=['advisory'],
        summary='تحلیل‌های آزمون خودِ دانش‌آموز',
        description=(
            'بدون مشاور فعال `200 {"active": false, "analyses": []}` — خطا نیست. '
            'با مشاور فعال، همهٔ تحلیل‌های مشاورِ خودش؛ فقط خواندنی.'
        ),
        responses={
            200: OpenApiResponse(description='{active, analyses}'),
        },
    )
    def get(self, request):
        engagement = student_active_engagement(request.user)
        if engagement is None:
            return Response({'active': False, 'analyses': []})
        rows = exam_service.list_exam_analyses(engagement)
        return Response({
            'active': True,
            'analyses': ExamAnalysisItemSerializer(rows, many=True).data,
        })
