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
    monkeypatch.setattr(ing, "ocr_assets_to_markdown", lambda exercise: "# ocr markdown")

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
    ex = baker.make(ClassExercise, status=Status.DRAFT)

    result = _run(ex.id)

    assert result["status"] == "extracted"
    assert result["sections"] == 1 and result["questions"] == 2
    ex.refresh_from_db()
    assert ex.status == Status.EXTRACTED
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
    ex = baker.make(ClassExercise, status=Status.DRAFT)
    first = _run(ex.id)
    assert first["status"] == "extracted"
    # Second dispatch: now EXTRACTED -> not runnable -> skip (no duplicate rows).
    second = _run(ex.id)
    assert second["status"] == "skipped"
    assert ClassExerciseSection.objects.filter(exercise=ex).count() == 1


def test_failure_marks_failed(monkeypatch):
    _mock_pipeline(monkeypatch, raise_on_structure=True)
    ex = baker.make(ClassExercise, status=Status.DRAFT)
    result = _run(ex.id)
    assert result["status"] == "failed"
    ex.refresh_from_db()
    assert ex.status == Status.FAILED


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
    ex = baker.make(ClassExercise, status=Status.EXTRACTING, extract_task_id="same-task")
    monkeypatch.setattr(tasks.extract_exercise_content.request, "id", "same-task", raising=False)

    result = tasks.extract_exercise_content.run(ex.id)

    assert result["status"] == "extracted"
    ex.refresh_from_db()
    assert ex.status == Status.EXTRACTED


def test_rerun_from_failed_clears_old_rows(monkeypatch):
    _mock_pipeline(monkeypatch)
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
    ex = baker.make(ClassExercise, status=Status.DRAFT)
    _run(ex.id)
    ex.refresh_from_db()
    # eager apply() assigns a request id; the task persists it.
    assert ex.extract_task_id != ''
