"""Advisory report endpoints (risman step 2) — ق۱۱: new module, not views.py.

Two routes over the shared reporting engine:

* ``AdvisorPlannerReportView`` — ``GET students/<pk>/reports/planner/``;
* ``AdvisorStudentReportView`` — ``GET students/<pk>/reports/student/``.

Both accept the **required** ``?from=&to=`` ISO window (to ≥ from, at most 92
inclusive days) and answer JSON; ``&format=xlsx`` swaps the planner payload
for the openpyxl workbook bytes with the §۴.۲ Content-Disposition filename.

The shells stay thin exactly like ``views_exams``: role gate → tenancy resolve
through ``scope.advisor_engagement`` (stranger ⇒ 404-not-403) → service call.
The services emit wire-ready camelCase dicts, so the JSON branch returns them
directly — except ``examScores``, which are model rows projected through the
shared ``ExamScoreItemSerializer`` so the scores table keeps one wire shape
everywhere it appears. The schema serializers below document that shape for
drf-spectacular only; they do not sit in the response path.

Routes live in the module-level ``urlpatterns`` list at the bottom so wiring
into ``urls.py`` is one ``include`` line later.
"""

from __future__ import annotations

import datetime
import json
import re

from django.urls import path
from django.utils.dateparse import parse_date
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import BaseRenderer, JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdvisorUser

from .serializers import ExamScoreItemSerializer
from .services import excel_export, reports
from .views import _resolve_engagement_or_404

MSG_BAD_DATE = 'تاریخ باید به شکل YYYY-MM-DD باشد.'
MSG_REVERSED_RANGE = 'تاریخ پایان نمی‌تواند پیش از تاریخ شروع باشد.'
MSG_RANGE_TOO_LONG = 'بازه حداکثر ۹۲ روز است.'

# Inclusive day count of the window: a «۷ روز» chip spans from..from+6, so the
# length is ``(to - from).days + 1``. 92 days ≈ one quarter — long enough for
# any chip the UI offers, short enough that no request can aggregate unbounded.
MAX_REPORT_RANGE_DAYS = 92

XLSX_CONTENT_TYPE = (
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
)

# ``format`` is a RESERVED DRF query parameter (URL_FORMAT_OVERRIDE): content
# negotiation consumes it before any view runs and raises Http404 unless a
# registered renderer claims the value. So «&format=xlsx» is implemented as a
# first-class renderer below, not as a hand-read query flag.
XLSX_FORMAT_CODE = 'xlsx'


class ReportXlsxRenderer(BaseRenderer):
    """Renders a planner-report payload as the openpyxl workbook download.

    Selected by DRF's ``?format=xlsx`` override. The report kind comes from
    the serving view's ``report_kind`` attribute, and the §۴.۲ attachment name
    is stamped onto the response from the request's raw ``from``/``to``
    values. A non-report payload reaching this renderer (an error body under
    ``?format=xlsx``) degrades to its JSON bytes so pinned Persian messages
    stay readable instead of arriving wrapped in a corrupt spreadsheet.
    """

    media_type = XLSX_CONTENT_TYPE
    format = XLSX_FORMAT_CODE
    # Binary payload: without this, DRF appends ``; charset=utf-8`` to the
    # Content-Type of every workbook response.
    charset = None

    def render(self, data, accepted_media_type=None, renderer_context=None):
        context = renderer_context or {}
        view = context.get('view')
        request = context.get('request')
        response = context.get('response')

        if not isinstance(data, dict) or 'days' not in data:
            return json.dumps(data, ensure_ascii=False, default=str).encode('utf-8')

        kind = getattr(view, 'report_kind', 'report')
        raw_from = request.query_params.get('from') if request is not None else ''
        raw_to = request.query_params.get('to') if request is not None else ''
        workbook = excel_export.report_workbook(kind, data)
        if response is not None:
            response['Content-Disposition'] = (
                f'attachment; filename=report-{kind}-{raw_from}_{raw_to}.xlsx'
            )
        return workbook.getvalue()


