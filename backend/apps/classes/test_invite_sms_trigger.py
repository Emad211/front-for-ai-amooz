"""Tests for SMS triggers on post-publish invite additions.

Covers:
- send_invite_sms_for_ids (service layer)
- send_new_invites_sms_task (celery task)
- ClassInvitationListCreateView triggers SMS for already-published sessions
- ExamPrepInvitationListCreateView triggers SMS for already-published sessions
- No SMS is sent when session is NOT published
"""
import pytest
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.classes.models import ClassCreationSession, ClassInvitation
from apps.classes.services.mediana_sms import send_invite_sms_for_ids

User = get_user_model()


_counter = 0


def _teacher_client() -> tuple[APIClient, 'User']:
    global _counter
    _counter += 1
    user = User.objects.create_user(
        username=f'sms_teacher_{_counter}', password='pass', role=User.Role.TEACHER,
    )
    token = str(RefreshToken.for_user(user).access_token)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return client, user


def _make_session(teacher, *, published=False, pipeline_type='class', status_val=None):
    """Create a minimal ClassCreationSession for testing."""
    from django.utils import timezone

    st = status_val or ClassCreationSession.Status.STRUCTURED
    if pipeline_type == 'exam_prep':
        st = status_val or ClassCreationSession.Status.EXAM_STRUCTURED

    return ClassCreationSession.objects.create(
        teacher=teacher,
        title='Test Session',
        description='',
        source_file=SimpleUploadedFile('audio.ogg', b'fake', content_type='audio/ogg'),
        source_mime_type='audio/ogg',
        source_original_name='audio.ogg',
        status=st,
        transcript_markdown='hello',
        structure_json='{"root_object": {"title": "x"}, "outline": []}',
        is_published=published,
        published_at=timezone.now() if published else None,
        pipeline_type=pipeline_type,
    )


# ===========================================================================
# Service layer: send_invite_sms_for_ids
# ===========================================================================


@pytest.mark.django_db
class TestSendInviteSmsForIds:
    """Tests for the targeted invite SMS function."""

    def test_skips_when_no_api_key(self, monkeypatch):
        from model_bakery import baker

        monkeypatch.delenv('MEDIANA_API_KEY', raising=False)
        session = baker.make('classes.ClassCreationSession')
        # Should not raise.
        send_invite_sms_for_ids(session.id, [1, 2, 3])

    def test_skips_when_session_not_found(self, monkeypatch):
        monkeypatch.setenv('MEDIANA_API_KEY', 'test-key')
        send_invite_sms_for_ids(99999, [1])

    def test_skips_when_no_matching_invites(self, monkeypatch):
        from model_bakery import baker

        monkeypatch.setenv('MEDIANA_API_KEY', 'test-key')
        session = baker.make('classes.ClassCreationSession')
        # IDs that don't exist.
        send_invite_sms_for_ids(session.id, [99998, 99999])

    def test_sends_sms_for_specific_invites(self, monkeypatch):
        from model_bakery import baker

        monkeypatch.setenv('MEDIANA_API_KEY', 'test-key')
        session = baker.make('classes.ClassCreationSession', title='Test Class')
        inv1 = baker.make('classes.ClassInvitation', session=session, phone='09121111111', invite_code='A1')
        inv2 = baker.make('classes.ClassInvitation', session=session, phone='09122222222', invite_code='A2')
        inv3 = baker.make('classes.ClassInvitation', session=session, phone='09123333333', invite_code='A3')

        calls = []
        fake_result = {
            'meta': {'errorMessage': None},
            'data': {'TotalSent': 2, 'TotalRequested': 2},
        }

        def fake_send(**kw):
            calls.append(kw)
            return fake_result

        monkeypatch.setattr(
            'apps.classes.services.mediana_sms.send_peer_to_peer_sms',
            fake_send,
        )

        # Only send to inv1 and inv2, NOT inv3.
        send_invite_sms_for_ids(session.id, [inv1.id, inv2.id])

        assert len(calls) == 1
        assert len(calls[0]['requests']) == 2
        phones_sent = {r['Recipients'][0] for r in calls[0]['requests']}
        assert phones_sent == {'09121111111', '09122222222'}


# ===========================================================================
# View layer: SMS triggered on adding invites to published sessions
# ===========================================================================


