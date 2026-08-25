"""Advisory intake endpoints (restart step 2, گام ۲) — ق۱۱: new module, not views.py.

Two mirrors of one form:

* ``AdvisorIntakeView`` — ``GET|PUT /api/advisory/students/<pk>/intake/``;
* ``StudentIntakeView`` — ``GET|PUT /api/advisory/me/intake/``.

Both are thin shells: role gate → tenancy resolve through ``scope.py`` →
``services.intake`` for every rule that needs the database. Reads are quiet on
the student side (no advisor is the ordinary state, answered ``200`` with
``intake: null``); writes refuse plainly with a 409 when there is no engagement
to hang the form off.
"""

from __future__ import annotations

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdvisorUser, IsStudentRole

from .serializers import IntakePayloadSerializer, IntakeWriteSerializer
from .services import intake as intake_service
from .services.scope import student_active_engagement
from .views import _resolve_engagement_or_404


class AdvisorIntakeView(APIView):
    """The advisor's window onto one student's intake form.

    ``pk`` is the engagement id; a foreign or unknown engagement is a 404 via
    the shared resolver. The form is readable and writable in any engagement
    status — it is context about the student, not a plan against time.
    """

    permission_classes = [IsAuthenticated, IsAdvisorUser]

    @extend_schema(
        tags=['advisory'],
        summary='فرم شناخت یک دانش‌آموز (خواندن)',
        description=(
            '`pk` شناسه‌ی همکاری است؛ همکاریِ ناموجود یا متعلق به مشاورِ دیگر ۴۰۴. '
            'اگر فرم هرگز ذخیره نشده باشد، همان شیء با مقادیر خالی برمی‌گردد.'
        ),
        responses={
            200: IntakePayloadSerializer,
            404: OpenApiResponse(description='همکاری پیدا نشد'),
        },
    )
    def get(self, request, pk: int):
        engagement, error = _resolve_engagement_or_404(request, pk)
        if error is not None:
            return error
        profile = intake_service.get_or_init_intake(engagement)
        return Response(IntakePayloadSerializer(profile).data)

    @extend_schema(
        tags=['advisory'],
        summary='ثبت فرم شناخت (جایگزینی کامل)',
        description=(
            'بدنه، کلِ فرم است: هر فیلدی که نیاید خالی می‌شود و ردیف‌های '
            '`classes` از نو ساخته می‌شوند. سقف ۱۰ کلاس؛ `weekday` بین ۰ تا ۶ '
            '(۰ = شنبه)؛ وقتی هر دو ساعت آمده‌اند پایان باید بعد از شروع باشد؛ '
            '`lastGpa` بین ۰ تا ۲۰ و `freeDayMinutes` بین ۰ تا ۱۴۴۰ — تخطی از '
            'هرکدام ۴۰۰ با پیام فارسی.'
        ),
        request=IntakeWriteSerializer,
        responses={
            200: IntakePayloadSerializer,
            400: OpenApiResponse(description='اعتبارسنجی فرم'),
            404: OpenApiResponse(description='همکاری پیدا نشد'),
        },
    )
    def put(self, request, pk: int):
        engagement, error = _resolve_engagement_or_404(request, pk)
        if error is not None:
            return error

        serializer = IntakeWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            profile = intake_service.replace_intake(
                engagement, serializer.validated_data, request.user,
            )
        except intake_service.IntakeError as exc:
            # The base class on purpose: any rule the door adds later must fail
            # as an actionable 400, never as a 500.
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(IntakePayloadSerializer(profile).data)


class StudentIntakeView(APIView):
    """The student's own intake form.

    Quiet read / plain-refuse write, exactly like the study log: without an
    active advisor, GET answers ``200 {"active": false, "intake": null}`` and
    PUT answers 409 — there is no engagement for the row to hang off.
    """

    permission_classes = [IsAuthenticated, IsStudentRole]

    @extend_schema(
        tags=['advisory'],
        summary='فرم شناخت خودِ دانش‌آموز',
        description=(
            'بدون مشاور فعال `200 {"active": false, "intake": null}` — خطا نیست. '
            'با مشاور فعال، همان شیء فرم که مشاور هم می‌بیند.'
        ),
        responses={
            200: OpenApiResponse(description='{active, intake}'),
        },
    )
    def get(self, request):
        engagement = student_active_engagement(request.user)
        if engagement is None:
            return Response({'active': False, 'intake': None})
        profile = intake_service.get_or_init_intake(engagement)
        return Response({
            'active': True,
            'intake': IntakePayloadSerializer(profile).data,
        })

    @extend_schema(
        tags=['advisory'],
        summary='ثبت فرم شناخت خودِ دانش‌آموز (جایگزینی کامل)',
        description=(
            'همان قواعد PUT مشاور. بدون مشاور فعال ۴۰۹ با پیام فارسی؛ '
            'پس از ذخیره، «آخرین ویرایشگر» دانش‌آموز می‌شود.'
        ),
        request=IntakeWriteSerializer,
        responses={
            200: OpenApiResponse(description='{active, intake}'),
            400: OpenApiResponse(description='اعتبارسنجی فرم'),
            409: OpenApiResponse(description='مشاور فعالی ندارید'),
        },
    )
    def put(self, request):
        engagement = student_active_engagement(request.user)
        if engagement is None:
            return Response(
                {'detail': 'ابتدا مشاور خود را تأیید کنید.'},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = IntakeWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            profile = intake_service.replace_intake(
                engagement, serializer.validated_data, request.user,
            )
        except intake_service.IntakeError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'active': True,
            'intake': IntakePayloadSerializer(profile).data,
        })
