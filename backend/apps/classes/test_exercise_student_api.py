"""E5 — Exercise Hub student API: phone-scoping + the reference-answer LEAK guard
+ submit/deadline/duplicate rules + the finished-answers reveal browse.

security-auditor lens: reference answers must NEVER appear in a student GET before
the reveal condition (deadline passed, or no-deadline + own GRADED).
"""
from __future__ import annotations

import io
import json
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
    ClassExerciseQuestion,
    ClassExerciseSection,
    StudentExerciseSubmission,
)

pytestmark = [pytest.mark.django_db, pytest.mark.api]

Status = ClassExercise.Status
SubStatus = StudentExerciseSubmission.Status
PHONE = '09121234567'
REF = 'پاسخ محرمانهٔ مرجع'


def _auth(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
    return c


def _student(phone=PHONE):
    return baker.make(User, role=User.Role.STUDENT, phone=phone)


def _published_exercise(*, invited_phone=PHONE, deadline=None, allow_late=False, status=Status.PUBLISHED):
    session = baker.make(ClassCreationSession, pipeline_type='class', is_published=True)
    if invited_phone:
        ClassInvitation.objects.create(session=session, phone=invited_phone, invite_code='INV')
    ex = baker.make(ClassExercise, session=session, status=status,
                    deadline=deadline, allow_late=allow_late)
    sec = baker.make(ClassExerciseSection, exercise=ex, order=0)
    baker.make(ClassExerciseQuestion, section=sec, order=0,
               question_markdown='سؤال؟', reference_answer_markdown=REF)
    return session, ex


def _url(session_id, exercise_id, suffix=''):
    return f'/api/classes/student/courses/{session_id}/exercises/{exercise_id}/{suffix}'


class TestPhoneScoping:
    def test_uninvited_student_gets_404(self):
        session, ex = _published_exercise(invited_phone=None)
        assert _auth(_student()).get(_url(session.id, ex.id)).status_code == 404

    def test_no_phone_gets_400(self):
        session, ex = _published_exercise()
        no_phone = baker.make(User, role=User.Role.STUDENT, phone=None)
        assert _auth(no_phone).get(_url(session.id, ex.id)).status_code == 400

    def test_anonymous_gets_401(self):
        session, ex = _published_exercise()
        assert APIClient().get(_url(session.id, ex.id)).status_code in (401, 403)

    def test_unpublished_exercise_hidden(self):
        session, ex = _published_exercise(status=Status.DRAFT)
        assert _auth(_student()).get(_url(session.id, ex.id)).status_code == 404

    def test_invited_student_sees_it(self):
        session, ex = _published_exercise()
        assert _auth(_student()).get(_url(session.id, ex.id)).status_code == 200


class TestReferenceAnswerLeakGuard:
    def test_detail_never_leaks_reference_answer(self):
        """The solving view must never carry the reference answer, even after the
        deadline (solving page is not the reveal surface)."""
        session, ex = _published_exercise(deadline=timezone.now() - timedelta(days=1))
        res = _auth(_student()).get(_url(session.id, ex.id))
        assert res.status_code == 200
        assert REF not in json.dumps(res.data, ensure_ascii=False)

    def test_list_never_leaks_reference_answer(self):
        session, ex = _published_exercise()
        res = _auth(_student()).get(f'/api/classes/student/courses/{session.id}/exercises/')
        assert res.status_code == 200
        assert REF not in json.dumps(res.data, ensure_ascii=False)

    def test_result_hides_reference_answer_before_deadline(self):
        """Graded, but the deadline has NOT passed -> reference answer withheld."""
        session, ex = _published_exercise(deadline=timezone.now() + timedelta(days=1))
        student = _student()
        baker.make(StudentExerciseSubmission, exercise=ex, student=student,
                   status=SubStatus.GRADED, result={'per_question': []})
        res = _auth(student).get(_url(session.id, ex.id, 'result/'))
        assert res.status_code == 200
        assert res.data['answersRevealed'] is False
        assert REF not in json.dumps(res.data, ensure_ascii=False)

    def test_result_reveals_reference_answer_after_deadline(self):
        session, ex = _published_exercise(deadline=timezone.now() - timedelta(minutes=1))
        student = _student()
        baker.make(StudentExerciseSubmission, exercise=ex, student=student,
                   status=SubStatus.GRADED, result={'per_question': []})
        res = _auth(student).get(_url(session.id, ex.id, 'result/'))
        assert res.status_code == 200
        assert res.data['answersRevealed'] is True
        assert REF in json.dumps(res.data, ensure_ascii=False)

    def test_no_deadline_reveals_on_own_graded(self):
        session, ex = _published_exercise(deadline=None)
        student = _student()
        baker.make(StudentExerciseSubmission, exercise=ex, student=student,
                   status=SubStatus.GRADED, result={'per_question': []})
        res = _auth(student).get(_url(session.id, ex.id, 'result/'))
        assert res.data['answersRevealed'] is True

    def test_result_passthrough_strips_reference_before_reveal(self):
        """Defense-in-depth (security-auditor E5 Low-1): even if a future grader
        writes a reference answer into result['per_question'], it must be stripped
        from the student's response while reveal is closed."""
        session, ex = _published_exercise(deadline=timezone.now() + timedelta(days=1))
        student = _student()
        baker.make(
            StudentExerciseSubmission, exercise=ex, student=student,
            status=SubStatus.GRADED,
            result={'per_question': [{
                'question_id': 'q1', 'llm_score': 1,
                'reference_answer': 'SECRET-IN-RESULT',
                'grading_notes': 'SECRET-NOTES',
            }]},
        )
        res = _auth(student).get(_url(session.id, ex.id, 'result/'))
        assert res.data['answersRevealed'] is False
        assert 'SECRET-IN-RESULT' not in json.dumps(res.data, ensure_ascii=False)
        assert 'SECRET-NOTES' not in json.dumps(res.data, ensure_ascii=False)


class TestSubmit:
    def test_submit_creates_submission(self):
        session, ex = _published_exercise()
        res = _auth(_student()).post(_url(session.id, ex.id, 'submit/'),
                                     {'answers': {'1': {'text': 'x'}}}, format='json')
        assert res.status_code == 201
        assert res.data['status'] == SubStatus.SUBMITTED

    def test_submit_after_deadline_409(self):
        session, ex = _published_exercise(deadline=timezone.now() - timedelta(minutes=1))
        res = _auth(_student()).post(_url(session.id, ex.id, 'submit/'), {}, format='json')
        assert res.status_code == 409

    def test_submit_after_deadline_allowed_when_allow_late(self):
        session, ex = _published_exercise(
            deadline=timezone.now() - timedelta(minutes=1), allow_late=True)
        res = _auth(_student()).post(_url(session.id, ex.id, 'submit/'), {}, format='json')
        assert res.status_code == 201
        assert res.data['isLate'] is True

    def test_duplicate_submission_409(self):
        session, ex = _published_exercise()
        student = _student()
        first = _auth(student).post(_url(session.id, ex.id, 'submit/'), {}, format='json')
        assert first.status_code == 201
        second = _auth(student).post(_url(session.id, ex.id, 'submit/'), {}, format='json')
        assert second.status_code == 409

    def test_submit_uninvited_404(self):
        session, ex = _published_exercise(invited_phone=None)
        assert _auth(_student()).post(_url(session.id, ex.id, 'submit/'), {}, format='json').status_code == 404


class TestDraftAndImage:
    def test_draft_autosaves(self):
        session, ex = _published_exercise()
        res = _auth(_student()).put(_url(session.id, ex.id, 'draft/'),
                                    {'answers': {'1': {'text': 'draft'}}}, format='json')
        assert res.status_code == 200 and res.data['saved'] is True

    def test_draft_blocked_after_submit(self):
        session, ex = _published_exercise()
        student = _student()
        _auth(student).post(_url(session.id, ex.id, 'submit/'), {}, format='json')
        res = _auth(student).put(_url(session.id, ex.id, 'draft/'),
                                 {'answers': {}}, format='json')
        assert res.status_code == 409

    def test_image_rejects_non_image(self):
        session, ex = _published_exercise()
        q = ClassExerciseQuestion.objects.filter(section__exercise=ex).first()
        fake = io.BytesIO(b'%PDF-not-image')
        fake.name = 'x.pdf'
        res = _auth(_student()).post(
            _url(session.id, ex.id, f'questions/{q.id}/image/'),
            {'file': fake}, format='multipart',
        )
        assert res.status_code == 400


class TestFinishedAnswersBrowse:
    def test_lists_only_deadline_passed_with_reveal(self):
        student = _student()
        # past-deadline exercise (reveal open)
        s1, past = _published_exercise(deadline=timezone.now() - timedelta(days=1))
        # future-deadline exercise (must NOT appear, must NOT leak)
        s2, future = _published_exercise(deadline=timezone.now() + timedelta(days=1))
        res = _auth(student).get('/api/classes/student/exercises/answers/')
        assert res.status_code == 200
        ids = {row['id'] for row in res.data}
        assert past.id in ids and future.id not in ids
        assert REF in json.dumps(res.data, ensure_ascii=False)  # revealed for past

    def test_no_phone_400(self):
        no_phone = baker.make(User, role=User.Role.STUDENT, phone=None)
        assert _auth(no_phone).get('/api/classes/student/exercises/answers/').status_code == 400

    def test_anonymous_401(self):
        assert APIClient().get('/api/classes/student/exercises/answers/').status_code in (401, 403)
