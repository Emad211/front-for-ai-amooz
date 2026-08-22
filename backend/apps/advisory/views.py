"""Advisory API views.

Every view here is a thin shell: it checks the role, hands off to
``services/scope.py`` (reads) or ``services/invites.py`` (writes), and shapes the
response. None of them builds a queryset, and none of them may even *name* the
engagement model — ``test_import_boundaries`` asserts that, because a direct
``filter(advisor=request.user)`` looks correct while silently skipping the
organization-membership gate that ``scope.visible_engagements`` applies.

The role split is visible in the URLs on purpose: ``/advisory/…`` is the advisor's
side, ``/advisory/me/…`` is the student's. A reviewer can tell which permission
class belongs on a route without reading the body.
"""

from __future__ import annotations

from django.db.models import F, Q
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdvisorUser, IsStudentRole
from apps.core.throttling import SafeScopedRateThrottle

from .models import Subject
from .serializers import (
    AdvisorPendingInviteSerializer,
    AdvisorStudentSerializer,
    AdvisoryInviteCreateSerializer,
    EngagementSubjectsWriteSerializer,
    StudentEngagementSerializer,
    StudentInviteSerializer,
    StudentSubjectSerializer,
    SubjectSerializer,
)
from .services import invites as invite_service
from .services import student_subjects as subject_service
from .services.scope import (
    advisor_engagement,
    advisor_organization_ids,
    advisor_pending_invites,
    advisor_students,
    curriculum_subjects,
    student_active_engagement,
    student_claimable_invites,
    # The scope *read* aliased away from the service module of the same name
    # imported just above; both are needed here and only one can keep the bare name.
    student_subjects as engagement_subjects,
)


@extend_schema(
    tags=['advisory'],
    summary='فهرست درس‌های قابل انتخاب برای مشاور',
    description=(
        'درس‌های سراسری به‌علاوه‌ی درس‌های خصوصیِ سازمان‌هایی که کاربر در آن‌ها '
        'مشاورِ فعال است. صفحه‌بندی ندارد؛ خروجی یک آرایه‌ی کامل است.'
    ),
    responses={200: SubjectSerializer(many=True)},
)
class SubjectListView(ListAPIView):
    """``GET /api/advisory/subjects/`` — the advisor's subject picker.

    Pagination is switched off deliberately. DRF applies ``PageNumberPagination``
    globally at ``PAGE_SIZE`` (50 by default), and a picker that silently drops
    the 51st subject is a data-entry bug that nobody notices until an advisor
    cannot find a subject that exists. The catalog is small and admin-curated.
    """

    serializer_class = SubjectSerializer
    permission_classes = [IsAuthenticated, IsAdvisorUser]
    pagination_class = None

    def get_queryset(self):
        org_ids = advisor_organization_ids(self.request.user)
        return (
            Subject.objects.filter(is_active=True)
            .filter(Q(organization__isnull=True) | Q(organization_id__in=org_ids))
            .select_related('organization')
            # Globals first, then each organization's own additions. PostgreSQL
            # sorts NULLs last in ASC, so nulls_first has to be explicit.
            .order_by(F('organization_id').asc(nulls_first=True), 'name')
        )


# ── advisor side ──────────────────────────────────────────────────────────────

class AdvisorStudentListView(APIView):
    """``GET /api/advisory/students/`` — roster and outbox in one call.

    Both halves ship together because they are one screen: the advisor's page
    shows accepted students above still-unanswered invites, and splitting them
    into two requests buys nothing but a second loading state and a window where
    an invite that was just accepted appears in both lists.

    Neither list is paginated. The roster is a personal caseload and the outbox is
    hard-capped at ``ADVISOR_OPEN_PENDING_CAP``, so both are bounded by design —
    and a silently truncated roster is a much worse failure than a long response.
    """

    permission_classes = [IsAuthenticated, IsAdvisorUser]

    @extend_schema(
        tags=['advisory'],
        summary='دانش‌آموزان مشاور و دعوت‌نامه‌های بی‌پاسخ',
        description=(
            'دو فهرست: همکاری‌های فعال (`students`) و دعوت‌نامه‌های ارسال‌شده‌ی '
            'بی‌پاسخ (`pendingInvites`). دعوت‌نامه‌ها هیچ اطلاعاتی از هویت '
            'دعوت‌شده ندارند — فقط شماره‌ی ماسک‌شده‌ای که خود مشاور وارد کرده است.'
        ),
        responses={200: OpenApiResponse(description='students[] و pendingInvites[]')},
    )
    def get(self, request):
        return Response({
            'students': AdvisorStudentSerializer(
                advisor_students(request.user), many=True,
            ).data,
            'pendingInvites': AdvisorPendingInviteSerializer(
                advisor_pending_invites(request.user), many=True,
            ).data,
        })


