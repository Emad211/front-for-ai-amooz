"""The write door for the student's mistake notebook (دفتر اشتباهات).

Shape follows the canonical Iranian form: six root-cause categories, three
answer statuses (a doubt-right answer is data too) and the fix trio. Rows are
student-owned; the advisor reads them through the engagement join in a later
wave. Every rule below fails as a Persian 400 the student can act on.
"""

from __future__ import annotations

from django.utils import timezone

from ..models import MistakeEntry, MAX_MISTAKE_TEXT_CHARS
from . import scope


class MistakeError(Exception):
    """Base class — any rule added later must fail as an actionable 400."""


class SubjectNotInSelection(MistakeError):
    def __str__(self) -> str:
        return 'درس انتخاب‌شده در فهرست درس‌های فعال شما نیست.'


class MistakeNotFound(MistakeError):
    def __str__(self) -> str:
        return 'این خطا پیدا نشد.'


def _resolve_subject_row(engagement, subject_id: int):
    """The active ``StudentSubject`` row behind a catalog-subject id, or None."""
    if not isinstance(subject_id, int) or isinstance(subject_id, bool):
        return None
    return (
        scope.student_subjects(engagement)
        .filter(subject_id=subject_id)
        .first()
    )


def _clean_text(value, limit: int) -> str:
    return str(value or '').strip()[:limit]


def list_mistakes(engagement):
    return (
        MistakeEntry.objects.filter(engagement=engagement)
        .select_related('student_subject__subject')
    )


def get_mistake(engagement, mistake_id: int) -> MistakeEntry | None:
    return (
        MistakeEntry.objects.filter(engagement=engagement, pk=mistake_id)
        .select_related('student_subject__subject')
        .first()
    )


def create_mistake(engagement, *, subject_id: int, topic: str, status: str,
                   error_type: str, cause: str = '', fix_note: str = '',
                   next_action: str = '', priority: str = MistakeEntry.Priority.MEDIUM,
                   source_ref: str = '', review_date=None, **_ignored) -> MistakeEntry:
    subject_row = _resolve_subject_row(engagement, subject_id)
    if subject_row is None:
        raise SubjectNotInSelection()

    topic_clean = _clean_text(topic, 200)
    if not topic_clean:
        raise MistakeError('مبحث نمی‌تواند خالی باشد.')

    return MistakeEntry.objects.create(
        engagement=engagement,
        student_subject=subject_row,
        topic=topic_clean,
        status=status,
        error_type=error_type,
        cause=_clean_text(cause, MAX_MISTAKE_TEXT_CHARS),
        fix_note=_clean_text(fix_note, MAX_MISTAKE_TEXT_CHARS),
        next_action=_clean_text(next_action, MAX_MISTAKE_TEXT_CHARS),
        priority=priority,
        source_ref=_clean_text(source_ref, 120),
        review_date=review_date,
    )


def update_mistake(engagement, mistake_id: int, *, patch: dict) -> MistakeEntry:
    """Partial update: only the keys present in ``patch`` change.

    ``subjectId`` is the one re-validated key — moving a mistake to another
    subject still has to land on an active selection.
    """
    mistake = get_mistake(engagement, mistake_id)
    if mistake is None:
        raise MistakeNotFound()

    updates: dict = {}

    if 'subject_id' in patch:
        subject_row = _resolve_subject_row(engagement, patch['subject_id'])
        if subject_row is None:
            raise SubjectNotInSelection()
        updates['student_subject'] = subject_row

    text_fields = {
        'topic': 200,
        'cause': MAX_MISTAKE_TEXT_CHARS,
        'fix_note': MAX_MISTAKE_TEXT_CHARS,
        'next_action': MAX_MISTAKE_TEXT_CHARS,
        'source_ref': 120,
    }
    for field, limit in text_fields.items():
        if field in patch:
            value = _clean_text(patch[field], limit)
            if field == 'topic' and not value:
                raise MistakeError('مبحث نمی‌تواند خالی باشد.')
            updates[field] = value

    for field in ('status', 'error_type', 'priority'):
        if field in patch:
            updates[field] = patch[field]
    if 'review_date' in patch:
        updates['review_date'] = patch['review_date']
    if 'is_resolved' in patch:
        resolved = bool(patch['is_resolved'])
        updates['is_resolved'] = resolved
        # Stamped on the first resolve only — re-sending is_resolved=True never
        # rewrites history — and wiped when the student re-opens the mistake.
        if resolved and not mistake.is_resolved:
            updates['resolved_at'] = timezone.now()
        elif not resolved:
            updates['resolved_at'] = None

    if updates:
        for field, value in updates.items():
            setattr(mistake, field, value)
        mistake.save()

    return mistake


def delete_mistake(engagement, mistake_id: int) -> None:
    mistake = get_mistake(engagement, mistake_id)
    if mistake is None:
        raise MistakeNotFound()
    mistake.delete()
