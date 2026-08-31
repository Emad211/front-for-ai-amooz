"""The write door for the student's stated study goal (research wave 2026-08-31).

``AdvisoryGoal`` is tenancy-bearing like every advisory table; the door exists
to keep the Persian validation messages in one place and to keep views free of
model writes. One row per engagement, upserted wholesale.
"""

from __future__ import annotations

from django.db import transaction

from ..models import AdvisoryGoal, MAX_GOAL_TEXT_CHARS


class GoalError(Exception):
    """Base class — every rule the door adds later fails as an actionable 400."""


class EmptyGoalTitle(GoalError):
    def __str__(self) -> str:
        return 'متن هدف نمی‌تواند خالی باشد.'


def get_goal(engagement) -> AdvisoryGoal | None:
    return AdvisoryGoal.objects.filter(engagement=engagement).first()


def upsert_goal(engagement, *, target_title: str, target_rank: str = '',
                current_rank: str = '', note: str = '', updated_by=None,
                **_ignored) -> AdvisoryGoal:
    """Make the engagement's single goal row equal exactly what was sent.

    ``updated_by`` is recorded, never branched on — both the student and the
    advisor may refine the destination in this wave.
    """
    title = (target_title or '').strip()
    if not title:
        raise EmptyGoalTitle()
    if len(title) > MAX_GOAL_TEXT_CHARS:
        raise GoalError(f'متن هدف حداکثر {MAX_GOAL_TEXT_CHARS} نویسه است.')

    with transaction.atomic():
        goal, created = AdvisoryGoal.objects.get_or_create(
            engagement=engagement,
            defaults={
                'target_title': title,
                'target_rank': (target_rank or '')[:60],
                'current_rank': (current_rank or '')[:60],
                'note': note or '',
                'updated_by': updated_by,
            },
        )
        if not created:
            goal.target_title = title
            goal.target_rank = (target_rank or '')[:60]
            goal.current_rank = (current_rank or '')[:60]
            goal.note = note or ''
            goal.updated_by = updated_by
            goal.save()

    return goal
