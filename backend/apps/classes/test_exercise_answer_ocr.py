"""Interactive student-answer OCR: revision safety, ownership, and grading reuse."""
from __future__ import annotations

import base64
import hashlib
import importlib
from datetime import timedelta
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.cache import cache
from django.core.files.storage import storages
from django.apps import apps as django_apps
from django.test import RequestFactory, override_settings
from django.utils import timezone
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
    StudentExerciseAnswerAsset,
    StudentExerciseAnswerSource,
    StudentExerciseAttempt,
    StudentExerciseSubmission,
)
from apps.classes.services.exercise_answer_ocr import (
    AnswerSourceFailed,
    AnswerSourcePending,
    Page,
    StaleAnswerSource,
    _normalize_image_page,
    _render_pdf,
    _bundle_result,
    apply_source,
    freeze_sources,
    prepare_attempt_ocr,
    process_source,
    serialize_source,
)
from apps.classes.services.exercise_grading import _student_ocr
from apps.classes.views_exercises import _validate_answer_source_uploads
from apps.classes.services import exercise_grading
from apps.classes.services.exercise_grading import build_question_snapshot
from apps.classes.tasks import (
    cleanup_inactive_answer_ocr_assets,
    process_student_answer_source,
    recover_queued_answer_ocr_sources,
)
from apps.classes.services.schemas import (
    AnswerPageTranscriptionOutput,
    ExerciseAnswerBundleOutput,
    HandwritingTranscriptionOutput,
)
from apps.commons.structured_llm import StructuredOutputError, generate_structured
from core.middleware import AnswerOcrUploadLimitMiddleware

pytestmark = [pytest.mark.django_db, pytest.mark.api]

PHONE = '09121112233'
PNG = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
)


@pytest.fixture(autouse=True)
def _enable_answer_ocr_preview(monkeypatch):
    monkeypatch.setenv('EXERCISE_ANSWER_OCR_PREVIEW_ENABLED', '1')


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
    source = StudentExerciseAnswerSource.objects.get(id=response.data['source']['id'])
    assert source.submission.student == student
    assert source.target_question == question
    asset = StudentExerciseAnswerAsset.objects.get(source=source)
    assert asset.file.name.endswith('.png')
    assert 'answer.png' not in asset.file.name
    assert response.data['path'] == f'/api/classes/exercise-answer-assets/{asset.id}/content/'
    assert queued and queued[0][1]['countdown'] == 2


def test_rapid_question_upload_supersedes_settling_revision(
    monkeypatch, django_capture_on_commit_callbacks,
):
    _teacher, student, session, exercise, question = _world()
    queued = []
    monkeypatch.setattr(
        'apps.classes.tasks.process_student_answer_source.apply_async',
        lambda *args, **kwargs: queued.append((args, kwargs)),
    )
    client = _auth(student)

    with django_capture_on_commit_callbacks(execute=True):
        first = client.post(
            _base(session, exercise) + f'questions/{question.id}/image/',
            {'file': SimpleUploadedFile('one.png', PNG, content_type='image/png')},
            format='multipart',
        )
    source = StudentExerciseAnswerSource.objects.get(id=first.data['source']['id'])
    assert source.processing_task_id

    with django_capture_on_commit_callbacks(execute=True):
        second = client.post(
            _base(session, exercise) + f'questions/{question.id}/image/',
            {'file': SimpleUploadedFile('two.png', PNG + b'2', content_type='image/png')},
            format='multipart',
        )

    assert first.status_code == 201
    assert second.status_code == 201
    source.refresh_from_db()
    assert source.revision == 2
    assert source.assets.filter(is_active=True).count() == 2
    assert [call[1]['args'][1] for call in queued] == [1, 2]


def test_rapid_bundle_replacement_supersedes_settling_revision(
    monkeypatch, django_capture_on_commit_callbacks,
):
    _teacher, student, session, exercise, _question = _world()
    queued = []
    monkeypatch.setattr(
        'apps.classes.tasks.process_student_answer_source.apply_async',
        lambda *args, **kwargs: queued.append((args, kwargs)),
    )
    client = _auth(student)

    with django_capture_on_commit_callbacks(execute=True):
        first = client.post(
            _base(session, exercise) + 'answer-source/',
            {'files': [SimpleUploadedFile('one.png', PNG, content_type='image/png')]},
            format='multipart',
        )
    source = StudentExerciseAnswerSource.objects.get(id=first.data['id'])
    first_asset = source.assets.get()
    assert source.processing_task_id

    with django_capture_on_commit_callbacks(execute=True):
        second = client.post(
            _base(session, exercise) + 'answer-source/',
            {'files': [SimpleUploadedFile('two.png', PNG + b'2', content_type='image/png')]},
            format='multipart',
        )

    assert second.status_code == 201
    source.refresh_from_db()
    first_asset.refresh_from_db()
    assert source.revision == 2
    assert first_asset.is_active is False
    assert source.assets.filter(is_active=True).count() == 1
    assert [call[1]['args'][1] for call in queued] == [1, 2]


