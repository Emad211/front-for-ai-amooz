"""Interactive student-answer OCR: revision safety, ownership, and grading reuse."""
from __future__ import annotations

import base64

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.classes.models import (
    ClassCreationSession,
    ClassExercise,
    ClassExerciseQuestion,
    ClassExerciseSection,
    ClassInvitation,
    StudentExerciseAnswerSource,
    StudentExerciseAttempt,
    StudentExerciseSubmission,
)
from apps.classes.services.exercise_answer_ocr import (
    AnswerSourceFailed,
    AnswerSourcePending,
    Page,
    _bundle_result,
    apply_source,
    prepare_attempt_ocr,
    process_source,
)
from apps.classes.services import exercise_grading
from apps.classes.services.exercise_grading import build_question_snapshot
from apps.classes.services.schemas import (
    AnswerPageTranscriptionOutput,
    ExerciseAnswerBundleOutput,
    HandwritingTranscriptionOutput,
)

pytestmark = [pytest.mark.django_db, pytest.mark.api]

PHONE = '09121112233'
PNG = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
)


def _auth(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
    return client


def _world():
    teacher = baker.make(User, role=User.Role.TEACHER)
    student = baker.make(User, role=User.Role.STUDENT, phone=PHONE)
    session = baker.make(
        ClassCreationSession, teacher=teacher, pipeline_type='class', is_published=True,
    )
    ClassInvitation.objects.create(session=session, phone=PHONE, invite_code='OCR-INV')
    exercise = baker.make(ClassExercise, session=session, status=ClassExercise.Status.PUBLISHED)
    section = baker.make(ClassExerciseSection, exercise=exercise, order=0)
    question = baker.make(
        ClassExerciseQuestion,
        section=section,
        order=0,
        question_markdown='دو به علاوه دو چند می‌شود؟',
        reference_answer_markdown='پاسخ محرمانه ۴',
    )
    return teacher, student, session, exercise, question


def _base(session, exercise):
    return f'/api/classes/student/courses/{session.id}/exercises/{exercise.id}/'


def _source(submission, question=None, *, status='ready', revision=1):
    scope = 'question' if question else 'exercise'
    return baker.make(
        StudentExerciseAnswerSource,
        submission=submission,
        scope=scope,
        target_question=question,
        status=status,
        revision=revision,
        source_fingerprint='sha256:preview',
        raw_result={
            'answers': [{
                'question_id': question.id if question else None,
                'text': 'متن خام',
                'match_status': 'matched',
                'unclear_parts': [],
            }],
            'unmatched_fragments': [],
            'missing_question_ids': [],
        },
        reviewed_result={
            'answers': [{
                'question_id': question.id if question else None,
                'text': 'متن اصلاح‌شده',
                'match_status': 'matched',
                'unclear_parts': [],
            }],
            'unmatched_fragments': [],
            'missing_question_ids': [],
        },
    )


def test_question_upload_creates_server_owned_source_and_queues_task(
    monkeypatch, django_capture_on_commit_callbacks,
):
    _teacher, student, session, exercise, question = _world()
    monkeypatch.setenv('EXERCISE_ANSWER_OCR_PREVIEW_ENABLED', '1')
    queued = []
    monkeypatch.setattr(
        'apps.classes.tasks.process_student_answer_source.apply_async',
        lambda *args, **kwargs: queued.append((args, kwargs)),
    )
    with django_capture_on_commit_callbacks(execute=True):
        response = _auth(student).post(
            _base(session, exercise) + f'questions/{question.id}/image/',
            {'file': SimpleUploadedFile('answer.png', PNG, content_type='image/png')},
            format='multipart',
        )
    assert response.status_code == 201
    assert response.data['source']['scope'] == 'question'
    source = StudentExerciseAnswerSource.objects.get()
    assert source.submission.student == student
    assert source.target_question == question
    assert queued and queued[0][1]['countdown'] == 2


def test_whole_bundle_upload_accepts_multiple_images(monkeypatch):
    _teacher, student, session, exercise, _question = _world()
    monkeypatch.setenv('EXERCISE_ANSWER_OCR_PREVIEW_ENABLED', '1')
    monkeypatch.setattr(
        'apps.classes.tasks.process_student_answer_source.apply_async', lambda *args, **kwargs: None,
    )
    response = _auth(student).post(
        _base(session, exercise) + 'answer-source/',
        {
            'files': [
                SimpleUploadedFile('one.png', PNG, content_type='image/png'),
                SimpleUploadedFile('two.png', PNG, content_type='image/png'),
            ],
        },
        format='multipart',
    )
    assert response.status_code == 201
    assert response.data['scope'] == 'exercise'
    assert len(response.data['assets']) == 2


def test_stale_revision_patch_returns_409():
    _teacher, student, session, exercise, question = _world()
    submission = baker.make(
        StudentExerciseSubmission, exercise=exercise, student=student,
        status=StudentExerciseSubmission.Status.DRAFT,
    )
    _source(submission, question, revision=3)
    response = _auth(student).patch(
        _base(session, exercise) + f'questions/{question.id}/answer-source/',
        {'revision': 2, 'answers': [{'questionId': question.id, 'text': 'اصلاح'}]},
        format='json',
    )
    assert response.status_code == 409
    assert response.data['revision'] == 3


def test_student_edit_cannot_replace_server_owned_uncertainty_metadata():
    _teacher, student, session, exercise, question = _world()
    submission = baker.make(
        StudentExerciseSubmission, exercise=exercise, student=student,
        status=StudentExerciseSubmission.Status.DRAFT,
    )
    source = _source(submission, question)
    server_uncertainty = [{
        'page_number': 1,
        'excerpt': '۳',
        'reason': 'نماد کم‌رنگ است',
        'alternatives': ['۸'],
    }]
    source.reviewed_result['answers'][0]['quality'] = 'review_recommended'
    source.reviewed_result['answers'][0]['unclear_parts'] = server_uncertainty
    source.save(update_fields=['reviewed_result', 'updated_at'])

    response = _auth(student).patch(
        _base(session, exercise) + f'questions/{question.id}/answer-source/',
        {
            'revision': source.revision,
            'answers': [{
                'questionId': question.id,
                'text': 'متن اصلاح‌شده دانش‌آموز',
                'unclearParts': [{'reason': 'metadata جعلی client'}],
            }],
        },
        format='json',
    )

    assert response.status_code == 200
    source.refresh_from_db()
    reviewed = source.reviewed_result['answers'][0]
    assert reviewed['text'] == 'متن اصلاح‌شده دانش‌آموز'
    assert reviewed['quality'] == 'review_recommended'
    assert reviewed['unclear_parts'] == server_uncertainty


def test_source_is_fail_closed_for_another_student():
    _teacher, student, session, exercise, question = _world()
    submission = baker.make(StudentExerciseSubmission, exercise=exercise, student=student)
    _source(submission, question)
    stranger = baker.make(User, role=User.Role.STUDENT, phone='09129998877')
    response = _auth(stranger).get(
        _base(session, exercise) + f'questions/{question.id}/answer-source/',
    )
    assert response.status_code == 404


def test_apply_preserves_typed_answer_and_audits_raw_and_reviewed_text():
    _teacher, student, _session, exercise, question = _world()
    submission = baker.make(
        StudentExerciseSubmission,
        exercise=exercise,
        student=student,
        status=StudentExerciseSubmission.Status.DRAFT,
        answers={str(question.id): {'text': 'پاسخ تایپی مستقل'}},
    )
    source = _source(submission, question)
    apply_source(source)
    submission.refresh_from_db()
    entry = submission.answers[str(question.id)]
    assert entry['text'] == 'پاسخ تایپی مستقل'
    assert entry['ocr']['rawText'] == 'متن خام'
    assert entry['ocr']['text'] == 'متن اصلاح‌شده'
    assert entry['ocr']['correctedByStudent'] is True


def test_prepare_attempt_reuses_preview_without_vision_call():
    _teacher, student, _session, exercise, question = _world()
    submission = baker.make(
        StudentExerciseSubmission, exercise=exercise, student=student,
        status=StudentExerciseSubmission.Status.SUBMITTED,
    )
    source = _source(submission, question)
    attempt = baker.make(
        StudentExerciseAttempt,
        submission=submission,
        status=StudentExerciseAttempt.Status.SUBMITTED,
        grader_metadata={'answerSources': [{
            'sourceId': source.id, 'revision': source.revision,
            'scope': 'question', 'includeUnapplied': False,
        }]},
    )
    assert prepare_attempt_ocr(attempt) == 'ready'
    attempt.refresh_from_db()
    assert attempt.answers[str(question.id)]['ocr']['text'] == 'متن اصلاح‌شده'
    assert attempt.answers[str(question.id)]['ocr']['sourceFingerprint'] == 'sha256:preview'


def test_grading_preview_does_not_reopen_storage_or_call_vision(monkeypatch):
    _teacher, student, _session, exercise, question = _world()
    question.question_type = 'descriptive'
    question.max_points = 2
    question.save(update_fields=['question_type', 'max_points'])
    submission = baker.make(StudentExerciseSubmission, exercise=exercise, student=student)
    attempt = baker.make(
        StudentExerciseAttempt,
        submission=submission,
        answers={str(question.id): {
            'images': ['exercises/answers/sources/preview.png'],
            'ocr': {
                'sourceId': 7,
                'revision': 2,
                'rawText': 'متن خام',
                'text': 'متن تاییدشده',
                'quality': 'clear',
                'unclearParts': [],
                'sourceFingerprint': 'sha256:preview',
            },
        }},
        question_snapshot=build_question_snapshot(exercise),
    )
    monkeypatch.setattr(
        exercise_grading,
        '_load_image_contents',
        lambda _paths: (_ for _ in ()).throw(AssertionError('storage must not be reopened')),
    )
    monkeypatch.setattr(
        exercise_grading,
        '_transcribe_answer_images',
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError('vision must not run')),
    )
    seen = {}

    def fake_grade(items):
        seen['answer'] = items[0]['student_answer']
        return {str(question.id): {
            'question_id': str(question.id), 'llm_score': 1.0,
            'score_points': 1.0, 'max_points': 2.0, 'label': 'partial',
            'feedback': '', 'missing_points': [],
            'teacher_score': None, 'teacher_feedback': None,
        }}

    monkeypatch.setattr(exercise_grading, '_grade_descriptive_batch', fake_grade)
    result = exercise_grading.grade_attempt(attempt)
    assert 'متن تاییدشده' in seen['answer']
    assert result['score_points'] == 1.0


