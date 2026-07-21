"""E8 — exercise assistant: two-level toggle 403 + the STRUCTURAL reference-answer
leak guard (reference never in context pre-reveal) + phone-scope + happy chat.
LLM mocked (0 tokens).
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from model_bakery import baker
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.classes.services import exercise_assistant as asst
from apps.classes.services.exercise_assistant import build_question_context
from apps.classes.models import (
    ClassCreationSession,
    ClassInvitation,
    ClassExercise,
    ClassExerciseQuestion,
    ClassExerciseSection,
)

pytestmark = [pytest.mark.django_db]

PHONE = '09121234567'
REF = 'SECRET-REFERENCE-ANSWER'


def _auth(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
    return c


def _student(phone=PHONE):
    return baker.make(User, role=User.Role.STUDENT, phone=phone)


def _setup(*, invited=True, deadline=None, allow_late=False,
           ex_assistant=True, sec_assistant=True):
    session = baker.make(ClassCreationSession, pipeline_type='class', is_published=True)
    if invited:
        ClassInvitation.objects.create(session=session, phone=PHONE, invite_code='INV')
    ex = baker.make(ClassExercise, session=session, status=ClassExercise.Status.PUBLISHED,
                    deadline=deadline, allow_late=allow_late,
                    assistant_enabled=ex_assistant)
    sec = baker.make(ClassExerciseSection, exercise=ex, order=0, assistant_enabled=sec_assistant)
    q = baker.make(ClassExerciseQuestion, section=sec, order=0,
                   question_markdown='۲+۲=؟', reference_answer_markdown=REF)
    return session, ex, sec, q


def _url(session_id, exercise_id):
    return f'/api/classes/student/courses/{session_id}/exercises/{exercise_id}/assistant/'


@pytest.fixture
def mock_llm(monkeypatch):
    monkeypatch.setenv('EXERCISE_CHAT_MODEL', 'test-model')
    monkeypatch.setattr(
        asst, 'generate_structured',
        lambda **k: type('O', (), {'content': 'یه راهنمایی کوچیک', 'suggestions': ['ادامه بده']})(),
    )


class TestContextLeakGuard:
    """The STRUCTURAL guard: reference answer only in context when reveal=True."""

    def test_context_excludes_reference_before_reveal(self):
        _s, _ex, _sec, q = _setup()
        ctx = build_question_context(q, reveal=False)
        assert REF not in ctx

    def test_context_includes_reference_after_reveal(self):
        _s, _ex, _sec, q = _setup()
        ctx = build_question_context(q, reveal=True)
        assert REF in ctx

    def test_assistant_excludes_reference_while_late_submissions_are_open(self, monkeypatch):
        captured = {}

        def fake_generate_structured(**kwargs):
            captured['contents'] = kwargs['contents']
            return type('O', (), {'content': 'راهنمایی', 'suggestions': []})()

        monkeypatch.setenv('EXERCISE_CHAT_MODEL', 'test-model')
        monkeypatch.setattr(asst, 'generate_structured', fake_generate_structured)
        session, ex, _sec, q = _setup(
            deadline=timezone.now() - timedelta(minutes=1),
            allow_late=True,
        )

        res = _auth(_student()).post(
            _url(session.id, ex.id),
            {'question_id': q.id, 'message': 'راهنمایی کن'},
            format='json',
        )

        assert res.status_code == 200
        assert REF not in captured['contents']


class TestToggleGuard:
    def test_exercise_assistant_off_403(self, mock_llm):
        session, ex, sec, q = _setup(ex_assistant=False)
        res = _auth(_student()).post(_url(session.id, ex.id),
                                     {'question_id': q.id, 'message': 'کمک'}, format='json')
        assert res.status_code == 403
        assert res.data['code'] == 'assistant_disabled'

    def test_legacy_section_assistant_flag_no_longer_blocks(self, mock_llm):
        session, ex, sec, q = _setup(sec_assistant=False)
        res = _auth(_student()).post(_url(session.id, ex.id),
                                     {'question_id': q.id, 'message': 'کمک'}, format='json')
        assert res.status_code == 200
        assert res.data['content']

    def test_both_on_allows(self, mock_llm):
        session, ex, sec, q = _setup()
        res = _auth(_student()).post(_url(session.id, ex.id),
                                     {'question_id': q.id, 'message': 'کمک'}, format='json')
        assert res.status_code == 200
        assert res.data['content']


class TestScopingAndHappy:
    def test_uninvited_404(self, mock_llm):
        session, ex, sec, q = _setup(invited=False)
        assert _auth(_student()).post(_url(session.id, ex.id),
                                      {'question_id': q.id, 'message': 'x'}, format='json').status_code == 404

    def test_no_phone_400(self, mock_llm):
        session, ex, sec, q = _setup()
        no_phone = baker.make(User, role=User.Role.STUDENT, phone=None)
        assert _auth(no_phone).post(_url(session.id, ex.id),
                                    {'question_id': q.id, 'message': 'x'}, format='json').status_code == 400

    def test_anonymous_401(self):
        session, ex, sec, q = _setup()
        assert APIClient().post(_url(session.id, ex.id),
                                {'question_id': q.id, 'message': 'x'}, format='json').status_code in (401, 403)

    def test_unknown_question_404(self, mock_llm):
        session, ex, sec, q = _setup()
        assert _auth(_student()).post(_url(session.id, ex.id),
                                      {'question_id': 999999, 'message': 'x'}, format='json').status_code == 404

    def test_happy_chat_returns_reply(self, mock_llm):
        session, ex, sec, q = _setup()
        res = _auth(_student()).post(_url(session.id, ex.id),
                                     {'question_id': q.id, 'message': 'راهنمایی کن'}, format='json')
        assert res.status_code == 200
        assert res.data['content'] == 'یه راهنمایی کوچیک'
        assert res.data['suggestions'] == ['ادامه بده']

    def test_cross_exercise_question_smuggling_404(self, mock_llm):
        """security-auditor E8 Info: a question from a SIBLING exercise (assistant
        on) must not be usable against this exercise — locks section__exercise scope."""
        session, ex, sec, q = _setup()
        # a second exercise in the SAME session, assistant on, with its own question
        other = baker.make(ClassExercise, session=session,
                           status=ClassExercise.Status.PUBLISHED, assistant_enabled=True)
        osec = baker.make(ClassExerciseSection, exercise=other, order=0, assistant_enabled=True)
        oq = baker.make(ClassExerciseQuestion, section=osec, order=0)
        res = _auth(_student()).post(_url(session.id, ex.id),
                                     {'question_id': oq.id, 'message': 'x'}, format='json')
        assert res.status_code == 404  # oq is not a question of `ex`

    def test_model_unset_degrades_gracefully_not_500(self, monkeypatch):
        """security-auditor E8 Low-1: all *_MODEL env unset -> graceful fallback, not 500."""
        for var in ('EXERCISE_CHAT_MODEL', 'CHAT_MODEL', 'MODEL_NAME'):
            monkeypatch.delenv(var, raising=False)
        session, ex, sec, q = _setup()
        res = _auth(_student()).post(_url(session.id, ex.id),
                                     {'question_id': q.id, 'message': 'کمک'}, format='json')
        assert res.status_code == 200
        assert 'متأسفم' in res.data['content']
