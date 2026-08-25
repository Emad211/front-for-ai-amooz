"""Advisory weekly-assessment and call-log endpoints (restart steps 7 and 10).

ق۱۱: new module, not views.py. Both resources are advisor-internal by locked
decision — there is deliberately **no** ``me/`` route for either, so the
permission split here is one-sided: ``IsAdvisorUser`` everywhere.

``AdvisorWeeklyAssessmentsView``
    ``GET|PUT /api/advisory/students/<pk>/weekly-assessments/?week_start=…``
``AdvisorCallLogsView``
    ``GET|PUT /api/advisory/students/<pk>/call-logs/?week_start=…``

Both PUTs upsert the single row keyed ``(engagement, week_start)``; the
Saturday-anchor rule is enforced once, inside each service, through
``services.calendar.ensure_saturday``.
"""

from __future__ import annotations

from django.utils.dateparse import parse_date
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdvisorUser

from .serializers import (
    CallLogItemSerializer,
    CallLogWriteSerializer,
    WeeklyAssessmentItemSerializer,
    WeeklyAssessmentWriteSerializer,
)
from .services import assessments as assessment_service
from .services import calls as call_service
from .services.assessments import WEEKLY_ASSESSMENT_CRITERIA
from .views import _resolve_engagement_or_404


def _resolve_week_start(request):
    """``?week_start=YYYY-MM-DD`` → ``(date, None)``, or ``(None, Response)``.

    An absent parameter and an unparseable one are different mistakes with
    different messages; both are 400s before any service runs. The Saturday
    check is *not* done here — it lives in the services behind the shared ق۴
    validator, so every week-anchored endpoint rejects with the same message.
    """
    raw = request.query_params.get('week_start')
    if not raw:
        return None, Response(
            {'detail': 'پارامتر week_start الزامی است.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        week_start = parse_date(raw)
    except ValueError:
        week_start = None
    if week_start is None:
        return None, Response(
            {'detail': 'تاریخ باید به شکل YYYY-MM-DD باشد.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return week_start, None


class AdvisorWeeklyAssessmentsView(APIView):
    """The advisor's 15-criteria weekly assessment of one student."""

    permission_classes = [IsAuthenticated, IsAdvisorUser]

    @extend_schema(
        tags=['advisory'],
        summary='ارزیابی‌های هفتگی یک دانش‌آموز',
        description=(
            '`criteria` فهرست ثابت ۱۵ معیار (کد + برچسب فارسی) است و '
            '`assessments` هفته‌های ثبت‌شده را نزولی می‌دهد؛ `average` میانگین '
            'یک‌رقمِ اعشارِ امتیازهاست. این بخش داخلی مشاور است و مسیر '
            'دانش‌آموزی ندارد.'
        ),
        responses={
            200: OpenApiResponse(
                description='{criteria: [{code, label}×15], assessments: [...]}',
            ),
            404: OpenApiResponse(description='همکاری پیدا نشد'),
        },
    )
    def get(self, request, pk: int):
        engagement, error = _resolve_engagement_or_404(request, pk)
        if error is not None:
            return error
        rows = assessment_service.list_weekly_assessments(engagement)
        return Response({
            'criteria': [
                {'code': code, 'label': label}
                for code, label in WEEKLY_ASSESSMENT_CRITERIA
            ],
            'assessments': WeeklyAssessmentItemSerializer(rows, many=True).data,
        })

    @extend_schema(
        tags=['advisory'],
        summary='ثبت ارزیابی یک هفته (ایجاد یا به‌روزرسانی)',
        description=(
            'همۀ ۱۵ معیار باید امتیاز عددی ۱ تا ۵ داشته باشند؛ ذخیرهٔ دوبارهٔ '
            'همان هفته به‌روزرسانی است نه ردیف جدید. `week_start` باید شنبه '
            'باشد وگرنه ۴۰۰.'
        ),
        parameters=[
            OpenApiParameter(
                name='week_start',
                description='شنبهٔ آغاز هفته (`YYYY-MM-DD`). الزامی.',
                required=True,
                type=str,
            ),
        ],
        request=WeeklyAssessmentWriteSerializer,
        responses={
            200: WeeklyAssessmentItemSerializer,
            400: OpenApiResponse(description='هفته/امتیازها نامعتبر'),
            404: OpenApiResponse(description='همکاری پیدا نشد'),
        },
    )
    def put(self, request, pk: int):
        engagement, error = _resolve_engagement_or_404(request, pk)
        if error is not None:
            return error

        week_start, param_error = _resolve_week_start(request)
        if param_error is not None:
            return param_error

        serializer = WeeklyAssessmentWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            row = assessment_service.upsert_weekly_assessment(
                engagement,
                week_start,
                data['scores'],
                data.get('advisor_summary', ''),
                request.user,
            )
        except assessment_service.WeeklyAssessmentError as exc:
            # Base class on purpose: future rules fail as actionable 400s.
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(WeeklyAssessmentItemSerializer(row).data)


class AdvisorCallLogsView(APIView):
    """The advisor's weekly-call checklist: four weeks at a glance."""

    permission_classes = [IsAuthenticated, IsAdvisorUser]

    @extend_schema(
        tags=['advisory'],
        summary='طرح تماس هفتگی یک دانش‌آموز',
        description=(
            'چهار هفتۀ اخیر تا هفتۀ جاری، صعودی. هفته‌های بدون ردیف ذخیره‌شده '
            'با «انجام نشده» و موضوع پیش‌فرض همان هفته پر می‌شوند؛ موضوعِ '
            'ذخیره‌شده همیشه بر پیش‌فرض می‌برد.'
        ),
        responses={
            200: OpenApiResponse(description='{weeks: [weekItem×4]}'),
            404: OpenApiResponse(description='همکاری پیدا نشد'),
        },
    )
    def get(self, request, pk: int):
        engagement, error = _resolve_engagement_or_404(request, pk)
        if error is not None:
            return error
        items = call_service.list_call_logs(engagement)
        return Response({'weeks': CallLogItemSerializer(items, many=True).data})

    @extend_schema(
        tags=['advisory'],
        summary='ثبت وضعیت تماس یک هفته (ایجاد یا به‌روزرسانی)',
        description=(
            '`done` الزامی است؛ کلیدهای اختیاریِ نیامده (`callDate`/`topic`/'
            '`note`) مقدار ذخیره‌شده را نگه می‌دارند. `week_start` باید شنبه '
            'باشد وگرنه ۴۰۰.'
        ),
        parameters=[
            OpenApiParameter(
                name='week_start',
                description='شنبهٔ آغاز هفته (`YYYY-MM-DD`). الزامی.',
                required=True,
                type=str,
            ),
        ],
        request=CallLogWriteSerializer,
        responses={
            200: CallLogItemSerializer,
            400: OpenApiResponse(description='هفته نامعتبر'),
            404: OpenApiResponse(description='همکاری پیدا نشد'),
        },
    )
    def put(self, request, pk: int):
        engagement, error = _resolve_engagement_or_404(request, pk)
        if error is not None:
            return error

        week_start, param_error = _resolve_week_start(request)
        if param_error is not None:
            return param_error

        serializer = CallLogWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            row = call_service.upsert_call_log(
                engagement,
                week_start,
                done=data['done'],
                # Absent key ⇒ UNSET ⇒ stored value kept (upsert semantics).
                call_date=data.get('call_date', call_service.UNSET),
                topic=data.get('topic', call_service.UNSET),
                note=data.get('note', call_service.UNSET),
            )
        except call_service.CallLogError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        item = {
            'weekStart': row.week_start,
            'done': row.done,
            'callDate': row.call_date,
            'topic': row.topic,
            'note': row.note,
        }
        return Response(CallLogItemSerializer(item).data)