def test_question_image_limit_rejection_does_not_mutate_source(monkeypatch):
    _teacher, student, session, exercise, question = _world()
    submission = baker.make(
        StudentExerciseSubmission, exercise=exercise, student=student,
        status=StudentExerciseSubmission.Status.DRAFT,
    )
    source = _source(submission, question, revision=4)
    for order in range(3):
        baker.make(
            StudentExerciseAnswerAsset,
            source=source,
            order=order,
            sha256=f'{order:064x}',
            file=SimpleUploadedFile(f'{order}.png', PNG, content_type='image/png'),
            content_type='image/png',
            byte_size=len(PNG),
        )
    queued = []
    monkeypatch.setattr(
        'apps.classes.tasks.process_student_answer_source.apply_async',
        lambda *args, **kwargs: queued.append((args, kwargs)),
    )

    response = _auth(student).post(
        _base(session, exercise) + f'questions/{question.id}/image/',
        {'file': SimpleUploadedFile('fourth.png', PNG + b'x', content_type='image/png')},
        format='multipart',
    )

    assert response.status_code == 400
    source.refresh_from_db()
    assert source.revision == 4
    assert source.status == StudentExerciseAnswerSource.Status.READY
    assert source.raw_result['answers'][0]['text'] == 'متن خام'
    assert source.reviewed_result['answers'][0]['text'] == 'متن اصلاح‌شده'
    assert queued == []


def test_declared_oversized_bundle_is_rejected_before_read(monkeypatch):
    class OversizedUpload:
        size = 31

        def read(self):
            pytest.fail('oversized upload must be rejected before reading its body')

    monkeypatch.setattr(
        'apps.classes.views_exercises.answer_ocr_max_bytes', lambda: 30,
    )
    validated, response = _validate_answer_source_uploads([OversizedUpload()])

    assert validated == []
    assert response.status_code == 413


def test_validated_bundle_retains_metadata_not_payload_bytes():
    upload = SimpleUploadedFile('answer.png', PNG, content_type='image/png')

    validated, response = _validate_answer_source_uploads([upload])

    assert response is None
    assert len(validated) == 1
    stored_upload, content_type, page_count, byte_size, sha256 = validated[0]
    assert stored_upload is upload
    assert content_type == 'image/png'
    assert page_count == 1
    assert byte_size == len(PNG)
    assert sha256 == hashlib.sha256(PNG).hexdigest()
    assert all(not isinstance(item, bytes) for item in validated[0])


@override_settings(EXERCISE_ANSWER_OCR_REQUEST_MAX_BYTES=100)
def test_route_upload_limit_rejects_before_source_or_task(
    monkeypatch, django_capture_on_commit_callbacks,
):
    _teacher, student, session, exercise, _question = _world()
    queued = []
    monkeypatch.setattr(
        'apps.classes.tasks.process_student_answer_source.apply_async',
        lambda *args, **kwargs: queued.append((args, kwargs)),
    )

    with django_capture_on_commit_callbacks(execute=True):
        response = _auth(student).post(
            _base(session, exercise) + 'answer-source/',
            {'files': [SimpleUploadedFile('large.png', PNG * 4, content_type='image/png')]},
            format='multipart',
        )

    assert response.status_code == 413
    assert not StudentExerciseAnswerSource.objects.exists()
    assert queued == []


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
    stored_names = list(StudentExerciseAnswerAsset.objects.values_list('file', flat=True))
    assert all('one.png' not in name and 'two.png' not in name for name in stored_names)


def test_page_quota_rejects_changed_bundle_before_asset_or_task(
    monkeypatch, django_capture_on_commit_callbacks,
):
    _teacher, student, session, exercise, _question = _world()
    monkeypatch.setenv('EXERCISE_ANSWER_OCR_MAX_PAGES_PER_HOUR', '1')
    queued = []
    monkeypatch.setattr(
        'apps.classes.tasks.process_student_answer_source.apply_async',
        lambda *args, **kwargs: queued.append((args, kwargs)),
    )
    client = _auth(student)
    with django_capture_on_commit_callbacks(execute=True):
        first = client.post(
            _base(session, exercise) + 'answer-source/',
            {'files': [SimpleUploadedFile('one.png', PNG, content_type='image/png')]},
            format='multipart',
        )
    assert first.status_code == 201
    source = StudentExerciseAnswerSource.objects.get(submission__student=student)
    first_asset_ids = list(source.assets.values_list('id', flat=True))
    source.processing_task_id = ''
    source.save(update_fields=['processing_task_id'])

    with django_capture_on_commit_callbacks(execute=True):
        second = client.post(
            _base(session, exercise) + 'answer-source/',
            {'files': [SimpleUploadedFile('two.png', PNG + b'x', content_type='image/png')]},
            format='multipart',
        )

    assert second.status_code == 429
    source.refresh_from_db()
    assert source.revision == 1
    assert list(source.assets.values_list('id', flat=True)) == first_asset_ids
    assert len(queued) == 1


