"""S4 — the per-student subject selection: the advisor's picker and the mirror
the student sees.

This is the first table that hangs off an ``AdvisoryEngagement`` rather than a
``User``, so the tests here are really two things at once: a plain CRUD contract
(``PUT`` a set, ``GET`` it back) and the tenancy proof that the CRUD cannot be
addressed except through an engagement the caller owns. The headline test — an
advisor ticks three subjects and the student sees exactly those three — is the
spec's live check written down; everything around it pins the ways that join
could silently open onto the wrong student.

Two properties recur and are worth stating once:

* **404, not 403, for a foreign or unknown engagement.** A 403 would confirm the
  engagement exists and leak that some advisor works with that student. Ownership
  is resolved *before* the ACTIVE check, so a foreigner cannot even learn that the
  engagement is in the wrong state (they get 404, never 409).
* **A removed subject is deactivated, never deleted.** The set-replace toggles
  ``is_active`` so a plan (step 8) pointing at a row never dangles, and re-adding a
  subject next week is the same row with its history intact.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from model_bakery import baker
from rest_framework.test import APIClient

from apps.advisory.models import AdvisoryEngagement, StudentSubject, Subject
from apps.organizations.models import Organization

User = get_user_model()
Status = AdvisoryEngagement.Status
Mode = AdvisoryEngagement.Mode

pytestmark = [pytest.mark.django_db, pytest.mark.api]

MY_SUBJECTS_URL = '/api/advisory/me/subjects/'

# The common student and the common subject share this grade, so a plain
# ``_subject('ریاضی')`` is derivable for a plain ``_student()``. Under the national
# curriculum a subject is assignable only when its ``(grade, major, org)`` matches
# what the *student's own* profile derives — a blank-grade student derives nothing —
# so the fixtures give both a concrete grade rather than relying on the old
# "any global subject is assignable to anyone" rule, which no longer holds.
GRADE = '10'


def _subjects_url(pk: int) -> str:
    """The advisor's per-student picker. ``pk`` is the **engagement** id."""
    return f'/api/advisory/students/{pk}/subjects/'


# ── fixtures ──────────────────────────────────────────────────────────────────

