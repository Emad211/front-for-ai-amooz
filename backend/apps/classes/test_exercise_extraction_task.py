"""E3 — extract_exercise_content Celery task (eager): state machine, idempotency,
FAILED path, row creation. OCR + LLM structure are mocked (0 tokens, no media).

Design: docs/features/exercise-hub.md. The task calls
``exercise_ingest.{ocr_assets_to_markdown, structure_exercise_markdown}`` via a
local import, so patching those module attributes intercepts all LLM/OCR work.
"""
from __future__ import annotations

import pytest
from celery.exceptions import Retry as CeleryRetry
from model_bakery import baker

from apps.chatbot.services.llm_client import ProviderTransientError
from apps.classes import tasks
from apps.classes.services import exercise_ingest as ing
from apps.classes.models import (
    ClassExercise,
    ClassExerciseQuestion,
    ClassExerciseSection,
)

pytestmark = [pytest.mark.django_db, pytest.mark.integration]

Status = ClassExercise.Status

STRUCTURE = {
    "exercise_title": "T",
    "sections": [
        {"section_id": "s1", "title": "بخش ۱", "questions": [
            {"question_id": "s1q1", "question_text_markdown": "سؤال ۱",
             "question_type": "descriptive", "options": None,
             "points": 2, "reference_answer_markdown": None},
            {"question_id": "s1q2", "question_text_markdown": "سؤال ۲",
             "question_type": "multiple_choice", "options": ["الف", "ب"],
             "points": None, "reference_answer_markdown": None},
        ]},
    ],
}


def _mock_pipeline(monkeypatch, *, structure=STRUCTURE, raise_on_structure=False, transient=False):
    monkeypatch.setattr(ing, "ocr_assets_to_markdown", lambda exercise, **kwargs: "# ocr markdown")

    def fake_structure(*, ingest_markdown):
        if transient:
            raise ProviderTransientError("avalai 502")
        if raise_on_structure:
            raise RuntimeError("boom")
        return structure, "test", "test-model"

    monkeypatch.setattr(ing, "structure_exercise_markdown", fake_structure)


def _run(exercise_id):
    return tasks.extract_exercise_content.apply(args=[exercise_id]).result


def test_happy_extraction_builds_rows_and_reaches_extracted(monkeypatch):
    _mock_pipeline(monkeypatch)
    monkeypatch.setattr(tasks.send_exercise_review_ready_sms_task, 'delay', lambda _eid: None)
    ex = baker.make(ClassExercise, status=Status.DRAFT)

    result = _run(ex.id)

    assert result["status"] == "extracted"
    assert result["sections"] == 1 and result["questions"] == 2
    ex.refresh_from_db()
    assert ex.status == Status.EXTRACTED
    assert ex.workflow_state['stage'] == 'ready_for_review'
    assert ex.workflow_state['readyForReview'] is True
    assert ex.review_ready_notified_at is not None
    secs = list(ClassExerciseSection.objects.filter(exercise=ex).order_by("order"))
    assert len(secs) == 1 and secs[0].title == "بخش ۱"
    qs = list(ClassExerciseQuestion.objects.filter(section=secs[0]).order_by("order"))
    assert [q.question_type for q in qs] == ["descriptive", "multiple_choice"]
    assert str(qs[0].max_points) == "2.00"          # points extracted
    assert str(qs[1].max_points) == "1.00"          # null points -> default 1
    assert qs[1].options == ["الف", "ب"]


def test_status_guard_skips_non_runnable(monkeypatch):
    _mock_pipeline(monkeypatch)
    ex = baker.make(ClassExercise, status=Status.PUBLISHED)
    result = _run(ex.id)
    assert result["status"] == "skipped"
    ex.refresh_from_db()
    assert ex.status == Status.PUBLISHED  # untouched


def test_double_dispatch_is_noop(monkeypatch):
    _mock_pipeline(monkeypatch)
    monkeypatch.setattr(tasks.send_exercise_review_ready_sms_task, 'delay', lambda _eid: None)
    ex = baker.make(ClassExercise, status=Status.DRAFT)
    first = _run(ex.id)
    assert first["status"] == "extracted"
    # Second dispatch: EXTRACTED is now a valid manual rerun state.
    second = _run(ex.id)
    assert second["status"] == "extracted"
    assert ClassExerciseSection.objects.filter(exercise=ex).count() == 1


