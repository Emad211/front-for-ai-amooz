"""Teacher-owned resource IDOR (security-auditor, MANDATORY on ownership).

`test_permissions.TestCrossTeacherIsolation` already proves a non-owner teacher
gets 404 on another teacher's CLASS session for **view / delete / publish /
invite-POST**, and `test_pipeline_cancel` covers cross-teacher **cancel**. Not
duplicated.

The remaining owner-scoped surfaces had no non-owner negative:
* **PATCH-update** a class session (edit title/description/structure),
* the session **list** must be owner-scoped (no cross-teacher leak in the feed),
* **GET-invites** and **announcements** of another teacher's session,
* the entire **exam-prep** session surface (view/delete/publish/invites), which
  the class-only isolation class never exercised.

Every case must fail closed (404 — the object is simply not in the owner-scoped
queryset), and a student is blocked from the teacher creation-session endpoints.
"""
from __future__ import annotations

import pytest
from model_bakery import baker
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.classes.models import ClassCreationSession

pytestmark = [pytest.mark.django_db, pytest.mark.permission]

DETAIL = '/api/classes/creation-sessions/{}/'
LIST = '/api/classes/creation-sessions/'
INVITES = '/api/classes/creation-sessions/{}/invites/'
ANNOUNCE = '/api/classes/creation-sessions/{}/announcements/'
EP_DETAIL = '/api/classes/exam-prep-sessions/{}/'
EP_PUBLISH = '/api/classes/exam-prep-sessions/{}/publish/'
EP_INVITES = '/api/classes/exam-prep-sessions/{}/invites/'


def _auth(user) -> APIClient:
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
    return c


def _teacher():
    return baker.make(User, role=User.Role.TEACHER)


def _class(owner, **kw):
    return baker.make(ClassCreationSession, teacher=owner, pipeline_type='class', **kw)


def _exam_prep(owner, **kw):
    return baker.make(ClassCreationSession, teacher=owner, pipeline_type='exam_prep', **kw)


class TestClassSessionNonOwner:
    def test_cannot_patch_other_teacher_session(self):
        owner, other = _teacher(), _teacher()
        s = _class(owner, title='original')
        res = _auth(other).patch(DETAIL.format(s.id), {'title': 'hijacked'}, format='json')
        assert res.status_code == 404
        s.refresh_from_db()
        assert s.title == 'original'  # untouched

    def test_list_is_owner_scoped(self):
        owner, other = _teacher(), _teacher()
        s = _class(owner, title='owners-class')
        # The owner sees it…
        owner_ids = {row['id'] for row in _auth(owner).get(LIST).data}
        assert s.id in owner_ids
        # …the other teacher's list must NOT contain it (no cross-teacher leak).
        other_ids = {row['id'] for row in _auth(other).get(LIST).data}
        assert s.id not in other_ids

    def test_cannot_list_invites_of_other_teacher_session(self):
        owner, other = _teacher(), _teacher()
        s = _class(owner)
        assert _auth(other).get(INVITES.format(s.id)).status_code == 404

    def test_cannot_post_announcement_to_other_teacher_session(self):
        owner, other = _teacher(), _teacher()
        s = _class(owner)
        res = _auth(other).post(
            ANNOUNCE.format(s.id), {'title': 'x', 'body': 'y'}, format='json',
        )
        assert res.status_code in (403, 404)

    def test_student_blocked_from_creation_session_detail(self):
        owner = _teacher()
        s = _class(owner)
        student = baker.make(User, role=User.Role.STUDENT)
        # Not a teacher endpoint for this student's data → not their session.
        assert _auth(student).get(DETAIL.format(s.id)).status_code in (403, 404)

    def test_anonymous_denied_on_list(self):
        assert APIClient().get(LIST).status_code in (401, 403)


class TestExamPrepSessionNonOwner:
    """The exam-prep surface is a parallel pipeline the class-only isolation
    class never covered — same owner-scoping must hold."""

    def test_cannot_view_other_teacher_exam_prep(self):
        owner, other = _teacher(), _teacher()
        s = _exam_prep(owner)
        assert _auth(other).get(EP_DETAIL.format(s.id)).status_code == 404

    def test_cannot_delete_other_teacher_exam_prep(self):
        owner, other = _teacher(), _teacher()
        s = _exam_prep(owner)
        assert _auth(other).delete(EP_DETAIL.format(s.id)).status_code == 404
        assert ClassCreationSession.objects.filter(id=s.id).exists()

    def test_cannot_publish_other_teacher_exam_prep(self):
        owner, other = _teacher(), _teacher()
        s = _exam_prep(owner, structure_json='{}')
        assert _auth(other).post(EP_PUBLISH.format(s.id)).status_code == 404

    def test_cannot_invite_to_other_teacher_exam_prep(self):
        owner, other = _teacher(), _teacher()
        s = _exam_prep(owner)
        res = _auth(other).post(
            EP_INVITES.format(s.id), {'phones': ['09121111111']}, format='json',
        )
        assert res.status_code == 404

    def test_exam_prep_list_is_owner_scoped(self):
        owner, other = _teacher(), _teacher()
        s = _exam_prep(owner)
        other_ids = {row['id'] for row in _auth(other).get('/api/classes/exam-prep-sessions/').data}
        assert s.id not in other_ids