@pytest.mark.parametrize(
    ('source_status', 'error'),
    [
        (StudentExerciseAnswerSource.Status.READING, AnswerSourcePending),
        (StudentExerciseAnswerSource.Status.FAILED, AnswerSourceFailed),
    ],
)
def test_prepare_attempt_distinguishes_pending_from_failed(source_status, error):
    _teacher, student, _session, exercise, question = _world()
    submission = baker.make(StudentExerciseSubmission, exercise=exercise, student=student)
    source = _source(submission, question, status=source_status)
    attempt = baker.make(
        StudentExerciseAttempt,
        submission=submission,
        grader_metadata={'answerSources': [{
            'sourceId': source.id, 'revision': source.revision,
            'scope': 'question', 'includeUnapplied': False,
        }]},
    )
    with pytest.raises(error):
        prepare_attempt_ocr(attempt)


def test_solving_detail_never_exposes_reference_answer_with_ocr_source():
    _teacher, student, session, exercise, question = _world()
    submission = baker.make(StudentExerciseSubmission, exercise=exercise, student=student)
    _source(submission, question)
    response = _auth(student).get(_base(session, exercise))
    assert response.status_code == 200
    assert response.data['answerSources'][0]['answers'][0]['text'] == 'متن اصلاح‌شده'
    assert 'پاسخ محرمانه' not in str(response.data)


