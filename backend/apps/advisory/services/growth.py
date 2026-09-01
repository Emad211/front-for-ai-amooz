"""Advisor-owned composite growth projection — the decision-support read model.

One engagement, one response: a FLAT evidence digest plus at most three
deterministic recommendations. Deliberately NOT a dump of the whole
notebook/analytics payload — the advisor decision surface needs the few
numbers a decision cites, and the existing feed/plan/exam tabs already
carry the full detail. Services stay serializer-free: models are mapped
to plain primitives here and the view shapes the wire dict directly.
"""

from __future__ import annotations

from django.utils import timezone

from . import analytics as analytics_service
from . import mistakes as mistake_service
from . import topics as topic_service
from .recommendations import build_recommendations

# Flat evidence vocabulary — keys are the contract shared with the frontend's
# ``AdvisorGrowthEvidenceValue`` panel; values must stay scalar
# (str | int | bool | None) so the UI renders them without interpretation.
EVIDENCE_KEYS = (
    'streak',
    'loggedToday',
    'planExecutionPercent',
    'latestExamPercent',
    'examTrend',
    'openMistakes',
    'reviewDue',
    'backlogTotal',
    'testDensity',
    'mistakeResolutionDays',
    'planCalibration',
    'reportRate7d',
    'advisorDosageDays',
)


def build_evidence_digest(analytics: dict) -> dict:
    """Flatten the analytics bundle into display-safe scalar metrics."""
    trend_rows = analytics.get('examTrend') or []
    percents = [row['score_percent'] for row in trend_rows if row['score_percent'] is not None]
    latest = percents[-1] if percents else None
    if len(percents) >= 2:
        delta = percents[-1] - percents[-2]
        trend = 'روند صعودی' if delta > 0 else 'روند نزولی' if delta < 0 else 'ثابت'
    else:
        trend = 'بدون داده'
    plan_execution = analytics.get('planExecution')
    return {
        'streak': analytics['streak'],
        'loggedToday': analytics['loggedToday'],
        'planExecutionPercent': plan_execution['percent'] if plan_execution else None,
        'latestExamPercent': latest,
        'examTrend': trend,
        'openMistakes': analytics['openMistakes'],
        'reviewDue': len(analytics['reviewDue']),
        'backlogTotal': analytics['backlogTotal'],
        'testDensity': analytics.get('testDensity'),
        'mistakeResolutionDays': analytics.get('mistakeResolutionDays'),
        'planCalibration': analytics.get('planCalibration'),
        'reportRate7d': analytics.get('reportRate7d'),
        'advisorDosageDays': analytics.get('advisorDosageDays'),
    }


def get_growth_projection(engagement) -> dict:
    """Build the read-only wire payload for a resolved ACTIVE engagement."""
    today = timezone.localdate()
    analytics = analytics_service.compute_analytics(engagement)

    # Serializer-free by boundary rule: services map models to plain primitives.
    mistake_rows = [
        {
            'id': row.pk,
            'topic': row.topic,
            'priority': row.priority,
            'isResolved': row.is_resolved,
            'nextAction': row.next_action,
        }
        for row in mistake_service.list_mistakes(engagement)
    ]
    topic_rows = [
        {
            'id': row.pk,
            'topic': row.topic,
            'status': row.status,
            'nextReviewAt': row.next_review_at.isoformat() if row.next_review_at else None,
        }
        for row in topic_service.list_topics(engagement)
    ]

    return {
        'active': True,
        'asOf': today.isoformat(),
        'evidence': build_evidence_digest(analytics),
        'recommendations': build_recommendations(
            mistakes=mistake_rows,
            topics=topic_rows,
            analytics=analytics,
            as_of=today,
        ),
    }