class AdvisoryInviteCreateView(APIView):
    """``POST /api/advisory/invites/`` — invite a student by phone number.

    The response is ``202 {"status": "sent"}`` for **every** phone number that is
    merely well-formed: one that belongs to a student, one that belongs to nobody,
    one on cooldown, one blocked by a past rejection. That uniformity is the point
    (B2) — anything else turns an authenticated advisor account into a
    phone-number→identity lookup service for the whole platform.

    Uniformity of *timing* matters as much as uniformity of body, so this view
    performs no phone-dependent work at all. It validates the shape of the string,
    charges the quota, fires exactly one task, and answers. Everything that
    depends on who owns the number happens in the worker.
    """

    permission_classes = [IsAuthenticated, IsAdvisorUser]
    throttle_classes = [SafeScopedRateThrottle]
    # Without its own scope this inherits 'user' at 300/minute — an authenticated
    # SMS trigger at eighteen thousand messages an hour. See B3.
    throttle_scope = 'advisory_invite'

    @extend_schema(
        tags=['advisory'],
        summary='ارسال دعوت‌نامه‌ی همکاری به دانش‌آموز',
        description=(
            'پاسخ برای هر شماره‌ی معتبری یکسان است (`202`) — وجود یا نبودِ حساب '
            'با آن شماره لو نمی‌رود. `400` فقط برای شماره‌ی بدشکل است. '
            '`429` سقف مشاور، `503` بریکر پلتفرم.'
        ),
        request=AdvisoryInviteCreateSerializer,
        responses={
            202: OpenApiResponse(description='{"status": "sent"}'),
            400: OpenApiResponse(description='شماره‌ی موبایل بدشکل'),
            429: OpenApiResponse(description='سقف روزانه یا سقف دعوت‌های بی‌پاسخ'),
            503: OpenApiResponse(description='بریکر پلتفرم فعال است'),
        },
    )
    def post(self, request):
        serializer = AdvisoryInviteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data['phone']

        try:
            invite_service.charge_invite_quota(
                request.user,
                open_pending_count=advisor_pending_invites(request.user).count(),
            )
        except invite_service.InviteQuotaExceeded as exc:
            code = (
                status.HTTP_503_SERVICE_UNAVAILABLE
                if exc.kind == 'platform'
                else status.HTTP_429_TOO_MANY_REQUESTS
            )
            return Response({'detail': exc.message}, status=code)

        invite_service.enqueue_invite(advisor_id=request.user.pk, phone=phone)
        return Response({'status': 'sent'}, status=status.HTTP_202_ACCEPTED)