def test_failure_marks_failed(monkeypatch):
    _mock_pipeline(monkeypatch, raise_on_structure=True)
    ex = baker.make(ClassExercise, status=Status.DRAFT)
    result = _run(ex.id)
    assert result["status"] == "failed"
    ex.refresh_from_db()
    assert ex.status == Status.FAILED
    assert ex.workflow_state['stage'] == 'failed'
    assert ex.workflow_state['warnings'] == ['ساخت پیش‌نویس تمرین کامل نشد. دوباره تلاش کنید یا منابع را بازبینی کنید.']
    assert ex.review_ready_notified_at is None


def test_transient_provider_failure_uses_celery_retry_without_marking_failed(monkeypatch):
    _mock_pipeline(monkeypatch, transient=True)
    ex = baker.make(ClassExercise, status=Status.DRAFT)
    monkeypatch.setattr(tasks.extract_exercise_content.request, "id", "retry-task", raising=False)

    def fake_retry(*, exc=None, countdown=None):
        raise CeleryRetry(exc=exc, when=countdown)

    monkeypatch.setattr(tasks.extract_exercise_content, "retry", fake_retry)

    with pytest.raises(CeleryRetry):
        tasks.extract_exercise_content.run(ex.id)

    ex.refresh_from_db()
    assert ex.status == Status.EXTRACTING
    assert ex.extract_task_id != ""


def test_redelivered_same_extraction_task_can_resume_from_extracting(monkeypatch):
    _mock_pipeline(monkeypatch)
    monkeypatch.setattr(tasks.send_exercise_review_ready_sms_task, 'delay', lambda _eid: None)
    ex = baker.make(ClassExercise, status=Status.EXTRACTING, extract_task_id="same-task")
    monkeypatch.setattr(tasks.extract_exercise_content.request, "id", "same-task", raising=False)

    result = tasks.extract_exercise_content.run(ex.id)

    assert result["status"] == "extracted"
    ex.refresh_from_db()
    assert ex.status == Status.EXTRACTED


def test_rerun_from_failed_clears_old_rows(monkeypatch):
    _mock_pipeline(monkeypatch)
    monkeypatch.setattr(tasks.send_exercise_review_ready_sms_task, 'delay', lambda _eid: None)
    ex = baker.make(ClassExercise, status=Status.FAILED)
    # seed a stale section from a prior failed run
    baker.make(ClassExerciseSection, exercise=ex, order=0, title="stale")
    result = _run(ex.id)
    assert result["status"] == "extracted"
    titles = list(ClassExerciseSection.objects.filter(exercise=ex).values_list("title", flat=True))
    assert titles == ["بخش ۱"]  # stale section replaced


def test_missing_exercise_is_safe(monkeypatch):
    _mock_pipeline(monkeypatch)
    assert _run(999999)["status"] == "skipped"


def test_task_id_is_persisted(monkeypatch):
    _mock_pipeline(monkeypatch)
    monkeypatch.setattr(tasks.send_exercise_review_ready_sms_task, 'delay', lambda _eid: None)
    ex = baker.make(ClassExercise, status=Status.DRAFT)
    _run(ex.id)
    ex.refresh_from_db()
    # eager apply() assigns a request id; the task persists it.
    assert ex.extract_task_id != ''


def test_answer_ingest_low_confidence_becomes_warning_not_hard_fail(monkeypatch):
    _mock_pipeline(monkeypatch)
    monkeypatch.setattr(tasks.send_exercise_review_ready_sms_task, 'delay', lambda _eid: None)
    monkeypatch.setattr(
        ing,
        'ingest_reference_answers_markdown',
        lambda **kwargs: ({
            'mode_detected': 'answer_only',
            'items': [{
                'item_id': 'i1',
                'question_number': 999,
                'reference_answer_markdown': 'پاسخ',
                'confidence': 0.25,
                'question_text_markdown': None,
                'question_type': None,
                'options': None,
                'points': 2,
                'notes': '',
            }],
            'warnings': [],
        }, 'test', 'model'),
    )
    ex = baker.make(
        ClassExercise,
        status=Status.DRAFT,
        intake_config={
            'sources': [
                {
                    'assetOrder': 0,
                    'assetName': 'qa.png',
                    'role': 'question_and_answer',
                    'writingMode': 'typed',
                    'answerLayout': 'inline',
                }
            ]
        },
    )

    result = _run(ex.id)

    assert result['status'] == 'extracted'
    ex.refresh_from_db()
    assert ex.workflow_state['stage'] == 'ready_for_review'
    assert ex.workflow_state['warnings']