def test_answer_source_status_endpoint_is_narrow():
    _teacher, student, session, exercise, question = _world()
    submission = baker.make(StudentExerciseSubmission, exercise=exercise, student=student)
    source = _source(submission, question, status=StudentExerciseAnswerSource.Status.READING)
    baker.make(
        StudentExerciseAnswerAsset,
        source=source,
        file=SimpleUploadedFile('answer.png', PNG, content_type='image/png'),
        content_type='image/png',
        byte_size=len(PNG),
        sha256='c' * 64,
    )

    response = _auth(student).get(_base(session, exercise) + 'answer-sources/status/')

    assert response.status_code == 200
    assert set(response.data) == {'answerSources'}
    item = response.data['answerSources'][0]
    assert item['status'] == 'reading'
    assert set(item) == {
        'id', 'scope', 'questionId', 'status', 'revision', 'workflowStage',
        'workflowMessage', 'progressPercent',
    }
    assert response['Cache-Control'] == 'private, no-store'
    assert 'Authorization' in response['Vary']


def test_whole_bundle_cannot_be_applied_until_every_fragment_has_a_question():
    _teacher, student, session, exercise, _question = _world()
    submission = baker.make(
        StudentExerciseSubmission, exercise=exercise, student=student,
        status=StudentExerciseSubmission.Status.DRAFT,
    )
    source = _source(submission)

    response = _auth(student).post(
        _base(session, exercise) + 'answer-source/apply/',
        {'revision': source.revision},
        format='json',
    )

    assert response.status_code == 409
    source.refresh_from_db()
    assert source.applied_at is None


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


def test_answer_asset_content_is_private_and_owner_scoped():
    teacher, student, _session, exercise, question = _world()
    submission = baker.make(StudentExerciseSubmission, exercise=exercise, student=student)
    source = _source(submission, question)
    asset = baker.make(
        StudentExerciseAnswerAsset,
        source=source,
        file=SimpleUploadedFile('private.png', PNG, content_type='image/png'),
        content_type='image/png',
        byte_size=len(PNG),
        sha256='a' * 64,
    )
    url = f'/api/classes/exercise-answer-assets/{asset.id}/content/'

    assert APIClient().get(url).status_code == 401
    stranger = baker.make(User, role=User.Role.STUDENT, phone='09128887766')
    assert _auth(stranger).get(url).status_code == 404
    student_response = _auth(student).get(url)
    assert student_response.status_code == 200
    assert _auth(teacher).get(url).status_code == 404
    baker.make(
        StudentExerciseAttempt,
        submission=submission,
        grader_metadata={'answerSources': [{
            'sourceId': source.id,
            'revision': source.revision,
            'assetIds': [asset.id],
        }]},
    )
    teacher_response = _auth(teacher).get(url)
    assert teacher_response.status_code == 200
    assert student_response['Cache-Control'] == 'private, no-store'
    assert student_response['X-Content-Type-Options'] == 'nosniff'


def test_serialized_source_uses_private_asset_endpoint():
    _teacher, student, _session, exercise, question = _world()
    submission = baker.make(StudentExerciseSubmission, exercise=exercise, student=student)
    source = _source(submission, question)
    asset = baker.make(
        StudentExerciseAnswerAsset,
        source=source,
        file=SimpleUploadedFile('private.png', PNG, content_type='image/png'),
        content_type='image/png',
        byte_size=len(PNG),
        sha256='b' * 64,
    )

    payload = serialize_source(source)

    assert payload['assets'][0]['url'] == f'/api/classes/exercise-answer-assets/{asset.id}/content/'
    assert '/media/' not in payload['assets'][0]['url']

    assert APIClient().get(f'/media/{asset.file.name}').status_code == 404


def test_cleanup_deletes_only_unreferenced_inactive_assets(
    monkeypatch, django_capture_on_commit_callbacks,
):
    _teacher, student, _session, exercise, question = _world()
    submission = baker.make(StudentExerciseSubmission, exercise=exercise, student=student)
    source = _source(submission, question)
    retained = baker.make(
        StudentExerciseAnswerAsset,
        source=source,
        order=0,
        is_active=False,
        file=SimpleUploadedFile('retained.png', PNG, content_type='image/png'),
        content_type='image/png',
        byte_size=len(PNG),
        sha256='d' * 64,
    )
    removable = baker.make(
        StudentExerciseAnswerAsset,
        source=source,
        order=1,
        is_active=False,
        file=SimpleUploadedFile('removable.png', PNG, content_type='image/png'),
        content_type='image/png',
        byte_size=len(PNG),
        sha256='e' * 64,
    )
    old = timezone.now() - timedelta(days=31)
    StudentExerciseAnswerAsset.objects.filter(id__in=[retained.id, removable.id]).update(
        deactivated_at=old,
    )
    baker.make(
        StudentExerciseAttempt,
        submission=submission,
        answers={str(question.id): {'images': [retained.file.name]}},
    )
    deleted_paths = []
    monkeypatch.setattr(
        'apps.classes.signals.delete_answer_source_file',
        lambda path: deleted_paths.append(path),
    )

    with django_capture_on_commit_callbacks(execute=True):
        result = cleanup_inactive_answer_ocr_assets.run()

    assert result['deleted_count'] == 1
    assert deleted_paths == [removable.file.name]
    assert StudentExerciseAnswerAsset.objects.filter(id=retained.id).exists()
    assert not StudentExerciseAnswerAsset.objects.filter(id=removable.id).exists()