class AdvisorEngagementSubjectsView(APIView):
    """``GET``/``PUT`` ``/api/advisory/students/<pk>/subjects/`` — the per-student picker.

    ``<pk>`` is the **engagement** id (``AdvisorStudent.id``), the same tenancy-keyed
    address every advisor route uses from step 5 on — never a user id.
    ``scope.advisor_engagement`` resolves it out of the advisor's visible set, so a
    foreign or unknown id is a **404, not a 403**: a 403 would confirm the engagement
    exists and leak that some advisor works with that student.

    The subject set is sent whole on ``PUT`` (a set-replace, not an append), and the
    service — which alone holds the advisor's org scope — decides assignability. This
    view enforces only the two things it can see without a query: that the engagement
    is the advisor's, and that it is still ``ACTIVE`` (a picker for an ended engagement
    would write rows nobody can ever read).
    """

    permission_classes = [IsAuthenticated, IsAdvisorUser]
    pagination_class = None

    def _student_axes(self, engagement):
        """The student's own ``(grade, gradeLabel, major, majorLabel)``.

        Read defensively and exactly as ``accounts`` reads these fields: a student
        may have no ``StudentProfile`` row yet, and either field on it may be blank.
        These values pre-fill the picker's header and are what the server derived the
        candidate ``subjects`` from — they gate nothing here (the service re-derives),
        so an absent profile is a quiet all-``None``. The ``hasattr`` guard is safe
        because Django makes a reverse-one-to-one miss raise ``AttributeError``.
        """
        student = engagement.student
        if not hasattr(student, 'studentprofile'):
            return None, None, None, None
        profile = student.studentprofile
        grade = getattr(profile, 'grade', None) or None
        major = getattr(profile, 'major', None) or None
        return (
            grade,
            profile.get_grade_display() if grade else None,
            major,
            profile.get_major_display() if major else None,
        )

    @extend_schema(
        tags=['advisory'],
        summary='درس‌های قابل‌انتخاب و انتخاب‌شده‌ی یک دانش‌آموز (خواندن)',
        description=(
            '`pk` شناسه‌ی همکاری است، نه شناسه‌ی کاربر؛ برای همکاریِ ناموجود یا '
            'متعلق به مشاورِ دیگر ۴۰۴. `subjects` برنامه‌ی درسیِ مشتق‌شده از '
            'پایه و رشته‌ی خودِ دانش‌آموز است (کاندیداهای پیکر)، و '
            '`selectedSubjectIds` زیرمجموعه‌ای است که مشاور فوکوس کرده. '
            '`studentGrade`/`studentMajor` فقط برای نمایش در سرصفحه‌اند.'
        ),
        responses={
            200: OpenApiResponse(
                description=(
                    '{studentGrade, studentGradeLabel, studentMajor, '
                    'studentMajorLabel, subjects[], selectedSubjectIds[]}'
                ),
            ),
            404: OpenApiResponse(description='همکاری پیدا نشد'),
        },
    )
    def get(self, request, pk: int):
        engagement = advisor_engagement(request.user, pk)
        if engagement is None:
            return Response({'detail': 'همکاری پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        grade, grade_label, major, major_label = self._student_axes(engagement)
        # The candidate set is the student's derived curriculum — the same queryset
        # the write door validates against — so the picker and the validator can
        # never disagree about what is assignable.
        candidates = curriculum_subjects(engagement.student).select_related('organization')
        selected = list(
            engagement_subjects(engagement).values_list('subject_id', flat=True)
        )
        return Response({
            'studentGrade': grade,
            'studentGradeLabel': grade_label,
            'studentMajor': major,
            'studentMajorLabel': major_label,
            'subjects': SubjectSerializer(candidates, many=True).data,
            'selectedSubjectIds': selected,
        })

    @extend_schema(
        tags=['advisory'],
        summary='ثبت درس‌های یک دانش‌آموز (جایگزینیِ کامل)',
        description=(
            '`subjectIds` مجموعه‌ی کاملِ درس‌هاست؛ هرچه نیاید غیرفعال می‌شود '
            '(حذف نمی‌شود). فقط برای همکاریِ فعال؛ روی همکاریِ در انتظار یا '
            'پایان‌یافته ۴۰۹. درسِ خارج از فهرستِ مجازِ مشاور ۴۰۰. لیستِ خالی '
            'یعنی «انتخاب را پاک کن».'
        ),
        request=EngagementSubjectsWriteSerializer,
        responses={
            200: StudentSubjectSerializer(many=True),
            400: OpenApiResponse(description='درسِ خارج از فهرستِ مجاز'),
            404: OpenApiResponse(description='همکاری پیدا نشد'),
            409: OpenApiResponse(description='همکاری فعال نیست'),
        },
    )
    def put(self, request, pk: int):
        engagement = advisor_engagement(request.user, pk)
        if engagement is None:
            return Response({'detail': 'همکاری پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND)
        # Not the model's ``Status.ACTIVE`` by name — this view is forbidden from
        # naming the engagement model (import-boundary guard); the nested enum reached
        # through the instance is the same value without the import.
        if engagement.status != engagement.Status.ACTIVE:
            return Response(
                {'detail': 'انتخاب درس فقط برای همکاریِ فعال ممکن است.'},
                status=status.HTTP_409_CONFLICT,
            )
        serializer = EngagementSubjectsWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            rows = subject_service.set_engagement_subjects(
                engagement,
                serializer.validated_data['subjectIds'],
                advisor=request.user,
            )
        except subject_service.SubjectNotAssignable as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(StudentSubjectSerializer(rows, many=True).data)


# ── student side ──────────────────────────────────────────────────────────────

class StudentEngagementView(APIView):
    """``GET /api/advisory/me/engagement/`` — "do I have an advisor?"

    Drives two pieces of UI from one call: the accept banner (``invites``) and the
    advisory section of the dashboard (``active``). Both are ``null``/empty for the
    overwhelming majority of students, which is deliberate — the *existence of an
    active engagement* is what gates the advisory UI, since this repo has no
    feature-flag mechanism to gate it with.
    """

    permission_classes = [IsAuthenticated, IsStudentRole]

    @extend_schema(
        tags=['advisory'],
        summary='مشاور فعال و دعوت‌نامه‌های قابل پذیرش دانش‌آموز',
        description=(
            'دعوت‌نامه‌های منقضی‌شده در `invites` نمی‌آیند؛ همان قواعدی که '
            'پذیرش/رد را ۴۰۴ می‌کند این فهرست را هم می‌سازد.'
        ),
        responses={200: OpenApiResponse(description='active (یا null) و invites[]')},
    )
    def get(self, request):
        active = student_active_engagement(request.user)
        return Response({
            'active': StudentEngagementSerializer(active).data if active else None,
            'invites': StudentInviteSerializer(
                student_claimable_invites(request.user), many=True,
            ).data,
        })


class StudentInviteAcceptView(APIView):
    """``POST /api/advisory/me/invites/<pk>/accept/`` — grant the advisor access.

    This is the moment a stranger gains read access to a teenager's study log, so
    the authority to perform it is an authenticated session belonging to exactly
    the invited student, re-verified server-side against the phone the invite was
    addressed to. No code is sent over SMS and none is accepted here: B1 forbids
    handing a credential to a phone number, and the accept step is the one action
    that must never become un-completable because an SMS did not arrive.
    """

    permission_classes = [IsAuthenticated, IsStudentRole]

    @extend_schema(
        tags=['advisory'],
        summary='پذیرش دعوت‌نامه‌ی مشاور',
        description=(
            'شروع همکاری از **امروز** ثبت می‌شود، نه از تاریخ دعوت — مشاور به '
            'گذشته‌ی دانش‌آموز دسترسی پیدا نمی‌کند. '
            '`404` برای دعوت‌نامه‌ی ناموجود/منقضی/متعلق به دیگری، '
            '`409` اگر از قبل مشاور فعال داشته باشد یا همین دعوت پذیرفته شده باشد.'
        ),
        request=None,
        responses={
            200: OpenApiResponse(description='همکاری فعال شد'),
            404: OpenApiResponse(description='دعوت‌نامه پیدا نشد'),
            409: OpenApiResponse(description='وضعیت اجازه‌ی پذیرش نمی‌دهد'),
        },
    )
    def post(self, request, pk: int):
        try:
            engagement = invite_service.accept_invite(request.user, pk)
        except invite_service.InviteNotFound as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except invite_service.InviteConflict as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(StudentEngagementSerializer(engagement).data)


class StudentInviteRejectView(APIView):
    """``POST /api/advisory/me/invites/<pk>/reject/`` — decline, permanently.

    Terminal by design: the same advisor cannot re-invite this student for
    ``REJECT_BLOCK_DAYS``. A rejection that could be retried tomorrow is a rate
    limit, not an answer, and would make "no" cost the student more than the
    advisor.
    """

    permission_classes = [IsAuthenticated, IsStudentRole]

    @extend_schema(
        tags=['advisory'],
        summary='رد دعوت‌نامه‌ی مشاور',
        description='رد نهایی است؛ همان مشاور تا ۳۰ روز نمی‌تواند دوباره دعوت کند.',
        request=None,
        responses={
            200: OpenApiResponse(description='{"status": "rejected"}'),
            404: OpenApiResponse(description='دعوت‌نامه پیدا نشد'),
            409: OpenApiResponse(description='وضعیت اجازه‌ی رد نمی‌دهد'),
        },
    )
    def post(self, request, pk: int):
        try:
            invite_service.reject_invite(request.user, pk)
        except invite_service.InviteNotFound as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except invite_service.InviteConflict as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response({'status': 'rejected'})


class StudentSubjectsView(APIView):
    """``GET /api/advisory/me/subjects/`` — "what did my advisor pick for me?"

    Quiet like ``StudentEngagementView``: a student with no active engagement gets
    ``200 {"active": false, "subjects": []}``, never a 404. The advisory UI is gated
    on ``active`` being true and the overwhelming majority of students never have an
    advisor, so an error status for the ordinary case would be the wrong signal.
    ``advisorName`` is present only when active, for the same reason the accept banner
    names the advisor — the student should see *who* chose these subjects.
    """

    permission_classes = [IsAuthenticated, IsStudentRole]

    @extend_schema(
        tags=['advisory'],
        summary='درس‌هایی که مشاور برای دانش‌آموز انتخاب کرده',
        description=(
            'اگر مشاور فعالی نباشد، `200` با `{"active": false, "subjects": []}` — '
            'خطا نیست. درس‌ها همان مجموعه‌ای است که مشاور در پیکر ثبت کرده.'
        ),
        responses={200: OpenApiResponse(description='{active, advisorName?, subjects[]}')},
    )
    def get(self, request):
        engagement = student_active_engagement(request.user)
        if engagement is None:
            return Response({'active': False, 'subjects': []})
        # Reuse the engagement serializer for the name so the "first+last or username"
        # display rule lives in exactly one place; ``advisor`` is already
        # select_related on this queryset, so this adds no query.
        advisor_name = StudentEngagementSerializer(engagement).data['advisorName']
        return Response({
            'active': True,
            'advisorName': advisor_name,
            'subjects': StudentSubjectSerializer(
                engagement_subjects(engagement), many=True,
            ).data,
        })
