import json
import tempfile
import uuid
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import override_settings
from model_bakery import baker
from rest_framework.test import APIClient

from apps.classes.models import ClassCreationSession, ClassExercise, ClassExerciseAsset
from apps.classes.tasks import _make_step1_heartbeat, _mark_session_ready_for_review


User = get_user_model()


_STEP1_URL = "/api/classes/creation-sessions/step-1/"


def _filesystem_storages():
    return {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": tempfile.mkdtemp(prefix="aiamooz_embedded_exercise_")},
        },
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }


@pytest.mark.django_db
def test_mark_session_ready_for_review_materializes_pending_exercises_and_notifies_once(monkeypatch):
    teacher = baker.make(User, role=User.Role.TEACHER)
    session = baker.make(
        ClassCreationSession,
        teacher=teacher,
        pipeline_type=ClassCreationSession.PipelineType.CLASS,
        status=ClassCreationSession.Status.RECAPPED,
        pending_exercises=[
            {
                'clientExerciseKey': 'exercise-1',
                'title': 'تمرین فصل اول',
                'noDeadline': True,
                'deadline': None,
                'allowLate': False,
                'assistantEnabled': True,
                'teacherNote': 'یادداشت',
                'status': 'pending',
                'sources': [
                    {
                        'clientFileKey': 'source-1',
                        'assetOrder': 0,
                        'assetName': 'exercise.pdf',
                        'assetKind': 'pdf',
                        'assetBytes': 128,
                        'role': 'question_only',
                        'writingMode': 'typed',
                        'answerLayout': 'auto',
                        'storagePath': 'class_creation/pending_exercises/source-1.pdf',
                    }
                ],
            }
        ],
        workflow_state={},
        review_ready_notified_at=None,
    )
    extract_calls: list[int] = []
    sms_calls: list[int] = []

    monkeypatch.setattr(
        'apps.classes.tasks.extract_exercise_content.delay',
        lambda exercise_id: extract_calls.append(exercise_id),
    )
    monkeypatch.setattr(
        'apps.classes.tasks.send_session_review_ready_sms_task.delay',
        lambda session_id: sms_calls.append(session_id),
    )
    monkeypatch.setattr(
        transaction,
        'on_commit',
        lambda func, using=None, robust=False: func(),
    )

    _mark_session_ready_for_review(session)
    session.refresh_from_db()
    exercise = ClassExercise.objects.get(session=session)

    assert exercise.title == 'تمرین فصل اول'
    assert exercise.workflow_state['stage'] == 'queued'
    assert ClassExerciseAsset.objects.filter(exercise=exercise, order=0, kind='pdf').count() == 1
    assert session.review_ready_notified_at is not None
    assert session.workflow_state['stage'] == 'ready_for_review'
    assert session.workflow_state['readyForReview'] is True
    assert session.pending_exercises[0]['exerciseId'] == exercise.id
    assert session.pending_exercises[0]['status'] == 'queued'
    assert extract_calls == [exercise.id]
    assert sms_calls == [session.id]

    _mark_session_ready_for_review(session)
    session.refresh_from_db()

    assert ClassExercise.objects.filter(session=session).count() == 1
    assert extract_calls == [exercise.id]
    assert sms_calls == [session.id]