def test_cleanup_preserves_asset_ids_frozen_in_attempt(monkeypatch):
    _teacher, student, _session, exercise, question = _world()
    submission = baker.make(StudentExerciseSubmission, exercise=exercise, student=student)
    source = _source(submission, question)
    asset = baker.make(
        StudentExerciseAnswerAsset,
        source=source,
        is_active=False,
        deactivated_at=timezone.now() - timedelta(days=31),
        file=SimpleUploadedFile('history.png', PNG, content_type='image/png'),
        content_type='image/png',
        byte_size=len(PNG),
        sha256='f' * 64,
    )
    baker.make(
        StudentExerciseAttempt,
        submission=submission,
        grader_metadata={'answerSources': [{
            'sourceId': source.id,
            'revision': source.revision,
            'scope': 'question',
            'assetIds': [asset.id],
        }]},
    )
    deleted = []
    monkeypatch.setattr(
        'django.core.files.storage.default_storage.delete', deleted.append,
    )

    result = cleanup_inactive_answer_ocr_assets.run()

    assert result['deleted_count'] == 0
    assert deleted == []
    assert StudentExerciseAnswerAsset.objects.filter(id=asset.id).exists()


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


def test_attempt_detail_uses_assets_frozen_for_selected_attempt():
    teacher, student, _session, exercise, question = _world()
    submission = baker.make(StudentExerciseSubmission, exercise=exercise, student=student)
    source = _source(submission, question)
    old_asset = baker.make(
        StudentExerciseAnswerAsset,
        source=source,
        order=0,
        is_active=False,
        deactivated_at=timezone.now(),
        file=SimpleUploadedFile('old.png', PNG, content_type='image/png'),
        content_type='image/png', byte_size=len(PNG), sha256='1' * 64,
    )
    new_asset = baker.make(
        StudentExerciseAnswerAsset,
        source=source,
        order=1,
        is_active=True,
        file=SimpleUploadedFile('new.png', PNG, content_type='image/png'),
        content_type='image/png', byte_size=len(PNG), sha256='2' * 64,
    )
    attempt = baker.make(
        StudentExerciseAttempt,
        submission=submission,
        attempt_number=1,
        grader_metadata={'answerSources': [{
            'sourceId': source.id,
            'revision': 1,
            'scope': 'question',
            'assetIds': [old_asset.id],
        }]},
    )

    response = _auth(teacher).get(
        f'/api/classes/exercises/submissions/{submission.id}/?attemptId={attempt.id}',
    )

    assert response.status_code == 200
    ids = [asset['id'] for item in response.data['answerSources'] for asset in item['assets']]
    assert ids == [old_asset.id]
    assert new_asset.id not in ids


def test_apply_preserves_raw_text_when_student_maps_an_unmatched_fragment():
    _teacher, student, _session, exercise, question = _world()
    submission = baker.make(
        StudentExerciseSubmission,
        exercise=exercise,
        student=student,
        status=StudentExerciseSubmission.Status.DRAFT,
    )
    source = _source(submission)
    source.raw_result['answers'] = []
    source.raw_result['unmatched_fragments'] = ['متن خام بدون شماره']
    source.reviewed_result['answers'] = [{
        'question_id': question.id,
        'text': 'متن اصلاح‌شده و متصل به سؤال',
        'match_status': 'matched',
        'unclear_parts': [],
    }]
    source.save(update_fields=['raw_result', 'reviewed_result', 'updated_at'])

    apply_source(source)

    submission.refresh_from_db()
    projection = submission.answers[str(question.id)]['ocr']
    assert projection['rawText'] == 'متن خام بدون شماره'
    assert projection['text'] == 'متن اصلاح‌شده و متصل به سؤال'
    assert projection['correctedByStudent'] is True


def test_apply_rejects_stale_source_object_without_mutating_submission():
    _teacher, student, _session, exercise, question = _world()
    submission = baker.make(
        StudentExerciseSubmission,
        exercise=exercise,
        student=student,
        status=StudentExerciseSubmission.Status.DRAFT,
        answers={str(question.id): {'text': 'پاسخ تایپی'}},
    )
    source = _source(submission, question, revision=2)
    StudentExerciseAnswerSource.objects.filter(id=source.id).update(revision=3)

    with pytest.raises(StaleAnswerSource):
        apply_source(source)

    submission.refresh_from_db()
    assert submission.answers == {str(question.id): {'text': 'پاسخ تایپی'}}


def test_submit_requires_explicit_confirmation_for_unapplied_bundle(monkeypatch):
    _teacher, student, session, exercise, question = _world()
    submission = baker.make(
        StudentExerciseSubmission,
        exercise=exercise,
        student=student,
        status=StudentExerciseSubmission.Status.DRAFT,
    )
    source = _source(submission)
    source.raw_result['answers'][0]['question_id'] = question.id
    source.reviewed_result['answers'][0]['question_id'] = question.id
    source.save(update_fields=['raw_result', 'reviewed_result', 'updated_at'])
    queued = []
    monkeypatch.setattr(
        'apps.classes.tasks.grade_exercise_submission.delay',
        lambda *args, **kwargs: queued.append((args, kwargs)),
    )

    response = _auth(student).post(
        _base(session, exercise) + 'submit/',
        {'answers': {}},
        format='json',
    )

    assert response.status_code == 409
    assert StudentExerciseAttempt.objects.filter(submission=submission).count() == 0
    assert queued == []


