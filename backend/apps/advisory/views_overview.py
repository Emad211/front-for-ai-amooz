"""The advisor cockpit's overview endpoint (``GET /api/advisory/overview/``).

ق۱۱ again: new module, not views.py. One route, no ``<pk>`` — the resource is
"this advisor's whole cockpit", so there is no engagement id to resolve and no
404-not-403 decision to make; the permission class alone scopes it, and a
stranger advisor simply gets their own (possibly empty) numbers.

All measurement lives in ``services.overview``; this module only projects the
payload through the response serializer, exactly like the other view modules
delegate to their doors.
"""

from __future__ import annotations

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdvisorUser

from .serializers import AdvisorOverviewResponseSerializer
from .services import overview as overview_service


class AdvisorOverviewView(APIView):
    """``GET /api/advisory/overview/`` — per-student live metrics for the home screen.

    Three roster-level metrics plus one row per ACTIVE engagement: the feed's
    own 7-day adherence chip, the last logged day, and the newest ACTIVE
    challenge's title. Advisor-scoped by construction — every queryset comes
    from ``services/scope.py``, so an org advisor removed mid-session loses the
    org rows on the very next request, same as everywhere else.
    """

    permission_classes = [IsAuthenticated, IsAdvisorUser]

    @extend_schema(
        tags=['advisory'],
        summary='نمای کلی داشبورد مشاور',
        description=(
            'سه سنجه‌ی سطح رستر (`activeStudents`, `pendingInvites`, '
            '`averageAdherence7d`) به‌همراه یک ردیف برای هر همکاری فعال: '
            '`adherence7d` همان عدد چیپ «۷ روز» فید مطالعه است (بدون برنامهٔ '
            'منتشرشدهٔ در بازه ⇒ null)، `lastLogDate` آخرین روزِ گزارش ثبت‌شده '
            'و `activeChallengeTitle` عنوان جدیدترین چالش فعال است. '
            '`pendingInvites` همهٔ دعوت‌نامه‌های بی‌پاسخ را می‌شمارد، منقضی‌شده‌ها '
            'نیز — دقیقاً مثل `/api/advisory/students/`.'
        ),
        responses={
            200: AdvisorOverviewResponseSerializer,
            401: OpenApiResponse(description='ناشناس'),
            403: OpenApiResponse(description='نقش غیر از مشاور'),
        },
    )
    def get(self, request):
        payload = overview_service.advisor_overview(request.user)
        return Response(AdvisorOverviewResponseSerializer(payload).data)