def test_question_preview_is_reused_and_prompt_never_contains_reference(monkeypatch):
    _teacher, student, _session, exercise, question = _world()
    submission = baker.make(
        StudentExerciseSubmission,
        exercise=exercise,
        student=student,
        status=StudentExerciseSubmission.Status.DRAFT,
    )
    source = baker.make(
        StudentExerciseAnswerSource,
        submission=submission,
        scope=StudentExerciseAnswerSource.Scope.QUESTION,
        target_question=question,
        status=StudentExerciseAnswerSource.Status.QUEUED,
    )
    monkeypatch.setenv('EXERCISE_ANSWER_OCR_MODEL', 'fixture-model')
    monkeypatch.setattr(
        'apps.classes.services.exercise_answer_ocr._load_pages',
        lambda _source: [Page(1, 'answer.png', PNG)],
    )
    prompts = []

    def fake_vision(_pages, *, prompt, schema):
        prompts.append(prompt)
        return HandwritingTranscriptionOutput(
            text='$2+2=4$', quality='clear', unclear_parts=[],
        )

    monkeypatch.setattr('apps.classes.services.exercise_answer_ocr._vision_call', fake_vision)
    assert process_source(source.id, 1)['reused'] is False
    assert process_source(source.id, 1)['reused'] is True
    assert len(prompts) == 1
    assert question.question_markdown in prompts[0]
    assert question.reference_answer_markdown not in prompts[0]
    submission.refresh_from_db()
    assert submission.answers[str(question.id)]['ocr']['text'] == '$2+2=4$'


