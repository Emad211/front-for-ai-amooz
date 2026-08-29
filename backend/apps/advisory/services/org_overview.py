"""The aggregation layer behind risman step 3 — the thin org-manager panel.

A read-side engine like ``reports.py`` (and sharing its bucket math so the two
surfaces can never disagree about what «تعهد» means), plus the ONE org-side
write: moving a student from one of the org's advisors to another. Pure functions;
every lookup that decides visibility has already happened in ``views_org.py``.
The resolved org is the tenancy here: nothing below ever queries an engagement
without ``mode=org, organization=org`` — a freelance pair of the same humans is
invisible to this module by construction (ق۳, ق۶).

Deviation note (deliberate): ``reports.advisor_report`` measures an advisor's
WHOLE roster including freelance students, so the org report cannot wrap it.
Instead this module reuses the shared bucket helpers (``_planned_buckets`` /
``_actual_buckets`` / ``_coverage_percent``) directly — one source of arithmetic,
two scopes of filtering.
"""

from __future__ import annotations

import datetime

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.models import Organization, OrganizationMembership

from ..models import (
    AdvisoryAccessLog,
    AdvisoryEngagement,
    DailyLog,
    DailyLogItem,
    StudyExamAnalysis,
    StudyPlan,
    WeeklyAssessment,
)
from . import calendar, reports


class OrgOverviewError(Exception):
    """Base typed error the view turns into a 400/404 with its Persian message."""

    http_status = 400


class OrgResourceNotFound(OrgOverviewError):
    """A referenced resource does not exist inside THIS org (ق۶: ۴۰۴ نه ۴۰۳)."""

    http_status = 404


def _display(user) -> str:
    """Same label rule as the roster/report serializers."""
    return reports._display_name(user)


def _active_org_engagements(org: Organization):
    """Every ACTIVE org-mode engagement of one organization, people joined."""
    return (
        AdvisoryEngagement.objects.select_related('advisor', 'student')
        .filter(
            mode=AdvisoryEngagement.Mode.ORG,
            organization=org,
            status=AdvisoryEngagement.Status.ACTIVE,
        )
        .order_by('id')
    )


def org_overview(org: Organization) -> dict:
    """Live headline counters of one organization (camelCase per ق۸).

    ``avgCommitmentPercent`` is the WEIGHTED overall over the current Iranian
    week (شنبه-anchor from the shared calendar module): Σactual ÷ Σplanned —
    matching the feed doctrine («never averaging percentages»), clamped to
    elapsed days by the shared buckets, and quiet-NULL when nothing was planned
    yet — never a fake 0%.
    """
    today = timezone.localdate()
    week_start = calendar.week_start_of(today)
    week_end = week_start + datetime.timedelta(days=6)

    engagements = list(_active_org_engagements(org))
    engagement_ids = [e.pk for e in engagements]

    planned_total = 0
    actual_total = 0
    for engagement in engagements:
        planned_by_day, _, _ = reports._planned_buckets(
            engagement, week_start, min(week_end, today),
        )
        actual_by_day, _, _ = reports._actual_buckets(
            engagement, week_start, min(week_end, today),
        )
        planned_total += sum(planned_by_day.values())
        actual_total += sum(actual_by_day.values())

    member_role = OrganizationMembership.OrgRole
    memberships = OrganizationMembership.objects.filter(
        organization=org,
        status=OrganizationMembership.MemberStatus.ACTIVE,
    )
    today_logs = DailyLog.objects.filter(
        engagement_id__in=engagement_ids, log_date=today,
    )
    minutes_today = (
        DailyLogItem.objects.filter(log__in=today_logs)
        .aggregate(total=Sum('actual_minutes'))['total']
        or 0
    )

    return {
        'activeStudents': memberships.filter(org_role=member_role.STUDENT).count(),
        'activeAdvisors': memberships.filter(org_role=member_role.ADVISOR).count(),
        'activeEngagements': len(engagements),
        'weekPlansPublished': StudyPlan.objects.filter(
            engagement_id__in=engagement_ids,
            status=StudyPlan.Status.PUBLISHED,
            start_date__gte=week_start,
            start_date__lte=week_end,
        ).count(),
        'logsToday': today_logs.count(),
        'minutesToday': int(minutes_today),
        'avgCommitmentPercent': reports._coverage_percent(
            actual_total, planned_total,
        ),
    }