@pytest.mark.django_db
def test_step1_pending_exercise_snapshot_materializes_after_class_ready(monkeypatch):
    teacher = baker.make(User, role=User.Role.TEACHER)
    client = APIClient()
    client.force_authenticate(user=teacher)
    exercise_key = f'exercise-{uuid.uuid4().hex[:8]}'
    source_key = f'source-{uuid.uuid4().hex[:8]}'
    payload = {
        'title': 'کلاس همراه تمرین',
        'description': 'diagnostic',
        'file': SimpleUploadedFile('lesson.mp4', b'fake-media-bytes', content_type='video/mp4'),
        'client_request_id': str(uuid.uuid4()),
        'run_full_pipeline': 'true',
        'pending_exercises': json.dumps([
            {
                'clientExerciseKey': exercise_key,
                'title': 'تمرین همراه کلاس',
                'noDeadline': True,
                'deadline': None,
                'allowLate': False,
                'assistantEnabled': True,
                'teacherNote': 'یادداشت',
                'sources': [
                    {
                        'clientFileKey': source_key,
                        'role': 'question_and_answer',
                        'writingMode': 'typed',
                        'answerLayout': 'inline',
                    }
                ],
            }
        ]),
        f'exercise_{exercise_key}__file_{source_key}': SimpleUploadedFile(
            'exercise.pdf',
            b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF',
            content_type='application/pdf',
        ),
    }
    extract_calls: list[int] = []
    sms_calls: list[int] = []

    with override_settings(
        STORAGES=_filesystem_storages(),
        FILE_UPLOAD_HANDLERS=['django.core.files.uploadhandler.MemoryFileUploadHandler'],
        CLASS_PIPELINE_ASYNC=True,
    ):
        with patch('apps.classes.views.process_class_full_pipeline', new=MagicMock()):
            response = client.post(_STEP1_URL, payload, format='multipart')

        assert response.status_code == 202, response.content
        assert response.data['pendingExercises'][0]['status'] == 'pending'
        session = ClassCreationSession.objects.get(id=response.data['id'])
        assert len(session.pending_exercises) == 1
        assert session.pending_exercises[0]['sources'][0]['storagePath']

        session.status = ClassCreationSession.Status.RECAPPED
        session.save(update_fields=['status', 'updated_at'])
        monkeypatch.setattr(
            'apps.classes.tasks.extract_exercise_content.delay',
            lambda exercise_id: extract_calls.append(exercise_id),
        )
        monkeypatch.setattr(
            'apps.classes.tasks.send_session_review_ready_sms_task.delay',
            lambda session_id: sms_calls.append(session_id),
        )
        monkeypatch.setattr(transaction, 'on_commit', lambda func, using=None, robust=False: func())

        _mark_session_ready_for_review(session)

    session.refresh_from_db()
    exercise = ClassExercise.objects.get(session=session)
    assert exercise.title == 'تمرین همراه کلاس'
    assert exercise.workflow_state['stage'] == 'queued'
    assert exercise.intake_config['mode'] == 'embedded_class_create'
    assert ClassExerciseAsset.objects.filter(exercise=exercise, kind='pdf').count() == 1
    assert session.pending_exercises[0]['exerciseId'] == exercise.id
    assert session.pending_exercises[0]['status'] == 'queued'
    assert extract_calls == [exercise.id]
    assert sms_calls == [session.id]


@pytest.mark.django_db
def test_mark_exam_session_ready_for_review_notifies_once_without_exercises(monkeypatch):
    teacher = baker.make(User, role=User.Role.TEACHER)
    session = baker.make(
        ClassCreationSession,
        teacher=teacher,
        pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        status=ClassCreationSession.Status.EXAM_STRUCTURED,
        pending_exercises=[],
        workflow_state={},
        review_ready_notified_at=None,
    )
    sms_calls: list[int] = []

    monkeypatch.setattr(
        'apps.classes.tasks.send_session_review_ready_sms_task.delay',
        lambda session_id: sms_calls.append(session_id),
    )

    _mark_session_ready_for_review(session)
    session.refresh_from_db()

    assert session.review_ready_notified_at is not None
    assert session.workflow_state['stage'] == 'ready_for_review'
    assert session.workflow_state['readyForReview'] is True
    assert ClassExercise.objects.filter(session=session).count() == 0
    assert sms_calls == [session.id]

    _mark_session_ready_for_review(session)
    assert sms_calls == [session.id]


@pytest.mark.django_db
def test_step1_heartbeat_persists_chunk_progress():
    teacher = baker.make(User, role=User.Role.TEACHER)
    session = baker.make(
        ClassCreationSession,
        teacher=teacher,
        status=ClassCreationSession.Status.TRANSCRIBING,
        workflow_state={'stage': 'queued', 'progressPercent': 5},
        cancel_requested=False,
    )

    heartbeat = _make_step1_heartbeat(session.id)

    assert heartbeat(2, 4) is True

    session.refresh_from_db()
    assert session.workflow_state['stage'] == 'transcribing'
    assert session.workflow_state['progressPercent'] == 37
    assert session.workflow_state['message'] == 'در حال تبدیل فایل به متن هستیم (2 از 4).'