def test_prepare_attempt_reuses_preview_without_vision_call(django_assert_num_queries):
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
    with django_assert_num_queries(2):
        assert prepare_attempt_ocr(attempt) == 'ready'
    attempt.refresh_from_db()
    assert attempt.answers[str(question.id)]['ocr']['text'] == 'متن اصلاح‌شده'
    assert attempt.answers[str(question.id)]['ocr']['sourceFingerprint'] == 'sha256:preview'


def test_duplicate_ocr_delivery_exits_before_processing(monkeypatch):
    _teacher, student, _session, exercise, question = _world()
    submission = baker.make(StudentExerciseSubmission, exercise=exercise, student=student)
    source = _source(submission, question, status=StudentExerciseAnswerSource.Status.QUEUED)
    monkeypatch.setattr('django.core.cache.cache.add', lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        'apps.classes.services.exercise_answer_ocr.process_source',
        lambda *_args, **_kwargs: pytest.fail('duplicate delivery must not process the source'),
    )

    result = process_student_answer_source.run(source.id, source.revision)

    assert result['status'] == 'already_processing'


def test_stale_queued_source_is_recovered_after_broker_publish_gap(monkeypatch):
    _teacher, student, _session, exercise, question = _world()
    submission = baker.make(StudentExerciseSubmission, exercise=exercise, student=student)
    source = _source(submission, question, status=StudentExerciseAnswerSource.Status.QUEUED)
    StudentExerciseAnswerSource.objects.filter(id=source.id).update(
        updated_at=timezone.now() - timedelta(minutes=3),
    )
    queued = []
    monkeypatch.setattr(
        'apps.classes.tasks.process_student_answer_source.apply_async',
        lambda *args, **kwargs: queued.append((args, kwargs)),
    )

    result = recover_queued_answer_ocr_sources.run()

    assert result['queued_count'] == 1
    assert queued[0][1]['args'] == [source.id, source.revision]


def test_feature_flag_stops_new_processing_but_preserves_frozen_ocr(monkeypatch):
    _teacher, student, _session, exercise, question = _world()
    submission = baker.make(StudentExerciseSubmission, exercise=exercise, student=student)
    source = _source(submission, question, status=StudentExerciseAnswerSource.Status.QUEUED)
    attempt = baker.make(
        StudentExerciseAttempt,
        submission=submission,
        grader_metadata={'answerSources': [{
            'sourceId': source.id,
            'revision': source.revision,
            'scope': 'question',
            'includeUnapplied': False,
        }]},
    )
    monkeypatch.setenv('EXERCISE_ANSWER_OCR_PREVIEW_ENABLED', '0')

    with pytest.raises(AnswerSourcePending):
        prepare_attempt_ocr(attempt)
    assert freeze_sources(submission, include_unapplied=True)[0]['sourceId'] == source.id
    assert _student_ocr(
        {str(question.id): {'ocr': {'text': 'متن موجود'}}}, question.id,
    )['text'] == 'متن موجود'


def test_disabled_flag_allows_already_queued_source_to_drain(monkeypatch):
    _teacher, student, _session, exercise, question = _world()
    submission = baker.make(StudentExerciseSubmission, exercise=exercise, student=student)
    source = _source(submission, question, status=StudentExerciseAnswerSource.Status.QUEUED)
    monkeypatch.setenv('EXERCISE_ANSWER_OCR_PREVIEW_ENABLED', '0')
    monkeypatch.setattr('django.core.cache.cache.add', lambda *_args, **_kwargs: True)
    monkeypatch.setattr('django.core.cache.cache.get', lambda *_args, **_kwargs: 'direct-call')
    monkeypatch.setattr('django.core.cache.cache.delete', lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        'apps.classes.services.exercise_answer_ocr._load_pages',
        lambda _assets: [Page(number=1, name='answer.png', data=PNG)],
    )
    monkeypatch.setattr(
        'apps.classes.services.exercise_answer_ocr._question_result',
        lambda current_source, _pages: {
            'answers': [{
                'question_id': current_source.target_question_id,
                'text': 'پاسخ',
                'match_status': 'matched',
                'quality': 'clear',
                'unclear_parts': [],
            }],
            'unmatched_fragments': [],
            'missing_question_ids': [],
        },
    )

    result = process_student_answer_source.run(source.id, source.revision)

    source.refresh_from_db()
    assert result['status'] == StudentExerciseAnswerSource.Status.READY
    assert source.status == StudentExerciseAnswerSource.Status.READY


def test_vision_payload_is_resized_and_bounded(monkeypatch):
    from PIL import Image

    source = Image.new('RGB', (800, 600), color='white')
    raw = BytesIO()
    source.save(raw, format='PNG')
    monkeypatch.setenv('EXERCISE_ANSWER_OCR_IMAGE_MAX_DIMENSION', '128')
    monkeypatch.setenv('EXERCISE_ANSWER_OCR_IMAGE_MAX_BYTES', '65536')

    page = _normalize_image_page(raw.getvalue(), 1)

    with Image.open(BytesIO(page.data)) as normalized:
        assert max(normalized.size) <= 128
    assert len(page.data) <= 65536
    assert page.name == 'page-1.jpg'


