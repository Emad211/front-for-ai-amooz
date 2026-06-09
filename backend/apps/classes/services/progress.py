"""Student enrollment + per-unit progress logic.

This is the single source of truth for "how far is a student through a class" and
"how active is a student", replacing the old invite-derived stubs (progress hard
coded to 0, status always 'inactive'). Pure logic — no request/response handling —
per the project convention of keeping services out of views/tasks.

Data model (see apps/classes/models.py):
- ``Enrollment(session, student, joined_at, last_activity_at)`` — the real
  student↔class link plus an activity heartbeat.
- ``StudentUnitProgress(session, student, unit_external_id)`` — one row per
  completed unit, keyed by the unit's stable ``external_id``.

Scores already live in ``ClassSectionQuiz.last_score_0_100`` and
``ClassFinalExam.last_score_0_100``; we only aggregate them here.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from django.db.models import Avg, Count, Max
from django.utils import timezone

from apps.classes.models import (
    ClassCreationSession,
    ClassFinalExam,
    ClassSection,
    ClassSectionQuiz,
    ClassUnit,
    Enrollment,
    StudentUnitProgress,
)

# A student counts as "active" if they did something within this window.
ACTIVE_WINDOW_DAYS = 30


# ---------------------------------------------------------------------------
# Enrollment + activity heartbeat
# ---------------------------------------------------------------------------

def touch_enrollment(*, session: ClassCreationSession, student) -> Enrollment:
    """Ensure an ``Enrollment`` exists for (session, student) and bump activity.

    Idempotent: safe to call on every authenticated student action. Lazily
    enrolls students who joined before the enrollment model existed.
    """
    enrollment, _ = Enrollment.objects.update_or_create(
        session=session,
        student=student,
        defaults={'last_activity_at': timezone.now()},
    )
    return enrollment


def activity_status(last_activity: Optional[datetime]) -> str:
    """'active' if the student acted within ``ACTIVE_WINDOW_DAYS``, else 'inactive'."""
    if last_activity is None:
        return 'inactive'
    return 'active' if last_activity >= timezone.now() - timedelta(days=ACTIVE_WINDOW_DAYS) else 'inactive'


# ---------------------------------------------------------------------------
# Per-unit completion
# ---------------------------------------------------------------------------

def total_units(*, session: ClassCreationSession) -> int:
    return ClassUnit.objects.filter(session=session).count()


def completed_unit_ids(*, session: ClassCreationSession, student) -> set[str]:
    """Set of ``unit_external_id`` the student has completed in this session."""
    return set(
        StudentUnitProgress.objects.filter(session=session, student=student)
        .values_list('unit_external_id', flat=True)
    )


def resolve_unit(*, session: ClassCreationSession, lesson_id: str) -> Optional[ClassUnit]:
    """Resolve a unit from the id the student UI holds (external_id OR DB pk).

    The student content endpoint exposes ``str(unit.id)`` as the lesson id, but
    progress is keyed by the stable ``external_id``; accept either form.
    """
    key = (lesson_id or '').strip()
    if not key:
        return None
    qs = ClassUnit.objects.filter(session=session)
    unit = qs.filter(external_id=key).first()
    if unit is not None:
        return unit
    try:
        pk = int(key)
    except (TypeError, ValueError):
        return None
    return qs.filter(pk=pk).first()


def mark_unit_complete(*, session: ClassCreationSession, student, unit: ClassUnit) -> StudentUnitProgress:
    obj, _ = StudentUnitProgress.objects.get_or_create(
        session=session, student=student, unit_external_id=unit.external_id,
    )
    touch_enrollment(session=session, student=student)
    return obj


def mark_section_units_complete(*, session: ClassCreationSession, student, section: ClassSection) -> None:
    """Mark every unit in a section complete (used when its quiz is passed)."""
    external_ids = list(section.units.values_list('external_id', flat=True))
    if not external_ids:
        return
    existing = set(
        StudentUnitProgress.objects.filter(
            session=session, student=student, unit_external_id__in=external_ids,
        ).values_list('unit_external_id', flat=True)
    )
    to_create = [
        StudentUnitProgress(session=session, student=student, unit_external_id=ext)
        for ext in external_ids
        if ext not in existing
    ]
    if to_create:
        StudentUnitProgress.objects.bulk_create(to_create, ignore_conflicts=True)


# ---------------------------------------------------------------------------
# Course progress percent (used by student + teacher views)
# ---------------------------------------------------------------------------

def lesson_progress_percent(*, session: ClassCreationSession, student) -> int:
    """Content progress: completed units / total units.

    The intuitive "how far through the lessons" measure. Used by the teacher
    rosters and the mark-lesson-complete response. Distinct from
    ``course_progress_percent`` (mastery, quiz/exam based).
    """
    total = total_units(session=session)
    if total <= 0:
        return 0
    done = StudentUnitProgress.objects.filter(session=session, student=student).count()
    # Guard against orphaned progress rows left by a later structure edit.
    done = min(done, total)
    return max(0, min(100, int(round(done / total * 100))))


def course_progress_percent(*, session: ClassCreationSession, student) -> int:
    """Mastery progress for a student in a class session.

    MVP rule (unchanged): each chapter quiz passed counts equally + the final
    exam passed counts equally. This is the student-facing headline progress;
    see ``lesson_progress_percent`` for raw content completion.
    """
    try:
        total_sections = session.sections.count()
    except Exception:
        total_sections = 0

    total_parts = total_sections + 1
    if total_parts <= 0:
        return 0

    passed_sections = (
        ClassSectionQuiz.objects.filter(session=session, student=student, last_passed=True).count()
        if total_sections > 0
        else 0
    )
    passed_final = ClassFinalExam.objects.filter(session=session, student=student, last_passed=True).exists()
    passed_parts = passed_sections + (1 if passed_final else 0)
    return max(0, min(100, int(round(passed_parts / total_parts * 100))))


def course_progress_percent_bulk(*, sessions, student) -> dict[int, int]:
    """Batched :func:`course_progress_percent` for many sessions / one student.

    Identical mastery rule (each chapter quiz passed + the final exam passed
    count equally) but computed with a CONSTANT number of grouped queries (3)
    instead of ~3 *per session*. This is what the student course-list endpoint
    must use — calling the single-session version in a loop is an O(courses)
    N+1 that multiplies under concurrent load.

    Returns ``{session_id: percent}`` for every session id in ``sessions``.
    """
    session_ids = [s.id for s in sessions]
    result: dict[int, int] = {sid: 0 for sid in session_ids}
    if not session_ids:
        return result

    # Chapters per session (1 query).
    section_counts = {
        r['session_id']: r['c']
        for r in (
            ClassSection.objects.filter(session_id__in=session_ids)
            .values('session_id')
            .annotate(c=Count('id'))
        )
    }
    # Chapter quizzes this student has passed, per session (1 query).
    passed_quiz_counts = {
        r['session_id']: r['c']
        for r in (
            ClassSectionQuiz.objects
            .filter(session_id__in=session_ids, student=student, last_passed=True)
            .values('session_id')
            .annotate(c=Count('id'))
        )
    }
    # Sessions whose final exam this student has passed (1 query).
    passed_final_ids = set(
        ClassFinalExam.objects
        .filter(session_id__in=session_ids, student=student, last_passed=True)
        .values_list('session_id', flat=True)
    )

    for sid in session_ids:
        total_sections = section_counts.get(sid, 0)
        total_parts = total_sections + 1  # +1 for the final exam, mirrors single
        passed_sections = passed_quiz_counts.get(sid, 0) if total_sections > 0 else 0
        passed_parts = passed_sections + (1 if sid in passed_final_ids else 0)
        result[sid] = max(0, min(100, int(round(passed_parts / total_parts * 100))))
    return result


# ---------------------------------------------------------------------------
# Teacher roster aggregates (batched — avoids N+1 across many students)
# ---------------------------------------------------------------------------

def _weighted_avg(a_avg, a_n, b_avg, b_n) -> Optional[int]:
    total_n = (a_n or 0) + (b_n or 0)
    if total_n == 0:
        return None
    total = (a_avg or 0) * (a_n or 0) + (b_avg or 0) * (b_n or 0)
    return int(round(total / total_n))


def teacher_roster_stats(*, teacher, user_ids: list[int]) -> dict[int, dict]:
    """Real per-student aggregates across all of ``teacher``'s sessions.

    Returns ``{user_id: {completedLessons, averageScore (int|None),
    lastActivity (datetime|None)}}``. ``totalLessons`` depends on which sessions
    each student is in, so the caller computes it from invite→session data.
    Computed with a handful of grouped queries rather than per-student loops.
    """
    stats: dict[int, dict] = {
        uid: {'completedLessons': 0, 'averageScore': None, 'lastActivity': None}
        for uid in user_ids
    }
    if not user_ids:
        return stats

    for row in (
        StudentUnitProgress.objects
        .filter(student_id__in=user_ids, session__teacher=teacher)
        .values('student_id')
        .annotate(c=Count('id'))
    ):
        stats[row['student_id']]['completedLessons'] = row['c']

    quiz_rows = {
        r['student_id']: (r['avg'], r['n'])
        for r in (
            ClassSectionQuiz.objects
            .filter(student_id__in=user_ids, session__teacher=teacher, last_score_0_100__isnull=False)
            .values('student_id')
            .annotate(avg=Avg('last_score_0_100'), n=Count('id'))
        )
    }
    final_rows = {
        r['student_id']: (r['avg'], r['n'])
        for r in (
            ClassFinalExam.objects
            .filter(student_id__in=user_ids, session__teacher=teacher, last_score_0_100__isnull=False)
            .values('student_id')
            .annotate(avg=Avg('last_score_0_100'), n=Count('id'))
        )
    }
    for uid in user_ids:
        qa, qn = quiz_rows.get(uid, (None, 0))
        fa, fn = final_rows.get(uid, (None, 0))
        stats[uid]['averageScore'] = _weighted_avg(qa, qn, fa, fn)

    for row in (
        Enrollment.objects
        .filter(student_id__in=user_ids, session__teacher=teacher)
        .values('student_id')
        .annotate(m=Max('last_activity_at'))
    ):
        stats[row['student_id']]['lastActivity'] = row['m']

    return stats


def units_per_session(*, teacher) -> dict[int, int]:
    """{session_id: unit_count} for all of the teacher's sessions (one query)."""
    return {
        r['session_id']: r['c']
        for r in (
            ClassUnit.objects.filter(session__teacher=teacher)
            .values('session_id')
            .annotate(c=Count('id'))
        )
    }


