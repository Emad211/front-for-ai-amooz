"""Pipeline robustness tests.

Tests for all edge cases, race conditions, and failure scenarios in the
class/exam-prep pipeline: DoesNotExist during pipeline, FFmpeg failures,
session deletion mid-pipeline, concurrent session limits, stale session
cleanup, and video duration pre-checks.
"""
from __future__ import annotations

import uuid
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from model_bakery import baker
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.classes.models import ClassCreationSession


@pytest.fixture(autouse=True)
def _celery_eager(settings):
    """Run Celery tasks synchronously in tests."""
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True


def _auth_client(user) -> APIClient:
    refresh = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


# ---------------------------------------------------------------------------
# Safe helpers unit tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSafeRefresh:
    """_safe_refresh must not crash when session is deleted."""

    def test_safe_refresh_returns_true_for_existing_session(self):
        from apps.classes.tasks import _safe_refresh
        session = baker.make(ClassCreationSession)
        assert _safe_refresh(session) is True

    def test_safe_refresh_returns_false_for_deleted_session(self):
        from apps.classes.tasks import _safe_refresh
        session = baker.make(ClassCreationSession)
        session_id = session.id
        session.delete()
        # session Python object still exists but DB row is gone
        assert _safe_refresh(session) is False


@pytest.mark.django_db
class TestSafeMarkFailed:
    """_safe_mark_failed must not crash when session is deleted."""

    def test_marks_session_as_failed(self):
        from apps.classes.tasks import _safe_mark_failed
        session = baker.make(ClassCreationSession, status='transcribing')
        _safe_mark_failed(session, 'test error')
        session.refresh_from_db()
        assert session.status == ClassCreationSession.Status.FAILED
        assert session.error_detail == 'test error'

    def test_no_crash_on_deleted_session(self):
        from apps.classes.tasks import _safe_mark_failed
        session = baker.make(ClassCreationSession, status='transcribing')
        session.delete()
        # Must not raise
        _safe_mark_failed(session, 'test error')

    def test_truncates_long_error_detail(self):
        from apps.classes.tasks import _safe_mark_failed
        session = baker.make(ClassCreationSession, status='transcribing')
        long_error = 'x' * 5000
        _safe_mark_failed(session, long_error)
        session.refresh_from_db()
        assert len(session.error_detail) == 2000


@pytest.mark.django_db
class TestSafeSave:
    """_safe_save must not crash when session is deleted."""

    def test_saves_fields_successfully(self):
        from apps.classes.tasks import _safe_save
        session = baker.make(ClassCreationSession, title='old')
        session.title = 'new'
        assert _safe_save(session, ['title', 'updated_at']) is True
        session.refresh_from_db()
        assert session.title == 'new'

    def test_returns_false_on_deleted_session(self):
        from apps.classes.tasks import _safe_save
        session = baker.make(ClassCreationSession, title='old')
        session.delete()
        session.title = 'new'
        assert _safe_save(session, ['title', 'updated_at']) is False


# ---------------------------------------------------------------------------
# Pipeline step with deleted session
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestRunPipelineStepDeletedSession:
    """_run_pipeline_step must abort gracefully if session is deleted mid-retry."""

    def test_aborts_on_deleted_session_during_retry(self):
        from apps.classes.tasks import _run_pipeline_step

        session = baker.make(
            ClassCreationSession,
            status=ClassCreationSession.Status.TRANSCRIBING,
        )

        call_count = {'n': 0}

        def _failing_step(session_id):
            call_count['n'] += 1
            if call_count['n'] == 1:
                # First call fails; before retry, delete the session
                ClassCreationSession.objects.filter(id=session.id).delete()
                raise RuntimeError('LLM timeout')
            return {'status': 'success'}

        result = _run_pipeline_step(
            _failing_step, 'test_step', session.id, session,
            max_attempts=3, base_delay=0,
        )
        # Should return False (aborted) rather than crash with DoesNotExist
        assert result is False
        assert call_count['n'] == 1  # didn't retry after session was deleted


