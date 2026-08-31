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
from django.utils import timezone
from django.utils.dateparse import parse_date
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
    AdvisorFolderSerializer,
    AdvisorPendingInviteSerializer,
    AdvisorStudentSerializer,
    AdvisoryInviteCreateSerializer,
    DailyLogSerializer,
    DailyLogWriteSerializer,
    EngagementSubjectsWriteSerializer,
    FeedDaySerializer,
    StudentEngagementSerializer,
    StudentInviteSerializer,
    StudentSubjectSerializer,
    StudyPlanDraftWriteSerializer,
    StudyPlanOutSerializer,
    SubjectSerializer,
    _display_name,
)
from .services import daily_logs as log_service
from .services import folders as folder_service
from .services import invites as invite_service
from .services import student_subjects as subject_service
from .services import study_plans as plan_service
from .services.scope import (
    advisor_engagement,
    advisor_feed_logs,
    advisor_organization_ids,
    advisor_pending_invites,
    advisor_plans,
    advisor_students,
    curriculum_subjects,
    feed_date_range,
    log_date_window,
    student_active_engagement,
    student_claimable_invites,
    student_day_log,
    student_published_plans,
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
            'دعوت‌شده ندارند — فقط شماره‌ی ماسک‌شده‌ای که خود مشاور وارد کرده است. '
            'ریسمان گام ۱: `?q=` (icontains روی نام/نام خانوادگی/نام کاربری/تلفن) '
            'و `?folder=<id>` رستر را محدود می‌کنند؛ پاسخ `folders` (پوشه‌های خود '
            'مشاور) و `folderId` هر دانش‌آموز را هم دارد. پوشهٔ غریبه/ناموجود ۴۰۴.'
        ),
        parameters=[
            OpenApiParameter(
                name='q', description='جستجو در نام، نام خانوادگی، نام کاربری و تلفن.',
                required=False, type=str,
            ),
            OpenApiParameter(
                name='folder', description='شناسهٔ پوشهٔ خود مشاور.',
                required=False, type=int,
            ),
        ],
        responses={200: OpenApiResponse(description='students[] و pendingInvites[] و folders[]')},
    )
    def get(self, request):
        # Risman step 1: ?folder=<id> must resolve inside the advisor's OWN
        # folders before any filtering — a foreign or unknown id is a 404,
        # never a 403, so one advisor cannot probe another's folder ids.
        raw_folder = request.query_params.get('folder') or ''
        folder = None
        if raw_folder:
            try:
                folder = folder_service.get_folder(request.user, int(raw_folder))
            except ValueError:
                folder = None
            if folder is None:
                return Response(
                    {'detail': 'پوشه پیدا نشد.'},
                    status=status.HTTP_404_NOT_FOUND,
                )

        roster = folder_service.filter_roster(
            advisor_students(request.user),
            q=request.query_params.get('q'),
            folder=folder,
        )

        return Response({
            'students': AdvisorStudentSerializer(roster, many=True).data,
            'pendingInvites': AdvisorPendingInviteSerializer(
                advisor_pending_invites(request.user), many=True,
            ).data,
            'folders': AdvisorFolderSerializer(
                folder_service.list_folders(request.user), many=True,
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
        selected = []
        selected_sources = {}
        # Restart step 3: the picker prefills each row's source Select from what
        # is already stored, keyed by catalog subject id as strings (JSON keys).
        for row in engagement_subjects(engagement):
            selected.append(row.subject_id)
            if row.source:
                selected_sources[str(row.subject_id)] = row.source
        return Response({
            'studentGrade': grade,
            'studentGradeLabel': grade_label,
            'studentMajor': major,
            'studentMajorLabel': major_label,
            'subjects': SubjectSerializer(candidates, many=True).data,
            'selectedSubjectIds': selected,
            'selectedSources': selected_sources,
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

        sources = None
        raw_sources = (
            request.data.get('sources')
            if isinstance(request.data, dict)
            else None
        )
        if raw_sources is not None:
            if not isinstance(raw_sources, dict):
                return Response(
                    {'detail': 'شناسۀ درس در sources نامعتبر است.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # JSON object keys are strings; coerce to the ints the service speaks,
            # failing closed on anything non-numeric rather than guessing.
            sources = {}
            for key, code in raw_sources.items():
                try:
                    sources[int(key)] = code
                except (TypeError, ValueError):
                    return Response(
                        {'detail': 'شناسۀ درس در sources نامعتبر است.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        try:
            rows = subject_service.set_engagement_subjects(
                engagement,
                serializer.validated_data['subjectIds'],
                advisor=request.user,
                sources=sources,
            )
        except subject_service.SubjectSelectionError as exc:
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


# ── S5: the daily study log ──────────────────────────────────────────────────

def _study_log_payload(engagement, log_date) -> dict:
    """Everything the study-log form needs for one date, in one shape.

    GET and PUT both answer with this. That is not tidiness: the PUT response is what
    the client re-renders from after a save, so if the two shapes could drift, a
    successful save would be able to paint a screen that a refresh then contradicts.

    ``minDate``/``maxDate`` come from ``scope.log_date_window`` — the C3 bound — and
    are published so the date stepper can grey itself out instead of discovering the
    limit by collecting a 400.

    ``subjects`` is the *currently selected* set (the rows the student may write
    against today), while ``log.items`` is what was actually recorded. Those two lists
    can legitimately disagree: an item whose subject the advisor has since dropped
    keeps its minutes and comes back with ``isSelected: false``. The form renders the
    union — selected rows editable, unselected-but-recorded rows read-only.
    """
    earliest, latest = log_date_window(engagement)
    log = student_day_log(engagement, log_date)
    return {
        'active': True,
        # Reuse of the engagement serializer, as in ``StudentSubjectsView``: the
        # "first+last or username" display rule stays in one place, and ``advisor`` is
        # already select_related, so this costs no query.
        'advisorName': StudentEngagementSerializer(engagement).data['advisorName'],
        'date': log_date,
        'minDate': earliest,
        'maxDate': latest,
        'subjects': StudentSubjectSerializer(
            engagement_subjects(engagement), many=True,
        ).data,
        'log': DailyLogSerializer(log).data if log is not None else None,
    }


class StudentStudyLogView(APIView):
    """``GET|PUT /api/advisory/me/study-log/`` — the student writes their own day.

    The whole of D3 in one class: this is the *only* endpoint that writes a log, it
    lives under ``/me/``, and it is bolted to ``IsStudentRole``. An advisor cannot
    edit a student's report because there is nowhere for them to do it — and, for the
    day that stops being true, ``services.daily_logs`` re-checks ownership against
    the engagement anyway.

    ``PUT`` and not ``POST``/``PATCH``: the body is the complete day and the operation
    is idempotent (send it twice, get the same day). A ``POST`` would imply a second
    submit creates a second row, and the unique ``(engagement, log_date)`` constraint
    would turn that misreading into a 500.

    Reads are quiet, writes are not. ``GET`` with no active advisor is a
    ``200 {"active": false, …}`` — the ordinary state for almost every student on the
    platform, and not an error. ``PUT`` in that state is a ``409``: there is no
    engagement for the row to hang off, so the request cannot be honoured and saying
    so plainly beats inventing a home for the data.
    """

    permission_classes = [IsAuthenticated, IsStudentRole]

    @staticmethod
    def _requested_date(request):
        """``?date=YYYY-MM-DD`` → a date, or ``None`` if it was sent but unparseable.

        An **absent** parameter is the normal case and means today, so it returns
        today's date; ``None`` therefore means exactly one thing — the client sent
        something that is not a date — and the caller turns that into a 400. Uses
        ``timezone.localdate()`` for the same reason ``log_date_window`` does: «امروز»
        must be the student's today, not the server's UTC one.

        ``ValueError`` is caught because ``parse_date`` has *two* failure modes and
        only one of them is a return value: it answers ``None`` for a string that is
        not date-shaped (``'yesterday'``), but **raises** for one that is shaped right
        and impossible (``'2026-13-45'``). Letting that escape would turn a typo into
        a 500 on a read.
        """
        raw = request.query_params.get('date')
        if not raw:
            return timezone.localdate()
        try:
            return parse_date(raw)
        except ValueError:
            return None

    @extend_schema(
        tags=['advisory'],
        summary='گزارش روزانه‌ی مطالعه‌ی دانش‌آموز (یک روز)',
        description=(
            'اگر مشاور فعالی نباشد، `200` با `{"active": false}` — خطا نیست. '
            '`date` اختیاری است و پیش‌فرضش «امروز» است؛ باید بین `minDate` '
            '(روزِ شروع همکاری) و `maxDate` (امروز) باشد وگرنه `400`. '
            '`log` برای روزی که ثبت نشده `null` است.'
        ),
        parameters=[
            OpenApiParameter(
                name='date',
                description='روز مورد نظر به میلادی (`YYYY-MM-DD`). پیش‌فرض: امروز.',
                required=False,
                type=str,
            ),
        ],
        responses={
            200: OpenApiResponse(
                description='{active, advisorName?, date, minDate, maxDate, subjects[], log}',
            ),
            400: OpenApiResponse(description='تاریخ بدشکل یا بیرون از بازه‌ی مجاز'),
        },
    )
    def get(self, request):
        log_date = self._requested_date(request)
        if log_date is None:
            return Response(
                {'detail': 'تاریخ باید به شکل YYYY-MM-DD باشد.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        engagement = student_active_engagement(request.user)
        if engagement is None:
            # Quiet, and with the full key set so the client needs no special case —
            # only ``active`` decides whether the study-log button renders at all.
            # ``minDate``/``maxDate`` are null rather than today: with no engagement
            # there is no window, and "you may log today" would simply be false.
            return Response({
                'active': False,
                'date': log_date,
                'minDate': None,
                'maxDate': None,
                'subjects': [],
                'log': None,
            })

        earliest, latest = log_date_window(engagement)
        if not (earliest <= log_date <= latest):
            # A 400 on a *read* looks strict, but the alternative is worse: happily
            # answering ``log: null`` for a date the student can never write would
            # invite a form that submits and then fails.
            return Response(
                {'detail': 'این تاریخ بیرون از بازه‌ی مجاز است.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(_study_log_payload(engagement, log_date))

    @extend_schema(
        tags=['advisory'],
        summary='ثبت/به‌روزرسانی گزارش یک روز',
        description=(
            'بدنه، **کلِ** آن روز است: هر درسی که در `items` نباشد از آن روز پاک '
            'می‌شود و `mood`/`note` نیامده یعنی «خالی». `minutes` صفر یعنی «نخواندم» '
            'و ذخیره نمی‌شود. '
            'چهار فیلد اختیاری `dayGoal`/`motivationNote`/`testsTaken`/`testPercent` '
            'نیز قابل ثبت‌اند؛ نیامدنِ آن‌ها یعنی «بدون تغییر» و آمدنشان جایگزین کامل '
            '(حتی با خالی/صفر/null). '
            '`409` اگر مشاور فعال نداشته باشد، '
            '`400` برای تاریخ بیرون از بازه، درسِ بیرون از فهرست، یا مجموع بیش از '
            'یک شبانه‌روز، `403` اگر گزارش متعلق به دانش‌آموز دیگری باشد.'
        ),
        request=DailyLogWriteSerializer,
        responses={
            200: OpenApiResponse(description='همان ساختار GET، با روزِ ذخیره‌شده'),
            400: OpenApiResponse(description='بدنه یا تاریخ یا درس نامعتبر'),
            403: OpenApiResponse(description='گزارش دانش‌آموز دیگری'),
            409: OpenApiResponse(description='مشاور فعالی ندارید'),
        },
    )
    def put(self, request):
        engagement = student_active_engagement(request.user)
        if engagement is None:
            return Response(
                {'detail': 'برای ثبت گزارش روزانه باید مشاور فعال داشته باشید.'},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = DailyLogWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Restart plan step 1: forward ONLY the enrichment keys the client sent
        # — ``validated_data`` carries a key just when it was present on the
        # wire, and save_day's ``_UNSET`` default turns absence into «untouched»
        # so legacy payloads cannot wipe columns they never knew about.
        enrichment = {
            key: data[key]
            for key in ('day_goal', 'motivation_note', 'tests_taken', 'test_percent')
            if key in data
        }

        try:
            log = log_service.save_day(
                engagement,
                data['log_date'],
                mood=data.get('mood'),
                note=data.get('note', ''),
                items=data['items'],
                student=request.user,
                **enrichment,
            )
        except log_service.NotTheLogOwner as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except log_service.DailyLogError as exc:
            # The base class on purpose: out-of-window, unselected subject and
            # over-long day are all "your request, not our state", and catching the
            # family means a rule added to the service later fails as a 400 rather
            # than as a 500.
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # Echo the date back off the **stored** row, not off the request body, so the
        # response cannot claim to have saved a day other than the one it saved.
        return Response(_study_log_payload(engagement, log.log_date))


# ── S6/S7 (§14): the advisor's study feed and study planner ──────────────────

def _resolve_engagement_or_404(request, pk: int):
    """The shared first line of every advisor route below.

    ``scope.advisor_engagement`` answers ``None`` for both "no such id" and "not
    yours", and the view turns that into a **404, not a 403** — a 403 would
    confirm the engagement exists and leak that some advisor works with that
    student. Returns ``(engagement, None)`` or ``(None, response)``.
    """
    engagement = advisor_engagement(request.user, pk)
    if engagement is None:
        return None, Response(
            {'detail': 'همکاری پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND,
        )
    return engagement, None


class AdvisorStudyFeedView(APIView):
    """``GET /api/advisory/students/<pk>/study-feed/?days=7|14|30|all`` (S6).

    The advisor's window onto the student's reported days plus the published
    plans intersecting that window. ``days`` selects the horizon; anything else
    is a 400 with the exact Persian message the frontend chips map to. On a
    successful 200 exactly **one** ``AdvisoryAccessLog(action='study_feed_view')``
    row is appended (D4) — and on any error none is, so the audit trail counts
    successful reads only.
    """

    permission_classes = [IsAuthenticated, IsAdvisorUser]

    @extend_schema(
        tags=['advisory'],
        summary='فید مطالعه‌ی یک دانش‌آموز برای مشاور',
        description=(
            '`pk` شناسه‌ی همکاری است؛ همکاریِ ناموجود یا متعلق به مشاورِ دیگر ۴۰۴. '
            '`days` یکی از ۷، ۱۴، ۳۰ یا `all` (از شروع همکاری)؛ مقدار نامعتبر ۴۰۰. '
            'شروعِ بازه هرگز پیش از شروعِ همکاری نمی‌رود (کلمپ C3).'
        ),
        parameters=[
            OpenApiParameter(
                name='days',
                description='طول بازه: 7 | 14 | 30 | all. پیش‌فرض: 7.',
                required=False,
                type=str,
            ),
        ],
        responses={
            200: OpenApiResponse(
                description=(
                    '{studentName, range:{from,to}, days[], plans[], '
                    'adherencePercent, moodAverage}'
                ),
            ),
            400: OpenApiResponse(description='بازه‌ی نامعتبر'),
            404: OpenApiResponse(description='همکاری پیدا نشد'),
        },
    )
    def get(self, request, pk: int):
        engagement, error = _resolve_engagement_or_404(request, pk)
        if error is not None:
            return error

        raw_days = request.query_params.get('days', '7')
        if raw_days not in {'7', '14', '30', 'all'}:
            return Response(
                {'detail': 'بازه باید یکی از ۷، ۱۴، ۳۰ یا all باشد.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        days = None if raw_days == 'all' else int(raw_days)

        from_date, to_date = feed_date_range(engagement, days)
        logs = advisor_feed_logs(engagement, from_date, to_date)

        # Plan intersection in Python: the horizon end is computed
        # (start + duration - 1), and the plan count per engagement is small.
        # The nested enum keeps this file free of a tenancy-model import.
        plans = [
            plan
            for plan in advisor_plans(engagement)
            if plan.status == plan.Status.PUBLISHED
            and plan.start_date <= to_date
            and plan.end_date >= from_date
        ]

        days_data = FeedDaySerializer(logs, many=True).data
        # Restart step 4: stamp «جبران‌نشده» onto the serialized day items from
        # the PUBLISHED plans of each date's week (pure, in-place, additive).
        plan_service.attach_uncompensated_flags(days_data, plans)
        payload = {
            'studentName': _display_name(engagement.student),
            'range': {'from': from_date, 'to': to_date},
            'days': days_data,
            'plans': StudyPlanOutSerializer(plans, many=True).data,
            # S8 chips — quiet-None when there is nothing to measure; the null
            # and clipping rules live on the two service helpers.
            'adherencePercent': plan_service.feed_overall_adherence(
                engagement, plans, from_date, to_date,
            ),
            'moodAverage': plan_service.feed_mood_average(days_data),
        }
        # After the payload, before the answer: a failed read above returned
        # early, so this row lands only for a successful 200 — exactly one.
        plan_service.record_study_feed_view(engagement, request.user)
        return Response(payload)


class AdvisorStudyPlanDraftView(APIView):
    """``PUT /api/advisory/students/<pk>/study-plan/draft/`` (S7).

    Upserts the engagement's **single** DRAFT slot wholesale: the body is the
    whole draft and omitted rows are gone. The answer is the stored plan in the
    same ``PlanOut`` shape publish/unpublish answer with, so one client renderer
    covers all three.
    """

    permission_classes = [IsAuthenticated, IsAdvisorUser]

    @extend_schema(
        tags=['advisory'],
        summary='ذخیره‌ی پیش‌نویس برنامه‌ی مطالعه (جایگزینی کامل)',
        description=(
            'بدنه `{startDate, durationDays, items:[{dayOffset, subjectId, '
            'plannedMinutes}]}` کلِ اسلات پیش‌نویس را عوض می‌کند. ترتیب خطاها: '
            'شروعِ پیش از همکاری، طول بیرون از ۱..۹۰، روزِ بیرون از طول، درسِ '
            'غیرفعال، دقیقه‌ی بیرون از ۱..۹۶۰، ردیفِ تکراری — همه ۴۰۰.'
        ),
        request=StudyPlanDraftWriteSerializer,
        responses={
            200: StudyPlanOutSerializer,
            400: OpenApiResponse(description='بدنه‌ی نامعتبر'),
            404: OpenApiResponse(description='همکاری پیدا نشد'),
        },
    )
    def put(self, request, pk: int):
        engagement, error = _resolve_engagement_or_404(request, pk)
        if error is not None:
            return error

        serializer = StudyPlanDraftWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            plan = plan_service.save_draft(
                engagement,
                start_date=data['start_date'],
                duration_days=data['duration_days'],
                items=data['items'],
                # Absent key ⇒ UNSET ⇒ stored day notes untouched (legacy
                # planner payloads must not wipe what they never sent).
                day_notes=data.get('day_notes', plan_service.UNSET),
                # Research wave (2026-08-31): roadmap labels, wholesale like
                # the rest of the draft body.
                phase=data.get('phase', ''),
                strategy=data.get('strategy', ''),
            )
        except plan_service.StudyPlanError as exc:
            # The base class on purpose: every rule the door adds later must fail
            # as a 400 the advisor can act on, never as a 500.
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(StudyPlanOutSerializer(plan).data)


class AdvisorStudyPlansView(APIView):
    """``GET /api/advisory/students/<pk>/study-plans/`` — every status, calendar order.

    The planner's list view: drafts and published plans side by side, ascending
    by start date, so the advisor sees what is live and what is still scratch.
    """

    permission_classes = [IsAuthenticated, IsAdvisorUser]

    @extend_schema(
        tags=['advisory'],
        summary='همه‌ی برنامه‌های مطالعه‌ی یک دانش‌آموز',
        description='پیش‌نویس و منتشرشده با هم، صعودی بر اساس تاریخ شروع.',
        responses={
            200: OpenApiResponse(description='{plans: PlanOut[]}'),
            404: OpenApiResponse(description='همکاری پیدا نشد'),
        },
    )
    def get(self, request, pk: int):
        engagement, error = _resolve_engagement_or_404(request, pk)
        if error is not None:
            return error
        plans = advisor_plans(engagement)
        return Response({'plans': StudyPlanOutSerializer(plans, many=True).data})


class AdvisorStudyPlanPublishView(APIView):
    """``POST /api/advisory/students/<pk>/study-plan/draft/publish/`` (S7).

    Re-validates the draft against the *current* state — selections may have
    changed since it was saved — then checks overlap with the other PUBLISHED
    plans and flips it. No draft is a 404 (nothing to publish), an empty or
    stale draft a 400.
    """

    permission_classes = [IsAuthenticated, IsAdvisorUser]

    @extend_schema(
        tags=['advisory'],
        summary='انتشار پیش‌نویس برنامه‌ی مطالعه',
        description=(
            'اعتبارسنجی دوباره مقابل انتخاب‌های فعلی؛ خالی ⇒ ۴۰۰، درسِ حذف‌شده '
            '⇒ ۴۰۰، همپوشانی با برنامهٔ منتشرشدهٔ دیگر ⇒ ۴۰۰ (لمسِ لبه مجاز است)، '
            'پیش‌نویسی که نیست ⇒ ۴۰۴.'
        ),
        request=None,
        responses={
            200: StudyPlanOutSerializer,
            400: OpenApiResponse(description='خالی / درسِ حذف‌شده / همپوشانی'),
            404: OpenApiResponse(description='پیش‌نویس یا همکاری پیدا نشد'),
        },
    )
    def post(self, request, pk: int):
        engagement, error = _resolve_engagement_or_404(request, pk)
        if error is not None:
            return error

        try:
            plan = plan_service.publish_draft(engagement)
        except plan_service.PlanNotFound as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except plan_service.StudyPlanError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(StudyPlanOutSerializer(plan).data)


class AdvisorStudyPlanUnpublishView(APIView):
    """``POST /api/advisory/students/<pk>/study-plan/<plan_id>/unpublish/`` (S7).

    The §5 rollback lever: the plan leaves the student's view by returning to the
    draft slot. A plan id that is not a PUBLISHED plan of **this** engagement is
    a 404 — foreign ids and nonexistent ones are indistinguishable, same as the
    engagement-level convention.
    """

    permission_classes = [IsAuthenticated, IsAdvisorUser]

    @extend_schema(
        tags=['advisory'],
        summary='لغو انتشار برنامه‌ی مطالعه',
        description='برنامهٔ منتشرشده به پیش‌نویس برمی‌گردد و از دید دانش‌آموز محو می‌شود.',
        request=None,
        responses={
            200: StudyPlanOutSerializer,
            404: OpenApiResponse(description='برنامه یا همکاری پیدا نشد'),
        },
    )
    def post(self, request, pk: int, plan_id: int):
        engagement, error = _resolve_engagement_or_404(request, pk)
        if error is not None:
            return error

        try:
            plan = plan_service.unpublish_plan(engagement, plan_id)
        except plan_service.PlanNotFound as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except plan_service.StudyPlanError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(StudyPlanOutSerializer(plan).data)


class StudentPlansView(APIView):
    """``GET /api/advisory/me/plans/`` — the student's published plans.

    Quiet like every ``me/`` read: no active advisor is the ordinary state and
    answers ``200 {"plans": []}``, never a 404. Only PUBLISHED plans appear —
    publishing is precisely the act of making a plan visible here — newest
    horizon first so the client's «next up» card is the first element.
    """

    permission_classes = [IsAuthenticated, IsStudentRole]

    @extend_schema(
        tags=['advisory'],
        summary='برنامه‌های مطالعه‌ی منتشرشده‌ی دانش‌آموز',
        description='بی‌مشاور `200 {"plans": []}` — خطا نیست. فقط منتشرشده‌ها، نزولی.',
        responses={200: OpenApiResponse(description='{plans: PlanOut[]}')},
    )
    def get(self, request):
        plans = student_published_plans(request.user)
        return Response({'plans': StudyPlanOutSerializer(plans, many=True).data})