def session_roster_stats(*, session: ClassCreationSession, user_ids: list[int]) -> dict[int, dict]:
    """Real per-student stats scoped to a SINGLE session.

    Returns ``{user_id: {completedLessons, totalLessons, progress, averageScore
    (int|None), lastActivity (datetime|None)}}``. Used by the per-class roster.
    """
    total = total_units(session=session)
    stats: dict[int, dict] = {
        uid: {
            'completedLessons': 0,
            'totalLessons': total,
            'progress': 0,
            'averageScore': None,
            'lastActivity': None,
        }
        for uid in user_ids
    }
    if not user_ids:
        return stats

    for row in (
        StudentUnitProgress.objects
        .filter(session=session, student_id__in=user_ids)
        .values('student_id')
        .annotate(c=Count('id'))
    ):
        done = min(row['c'], total) if total else row['c']
        stats[row['student_id']]['completedLessons'] = done
        stats[row['student_id']]['progress'] = (
            max(0, min(100, int(round(done / total * 100)))) if total else 0
        )

    quiz_rows = {
        r['student_id']: (r['avg'], r['n'])
        for r in (
            ClassSectionQuiz.objects
            .filter(session=session, student_id__in=user_ids, last_score_0_100__isnull=False)
            .values('student_id')
            .annotate(avg=Avg('last_score_0_100'), n=Count('id'))
        )
    }
    final_rows = {
        r['student_id']: (r['avg'], r['n'])
        for r in (
            ClassFinalExam.objects
            .filter(session=session, student_id__in=user_ids, last_score_0_100__isnull=False)
            .values('student_id')
            .annotate(avg=Avg('last_score_0_100'), n=Count('id'))
        )
    }
    for uid in user_ids:
        qa, qn = quiz_rows.get(uid, (None, 0))
        fa, fn = final_rows.get(uid, (None, 0))
        stats[uid]['averageScore'] = _weighted_avg(qa, qn, fa, fn)

    for row in (
        Enrollment.objects
        .filter(session=session, student_id__in=user_ids)
        .values('student_id')
        .annotate(m=Max('last_activity_at'))
    ):
        stats[row['student_id']]['lastActivity'] = row['m']

    return stats
