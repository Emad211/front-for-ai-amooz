"""Org-manager advisory endpoints (risman step 3) — ق۱۱: new module, not views.py.

Three routes, all gated by ``IsOrgManager`` and all tenancy-resolved from the
requesting manager's own ACTIVE admin/deputy membership:

* ``OrgAdvisoryOverviewView``    — ``GET org/overview/``
* ``OrgAdvisoryReportView``      — ``GET org/advisors/?from=&to=``
* ``OrgReassignEngagementView``  — ``POST org/engagements/<pk>/reassign/``

The shells stay thin exactly like ``views_reports.py``: permission gate →
org resolve → service call. A user who manages no organization, or another
org's manager, is a stranger ⇒ **404** («سازمانی برای شما یافت نشد.»), never a
403 that would confirm an org exists (ق۶). The services emit wire-ready
camelCase dicts; error paths use the pinned Persian messages verbatim.

Routes live in the module-level ``urlpatterns`` list so wiring into ``urls.py``
is one include line.
"""

from __future__ import annotations

import json

from django.urls import path
from django.utils.dateparse import parse_date
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import BaseRenderer, JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsOrgManager
from apps.organizations.models import OrganizationMembership

from .services import excel_export, org_overview as svc

XLSX_CONTENT_TYPE = (
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
)
XLSX_FORMAT_CODE = 'xlsx'


class OrgAdvisorsXlsxRenderer(BaseRenderer):
    """Renders the org per-advisor report as the openpyxl workbook download.

    Selected by DRF's ``?format=xlsx`` URL_FORMAT_OVERRIDE — the same
    mechanism ``views_reports.py`` uses, so the org export needs no
    hand-read query flag either. A non-report payload reaching this renderer
    (an error body under ``?format=xlsx``) degrades to its JSON bytes so the
    pinned Persian messages stay readable instead of arriving wrapped in a
    corrupt spreadsheet.
    """

    media_type = XLSX_CONTENT_TYPE
    format = XLSX_FORMAT_CODE
    # Binary payload: without this, DRF appends ``; charset=utf-8`` to the
    # Content-Type of every workbook response.
    charset = None

    def render(self, data, accepted_media_type=None, renderer_context=None):
        context = renderer_context or {}
        request = context.get('request')
        response = context.get('response')

        if not isinstance(data, dict) or 'advisors' not in data:
            return json.dumps(data, ensure_ascii=False, default=str).encode('utf-8')

        raw_from = request.query_params.get('from') if request is not None else ''
        raw_to = request.query_params.get('to') if request is not None else ''
        workbook = excel_export.org_advisor_workbook(data)
        if response is not None:
            # Same §۴.۲ filename rule as the per-student exports.
            response['Content-Disposition'] = (
                f'attachment; filename=report-advisors-{raw_from}_{raw_to}.xlsx'
            )
        return workbook.getvalue()

MSG_NO_ORG = 'سازمانی برای شما یافت نشد.'
MSG_BAD_DATE = 'تاریخ باید به شکل YYYY-MM-DD باشد.'
MSG_REVERSED_RANGE = 'تاریخ پایان نمی‌تواند پیش از تاریخ شروع باشد.'
MSG_RANGE_TOO_LONG = 'بازه حداکثر ۹۲ روز است.'
MSG_BODY = 'بدنه‌ی درخواست نامعتبر است.'

# Same window ceiling as the per-student reports — one number, stated once there.
MAX_REPORT_RANGE_DAYS = 92


def _resolve_org(request):
    """The ACTIVE org this manager oversees, or None.

    Mirrors the organizations app's own resolution rule (ADMIN **or** DEPUTY,
    membership must be ACTIVE): a suspended manager loses the panel the moment
    their row flips, with no signal to fire. A DEPUTY is accepted because the
    role class is about *oversight of the school's people*, and deputies are
    oversight staff everywhere else in the platform.
    """
    return (
        OrganizationMembership.objects.select_related('organization')
        .filter(
            user=request.user,
            org_role__in=[
                OrganizationMembership.OrgRole.ADMIN,
                OrganizationMembership.OrgRole.DEPUTY,
            ],
            status=OrganizationMembership.MemberStatus.ACTIVE,
            organization__subscription_status='active',
        )
        .order_by('organization_id')
        .first()
    )


def _resolve_range(request):
    """Required ``?from=&to=`` ISO window; ``(None, None)`` on any violation."""
    raw_from = request.query_params.get('from', '')
    raw_to = request.query_params.get('to', '')
    date_from = parse_date(raw_from or '')
    date_to = parse_date(raw_to or '')
    if not raw_from or not raw_to or date_from is None or date_to is None:
        return None, None
    if date_to < date_from:
        return None, None
    if (date_to - date_from).days + 1 > 92:
        return None, None
    return date_from, date_to


