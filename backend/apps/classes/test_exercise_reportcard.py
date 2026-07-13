"""E7 — teacher override + allow-redo + student report cards.

Key invariants: teacher override writes teacher_score/teacher_feedback but
NEVER touches llm_score (audit); score_points is recomputed from the effective
score; report-card average = mean of the student's GRADED exercise percentages.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from model_bakery import baker
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.classes.models import (
    ClassCreationSession,
    ClassInvitation,
    ClassExercise,
    StudentExerciseSubmission,
)

pytestmark = [pytest.mark.django_db, pytest.mark.api]

SubStatus = StudentExerciseSubmission.Status
PHONE = '09121234567'


def _auth(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
    return c


def _teacher():
    return baker.make(User, role=User.Role.TEACHER)


def _graded_submission(owner, *, student=None, score='7', mx='10', per_question=None):
    session = baker.make(ClassCreationSession, teacher=owner, pipeline_type='class',
                         is_published=True)
    ex = baker.make(ClassExercise, session=session, status=ClassExercise.Status.PUBLISHED)
    student = student or baker.make(User, role=User.Role.STUDENT, phone=PHONE)
    ClassInvitation.objects.get_or_create(
        session=session,
        phone=student.phone,
        defaults={'invite_code': f'RC-{session.id}'},
    )
    sub = baker.make(
        StudentExerciseSubmission, exercise=ex, student=student, status=SubStatus.GRADED,
        score_points=Decimal(score), max_points=Decimal(mx),
        result={'per_question': per_question or [
            {'question_id': 'q1', 'llm_score': 3.0, 'score_points': 3.0, 'max_points': 4.0,
             'teacher_score': None, 'teacher_feedback': None, 'label': 'partially_correct'},
            {'question_id': 'q2', 'llm_score': 4.0, 'score_points': 4.0, 'max_points': 6.0,
             'teacher_score': None, 'teacher_feedback': None, 'label': 'partially_correct'},
        ]},
    )
    return session, ex, student, sub


class TestOverride:
    def test_override_keeps_llm_score_and_recomputes(self):
        owner = _teacher()
        _s, _ex, _st, sub = _graded_submission(owner, score='7', mx='10')
        res = _auth(owner).patch(
            f'/api/classes/exercises/submissions/{sub.id}/override/',
            {'overrides': [{'question_id': 'q1', 'teacher_score': 4, 'teacher_feedback': 'عالی'}]},
            format='json',
        )
        assert res.status_code == 200
        sub.refresh_from_db()
        pq1 = next(p for p in sub.result['per_question'] if p['question_id'] == 'q1')
        assert pq1['llm_score'] == 3.0          # IMMUTABLE audit value
        assert pq1['teacher_score'] == 4.0
        assert pq1['score_points'] == 4.0        # effective = teacher_score
        # total recomputed: q1 effective 4 + q2 effective 4 = 8
        assert str(sub.score_points) == '8.00'
        assert sub.overridden_at is not None

    def test_override_cross_teacher_404(self):
        owner, other = _teacher(), _teacher()
        _s, _ex, _st, sub = _graded_submission(owner)
        assert _auth(other).patch(
            f'/api/classes/exercises/submissions/{sub.id}/override/',
            {'overrides': []}, format='json',
        ).status_code == 404

    def test_override_anonymous_401(self):
        owner = _teacher()
        _s, _ex, _st, sub = _graded_submission(owner)
        assert APIClient().patch(
            f'/api/classes/exercises/submissions/{sub.id}/override/', {}, format='json',
        ).status_code in (401, 403)


class TestSubmissionsListAndDetail:
    def test_list_owner_only(self):
        owner, other = _teacher(), _teacher()
        _s, ex, _st, sub = _graded_submission(owner)
        ok = _auth(owner).get(f'/api/classes/exercises/{ex.id}/submissions/')
        assert ok.status_code == 200 and len(ok.data) == 1
        assert _auth(other).get(f'/api/classes/exercises/{ex.id}/submissions/').status_code == 404

    def test_detail_owner_only(self):
        owner, other = _teacher(), _teacher()
        _s, _ex, _st, sub = _graded_submission(owner)
        assert _auth(owner).get(f'/api/classes/exercises/submissions/{sub.id}/').status_code == 200
        assert _auth(other).get(f'/api/classes/exercises/submissions/{sub.id}/').status_code == 404


class TestAllowRedo:
    def test_allow_redo_resets_to_draft(self):
        owner = _teacher()
        _s, _ex, _st, sub = _graded_submission(owner)
        res = _auth(owner).post(f'/api/classes/exercises/submissions/{sub.id}/allow-redo/')
        assert res.status_code == 200
        sub.refresh_from_db()
        assert sub.status == SubStatus.DRAFT
        assert sub.score_points is None and sub.result == {}

    def test_allow_redo_cross_teacher_404(self):
        owner, other = _teacher(), _teacher()
        _s, _ex, _st, sub = _graded_submission(owner)
        assert _auth(other).post(
            f'/api/classes/exercises/submissions/{sub.id}/allow-redo/').status_code == 404


class TestReportCard:
    def test_course_report_average(self):
        owner = _teacher()
        student = baker.make(User, role=User.Role.STUDENT, phone=PHONE)
        session, ex, _st, sub = _graded_submission(owner, student=student, score='8', mx='10')
        res = _auth(student).get(f'/api/classes/student/courses/{session.id}/report-card/')
        assert res.status_code == 200
        assert res.data['average'] == 80.0
        assert len(res.data['exercises']) == 1

    def test_course_report_no_phone_400(self):
        owner = _teacher()
        session = baker.make(ClassCreationSession, teacher=owner, is_published=True)
        no_phone = baker.make(User, role=User.Role.STUDENT, phone=None)
        assert _auth(no_phone).get(
            f'/api/classes/student/courses/{session.id}/report-card/').status_code == 400

    def test_course_report_uninvited_404(self):
        owner = _teacher()
        session, ex, _st, sub = _graded_submission(owner)
        outsider = baker.make(User, role=User.Role.STUDENT, phone='09129999999')
        assert _auth(outsider).get(
            f'/api/classes/student/courses/{session.id}/report-card/').status_code == 404

    def test_overall_report_averages_across_courses(self):
        owner = _teacher()
        student = baker.make(User, role=User.Role.STUDENT, phone=PHONE)
        _graded_submission(owner, student=student, score='10', mx='10')  # 100%
        _graded_submission(owner, student=student, score='5', mx='10')   # 50%
        res = _auth(student).get('/api/classes/student/report-card/')
        assert res.status_code == 200
        assert res.data['average'] == 75.0  # mean(100, 50)

    def test_overall_report_anonymous_401(self):
        assert APIClient().get('/api/classes/student/report-card/').status_code in (401, 403)