def test_answer_ingest_raw_diagnostics_are_not_leaked_to_workflow_state(monkeypatch):
    _mock_pipeline(monkeypatch)
    monkeypatch.setattr(tasks.send_exercise_review_ready_sms_task, 'delay', lambda _eid: None)
    monkeypatch.setattr(
        ing,
        'ingest_reference_answers_markdown',
        lambda **kwargs: ({
            'mode_detected': 'question_and_answer',
            'items': [{
                'item_id': 'i1',
                'question_number': 999,
                'reference_answer_markdown': 'پاسخ',
                'confidence': 0.95,
                'question_text_markdown': None,
                'question_type': None,
                'options': None,
                'points': 2,
                'notes': '',
            }],
            'warnings': [
                'Answer for Q4 seems to refer to a different definition of $A_n$ and needs manual review.',
            ],
        }, 'test', 'model'),
    )
    ex = baker.make(
        ClassExercise,
        status=Status.DRAFT,
        intake_config={
            'sources': [
                {
                    'assetOrder': 0,
                    'assetName': 'qa.png',
                    'role': 'question_and_answer',
                    'writingMode': 'typed',
                    'answerLayout': 'inline',
                }
            ]
        },
    )

    result = _run(ex.id)

    assert result['status'] == 'extracted'
    ex.refresh_from_db()
    assert all('Answer for Q4' not in warning for warning in ex.workflow_state['warnings'])
    assert any('بازبینی' in warning for warning in ex.workflow_state['warnings'])


def test_answer_ingest_exception_text_is_not_leaked_to_workflow_state(monkeypatch):
    _mock_pipeline(monkeypatch)
    monkeypatch.setattr(tasks.send_exercise_review_ready_sms_task, 'delay', lambda _eid: None)

    def boom(**kwargs):
        raise RuntimeError('HTTP 502 upstream failure while matching answers')

    monkeypatch.setattr(ing, 'ingest_reference_answers_markdown', boom)
    ex = baker.make(
        ClassExercise,
        status=Status.DRAFT,
        intake_config={
            'sources': [
                {
                    'assetOrder': 0,
                    'assetName': 'questions.png',
                    'role': 'question_only',
                    'writingMode': 'typed',
                    'answerLayout': 'auto',
                },
                {
                    'assetOrder': 1,
                    'assetName': 'answers.png',
                    'role': 'answer_only',
                    'writingMode': 'typed',
                    'answerLayout': 'separate',
                }
            ]
        },
    )

    result = _run(ex.id)

    assert result['status'] == 'extracted'
    ex.refresh_from_db()
    assert all('502' not in warning for warning in ex.workflow_state['warnings'])
    assert any('خودکار اعمال نشد' in warning for warning in ex.workflow_state['warnings'])


def test_review_ready_notification_is_only_queued_once(monkeypatch):
    _mock_pipeline(monkeypatch)
    calls = []
    monkeypatch.setattr(tasks.send_exercise_review_ready_sms_task, 'delay', lambda eid: calls.append(eid))
    ex = baker.make(ClassExercise, status=Status.DRAFT)

    first = _run(ex.id)
    ex.refresh_from_db()
    first_ts = ex.review_ready_notified_at
    second = _run(ex.id)
    ex.refresh_from_db()

    assert first['status'] == 'extracted'
    assert second['status'] == 'extracted'
    assert ex.review_ready_notified_at == first_ts
    assert calls == [ex.id]


def test_cancelled_extraction_stops_at_first_checkpoint(monkeypatch):
    _mock_pipeline(monkeypatch)
    ex = baker.make(
        ClassExercise,
        status=Status.EXTRACTING,
        extract_task_id='cancel-task',
        cancel_requested=True,
    )
    monkeypatch.setattr(tasks.extract_exercise_content.request, "id", "cancel-task", raising=False)

    result = tasks.extract_exercise_content.run(ex.id)

    assert result['status'] == 'cancelled'
    ex.refresh_from_db()
    assert ex.status == Status.CANCELLED
    assert ex.workflow_state['stage'] == 'cancelled'


def test_cancelled_status_is_rerunnable(monkeypatch):
    _mock_pipeline(monkeypatch)
    monkeypatch.setattr(tasks.send_exercise_review_ready_sms_task, 'delay', lambda _eid: None)
    ex = baker.make(ClassExercise, status=Status.CANCELLED, cancel_requested=False)

    result = _run(ex.id)

    assert result['status'] == 'extracted'
    ex.refresh_from_db()
    assert ex.status == Status.EXTRACTED
    assert ex.cancel_requested is False
