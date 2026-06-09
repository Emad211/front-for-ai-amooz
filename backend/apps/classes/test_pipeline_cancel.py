"""Pipeline cancellation tests.

Covers the cancel endpoints (class + exam-prep), the cooperative-cancellation
checkpoints inside the full-pipeline tasks, the hard Celery revoke, ownership
and status guards, and the model helpers.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from model_bakery import baker
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.classes.models import ClassCreationSession

Status = ClassCreationSession.Status
PipelineType = ClassCreationSession.PipelineType


def _auth_client(user) -> APIClient:
    refresh = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


@pytest.fixture(autouse=True)
def _celery_eager(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True


CLASS_CANCEL = '/api/classes/creation-sessions/{}/cancel/'
EXAM_CANCEL = '/api/classes/exam-prep-sessions/{}/cancel/'


# ---------------------------------------------------------------------------
# Model helpers
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestModelHelpers:
    @pytest.mark.parametrize('status', [
        Status.TRANSCRIBING, Status.STRUCTURING, Status.PREREQ_EXTRACTING,
        Status.PREREQ_TEACHING, Status.RECAPPING, Status.EXAM_TRANSCRIBING,
        Status.EXAM_STRUCTURING, Status.TRANSCRIBED, Status.STRUCTURED,
    ])
    def test_active_statuses_are_cancellable(self, status):
        session = baker.make(ClassCreationSession, status=status)
        assert session.is_active_pipeline is True

    @pytest.mark.parametrize('status', [
        Status.RECAPPED, Status.EXAM_STRUCTURED, Status.FAILED, Status.CANCELLED,
    ])
    def test_terminal_statuses_are_not_cancellable(self, status):
        session = baker.make(ClassCreationSession, status=status)
        assert session.is_active_pipeline is False

    def test_pipeline_cancelled_helper_detects_flag(self):
        from apps.classes.tasks import _pipeline_cancelled
        session = baker.make(ClassCreationSession, status=Status.STRUCTURING, cancel_requested=True)
        assert _pipeline_cancelled(session) is True
        session.refresh_from_db()
        assert session.status == Status.CANCELLED

    def test_pipeline_cancelled_helper_false_when_active(self):
        from apps.classes.tasks import _pipeline_cancelled
        session = baker.make(ClassCreationSession, status=Status.STRUCTURING, cancel_requested=False)
        assert _pipeline_cancelled(session) is False
        session.refresh_from_db()
        assert session.status == Status.STRUCTURING


# ---------------------------------------------------------------------------
# Cancel endpoint — class pipeline
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestClassCancelEndpoint:
    def test_cancels_running_class_session(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        client = _auth_client(teacher)
        session = baker.make(
            ClassCreationSession, teacher=teacher,
            pipeline_type=PipelineType.CLASS, status=Status.STRUCTURING,
        )
        resp = client.post(CLASS_CANCEL.format(session.id))
        assert resp.status_code == 200
        assert resp.data['status'] == 'cancelled'
        session.refresh_from_db()
        assert session.status == Status.CANCELLED
        assert session.cancel_requested is True

    def test_cancel_is_idempotent(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        client = _auth_client(teacher)
        session = baker.make(
            ClassCreationSession, teacher=teacher,
            pipeline_type=PipelineType.CLASS, status=Status.TRANSCRIBING,
        )
        first = client.post(CLASS_CANCEL.format(session.id))
        assert first.status_code == 200
        # Second call: now terminal → 409 (already cancelled, not re-cancellable).
        second = client.post(CLASS_CANCEL.format(session.id))
        assert second.status_code == 409

    @pytest.mark.parametrize('status', [Status.RECAPPED, Status.FAILED, Status.CANCELLED])
    def test_rejects_terminal_session(self, status):
        teacher = baker.make(User, role=User.Role.TEACHER)
        client = _auth_client(teacher)
        session = baker.make(
            ClassCreationSession, teacher=teacher,
            pipeline_type=PipelineType.CLASS, status=status,
        )
        resp = client.post(CLASS_CANCEL.format(session.id))
        assert resp.status_code == 409
        session.refresh_from_db()
        assert session.status == status  # unchanged

    def test_another_teachers_session_returns_404(self):
        owner = baker.make(User, role=User.Role.TEACHER)
        other = baker.make(User, role=User.Role.TEACHER)
        session = baker.make(
            ClassCreationSession, teacher=owner,
            pipeline_type=PipelineType.CLASS, status=Status.STRUCTURING,
        )
        resp = _auth_client(other).post(CLASS_CANCEL.format(session.id))
        assert resp.status_code == 404
        session.refresh_from_db()
        assert session.status == Status.STRUCTURING

    def test_class_endpoint_rejects_exam_prep_session(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        client = _auth_client(teacher)
        session = baker.make(
            ClassCreationSession, teacher=teacher,
            pipeline_type=PipelineType.EXAM_PREP, status=Status.EXAM_STRUCTURING,
        )
        # Wrong endpoint for this pipeline type → 404 (not cross-cancellable).
        resp = client.post(CLASS_CANCEL.format(session.id))
        assert resp.status_code == 404

    def test_revoke_called_with_persisted_task_id(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        client = _auth_client(teacher)
        session = baker.make(
            ClassCreationSession, teacher=teacher,
            pipeline_type=PipelineType.CLASS, status=Status.STRUCTURING,
            celery_task_id='task-abc-123',
        )
        with patch('core.celery.app.control.revoke') as mock_revoke:
            resp = client.post(CLASS_CANCEL.format(session.id))
        assert resp.status_code == 200
        mock_revoke.assert_called_once()
        args, kwargs = mock_revoke.call_args
        assert args[0] == 'task-abc-123'
        assert kwargs.get('terminate') is True

    def test_revoke_failure_does_not_block_cancel(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        client = _auth_client(teacher)
        session = baker.make(
            ClassCreationSession, teacher=teacher,
            pipeline_type=PipelineType.CLASS, status=Status.STRUCTURING,
            celery_task_id='task-broken',
        )
        with patch('core.celery.app.control.revoke', side_effect=RuntimeError('broker down')):
            resp = client.post(CLASS_CANCEL.format(session.id))
        # DB transition still succeeds — cooperative flag is the safety net.
        assert resp.status_code == 200
        session.refresh_from_db()
        assert session.status == Status.CANCELLED
        assert session.cancel_requested is True

    def test_requires_authentication(self):
        session = baker.make(ClassCreationSession, status=Status.STRUCTURING)
        resp = APIClient().post(CLASS_CANCEL.format(session.id))
        assert resp.status_code in (401, 403)

    def test_student_forbidden(self):
        student = baker.make(User, role=User.Role.STUDENT)
        session = baker.make(
            ClassCreationSession, pipeline_type=PipelineType.CLASS, status=Status.STRUCTURING,
        )
        resp = _auth_client(student).post(CLASS_CANCEL.format(session.id))
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Cancel endpoint — exam-prep pipeline
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestExamPrepCancelEndpoint:
    def test_cancels_running_exam_prep_session(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        client = _auth_client(teacher)
        session = baker.make(
            ClassCreationSession, teacher=teacher,
            pipeline_type=PipelineType.EXAM_PREP, status=Status.EXAM_TRANSCRIBING,
        )
        resp = client.post(EXAM_CANCEL.format(session.id))
        assert resp.status_code == 200
        assert resp.data['status'] == 'cancelled'
        session.refresh_from_db()
        assert session.status == Status.CANCELLED
        assert session.cancel_requested is True

    def test_exam_endpoint_rejects_class_session(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        client = _auth_client(teacher)
        session = baker.make(
            ClassCreationSession, teacher=teacher,
            pipeline_type=PipelineType.CLASS, status=Status.STRUCTURING,
        )
        resp = client.post(EXAM_CANCEL.format(session.id))
        assert resp.status_code == 404

    def test_rejects_completed_exam_prep(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        client = _auth_client(teacher)
        session = baker.make(
            ClassCreationSession, teacher=teacher,
            pipeline_type=PipelineType.EXAM_PREP, status=Status.EXAM_STRUCTURED,
        )
        resp = client.post(EXAM_CANCEL.format(session.id))
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Cooperative cancellation inside the full-pipeline tasks
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCooperativePipelineCancellation:
    def test_class_pipeline_aborts_when_cancel_requested(self):
        from apps.classes.tasks import process_class_full_pipeline
        session = baker.make(
            ClassCreationSession, pipeline_type=PipelineType.CLASS,
            status=Status.TRANSCRIBING, cancel_requested=True,
        )
        result = process_class_full_pipeline.apply(args=[session.id]).result
        assert result['status'] == 'cancelled'
        session.refresh_from_db()
        assert session.status == Status.CANCELLED

    def test_class_pipeline_aborts_when_already_cancelled(self):
        """A re-queued task (acks_late) re-reads a CANCELLED row and stops."""
        from apps.classes.tasks import process_class_full_pipeline
        session = baker.make(
            ClassCreationSession, pipeline_type=PipelineType.CLASS,
            status=Status.CANCELLED,
        )
        result = process_class_full_pipeline.apply(args=[session.id]).result
        assert result['status'] == 'cancelled'

    def test_exam_pipeline_aborts_when_cancel_requested(self):
        from apps.classes.tasks import process_exam_prep_full_pipeline
        session = baker.make(
            ClassCreationSession, pipeline_type=PipelineType.EXAM_PREP,
            status=Status.EXAM_TRANSCRIBING, cancel_requested=True,
        )
        result = process_exam_prep_full_pipeline.apply(args=[session.id]).result
        assert result['status'] == 'cancelled'
        session.refresh_from_db()
        assert session.status == Status.CANCELLED