BUNDLE_FIXTURES = [
    pytest.param(
        [{'question_id': 'target', 'text': 'پاسخ ۱', 'match_status': 'matched', 'unclear_parts': []}],
        [],
        id='persian-numbered-answer',
    ),
    pytest.param(
        [{'question_id': 'target', 'text': 'خط اول\nادامه در صفحه بعد', 'match_status': 'matched', 'unclear_parts': []}],
        [],
        id='continuation-on-next-page',
    ),
    pytest.param(
        [{'question_id': None, 'text': 'قطعه بدون شماره', 'match_status': 'unmatched', 'unclear_parts': []}],
        [1],
        id='unnumbered-fragment',
    ),
    pytest.param(
        [
            {'question_id': 'target', 'text': 'اول', 'match_status': 'matched', 'unclear_parts': []},
            {'question_id': 'target', 'text': 'تکراری', 'match_status': 'matched', 'unclear_parts': []},
        ],
        [],
        id='duplicate-mapping-is-demoted',
    ),
]


@pytest.mark.parametrize(('mapped_answers', 'provider_missing'), BUNDLE_FIXTURES)
def test_bundle_mapping_fixture_normalization_and_no_reference_leak(
    monkeypatch, mapped_answers, provider_missing,
):
    _teacher, student, _session, exercise, question = _world()
    submission = baker.make(StudentExerciseSubmission, exercise=exercise, student=student)
    source = baker.make(
        StudentExerciseAnswerSource,
        submission=submission,
        scope=StudentExerciseAnswerSource.Scope.EXERCISE,
        target_question=None,
        status=StudentExerciseAnswerSource.Status.SEGMENTING,
    )
    monkeypatch.setenv('EXERCISE_ANSWER_OCR_MODEL', 'fixture-model')
    mapped_answers = [
        {**item, 'question_id': question.id if item.get('question_id') == 'target' else item.get('question_id')}
        for item in mapped_answers
    ]
    monkeypatch.setattr(
        'apps.classes.services.exercise_answer_ocr._vision_call',
        lambda *_args, **_kwargs: AnswerPageTranscriptionOutput(
            text='## صفحه ۱\nسؤال ۱: پاسخ دست‌نویس', quality='clear', unclear_parts=[],
        ),
    )
    mapping_prompts = []

    def fake_structured(**kwargs):
        mapping_prompts.append(kwargs['contents'])
        return ExerciseAnswerBundleOutput(
            answers=mapped_answers,
            unmatched_fragments=[],
            missing_question_ids=provider_missing,
        )

    monkeypatch.setattr('apps.classes.services.exercise_answer_ocr.generate_structured', fake_structured)
    result = _bundle_result(source, [Page(1, 'one.png', PNG), Page(2, 'two.png', PNG)], 1)
    assert question.reference_answer_markdown not in mapping_prompts[0]
    ids = [item.get('question_id') for item in result['answers']]
    assert len([qid for qid in ids if qid == question.id]) <= 1
    assert result['missing_question_ids'] == ([] if question.id in ids else [question.id])
