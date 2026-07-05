"""E6 — exercise grading: LLM-mocked descriptive grading + deterministic MCQ/
fill-blank (no LLM) + correct sum + idempotent re-run + GRADING_FAILED + the
Low-1 guard (no reference answer in result). 0 tokens.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from model_bakery import baker

from apps.classes import tasks
from apps.classes.services import exercise_grading as grading
from apps.classes.models import (
    ClassExercise,
    ClassExerciseQuestion,
    ClassExerciseSection,
    StudentExerciseSubmission,
)

pytestmark = [pytest.mark.django_db, pytest.mark.integration]

SubStatus = StudentExerciseSubmission.Status
QType = ClassExerciseQuestion.QuestionType


def _submission_with_questions(monkeypatch, *, descriptive_llm=None, raise_llm=False):
    ex = baker.make(ClassExercise, status=ClassExercise.Status.PUBLISHED)
    sec = baker.make(ClassExerciseSection, exercise=ex, order=0)
    # q1 descriptive (LLM), q2 multiple_choice (deterministic)
    q1 = baker.make(ClassExerciseQuestion, section=sec, order=0,
                    question_type=QType.DESCRIPTIVE, question_markdown='توضیح بده',
                    reference_answer_markdown='SECRET-REFERENCE', max_points=Decimal('4'))
    q2 = baker.make(ClassExerciseQuestion, section=sec, order=1,
                    question_type=QType.MULTIPLE_CHOICE, question_markdown='کدام؟',
                    reference_answer_markdown='ب', max_points=Decimal('2'))
    student = baker.make('accounts.User', role='STUDENT')
    sub = baker.make(
        StudentExerciseSubmission, exercise=ex, student=student,
        status=SubStatus.SUBMITTED,
        answers={str(q1.id): {'text': 'پاسخ من'}, str(q2.id): {'text': 'ب'}},
    )

    calls = {'n': 0}

    def fake_batch(items):
        calls['n'] += 1
        if raise_llm:
            raise RuntimeError('llm boom')
        # score the (single) descriptive item with a fixed partial score
        out = {}
        for it in items:
            out[it['question_id']] = {
                'question_id': it['question_id'], 'llm_score': 3.0,
                'score_points': 3.0, 'max_points': it['max_points'],
                'label': 'partially_correct', 'feedback': 'خوب بود',
                'missing_points': [], 'teacher_score': None, 'teacher_feedback': None,
            }
        return out

    monkeypatch.setattr(grading, '_grade_descriptive_batch',
                        descriptive_llm if descriptive_llm else fake_batch)
    return ex, q1, q2, sub, calls


def _run(sid):
    return tasks.grade_exercise_submission.apply(args=[sid]).result


class TestGradingTask:
    def test_happy_grading_sums_llm_and_deterministic(self, monkeypatch):
        ex, q1, q2, sub, calls = _submission_with_questions(monkeypatch)
        result = _run(sub.id)
        assert result['status'] == 'graded'
        sub.refresh_from_db()
        assert sub.status == SubStatus.GRADED
        # q1 (descriptive) 3/4 + q2 (MCQ 'ب'=='ب') 2/2 = 5 of 6
        assert str(sub.score_points) == '5.00'
        assert str(sub.max_points) == '6.00'
        assert calls['n'] == 1  # one LLM batch (only the descriptive question)

    def test_mcq_graded_without_llm(self, monkeypatch):
        # If the ONLY question is MCQ, the LLM batch must never be called.
        ex = baker.make(ClassExercise, status=ClassExercise.Status.PUBLISHED)
        sec = baker.make(ClassExerciseSection, exercise=ex, order=0)
        q = baker.make(ClassExerciseQuestion, section=sec, order=0,
                       question_type=QType.MULTIPLE_CHOICE,
                       reference_answer_markdown='ج', max_points=Decimal('5'))
        student = baker.make('accounts.User', role='STUDENT')
        sub = baker.make(StudentExerciseSubmission, exercise=ex, student=student,
                         status=SubStatus.SUBMITTED, answers={str(q.id): {'text': 'ج'}})

        def boom(items):
            raise AssertionError('LLM must not be called for MCQ-only grading')

        monkeypatch.setattr(grading, '_grade_descriptive_batch', boom)
        result = _run(sub.id)
        assert result['status'] == 'graded'
        sub.refresh_from_db()
        assert str(sub.score_points) == '5.00'  # exact match -> full marks

    def test_result_never_contains_reference_answer(self, monkeypatch):
        """Low-1: the reference answer must not leak into the stored result."""
        ex, q1, q2, sub, calls = _submission_with_questions(monkeypatch)
        _run(sub.id)
        sub.refresh_from_db()
        import json
        blob = json.dumps(sub.result, ensure_ascii=False)
        assert 'SECRET-REFERENCE' not in blob
        for pq in sub.result['per_question']:
            assert 'reference_answer' not in pq
            assert 'grading_notes' not in pq

    def test_idempotent_rerun(self, monkeypatch):
        ex, q1, q2, sub, calls = _submission_with_questions(monkeypatch)
        _run(sub.id)
        # second dispatch: now GRADED -> not runnable -> skip
        second = _run(sub.id)
        assert second['status'] == 'skipped'

    def test_failure_marks_grading_failed(self, monkeypatch):
        ex, q1, q2, sub, calls = _submission_with_questions(monkeypatch, raise_llm=True)
        result = _run(sub.id)
        assert result['status'] == 'failed'
        sub.refresh_from_db()
        assert sub.status == SubStatus.GRADING_FAILED

    def test_kill_switch_leaves_submitted(self, monkeypatch):
        monkeypatch.setenv('EXERCISE_LLM_GRADING', '0')
        ex, q1, q2, sub, calls = _submission_with_questions(monkeypatch)
        result = _run(sub.id)
        assert result['status'] == 'skipped'
        sub.refresh_from_db()
        assert sub.status == SubStatus.SUBMITTED

    def test_missing_submission_safe(self, monkeypatch):
        _submission_with_questions(monkeypatch)  # sets up the mock
        assert _run(999999)['status'] == 'skipped'


class TestImageSniff:
    def test_is_real_image_rejects_garbage(self):
        assert grading.is_real_image(b'not an image') is False
        assert grading.is_real_image(b'') is False

    def test_is_real_image_accepts_png(self):
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.new('RGB', (2, 2)).save(buf, format='PNG')
        assert grading.is_real_image(buf.getvalue()) is True
