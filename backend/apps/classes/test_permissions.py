"""Permission and authorization tests.

Verifies that every endpoint enforces correct role-based access control.
Teachers cannot access student endpoints and vice versa.
Unauthenticated requests are rejected.
"""
from __future__ import annotations

import pytest
from model_bakery import baker

from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.classes.models import ClassCreationSession, ClassInvitation


def _auth_client(user) -> APIClient:
    refresh = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


@pytest.mark.django_db
class TestTeacherEndpointPermissions:
    """Teacher-only endpoints must reject students and anonymous users."""

    TEACHER_URLS = [
        '/api/classes/sessions/',
        '/api/classes/analytics/stats/',
        '/api/classes/analytics/chart/',
        '/api/classes/analytics/activities/',
        '/api/classes/analytics/distribution/',
        '/api/classes/exam-prep/sessions/',
    ]

    def test_anonymous_rejected(self):
        client = APIClient()
        for url in self.TEACHER_URLS:
            resp = client.get(url)
            assert resp.status_code in (401, 403), f'{url} allowed anonymous access'

    def test_student_rejected(self):
        student = baker.make('accounts.User', role='student')
        client = _auth_client(student)
        for url in self.TEACHER_URLS:
            resp = client.get(url)
            assert resp.status_code == 403, f'{url} allowed student access'

    def test_teacher_allowed(self):
        teacher = baker.make('accounts.User', role='teacher')
        client = _auth_client(teacher)
        for url in self.TEACHER_URLS:
            resp = client.get(url)
            assert resp.status_code in (200, 404), f'{url} rejected teacher with {resp.status_code}'


@pytest.mark.django_db
class TestStudentEndpointPermissions:
    """Student-only endpoints must reject teachers and anonymous users."""

    STUDENT_URLS = [
        '/api/classes/student/courses/',
        '/api/classes/student/notifications/',
        '/api/classes/student/exam-prep/',
    ]

    def test_anonymous_rejected(self):
        client = APIClient()
        for url in self.STUDENT_URLS:
            resp = client.get(url)
            assert resp.status_code in (401, 403), f'{url} allowed anonymous access'

    def test_teacher_rejected(self):
        teacher = baker.make('accounts.User', role='teacher')
        client = _auth_client(teacher)
        for url in self.STUDENT_URLS:
            resp = client.get(url)
            assert resp.status_code == 403, f'{url} allowed teacher access'

    def test_student_allowed(self):
        student = baker.make('accounts.User', role='student', phone='09121111111')
        client = _auth_client(student)
        for url in self.STUDENT_URLS:
            resp = client.get(url)
            assert resp.status_code in (200, 400), f'{url} rejected student with {resp.status_code}'


@pytest.mark.django_db
class TestCrossTeacherIsolation:
    """A teacher must not access another teacher's sessions."""

    def test_cannot_view_other_teacher_session(self):
        t1 = baker.make('accounts.User', role='teacher')
        t2 = baker.make('accounts.User', role='teacher')
        session = baker.make(
            'classes.ClassCreationSession',
            teacher=t1,
            pipeline_type='class',
        )

        client = _auth_client(t2)
        resp = client.get(f'/api/classes/sessions/{session.id}/')
        assert resp.status_code == 404

    def test_cannot_delete_other_teacher_session(self):
        t1 = baker.make('accounts.User', role='teacher')
        t2 = baker.make('accounts.User', role='teacher')
        session = baker.make(
            'classes.ClassCreationSession',
            teacher=t1,
            pipeline_type='class',
        )

        client = _auth_client(t2)
        resp = client.delete(f'/api/classes/sessions/{session.id}/')
        assert resp.status_code == 404

    def test_cannot_publish_other_teacher_session(self):
        t1 = baker.make('accounts.User', role='teacher')
        t2 = baker.make('accounts.User', role='teacher')
        session = baker.make(
            'classes.ClassCreationSession',
            teacher=t1,
            pipeline_type='class',
            structure_json='{}',
        )

        client = _auth_client(t2)
        resp = client.post(f'/api/classes/sessions/{session.id}/publish/')
        assert resp.status_code == 404

    def test_cannot_invite_to_other_teacher_session(self):
        t1 = baker.make('accounts.User', role='teacher')
        t2 = baker.make('accounts.User', role='teacher')
        session = baker.make(
            'classes.ClassCreationSession',
            teacher=t1,
            pipeline_type='class',
        )

        client = _auth_client(t2)
        resp = client.post(
            f'/api/classes/sessions/{session.id}/invites/',
            data={'phones': ['09121111111']},
            format='json',
        )
        assert resp.status_code == 404


@pytest.mark.django_db
class TestStudentCourseAccess:
    """Students can only access courses they're invited to."""

    def test_uninvited_student_cannot_see_course(self):
        student = baker.make('accounts.User', role='student', phone='09121111111')
        session = baker.make(
            'classes.ClassCreationSession',
            pipeline_type='class',
            is_published=True,
        )
        # No invitation for this student.

        client = _auth_client(student)
        resp = client.get(f'/api/classes/student/courses/{session.id}/content/')
        assert resp.status_code == 404

    def test_invited_student_can_see_course(self):
        student = baker.make('accounts.User', role='student', phone='09121111111')
        session = baker.make(
            'classes.ClassCreationSession',
            pipeline_type='class',
            is_published=True,
            structure_json='{"title":"Test","sections":[]}',
        )
        ClassInvitation.objects.create(
            session=session,
            phone='09121111111',
            invite_code='TEST',
        )

        client = _auth_client(student)
        resp = client.get(f'/api/classes/student/courses/{session.id}/content/')
        assert resp.status_code == 200

    def test_unpublished_course_not_visible(self):
        student = baker.make('accounts.User', role='student', phone='09121111111')
        session = baker.make(
            'classes.ClassCreationSession',
            pipeline_type='class',
            is_published=False,
        )
        ClassInvitation.objects.create(
            session=session,
            phone='09121111111',
            invite_code='TEST',
        )

        client = _auth_client(student)
        resp = client.get(f'/api/classes/student/courses/{session.id}/content/')
        assert resp.status_code == 404
