"""The write door for the advisor's weekly assessment (restart step 7, گام ۷).

``WeeklyAssessment`` is tenancy-bearing, so every mutation goes through this
module after the view has resolved ownership via ``scope.advisor_engagement``.
The fifteen criteria below are the **single canonical source**: the service
validates against them, and the wire's ``criteria`` list (code + Persian label)
is serialized straight from them, so a client can never disagree with the
validator about what a complete assessment is.

Locked product rule (گام ۷): this is advisor-internal — there is deliberately
no student route for assessments.
"""

from __future__ import annotations

from django.db import transaction

from ..models import WeeklyAssessment
from .calendar import ensure_saturday

# The 15 criteria of «ارزیابی هفتگی تیم مشاوره», in display order. Codes are
# stable JSON keys: renaming one after launch is a data migration; changing a
# Persian label is free. Do not reorder or reword without the owner.
WEEKLY_ASSESSMENT_CRITERIA = [
    ('plan_order', 'نظم و هماهنگی در اجرای برنامه'),
    ('exam_discipline', 'رعایت دقیق آزمون‌ها'),
    ('planning_accuracy', 'دقت در نوشتن برنامه و گزارش‌کار'),
    ('daily_log_discipline', 'ثبت روزانهٔ چکینگ'),
    ('study_hours', 'ساعت مطالعه نسبت به برنامه'),
    ('test_count', 'تست‌زنی نسبت به هدف'),
    ('review_discipline', 'مرور و جبران عقب‌افتادگی‌ها'),
    ('class_attendance', 'حضور در کلاس‌ها'),
    ('school_homework', 'تکالیف مدرسه'),
    ('sleep_routine', 'روتین خواب'),
    ('mood_level', 'سطح روحی و انگیزه'),
    ('focus_quality', 'کیفیت تمرکز در مطالعه'),
    ('stress_management', 'مدیریت استرس'),
    ('screen_time', 'کنترل فضای مجازی و تلویزیون'),
    ('home_environment', 'شرایط محیط منزل'),
]

CRITERIA_BY_CODE = dict(WEEKLY_ASSESSMENT_CRITERIA)

SCORE_MIN = 1
SCORE_MAX = 5


class WeeklyAssessmentError(Exception):
    """400-family validation error; ``str(exc)`` is the Persian wire message."""


def _ensure_week_start(week_start) -> None:
    """Saturday anchor check through the shared ق۴ validator."""
    try:
        ensure_saturday(week_start)
    except ValueError as exc:
        raise WeeklyAssessmentError('تاریخ باید شنبه باشد.') from exc


def validate_scores(scores) -> dict[str, int]:
    """Return a clean ``{code: int}`` with exactly the 15 keys, or raise.

    Three failure shapes, each with its pinned Persian message:

    * not a dict / any of the 15 codes missing → «همۀ ۱۵ معیار…»;
    * a known code whose value is not an int 1..5 → the criterion's label;
    * an unknown code → the raw code stands in where a label would be, since
      an unknown key has no label to name.
    """
    if not isinstance(scores, dict):
        raise WeeklyAssessmentError('همۀ ۱۵ معیار باید امتیاز داشته باشند.')

    missing = [code for code, _ in WEEKLY_ASSESSMENT_CRITERIA if code not in scores]
    if missing:
        raise WeeklyAssessmentError('همۀ ۱۵ معیار باید امتیاز داشته باشند.')

    cleaned: dict[str, int] = {}
    for code, value in scores.items():
        if code not in CRITERIA_BY_CODE:
            # An unknown key has no Persian label to name; the raw code stands
            # in where the label would be.
            raise WeeklyAssessmentError(
                f'امتیاز معیار {code} باید عددی بین ۱ تا ۵ باشد.'
            )
        # ``bool`` is an ``int`` subclass; True/False are not scores.
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not (SCORE_MIN <= value <= SCORE_MAX)
        ):
            raise WeeklyAssessmentError(
                f'امتیاز معیار {CRITERIA_BY_CODE[code]} باید عددی بین ۱ تا ۵ باشد.'
            )
        cleaned[code] = value
    return cleaned


def upsert_weekly_assessment(engagement, week_start, scores, summary, actor):
    """Create or update the single assessment row for ``(engagement, week_start)``.

    Re-saving a week updates in place — the unique constraint makes a second
    row impossible, and ``created_by`` keeps the *first* author even when a
    later save comes from someone else.
    """
    _ensure_week_start(week_start)
    cleaned = validate_scores(scores)

    with transaction.atomic():
        row, created = WeeklyAssessment.objects.get_or_create(
            engagement=engagement,
            week_start=week_start,
            defaults={
                'scores': cleaned,
                'advisor_summary': summary or '',
                'created_by': actor if getattr(actor, 'pk', None) else None,
            },
        )
        if not created:
            row.scores = cleaned
            row.advisor_summary = summary or ''
            row.save(update_fields=['scores', 'advisor_summary', 'updated_at'])
    return row


def list_weekly_assessments(engagement):
    """The engagement's assessments, newest week first (§۴.۲: تاریخ‌ها نزولی)."""
    return (
        WeeklyAssessment.objects.filter(engagement=engagement)
        .order_by('-week_start')
    )


def assessment_average(scores) -> float:
    """Mean of the 15 scores, rounded to one decimal place (the wire's ``average``)."""
    values = [scores[code] for code, _ in WEEKLY_ASSESSMENT_CRITERIA]
    return round(sum(values) / len(values), 1)
