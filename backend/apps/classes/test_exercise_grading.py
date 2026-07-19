"""E6 — exercise grading: LLM-mocked descriptive grading + deterministic MCQ/
fill-blank (no LLM) + correct sum + idempotent re-run + GRADING_FAILED + the
Low-1 guard (no reference answer in result). 0 tokens.
"""
from __future__ import annotations

import json
from decimal import Decimal

import pytest
from celery.exceptions import Retry as CeleryRetry
from model_bakery import baker

from apps.chatbot.services.llm_client import ProviderTransientError
from apps.commons.token_tracker import get_current_session_id, get_current_user
from apps.classes import tasks
from apps.classes.services import exercise_grading as grading
from apps.classes.models import (
    ClassExercise,
    ClassExerciseQuestion,
    ClassExerciseSection,
    StudentExerciseAttempt,
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


def _run_attempt(submission_id, attempt_id):
    return tasks.grade_exercise_submission.apply(args=[submission_id, attempt_id]).result


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

    def test_private_grading_notes_reach_grader_but_not_result(self, monkeypatch):
        seen = {}

        def fake_batch(items):
            seen['grading_notes'] = items[0]['grading_notes']
            item = items[0]
            return {item['question_id']: {
                'question_id': item['question_id'], 'llm_score': 2.0,
                'score_points': 2.0, 'max_points': item['max_points'],
                'label': 'partially_correct', 'feedback': '', 'missing_points': [],
                'teacher_score': None, 'teacher_feedback': None,
            }}

        _ex, question, _q2, submission, _calls = _submission_with_questions(
            monkeypatch, descriptive_llm=fake_batch,
        )
        question.grading_notes = 'روی روش حل هم امتیاز بده.'
        question.save(update_fields=['grading_notes'])
        assert _run(submission.id)['status'] == 'graded'
        submission.refresh_from_db()
        assert seen['grading_notes'] == 'روی روش حل هم امتیاز بده.'
        assert 'grading_notes' not in json.dumps(submission.result, ensure_ascii=False)

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

    def test_llm_usage_is_attributed_to_session_teacher(self, monkeypatch):
        seen = {}

        def attributed_batch(items):
            seen['user_id'] = get_current_user().id
            seen['session_id'] = get_current_session_id()
            item = items[0]
            return {item['question_id']: {
                'question_id': item['question_id'],
                'llm_score': 1.0,
                'score_points': 1.0,
                'max_points': item['max_points'],
                'label': 'partially_correct',
                'feedback': '',
                'missing_points': [],
                'teacher_score': None,
                'teacher_feedback': None,
            }}

        ex, _q1, _q2, sub, _calls = _submission_with_questions(
            monkeypatch,
            descriptive_llm=attributed_batch,
        )

        assert _run(sub.id)['status'] == 'graded'
        assert seen == {
            'user_id': ex.session.teacher_id,
            'session_id': ex.session_id,
        }

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


class TestStableResubmissionGrading:
    def _new_attempt(self, submission):
        latest = submission.attempts.order_by('-attempt_number').first()
        attempt = StudentExerciseAttempt.objects.create(
            submission=submission,
            attempt_number=(latest.attempt_number + 1) if latest else 1,
            status=StudentExerciseAttempt.Status.SUBMITTED,
            answers=submission.answers,
            is_late=submission.is_late,
        )
        submission.current_attempt = attempt
        submission.status = SubStatus.SUBMITTED
        submission.result = {}
        submission.save(update_fields=['current_attempt', 'status', 'result'])
        return attempt

    def test_identical_second_attempt_reuses_exact_result_without_llm(self, monkeypatch):
        _ex, _q1, _q2, submission, calls = _submission_with_questions(monkeypatch)
        assert _run(submission.id)['status'] == 'graded'
        submission.refresh_from_db()
        first_attempt = submission.current_attempt
        first_result = first_attempt.result
        assert calls['n'] == 1

        second_attempt = self._new_attempt(submission)
        assert _run_attempt(submission.id, second_attempt.id)['status'] == 'graded'
        second_attempt.refresh_from_db()

        assert calls['n'] == 1
        assert second_attempt.result == first_result
        assert second_attempt.grader_metadata['reusedQuestions'] == 2
        assert second_attempt.grader_metadata['regradedQuestions'] == 0

    def test_teacher_override_is_not_carried_to_reused_attempt(self, monkeypatch):
        _ex, q1, q2, submission, _calls = _submission_with_questions(monkeypatch)
        _run(submission.id)
        submission.refresh_from_db()
        first = submission.current_attempt
        result = first.result
        row = next(item for item in result['per_question'] if item['question_id'] == str(q1.id))
        row['teacher_score'] = 1.25
        row['teacher_feedback'] = 'اصلاح معلم'
        deterministic_row = next(
            item for item in result['per_question']
            if item['question_id'] == str(q2.id)
        )
        deterministic_row['teacher_score'] = 0.5
        deterministic_row['teacher_feedback'] = 'اصلاح تستی'
        deterministic_row['score_points'] = 0.5
        first.result = result
        first.save(update_fields=['result'])

        second = self._new_attempt(submission)
        _run_attempt(submission.id, second.id)
        second.refresh_from_db()
        reused = next(
            item for item in second.result['per_question']
            if item['question_id'] == str(q1.id)
        )
        assert reused['teacher_score'] is None
        assert reused['teacher_feedback'] is None
        assert reused['score_points'] == reused['llm_score']
        deterministic_reused = next(
            item for item in second.result['per_question']
            if item['question_id'] == str(q2.id)
        )
        assert deterministic_reused['teacher_score'] is None
        assert deterministic_reused['teacher_feedback'] is None
        assert deterministic_reused['score_points'] == 2.0
        assert deterministic_reused['score_points'] == deterministic_reused['llm_score']

    def test_changing_one_answer_only_regrades_that_question(self, monkeypatch):
        _ex, q1, _q2, submission, calls = _submission_with_questions(monkeypatch)
        _run(submission.id)
        submission.refresh_from_db()
        submission.answers[str(q1.id)]['text'] = 'پاسخ تغییرکرده'
        submission.save(update_fields=['answers'])

        second = self._new_attempt(submission)
        _run_attempt(submission.id, second.id)
        second.refresh_from_db()

        assert calls['n'] == 2
        assert second.grader_metadata['reusedQuestions'] == 1
        assert second.grader_metadata['regradedQuestions'] == 1

    def test_stale_attempt_task_cannot_overwrite_current_projection(self, monkeypatch):
        _ex, _q1, _q2, submission, _calls = _submission_with_questions(monkeypatch)
        first = StudentExerciseAttempt.objects.create(
            submission=submission,
            attempt_number=1,
            status=StudentExerciseAttempt.Status.GRADING,
            answers=submission.answers,
            grading_task_id='stale-task',
        )
        second = StudentExerciseAttempt.objects.create(
            submission=submission,
            attempt_number=2,
            status=StudentExerciseAttempt.Status.SUBMITTED,
            answers=submission.answers,
        )
        submission.current_attempt = second
        submission.status = SubStatus.SUBMITTED
        submission.result = {'sentinel': 'current'}
        submission.save(update_fields=['current_attempt', 'status', 'result'])
        monkeypatch.setattr(tasks.grade_exercise_submission.request, 'id', 'stale-task', raising=False)

        assert tasks.grade_exercise_submission.run(submission.id, first.id)['status'] == 'graded'
        submission.refresh_from_db()
        first.refresh_from_db()

        assert first.status == StudentExerciseAttempt.Status.GRADED
        assert submission.current_attempt_id == second.id
        assert submission.status == SubStatus.SUBMITTED
        assert submission.result == {'sentinel': 'current'}

    def test_redo_opened_during_grading_is_not_overwritten(self, monkeypatch):
        _ex, _q1, _q2, submission, _calls = _submission_with_questions(monkeypatch)
        original_grade_attempt = grading.grade_attempt

        def grade_then_open_redo(attempt):
            result = original_grade_attempt(attempt)
            StudentExerciseSubmission.objects.filter(id=submission.id).update(
                status=SubStatus.DRAFT,
                current_attempt=None,
                grading_task_id='',
            )
            return result

        monkeypatch.setattr(grading, 'grade_attempt', grade_then_open_redo)

        assert _run(submission.id)['status'] == 'graded'
        submission.refresh_from_db()

        assert submission.status == SubStatus.DRAFT
        assert submission.current_attempt_id is None

    def test_grading_uses_question_snapshot_not_later_edits(self, monkeypatch):
        ex, question, _q2, submission, _calls = _submission_with_questions(monkeypatch)
        captured = {}

        def capture_batch(items):
            captured.update(items[0])
            return {
                item['question_id']: {
                    'question_id': item['question_id'],
                    'llm_score': 1.0,
                    'score_points': 1.0,
                    'max_points': item['max_points'],
                    'label': 'partially_correct',
                    'feedback': '',
                    'missing_points': [],
                    'teacher_score': None,
                    'teacher_feedback': None,
                }
                for item in items
            }

        monkeypatch.setattr(grading, '_grade_descriptive_batch', capture_batch)
        attempt = StudentExerciseAttempt.objects.create(
            submission=submission,
            attempt_number=1,
            status=StudentExerciseAttempt.Status.SUBMITTED,
            answers=submission.answers,
            question_snapshot=grading.build_question_snapshot(ex),
        )
        submission.current_attempt = attempt
        submission.save(update_fields=['current_attempt'])
        question.question_markdown = 'سؤال ویرایش‌شده'
        question.reference_answer_markdown = 'مرجع ویرایش‌شده'
        question.grading_notes = 'یادداشت ویرایش‌شده'
        question.max_points = Decimal('9')
        question.save()

        assert _run_attempt(submission.id, attempt.id)['status'] == 'graded'

        assert captured['question_text'] == 'توضیح بده'
        assert captured['reference_answer'] == 'SECRET-REFERENCE'
        assert captured['grading_notes'] == ''
        assert captured['max_points'] == 4.0


class TestQuestionFingerprint:
    @pytest.mark.parametrize(
        ('field', 'value'),
        [
            ('question_markdown', 'متن تغییرکرده'),
            ('reference_answer_markdown', 'مرجع تغییرکرده'),
            ('grading_notes', 'نکته تازه معلم'),
            ('max_points', Decimal('7.25')),
        ],
    )
    def test_rubric_change_invalidates_fingerprint(self, monkeypatch, field, value):
        _ex, question, _q2, submission, _calls = _submission_with_questions(monkeypatch)
        before = grading._question_fingerprint(
            question, submission.answers, student_id=submission.student_id,
        )
        setattr(question, field, value)
        after = grading._question_fingerprint(
            question, submission.answers, student_id=submission.student_id,
        )
        assert after != before

    def test_model_or_prompt_change_invalidates_fingerprint(self, monkeypatch):
        _ex, question, _q2, submission, _calls = _submission_with_questions(monkeypatch)
        monkeypatch.setenv('EXERCISE_GRADING_MODEL', 'grader-a')
        before = grading._question_fingerprint(
            question, submission.answers, student_id=submission.student_id,
        )
        monkeypatch.setenv('EXERCISE_GRADING_MODEL', 'grader-b')
        model_changed = grading._question_fingerprint(
            question, submission.answers, student_id=submission.student_id,
        )
        monkeypatch.setitem(
            grading.PROMPTS['exercise_grading'],
            'default',
            grading.PROMPTS['exercise_grading']['default'] + '\ncontract-v-next',
        )
        prompt_changed = grading._question_fingerprint(
            question, submission.answers, student_id=submission.student_id,
        )
        assert model_changed != before
        assert prompt_changed != model_changed

    def test_image_content_change_under_same_path_invalidates_fingerprint(self, monkeypatch):
        _ex, question, submission = _photo_submission(images=['answer.png'])
        content = {'value': b'first-image-content'}
        monkeypatch.setattr(
            grading,
            '_read_answer_image',
            lambda _path: content['value'],
        )

        before = grading._question_fingerprint(
            question,
            submission.answers,
            student_id=submission.student_id,
        )
        content['value'] = b'replaced-image-content'
        after = grading._question_fingerprint(
            question,
            submission.answers,
            student_id=submission.student_id,
        )

        assert after != before


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

    def test_typed_deterministic_answer_does_not_read_irrelevant_image(self, monkeypatch):
        _ex, _q, sub = _photo_submission(text='ب', images=['answer.png'])
        monkeypatch.setattr(
            grading,
            '_read_answer_image',
            lambda _path: (_ for _ in ()).throw(AssertionError('image must be ignored')),
        )
        monkeypatch.setattr(
            grading,
            '_grade_descriptive_batch',
            lambda _items: (_ for _ in ()).throw(AssertionError('grading LLM must not run')),
        )

        assert _run(sub.id)['status'] == 'graded'
        sub.refresh_from_db()
        assert sub.score_points == Decimal('2.00')

    def test_missing_image_falls_back_to_typed_descriptive_answer(self, monkeypatch):
        _ex, _q, sub = _photo_submission(
            qtype=QType.DESCRIPTIVE,
            reference='مرجع',
            text='پاسخ تایپی',
            images=['answer.png'],
        )
        monkeypatch.setattr(
            grading,
            '_read_answer_image',
            lambda _path: (_ for _ in ()).throw(FileNotFoundError('missing object')),
        )
        seen = {}

        def grade_typed(items):
            item = items[0]
            seen['student_answer'] = item['student_answer']
            return {item['question_id']: {
                'question_id': item['question_id'],
                'llm_score': 1.0,
                'score_points': 1.0,
                'max_points': item['max_points'],
                'label': 'partially_correct',
                'feedback': '',
                'missing_points': [],
                'teacher_score': None,
                'teacher_feedback': None,
            }}

        monkeypatch.setattr(grading, '_grade_descriptive_batch', grade_typed)

        assert _run(sub.id)['status'] == 'graded'
        assert seen['student_answer'] == 'پاسخ تایپی'

    def test_identical_photo_attempt_reuses_ocr_and_grade(self, monkeypatch):
        ex, q, submission = _photo_submission(images=['answer.png'])
        captured = self._mock_vision(monkeypatch, text='ب')
        monkeypatch.setattr(
            grading,
            '_grade_descriptive_batch',
            lambda _items: (_ for _ in ()).throw(AssertionError('unexpected grading LLM')),
        )
        assert _run(submission.id)['status'] == 'graded'
        submission.refresh_from_db()
        first = submission.current_attempt
        second = StudentExerciseAttempt.objects.create(
            submission=submission,
            attempt_number=2,
            status=StudentExerciseAttempt.Status.SUBMITTED,
            answers=submission.answers,
        )
        submission.current_attempt = second
        submission.status = SubStatus.SUBMITTED
        submission.save(update_fields=['current_attempt', 'status'])

        assert _run_attempt(submission.id, second.id)['status'] == 'graded'
        second.refresh_from_db()
        assert captured['calls'] == 1
        assert second.result == first.result
        assert second.grader_metadata['reusedQuestions'] == 1

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

    def test_transient_vision_failure_retries_without_caching_empty_ocr(self, monkeypatch):
        _ex, _q, sub = _photo_submission(images=['answer.png'])
        self._mock_vision(
            monkeypatch,
            raise_exc=ProviderTransientError('vision gateway 502'),
        )

        def fake_retry(*, exc=None, countdown=None):
            raise CeleryRetry(exc=exc, when=countdown)

        monkeypatch.setattr(tasks.grade_exercise_submission.request, 'id', 'vision-retry', raising=False)
        monkeypatch.setattr(tasks.grade_exercise_submission, 'retry', fake_retry)

        with pytest.raises(CeleryRetry):
            tasks.grade_exercise_submission.run(sub.id)

        sub.refresh_from_db()
        attempt = sub.current_attempt
        attempt.refresh_from_db()
        assert sub.status == SubStatus.GRADING
        assert attempt.status == StudentExerciseAttempt.Status.GRADING
        assert attempt.ocr_text == {}

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