def test_extreme_pdf_page_is_scaled_before_rasterization(monkeypatch):
    from PIL import Image
    from pypdf import PdfWriter

    document = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100_000, height=100_000)
    writer.write(document)
    monkeypatch.setenv('EXERCISE_ANSWER_OCR_IMAGE_MAX_DIMENSION', '128')
    monkeypatch.setenv('EXERCISE_ANSWER_OCR_IMAGE_MAX_PIXELS', str(128 * 128))

    pages = _render_pdf(document.getvalue(), 1)

    with Image.open(BytesIO(pages[0].data)) as image:
        assert image.width <= 128
        assert image.height <= 128


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
    page_loads = []
    monkeypatch.setattr(
        'apps.classes.services.exercise_answer_ocr._load_pages',
        lambda assets: page_loads.append([asset.id for asset in assets]) or [Page(1, 'answer.png', PNG)],
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
    assert page_loads == [[]]
    source.refresh_from_db()
    assert source.status == StudentExerciseAnswerSource.Status.READY
    assert source.workflow_state['progressPercent'] == 100
    assert question.question_markdown in prompts[0]
    assert question.reference_answer_markdown not in prompts[0]
    submission.refresh_from_db()
    assert submission.answers[str(question.id)]['ocr']['text'] == '$2+2=4$'


def test_submit_race_does_not_turn_ready_ocr_into_failure(monkeypatch):
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
        lambda _assets: [Page(1, 'answer.png', PNG)],
    )
    monkeypatch.setattr(
        'apps.classes.services.exercise_answer_ocr._vision_call',
        lambda *_args, **_kwargs: HandwritingTranscriptionOutput(
            text='پاسخ خوانده‌شده', quality='clear', unclear_parts=[],
        ),
    )
    monkeypatch.setattr(
        'apps.classes.services.exercise_answer_ocr.apply_source',
        lambda _source: (_ for _ in ()).throw(ValueError('submission_locked')),
    )

    result = process_source(source.id, source.revision)

    source.refresh_from_db()
    assert result['status'] == StudentExerciseAnswerSource.Status.READY
    assert source.status == StudentExerciseAnswerSource.Status.READY
    assert source.error_code == ''


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


def test_bundle_retry_reuses_persisted_page_chunks(monkeypatch):
    _teacher, student, _session, exercise, question = _world()
    submission = baker.make(StudentExerciseSubmission, exercise=exercise, student=student)
    source = baker.make(
        StudentExerciseAnswerSource,
        submission=submission,
        scope=StudentExerciseAnswerSource.Scope.EXERCISE,
        target_question=None,
        status=StudentExerciseAnswerSource.Status.SEGMENTING,
    )
    monkeypatch.setenv('EXERCISE_ANSWER_OCR_PAGES_PER_CALL', '1')
    vision_calls = []

    def fake_vision(pages, **_kwargs):
        vision_calls.append(pages[0].number)
        return AnswerPageTranscriptionOutput(
            text=f'متن صفحه {pages[0].number}', quality='clear', unclear_parts=[],
        )

    mapping_calls = 0

    def flaky_mapping(**_kwargs):
        nonlocal mapping_calls
        mapping_calls += 1
        if mapping_calls == 1:
            raise RuntimeError('transient mapping failure')
        return ExerciseAnswerBundleOutput(
            answers=[{
                'question_id': question.id,
                'text': 'پاسخ نهایی',
                'match_status': 'matched',
                'unclear_parts': [],
            }],
            unmatched_fragments=[],
            missing_question_ids=[],
        )

    monkeypatch.setattr('apps.classes.services.exercise_answer_ocr._vision_call', fake_vision)
    monkeypatch.setattr('apps.classes.services.exercise_answer_ocr.generate_structured', flaky_mapping)
    pages = [Page(1, 'one.png', PNG), Page(2, 'two.png', PNG)]

    with pytest.raises(RuntimeError, match='transient mapping failure'):
        _bundle_result(source, pages, source.revision, 'sha256:retry')
    source.refresh_from_db()
    result = _bundle_result(source, pages, source.revision, 'sha256:retry')

    assert vision_calls == [1, 2]
    assert result['answers'][0]['text'] == 'پاسخ نهایی'


