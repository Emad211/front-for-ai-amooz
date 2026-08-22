"""The only door to tenancy-bearing advisory data.

The repository's existing pattern is a hand-rolled ``IsOrgAdmin.check(...)`` call
repeated at ~19 call sites in ``organizations``. One forgotten call there is one
cross-tenant leak. Advisory does not repeat that: every view asks this module for
a queryset that is *already* scoped, and a guard test (``test_import_boundaries``)
keeps advisory models from being imported anywhere else.

Step 3 adds the engagement queries. Step 5 adds the student-side log reads plus
``log_date_window``, the one place the C3 "no retroactive visibility" bound is
written down; ``visible_logs`` / ``visible_plans`` are the *advisor*-facing reads
and land in steps 6 and 7 with the feed and the planner that consume them, built
on top of ``visible_engagements`` and reusing that same window.
"""

from __future__ import annotations

import datetime

from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.organizations.models import Organization, OrganizationMembership

from ..models import AdvisoryEngagement, DailyLog, StudentSubject, Subject


def advisor_organization_ids(user) -> list[int]:
    """Return the organizations whose private data this advisor may see.

    Three conditions, all live (no cached column, no denormalized flag):

    1. the membership row exists and is ``ACTIVE`` — a suspended advisor loses
       access the moment the manager suspends them, with no signal to fire;
    2. its ``org_role`` is ``advisor`` — being a *student* or *teacher* of an
       organization grants no advisory visibility;
    3. the organization's subscription is ``ACTIVE`` — an expired org goes dark
       for the same reason it does everywhere else in the platform.

    Membership rows are hard-deleted on removal (``organizations/views.py``), so
    checking them live is the only reliable gate — see C1 in the spec.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return []
    return list(
        OrganizationMembership.objects.filter(
            user=user,
            org_role=OrganizationMembership.OrgRole.ADVISOR,
            status=OrganizationMembership.MemberStatus.ACTIVE,
            organization__subscription_status=Organization.SubscriptionStatus.ACTIVE,
        )
        .values_list('organization_id', flat=True)
        .distinct()
    )


def _is_advisor(user) -> bool:
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    return getattr(user, 'role', None) == 'ADVISOR'


def _is_student(user) -> bool:
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    return getattr(user, 'role', None) == 'STUDENT'


def visible_engagements(advisor) -> QuerySet[AdvisoryEngagement]:
    """Every engagement this advisor may act on, in any status.

    Two halves, and the difference between them is the whole point of C1:

    * **freelance** rows need only ``advisor=advisor`` — the advisor owns them
      outright, nobody can revoke them but the student;
    * **org** rows are additionally filtered through ``advisor_organization_ids``,
      re-evaluated on **every** query. When a manager removes an advisor from the
      organization the membership row is hard-deleted with no signal fired, so a
      stored flag would keep the advisor reading that org's students forever.
      The join is layer one of C1's three; the sweep and the nightly reconciler
      land in step 9 with the org fan-out that actually creates these rows.

    A non-advisor gets an empty queryset rather than an exception: views already
    return 403 via ``IsAdvisorUser``, and a silent ``.none()`` here means a future
    caller that forgets the permission class leaks nothing.
    """
    if not _is_advisor(advisor):
        return AdvisoryEngagement.objects.none()
    org_ids = advisor_organization_ids(advisor)
    return AdvisoryEngagement.objects.filter(
        Q(mode=AdvisoryEngagement.Mode.FREELANCE)
        | Q(mode=AdvisoryEngagement.Mode.ORG, organization_id__in=org_ids),
        advisor=advisor,
    )


def advisor_engagement(advisor, pk) -> AdvisoryEngagement | None:
    """Resolve one engagement by id **from the advisor's visible set**, or ``None``.

    This is the per-id sibling of ``visible_engagements``: a view hands it a URL
    ``pk`` and gets back either the row the advisor owns or ``None`` — never a row
    belonging to someone else. The view turns ``None`` into a **404, not a 403**
    (the S1–S3 convention): a 403 would confirm the engagement exists and leak that
    some advisor works with that student. Because the lookup rides on
    ``visible_engagements``, a foreign row and a nonexistent id are indistinguishable
    here, which is exactly what upholds that.
    """
    if not _is_advisor(advisor):
        return None
    return visible_engagements(advisor).filter(pk=pk).first()


def advisor_students(advisor) -> QuerySet[AdvisoryEngagement]:
    """The advisor's roster — ``ACTIVE`` engagements only, student prefetched."""
    return (
        visible_engagements(advisor)
        .filter(status=AdvisoryEngagement.Status.ACTIVE)
        .select_related('student', 'organization')
        .order_by('-started_on', '-invited_at')
    )


