"""The advisor cockpit's read-side aggregator (``GET /api/advisory/overview/``).

A new module rather than more ``scope.py`` on purpose: scope is the tenancy
*door* and stays free of metric arithmetic, exactly as ``study_plans`` keeps its
S8 helpers out of the write door itself. Everything computed here is read-side
and pure in that same sense — nothing is written, and every number is either
lifted verbatim from an existing feed helper or a trivial column read.

One row per **ACTIVE** engagement (the roster), plus two roster-level numbers.
The three per-student metrics:

* ``adherence7d`` — the study feed's own «۷ روز» chip, not a reimplementation:
  the window comes from ``scope.feed_date_range(engagement, 7)`` (so the C3
  clamp to ``started_on`` rides along), the plan set is the same
  PUBLISHED-and-intersecting filter the feed view runs, and the ratio is
  ``study_plans.feed_overall_adherence`` itself. No published plan with elapsed
  planned minutes ⇒ ``None``, which is precisely when the feed would show no
  adherence either.
* ``lastLogDate`` — max ``DailyLog.log_date`` for the engagement; batched into
  one aggregate across the whole roster so N students cost one query, not N.
* ``activeChallengeTitle`` — title of the engagement's first ACTIVE challenge
  by ``-id`` (newest created wins); prefetched per roster in one extra query.

The two roster-level numbers reuse the scope queries the existing screens use:
``activeStudents`` is the length of ``scope.advisor_students`` and
``pendingInvites`` is ``scope.advisor_pending_invites(...).count()`` — the same
count ``AdvisorStudentListView``'s quota check and outbox answer from, i.e.
**all** PENDING rows including expired ones (an unanswered invite must stay
visible to the advisor even after its TTL).

This module imports tenancy-bearing models directly for those two batched
reads, so it sits on ``test_import_boundaries._EXEMPT_FILES`` next to the other
read/write doors — pinned there on purpose, like every entry before it.
"""

from __future__ import annotations

from django.db.models import Max, Prefetch

from ..models import DailyLog, StudyChallenge, StudyPlan
from . import scope
from .study_plans import feed_overall_adherence

# The trailing window the cockpit's adherence chip covers: the same «۷ روز»
# chip the study feed defaults to. ``feed_date_range`` turns this into the
# inclusive ``[max(started_on, today-6), today]`` pair, C3 clamp included.
ADHERENCE_WINDOW_DAYS = 7


def engagement_adherence_7d(engagement) -> int | None:
    """The feed's overall-adherence number over this engagement's trailing week.

    Deliberately a transcription of ``AdvisorStudyFeedView.get``'s plan step,
    with only the window fixed at 7 days: intersecting PUBLISHED plans are
    selected first (status-blind drafts excluded, horizons compared inclusively
    against the window), then handed to ``feed_overall_adherence`` together with
    the engagement and the same ``(from, to)`` pair. The quiet-``None`` rule —
    no surviving plan with elapsed planned minutes — is the helper's own, so
    this endpoint can never disagree with the feed's chip about the same week.
    """
    date_from, date_to = scope.feed_date_range(engagement, ADHERENCE_WINDOW_DAYS)
    plans = [
        plan
        for plan in scope.advisor_plans(engagement)
        if plan.status == StudyPlan.Status.PUBLISHED
        and plan.start_date <= date_to
        and plan.end_date >= date_from
    ]
    return feed_overall_adherence(engagement, plans, date_from, date_to)


def _last_log_dates(engagement_ids) -> dict:
    """``{engagement_id: max(log_date)}`` for the roster, in one query.

    Rosters without any log yet simply miss their key; the caller renders that
    as ``None`` («هیچ گزارشی ثبت نشده»), never as an error.
    """
    if not engagement_ids:
        return {}
    return dict(
        DailyLog.objects.filter(engagement_id__in=engagement_ids)
        .values('engagement_id')
        .annotate(last_date=Max('log_date'))
        .values_list('engagement_id', 'last_date')
    )


def _active_challenges_prefetch() -> Prefetch:
    """ACTIVE challenges only, newest id first — the contract's pick order."""
    # The literal is the first code of ``CHALLENGE_STATUS_CHOICES``; the model
    # carries no nested enum to name here.
    return Prefetch(
        'challenges',
        queryset=StudyChallenge.objects.filter(status='ACTIVE').order_by('-id'),
    )


def advisor_overview(advisor) -> dict:
    """Build the whole cockpit payload for one advisor.

    Returns plain snake_case dicts; ``serializers.AdvisorOverviewResponseSerializer``
    owns the camelCase wire projection. Row order is ``scope.advisor_students``'s
    own (newest started/invited first) — the roster's order, unchanged.
    """
    engagements = list(
        scope.advisor_students(advisor).prefetch_related(_active_challenges_prefetch())
    )
    # Same count the roster endpoint answers with — all PENDING rows, expired
    # ones included, because an unanswered invite is information the advisor
    # needs (see ``scope.advisor_pending_invites``).
    pending_invites = scope.advisor_pending_invites(advisor).count()
    last_logs = _last_log_dates([engagement.pk for engagement in engagements])

    adherences = []
    rows = []
    for engagement in engagements:
        adherence = engagement_adherence_7d(engagement)
        if adherence is not None:
            adherences.append(adherence)
        challenges = list(engagement.challenges.all())  # prefetched above
        rows.append({
            'engagement_id': engagement.pk,
            'adherence7d': adherence,
            'last_log_date': last_logs.get(engagement.pk),
            'active_challenge_title': challenges[0].title if challenges else None,
        })

    average = round(sum(adherences) / len(adherences), 1) if adherences else None
    return {
        'metrics': {
            'active_students': len(engagements),
            'pending_invites': pending_invites,
            'average_adherence_7d': average,
        },
        'students': rows,
    }