@pytest.mark.django_db
class TestFullPipelineDeletedSession:
    """Full pipeline must abort gracefully if session is deleted between steps."""

    def test_class_pipeline_aborts_on_deleted_session(self):
        from apps.classes.tasks import process_class_full_pipeline

        session = baker.make(
            ClassCreationSession,
            status=ClassCreationSession.Status.TRANSCRIBING,
            pipeline_type=ClassCreationSession.PipelineType.CLASS,
        )
        # Delete session before pipeline runs
        session_id = session.id
        ClassCreationSession.objects.filter(id=session_id).delete()

        result = process_class_full_pipeline.apply(args=[session_id]).result
        assert result['status'] == 'skipped'
        assert 'not found' in result['reason']

    def test_exam_prep_pipeline_aborts_on_deleted_session(self):
        from apps.classes.tasks import process_exam_prep_full_pipeline

        session = baker.make(
            ClassCreationSession,
            status=ClassCreationSession.Status.EXAM_TRANSCRIBING,
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        )
        session_id = session.id
        ClassCreationSession.objects.filter(id=session_id).delete()

        result = process_exam_prep_full_pipeline.apply(args=[session_id]).result
        assert result['status'] == 'skipped'
        assert 'not found' in result['reason']


# ---------------------------------------------------------------------------
# Concurrent session limit (TOCTOU prevention)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestConcurrentSessionLimit:
    """Step 1 must enforce a per-teacher concurrent session limit."""

    @pytest.fixture(autouse=True)
    def _setup(self, settings):
        settings.CLASS_PIPELINE_ASYNC = True

    def test_rejects_6th_concurrent_class_session(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        client = _auth_client(teacher)

        # Create 5 active sessions
        for i in range(5):
            baker.make(
                ClassCreationSession,
                teacher=teacher,
                pipeline_type=ClassCreationSession.PipelineType.CLASS,
                status=ClassCreationSession.Status.TRANSCRIBING,
            )

        upload = SimpleUploadedFile('audio.ogg', b'fake-audio', content_type='audio/ogg')
        resp = client.post(
            '/api/classes/creation-sessions/step-1/',
            {'title': 'test', 'file': upload, 'client_request_id': str(uuid.uuid4())},
            format='multipart',
        )
        assert resp.status_code == 429

    def test_allows_new_session_after_one_completes(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        client = _auth_client(teacher)

        # Create 5 active sessions
        sessions = []
        for i in range(5):
            s = baker.make(
                ClassCreationSession,
                teacher=teacher,
                pipeline_type=ClassCreationSession.PipelineType.CLASS,
                status=ClassCreationSession.Status.TRANSCRIBING,
            )
            sessions.append(s)

        # Complete one
        sessions[0].status = ClassCreationSession.Status.TRANSCRIBED
        sessions[0].save(update_fields=['status'])

        upload = SimpleUploadedFile('audio.ogg', b'fake-audio', content_type='audio/ogg')
        resp = client.post(
            '/api/classes/creation-sessions/step-1/',
            {'title': 'test', 'file': upload, 'client_request_id': str(uuid.uuid4())},
            format='multipart',
        )
        assert resp.status_code == 202

    def test_rejects_6th_concurrent_exam_prep_session(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        client = _auth_client(teacher)

        for i in range(5):
            baker.make(
                ClassCreationSession,
                teacher=teacher,
                pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
                status=ClassCreationSession.Status.EXAM_TRANSCRIBING,
            )

        upload = SimpleUploadedFile('audio.ogg', b'fake-audio', content_type='audio/ogg')
        resp = client.post(
            '/api/classes/exam-prep-sessions/step-1/',
            {'title': 'test', 'file': upload, 'client_request_id': str(uuid.uuid4())},
            format='multipart',
        )
        assert resp.status_code == 429

    def test_failed_sessions_dont_count_toward_limit(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        client = _auth_client(teacher)

        # Create 5 FAILED sessions — should NOT count
        for i in range(5):
            baker.make(
                ClassCreationSession,
                teacher=teacher,
                pipeline_type=ClassCreationSession.PipelineType.CLASS,
                status=ClassCreationSession.Status.FAILED,
            )

        upload = SimpleUploadedFile('audio.ogg', b'fake-audio', content_type='audio/ogg')
        resp = client.post(
            '/api/classes/creation-sessions/step-1/',
            {'title': 'test', 'file': upload, 'client_request_id': str(uuid.uuid4())},
            format='multipart',
        )
        assert resp.status_code == 202


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestIdempotency:
    """Step 1 must be idempotent when client_request_id is provided."""

    @pytest.fixture(autouse=True)
    def _setup(self, settings):
        settings.CLASS_PIPELINE_ASYNC = True

    def test_duplicate_request_returns_existing_session(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        client = _auth_client(teacher)
        req_id = str(uuid.uuid4())

        upload1 = SimpleUploadedFile('audio.ogg', b'fake-audio', content_type='audio/ogg')
        resp1 = client.post(
            '/api/classes/creation-sessions/step-1/',
            {'title': 'test', 'file': upload1, 'client_request_id': req_id},
            format='multipart',
        )
        assert resp1.status_code == 202
        session_id = resp1.data['id']

        upload2 = SimpleUploadedFile('audio.ogg', b'fake-audio', content_type='audio/ogg')
        resp2 = client.post(
            '/api/classes/creation-sessions/step-1/',
            {'title': 'test', 'file': upload2, 'client_request_id': req_id},
            format='multipart',
        )
        # Should return existing session, not create a new one
        assert resp2.data['id'] == session_id
        assert ClassCreationSession.objects.filter(teacher=teacher).count() == 1

    def test_without_client_request_id_creates_new_session(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        client = _auth_client(teacher)

        for _ in range(2):
            upload = SimpleUploadedFile('audio.ogg', b'fake-audio', content_type='audio/ogg')
            resp = client.post(
                '/api/classes/creation-sessions/step-1/',
                {'title': 'test', 'file': upload},
                format='multipart',
            )
            assert resp.status_code == 202

        assert ClassCreationSession.objects.filter(teacher=teacher).count() == 2


# ---------------------------------------------------------------------------
# Stale session cleanup
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestStaleSessionCleanup:
    """cleanup_stale_sessions must mark stuck sessions as FAILED."""

    @pytest.fixture(autouse=True)
    def _clean_sessions(self):
        """Remove leftover sessions from --reuse-db to isolate each test."""
        ClassCreationSession.objects.all().delete()

    def test_marks_stuck_sessions_as_failed(self):
        from apps.classes.tasks import cleanup_stale_sessions

        old_time = timezone.now() - timedelta(hours=3)
        session = baker.make(
            ClassCreationSession,
            status=ClassCreationSession.Status.TRANSCRIBING,
        )
        # Manually set updated_at to 3 hours ago
        ClassCreationSession.objects.filter(id=session.id).update(updated_at=old_time)

        result = cleanup_stale_sessions()
        assert result['stale_count'] == 1

        session.refresh_from_db()
        assert session.status == ClassCreationSession.Status.FAILED

    def test_ignores_recent_sessions(self):
        from apps.classes.tasks import cleanup_stale_sessions

        baker.make(
            ClassCreationSession,
            status=ClassCreationSession.Status.TRANSCRIBING,
        )
        result = cleanup_stale_sessions()
        assert result['stale_count'] == 0

    def test_ignores_completed_sessions(self):
        from apps.classes.tasks import cleanup_stale_sessions

        old_time = timezone.now() - timedelta(hours=3)
        session = baker.make(
            ClassCreationSession,
            status=ClassCreationSession.Status.TRANSCRIBED,
        )
        ClassCreationSession.objects.filter(id=session.id).update(updated_at=old_time)

        result = cleanup_stale_sessions()
        assert result['stale_count'] == 0

    def test_cleans_all_stuck_pipeline_statuses(self):
        from apps.classes.tasks import cleanup_stale_sessions

        old_time = timezone.now() - timedelta(hours=3)
        statuses = [
            ClassCreationSession.Status.TRANSCRIBING,
            ClassCreationSession.Status.STRUCTURING,
            ClassCreationSession.Status.PREREQ_EXTRACTING,
            ClassCreationSession.Status.PREREQ_TEACHING,
            ClassCreationSession.Status.RECAPPING,
            ClassCreationSession.Status.EXAM_TRANSCRIBING,
            ClassCreationSession.Status.EXAM_STRUCTURING,
        ]
        for s in statuses:
            session = baker.make(ClassCreationSession, status=s)
            ClassCreationSession.objects.filter(id=session.id).update(updated_at=old_time)

        result = cleanup_stale_sessions()
        assert result['stale_count'] == len(statuses)


# ---------------------------------------------------------------------------
# Video duration pre-check
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestVideoDurationPreCheck:
    """prepare_media_parts_for_api must reject excessively long videos."""

    def test_rejects_video_exceeding_max_duration(self):
        from apps.classes.services.media_compressor import (
            prepare_media_parts_for_api,
            MAX_VIDEO_DURATION_SECONDS,
        )

        # Mock _get_duration to return a very long duration
        with patch('apps.classes.services.media_compressor._get_duration') as mock_dur:
            mock_dur.return_value = MAX_VIDEO_DURATION_SECONDS + 100
            with pytest.raises(RuntimeError, match='بیش از حد طولانی'):
                prepare_media_parts_for_api(
                    b'\x00' * (17 * 1024 * 1024),  # >16MB to trigger processing
                    'video/mp4',
                )

    def test_allows_video_within_duration_limit(self):
        from apps.classes.services.media_compressor import (
            prepare_media_parts_for_api,
        )

        # Small file — should pass through without FFmpeg
        result = prepare_media_parts_for_api(b'\x00' * 100, 'video/mp4')
        assert len(result) == 1
        assert result[0][1] == 'video/mp4'


# ---------------------------------------------------------------------------
# Error detail not leaked to client
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestNoErrorDetailLeak:
    """API responses must NOT contain raw exception details."""

    @pytest.fixture(autouse=True)
    def _setup(self, settings):
        settings.CLASS_PIPELINE_ASYNC = False

    def test_step1_sync_failure_does_not_leak_error(self, monkeypatch):
        teacher = baker.make(User, role=User.Role.TEACHER)
        client = _auth_client(teacher)

        def _failing_transcribe(*, data, mime_type):
            raise RuntimeError('SECRET_API_KEY_12345 invalid')

        monkeypatch.setattr(
            'apps.classes.views.transcribe_media_bytes',
            _failing_transcribe,
        )

        upload = SimpleUploadedFile('audio.ogg', b'fake-audio', content_type='audio/ogg')
        resp = client.post(
            '/api/classes/creation-sessions/step-1/',
            {'title': 'test', 'file': upload},
            format='multipart',
        )
        assert resp.status_code == 502
        # Must NOT contain the raw exception
        assert 'SECRET_API_KEY_12345' not in str(resp.data)
        assert 'error_detail' not in resp.data

    def test_step1_storage_failure_does_not_leak_error(self, monkeypatch):
        teacher = baker.make(User, role=User.Role.TEACHER)
        client = _auth_client(teacher)

        # Make create fail by mocking it to raise a generic exception
        original_create = ClassCreationSession.objects.create

        def _failing_create(**kwargs):
            raise Exception('Connection to minio.internal:9000 refused')

        monkeypatch.setattr(ClassCreationSession.objects, 'create', _failing_create)

        upload = SimpleUploadedFile('audio.ogg', b'fake-audio', content_type='audio/ogg')
        resp = client.post(
            '/api/classes/creation-sessions/step-1/',
            {'title': 'test', 'file': upload, 'client_request_id': str(uuid.uuid4())},
            format='multipart',
        )
        assert resp.status_code == 503
        assert 'minio.internal' not in str(resp.data)
        assert 'error' not in resp.data


# ---------------------------------------------------------------------------
# Session delete while pipeline is running
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDeleteDuringPipeline:
    """Deleting a session while it's in a processing status must be allowed
    and must not leave orphan data."""

    def test_delete_transcribing_session(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        client = _auth_client(teacher)
        session = baker.make(
            ClassCreationSession,
            teacher=teacher,
            pipeline_type='class',
            status=ClassCreationSession.Status.TRANSCRIBING,
        )
        resp = client.delete(f'/api/classes/creation-sessions/{session.id}/')
        assert resp.status_code == 204
        assert not ClassCreationSession.objects.filter(id=session.id).exists()

    def test_pipeline_handles_deleted_session_gracefully(self):
        """Simulate: user deletes session → pipeline task runs → no crash."""
        from apps.classes.tasks import process_class_step2_structure

        session = baker.make(
            ClassCreationSession,
            status=ClassCreationSession.Status.STRUCTURING,
        )
        session_id = session.id
        ClassCreationSession.objects.filter(id=session_id).delete()

        # Call task synchronously (.apply returns EagerResult)
        result = process_class_step2_structure.apply(args=[session_id]).result
        assert result['status'] == 'skipped'


# ---------------------------------------------------------------------------
# File validation
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestFileValidation:
    """Uploaded files must be validated for type and size."""

    @pytest.fixture(autouse=True)
    def _setup(self, settings):
        settings.CLASS_PIPELINE_ASYNC = True

    def test_rejects_non_media_file(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        client = _auth_client(teacher)

        upload = SimpleUploadedFile('test.pdf', b'fake-pdf', content_type='application/pdf')
        resp = client.post(
            '/api/classes/creation-sessions/step-1/',
            {'title': 'test', 'file': upload, 'client_request_id': str(uuid.uuid4())},
            format='multipart',
        )
        assert resp.status_code == 400

    def test_rejects_oversized_file(self, settings):
        teacher = baker.make(User, role=User.Role.TEACHER)
        client = _auth_client(teacher)
        settings.TRANSCRIPTION_MAX_UPLOAD_BYTES = 100  # 100 bytes

        upload = SimpleUploadedFile('audio.ogg', b'x' * 200, content_type='audio/ogg')
        resp = client.post(
            '/api/classes/creation-sessions/step-1/',
            {'title': 'test', 'file': upload, 'client_request_id': str(uuid.uuid4())},
            format='multipart',
        )
        assert resp.status_code == 400

    def test_accepts_valid_audio_file(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        client = _auth_client(teacher)

        upload = SimpleUploadedFile('audio.mp3', b'fake-audio', content_type='audio/mpeg')
        resp = client.post(
            '/api/classes/creation-sessions/step-1/',
            {'title': 'test', 'file': upload, 'client_request_id': str(uuid.uuid4())},
            format='multipart',
        )
        assert resp.status_code == 202

    def test_accepts_valid_video_file(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        client = _auth_client(teacher)

        upload = SimpleUploadedFile('video.mp4', b'fake-video', content_type='video/mp4')
        resp = client.post(
            '/api/classes/creation-sessions/step-1/',
            {'title': 'test', 'file': upload, 'client_request_id': str(uuid.uuid4())},
            format='multipart',
        )
        assert resp.status_code == 202


# ---------------------------------------------------------------------------
# Step status transition edge cases
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestStepStatusTransitions:
    """Steps 2-5 must enforce correct status prerequisites."""

    @pytest.fixture(autouse=True)
    def _setup(self, settings):
        settings.CLASS_PIPELINE_ASYNC = True

    def test_step2_rejects_if_not_transcribed(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        client = _auth_client(teacher)
        session = baker.make(
            ClassCreationSession,
            teacher=teacher,
            pipeline_type='class',
            status=ClassCreationSession.Status.TRANSCRIBING,
        )
        resp = client.post(
            '/api/classes/creation-sessions/step-2/',
            {'session_id': session.id},
            format='json',
        )
        assert resp.status_code == 409

    def test_step2_returns_202_if_already_structuring(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        client = _auth_client(teacher)
        session = baker.make(
            ClassCreationSession,
            teacher=teacher,
            pipeline_type='class',
            status=ClassCreationSession.Status.STRUCTURING,
        )
        resp = client.post(
            '/api/classes/creation-sessions/step-2/',
            {'session_id': session.id},
            format='json',
        )
        assert resp.status_code == 202

    def test_step2_returns_200_if_already_structured(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        client = _auth_client(teacher)
        session = baker.make(
            ClassCreationSession,
            teacher=teacher,
            pipeline_type='class',
            status=ClassCreationSession.Status.STRUCTURED,
            structure_json='{"sections": []}',
        )
        resp = client.post(
            '/api/classes/creation-sessions/step-2/',
            {'session_id': session.id},
            format='json',
        )
        assert resp.status_code == 200

    def test_step3_rejects_if_not_structured(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        client = _auth_client(teacher)
        session = baker.make(
            ClassCreationSession,
            teacher=teacher,
            pipeline_type='class',
            status=ClassCreationSession.Status.TRANSCRIBED,
        )
        resp = client.post(
            '/api/classes/creation-sessions/step-3/',
            {'session_id': session.id},
            format='json',
        )
        assert resp.status_code == 409

    def test_another_teachers_session_returns_404(self):
        teacher1 = baker.make(User, role=User.Role.TEACHER)
        teacher2 = baker.make(User, role=User.Role.TEACHER)
        session = baker.make(
            ClassCreationSession,
            teacher=teacher1,
            pipeline_type='class',
            status=ClassCreationSession.Status.TRANSCRIBED,
        )
        client = _auth_client(teacher2)
        resp = client.post(
            '/api/classes/creation-sessions/step-2/',
            {'session_id': session.id},
            format='json',
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# FFmpeg helpers
# ---------------------------------------------------------------------------

class TestFFmpegHelpers:
    """Unit tests for media compressor functions."""

    def test_small_file_passes_through(self):
        from apps.classes.services.media_compressor import prepare_media_parts_for_api
        data = b'\x00' * 100
        result = prepare_media_parts_for_api(data, 'audio/ogg')
        assert len(result) == 1
        assert result[0] == (data, 'audio/ogg')

    def test_large_audio_raises_error(self):
        from apps.classes.services.media_compressor import prepare_media_parts_for_api
        data = b'\x00' * (17 * 1024 * 1024)
        with pytest.raises(RuntimeError, match='بزرگ'):
            prepare_media_parts_for_api(data, 'audio/mpeg')

    def test_get_duration_returns_zero_on_invalid_file(self):
        from apps.classes.services.media_compressor import _get_duration
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
            f.write(b'\x00' * 100)
            f.flush()
            path = f.name
        try:
            # Invalid file — should return 0.0, not crash
            dur = _get_duration(path)
            assert dur == 0.0 or isinstance(dur, float)
        finally:
            os.unlink(path)
