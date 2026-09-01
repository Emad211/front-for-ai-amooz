"""The filtered weekly digest a parent reads — numbers only, by construction.

Wave 5 (2026-08-31). This module is the privacy filter as much as the math:
the payload it returns is the **entire** set of keys the parent route may
ship. Everything a consultant would recognize as sensitive prose — the
student's mood, free-text notes, day goals, motivation lines, mistake topics
and texts, call logs, weekly-assessment scores — simply has no code path into
this dict. ``test_parent_links`` pins that twice over: the key set is exact,
and the marker strings planted in the stored prose must be absent from the
serialized body.

The heavy lifting rides ``analytics.compute_analytics`` (streak, open
mistakes, due reviews) plus one small weekly window query for the numbers
analytics does not window: minutes logged, minutes planned and tests taken
over the last 7 days ending today. The window is inclusive of today and uses
``timezone.localdate()`` — «این هفته» is the student's week, not UTC's.
"""

from __future__ import annotations

import datetime

from django.db.models import Sum
from django.utils import timezone

from ..models import (
    DailyLog,
    DailyLogItem,
    StudyChallenge,
    StudyExamScore,
    StudyPlan,
    StudyPlanItem,
)
from .analytics import compute_analytics

DIGEST_WINDOW_DAYS = 7
EXAM_TREND_LIMIT = 5


def build_parent_digest(engagement) -> dict:
    """One engagement's weekly digest in the exact wire shape.

    The caller has already proven the reader owns an ACTIVE link to this
    engagement (``parent_links.parent_digest_link``), so this function does no
    scoping of its own — it is the pure build, safe to reuse from the Thursday
    beat if that ever needs the numbers too.
    """
    today = timezone.localdate()
    window_start = today - datetime.timedelta(days=DIGEST_WINDOW_DAYS - 1)

    week_minutes = (
        DailyLogItem.objects.filter(
            log__engagement=engagement,
            log__log_date__gte=window_start,
            log__log_date__lte=today,
        ).aggregate(total=Sum('actual_minutes'))['total']
        or 0
    )

    tests_taken = (
        DailyLog.objects.filter(
            engagement=engagement,
            log_date__gte=window_start,
            log_date__lte=today,
        ).aggregate(total=Sum('tests_taken'))['total']
        or 0
    )

    # Planned minutes: PUBLISHED plan rows whose calendar day falls inside the
    # window — the same per-item date arithmetic the backlog reader uses.
    week_plan_minutes = 0
    published_plans = (
        StudyPlan.objects.filter(
            engagement=engagement,
            status=StudyPlan.Status.PUBLISHED,
        ).prefetch_related('items')
    )
    for plan in published_plans:
        for item in plan.items.all():
            item_date = plan.start_date + datetime.timedelta(days=item.day_offset)
            if window_start <= item_date <= today:
                week_plan_minutes += item.planned_minutes

    adherence_percent = None
    if week_plan_minutes > 0:
        # Clipped at 100 like every adherence surface: a week at 200% is a
        # fact about over-delivery, not a bigger number for the parent to parse.
        adherence_percent = min(100, round(week_minutes / week_plan_minutes * 100))

    exam_trend = [
        {
            'date': row['exam_date'].isoformat(),
            'scorePercent': float(row['score_percent']),
            'tara': row['tara'],
        }
        for row in (
            StudyExamScore.objects.filter(engagement=engagement)
            .order_by('-exam_date', '-id')
            .values('exam_date', 'score_percent', 'tara')[:EXAM_TREND_LIMIT]
        )
    ]

    # Reuse the analytics bundle for the three numbers it already defines —
    # one definition, two surfaces (student analytics + parent digest).
    analytics = compute_analytics(engagement)

    return {
        'asOf': today.isoformat(),
        'weekMinutes': week_minutes,
        'weekPlanMinutes': week_plan_minutes or None,
        'adherencePercent': adherence_percent,
        'testsTaken': tests_taken,
        'examTrend': exam_trend,
        'openMistakesCount': analytics['openMistakes'],
        'reviewDueCount': len(analytics['reviewDue']),
        'activeChallengeTitle': StudyChallenge.objects.filter(
            engagement=engagement,
            status='ACTIVE',
        ).values_list('title', flat=True).first(),
        'streak': analytics['streak'],
    }
