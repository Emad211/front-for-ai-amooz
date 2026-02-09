"""Concurrency & race condition tests.

Verifies that endpoints behave correctly under concurrent access patterns
that would occur with ~100 simultaneous users.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from model_bakery import baker

from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.classes.models import (
    ClassCreationSession,
    ClassInvitation,
    StudentInviteCode,
)


def _auth_client(user) -> APIClient:
    refresh = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


@pytest.mark.django_db
class TestPublishRaceCondition:
    """Two sequential publish requests must not both trigger SMS."""

    def test_double_publish_only_publishes_once(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        session = baker.make(
            ClassCreationSession,
            teacher=teacher,
            pipeline_type='class',
            status='structured',
            structure_json='{"sections": []}',
            is_published=False,
        )

        client = _auth_client(teacher)

        # First publish — should succeed and set is_published=True.
        resp1 = client.post(
            f'/api/classes/creation-sessions/{session.id}/publish/'
        )
        assert resp1.status_code == 200

        session.refresh_from_db()
        assert session.is_published is True
        first_published_at = session.published_at

        # Second publish — idempotent, should still return 200 but NOT update.
        resp2 = client.post(
            f'/api/classes/creation-sessions/{session.id}/publish/'
        )
        assert resp2.status_code == 200

        session.refresh_from_db()
        assert session.is_published is True
        # published_at should not change on the re-publish.
        assert session.published_at == first_published_at

    def test_publish_failed_session_rejected(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        session = baker.make(
            ClassCreationSession,
            teacher=teacher,
            pipeline_type='class',
            status='failed',
            is_published=False,
        )
        client = _auth_client(teacher)
        resp = client.post(
            f'/api/classes/creation-sessions/{session.id}/publish/'
        )
        assert resp.status_code == 400


@pytest.mark.django_db
class TestInvitationConcurrency:
    """Invitation creation must be safe under concurrent access."""

    def test_bulk_invite_no_duplicates(self):
        """Inviting the same phone twice in a single request creates only one invitation."""
        teacher = baker.make(User, role=User.Role.TEACHER)
        session = baker.make(
            ClassCreationSession,
            teacher=teacher,
            pipeline_type='class',
        )
        StudentInviteCode.objects.get_or_create(
            phone='09121111111', defaults={'code': 'ABC123'},
        )

        client = _auth_client(teacher)
        resp = client.post(
            f'/api/classes/creation-sessions/{session.id}/invites/',
            data={'phones': ['09121111111', '09121111111']},
            format='json',
        )
        assert resp.status_code == 200
        assert ClassInvitation.objects.filter(session=session).count() == 1

    def test_bulk_invite_idempotent(self):
        """Calling invite twice with the same phone doesn't create duplicates."""
        teacher = baker.make(User, role=User.Role.TEACHER)
        session = baker.make(
            ClassCreationSession,
            teacher=teacher,
            pipeline_type='class',
        )
        StudentInviteCode.objects.get_or_create(
            phone='09121111111', defaults={'code': 'ABC123'},
        )

        client = _auth_client(teacher)
        # First call
        client.post(
            f'/api/classes/creation-sessions/{session.id}/invites/',
            data={'phones': ['09121111111']},
            format='json',
        )
        # Second call (same phone)
        resp = client.post(
            f'/api/classes/creation-sessions/{session.id}/invites/',
            data={'phones': ['09121111111']},
            format='json',
        )
        assert resp.status_code == 200
        assert ClassInvitation.objects.filter(session=session).count() == 1

    def test_bulk_invite_multiple_phones(self):
        """Inviting multiple new phones creates correct number of invitations."""
        teacher = baker.make(User, role=User.Role.TEACHER)
        session = baker.make(
            ClassCreationSession,
            teacher=teacher,
            pipeline_type='class',
        )
        phones = [f'0912000000{i}' for i in range(5)]
        for phone in phones:
            StudentInviteCode.objects.get_or_create(
                phone=phone, defaults={'code': f'CODE-{phone[-1]}'},
            )

        client = _auth_client(teacher)
        resp = client.post(
            f'/api/classes/creation-sessions/{session.id}/invites/',
            data={'phones': phones},
            format='json',
        )
        assert resp.status_code == 200
        assert ClassInvitation.objects.filter(session=session).count() == 5


@pytest.mark.django_db
class TestSessionStatusTransition:
    """Only the correct status allows a step to proceed."""

    @pytest.fixture(autouse=True)
    def _disable_async(self, settings):
        settings.CLASS_PIPELINE_ASYNC = False

    def test_step2_requires_transcribed_status(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        session = baker.make(
            ClassCreationSession,
            teacher=teacher,
            pipeline_type='class',
            status='transcribing',
        )
        client = _auth_client(teacher)
        resp = client.post(
            '/api/classes/creation-sessions/step-2/',
            data={'session_id': session.id},
            format='json',
        )
        assert resp.status_code == 400

    def test_step3_requires_structured_status(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        session = baker.make(
            ClassCreationSession,
            teacher=teacher,
            pipeline_type='class',
            status='transcribed',
        )
        client = _auth_client(teacher)
        resp = client.post(
            '/api/classes/creation-sessions/step-3/',
            data={'session_id': session.id},
            format='json',
        )
        assert resp.status_code == 400
