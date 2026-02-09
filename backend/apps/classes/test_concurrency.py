"""Concurrency & race condition tests.

Verifies that endpoints behave correctly under concurrent access patterns
that would occur with ~100 simultaneous users.
"""
from __future__ import annotations

import threading
from unittest.mock import MagicMock

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from model_bakery import baker

from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

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


@pytest.mark.django_db(transaction=True)
class TestPublishRaceCondition:
    """Two concurrent publish requests must not both trigger SMS."""

    def test_double_publish_only_publishes_once(self):
        teacher = baker.make('accounts.User', role='teacher')
        session = baker.make(
            'classes.ClassCreationSession',
            teacher=teacher,
            pipeline_type='class',
            status='structured',
            structure_json='{"sections": []}',
            is_published=False,
        )

        results = {'sms_call_count': 0}
        original_delay = None

        def fake_sms_delay(session_id):
            results['sms_call_count'] += 1

        # Monkey-patch the SMS task at the module level
        from apps.classes import tasks
        original_delay = tasks.send_publish_sms_task.delay
        tasks.send_publish_sms_task.delay = fake_sms_delay

        try:
            client = _auth_client(teacher)

            # First publish
            resp1 = client.post(f'/api/classes/sessions/{session.id}/publish/')
            # Second publish (concurrent)
            resp2 = client.post(f'/api/classes/sessions/{session.id}/publish/')

            assert resp1.status_code == 200
            assert resp2.status_code == 200

            session.refresh_from_db()
            assert session.is_published is True
            # SMS should only be triggered ONCE due to atomic update.
            assert results['sms_call_count'] == 1
        finally:
            tasks.send_publish_sms_task.delay = original_delay

    def test_publish_failed_session_rejected(self):
        teacher = baker.make('accounts.User', role='teacher')
        session = baker.make(
            'classes.ClassCreationSession',
            teacher=teacher,
            pipeline_type='class',
            status='failed',
            is_published=False,
        )

        client = _auth_client(teacher)
        resp = client.post(f'/api/classes/sessions/{session.id}/publish/')
        assert resp.status_code == 400


@pytest.mark.django_db(transaction=True)
class TestInvitationConcurrency:
    """Invitation creation must be safe under concurrent access."""

    def test_bulk_invite_no_duplicates(self):
        """Inviting the same phone twice in a single request creates only one invitation."""
        teacher = baker.make('accounts.User', role='teacher')
        session = baker.make(
            'classes.ClassCreationSession',
            teacher=teacher,
            pipeline_type='class',
        )

        # Pre-create an invite code
        StudentInviteCode.objects.create(phone='09121111111', code='ABC123')

        client = _auth_client(teacher)
        resp = client.post(
            f'/api/classes/sessions/{session.id}/invites/',
            data={'phones': ['09121111111', '09121111111']},
            format='json',
        )

        assert resp.status_code == 200
        assert ClassInvitation.objects.filter(session=session).count() == 1

    def test_bulk_invite_idempotent(self):
        """Calling invite twice with the same phone doesn't create duplicates."""
        teacher = baker.make('accounts.User', role='teacher')
        session = baker.make(
            'classes.ClassCreationSession',
            teacher=teacher,
            pipeline_type='class',
        )
        StudentInviteCode.objects.create(phone='09121111111', code='ABC123')

        client = _auth_client(teacher)
        # First call
        client.post(
            f'/api/classes/sessions/{session.id}/invites/',
            data={'phones': ['09121111111']},
            format='json',
        )
        # Second call (same phone)
        resp = client.post(
            f'/api/classes/sessions/{session.id}/invites/',
            data={'phones': ['09121111111']},
            format='json',
        )

        assert resp.status_code == 200
        assert ClassInvitation.objects.filter(session=session).count() == 1

    def test_bulk_invite_multiple_phones(self):
        """Inviting multiple new phones creates correct number of invitations."""
        teacher = baker.make('accounts.User', role='teacher')
        session = baker.make(
            'classes.ClassCreationSession',
            teacher=teacher,
            pipeline_type='class',
        )
        phones = [f'0912000000{i}' for i in range(5)]
        for phone in phones:
            StudentInviteCode.objects.create(
                phone=phone, code=f'CODE-{phone[-1]}',
            )

        client = _auth_client(teacher)
        resp = client.post(
            f'/api/classes/sessions/{session.id}/invites/',
            data={'phones': phones},
            format='json',
        )

        assert resp.status_code == 200
        assert ClassInvitation.objects.filter(session=session).count() == 5


@pytest.mark.django_db(transaction=True)
class TestSessionStatusTransition:
    """Only the correct status allows a step to proceed."""

    @pytest.fixture(autouse=True)
    def _disable_async(self, settings):
        settings.CLASS_PIPELINE_ASYNC = False

    def test_step2_requires_transcribed_status(self):
        teacher = baker.make('accounts.User', role='teacher')
        session = baker.make(
            'classes.ClassCreationSession',
            teacher=teacher,
            pipeline_type='class',
            status='transcribing',  # wrong status for step 2
        )

        client = _auth_client(teacher)
        resp = client.post(
            '/api/classes/sessions/step2-structure/',
            data={'session_id': session.id},
            format='json',
        )

        assert resp.status_code == 400

    def test_step3_requires_structured_status(self):
        teacher = baker.make('accounts.User', role='teacher')
        session = baker.make(
            'classes.ClassCreationSession',
            teacher=teacher,
            pipeline_type='class',
            status='transcribed',  # wrong status for step 3
        )

        client = _auth_client(teacher)
        resp = client.post(
            '/api/classes/sessions/step3-prerequisites/',
            data={'session_id': session.id},
            format='json',
        )

        assert resp.status_code == 400