def advisor_pending_invites(advisor) -> QuerySet[AdvisoryEngagement]:
    """Invites the advisor has sent that nobody has answered yet.

    Expired invites are included on purpose: the advisor needs to see that the
    invite went unanswered, otherwise a wrong number silently disappears and gets
    typed again. ``is_expired`` on the model marks them for the UI.
    """
    return (
        visible_engagements(advisor)
        .filter(status=AdvisoryEngagement.Status.PENDING)
        .select_related('student')
        .order_by('-invited_at')
    )


def student_active_engagement(student) -> AdvisoryEngagement | None:
    """The student's one current advisor, or ``None``.

    The partial unique constraint guarantees at most one ``ACTIVE`` row, so this
    returning a single object rather than a queryset is a fact about the schema,
    not an assumption.
    """
    if not _is_student(student):
        return None
    return (
        AdvisoryEngagement.objects.filter(
            student=student,
            status=AdvisoryEngagement.Status.ACTIVE,
        )
        .select_related('advisor', 'organization')
        .first()
    )


def student_claimable_invites(student) -> QuerySet[AdvisoryEngagement]:
    """Invites this student may still accept or reject.

    Expired ones are excluded here, unlike ``advisor_pending_invites``: this
    queryset is what the accept/reject views look up through, so an expired row
    must be **absent** and produce a 404 rather than be accept-able.
    """
    if not _is_student(student):
        return AdvisoryEngagement.objects.none()
    return (
        AdvisoryEngagement.objects.filter(
            student=student,
            status=AdvisoryEngagement.Status.PENDING,
        )
        .filter(
            Q(invite_expires_at__isnull=True) | Q(invite_expires_at__gt=timezone.now()),
        )
        .select_related('advisor')
        .order_by('-invited_at')
    )


# ── S4: per-student subject selection ────────────────────────────────────────

def student_subjects(engagement) -> QuerySet[StudentSubject]:
    """The **active** subject rows selected for one engagement, subject prefetched.

    Read side of the S4 write door. Takes a resolved engagement (the caller has
    already proven ownership via ``advisor_engagement`` or
    ``student_active_engagement``), so it does no scoping of its own — it only
    hides the deactivated history rows the set-replace leaves behind.
    """
    return (
        StudentSubject.objects.filter(engagement=engagement, is_active=True)
        .select_related('subject', 'subject__organization')
        .order_by('subject__name')
    )


def assignable_subjects(advisor) -> QuerySet[Subject]:
    """The subjects this advisor is allowed to select for a student.

    The single source of truth for "what may this advisor assign", used both to
    build the picker and to validate a write (``services/student_subjects``). It is
    the same set ``SubjectListView`` shows: active, and either global
    (``organization IS NULL``) or private to an organization the advisor currently
    belongs to. Re-evaluated live through ``advisor_organization_ids`` for the same
    C1 reason ``visible_engagements`` is — a removed advisor loses org subjects at
    once. A non-advisor gets ``.none()``, never an exception.
    """
    if not _is_advisor(advisor):
        return Subject.objects.none()
    org_ids = advisor_organization_ids(advisor)
    return Subject.objects.filter(is_active=True).filter(
        Q(organization__isnull=True) | Q(organization_id__in=org_ids),
    )


# ── national curriculum: subjects derived from the student's own (grade, major) ──

def student_organization_ids(student) -> list[int]:
    """The organizations whose private subjects this student may see.

    The student-side mirror of ``advisor_organization_ids``, and it keeps the same
    three live conditions — only ``org_role`` differs (``STUDENT`` not ``ADVISOR``).
    A subject an org made private is offered to that org's students on top of the
    national base; a student who leaves the org (membership hard-deleted) loses
    those the moment they go, with no signal to fire — hence the live check, never
    a stored flag. C1 again, on the student side.
    """
    if not student or not getattr(student, 'is_authenticated', False):
        return []
    return list(
        OrganizationMembership.objects.filter(
            user=student,
            org_role=OrganizationMembership.OrgRole.STUDENT,
            status=OrganizationMembership.MemberStatus.ACTIVE,
            organization__subscription_status=Organization.SubscriptionStatus.ACTIVE,
        )
        .values_list('organization_id', flat=True)
        .distinct()
    )


