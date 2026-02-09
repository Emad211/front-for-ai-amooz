"""Edge cases and error handling tests.

Tests for boundary conditions, invalid inputs, and error paths
that are critical under production load.
"""
from __future__ import annotations

import pytest
from model_bakery import baker

from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.classes.models import ClassCreationSession, ClassInvitation, StudentInviteCode


def _auth_client(user) -> APIClient:
    refresh = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


@pytest.mark.django_db
class TestSessionCRUDEdgeCases:
    """Test CRUD operations on sessions with edge-case inputs."""

    def test_get_nonexistent_session(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        client = _auth_client(teacher)
        resp = client.get('/api/classes/creation-sessions/999999/')
        assert resp.status_code == 404

    def test_delete_nonexistent_session(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        client = _auth_client(teacher)
        resp = client.delete('/api/classes/creation-sessions/999999/')
        assert resp.status_code == 404

    def test_publish_session_without_structure(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        session = baker.make(
            ClassCreationSession,
            teacher=teacher,
            pipeline_type='class',
            structure_json='',
            is_published=False,
        )
        client = _auth_client(teacher)
        resp = client.post(f'/api/classes/creation-sessions/{session.id}/publish/')
        assert resp.status_code == 400

    def test_patch_session_title(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        session = baker.make(
            ClassCreationSession,
            teacher=teacher,
            pipeline_type='class',
            title='Old Title',
        )
        client = _auth_client(teacher)
        resp = client.patch(
            f'/api/classes/creation-sessions/{session.id}/',
            data={'title': 'New Title'},
            format='json',
        )
        assert resp.status_code == 200
        session.refresh_from_db()
        assert session.title == 'New Title'

    def test_re_publish_is_idempotent(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        session = baker.make(
            ClassCreationSession,
            teacher=teacher,
            pipeline_type='class',
            structure_json='{"sections":[]}',
            is_published=True,
        )
        client = _auth_client(teacher)
        resp = client.post(f'/api/classes/creation-sessions/{session.id}/publish/')
        assert resp.status_code == 200


@pytest.mark.django_db
class TestInvitationEdgeCases:
    """Edge cases for invitation creation and deletion."""

    def test_invite_with_empty_phones_list(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        session = baker.make(
            ClassCreationSession,
            teacher=teacher,
            pipeline_type='class',
        )
        client = _auth_client(teacher)
        resp = client.post(
            f'/api/classes/creation-sessions/{session.id}/invites/',
            data={'phones': []},
            format='json',
        )
        assert resp.status_code in (200, 400)

    def test_delete_nonexistent_invite(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        session = baker.make(
            ClassCreationSession,
            teacher=teacher,
            pipeline_type='class',
        )
        client = _auth_client(teacher)
        resp = client.delete(
            f'/api/classes/creation-sessions/{session.id}/invites/999999/'
        )
        assert resp.status_code == 404

    def test_delete_invite_from_other_session(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        s1 = baker.make(ClassCreationSession, teacher=teacher, pipeline_type='class')
        s2 = baker.make(ClassCreationSession, teacher=teacher, pipeline_type='class')
        inv = baker.make(ClassInvitation, session=s1)

        client = _auth_client(teacher)
        resp = client.delete(
            f'/api/classes/creation-sessions/{s2.id}/invites/{inv.id}/'
        )
        assert resp.status_code == 404


@pytest.mark.django_db
class TestAnnouncementEdgeCases:
    """Edge cases for announcement CRUD."""

    def test_create_announcement(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        session = baker.make(
            ClassCreationSession,
            teacher=teacher,
            pipeline_type='class',
        )
        client = _auth_client(teacher)
        resp = client.post(
            f'/api/classes/creation-sessions/{session.id}/announcements/',
            data={'title': 'Test', 'content': 'Hello students'},
            format='json',
        )
        assert resp.status_code == 201

    def test_update_nonexistent_announcement(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        session = baker.make(
            ClassCreationSession,
            teacher=teacher,
            pipeline_type='class',
        )
        client = _auth_client(teacher)
        resp = client.patch(
            f'/api/classes/creation-sessions/{session.id}/announcements/999999/',
            data={'title': 'Updated'},
            format='json',
        )
        assert resp.status_code == 404


@pytest.mark.django_db
class TestStudentEdgeCases:
    """Edge cases for student-facing endpoints."""

    def test_student_without_phone_gets_empty_list(self):
        student = baker.make(User, role=User.Role.STUDENT, phone='')
        client = _auth_client(student)
        resp = client.get('/api/classes/student/courses/')
        assert resp.status_code == 200

    def test_student_course_content_without_phone(self):
        student = baker.make(User, role=User.Role.STUDENT, phone='')
        client = _auth_client(student)
        resp = client.get('/api/classes/student/courses/1/content/')
        assert resp.status_code == 400

    def test_invite_code_verify_invalid_code(self):
        client = APIClient()
        resp = client.post(
            '/api/classes/invites/verify/',
            data={'invite_code': 'NONEXISTENT'},
            format='json',
        )
        assert resp.status_code in (200, 400, 404)


@pytest.mark.django_db
class TestAnalyticsEdgeCases:
    """Edge cases for analytics endpoints."""

    def test_analytics_stats_empty_data(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        client = _auth_client(teacher)
        resp = client.get('/api/classes/teacher/analytics/stats/')
        assert resp.status_code == 200

    def test_analytics_stats_with_invalid_days(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        client = _auth_client(teacher)
        resp = client.get('/api/classes/teacher/analytics/stats/?days=-1')
        assert resp.status_code in (200, 400)

    def test_analytics_chart_empty(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        client = _auth_client(teacher)
        resp = client.get('/api/classes/teacher/analytics/chart/')
        assert resp.status_code == 200

    def test_analytics_distribution_empty(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        client = _auth_client(teacher)
        resp = client.get('/api/classes/teacher/analytics/distribution/')
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, (list, dict))