@pytest.mark.django_db
class TestClassInviteSmsOnPublishedSession:
    """Adding invites to an already-published class session should trigger SMS."""

    def test_sms_sent_when_session_published(self, monkeypatch):
        client, teacher = _teacher_client()
        session = _make_session(teacher, published=True, pipeline_type='class')

        fake_task = MagicMock()
        monkeypatch.setattr('apps.classes.views.send_new_invites_sms_task', fake_task)
        monkeypatch.setattr(
            'django.db.transaction.on_commit',
            lambda func, using=None, robust=False: func(),
        )

        res = client.post(
            f'/api/classes/creation-sessions/{session.id}/invites/',
            {'phones': ['09121111111']},
            format='json',
        )
        assert res.status_code == 200
        # SMS task should have been dispatched.
        fake_task.delay.assert_called_once()
        call_args = fake_task.delay.call_args
        assert call_args[0][0] == session.id
        assert len(call_args[0][1]) == 1  # 1 invite ID

    def test_no_sms_when_session_not_published(self, monkeypatch):
        client, teacher = _teacher_client()
        session = _make_session(teacher, published=False, pipeline_type='class')

        fake_task = MagicMock()
        monkeypatch.setattr('apps.classes.views.send_new_invites_sms_task', fake_task)

        res = client.post(
            f'/api/classes/creation-sessions/{session.id}/invites/',
            {'phones': ['09121111111']},
            format='json',
        )
        assert res.status_code == 200
        # SMS task should NOT have been dispatched.
        fake_task.delay.assert_not_called()

    def test_no_sms_when_no_new_invites(self, monkeypatch):
        """If all phones already exist, no SMS is sent."""
        client, teacher = _teacher_client()
        session = _make_session(teacher, published=True, pipeline_type='class')

        # Pre-create the invite.
        ClassInvitation.objects.create(session=session, phone='09121111111', invite_code='X1')

        fake_task = MagicMock()
        monkeypatch.setattr('apps.classes.views.send_new_invites_sms_task', fake_task)

        res = client.post(
            f'/api/classes/creation-sessions/{session.id}/invites/',
            {'phones': ['09121111111']},
            format='json',
        )
        assert res.status_code == 200
        fake_task.delay.assert_not_called()

    def test_sms_only_for_new_invites_not_existing(self, monkeypatch):
        """When adding mix of new and existing phones, SMS only sent for new."""
        client, teacher = _teacher_client()
        session = _make_session(teacher, published=True, pipeline_type='class')

        # Pre-create one invite.
        ClassInvitation.objects.create(session=session, phone='09121111111', invite_code='X1')

        fake_task = MagicMock()
        monkeypatch.setattr('apps.classes.views.send_new_invites_sms_task', fake_task)
        monkeypatch.setattr(
            'django.db.transaction.on_commit',
            lambda func, using=None, robust=False: func(),
        )

        res = client.post(
            f'/api/classes/creation-sessions/{session.id}/invites/',
            {'phones': ['09121111111', '09122222222']},  # 1 existing, 1 new
            format='json',
        )
        assert res.status_code == 200
        fake_task.delay.assert_called_once()
        call_args = fake_task.delay.call_args
        assert len(call_args[0][1]) == 1  # only 1 new invite ID


@pytest.mark.django_db
class TestExamPrepInviteSmsOnPublishedSession:
    """Adding invites to an already-published exam-prep session should trigger SMS."""

    def test_sms_sent_when_session_published(self, monkeypatch):
        client, teacher = _teacher_client()
        session = _make_session(teacher, published=True, pipeline_type='exam_prep')

        fake_task = MagicMock()
        monkeypatch.setattr('apps.classes.views.send_new_invites_sms_task', fake_task)
        monkeypatch.setattr(
            'django.db.transaction.on_commit',
            lambda func, using=None, robust=False: func(),
        )

        res = client.post(
            f'/api/classes/exam-prep-sessions/{session.id}/invites/',
            {'phones': ['09121111111']},
            format='json',
        )
        assert res.status_code == 200
        fake_task.delay.assert_called_once()
        call_args = fake_task.delay.call_args
        assert call_args[0][0] == session.id

    def test_no_sms_when_session_not_published(self, monkeypatch):
        client, teacher = _teacher_client()
        session = _make_session(teacher, published=False, pipeline_type='exam_prep')

        fake_task = MagicMock()
        monkeypatch.setattr('apps.classes.views.send_new_invites_sms_task', fake_task)

        res = client.post(
            f'/api/classes/exam-prep-sessions/{session.id}/invites/',
            {'phones': ['09121111111']},
            format='json',
        )
        assert res.status_code == 200
        fake_task.delay.assert_not_called()
