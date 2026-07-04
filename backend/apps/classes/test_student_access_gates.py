"""Student course-access gates — the phone-scoping security model.

Per CLAUDE.md, student endpoints are **phone-scoped**, not role-scoped: a
non-invited student sees 404 / 400 / empty-200, never a role-403 (that policy is
verified separately in `test_permissions`). The list phone-scoping, course
content invite gate, PDF-export-for-uninvited, chapter-quiz invite gate, and
lesson-complete invite gate are already covered. Not duplicated.

Untested gaps closed here — the SAME `is_published=True, invites__phone=phone`
gate on the endpoints that lacked a negative test:
* **final exam** GET (uninvited→404, no-phone→400, anon→401),
* **exam-prep detail** GET (uninvited→404, no-phone→400, anon→401),
* **PDF export** anonymous→401.

Every deny path short-circuits BEFORE any LLM/generation call, so these are
zero-token (no `mock_llm` needed — an uninvited request never reaches a model).
"""
from __future__ import annotations

import pytest
from model_bakery import baker
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.classes.models import ClassCreationSession, ClassInvitation

pytestmark = [pytest.mark.django_db, pytest.mark.permission]

FINAL_EXAM = '/api/classes/student/courses/{}/final-exam/'
EXAM_PREP_DETAIL = '/api/classes/student/exam-preps/{}/'
PDF_EXPORT = '/api/classes/student/courses/{}/export-pdf/'


def _auth(user) -> APIClient:
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
    return c


def _student(phone='09121234567'):
    return baker.make(User, role=User.Role.STUDENT, phone=phone)


def _published_class(**kw):
    return baker.make(ClassCreationSession, pipeline_type='class', is_published=True, **kw)


def _published_exam_prep(**kw):
    return baker.make(ClassCreationSession, pipeline_type='exam_prep', is_published=True, **kw)


class TestFinalExamGate:
    def test_uninvited_student_gets_404(self):
        """A published class the student was never invited to is invisible (404),
        and the request never reaches exam generation."""
        s = _published_class()
        student = _student()  # not invited
        assert _auth(student).get(FINAL_EXAM.format(s.id)).status_code == 404

    def test_student_without_phone_gets_400(self):
        s = _published_class()
        no_phone = baker.make(User, role=User.Role.STUDENT, phone=None)
        assert _auth(no_phone).get(FINAL_EXAM.format(s.id)).status_code == 400

    def test_anonymous_gets_401(self):
        s = _published_class()
        assert APIClient().get(FINAL_EXAM.format(s.id)).status_code in (401, 403)

    def test_unpublished_class_is_404_even_when_invited(self):
        """Invite alone isn't enough — an unpublished class stays hidden."""
        s = baker.make(ClassCreationSession, pipeline_type='class', is_published=False)
        student = _student()
        ClassInvitation.objects.create(session=s, phone=student.phone, invite_code='INV1')
        assert _auth(student).get(FINAL_EXAM.format(s.id)).status_code == 404


class TestExamPrepDetailGate:
    def test_uninvited_student_gets_404(self):
        s = _published_exam_prep()
        student = _student()
        assert _auth(student).get(EXAM_PREP_DETAIL.format(s.id)).status_code == 404

    def test_student_without_phone_gets_400(self):
        s = _published_exam_prep()
        no_phone = baker.make(User, role=User.Role.STUDENT, phone=None)
        assert _auth(no_phone).get(EXAM_PREP_DETAIL.format(s.id)).status_code == 400

    def test_anonymous_gets_401(self):
        s = _published_exam_prep()
        assert APIClient().get(EXAM_PREP_DETAIL.format(s.id)).status_code in (401, 403)

    def test_class_session_not_reachable_via_exam_prep_route(self):
        """A CLASS session must not be returned by the exam-prep detail route even
        to an invited student — the route filters pipeline_type=EXAM_PREP."""
        s = _published_class()
        student = _student()
        ClassInvitation.objects.create(session=s, phone=student.phone, invite_code='INV2')
        assert _auth(student).get(EXAM_PREP_DETAIL.format(s.id)).status_code == 404


class TestPdfExportGate:
    def test_anonymous_cannot_export(self):
        s = _published_class()
        assert APIClient().get(PDF_EXPORT.format(s.id)).status_code in (401, 403)