def org_advisor_report(
    org: Organization,
    date_from: datetime.date,
    date_to: datetime.date,
) -> dict:
    """Per-advisor aggregates across the org's own rosters (the panel table).

    One row per advisor holding ≥1 ACTIVE org engagement (sorted by load, then
    name), embedding that advisor's per-student rows — each carrying its
    ENGAGEMENT id so the UI can hang the existing Excel export off it. Tool
    counters measure the advisor's usage **inside this org** only.
    """
    measurable_end = min(date_to, timezone.localdate())

    advisors: dict[int, dict] = {}
    for engagement in _active_org_engagements(org):
        planned_by_day, _, _ = reports._planned_buckets(
            engagement, date_from, measurable_end,
        )
        actual_by_day, _, _ = reports._actual_buckets(
            engagement, date_from, measurable_end,
        )
        planned = sum(planned_by_day.values())
        actual = sum(actual_by_day.values())
        tests_taken = DailyLog.objects.filter(
            engagement=engagement,
            log_date__gte=date_from,
            log_date__lte=date_to,
        ).aggregate(total=Sum('tests_taken'))['total'] or 0

        advisor = engagement.advisor
        bucket = advisors.setdefault(advisor.pk, {
            'advisorId': advisor.pk,
            'advisorName': _display(advisor),
            'students': [],
            '_engagementIds': [],
        })
        bucket['students'].append({
            'engagementId': engagement.pk,
            'studentName': _display(engagement.student),
            'planned': planned,
            'actual': actual,
            'coveragePercent': reports._coverage_percent(actual, planned),
            'testsTaken': int(tests_taken),
        })
        bucket['_engagementIds'].append(engagement.pk)

    rows = []
    for bucket in advisors.values():
        ids = bucket.pop('_engagementIds')
        students = sorted(bucket['students'], key=lambda r: r['studentName'])
        planned = sum(r['planned'] for r in students)
        actual = sum(r['actual'] for r in students)
        rows.append({
            **bucket,
            'students': students,
            'studentCount': len(students),
            'planned': planned,
            'actual': actual,
            'coveragePercent': reports._coverage_percent(actual, planned),
            'plansPublished': StudyPlan.objects.filter(
                engagement_id__in=ids,
                status=StudyPlan.Status.PUBLISHED,
                start_date__gte=date_from,
                start_date__lte=min(date_to, timezone.localdate()),
            ).count(),
            'assessmentsWritten': WeeklyAssessment.objects.filter(
                engagement_id__in=ids,
                week_start__gte=date_from,
                week_start__lte=date_to,
            ).count(),
            'analysesCreated': StudyExamAnalysis.objects.filter(
                engagement_id__in=ids,
                created_at__date__gte=date_from,
                created_at__date__lte=date_to,
            ).count(),
        })

    rows.sort(key=lambda r: (-r['studentCount'], r['advisorName']))
    return {'advisors': rows}


def reassign_engagement(
    org: Organization,
    engagement_pk: int,
    new_advisor_id: int,
    actor,
) -> AdvisoryEngagement:
    """Move one ACTIVE org engagement to another advisor OF THE SAME org.

    The single guarded write of the panel. Raises ``OrgResourceNotFound`` for an
    engagement that is not this org's (stranger ⇒ 404, ق۶) and
    ``OrgOverviewError`` (400) for every business-rule violation with a pinned
    Persian message. Both legs pass through org membership, so no freelancer and
    no foreign-org advisor can be smuggled in. An ``AdvisoryAccessLog`` row keeps
    the who-did-this answer, mirroring every other read/write trail of the app.
    """
    try:
        engagement = AdvisoryEngagement.objects.select_related(
            'student', 'advisor', 'organization',
        ).get(
            pk=engagement_pk,
            mode=AdvisoryEngagement.Mode.ORG,
            organization=org,
        )
    except AdvisoryEngagement.DoesNotExist as exc:
        raise OrgResourceNotFound('همکاری پیدا نشد.') from exc

    if engagement.status != AdvisoryEngagement.Status.ACTIVE:
        raise OrgOverviewError('فقط همکاری فعال قابل جابجایی است.')

    try:
        new_advisor = User.objects.get(pk=new_advisor_id)
    except User.DoesNotExist as exc:
        raise OrgOverviewError('مشاور انتخابی به این سازمان تعلق ندارد.') from exc

    if new_advisor.pk == engagement.advisor_id:
        raise OrgOverviewError('این دانش‌آموز از قبل با همین مشاور همکاری می‌کند.')
    if new_advisor.role != User.Role.ADVISOR:
        raise OrgOverviewError('کاربر انتخابی مشاور نیست.')
    if not OrganizationMembership.objects.filter(
        user=new_advisor,
        organization=org,
        org_role=OrganizationMembership.OrgRole.ADVISOR,
        status=OrganizationMembership.MemberStatus.ACTIVE,
    ).exists():
        raise OrgOverviewError('مشاور انتخابی به این سازمان تعلق ندارد.')

    with transaction.atomic():
        engagement.advisor = new_advisor
        engagement.save(update_fields=['advisor'])
        AdvisoryAccessLog.objects.create(
            reader=actor,
            engagement=engagement,
            action='org_reassign',
        )
    return engagement