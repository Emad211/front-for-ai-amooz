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

Restart wave 5 appends to this module (same ق۱۱ rationale): step 8's monthly
outlook pair below is the first two-sided resource here — advisor read/write,
student quiet mirror.
"""

from __future__ import annotations

from django.utils.dateparse import parse_date
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdvisorUser, IsStudentRole

from .serializers import (
    CallLogItemSerializer,
    CallLogWriteSerializer,
    ChallengeCreateSerializer,
    ChallengeDaysWriteSerializer,
    ChallengeItemSerializer,
    ChallengePatchSerializer,
    MonthlyOutlookPayloadSerializer,
    MonthlyOutlookWriteSerializer,
    WeeklyAssessmentItemSerializer,
    WeeklyAssessmentWriteSerializer,
)
from .services import assessments as assessment_service
from .services import calls as call_service
from .services import challenges as challenge_service
from .services import monthly as monthly_service
from .services.assessments import WEEKLY_ASSESSMENT_CRITERIA
from .services.scope import student_active_engagement
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


# ── Restart wave 5, step 8: the monthly outlook + strategies ─────────────────

class AdvisorMonthlyOutlookView(APIView):
    """One month of «ماه در یک نگاه» for one student — read and wholesale replace.

    ``month_start`` arrives as a plain Gregorian date path segment (ق۵: the
    Jalali month key is computed client-side; the server treats it as an
    opaque equality key). A never-saved month reads back as the all-empty
    payload via ``get_or_init`` semantics, exactly like the intake form.
    """

    permission_classes = [IsAuthenticated, IsAdvisorUser]

    @extend_schema(
        tags=['advisory'],
        summary='برنامهٔ ماه یک دانش‌آموز (تقویم و استراتژی‌ها)',
        description=(
            '`pk` شناسه‌ی همکاری است؛ همکاریِ ناموجود یا متعلق به مشاورِ دیگر ۴۰۴. '
            '`month_start` اولین روزِ میلادیِ ماه جلالی است. اگر ماه هرگز ذخیره '
            'نشده باشد، همان شیء با لیست‌های خالی برمی‌گردد.'
        ),
        responses={
            200: MonthlyOutlookPayloadSerializer,
            404: OpenApiResponse(description='همکاری پیدا نشد'),
        },
    )
    def get(self, request, pk: int, month_start):
        engagement, error = _resolve_engagement_or_404(request, pk)
        if error is not None:
            return error
        outlook = monthly_service.get_or_init_outlook(engagement, month_start)
        return Response(MonthlyOutlookPayloadSerializer(outlook).data)

    @extend_schema(
        tags=['advisory'],
        summary='ثبت برنامهٔ ماه (جایگزینی کامل تقویم و استراتژی‌ها)',
        description=(
            'بدنه، کلِ ماه است: `entries` و `strategies` از نو ساخته می‌شوند — '
            'کلید نیامده یعنی حذف‌شده. پوزیشن تکراری، پوزیشن بیرون از ۱ تا ۱۰ و '
            'مجری نامعتبر هرکدام ۴۰۰ با پیام فارسی می‌دهند. تاریخِ روزهای تقویم '
            'لازم نیست داخل همان ماه باشد (تقویم مرزی مجاز است).'
        ),
        request=MonthlyOutlookWriteSerializer,
        responses={
            200: MonthlyOutlookPayloadSerializer,
            400: OpenApiResponse(description='اعتبارسنجی برنامهٔ ماه'),
            404: OpenApiResponse(description='همکاری پیدا نشد'),
        },
    )
    def put(self, request, pk: int, month_start):
        engagement, error = _resolve_engagement_or_404(request, pk)
        if error is not None:
            return error

        serializer = MonthlyOutlookWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            outlook = monthly_service.upsert_outlook(
                engagement, month_start, serializer.validated_data,
            )
        except monthly_service.MonthlyOutlookError as exc:
            # The base class on purpose: any rule the door adds later must fail
            # as an actionable 400, never as a 500.
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(MonthlyOutlookPayloadSerializer(outlook).data)


class StudentMonthlyOutlookView(APIView):
    """The student's read-only mirror of their advisor's month plan."""

    permission_classes = [IsAuthenticated, IsStudentRole]

    @extend_schema(
        tags=['advisory'],
        summary='برنامهٔ ماه خودِ دانش‌آموز',
        description=(
            'بدون مشاور فعال `200 {"active": false, "outlook": null}` — خطا نیست. '
            'با مشاور فعال، همان شیء ماه که مشاور می‌بیند؛ فقط خواندنی.'
        ),
        responses={
            200: OpenApiResponse(description='{active, outlook}'),
        },
    )
    def get(self, request, month_start):
        engagement = student_active_engagement(request.user)
        if engagement is None:
            return Response({'active': False, 'outlook': None})
        outlook = monthly_service.get_or_init_outlook(engagement, month_start)
        return Response({
            'active': True,
            'outlook': MonthlyOutlookPayloadSerializer(outlook).data,
        })


# ── Restart wave 5, step 9: the 7-day challenge ──────────────────────────────

def _challenge_error_response(exc: challenge_service.ChallengeError) -> Response:
    """Map the door's error family onto the wire: state conflicts 409, rest 400."""
    if isinstance(exc, challenge_service.ChallengeStateError):
        return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)
    return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class AdvisorChallengesView(APIView):
    """The advisor's challenge list for one student, and the create door."""

    permission_classes = [IsAuthenticated, IsAdvisorUser]

    @extend_schema(
        tags=['advisory'],
        summary='چالش‌های یک دانش‌آموز',
        description=(
            '`pk` شناسه‌ی همکاری است؛ همکاریِ ناموجود یا متعلق به مشاورِ دیگر ۴۰۴. '
            'لیست نزولی بر تاریخ شروع است و روزهای هر چالش همراهش می‌آید.'
        ),
        responses={
            200: ChallengeItemSerializer(many=True),
            404: OpenApiResponse(description='همکاری پیدا نشد'),
        },
    )
    def get(self, request, pk: int):
        engagement, error = _resolve_engagement_or_404(request, pk)
        if error is not None:
            return error
        rows = challenge_service.list_challenges(engagement)
        return Response(ChallengeItemSerializer(rows, many=True).data)

    @extend_schema(
        tags=['advisory'],
        summary='ساخت چالش هفت‌روزه',
        description=(
            '`startDate` الزامی است؛ `endDate` همیشه سرور محاسبه می‌شود '
            '(ششمین روز پس از شروع) و مقدار ارسالی نادیده گرفته می‌شود. با '
            'رسیدن به سقف ۳ چالش فعال، ۴۰۰ با پیام فارسی می‌دهد.'
        ),
        request=ChallengeCreateSerializer,
        responses={
            201: ChallengeItemSerializer,
            400: OpenApiResponse(description='اعتبارسنجی چالش'),
            404: OpenApiResponse(description='همکاری پیدا نشد'),
        },
    )
    def post(self, request, pk: int):
        engagement, error = _resolve_engagement_or_404(request, pk)
        if error is not None:
            return error

        serializer = ChallengeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            challenge = challenge_service.create_challenge(
                engagement, serializer.validated_data,
            )
        except challenge_service.ChallengeError as exc:
            # The base class on purpose: any rule the door adds later must fail
            # as an actionable client error, never as a 500.
            return _challenge_error_response(exc)
        return Response(
            ChallengeItemSerializer(challenge).data,
            status=status.HTTP_201_CREATED,
        )


