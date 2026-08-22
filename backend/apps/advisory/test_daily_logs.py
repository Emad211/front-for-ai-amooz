"""S5 — the daily study log: the student's write door and its one endpoint.

``save_day`` is a **set-replace of a whole day** and ``PUT /api/advisory/me/study-log/``
is its only route in; this file pins both halves. The service tests hold the
semantics that are invisible from the wire (idempotence, ``created_at`` survival,
reported-but-empty ≠ unreported, hard-delete of omitted items) and the four
exceptions that make up the mandatory negative matrix (owner → date → subjects →
total, all checked before any write opens). The API tests hold the wire contract:
the quiet 200 for "no advisor", the 409 for writing without one, the serializer
bounds, and the strict permission matrix — anonymous is 401, TEACHER and ADVISOR
are both 403, because ``IsStudentRole`` admits nobody else.

One distinction worth stating once, because it looks contradictory and is not:

* saving day D **omitting** a subject hard-deletes that subject's item on day D —
  the student is correcting their own report of their own day;
* minutes recorded on an **earlier** day survive the advisor dropping the subject —
  history is never rewritten by a later plan change.

Both behaviours are asserted below, on opposite sides of that line.
"""

from __future__ import annotations

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from model_bakery import baker
from rest_framework.test import APIClient

from apps.advisory.models import (
    MAX_LOG_MINUTES_PER_DAY,
    MAX_LOG_MINUTES_PER_ITEM,
    MAX_LOG_NOTE_CHARS,
    MOOD_MAX,
    MOOD_MIN,
    AdvisoryEngagement,
    DailyLog,
    DailyLogItem,
    StudentSubject,
    Subject,
)
from apps.advisory.services import daily_logs as log_service

User = get_user_model()
Status = AdvisoryEngagement.Status
Mode = AdvisoryEngagement.Mode

pytestmark = [pytest.mark.django_db, pytest.mark.api]

STUDY_LOG_URL = '/api/advisory/me/study-log/'

GRADE = '10'


def _iso(day: datetime.date) -> str:
    return day.isoformat()


# ── fixtures ──────────────────────────────────────────────────────────────────

