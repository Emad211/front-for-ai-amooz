import pytest
from django.contrib.auth import get_user_model
from django.db import transaction
from model_bakery import baker

from apps.classes.models import ClassCreationSession, ClassExercise, ClassExerciseAsset
from apps.classes.tasks import _mark_session_ready_for_review


User = get_user_model()


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
