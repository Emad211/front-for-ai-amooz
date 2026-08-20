"""The only door to tenancy-bearing advisory data.

The repository's existing pattern is a hand-rolled ``IsOrgAdmin.check(...)`` call
repeated at ~19 call sites in ``organizations``. One forgotten call there is one
cross-tenant leak. Advisory does not repeat that: every view asks this module for
a queryset that is *already* scoped, and a guard test (``test_import_boundaries``)
keeps advisory models from being imported anywhere else.

Step 3 adds the engagement queries. ``visible_logs`` / ``visible_plans`` land in
steps 5 and 7 alongside their models, and will be built *on top of*
``visible_engagements`` rather than beside it.
"""

from __future__ import annotations

from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.organizations.models import Organization, OrganizationMembership

from ..models import AdvisoryEngagement, StudentSubject, Subject


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