def _auth(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _advisor(username='adv', **kwargs):
    return baker.make(User, username=username, role=User.Role.ADVISOR, **kwargs)


def _student(username='stu', phone='09120000001', *, grade=GRADE, major=None, **kwargs):
    """A student whose profile carries ``grade``/``major`` (defaults: ``GRADE``, none).

    Mirrors the S4 sibling builder. The daily-log write rule keys on active
    ``StudentSubject`` rows rather than curriculum derivation, so the axes are
    set for consistency, not out of necessity.
    """
    user = baker.make(User, username=username, role=User.Role.STUDENT, phone=phone, **kwargs)
    profile = user.studentprofile
    profile.grade = grade
    profile.major = major
    profile.save(update_fields=['grade', 'major'])
    return user


def _engagement(advisor, student, *, status=Status.ACTIVE, **kwargs):
    """A **freelance** engagement in ``status`` (ACTIVE by default), started today.

    Pass ``started_on=`` to shift the C3 window backwards for the out-of-window
    tests; ``log_date_window`` reads exactly this field.
    """
    defaults = {
        'invited_phone': student.phone or '',
        'mode': Mode.FREELANCE,
        'organization': None,
        'status': status,
    }
    if status == Status.ACTIVE:
        defaults['started_on'] = timezone.localdate()
    defaults.update(kwargs)
    return AdvisoryEngagement.objects.create(advisor=advisor, student=student, **defaults)


def _subject(name, *, grade=GRADE, major=None, organization=None, is_active=True):
    """A catalog subject at ``GRADE``, general and national unless told otherwise."""
    return baker.make(
        Subject, name=name, grade=grade, major=major,
        organization=organization, is_active=is_active,
    )


def _selection(engagement, *subjects):
    """Active ``StudentSubject`` rows — the S4 state a log hangs off.

    Created directly instead of through the advisor picker endpoint: this file is
    about the student's write door, not S4's API, and these rows are byte-for-byte
    what ``set_engagement_subjects`` would have left behind.
    """
    return [
        baker.make(StudentSubject, engagement=engagement, subject=s, is_active=True)
        for s in subjects
    ]


def _save(engagement, log_date, items=(), *, mood=None, note='', student):
    """Call the write door with ``(subject_id, minutes)`` pairs as ``items``."""
    return log_service.save_day(
        engagement,
        log_date,
        mood=mood,
        note=note,
        items=[{'subject_id': sid, 'minutes': m} for sid, m in items],
        student=student,
    )


def _flat_errors(data) -> list[str]:
    """Every leaf message of a DRF error body, however deeply it is nested."""
    if isinstance(data, dict):
        return [msg for value in data.values() for msg in _flat_errors(value)]
    if isinstance(data, list):
        return [msg for value in data for msg in _flat_errors(value)]
    return [str(data)]


# ── service: the happy path, idempotence, and the shape of the return ────────

def test_save_day_creates_the_log_and_returns_the_scope_shape():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    math, physics = _subject('ریاضی'), _subject('فیزیک')
    _selection(engagement, math, physics)
    today = timezone.localdate()

    log = _save(
        engagement, today,
        [(math.id, 45), (physics.id, 30)],
        mood=4, note='تمرین فصل دو', student=student,
    )

    assert DailyLog.objects.count() == 1
    assert DailyLogItem.objects.count() == 2
    assert log.engagement_id == engagement.pk
    assert log.log_date == today
    assert log.mood == 4
    assert log.note == 'تمرین فصل دو'
    stored = {i.student_subject.subject_id: i.actual_minutes for i in log.items.all()}
    assert stored == {math.id: 45, physics.id: 30}
    # Scope-shaped on purpose: save_day re-reads through scope so GET and PUT
    # serialize one canonical object — items arrive prefetched, not lazy.
    assert 'items' in getattr(log, '_prefetched_objects_cache', {})


def test_saving_the_same_day_twice_is_idempotent_and_preserves_item_created_at():
    """Send the same day twice, get the same day — and the item keeps its birth.

    Items are upserted (``update_or_create``), not wiped and re-made, so a student
    fixing a typo does not silently reset when the row was first recorded.
    """
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    math = _subject('ریاضی')
    _selection(engagement, math)
    today = timezone.localdate()

    first = _save(engagement, today, [(math.id, 45)], mood=3, student=student)
    item = DailyLogItem.objects.get(log=first)
    created_at = item.created_at

    second = _save(engagement, today, [(math.id, 45)], mood=3, student=student)

    assert second.pk == first.pk
    assert DailyLog.objects.count() == 1
    assert DailyLogItem.objects.count() == 1
    reloaded = DailyLogItem.objects.get(pk=item.pk)
    assert reloaded.created_at == created_at
    assert reloaded.actual_minutes == 45


def test_zero_and_negative_minutes_are_dropped_never_stored():
    """Zero is how the form says «I did not study this» — it stores nothing.

    The DB check would reject a zero-minute row anyway; the door drops it before
    the transaction ever opens so the day still counts as reported-but-empty.
    """
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    math, physics = _subject('ریاضی'), _subject('فیزیک')
    _selection(engagement, math, physics)

    log = _save(engagement, timezone.localdate(), [(math.id, 0), (physics.id, -15)], student=student)

    assert DailyLog.objects.count() == 1  # the report itself exists…
    assert log.items.count() == 0         # …but no minute rows do


def test_a_subject_left_out_of_a_later_save_is_hard_deleted():
    """Set-replace: what is not in the body is not in the day.

    Deliberately the opposite of the selection door's deactivate-never-delete —
    here the student corrects their own report, and there is nothing to preserve.
    (Cross-day history preservation is a different test below.)
    """
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    math, physics = _subject('a'), _subject('b')
    _selection(engagement, math, physics)
    today = timezone.localdate()

    _save(engagement, today, [(math.id, 45), (physics.id, 30)], student=student)
    saved = _save(engagement, today, [(math.id, 45)], student=student)

    assert DailyLogItem.objects.count() == 1
    assert [i.student_subject.subject_id for i in saved.items.all()] == [math.id]


def test_an_empty_items_list_still_records_the_reported_but_empty_day():
    """«I reported, and it was nothing» is a different fact from no report at all.

    The ``DailyLog`` row is created or updated, never deleted, so the S8 metric
    can tell a zero day apart from an unreported one.
    """
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)

    log = _save(engagement, timezone.localdate(), [], mood=2, student=student)

    assert DailyLog.objects.filter(engagement=engagement).count() == 1
    assert log.items.count() == 0


