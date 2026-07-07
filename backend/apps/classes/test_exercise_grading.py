"""E6 — exercise grading: LLM-mocked descriptive grading + deterministic MCQ/
fill-blank (no LLM) + correct sum + idempotent re-run + GRADING_FAILED + the
Low-1 guard (no reference answer in result). 0 tokens.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from celery.exceptions import Retry as CeleryRetry
from model_bakery import baker

from apps.chatbot.services.llm_client import ProviderTransientError
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

    def test_transient_provider_failure_uses_celery_retry_without_marking_failed(self, monkeypatch):
        ex, q1, q2, sub, calls = _submission_with_questions(
            monkeypatch,
            descriptive_llm=lambda items: (_ for _ in ()).throw(ProviderTransientError('avalai 502')),
        )

        def fake_retry(*, exc=None, countdown=None):
            raise CeleryRetry(exc=exc, when=countdown)

        monkeypatch.setattr(tasks.grade_exercise_submission.request, 'id', 'retry-task', raising=False)
        monkeypatch.setattr(tasks.grade_exercise_submission, 'retry', fake_retry)

        with pytest.raises(CeleryRetry):
            tasks.grade_exercise_submission.run(sub.id)

        sub.refresh_from_db()
        assert sub.status == SubStatus.GRADING
        assert sub.grading_task_id != ''

    def test_redelivered_same_grading_task_can_resume_from_grading(self, monkeypatch):
        ex, q1, q2, sub, calls = _submission_with_questions(monkeypatch)
        sub.status = SubStatus.GRADING
        sub.grading_task_id = 'same-task'
        sub.save(update_fields=['status', 'grading_task_id'])
        monkeypatch.setattr(tasks.grade_exercise_submission.request, 'id', 'same-task', raising=False)

        result = tasks.grade_exercise_submission.run(sub.id)

        assert result['status'] == 'graded'
        sub.refresh_from_db()
        assert sub.status == SubStatus.GRADED

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
        assert grading.is_real_image(_png_bytes()) is True


# ---------------------------------------------------------------------------
# E13 — handwriting-photo answers are vision-extracted before grading.
# ALL LLM + storage reads mocked: 0 tokens.
# ---------------------------------------------------------------------------


def _png_bytes() -> bytes:
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (2, 2)).save(buf, format='PNG')
    return buf.getvalue()


def _photo_submission(*, qtype=None, reference='ب', text='', images=(),
                      grading_notes=''):
    """One-question submission whose answer carries handwriting photo paths."""
    qtype = qtype or QType.MULTIPLE_CHOICE
    ex = baker.make(ClassExercise, status=ClassExercise.Status.PUBLISHED)
    sec = baker.make(ClassExerciseSection, exercise=ex, order=0)
    q = baker.make(ClassExerciseQuestion, section=sec, order=0,
                   question_type=qtype, question_markdown='سؤال؟',
                   reference_answer_markdown=reference,
                   grading_notes=grading_notes, max_points=Decimal('2'))
    student = baker.make('accounts.User', role='STUDENT')
    entry = {}
    if text:
        entry['text'] = text
    sub = baker.make(StudentExerciseSubmission, exercise=ex, student=student,
                     status=SubStatus.SUBMITTED, answers={str(q.id): entry})
    if images:
        entry['images'] = [
            f'exercises/answers/{ex.id}/{student.id}/{q.id}_{idx}.png'
            for idx, _path in enumerate(images)
        ]
        sub.answers = {str(q.id): entry}
        sub.save(update_fields=['answers'])
    return ex, q, sub


class TestHandwritingVision:
    def _mock_vision(self, monkeypatch, *, text='ب', raise_exc=None):
        """Mock storage read (real PNG bytes) + the vision LLM; returns capture."""
        from apps.classes.services.schemas import HandwritingTranscriptionOutput
        monkeypatch.setenv('EXERCISE_VISION_MODEL', 'test-vision-model')
        monkeypatch.setattr(grading, '_read_answer_image', lambda path: _png_bytes())
        captured = {'calls': 0, 'kwargs': None}

        def fake_generate_structured(**kwargs):
            captured['calls'] += 1
            captured['kwargs'] = kwargs
            if raise_exc is not None:
                raise raise_exc
            return HandwritingTranscriptionOutput(text=text)

        monkeypatch.setattr(grading, 'generate_structured', fake_generate_structured)
        return captured

    def test_photo_only_answer_extracted_and_graded(self, monkeypatch):
        """(a) Photo-only MCQ answer: vision text is used verbatim, so the
        deterministic comparison grades it end-to-end — no grading-LLM call."""
        ex, q, sub = _photo_submission(images=['exercises/answers/1/1/a.png'])
        captured = self._mock_vision(monkeypatch, text='ب')

        def boom(items):
            raise AssertionError('grading LLM must not be called for MCQ-only')

        monkeypatch.setattr(grading, '_grade_descriptive_batch', boom)
        result = _run(sub.id)
        assert result['status'] == 'graded'
        assert captured['calls'] == 1  # exactly one vision call
        sub.refresh_from_db()
        assert sub.status == SubStatus.GRADED
        assert str(sub.score_points) == '2.00'  # extracted 'ب' == reference 'ب'

    def test_vision_failure_falls_back_to_text_only(self, monkeypatch):
        """(b) Vision blows up -> the typed text is graded alone and the
        submission still ends GRADED (never fail a submission on a bad photo)."""
        ex, q, sub = _photo_submission(
            qtype=QType.DESCRIPTIVE, reference='SECRET-REFERENCE',
            text='متن تایپ‌شده', images=['exercises/answers/1/1/a.png'],
        )
        self._mock_vision(monkeypatch, raise_exc=RuntimeError('vision boom'))
        seen = {}

        def fake_batch(items):
            seen['student_answer'] = items[0]['student_answer']
            return {items[0]['question_id']: {
                'question_id': items[0]['question_id'], 'llm_score': 1.0,
                'score_points': 1.0, 'max_points': items[0]['max_points'],
                'label': 'partially_correct', 'feedback': '', 'missing_points': [],
                'teacher_score': None, 'teacher_feedback': None,
            }}

        monkeypatch.setattr(grading, '_grade_descriptive_batch', fake_batch)
        assert _run(sub.id)['status'] == 'graded'
        sub.refresh_from_db()
        assert sub.status == SubStatus.GRADED
        assert seen['student_answer'] == 'متن تایپ‌شده'
        assert '[متن استخراج‌شده از تصویر پاسخ]' not in seen['student_answer']

    def test_missing_vision_model_fails_grading_instead_of_silent_zero(self, monkeypatch):
        """A deployment misconfiguration is not a bad-photo transient. For a
        photo-only answer, silently grading empty text as zero would be
        misleading, so the task must surface GRADING_FAILED."""
        for var in ('EXERCISE_VISION_MODEL', 'IMAGE_MODEL', 'MODEL_NAME'):
            monkeypatch.delenv(var, raising=False)
        ex, q, sub = _photo_submission(images=['exercises/answers/1/1/a.png'])
        monkeypatch.setattr(grading, '_read_answer_image', lambda path: _png_bytes())

        result = _run(sub.id)
        assert result['status'] == 'failed'
        sub.refresh_from_db()
        assert sub.status == SubStatus.GRADING_FAILED

    def test_fake_image_bytes_skipped_without_vision_call(self, monkeypatch):
        """(c) Bytes that fail is_real_image are skipped -> no vision call."""
        ex, q, sub = _photo_submission(images=['exercises/answers/1/1/a.png'])
        captured = self._mock_vision(monkeypatch)
        monkeypatch.setattr(grading, '_read_answer_image', lambda path: b'not an image')
        assert _run(sub.id)['status'] == 'graded'
        assert captured['calls'] == 0
        sub.refresh_from_db()
        assert sub.status == SubStatus.GRADED
        assert str(sub.score_points) == '0.00'  # no readable answer -> incorrect

    def test_unowned_image_path_ignored_without_storage_read(self, monkeypatch):
        """Client/legacy JSON must not let the grader open arbitrary storage paths."""
        ex, q, sub = _photo_submission()
        sub.answers = {str(q.id): {'images': ['exercises/answers/999/999/x.png']}}
        sub.save(update_fields=['answers'])
        captured = self._mock_vision(monkeypatch)
        read_called = {'n': 0}

        def fake_read(_path):
            read_called['n'] += 1
            return _png_bytes()

        monkeypatch.setattr(grading, '_read_answer_image', fake_read)
        assert _run(sub.id)['status'] == 'graded'
        assert captured['calls'] == 0
        assert read_called['n'] == 0

    def test_reference_answer_never_in_vision_prompt(self, monkeypatch):
        """(d) Leak guard: the vision call must never see the reference answer
        or the grading notes — it only transcribes the student's photo."""
        ex, q, sub = _photo_submission(
            qtype=QType.DESCRIPTIVE, reference='SECRET-REFERENCE',
            grading_notes='SECRET-NOTES', images=['exercises/answers/1/1/a.png'],
        )
        captured = self._mock_vision(monkeypatch, text='راه‌حل من')
        monkeypatch.setattr(grading, '_grade_descriptive_batch', lambda items: {})
        assert _run(sub.id)['status'] == 'graded'
        assert captured['calls'] == 1
        import json
        blob = json.dumps(captured['kwargs'].get('messages'), ensure_ascii=False, default=str)
        assert 'SECRET-REFERENCE' not in blob
        assert 'SECRET-NOTES' not in blob
        assert 'سؤال؟' in blob  # the question text IS the allowed context

    def test_image_cap_respected(self, monkeypatch):
        """(e) EXERCISE_MAX_IMAGES_PER_QUESTION (default 3) caps the payload."""
        paths = [f'exercises/answers/1/1/{i}.png' for i in range(5)]
        ex, q, sub = _photo_submission(images=paths)
        captured = self._mock_vision(monkeypatch, text='ب')
        assert _run(sub.id)['status'] == 'graded'
        content = captured['kwargs']['messages'][0]['content']
        image_parts = [p for p in content if p.get('type') == 'image_url']
        assert len(image_parts) == 3
        # Standard OpenAI shape — the AvalAI gateway ignores legacy shapes.
        assert all(p['image_url']['url'].startswith('data:image/') for p in image_parts)

    def test_extracted_text_appended_with_delimiter(self, monkeypatch):
        """Typed + photo on a descriptive question -> extracted text appended
        under the Persian delimiter, typed text first."""
        ex, q, sub = _photo_submission(
            qtype=QType.DESCRIPTIVE, reference='REF', text='متن تایپ‌شده',
            images=['exercises/answers/1/1/a.png'],
        )
        captured = self._mock_vision(monkeypatch, text='حل دست‌نویس')
        seen = {}

        def fake_batch(items):
            seen['student_answer'] = items[0]['student_answer']
            return {}

        monkeypatch.setattr(grading, '_grade_descriptive_batch', fake_batch)
        assert _run(sub.id)['status'] == 'graded'
        assert captured['calls'] == 1
        assert seen['student_answer'] == (
            'متن تایپ‌شده\n\n[متن استخراج‌شده از تصویر پاسخ]\nحل دست‌نویس'
        )