def test_bundle_pages_are_consumed_one_chunk_at_a_time(monkeypatch):
    _teacher, student, _session, exercise, question = _world()
    submission = baker.make(StudentExerciseSubmission, exercise=exercise, student=student)
    source = baker.make(
        StudentExerciseAnswerSource,
        submission=submission,
        scope=StudentExerciseAnswerSource.Scope.EXERCISE,
        target_question=None,
        status=StudentExerciseAnswerSource.Status.SEGMENTING,
    )
    monkeypatch.setenv('EXERCISE_ANSWER_OCR_PAGES_PER_CALL', '2')
    produced = 0
    consumed = 0

    def pages():
        nonlocal produced
        for number in range(1, 7):
            produced += 1
            if produced - consumed > 2:
                raise AssertionError('pages were materialized beyond one provider chunk')
            yield Page(number, f'{number}.png', PNG)

    def fake_vision(chunk, **_kwargs):
        nonlocal consumed
        consumed += len(chunk)
        return AnswerPageTranscriptionOutput(
            text=f'صفحات {chunk[0].number} تا {chunk[-1].number}',
            quality='clear',
            unclear_parts=[],
        )

    monkeypatch.setattr('apps.classes.services.exercise_answer_ocr._vision_call', fake_vision)
    monkeypatch.setattr(
        'apps.classes.services.exercise_answer_ocr.generate_structured',
        lambda **_kwargs: ExerciseAnswerBundleOutput(
            answers=[{
                'question_id': question.id,
                'text': 'پاسخ',
                'match_status': 'matched',
                'unclear_parts': [],
            }],
            unmatched_fragments=[],
            missing_question_ids=[],
        ),
    )

    result = _bundle_result(source, pages(), source.revision, 'sha256:stream')

    assert produced == consumed == 6
    assert len(result['page_transcripts']) == 3


def test_stale_bundle_revision_is_rejected_before_reading_pages():
    _teacher, student, _session, exercise, _question = _world()
    submission = baker.make(StudentExerciseSubmission, exercise=exercise, student=student)
    source = baker.make(
        StudentExerciseAnswerSource,
        submission=submission,
        scope=StudentExerciseAnswerSource.Scope.EXERCISE,
        target_question=None,
        revision=2,
        status=StudentExerciseAnswerSource.Status.QUEUED,
    )

    def pages():
        pytest.fail('a stale job must not open or render answer assets')
        yield Page(1, 'never.png', PNG)

    with pytest.raises(StaleAnswerSource):
        _bundle_result(source, pages(), 1, 'sha256:stale')


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
    result = _bundle_result(
        source, [Page(1, 'one.png', PNG), Page(2, 'two.png', PNG)], 1,
        'sha256:bundle-fixture',
    )
    assert question.reference_answer_markdown not in mapping_prompts[0]
    ids = [item.get('question_id') for item in result['answers']]
    assert len([qid for qid in ids if qid == question.id]) <= 1
    assert result['missing_question_ids'] == ([] if question.id in ids else [question.id])


def test_upload_limit_rejects_unknown_request_length_before_view():
    called = False

    def view(_request):
        nonlocal called
        called = True

    request = RequestFactory().post(
        '/api/classes/student/courses/1/exercises/1/answer-source/',
        data={},
    )
    request.META.pop('CONTENT_LENGTH', None)
    response = AnswerOcrUploadLimitMiddleware(view)(request)

    assert response.status_code == 411
    assert called is False


def test_sensitive_structured_failure_does_not_log_or_raise_private_text(monkeypatch, caplog):
    sentinel = 'PRIVATE-STUDENT-ANSWER-9381'
    monkeypatch.setattr(
        'apps.chatbot.services.llm_client.generate_text',
        lambda **_kwargs: type('Result', (), {
            'text': f'{{"text":"{sentinel}","quality":"invalid"}}',
        })(),
    )
    with pytest.raises(StructuredOutputError) as error:
        generate_structured(
            schema=HandwritingTranscriptionOutput,
            contents='private input',
            max_repair=0,
            sensitive=True,
        )
    assert sentinel not in str(error.value)
    assert sentinel not in caplog.text


def test_existing_ready_ocr_survives_feature_flag_disable(monkeypatch):
    _teacher, student, session, exercise, question = _world()
    submission = baker.make(
        StudentExerciseSubmission,
        exercise=exercise,
        student=student,
        status=StudentExerciseSubmission.Status.DRAFT,
    )
    source = _source(
        submission, question, status=StudentExerciseAnswerSource.Status.READY,
    )
    source.raw_result = {
        'answers': [{
            'question_id': question.id,
            'text': 'پاسخ تاییدشده',
            'quality': 'clear',
            'unclear_parts': [],
        }],
    }
    source.reviewed_result = {}
    source.save(update_fields=['raw_result', 'reviewed_result'])
    apply_source(source)
    monkeypatch.setenv('EXERCISE_ANSWER_OCR_PREVIEW_ENABLED', '0')

    response = _auth(student).post(
        _base(session, exercise) + 'submit/',
        {'answers': submission.answers},
        format='json',
    )

    assert response.status_code == 201
    attempt = StudentExerciseAttempt.objects.get(id=response.data['attemptId'])
    assert attempt.grader_metadata['answerSources'][0]['sourceId'] == source.id
    prepare_attempt_ocr(attempt)
    attempt.refresh_from_db()
    assert _student_ocr(attempt.answers, question.id)['text'] == 'پاسخ تاییدشده'


def test_recovery_does_not_duplicate_already_dispatched_queued_source(monkeypatch):
    _teacher, student, _session, exercise, question = _world()
    submission = baker.make(StudentExerciseSubmission, exercise=exercise, student=student)
    source = _source(submission, question, status=StudentExerciseAnswerSource.Status.QUEUED)
    old = timezone.now() - timedelta(minutes=3)
    StudentExerciseAnswerSource.objects.filter(id=source.id).update(
        processing_task_id='published-task', updated_at=old,
    )
    dispatched = []
    monkeypatch.setattr(
        'apps.classes.tasks.process_student_answer_source.apply_async',
        lambda **kwargs: dispatched.append(kwargs),
    )

    result = recover_queued_answer_ocr_sources.run()

    assert result['queued_count'] == 0
    assert dispatched == []