def test_mood_and_note_are_always_overwritten_including_back_to_empty():
    """The body is the whole day: an omitted mood means «cleared», not «unchanged»."""
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    math = _subject('ریاضی')
    _selection(engagement, math)
    today = timezone.localdate()

    _save(engagement, today, [(math.id, 30)], mood=5, note='حال خوب', student=student)
    cleared = _save(engagement, today, [(math.id, 30)], mood=None, note='', student=student)
    assert cleared.mood is None
    assert cleared.note == ''

    rewritten = _save(engagement, today, [(math.id, 30)], mood=2, note='خسته بودم', student=student)
    assert rewritten.mood == 2
    assert rewritten.note == 'خسته بودم'


# ── service: the negative matrix, all before any write ────────────────────────

def test_a_mismatched_student_kwarg_raises_not_the_log_owner():
    """D3 at the store: only the engagement's own student may write its log.

    Unreachable through the API (the view resolves the engagement *from* the
    caller); tested here because a rule upheld only by an absent endpoint is one
    refactor away from being untrue.
    """
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    math = _subject('ریاضی')
    _selection(engagement, math)

    with pytest.raises(log_service.NotTheLogOwner):
        _save(engagement, timezone.localdate(), [(math.id, 30)], student=advisor)

    assert DailyLog.objects.count() == 0
    assert DailyLogItem.objects.count() == 0


def test_dates_outside_the_window_raise_log_date_out_of_window():
    """C3 both ways: tomorrow is a forecast, before ``started_on`` is pre-hire.

    Both bounds come from ``scope.log_date_window``; the exception carries them so
    a caller can explain the window without recomputing it.
    """
    advisor, student = _advisor(), _student()
    started_on = timezone.localdate() - datetime.timedelta(days=5)
    engagement = _engagement(advisor, student, started_on=started_on)
    math = _subject('ریاضی')
    _selection(engagement, math)

    tomorrow = timezone.localdate() + datetime.timedelta(days=1)
    before_start = started_on - datetime.timedelta(days=1)
    for bad in (tomorrow, before_start):
        with pytest.raises(log_service.LogDateOutOfWindow) as excinfo:
            _save(engagement, bad, [(math.id, 30)], student=student)
        assert excinfo.value.log_date == bad
        assert excinfo.value.earliest == started_on
        assert excinfo.value.latest == timezone.localdate()

    assert DailyLog.objects.count() == 0


def test_an_unselected_subject_id_raises_subject_not_in_selection():
    """An id that does not exist folds into the same 400 as one not picked —
    neither is «a subject you may report minutes for», and telling them apart
    would leak the shape of other students' selections."""
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    math = _subject('ریاضی')
    _selection(engagement, math)

    with pytest.raises(log_service.SubjectNotInSelection) as excinfo:
        _save(engagement, timezone.localdate(), [(999_999, 30)], student=student)

    assert excinfo.value.subject_ids == [999_999]
    assert DailyLog.objects.count() == 0