def _auth(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _advisor(username='adv', **kwargs):
    return baker.make(User, username=username, role=User.Role.ADVISOR, **kwargs)


def _student(username='stu', phone='09120000001', *, grade=GRADE, major=None, **kwargs):
    """A student whose profile carries ``grade``/``major`` (defaults: ``GRADE``, none).

    The ``post_save`` signal already made the ``StudentProfile``; this sets the two
    curriculum axes on it, because assignability is now derived from the *student's
    own* (grade, major). Pass ``grade=None`` for the deliberately profile-less case.
    A ``None`` major means "no track declared" — only the general (major-NULL)
    subjects of the grade derive, never a major-specific one.
    """
    user = baker.make(User, username=username, role=User.Role.STUDENT, phone=phone, **kwargs)
    profile = user.studentprofile
    profile.grade = grade
    profile.major = major
    profile.save(update_fields=['grade', 'major'])
    return user


def _engagement(advisor, student, *, status=Status.ACTIVE, **kwargs):
    """A **freelance** engagement in ``status`` (ACTIVE by default).

    Freelance on purpose: no organization membership is needed, so the national
    (``organization=None``) subjects the fixtures create are derivable straight from
    the student's grade — keeping these tests about the S4 join, not org setup.
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
    """A catalog subject at ``GRADE``, general (``major=None``) and national
    (``organization=None``) unless told otherwise — i.e. derivable by default for a
    plain ``_student()``. Pass ``grade=None`` for a dead/legacy row (derives for
    nobody), ``major=`` for a track-specific one, ``organization=`` for a private one.
    """
    return baker.make(
        Subject, name=name, grade=grade, major=major,
        organization=organization, is_active=is_active,
    )


# ── permission matrix ─────────────────────────────────────────────────────────

@pytest.mark.permission
def test_anonymous_is_rejected_on_both_routes():
    anon = APIClient()
    assert anon.get(_subjects_url(1)).status_code == 401
    assert anon.put(_subjects_url(1), {'subjectIds': []}, format='json').status_code == 401
    assert anon.get(MY_SUBJECTS_URL).status_code == 401


@pytest.mark.permission
def test_a_teacher_is_forbidden_on_both_routes(teacher_user):
    """403, not 404: a teacher has no business on either side of advisory.

    Worth stating because ``IsStudentUser`` elsewhere admits teachers as learners;
    advisory uses the strict ``IsStudentRole``/``IsAdvisorUser`` so that habit does
    not leak in.
    """
    client = _auth(teacher_user)
    assert client.get(_subjects_url(1)).status_code == 403
    assert client.put(_subjects_url(1), {'subjectIds': []}, format='json').status_code == 403
    assert client.get(MY_SUBJECTS_URL).status_code == 403


@pytest.mark.permission
def test_a_student_cannot_use_the_advisor_picker(student_user):
    client = _auth(student_user)
    assert client.get(_subjects_url(1)).status_code == 403
    assert client.put(_subjects_url(1), {'subjectIds': []}, format='json').status_code == 403


@pytest.mark.permission
def test_a_platform_admin_does_not_inherit_the_advisor_picker(admin_user):
    """An admin curates the catalog in Django admin; they do not get a caseload."""
    assert _auth(admin_user).get(_subjects_url(1)).status_code == 403


@pytest.mark.permission
def test_an_advisor_cannot_read_the_student_mirror():
    assert _auth(_advisor()).get(MY_SUBJECTS_URL).status_code == 403


# ── the live check: what the advisor picks is what the student sees ───────────

def test_advisor_selection_is_exactly_what_the_student_sees():
    """The spec's live check, as a test.

    Advisor ticks three subjects on their own ACTIVE engagement; the student, on
    the other side of the app, reads back exactly those three.
    """
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    a, b, c = _subject('ریاضی'), _subject('فیزیک'), _subject('شیمی')

    put = _auth(advisor).put(
        _subjects_url(engagement.pk), {'subjectIds': [a.id, b.id, c.id]}, format='json',
    )
    assert put.status_code == 200
    assert {row['subjectId'] for row in put.data} == {a.id, b.id, c.id}

    seen = _auth(student).get(MY_SUBJECTS_URL)
    assert seen.status_code == 200
    assert seen.data['active'] is True
    assert {row['subjectId'] for row in seen.data['subjects']} == {a.id, b.id, c.id}


def test_one_students_selection_never_leaks_into_anothers():
    """The whole point of keying subjects on the engagement, not the user.

    Two students, each with their own advisor and selection; each student's mirror
    shows only their own set. A selection addressed to one engagement must never
    surface on another.
    """
    adv_a, stu_a = _advisor('adv_a'), _student('stu_a', '09120000001')
    adv_b, stu_b = _advisor('adv_b'), _student('stu_b', '09120000002')
    eng_a = _engagement(adv_a, stu_a)
    eng_b = _engagement(adv_b, stu_b)
    only_a, shared, only_b = _subject('اختصاصی الف'), _subject('مشترک'), _subject('اختصاصی ب')

    _auth(adv_a).put(_subjects_url(eng_a.pk), {'subjectIds': [only_a.id, shared.id]}, format='json')
    _auth(adv_b).put(_subjects_url(eng_b.pk), {'subjectIds': [only_b.id, shared.id]}, format='json')

    a_sees = {r['subjectId'] for r in _auth(stu_a).get(MY_SUBJECTS_URL).data['subjects']}
    b_sees = {r['subjectId'] for r in _auth(stu_b).get(MY_SUBJECTS_URL).data['subjects']}
    assert a_sees == {only_a.id, shared.id}
    assert b_sees == {only_b.id, shared.id}


# ── ownership: 404, never 403, for anything not the advisor's ─────────────────

def test_a_foreign_engagement_is_404_on_read():
    owner, student = _advisor('owner'), _student()
    engagement = _engagement(owner, student)
    assert _auth(_advisor('intruder')).get(_subjects_url(engagement.pk)).status_code == 404


def test_a_foreign_engagement_is_404_on_write_and_writes_nothing():
    owner, student = _advisor('owner'), _student()
    engagement = _engagement(owner, student)
    subject = _subject('ریاضی')

    intruder = _advisor('intruder')
    resp = _auth(intruder).put(
        _subjects_url(engagement.pk), {'subjectIds': [subject.id]}, format='json',
    )
    assert resp.status_code == 404
    assert StudentSubject.objects.count() == 0


def test_a_nonexistent_engagement_is_404():
    advisor = _advisor()
    assert _auth(advisor).get(_subjects_url(999_999)).status_code == 404
    assert _auth(advisor).put(
        _subjects_url(999_999), {'subjectIds': []}, format='json',
    ).status_code == 404


def test_a_foreign_engagement_is_404_even_when_it_would_be_409():
    """Ownership is resolved before the ACTIVE check.

    A PENDING engagement belonging to another advisor must answer 404, not 409: a
    foreigner cannot be allowed to learn even that the engagement exists in the
    wrong state.
    """
    owner, student = _advisor('owner'), _student()
    engagement = _engagement(owner, student, status=Status.PENDING)
    resp = _auth(_advisor('intruder')).put(
        _subjects_url(engagement.pk), {'subjectIds': []}, format='json',
    )
    assert resp.status_code == 404


# ── state: the picker writes only for an ACTIVE engagement ────────────────────

@pytest.mark.parametrize('status', [Status.PENDING, Status.REJECTED, Status.ENDED])
def test_writing_to_a_non_active_engagement_is_409(status):
    """A picker for a not-yet-accepted or already-ended engagement would write rows
    nobody can ever read. The advisor owns the row (so it is not 404) but may not
    write it (so it is not 200) — 409 is the honest answer.
    """
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student, status=status)
    subject = _subject('ریاضی')

    resp = _auth(advisor).put(
        _subjects_url(engagement.pk), {'subjectIds': [subject.id]}, format='json',
    )
    assert resp.status_code == 409
    assert StudentSubject.objects.count() == 0


@pytest.mark.parametrize('status', [Status.PENDING, Status.REJECTED, Status.ENDED])
def test_reading_is_allowed_regardless_of_status(status):
    """``GET`` is not gated to ACTIVE, only ``PUT`` is.

    Reading the historical selection of an ended engagement is legitimate — the
    advisor owns it — and the asymmetry with the 409 on write is deliberate.
    """
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student, status=status)
    resp = _auth(advisor).get(_subjects_url(engagement.pk))
    assert resp.status_code == 200
    assert resp.data['selectedSubjectIds'] == []


# ── assignability: the body may only name subjects this advisor may assign ────

def test_a_nonexistent_subject_id_is_400():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    resp = _auth(advisor).put(
        _subjects_url(engagement.pk), {'subjectIds': [999_999]}, format='json',
    )
    assert resp.status_code == 400
    assert StudentSubject.objects.count() == 0


def test_a_deactivated_subject_is_400():
    """A subject hidden from new pickers is not assignable — same 400 as unknown."""
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    retired = _subject('درسِ بازنشسته', is_active=False)
    resp = _auth(advisor).put(
        _subjects_url(engagement.pk), {'subjectIds': [retired.id]}, format='json',
    )
    assert resp.status_code == 400


def test_an_org_private_subject_of_a_foreign_org_is_400():
    """The security-meaningful case: a freelance advisor may not assign another
    organization's private subject, and the 400 does not distinguish it from an
    unknown id — so the existence of that org's private catalog never leaks.
    """
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    private = _subject('درسِ محرمانه', organization=baker.make(Organization, slug='foreign-org'))
    resp = _auth(advisor).put(
        _subjects_url(engagement.pk), {'subjectIds': [private.id]}, format='json',
    )
    assert resp.status_code == 400


def test_one_bad_id_in_the_batch_writes_nothing():
    """Assignability is checked before any write opens the transaction.

    A payload of one valid and one foreign id changes nothing at all — not even the
    valid one — so a client cannot smuggle a write past validation by pairing it
    with junk.
    """
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    good = _subject('ریاضی')

    resp = _auth(advisor).put(
        _subjects_url(engagement.pk), {'subjectIds': [good.id, 999_999]}, format='json',
    )
    assert resp.status_code == 400
    assert StudentSubject.objects.count() == 0


# ── set-replace: deactivate, never delete; re-add reactivates ─────────────────

def test_removing_a_subject_deactivates_the_row_and_readding_reactivates_it():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    a, b, c = _subject('a'), _subject('b'), _subject('c')
    client = _auth(advisor)
    url = _subjects_url(engagement.pk)

    client.put(url, {'subjectIds': [a.id, b.id, c.id]}, format='json')
    assert StudentSubject.objects.filter(engagement=engagement).count() == 3

    # Narrow to {a}: b and c are switched off, not deleted.
    narrowed = client.put(url, {'subjectIds': [a.id]}, format='json')
    assert {row['subjectId'] for row in narrowed.data} == {a.id}
    assert StudentSubject.objects.filter(engagement=engagement).count() == 3
    assert StudentSubject.objects.filter(engagement=engagement, is_active=True).count() == 1
    assert StudentSubject.objects.get(engagement=engagement, subject=b).is_active is False

    # Re-add b: the *same* row flips back on — still three rows total, no duplicate.
    readded = client.put(url, {'subjectIds': [a.id, b.id]}, format='json')
    assert {row['subjectId'] for row in readded.data} == {a.id, b.id}
    assert StudentSubject.objects.filter(engagement=engagement).count() == 3
    assert StudentSubject.objects.get(engagement=engagement, subject=b).is_active is True


def test_an_empty_list_clears_the_selection():
    """The explicit "clear my selection" move: an empty array is legal and empties
    the active set without deleting the history."""
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    a, b = _subject('a'), _subject('b')
    client = _auth(advisor)
    url = _subjects_url(engagement.pk)

    client.put(url, {'subjectIds': [a.id, b.id]}, format='json')
    cleared = client.put(url, {'subjectIds': []}, format='json')
    assert cleared.status_code == 200
    assert cleared.data == []
    assert StudentSubject.objects.filter(engagement=engagement, is_active=True).count() == 0
    assert StudentSubject.objects.filter(engagement=engagement).count() == 2  # history kept

    seen = _auth(student).get(MY_SUBJECTS_URL)
    assert seen.data['active'] is True
    assert seen.data['subjects'] == []


def test_a_duplicate_id_in_the_body_is_collapsed_not_an_error():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    a = _subject('ریاضی')
    resp = _auth(advisor).put(
        _subjects_url(engagement.pk), {'subjectIds': [a.id, a.id, a.id]}, format='json',
    )
    assert resp.status_code == 200
    assert [row['subjectId'] for row in resp.data] == [a.id]
    assert StudentSubject.objects.filter(engagement=engagement, is_active=True).count() == 1


def test_the_student_mirror_hides_deactivated_history():
    """The student sees the *current* set, never the rows a set-replace switched off."""
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    a, b = _subject('a'), _subject('b')
    client = _auth(advisor)
    url = _subjects_url(engagement.pk)

    client.put(url, {'subjectIds': [a.id, b.id]}, format='json')
    client.put(url, {'subjectIds': [a.id]}, format='json')  # b deactivated

    seen = _auth(student).get(MY_SUBJECTS_URL)
    assert {row['subjectId'] for row in seen.data['subjects']} == {a.id}


# ── the student mirror when there is no advisor ───────────────────────────────

def test_a_student_with_no_engagement_gets_a_quiet_200():
    """No advisor is the overwhelmingly common case, so it is a 200 with an empty
    body, never a 404 — the advisory UI is gated on ``active`` being true."""
    resp = _auth(_student()).get(MY_SUBJECTS_URL)
    assert resp.status_code == 200
    assert resp.data == {'active': False, 'subjects': []}


def test_a_pending_invite_does_not_count_as_active():
    """A student who has been invited but has not accepted still has no advisor."""
    advisor, student = _advisor(), _student()
    _engagement(advisor, student, status=Status.PENDING)
    resp = _auth(student).get(MY_SUBJECTS_URL)
    assert resp.data == {'active': False, 'subjects': []}


def test_the_mirror_names_the_advisor_when_active():
    advisor, student = _advisor(first_name='زهرا', last_name='مرادی'), _student()
    _engagement(advisor, student)
    resp = _auth(student).get(MY_SUBJECTS_URL)
    assert resp.data['active'] is True
    assert resp.data['advisorName'] == 'زهرا مرادی'


# ── the student's axes: shown in the picker header, derived from server-side ──

def test_get_exposes_the_students_grade_and_major_in_the_header():
    """The picker header names who the student is; the candidate ``subjects`` are
    derived from these axes server-side, so the client shows them but never filters
    on them (the old client-side grade chip is gone)."""
    advisor, student = _advisor(), _student(grade='11', major='science')
    engagement = _engagement(advisor, student)

    resp = _auth(advisor).get(_subjects_url(engagement.pk))
    assert resp.status_code == 200
    assert resp.data['studentGrade'] == '11'
    assert resp.data['studentGradeLabel'] == 'یازدهم'
    assert resp.data['studentMajor'] == 'science'
    assert resp.data['studentMajorLabel'] == 'علوم تجربی'


def test_get_is_quiet_and_empty_when_the_student_has_no_grade():
    """A student with no grade derives no curriculum, so the header reads ``null``
    and the candidate list is empty — not an error, just nothing to focus yet."""
    advisor, student = _advisor(), _student(grade=None)
    engagement = _engagement(advisor, student)
    _subject('ریاضی')  # a national subject exists, but a grade-less student derives nothing
    resp = _auth(advisor).get(_subjects_url(engagement.pk))
    assert resp.status_code == 200
    assert resp.data['studentGrade'] is None
    assert resp.data['studentGradeLabel'] is None
    assert resp.data['studentMajor'] is None
    assert resp.data['subjects'] == []


def test_get_returns_the_students_derived_curriculum_as_candidates():
    """The advisor GET no longer lists the flat catalog: ``subjects`` is exactly what
    the student's own (grade, major) derives — the HS band's general subjects plus
    the student's own track across 10–12 — and nothing from another major, an
    out-of-band grade, or a dead (grade-NULL) row. Inline round trip of
    ``curriculum_subjects``.
    """
    advisor, student = _advisor(), _student(grade='10', major='math')
    engagement = _engagement(advisor, student)
    general = _subject('ادبیات فارسی')                       # grade 10, major None → derives
    mine = _subject('هندسه', major='math')                    # my track → derives
    band_mine = _subject('حسابان', grade='12', major='math')  # same band, my track → derives too
    _subject('زیست', major='science')                         # another track → hidden
    _subject('ریاضی نهم', grade='09')                         # out-of-band grade → hidden
    _subject('زبان', grade=None)                              # dead row → hidden

    resp = _auth(advisor).get(_subjects_url(engagement.pk))
    assert resp.status_code == 200
    assert {s['id'] for s in resp.data['subjects']} == {general.id, mine.id, band_mine.id}


def test_an_off_grade_or_dead_subject_is_not_in_the_curriculum_and_is_400():
    """The S4→national reversal: grade now *gates*, it is not a filter tag.

    A 9th-grade subject is outside an 11th-grader's HS window (10–12 only), and a
    grade-less (dead/legacy) row is in nobody's — both are rejected, and because
    assignability is checked before any write opens, nothing at all is stored.
    """
    advisor, student = _advisor(), _student(grade='11', major='math')
    engagement = _engagement(advisor, student)
    off_grade = _subject('ریاضی نهم', grade='09')
    dead = _subject('زبان', grade=None)

    for bad in (off_grade, dead):
        resp = _auth(advisor).put(
            _subjects_url(engagement.pk), {'subjectIds': [bad.id]}, format='json',
        )
        assert resp.status_code == 400
    assert StudentSubject.objects.count() == 0


# ── wire shape: camelCase allowlist, no internal keys ─────────────────────────

def test_the_advisor_get_shape_is_an_exact_allowlist():
    advisor, student = _advisor(), _student()
    engagement = _engagement(advisor, student)
    resp = _auth(advisor).get(_subjects_url(engagement.pk))
    assert set(resp.data) == {
        'studentGrade', 'studentGradeLabel', 'studentMajor', 'studentMajorLabel',
        'subjects', 'selectedSubjectIds',
    }
    assert isinstance(resp.data['subjects'], list)
    assert isinstance(resp.data['selectedSubjectIds'], list)


def test_a_selected_subject_row_is_an_exact_camelcase_allowlist():
    """The row a client renders exposes only catalog facts — never the engagement it
    hangs off, nor the ``is_active`` bookkeeping, nor any snake_case leak.

    The row stays five keys even though the catalog now carries ``major``: the
    student mirror is deliberately minimal (decision 5), so ``major`` is an
    advisor-side fact that never reaches the student.
    """
    advisor, student = _advisor(), _student(grade='10', major='math')
    engagement = _engagement(advisor, student)
    general = _subject('ادبیات فارسی')          # grade 10, major=None → shared across majors
    track = _subject('هندسه', major='math')      # grade 10, major-specific — both derivable

    _auth(advisor).put(
        _subjects_url(engagement.pk), {'subjectIds': [general.id, track.id]}, format='json',
    )
    rows = {row['subjectId']: row for row in _auth(student).get(MY_SUBJECTS_URL).data['subjects']}

    for row in rows.values():
        assert set(row) == {'subjectId', 'name', 'grade', 'gradeLabel', 'isGlobal'}

    assert rows[general.id]['grade'] == '10'
    assert rows[general.id]['gradeLabel'] == 'دهم'
    assert rows[general.id]['isGlobal'] is True
    assert rows[track.id]['grade'] == '10'
    assert rows[track.id]['gradeLabel'] == 'دهم'
