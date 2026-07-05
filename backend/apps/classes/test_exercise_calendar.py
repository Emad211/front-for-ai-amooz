"""E9 — student calendar aggregate: enrolled exercise deadlines + scheduled
exam-preps, phone-scoped, with isCompleted + from/to filtering.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from model_bakery import baker
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.classes.models import (
    ClassCreationSession,
    ClassInvitation,
    ClassExercise,
    StudentExerciseSubmission,
    StudentExamPrepAttempt,
)

pytestmark = [pytest.mark.django_db, pytest.mark.api]

URL = '/api/classes/student/calendar/'
PHONE = '09121234567'


def _auth(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
    return c


def _student(phone=PHONE):
    return baker.make(User, role=User.Role.STUDENT, phone=phone)


def _class_with_deadline(*, invited=True, deadline=None):
    session = baker.make(ClassCreationSession, pipeline_type='class', is_published=True,
                         title='کلاس ریاضی')
    if invited:
        ClassInvitation.objects.create(session=session, phone=PHONE, invite_code='INV')
    ex = baker.make(ClassExercise, session=session, status=ClassExercise.Status.PUBLISHED,
                    title='تمرین ۱', deadline=deadline or (timezone.now() + timedelta(days=2)))
    return session, ex


def _exam_prep(*, invited=True, scheduled=None):
    session = baker.make(ClassCreationSession, pipeline_type='exam_prep', is_published=True,
                         title='آزمون آمادگی', scheduled_at=scheduled or (timezone.now() + timedelta(days=1)))
    if invited:
        ClassInvitation.objects.create(session=session, phone=PHONE, invite_code='INVE')
    return session


class TestCalendar:
    def test_returns_both_kinds_for_enrolled(self):
        _s, ex = _class_with_deadline()
        ep = _exam_prep()
        res = _auth(_student()).get(URL)
        assert res.status_code == 200
        kinds = {e['kind'] for e in res.data}
        assert kinds == {'exercise_deadline', 'exam_prep'}

    def test_excludes_non_enrolled_classes(self):
        _s, mine = _class_with_deadline()
        _s2, theirs = _class_with_deadline(invited=False)  # not invited
        res = _auth(_student()).get(URL)
        ids = {e.get('exerciseId') for e in res.data if e['kind'] == 'exercise_deadline'}
        assert mine.id in ids and theirs.id not in ids

    def test_is_completed_reflects_submission(self):
        _s, ex = _class_with_deadline()
        student = _student()
        baker.make(StudentExerciseSubmission, exercise=ex, student=student,
                   status=StudentExerciseSubmission.Status.SUBMITTED)
        res = _auth(student).get(URL)
        ev = next(e for e in res.data if e['kind'] == 'exercise_deadline')
        assert ev['isCompleted'] is True

    def test_is_completed_false_without_submission(self):
        _s, ex = _class_with_deadline()
        res = _auth(_student()).get(URL)
        ev = next(e for e in res.data if e['kind'] == 'exercise_deadline')
        assert ev['isCompleted'] is False

    def test_exam_prep_is_completed_on_finalized_attempt(self):
        ep = _exam_prep()
        student = _student()
        baker.make(StudentExamPrepAttempt, session=ep, student=student, finalized=True)
        res = _auth(student).get(URL)
        ev = next(e for e in res.data if e['kind'] == 'exam_prep')
        assert ev['isCompleted'] is True

    def test_from_to_filter(self):
        student = _student()
        _s1, near = _class_with_deadline(deadline=timezone.now() + timedelta(days=1))
        _s2, far = _class_with_deadline(deadline=timezone.now() + timedelta(days=30))
        # window that only includes `near`
        frm = (timezone.now()).isoformat()
        to = (timezone.now() + timedelta(days=5)).isoformat()
        res = _auth(student).get(URL, {'from': frm, 'to': to})
        ids = {e.get('exerciseId') for e in res.data if e['kind'] == 'exercise_deadline'}
        assert near.id in ids and far.id not in ids

    def test_no_phone_400(self):
        no_phone = baker.make(User, role=User.Role.STUDENT, phone=None)
        assert _auth(no_phone).get(URL).status_code == 400

    def test_anonymous_401(self):
        assert APIClient().get(URL).status_code in (401, 403)

    def test_exercise_without_deadline_excluded(self):
        session = baker.make(ClassCreationSession, pipeline_type='class', is_published=True)
        ClassInvitation.objects.create(session=session, phone=PHONE, invite_code='INV')
        baker.make(ClassExercise, session=session, status=ClassExercise.Status.PUBLISHED,
                   deadline=None)
        res = _auth(_student()).get(URL)
        assert res.data == []
