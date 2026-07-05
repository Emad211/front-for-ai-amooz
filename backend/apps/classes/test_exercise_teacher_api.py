"""E4 — Exercise Hub teacher API: happy CRUD + publish gate + the owner/role
negative matrix (anonymous→401, student→403, cross-teacher→404).

Design + permission matrix: docs/features/exercise-hub.md.
"""
from __future__ import annotations

import pytest
from decimal import Decimal
from model_bakery import baker
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.classes.models import (
    ClassCreationSession,
    ClassExercise,
    ClassExerciseQuestion,
    ClassExerciseSection,
)

pytestmark = [pytest.mark.django_db, pytest.mark.api]

Status = ClassExercise.Status


def _auth(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
    return c


def _teacher():
    return baker.make(User, role=User.Role.TEACHER)


def _session(owner):
    return baker.make(ClassCreationSession, teacher=owner, pipeline_type='class')


def _exercise(owner, **kw):
    return baker.make(ClassExercise, session=_session(owner), **kw)


LIST = '/api/classes/creation-sessions/{}/exercises/'
DETAIL = '/api/classes/exercises/{}/'
EXTRACT = '/api/classes/exercises/{}/extract/'
PUBLISH = '/api/classes/exercises/{}/publish/'


class TestCreateAndList:
    def test_teacher_creates_and_lists_exercise(self):
        owner = _teacher()
        session = _session(owner)
        res = _auth(owner).post(LIST.format(session.id), {'title': 'تمرین ۱'}, format='multipart')
        assert res.status_code == 201, res.content
        assert res.data['title'] == 'تمرین ۱'
        assert res.data['status'] == Status.DRAFT
        lst = _auth(owner).get(LIST.format(session.id))
        assert lst.status_code == 200 and len(lst.data) == 1

    def test_create_on_other_teacher_session_is_404(self):
        owner, other = _teacher(), _teacher()
        session = _session(owner)
        res = _auth(other).post(LIST.format(session.id), {'title': 'x'}, format='multipart')
        assert res.status_code == 404

    def test_anonymous_denied(self):
        session = _session(_teacher())
        assert APIClient().get(LIST.format(session.id)).status_code in (401, 403)

    def test_student_forbidden(self):
        session = _session(_teacher())
        student = baker.make(User, role=User.Role.STUDENT)
        assert _auth(student).get(LIST.format(session.id)).status_code == 403


class TestDetailUpdateDelete:
    def test_owner_patches_toggle_and_deadline(self):
        owner = _teacher()
        ex = _exercise(owner)
        res = _auth(owner).patch(
            DETAIL.format(ex.id), {'assistant_enabled': False, 'allow_late': True}, format='json',
        )
        assert res.status_code == 200
        ex.refresh_from_db()
        assert ex.assistant_enabled is False and ex.allow_late is True

    def test_non_owner_cannot_view_or_patch_or_delete(self):
        owner, other = _teacher(), _teacher()
        ex = _exercise(owner)
        assert _auth(other).get(DETAIL.format(ex.id)).status_code == 404
        assert _auth(other).patch(DETAIL.format(ex.id), {'title': 'hijack'}, format='json').status_code == 404
        assert _auth(other).delete(DETAIL.format(ex.id)).status_code == 404
        ex.refresh_from_db()
        assert ex.title != 'hijack'

    def test_owner_deletes(self):
        owner = _teacher()
        ex = _exercise(owner)
        assert _auth(owner).delete(DETAIL.format(ex.id)).status_code == 204
        assert not ClassExercise.objects.filter(id=ex.id).exists()


class TestExtract:
    def test_extract_dispatches(self, monkeypatch):
        from apps.classes import views_exercises as vx
        called = {}
        monkeypatch.setattr(vx.extract_exercise_content, 'delay', lambda eid: called.setdefault('id', eid))
        owner = _teacher()
        ex = _exercise(owner, status=Status.DRAFT)
        res = _auth(owner).post(EXTRACT.format(ex.id))
        assert res.status_code == 202

    def test_extract_conflicts_while_extracting(self):
        owner = _teacher()
        ex = _exercise(owner, status=Status.EXTRACTING)
        assert _auth(owner).post(EXTRACT.format(ex.id)).status_code == 409

    def test_extract_cross_teacher_404(self):
        owner, other = _teacher(), _teacher()
        ex = _exercise(owner)
        assert _auth(other).post(EXTRACT.format(ex.id)).status_code == 404


class TestPublishGate:
    def _exercise_with_question(self, owner, **qkw):
        ex = _exercise(owner, status=Status.EXTRACTED)
        sec = baker.make(ClassExerciseSection, exercise=ex, order=0)
        baker.make(ClassExerciseQuestion, section=sec, order=0, **qkw)
        return ex

    def test_publish_blocked_without_reference_answer(self):
        owner = _teacher()
        ex = self._exercise_with_question(
            owner, reference_answer_markdown='', max_points=Decimal('2'))
        res = _auth(owner).post(PUBLISH.format(ex.id))
        assert res.status_code == 400
        assert 'incompleteQuestionIds' in res.data
        ex.refresh_from_db()
        assert ex.status == Status.EXTRACTED  # not published

    def test_publish_blocked_wrong_status(self):
        owner = _teacher()
        ex = _exercise(owner, status=Status.DRAFT)
        assert _auth(owner).post(PUBLISH.format(ex.id)).status_code == 409

    def test_publish_blocked_when_no_questions(self):
        owner = _teacher()
        ex = _exercise(owner, status=Status.EXTRACTED)
        assert _auth(owner).post(PUBLISH.format(ex.id)).status_code == 400

    def test_publish_succeeds_when_complete(self):
        owner = _teacher()
        ex = self._exercise_with_question(
            owner, reference_answer_markdown='پاسخ', max_points=Decimal('2'))
        res = _auth(owner).post(PUBLISH.format(ex.id))
        assert res.status_code == 200
        ex.refresh_from_db()
        assert ex.status == Status.PUBLISHED

    def test_publish_cross_teacher_404(self):
        owner, other = _teacher(), _teacher()
        ex = self._exercise_with_question(
            owner, reference_answer_markdown='پاسخ', max_points=Decimal('2'))
        assert _auth(other).post(PUBLISH.format(ex.id)).status_code == 404


class TestSectionAndQuestionOwnership:
    def test_section_toggle_owner_only(self):
        owner, other = _teacher(), _teacher()
        ex = _exercise(owner)
        sec = baker.make(ClassExerciseSection, exercise=ex, order=0)
        url = f'/api/classes/exercises/sections/{sec.id}/'
        assert _auth(other).patch(url, {'assistant_enabled': False}, format='json').status_code == 404
        ok = _auth(owner).patch(url, {'assistant_enabled': False}, format='json')
        assert ok.status_code == 200 and ok.data['assistantEnabled'] is False

    def test_question_edit_owner_only(self):
        owner, other = _teacher(), _teacher()
        ex = _exercise(owner)
        sec = baker.make(ClassExerciseSection, exercise=ex, order=0)
        q = baker.make(ClassExerciseQuestion, section=sec, order=0)
        url = f'/api/classes/exercises/questions/{q.id}/'
        assert _auth(other).patch(url, {'reference_answer_markdown': 'x'}, format='json').status_code == 404
        ok = _auth(owner).patch(url, {'reference_answer_markdown': 'پاسخ'}, format='json')
        assert ok.status_code == 200
        q.refresh_from_db()
        assert q.reference_answer_markdown == 'پاسخ'
