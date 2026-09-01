"""Deterministic, evidence-backed growth recommendations (advisor read model).

Pure functions only: no queries, no writes, no LLM, no clock reads — the
caller injects ``as_of`` so identical evidence always yields identical
output. Rules run in a fixed precedence order, each citing the flat
evidence keys it derived from, and the list is capped at three items.

The wire contract (mirrored by ``AdvisorGrowthRecommendation`` on the
frontend) is::

    {
        'code': 'review-overdue-topics',      # stable, closed vocabulary
        'title': '…',                          # Persian display title
        'description': '…',                    # Persian, evidence-derived
        'priority': 'HIGH' | 'MEDIUM' | 'LOW',
        'evidenceKeys': ['reviewDue'],         # keys of the evidence digest
        'actionArea': 'plan' | 'exams' | 'feed' | None,
    }

``actionArea`` names an EXISTING advisor surface to open; it never
authorizes a mutation — the growth endpoint is read-only by design.
"""

from __future__ import annotations

import datetime
from typing import TypedDict

MAX_RECOMMENDATIONS = 3

AREA_PLAN = 'plan'
AREA_EXAMS = 'exams'
AREA_FEED = 'feed'

_PRIORITY_RANK = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}


class MistakeRuleData(TypedDict):
    id: int
    topic: str
    priority: str
    isResolved: bool
    nextAction: str


class TopicRuleData(TypedDict):
    id: int
    topic: str
    status: str
    nextReviewAt: str | None


class AnalyticsRuleData(TypedDict, total=False):
    loggedToday: bool
    backlogTotal: int
    backlog: list[dict[str, str | int]]
    planExecution: dict[str, str | int] | None


def _due_topics(topics: list[TopicRuleData], as_of: datetime.date) -> list[TopicRuleData]:
    due = [
        topic
        for topic in topics
        if topic['status'] == 'NEEDS_REVIEW'
        and topic['nextReviewAt'] is not None
        and datetime.date.fromisoformat(topic['nextReviewAt']) <= as_of
    ]
    due.sort(key=lambda item: (item['nextReviewAt'] or '', item['id']))
    return due


def build_recommendations(
    *,
    mistakes: list[MistakeRuleData],
    topics: list[TopicRuleData],
    analytics: AnalyticsRuleData,
    as_of: datetime.date,
) -> list[dict]:
    """Return at most three stable recommendations from supplied evidence."""
    recommendations: list[dict] = []

    due = _due_topics(topics, as_of)
    if due:
        names = '، '.join(f"«{topic['topic']}»" for topic in due[:3])
        suffix = ' و…' if len(due) > 3 else ''
        recommendations.append({
            'code': 'review-overdue-topics',
            'title': 'مرور مباحث عقب‌افتاده',
            'description': f'{len(due)} مبحث موعد مرورشان گذشته است: {names}{suffix}.',
            'priority': 'HIGH',
            'evidenceKeys': ['reviewDue'],
            'actionArea': AREA_PLAN,
        })

    open_mistakes = [mistake for mistake in mistakes if not mistake['isResolved']]
    open_mistakes.sort(key=lambda item: (_PRIORITY_RANK.get(item['priority'], 3), item['id']))
    if open_mistakes:
        top = open_mistakes[0]
        action = top['nextAction'].strip() if top['nextAction'] else ''
        lead = action or f"خطای حل‌نشدهٔ «{top['topic']}» را مرور کنید."
        recommendations.append({
            'code': 'follow-open-mistakes',
            'title': 'پیگیری خطاهای باز',
            'description': f'{len(open_mistakes)} خطای حل‌نشده ثبت شده است؛ اقدام بعدی: {lead}',
            'priority': 'HIGH' if top['priority'] == 'HIGH' else 'MEDIUM',
            'evidenceKeys': ['openMistakes'],
            'actionArea': AREA_EXAMS,
        })

    backlog = list(analytics.get('backlog') or [])
    if analytics.get('backlogTotal', 0) > 0 and backlog:
        row = sorted(
            backlog,
            key=lambda item: (
                -(int(item['planned']) - int(item['actual'])),
                str(item['date']),
                str(item['subject']),
            ),
        )[0]
        deficit = int(row['planned']) - int(row['actual'])
        recommendations.append({
            'code': 'compensate-backlog',
            'title': 'جبران عقب‌افتادگی برنامه',
            'description': f"بزرگ‌ترین شکاف: «{row['subject']}» با {deficit} دقیقه جبران‌نشده.",
            'priority': 'MEDIUM',
            'evidenceKeys': ['backlogTotal'],
            'actionArea': AREA_FEED,
        })

    if analytics.get('loggedToday') is False:
        recommendations.append({
            'code': 'record-today-log',
            'title': 'ثبت گزارش امروز',
            'description': 'گزارش مطالعهٔ امروز هنوز ثبت نشده است.',
            'priority': 'MEDIUM',
            'evidenceKeys': ['loggedToday'],
            'actionArea': AREA_FEED,
        })

    if analytics.get('planExecution') is None:
        recommendations.append({
            'code': 'publish-current-plan',
            'title': 'انتشار برنامهٔ جاری',
            'description': 'برای روزهای جاری برنامهٔ منتشرشده‌ای وجود ندارد.',
            'priority': 'MEDIUM',
            'evidenceKeys': ['planExecutionPercent'],
            'actionArea': AREA_PLAN,
        })

    return recommendations[:MAX_RECOMMENDATIONS]