def curriculum_subjects(student) -> QuerySet[Subject]:
    """The national curriculum a student's own (grade, major) derives — the S4
    picker's candidate set, replacing the flat ``assignable_subjects`` catalog.

    Three identity cases the query reads (see ``Subject`` model comment):

    * a subject's ``grade`` must equal the student's grade — a NULL-grade row
      (dead/legacy) derives for nobody;
    * ``major`` must be either the student's own major **or** NULL (the general
      subjects shared across every major of that grade);
    * scope must be national (``organization IS NULL``) **or** an org the student
      currently belongs to.

    Defensive exactly like ``AdvisorEngagementSubjectsView._student_axes``: a
    student with no ``StudentProfile`` — or a profile with no grade — has no
    derivable curriculum, so the answer is an empty queryset, never an exception.
    ``is_active=True`` is filtered here so a deactivated subject is genuinely
    non-assignable, not merely hidden from the picker.
    """
    if not hasattr(student, 'studentprofile'):
        return Subject.objects.none()
    profile = student.studentprofile
    grade = getattr(profile, 'grade', None)
    if not grade:
        return Subject.objects.none()
    major = getattr(profile, 'major', None) or None
    org_ids = student_organization_ids(student)
    return (
        Subject.objects.filter(is_active=True, grade=grade)
        .filter(Q(major=major) | Q(major__isnull=True))
        .filter(Q(organization__isnull=True) | Q(organization_id__in=org_ids))
    )


# ── S5: the daily study log ──────────────────────────────────────────────────

def log_date_window(engagement) -> tuple[datetime.date, datetime.date]:
    """The inclusive ``(earliest, latest)`` date a log may be written or read for.

    **This is where C3 lives.** The upper bound is today: a study log is a report of
    what happened, so tomorrow cannot be reported, and allowing it would let a
    student pre-fill a week and make the S8 commitment metric a forecast instead of a
    measurement. The lower bound is ``started_on`` — the day the student accepted —
    which is the whole of "no retroactive visibility": an advisor hired in آبان never
    sees مهر, and they never see it because those days are *not writable*, not because
    a reader remembered to filter them.

    ``started_on`` is nullable on the model (a PENDING row has none), and this
    function is only ever called for an ACTIVE engagement, where the accept path set
    it. It still guards: a NULL falls back to today, i.e. the narrowest possible
    window (today only) rather than the widest. If that data ever goes wrong the
    failure is "the student can only log today", not "the advisor can read the
    student's whole life".

    Returned as plain dates so callers compare with ``<=`` and the same two bounds
    reach the write door, the wire payload (``minDate``/``maxDate``) and step 6's
    advisor feed. Uses ``timezone.localdate()``, never ``date.today()``: the server
    runs UTC and «امروز» must mean the student's today.
    """
    today = timezone.localdate()
    started = getattr(engagement, 'started_on', None) or today
    # A clock skew or a hand-edited row could put ``started_on`` in the future; that
    # must collapse to an empty-but-valid window, not an inverted one.
    return (min(started, today), today)


def student_logs(engagement) -> QuerySet[DailyLog]:
    """Every day this engagement has recorded, newest first, items prefetched.

    Read side of the S5 write door, and the sibling of ``student_subjects``: it takes
    an engagement the caller has already resolved (via ``student_active_engagement``
    for the student, ``advisor_engagement`` for step 6's advisor) and does no scoping
    of its own.

    The item prefetch deliberately does **not** filter on
    ``student_subject__is_active``. An advisor dropping a subject must not erase the
    minutes a student already logged against it — see ``DailyLogItem``'s docstring.
    """
    return (
        DailyLog.objects.filter(engagement=engagement)
        .prefetch_related('items__student_subject__subject')
        .order_by('-log_date')
    )


def student_day_log(engagement, log_date) -> DailyLog | None:
    """One day's log, or ``None`` if the student has not reported that day.

    ``None`` is the ordinary case, not an error: most days are unreported, and the
    view answers with an empty form rather than a 404 — a 404 for "you have not
    written today's log yet" would be absurd.
    """
    return student_logs(engagement).filter(log_date=log_date).first()