def test_a_dropped_subject_rejects_new_minutes_but_keeps_recorded_history():
    """The asymmetry the model docstring warns about, pinned from both sides.

    After the advisor deactivates a selection, new minutes for it are rejected —
    but yesterday's recorded minutes survive untouched, because the read path
    filters by neither ``is_active`` nor current selection. History is never
    rewritten by a plan change.
    """
    advisor, student = _advisor(), _student()
    started_on = timezone.localdate() - datetime.timedelta(days=5)
    engagement = _engagement(advisor, student, started_on=started_on)
    kept, dropped = _subject('a'), _subject('b')
    _selection(engagement, kept, dropped)
    yesterday = timezone.localdate() - datetime.timedelta(days=1)
    today = timezone.localdate()

    _save(engagement, yesterday, [(kept.id, 30), (dropped.id, 40)], student=student)

    # The advisor drops b from the selection (S4: deactivate, never delete).
    StudentSubject.objects.filter(engagement=engagement, subject=dropped).update(is_active=False)

    # New minutes for the dropped subject are refused — and change nothing.
    with pytest.raises(log_service.SubjectNotInSelection) as excinfo:
        _save(engagement, today, [(kept.id, 25), (dropped.id, 10)], student=student)
    assert excinfo.value.subject_ids == [dropped.id]
    assert not DailyLog.objects.filter(log_date=today).exists()

    # Saving today without the dropped subject succeeds…
    saved = _save(engagement, today, [(kept.id, 25)], student=student)
    assert [(i.student_subject.subject_id, i.actual_minutes) for i in saved.items.all()] == [
        (kept.id, 25),
    ]

    # …and yesterday's minutes for the dropped subject are still there.
    old = DailyLog.objects.get(engagement=engagement, log_date=yesterday)
    assert old.items.get(student_subject__subject=dropped).actual_minutes == 40


def test_a_total_over_one_day_raises_daily_total_too_large_and_writes_nothing():
    """1440 minutes exist per day; the sum across subjects may not exceed them.

    A ``CheckConstraint`` cannot sum sibling rows, so this lives in the door —
    checked before the transaction, so an over-long day writes nothing at all.
    Exactly 1440 is legal.
    """
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    math, physics = _subject('a'), _subject('b')
    _selection(engagement, math, physics)
    today = timezone.localdate()

    with pytest.raises(log_service.DailyTotalTooLarge) as excinfo:
        _save(engagement, today, [(math.id, 800), (physics.id, 700)], student=student)
    assert excinfo.value.total == 1500
    assert excinfo.value.maximum == MAX_LOG_MINUTES_PER_DAY
    assert DailyLog.objects.count() == 0

    exact = _save(engagement, today, [(math.id, 720), (physics.id, 720)], student=student)
    assert sum(i.actual_minutes for i in exact.items.all()) == 1440


# ── API: GET ──────────────────────────────────────────────────────────────────

def test_get_without_an_engagement_is_a_quiet_200_with_the_full_key_set():
    """No advisor is the ordinary case, not an error — and the payload carries the
    whole key set so the client needs no special case beyond reading ``active``."""
    resp = _auth(_student()).get(STUDY_LOG_URL)

    assert resp.status_code == 200
    assert resp.data == {
        'active': False,
        'date': timezone.localdate(),
        'minDate': None,
        'maxDate': None,
        'subjects': [],
        'log': None,
    }


def test_get_defaults_to_today_and_honours_an_explicit_date():
    advisor, student = _advisor(), _student()
    started_on = timezone.localdate() - datetime.timedelta(days=3)
    _engagement(advisor, student, started_on=started_on)

    default = _auth(student).get(STUDY_LOG_URL)
    assert default.status_code == 200
    assert default.data['active'] is True
    assert default.data['date'] == timezone.localdate()
    assert default.data['minDate'] == started_on
    assert default.data['maxDate'] == timezone.localdate()

    explicit = _auth(student).get(STUDY_LOG_URL, {'date': _iso(started_on)})
    assert explicit.status_code == 200
    assert explicit.data['date'] == started_on
    assert explicit.data['log'] is None  # unreported days answer null, not 404


