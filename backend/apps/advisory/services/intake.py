"""The write door for the student intake form (restart step 2, گام ۲).

``AdvisoryIntakeProfile`` / ``AdvisoryIntakeClass`` are tenancy-bearing, so —
exactly like ``daily_logs.py`` for the log and ``study_plans.py`` for the plan —
every mutation goes through this one module, never through a view. The view has
already resolved ownership through ``scope.advisor_engagement`` or
``scope.student_active_engagement`` before calling in.

One public pair:

* ``get_or_init_intake(engagement)`` — the read side; a never-saved form reads
  back as the all-empty default profile, not a 404.
* ``replace_intake(engagement, payload, actor)`` — a **set-replace of the whole
  form**, including rebuilding the class rows: whatever is not in the payload
  is gone. The exact Persian validation messages are this module's contract;
  serializers stay shape-only so the wire errors never drift from here.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.db import transaction

from ..models import AdvisoryIntakeClass, AdvisoryIntakeProfile

# The paper form (PDF ص۱) carries 7 class rows; the plan grants headroom to 10.
# A service rule, not a constraint — a DB check cannot count sibling rows.
MAX_INTAKE_CLASSES = 10

GPA_MIN = Decimal('0')
GPA_MAX = Decimal('20')
FREE_DAY_MINUTES_MAX = 1440
WEEKDAY_MIN = 0
WEEKDAY_MAX = 6


class IntakeError(Exception):
    """400-family validation error; ``str(exc)`` is the Persian wire message."""


def _fail(message: str) -> None:
    raise IntakeError(message)


def get_or_init_intake(engagement) -> AdvisoryIntakeProfile:
    """Return the engagement's intake profile, creating an empty one if needed.

    The classes relation comes prefetched so the serializer renders the whole
    payload without an N+1, ordered by the model's ``['order', 'id']``.
    """
    AdvisoryIntakeProfile.objects.get_or_create(engagement=engagement)
    return (
        AdvisoryIntakeProfile.objects.filter(engagement=engagement)
        .prefetch_related('classes')
        .first()
    )


def _clean_gpa(value):
    """``None | number → None | Decimal(2dp)``, or the pinned Persian error."""
    if value is None:
        return None
    try:
        gpa = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        _fail('معدل باید بین ۰ تا ۲۰ باشد.')
    if not (GPA_MIN <= gpa <= GPA_MAX):
        _fail('معدل باید بین ۰ تا ۲۰ باشد.')
    return gpa.quantize(Decimal('0.01'))


def _clean_free_day_minutes(value):
    if value is None:
        return None
    # ``bool`` is an ``int`` subclass in Python; True/False are not minutes.
    if isinstance(value, bool) or not isinstance(value, int):
        _fail('دقایق مطالعهٔ آزاد نامعتبر است.')
    if not (0 <= value <= FREE_DAY_MINUTES_MAX):
        _fail('دقایق مطالعهٔ آزاد نامعتبر است.')
    return value


def _clean_classes(classes) -> list[dict]:
    """Validate one intake payload's class rows into storable dicts.

    Order of checks per row: weekday band, then the end>start rule when both
    times were sent, then the non-negative order guard. The order guard is
    defensive beyond the wire contract: the column is
    ``PositiveSmallIntegerField``, so letting a negative through would surface
    as an IntegrityError 500 instead of a 400.
    """
    if len(classes) > MAX_INTAKE_CLASSES:
        _fail('حداکثر ۱۰ کلاس می‌توانید ثبت کنید.')

    cleaned = []
    for row in classes:
        weekday = row.get('weekday')
        if (
            isinstance(weekday, bool)
            or not isinstance(weekday, int)
            or not (WEEKDAY_MIN <= weekday <= WEEKDAY_MAX)
        ):
            _fail('روز هفته نامعتبر است.')

        start_time = row.get('start_time')
        end_time = row.get('end_time')
        if start_time is not None and end_time is not None and end_time <= start_time:
            _fail('ساعت پایان باید بعد از ساعت شروع باشد.')

        order = row.get('order')
        if order is None:
            order = 0
        if isinstance(order, bool) or not isinstance(order, int) or order < 0:
            _fail('ترتیب کلاس نامعتبر است.')

        cleaned.append({
            'name': row.get('name') or '',
            'teacher': row.get('teacher') or '',
            'weekday': weekday,
            'start_time': start_time,
            'end_time': end_time,
            'order': order,
        })
    return cleaned


def replace_intake(engagement, payload, actor) -> AdvisoryIntakeProfile:
    """Make the stored intake equal exactly what was sent, and return it.

    ``payload`` is the validated serializer data with snake_case keys. Every
    scalar is overwritten — including back to empty/None — because the endpoint
    is a set-replace: an omitted field means «cleared», never «unchanged».
    Class rows are hard-deleted and re-created inside one transaction; the
    timetable describes the student's *current* schedule, so there is no row
    history worth preserving.

    ``actor`` lands on ``updated_by`` on every save, advisor or student alike.
    """
    if not isinstance(payload, dict):
        _fail('بدنهٔ فرم نامعتبر است.')

    cleaned_classes = _clean_classes(payload.get('classes') or [])

    with transaction.atomic():
        profile, _ = AdvisoryIntakeProfile.objects.update_or_create(
            engagement=engagement,
            defaults={
                'school': payload.get('school') or '',
                'city': payload.get('city') or '',
                'last_gpa': _clean_gpa(payload.get('last_gpa')),
                'target_major': payload.get('target_major') or '',
                'target_university': payload.get('target_university') or '',
                'mock_exam_institute': payload.get('mock_exam_institute') or '',
                'free_day_minutes': _clean_free_day_minutes(
                    payload.get('free_day_minutes')
                ),
                'updated_by': actor if getattr(actor, 'pk', None) else None,
            },
        )
        AdvisoryIntakeClass.objects.filter(intake=profile).delete()
        AdvisoryIntakeClass.objects.bulk_create([
            AdvisoryIntakeClass(intake=profile, **row) for row in cleaned_classes
        ])

    return get_or_init_intake(engagement)
