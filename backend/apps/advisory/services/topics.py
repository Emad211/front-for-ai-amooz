"""The write door for per-topic coverage (پوشش مبحث — research wave 2026-08-31).

The topic list grows as rows the student adds per selected subject; each row
carries a status on the NEW → STUDIED → NEEDS_REVIEW → MASTERED ladder. The
one computed touch: moving a topic to ``NEEDS_REVIEW`` without an explicit
``next_review_at`` defaults the review to two days out (the spaced-review
hook the mistake-notebook methodology prescribes), and reaching ``MASTERED``
clears any pending review date — mastered topics leave the queue.
"""

from __future__ import annotations

import datetime

from django.utils import timezone

from ..models import TopicProgress
from . import scope


class TopicError(Exception):
    """Base class — any rule added later must fail as an actionable 400."""


class SubjectNotInSelection(TopicError):
    def __str__(self) -> str:
        return 'درس انتخاب‌شده در فهرست درس‌های فعال شما نیست.'


class TopicNotFound(TopicError):
    def __str__(self) -> str:
        return 'این مبحث پیدا نشد.'


class DuplicateTopic(TopicError):
    def __str__(self) -> str:
        return 'این مبحث از قبل در فهرست هست.'


def _resolve_subject_row(engagement, subject_id: int):
    if not isinstance(subject_id, int) or isinstance(subject_id, bool):
        return None
    return (
        scope.student_subjects(engagement)
        .filter(subject_id=subject_id)
        .first()
    )


def _clean_topic(value) -> str:
    return str(value or '').strip()[:200]


def list_topics(engagement):
    return (
        TopicProgress.objects.filter(engagement=engagement)
        .select_related('student_subject__subject')
    )


def get_topic(engagement, topic_id: int) -> TopicProgress | None:
    return (
        TopicProgress.objects.filter(engagement=engagement, pk=topic_id)
        .select_related('student_subject__subject')
        .first()
    )


def create_topic(engagement, *, subject_id: int, topic: str,
                 status: str = TopicProgress.Status.NEW, next_review_at=None,
                 **_ignored) -> TopicProgress:
    subject_row = _resolve_subject_row(engagement, subject_id)
    if subject_row is None:
        raise SubjectNotInSelection()

    topic_clean = _clean_topic(topic)
    if not topic_clean:
        raise TopicError('نام مبحث نمی‌تواند خالی باشد.')
    if TopicProgress.objects.filter(
        engagement=engagement,
        student_subject=subject_row,
        topic=topic_clean,
    ).exists():
        raise DuplicateTopic()

    return TopicProgress.objects.create(
        engagement=engagement,
        student_subject=subject_row,
        topic=topic_clean,
        status=status,
        next_review_at=_effective_review_date(status, next_review_at),
    )


def update_topic(engagement, topic_id: int, *, patch: dict) -> TopicProgress:
    topic_row = get_topic(engagement, topic_id)
    if topic_row is None:
        raise TopicNotFound()

    updates: dict = {}

    if 'subject_id' in patch:
        subject_row = _resolve_subject_row(engagement, patch['subject_id'])
        if subject_row is None:
            raise SubjectNotInSelection()
        updates['student_subject'] = subject_row

    if 'topic' in patch:
        topic_clean = _clean_topic(patch['topic'])
        if not topic_clean:
            raise TopicError('نام مبحث نمی‌تواند خالی باشد.')
        updates['topic'] = topic_clean

    if 'status' in patch:
        updates['status'] = patch['status']
        if 'next_review_at' not in patch:
            updates['next_review_at'] = _effective_review_date(
                patch['status'], topic_row.next_review_at,
            )

    if 'next_review_at' in patch:
        updates['next_review_at'] = patch['next_review_at']

    if updates:
        # The uniqueness the create door enforces must hold across updates too.
        subject_row = updates.get('student_subject', topic_row.student_subject)
        topic_clean = updates.get('topic', topic_row.topic)
        if TopicProgress.objects.filter(
            engagement=engagement,
            student_subject=subject_row,
            topic=topic_clean,
        ).exclude(pk=topic_row.pk).exists():
            raise DuplicateTopic()

        for field, value in updates.items():
            setattr(topic_row, field, value)
        topic_row.save()

    return topic_row


def delete_topic(engagement, topic_id: int) -> None:
    topic_row = get_topic(engagement, topic_id)
    if topic_row is None:
        raise TopicNotFound()
    topic_row.delete()


def _effective_review_date(status: str, explicit):
    """NEEDS_REVIEW defaults to +2 days when no explicit date came; MASTERED
    always clears the queue date. Everything else keeps what the caller sent."""
    if status == TopicProgress.Status.NEEDS_REVIEW:
        if explicit is not None:
            return explicit
        return timezone.localdate() + datetime.timedelta(days=2)
    if status == TopicProgress.Status.MASTERED:
        return None
    return explicit