@pytest.mark.parametrize('raw', ['2026-13-45', 'yesterday'])
def test_get_rejects_malformed_dates_with_400(raw):
    """Both failure modes of ``parse_date`` land in the same 400.

    A well-formed impossibility ('2026-13-45') makes ``parse_date`` *raise*
    ValueError; a non-date word ('yesterday') makes it return None. The view
    catches both into one answer, so a typo can never become a 500 on a read.
    """
    resp = _auth(_student()).get(STUDY_LOG_URL, {'date': raw})
    assert resp.status_code == 400
    assert resp.data['detail'] == 'تاریخ باید به شکل YYYY-MM-DD باشد.'


def test_get_rejects_an_out_of_window_date_with_400():
    """Strict on purpose: happily answering ``log: null`` for an unwritable date
    would invite a form that submits and then fails."""
    advisor, student = _advisor(), _student()
    started_on = timezone.localdate() - datetime.timedelta(days=5)
    _engagement(advisor, student, started_on=started_on)

    before_start = started_on - datetime.timedelta(days=1)
    resp = _auth(student).get(STUDY_LOG_URL, {'date': _iso(before_start)})
    assert resp.status_code == 400
    assert resp.data['detail'] == 'این تاریخ بیرون از بازه‌ی مجاز است.'

    tomorrow = timezone.localdate() + datetime.timedelta(days=1)
    resp = _auth(student).get(STUDY_LOG_URL, {'date': _iso(tomorrow)})
    assert resp.status_code == 400


# ── API: PUT ──────────────────────────────────────────────────────────────────

def test_put_without_an_engagement_is_409_with_the_persian_detail():
    """Reads stay quiet (200, ``active: false``); writes refuse plainly (409):
    there is no engagement for the row to hang off."""
    resp = _auth(_student()).put(
        STUDY_LOG_URL,
        {'date': _iso(timezone.localdate()), 'items': []},
        format='json',
    )
    assert resp.status_code == 409
    assert resp.data['detail'] == 'برای ثبت گزارش روزانه باید مشاور فعال داشته باشید.'


def test_put_happy_path_persists_and_get_shows_it():
    """Step 5's live check, written down: submit → refresh → it stays.

    PUT answers with the same shape GET answers with, off the *stored* row — so a
    successful save can never paint a screen a refresh then contradicts.
    """
    advisor, student = _advisor(first_name='زهرا', last_name='مرادی'), _student()
    engagement = _engagement(advisor, student)
    math = _subject('ریاضی')
    _selection(engagement, math)
    today = timezone.localdate()

    put = _auth(student).put(
        STUDY_LOG_URL,
        {
            'date': _iso(today),
            'mood': 4,
            'note': 'تمرین فصل دو',
            'items': [{'subjectId': math.id, 'minutes': 45}],
        },
        format='json',
    )
    assert put.status_code == 200
    assert put.data['active'] is True
    assert put.data['advisorName'] == 'زهرا مرادی'
    assert put.data['date'] == today
    assert put.data['minDate'] == today
    assert put.data['maxDate'] == today
    assert put.data['subjects'][0]['subjectId'] == math.id
    assert put.data['log']['mood'] == 4
    assert put.data['log']['note'] == 'تمرین فصل دو'
    assert put.data['log']['totalMinutes'] == 45

    # Refresh: the same values come back through the read path.
    seen = _auth(student).get(STUDY_LOG_URL, {'date': _iso(today)})
    assert seen.status_code == 200
    assert seen.data['log']['mood'] == 4
    assert seen.data['log']['totalMinutes'] == 45
    assert seen.data['log']['items'] == [{
        'subjectId': math.id,
        'name': 'ریاضی',
        'minutes': 45,
        'isSelected': True,
    }]