class OrgAdvisoryOverviewView(APIView):
    """``GET /api/advisory/org/overview/`` — the panel's headline counters."""

    permission_classes = [IsAuthenticated, IsOrgManager]
    renderer_classes = [JSONRenderer]

    @extend_schema(
        tags=['advisory'],
        summary='نمای کلی پنل موسسه',
        description=(
            'آمار زندهٔ سازمانِ مدیری که درخواست را فرستاده: دانش‌آموز فعال، '
            'مشاور فعال، همکاری فعال، برنامه‌های منتشرشدهٔ هفتهٔ جاری (شنبه‌محور)، '
            'لاگ امروز و تعهد تجمعی وزنی هفته.'
        ),
        responses={
            200: OpenApiResponse(description='شمارنده‌ها'),
            404: OpenApiResponse(description='سازمانی یافت نشد'),
        },
    )
    def get(self, request):
        membership = _resolve_org(request)
        if membership is None:
            return Response({'detail': MSG_NO_ORG}, status=404)
        return Response(svc.org_overview(membership.organization))


class OrgAdvisoryReportView(APIView):
    """``GET /api/advisory/org/advisors/?from=&to=`` — the per-advisor table."""

    permission_classes = [IsAuthenticated, IsOrgManager]
    # JSON by default; ``?format=xlsx`` flips to the workbook download via
    # URL_FORMAT_OVERRIDE (same contract as the per-student reports).
    renderer_classes = [JSONRenderer, OrgAdvisorsXlsxRenderer]
    report_kind = 'org-advisors'

    @extend_schema(
        tags=['advisory'],
        summary='گزارش مشاوران موسسه',
        description=(
            'به‌ازای هر مشاورِ سازمان: تعداد شاگرد، تعهد وزنی، آزمون‌ها و '
            'شمارندهٔ ابزارها در بازهٔ `from`/`to` (اجباری، میلادی، حداکثر ۹۲ روز) '
            'به‌همراه ردیفِ هر دانش‌آموز با شناسهٔ همکاری‌اش.'
        ),
        responses={
            200: OpenApiResponse(description='ردیف‌های مشاوران'),
            400: OpenApiResponse(description='بازهٔ نامعتبر'),
            404: OpenApiResponse(description='سازمانی یافت نشد'),
        },
    )
    def get(self, request):
        membership = _resolve_org(request)
        if membership is None:
            return Response({'detail': MSG_NO_ORG}, status=404)

        date_from, date_to = _resolve_range(request)
        if date_from is None:
            if date_to is None:
                # Either a malformed date or a reversed window — tell them apart.
                raw_from = request.query_params.get('from', '')
                raw_to = request.query_params.get('to', '')
                if (parse_date(raw_from or '') and parse_date(raw_to or '')):
                    message = (
                        MSG_RANGE_TOO_LONG
                        if _days_between(raw_from, raw_to) > 92
                        else MSG_REVERSED_RANGE
                    )
                else:
                    message = MSG_BAD_DATE
            else:
                message = MSG_BAD_DATE
            return Response({'detail': message}, status=400)

        return Response(svc.org_advisor_report(
            membership.organization, date_from, date_to,
        ))


class OrgReassignEngagementView(APIView):
    """``POST /api/advisory/org/engagements/<pk>/reassign/`` — the one write."""

    permission_classes = [IsAuthenticated, IsOrgManager]
    renderer_classes = [JSONRenderer]

    @extend_schema(
        tags=['advisory'],
        summary='جابجایی دانش‌آموز به مشاور دیگر',
        description=(
            '`pk` شناسهٔ همکاری است؛ همکاریِ غریبه ۴۰۴. بدنه `{advisorId}` و '
            'مشاورِ هدف باید عضو فعال همین سازمان باشد — وگرنه ۴۰۰ با پیام فارسی.'
        ),
        responses={
            200: OpenApiResponse(description='همکاری جابجا شد'),
            400: OpenApiResponse(description='قاعدهٔ جابجایی نقض شد'),
            404: OpenApiResponse(description='سازمان یا همکاری یافت نشد'),
        },
    )
    def post(self, request, pk: int):
        membership = _resolve_org(request)
        if membership is None:
            return Response({'detail': MSG_NO_ORG}, status=404)

        body = request.data if isinstance(request.data, dict) else {}
        advisor_id = body.get('advisorId')
        if not isinstance(advisor_id, int):
            return Response({'detail': MSG_BODY}, status=400)

        try:
            engagement = svc.reassign_engagement(
                membership.organization, pk, advisor_id, request.user,
            )
        except svc.OrgResourceNotFound as exc:
            return Response({'detail': str(exc)}, status=404)
        except svc.OrgOverviewError as exc:
            return Response({'detail': str(exc)}, status=400)

        return Response({
            'engagementId': engagement.pk,
            'advisorId': engagement.advisor_id,
            'advisorName': svc._display(engagement.advisor),
            'studentName': svc._display(engagement.student),
        })


def _days_between(raw_from: str, raw_to: str) -> int:
    """Inclusive day count of two already-parsed ISO strings (error path only)."""
    d1, d2 = parse_date(raw_from), parse_date(raw_to)
    return (d2 - d1).days + 1


urlpatterns = [
    path(
        'org/overview/',
        OrgAdvisoryOverviewView.as_view(),
        name='advisory_org_overview',
    ),
    path(
        'org/advisors/',
        OrgAdvisoryReportView.as_view(),
        name='advisory_org_advisor_report',
    ),
    path(
        'org/engagements/<int:pk>/reassign/',
        OrgReassignEngagementView.as_view(),
        name='advisory_org_reassign',
    ),
]