# Django's ``parse_date`` tolerates single-digit month/day (``2026-8-1``);
# the wire contract — and the pinned Persian message — demand the strict
# zero-padded ``YYYY-MM-DD`` shape, so the shape is checked before parsing.
ISO_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def _parse_iso_date(raw) -> datetime.date | None:
    """Strict ``YYYY-MM-DD`` parse; anything else (missing/malformed) is None."""
    if not isinstance(raw, str) or not ISO_DATE_RE.match(raw):
        return None
    return parse_date(raw)


def _resolve_range(request):
    """Validate ``?from=&to=`` into dates, or an error Response.

    Order matters and each message is pinned: missing/malformed ⇒ the format
    message; ``to < from`` ⇒ the reversed message; more than
    ``MAX_REPORT_RANGE_DAYS`` inclusive days ⇒ the cap message. Returns
    ``(date_from, date_to, None)`` or ``(None, None, response)``.
    """
    date_from = _parse_iso_date(request.query_params.get('from'))
    date_to = _parse_iso_date(request.query_params.get('to'))
    if date_from is None or date_to is None:
        return None, None, Response(
            {'detail': MSG_BAD_DATE}, status=status.HTTP_400_BAD_REQUEST,
        )
    if date_to < date_from:
        return None, None, Response(
            {'detail': MSG_REVERSED_RANGE}, status=status.HTTP_400_BAD_REQUEST,
        )
    if (date_to - date_from).days + 1 > MAX_REPORT_RANGE_DAYS:
        return None, None, Response(
            {'detail': MSG_RANGE_TOO_LONG}, status=status.HTTP_400_BAD_REQUEST,
        )
    return date_from, date_to, None


# ── schema-only serializers (documentation, not the response path) ───────────

class PlannerDayItemSerializer(serializers.Serializer):
    """One day row of the planner report."""

    date = serializers.DateField()
    planned = serializers.IntegerField()
    actual = serializers.IntegerField()


class PlannerSubjectItemSerializer(serializers.Serializer):
    """One subject row of the planner report."""

    subjectId = serializers.IntegerField()  # noqa: N815 — camelCase wire key
    name = serializers.CharField()
    planned = serializers.IntegerField()
    actual = serializers.IntegerField()
    coveragePercent = serializers.IntegerField(allow_null=True)  # noqa: N815


class PlannerTotalsSerializer(serializers.Serializer):
    """The planner report's totals block."""

    planned = serializers.IntegerField()
    actual = serializers.IntegerField()
    coveragePercent = serializers.IntegerField(allow_null=True)  # noqa: N815


class PlannerReportSerializer(serializers.Serializer):
    """«گزارش برنامه» wire shape (schema documentation)."""

    days = PlannerDayItemSerializer(many=True)
    subjects = PlannerSubjectItemSerializer(many=True)
    totals = PlannerTotalsSerializer()


class StudySeriesPointSerializer(serializers.Serializer):
    """One point of the student report's study series."""

    date = serializers.DateField()
    minutes = serializers.IntegerField()


class TestSeriesPointSerializer(serializers.Serializer):
    """One point of the student report's test series."""

    date = serializers.DateField()
    testsTaken = serializers.IntegerField()  # noqa: N815 — camelCase wire key


class SubjectShareItemSerializer(serializers.Serializer):
    """One row of the student report's subject share."""

    subjectId = serializers.IntegerField()  # noqa: N815 — camelCase wire key
    name = serializers.CharField()
    minutes = serializers.IntegerField()
    sharePercent = serializers.FloatField(allow_null=True)  # noqa: N815


class StudentReportSerializer(serializers.Serializer):
    """«گزارش دانش‌آموز» wire shape (schema documentation)."""

    studySeries = StudySeriesPointSerializer(many=True)  # noqa: N815
    testSeries = TestSeriesPointSerializer(many=True)  # noqa: N815
    subjectShare = SubjectShareItemSerializer(many=True)  # noqa: N815
    examScores = ExamScoreItemSerializer(many=True)  # noqa: N815


# ── the views ────────────────────────────────────────────────────────────────