def test_put_rejects_duplicate_subject_ids_with_400():
    """Two entries for one subject carry two different minute counts and there is
    no honest way to pick one — so it is a 400 the student can act on."""
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    math = _subject('ریاضی')
    _selection(engagement, math)

    resp = _auth(student).put(
        STUDY_LOG_URL,
        {
            'date': _iso(timezone.localdate()),
            'items': [
                {'subjectId': math.id, 'minutes': 30},
                {'subjectId': math.id, 'minutes': 60},
            ],
        },
        format='json',
    )
    assert resp.status_code == 400
    assert 'برای هر درس فقط یک ردیف بفرستید.' in _flat_errors(resp.data)
    assert DailyLog.objects.count() == 0


@pytest.mark.parametrize('mutation', [
    'minutes_over_cap',
    'mood_too_low',
    'mood_too_high',
    'note_too_long',
])
def test_put_rejects_out_of_bounds_fields(mutation):
    """Serializer bounds read the same constants the columns are declared with,
    so an over-long field is a 400 and never an IntegrityError 500."""
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    math = _subject('ریاضی')
    _selection(engagement, math)

    body = {
        'date': _iso(timezone.localdate()),
        'mood': 3,
        'note': 'یادداشت',
        'items': [{'subjectId': math.id, 'minutes': 30}],
    }
    if mutation == 'minutes_over_cap':
        body['items'][0]['minutes'] = MAX_LOG_MINUTES_PER_ITEM + 1
    elif mutation == 'mood_too_low':
        body['mood'] = MOOD_MIN - 1
    elif mutation == 'mood_too_high':
        body['mood'] = MOOD_MAX + 1
    elif mutation == 'note_too_long':
        body['note'] = 'x' * (MAX_LOG_NOTE_CHARS + 1)

    resp = _auth(student).put(STUDY_LOG_URL, body, format='json')
    assert resp.status_code == 400
    assert DailyLog.objects.count() == 0


# ── API: the permission matrix ────────────────────────────────────────────────

@pytest.mark.permission
def test_anonymous_is_rejected_on_both_verbs():
    anon = APIClient()
    assert anon.get(STUDY_LOG_URL).status_code == 401
    assert anon.put(STUDY_LOG_URL, {}, format='json').status_code == 401


@pytest.mark.permission
def test_a_teacher_is_forbidden_on_both_verbs(teacher_user):
    """403, not 404: ``IsStudentRole`` is strict — it does not admit teachers as
    learners the way ``apps.classes.permissions.IsStudentUser`` does."""
    client = _auth(teacher_user)
    assert client.get(STUDY_LOG_URL).status_code == 403
    assert client.put(STUDY_LOG_URL, {}, format='json').status_code == 403


@pytest.mark.permission
def test_an_advisor_is_forbidden_on_both_verbs():
    """D3 on the wire: the advisor reads elsewhere; here they cannot even in.
    There is no endpoint by which an advisor writes a log, and none may open."""
    client = _auth(_advisor())
    assert client.get(STUDY_LOG_URL).status_code == 403
    assert client.put(STUDY_LOG_URL, {}, format='json').status_code == 403


@pytest.mark.permission
def test_writing_another_students_engagement_is_refused_by_the_store():
    """The D3 guard behind the API: even calling the service directly with another
    student's engagement and the wrong ``student`` kwarg raises — the store does
    not trust its caller to have resolved ownership."""
    mine_advisor, my_student = _advisor('adv_mine'), _student('stu_mine', '09120000001')
    other_advisor, other_student = _advisor('adv_other'), _student('stu_other', '09120000002')
    my_engagement = _engagement(mine_advisor, my_student)
    foreign_engagement = _engagement(other_advisor, other_student)
    math = _subject('ریاضی')
    _selection(foreign_engagement, math)

    with pytest.raises(log_service.NotTheLogOwner):
        _save(
            foreign_engagement, timezone.localdate(), [(math.id, 30)],
            student=my_student,
        )

    assert DailyLog.objects.count() == 0
    assert not DailyLog.objects.filter(engagement=my_engagement).exists()