def test_same_task_id_redelivery_never_runs_provider_concurrently(monkeypatch):
    _teacher, student, _session, exercise, question = _world()
    submission = baker.make(StudentExerciseSubmission, exercise=exercise, student=student)
    source = _source(submission, question, status=StudentExerciseAnswerSource.Status.QUEUED)
    lock_key = f'exercise-answer-ocr:{source.id}:{source.revision}'
    cache.set(lock_key, 'direct-call', timeout=60)
    monkeypatch.setattr(
        'apps.classes.services.exercise_answer_ocr.process_source',
        lambda *_args: pytest.fail('provider work must not run'),
    )
    try:
        result = process_student_answer_source.run(source.id, source.revision)
    finally:
        cache.delete(lock_key)

    assert result['status'] == 'already_processing'


def test_failed_whole_bundle_can_retry_identical_files():
    _teacher, student, session, exercise, _question = _world()
    submission = baker.make(
        StudentExerciseSubmission,
        exercise=exercise,
        student=student,
        status=StudentExerciseSubmission.Status.DRAFT,
    )
    source = baker.make(
        StudentExerciseAnswerSource,
        submission=submission,
        scope=StudentExerciseAnswerSource.Scope.EXERCISE,
        target_question=None,
        status=StudentExerciseAnswerSource.Status.FAILED,
        revision=1,
        error_code='provider_failed',
    )
    baker.make(
        StudentExerciseAnswerAsset,
        source=source,
        file=SimpleUploadedFile('bundle.png', PNG, content_type='image/png'),
        content_type='image/png',
        byte_size=len(PNG),
        sha256=hashlib.sha256(PNG).hexdigest(),
    )

    response = _auth(student).post(
        _base(session, exercise) + 'answer-source/',
        {'files': [SimpleUploadedFile('bundle.png', PNG, content_type='image/png')]},
        format='multipart',
    )

    assert response.status_code == 200
    source.refresh_from_db()
    assert source.status == StudentExerciseAnswerSource.Status.QUEUED
    assert source.revision == 2
    assert source.error_code == ''


def test_exercise_cascade_schedules_answer_blob_cleanup(
    monkeypatch, django_capture_on_commit_callbacks,
):
    _teacher, student, _session, exercise, question = _world()
    submission = baker.make(StudentExerciseSubmission, exercise=exercise, student=student)
    source = _source(submission, question)
    asset = baker.make(
        StudentExerciseAnswerAsset,
        source=source,
        file=SimpleUploadedFile('cascade.png', PNG, content_type='image/png'),
        content_type='image/png',
        byte_size=len(PNG),
        sha256=hashlib.sha256(PNG).hexdigest(),
    )
    deleted = []
    monkeypatch.setattr(
        'apps.classes.signals.delete_answer_source_file', deleted.append,
    )

    with django_capture_on_commit_callbacks(execute=True):
        exercise.delete()

    assert deleted == [asset.file.name]


def test_answer_original_uses_dedicated_private_storage():
    _teacher, student, _session, exercise, question = _world()
    submission = baker.make(StudentExerciseSubmission, exercise=exercise, student=student)
    source = _source(submission, question)
    asset = baker.make(
        StudentExerciseAnswerAsset,
        source=source,
        file=SimpleUploadedFile('private-store.png', PNG, content_type='image/png'),
        content_type='image/png',
        byte_size=len(PNG),
        sha256=hashlib.sha256(PNG).hexdigest(),
    )

    assert asset.file.storage is storages['answer_sources']
    assert asset.file.storage is not storages['default']


def test_attempt_asset_backfill_is_revision_safe():
    _teacher, student, _session, exercise, question = _world()
    submission = baker.make(StudentExerciseSubmission, exercise=exercise, student=student)
    source = _source(submission, question)
    asset = baker.make(
        StudentExerciseAnswerAsset,
        source=source,
        file=SimpleUploadedFile('backfill.png', PNG, content_type='image/png'),
        content_type='image/png',
        byte_size=len(PNG),
        sha256=hashlib.sha256(PNG).hexdigest(),
    )
    safe = baker.make(
        StudentExerciseAttempt,
        submission=submission,
        grader_metadata={'answerSources': [{
            'sourceId': source.id, 'revision': source.revision,
        }]},
    )
    ambiguous = baker.make(
        StudentExerciseAttempt,
        submission=submission,
        grader_metadata={'answerSources': [{
            'sourceId': source.id, 'revision': source.revision + 1,
        }]},
    )
    migration = importlib.import_module(
        'apps.classes.migrations.0036_backfill_attempt_answer_asset_ids',
    )

    migration.backfill_asset_ids(django_apps, None)

    safe.refresh_from_db()
    ambiguous.refresh_from_db()
    assert safe.grader_metadata['answerSources'][0]['assetIds'] == [asset.id]
    assert 'assetIds' not in ambiguous.grader_metadata['answerSources'][0]
