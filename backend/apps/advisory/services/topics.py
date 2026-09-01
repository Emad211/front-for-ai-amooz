"""The write door for per-topic coverage (پوشش مبحث — research wave 2026-08-31).

The topic list grows as rows the student adds per selected subject; each row
carries a status on the NEW → STUDIED → NEEDS_REVIEW → MASTERED ladder. The
one computed touch: moving a topic to ``NEEDS_REVIEW`` without an explicit
``next_review_at`` defaults the review to two days out (the spaced-review
hook the mistake-notebook methodology prescribes), and reaching ``MASTERED``
clears any pending review date — mastered topics leave the queue.

Wave 7 (2026-08-31): a row may also be **linked** to a leaf of the official
syllabus tree via ``syllabus_topic_id``. The link mirrors the tree node's
title into the free-text ``topic`` column (the display source of truth), is
unique per engagement per tree node — double-linking a node is double-counting
the budget — and survives unlinked with its mirrored title intact.
"""

from __future__ import annotations

import datetime

from django.utils import timezone

from ..models import SyllabusTopic, TopicProgress
from . import scope


class TopicError(Exception):
    """Base class — any rule added later must fail as an actionable 400."""


class SubjectNotInSelection(TopicError):
    def __str__(self) -> str:
        return 'درس انتخاب‌شده در فهرست درس‌های فعال شما نیست.'


class TopicNotFound(TopicError):
    def __str__(self) -> str:
        return 'این مبحث پیدا نشد.'


class SyllabusTopicNotFound(TopicError):
    def __str__(self) -> str:
        return 'مبحث انتخاب‌شده در درخت درس‌ها پیدا نشد.'


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


def _resolve_syllabus_topic(syllabus_topic_id):
    """The tree leaf a payload named, or ``None`` for an id that names none.

    ``None`` here means *not found*, not "not sent" — the caller has already
    branched on that distinction. A non-int id resolves to nothing as well:
    the serializer rejects those shapes first, and the door stays safe for
    direct service callers regardless.
    """
    if isinstance(syllabus_topic_id, bool) or not isinstance(syllabus_topic_id, int):
        return None
    return SyllabusTopic.objects.filter(pk=syllabus_topic_id).first()


def _clean_topic(value) -> str:
    return str(value or '').strip()[:200]


def list_topics(engagement):
    return (
        TopicProgress.objects.filter(engagement=engagement)
        .select_related('student_subject__subject', 'syllabus_topic')
    )


def get_topic(engagement, topic_id: int) -> TopicProgress | None:
    return (
        TopicProgress.objects.filter(engagement=engagement, pk=topic_id)
        .select_related('student_subject__subject', 'syllabus_topic')
        .first()
    )


def create_topic(engagement, *, subject_id: int, topic: str = '',
                 status: str = TopicProgress.Status.NEW, next_review_at=None,
                 syllabus_topic_id=None, **_ignored) -> TopicProgress:
    subject_row = _resolve_subject_row(engagement, subject_id)
    if subject_row is None:
        raise SubjectNotInSelection()

    syllabus_topic = None
    if syllabus_topic_id is not None:
        syllabus_topic = _resolve_syllabus_topic(syllabus_topic_id)
        if syllabus_topic is None:
            raise SyllabusTopicNotFound()
        # The tree link is unique per engagement per node, across every subject
        # row: one budget node may appear on a student's list exactly once,
        # whichever subject row it was added under.
        if TopicProgress.objects.filter(
            engagement=engagement, syllabus_topic=syllabus_topic,
        ).exists():
            raise DuplicateTopic()
        # The linked node owns the display title; free text sent alongside is
        # ignored rather than merged.
        topic_clean = syllabus_topic.title
    else:
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
        syllabus_topic=syllabus_topic,
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

    if 'syllabus_topic_id' in patch:
        new_id = patch['syllabus_topic_id']
        if new_id is None:
            # Explicit null = unlink. The free-text title keeps its last
            # written value — unlinking is not an invitation to blank the row.
            updates['syllabus_topic'] = None
        else:
            syllabus_topic = _resolve_syllabus_topic(new_id)
            if syllabus_topic is None:
                raise SyllabusTopicNotFound()
            updates['syllabus_topic'] = syllabus_topic
            # Linking re-mirrors the node's title, overriding a free-text
            # rename sent in the same patch.
            updates['topic'] = syllabus_topic.title

    if 'status' in patch:
        updates['status'] = patch['status']
        if 'next_review_at' not in patch:
            updates['next_review_at'] = _effective_review_date(
                patch['status'], topic_row.next_review_at,
            )

    if 'next_review_at' in patch:
        updates['next_review_at'] = patch['next_review_at']

    if updates:
        # The uniqueness the create door enforces must hold across updates
        # too, on both axes: the free-text title under its (possibly new)
        # subject row, and the tree link per engagement.
        subject_row = updates.get('student_subject', topic_row.student_subject)
        topic_clean = updates.get('topic', topic_row.topic)
        if TopicProgress.objects.filter(
            engagement=engagement,
            student_subject=subject_row,
            topic=topic_clean,
        ).exclude(pk=topic_row.pk).exists():
            raise DuplicateTopic()

        syllabus_topic = updates.get('syllabus_topic', topic_row.syllabus_topic)
        if syllabus_topic is not None and TopicProgress.objects.filter(
            engagement=engagement,
            syllabus_topic=syllabus_topic,
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