_FROM_TO_PARAMETERS = [
    OpenApiParameter(
        name='from',
        description='شروع بازه، میلادی و اجباری (YYYY-MM-DD).',
        required=True,
        type=str,
    ),
    OpenApiParameter(
        name='to',
        description='پایان بازه، میلادی و اجباری؛ نباید پیش از «از» باشد.',
        required=True,
        type=str,
    ),
]


class AdvisorPlannerReportView(APIView):
    """``GET /api/advisory/students/<pk>/reports/planner/?from=&to=[&format=xlsx]``."""

    permission_classes = [IsAuthenticated, IsAdvisorUser]
    renderer_classes = [JSONRenderer, ReportXlsxRenderer]
    report_kind = 'planner'

    @extend_schema(
        tags=['advisory'],
        summary='گزارش برنامه‌ریزی یک دانش‌آموز',
        description=(
            '`pk` شناسه‌ی همکاری است؛ همکاریِ ناموجود یا متعلق به مشاورِ دیگر ۴۰۴. '
            '`from` و `to` میلادی و اجباری‌اند؛ ترتیب معکوس یا بازهٔ بلندتر از '
            '۹۲ روز ۴۰۰ با پیام فارسی می‌دهد. با `format=xlsx` فایل اکسل برمی‌گردد.'
        ),
        parameters=[
            *_FROM_TO_PARAMETERS,
            OpenApiParameter(
                name='format',
                description='`xlsx` برای دریافت فایل اکسل؛ بدون آن پاسخ JSON.',
                required=False,
                type=str,
            ),
        ],
        responses={
            200: PlannerReportSerializer,
            400: OpenApiResponse(description='بازهٔ نامعتبر'),
            404: OpenApiResponse(description='همکاری پیدا نشد'),
        },
    )
    def get(self, request, pk: int):
        engagement, error = _resolve_engagement_or_404(request, pk)
        if error is not None:
            return error

        date_from, date_to, error = _resolve_range(request)
        if error is not None:
            return error

        # ``?format=xlsx`` never reaches this line as a query flag — DRF's
        # content negotiation swaps in ReportXlsxRenderer, which turns this
        # same payload into the workbook download (§۴.۲ filename included).
        return Response(reports.planner_report(engagement, date_from, date_to))


class AdvisorStudentReportView(APIView):
    """``GET /api/advisory/students/<pk>/reports/student/?from=&to=``."""

    permission_classes = [IsAuthenticated, IsAdvisorUser]

    @extend_schema(
        tags=['advisory'],
        summary='گزارش مطالعه و آزمون‌های یک دانش‌آموز',
        description=(
            'همان قرارداد بازهٔ گزارش برنامه: سری مطالعه، سری تست، سهم هر درس و '
            'نمرات آزمون‌های داخل بازه (نزولی). همکاریِ غریبه ۴۰۴ است.'
        ),
        parameters=_FROM_TO_PARAMETERS,
        responses={
            200: StudentReportSerializer,
            400: OpenApiResponse(description='بازهٔ نامعتبر'),
            404: OpenApiResponse(description='همکاری پیدا نشد'),
        },
    )
    def get(self, request, pk: int):
        engagement, error = _resolve_engagement_or_404(request, pk)
        if error is not None:
            return error

        date_from, date_to, error = _resolve_range(request)
        if error is not None:
            return error

        report = reports.student_report(engagement, date_from, date_to)
        return Response({
            'studySeries': report['studySeries'],
            'testSeries': report['testSeries'],
            'subjectShare': report['subjectShare'],
            'examScores': ExamScoreItemSerializer(
                report['examScores'], many=True,
            ).data,
        })


# Registered by urls.py with one include line once the risman step-2 wave lands:
#   path('api/advisory/', include('apps.advisory.views_reports'))
urlpatterns = [
    path(
        'students/<int:pk>/reports/planner/',
        AdvisorPlannerReportView.as_view(),
        name='advisory_student_planner_report',
    ),
    path(
        'students/<int:pk>/reports/student/',
        AdvisorStudentReportView.as_view(),
        name='advisory_student_report',
    ),
]