class AdvisorChallengeDetailView(APIView):
    """One challenge of one student — read, partial edit, delete.

    PATCH updates metadata fields and/or status; the status machine (only
    ACTIVE → DONE/CANCELLED) is enforced inside ``services.challenges`` and
    surfaces here as a 409.
    """

    permission_classes = [IsAuthenticated, IsAdvisorUser]

    @extend_schema(
        tags=['advisory'],
        summary='خواندن یک چالش',
        description=('چالشی که به این همکاری تعلق ندارد ۴۰۴ است.'),
        responses={
            200: ChallengeItemSerializer,
            404: OpenApiResponse(description='همکاری یا چالش پیدا نشد'),
        },
    )
    def get(self, request, pk: int, challenge_id: int):
        engagement, error = _resolve_engagement_or_404(request, pk)
        if error is not None:
            return error
        challenge = challenge_service.get_challenge(engagement, challenge_id)
        if challenge is None:
            return Response(
                {'detail': 'چالش پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND,
            )
        return Response(ChallengeItemSerializer(challenge).data)

    @extend_schema(
        tags=['advisory'],
        summary='ویرایش جزئی یک چالش (متادیتا و/یا وضعیت)',
        description=(
            'فقط کلیدهای ارسالی تغییر می‌کنند. تغییر وضعیت فقط در جهت '
            'فعال → پایان‌یافته/لغوشده مجاز است؛ هر حرکت دیگری ۴۰۹ با پیام '
            'فارسی می‌دهد. با تغییر `startDate`، `endDate` دوباره توسط سرور '
            'محاسبه می‌شود.'
        ),
        request=ChallengePatchSerializer,
        responses={
            200: ChallengeItemSerializer,
            400: OpenApiResponse(description='اعتبارسنجی چالش'),
            404: OpenApiResponse(description='همکاری یا چالش پیدا نشد'),
            409: OpenApiResponse(description='تغییر وضعیت برگشت‌پذیر نیست'),
        },
    )
    def patch(self, request, pk: int, challenge_id: int):
        engagement, error = _resolve_engagement_or_404(request, pk)
        if error is not None:
            return error
        challenge = challenge_service.get_challenge(engagement, challenge_id)
        if challenge is None:
            return Response(
                {'detail': 'چالش پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ChallengePatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            challenge = challenge_service.update_challenge(
                challenge, serializer.validated_data,
            )
        except challenge_service.ChallengeError as exc:
            return _challenge_error_response(exc)
        return Response(ChallengeItemSerializer(challenge).data)

    @extend_schema(
        tags=['advisory'],
        summary='حذف یک چالش',
        description=('حذف قطعی چالش به‌همراه روزهایش؛ فقط برای همکاریِ خودِ مشاور.'),
        responses={
            204: OpenApiResponse(description='حذف شد'),
            404: OpenApiResponse(description='همکاری یا چالش پیدا نشد'),
        },
    )
    def delete(self, request, pk: int, challenge_id: int):
        engagement, error = _resolve_engagement_or_404(request, pk)
        if error is not None:
            return error
        challenge = challenge_service.get_challenge(engagement, challenge_id)
        if challenge is None:
            return Response(
                {'detail': 'چالش پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND,
            )
        challenge_service.delete_challenge(challenge)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdvisorChallengeDaysView(APIView):
    """The advisor's wholesale replace of one challenge's seven day rows."""

    permission_classes = [IsAuthenticated, IsAdvisorUser]

    @extend_schema(
        tags=['advisory'],
        summary='ثبت روزهای یک چالش (جایگزینی کامل)',
        description=(
            'بدنه `{"days": [{dayNumber, goal, summary}]}` است و کلِ روزها از نو '
            'ساخته می‌شوند — ردیف نیامده یعنی حذف‌شده. شمارۀ روز بین ۱ تا ۷ است؛ '
            'نوشتن روز روی چالش پایان‌یافته یا لغوشده ۴۰۹ می‌دهد.'
        ),
        request=ChallengeDaysWriteSerializer,
        responses={
            200: ChallengeItemSerializer,
            400: OpenApiResponse(description='اعتبارسنجی روزها'),
            404: OpenApiResponse(description='همکاری یا چالش پیدا نشد'),
            409: OpenApiResponse(description='چالش پایان یافته است'),
        },
    )
    def put(self, request, pk: int, challenge_id: int):
        engagement, error = _resolve_engagement_or_404(request, pk)
        if error is not None:
            return error
        challenge = challenge_service.get_challenge(engagement, challenge_id)
        if challenge is None:
            return Response(
                {'detail': 'چالش پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ChallengeDaysWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            challenge = challenge_service.replace_days(
                challenge, serializer.validated_data['days'],
            )
        except challenge_service.ChallengeError as exc:
            return _challenge_error_response(exc)
        return Response(ChallengeItemSerializer(challenge).data)


class StudentChallengesView(APIView):
    """The student's read-only mirror of their advisor's challenges."""

    permission_classes = [IsAuthenticated, IsStudentRole]

    @extend_schema(
        tags=['advisory'],
        summary='چالش‌های خودِ دانش‌آموز',
        description=(
            'بدون مشاور فعال `200 {"active": false, "challenges": []}` — خطا نیست. '
            'با مشاور فعال، همهٔ چالش‌های مشاورِ خودش؛ فقط خواندنی.'
        ),
        responses={
            200: OpenApiResponse(description='{active, challenges}'),
        },
    )
    def get(self, request):
        engagement = student_active_engagement(request.user)
        if engagement is None:
            return Response({'active': False, 'challenges': []})
        rows = challenge_service.list_challenges(engagement)
        return Response({
            'active': True,
            'challenges': ChallengeItemSerializer(rows, many=True).data,
        })


class StudentChallengeDaysView(APIView):
    """The student's daily fill-in of their active challenge's day rows.

    The student may set only ``goal`` and ``summary`` per day — anything else
    in a row is a pinned 400 — and only while the challenge is still ACTIVE
    (otherwise the same 409 the advisor would hit).
    """

    permission_classes = [IsAuthenticated, IsStudentRole]

    @extend_schema(
        tags=['advisory'],
        summary='ثبت هدف و خلاصۀ روزهای چالش خودم',
        description=(
            'بدنه `{"days": [{dayNumber, goal, summary}]}` است؛ فقط «هدف» و '
            '«خلاصه» قابل ثبت‌اند و هر کلید دیگری در ردیف ۴۰۰ می‌دهد. نوشتن روی '
            'چالش پایان‌یافته یا لغوشده ۴۰۹ است.'
        ),
        request=ChallengeDaysWriteSerializer,
        responses={
            200: ChallengeItemSerializer,
            400: OpenApiResponse(description='اعتبارسنجی روزها'),
            404: OpenApiResponse(description='چالش پیدا نشد'),
            409: OpenApiResponse(description='چالش پایان یافته است'),
        },
    )
    def put(self, request, challenge_id: int):
        engagement = student_active_engagement(request.user)
        if engagement is None:
            return Response(
                {'detail': 'ابتدا مشاور خود را تأیید کنید.'},
                status=status.HTTP_409_CONFLICT,
            )
        challenge = challenge_service.get_challenge(engagement, challenge_id)
        if challenge is None:
            return Response(
                {'detail': 'چالش پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ChallengeDaysWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            challenge = challenge_service.replace_days(
                challenge,
                serializer.validated_data['days'],
                student_mode=True,
            )
        except challenge_service.ChallengeError as exc:
            return _challenge_error_response(exc)
        return Response(ChallengeItemSerializer(challenge).data)
