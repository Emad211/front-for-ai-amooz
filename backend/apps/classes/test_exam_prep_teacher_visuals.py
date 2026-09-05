"""Focused tests for teacher-scoped Exam Prep visual upload + content views."""
from __future__ import annotations

import io
import json
import sys
import types

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import include, path, resolve
from model_bakery import baker
from PIL import Image
from rest_framework.test import APIClient

from apps.classes.models import (
    ClassCreationSession,
    ClassInvitation,
    StudentExamPrepAttempt,
)
from apps.classes.services.exam_prep_teacher_visuals import (
    TEACHER_VISUAL_MAX_UPLOAD_BYTES,
    NotExamPrepSessionError,
    attach_teacher_visual,
    remove_teacher_visual,
)
from apps.classes.views_exam_prep_teacher_visuals import (
    TeacherExamPrepVisualContentView,
    TeacherExamPrepVisualUploadView,
)

pytestmark = pytest.mark.django_db

# ---------------------------------------------------------------------------
# The committed core/urls.py currently imports a review-view name that does not
# exist on this branch, so ANY routed request 500s with ImportError.  These
# tests therefore route through apps.classes.urls under the real ``api/classes/``
# prefix (same URL tree the production include exposes), bypassing only that
# broken top-level import.  See test_exam_prep_review_route.py for the baseline.
# ---------------------------------------------------------------------------
_TEST_URL_MODULE = '__test_exam_prep_teacher_visuals_urlconf__'


@pytest.fixture(scope='module', autouse=True)
def _teacher_visuals_urlconf():
    module = types.ModuleType(_TEST_URL_MODULE)
    module.urlpatterns = [path('api/classes/', include('apps.classes.urls'))]
    sys.modules[_TEST_URL_MODULE] = module
    with override_settings(ROOT_URLCONF=_TEST_URL_MODULE):
        yield
    sys.modules.pop(_TEST_URL_MODULE, None)


@pytest.fixture
def private_storage(tmp_path, settings):
    """Point the answer_sources storage at a throwaway directory."""
    configured = dict(settings.STORAGES)
    configured['answer_sources'] = {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
        'OPTIONS': {'location': str(tmp_path / 'private_answer_media')},
    }
    root = tmp_path / 'private_answer_media'
    with override_settings(STORAGES=configured):
        yield root


def _png_bytes(color: str = 'white') -> bytes:
    output = io.BytesIO()
    Image.new('RGB', (24, 24), color).save(output, format='PNG')
    return output.getvalue()


def _jpeg_bytes() -> bytes:
    output = io.BytesIO()
    Image.new('RGB', (24, 24), 'red').save(output, format='JPEG')
    return output.getvalue()


def _teacher():
    return baker.make('accounts.User', role='TEACHER', phone='09120000000')


def _session(teacher, *, published=False):
    payload = {
        'exam_prep': {
            'title': 'آزمون',
            'questions': [
                {
                    'question_id': 'q1',
                    'question_text_markdown': 'سؤال یک',
                    'options': [
                        {'label': '1', 'text_markdown': 'گزینه الف'},
                        {'label': '2', 'text_markdown': 'گزینه ب'},
                    ],
                },
                {
                    'question_id': 'q2',
                    'question_text_markdown': 'سؤال دو',
                    'options': [],
                },
            ],
        }
    }
    return ClassCreationSession.objects.create(
        teacher=teacher,
        title='آزمون معلم',
        pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        status=ClassCreationSession.Status.EXAM_STRUCTURED,
        is_published=published,
        exam_prep_json=json.dumps(payload, ensure_ascii=False),
    )


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _upload_url(session):
    return f'/api/classes/exam-prep-sessions/{session.id}/visuals/teacher/'


def _content_url(session, storage_name):
    return (
        f'/api/classes/exam-prep-sessions/{session.id}/'
        f'visuals/teacher/{storage_name}/content/'
    )


def _question_payload(session):
    payload = json.loads(ClassCreationSession.objects.get(id=session.id).exam_prep_json)
    return payload['exam_prep']['questions']


def _visuals_of(session, question_id):
    for question in _question_payload(session):
        if str(question.get('question_id')) == question_id:
            return question.get('visuals') or []
    return []


def _uploaded_storage_name(session, teacher):
    response = _client(teacher).post(
        _upload_url(session),
        {
            'question_id': 'q1',
            'role': 'question',
            'image': SimpleUploadedFile('diagram.png', _png_bytes(), content_type='image/png'),
        },
        format='multipart',
    )
    assert response.status_code == 201
    return response.data['visual']['url'].split('/visuals/teacher/')[1].split('/content/')[0]


# ---------------------------------------------------------------------------
# Route registration (no conflict with the numeric stored-asset route)
# ---------------------------------------------------------------------------


def test_upload_route_resolves_to_teacher_upload_view():
    match = resolve('/api/classes/exam-prep-sessions/123/visuals/teacher/')
    assert match.func.cls is TeacherExamPrepVisualUploadView


def test_content_route_is_distinct_from_numeric_asset_route():
    match = resolve(
        '/api/classes/exam-prep-sessions/123/visuals/teacher/'
        '0123456789abcdef0123456789abcdef.png/content/'
    )
    assert match.func.cls is TeacherExamPrepVisualContentView
    assert match.kwargs == {
        'session_id': 123,
        'storage_name': '0123456789abcdef0123456789abcdef.png',
    }

    legacy = resolve('/api/classes/exam-prep-sessions/123/visuals/55/content/')
    assert legacy.func.cls is not TeacherExamPrepVisualContentView
    assert legacy.kwargs == {'session_id': 123, 'asset_id': 55}


# ---------------------------------------------------------------------------
# Upload contract
# ---------------------------------------------------------------------------


def test_teacher_uploads_png_to_stem_stores_file_and_serves_it(private_storage):
    teacher = _teacher()
    session = _session(teacher)
    png = _png_bytes()

    response = _client(teacher).post(
        _upload_url(session),
        {
            'question_id': 'q1',
            'role': 'question',
            'image': SimpleUploadedFile('diagram.png', png, content_type='image/png'),
        },
        format='multipart',
    )

    assert response.status_code == 201, response.content
    visual = response.data['visual']
    assert visual['id'].startswith('teacher-')
    assert visual['role'] == 'question'
    assert visual['optionLabel'] is None
    assert visual['altText'] is None
    assert f'/visuals/teacher/{visual["id"][len("teacher-"):]}.png/content/' in visual['url']
    assert response.data['question']['question_id'] == 'q1'

    visuals = _visuals_of(session, 'q1')
    assert len(visuals) == 1
    assert visuals[0]['id'] == visual['id']

    storage_name = visual['url'].split('/visuals/teacher/')[1].split('/content/')[0]
    stored = private_storage / 'exam-prep' / 'teacher-visuals' / str(session.id) / storage_name
    assert stored.read_bytes() == png

    content_response = _client(teacher).get(_content_url(session, storage_name))
    assert content_response.status_code == 200
    assert content_response['Content-Type'].startswith('image/png')
    assert content_response['Cache-Control'] == 'private, no-store, max-age=0'
    assert b''.join(content_response.streaming_content) == png


def test_unrelated_teacher_cannot_fetch_content(private_storage):
    owner = _teacher()
    session = _session(owner)
    storage_name = _uploaded_storage_name(session, owner)

    intruder = _teacher()
    denied = _client(intruder).get(_content_url(session, storage_name))
    assert denied.status_code == 404


def test_upload_forbidden_for_non_owner_teacher():
    owner = _teacher()
    intruder = _teacher()
    session = _session(owner)

    response = _client(intruder).post(
        _upload_url(session),
        {
            'question_id': 'q1',
            'role': 'question',
            'image': SimpleUploadedFile('diagram.png', _png_bytes(), content_type='image/png'),
        },
        format='multipart',
    )

    assert response.status_code == 403


def test_option_role_requires_option_label():
    teacher = _teacher()
    session = _session(teacher)
    client = _client(teacher)

    missing = client.post(
        _upload_url(session),
        {
            'question_id': 'q1',
            'role': 'option',
            'image': SimpleUploadedFile('option.png', _png_bytes(), content_type='image/png'),
        },
        format='multipart',
    )
    assert missing.status_code == 400

    with_label = client.post(
        _upload_url(session),
        {
            'question_id': 'q1',
            'role': 'option',
            'option_label': '1',
            'image': SimpleUploadedFile('option.png', _png_bytes(), content_type='image/png'),
        },
        format='multipart',
    )
    assert with_label.status_code == 201, with_label.content
    assert with_label.data['visual']['role'] == 'option'
    assert with_label.data['visual']['optionLabel'] == '1'


def test_unknown_question_id_returns_404():
    teacher = _teacher()
    session = _session(teacher)

    response = _client(teacher).post(
        _upload_url(session),
        {
            'question_id': 'does-not-exist',
            'role': 'question',
            'image': SimpleUploadedFile('diagram.png', _png_bytes(), content_type='image/png'),
        },
        format='multipart',
    )

    assert response.status_code == 404
    assert 'q1' in str(response.data['detail'])


def test_invalid_role_returns_400():
    teacher = _teacher()
    session = _session(teacher)

    response = _client(teacher).post(
        _upload_url(session),
        {
            'question_id': 'q1',
            'role': 'thumbnail',
            'image': SimpleUploadedFile('diagram.png', _png_bytes(), content_type='image/png'),
        },
        format='multipart',
    )

    assert response.status_code == 400


def test_non_image_upload_returns_400():
    teacher = _teacher()
    session = _session(teacher)

    response = _client(teacher).post(
        _upload_url(session),
        {
            'question_id': 'q1',
            'role': 'question',
            'image': SimpleUploadedFile('fake.png', b'not-an-image', content_type='image/png'),
        },
        format='multipart',
    )

    assert response.status_code == 400
    assert _visuals_of(session, 'q1') == []


def test_extension_mismatch_returns_400():
    teacher = _teacher()
    session = _session(teacher)

    response = _client(teacher).post(
        _upload_url(session),
        {
            'question_id': 'q1',
            'role': 'question',
            'image': SimpleUploadedFile('diagram.jpg', _png_bytes(), content_type='image/png'),
        },
        format='multipart',
    )

    assert response.status_code == 400


def test_oversize_upload_returns_400():
    teacher = _teacher()
    session = _session(teacher)
    oversized = _png_bytes() + b'x' * TEACHER_VISUAL_MAX_UPLOAD_BYTES

    response = _client(teacher).post(
        _upload_url(session),
        {
            'question_id': 'q1',
            'role': 'question',
            'image': SimpleUploadedFile('big.png', oversized, content_type='image/png'),
        },
        format='multipart',
    )

    assert response.status_code == 400
    assert _visuals_of(session, 'q1') == []


def test_missing_image_field_returns_400():
    teacher = _teacher()
    session = _session(teacher)

    response = _client(teacher).post(
        _upload_url(session),
        {'question_id': 'q1', 'role': 'question'},
        format='multipart',
    )

    assert response.status_code == 400


def test_upload_requires_teacher_role():
    student = baker.make('accounts.User', role='STUDENT', phone='09120000002')
    teacher = _teacher()
    session = _session(teacher)

    response = _client(student).post(
        _upload_url(session),
        {
            'question_id': 'q1',
            'role': 'question',
            'image': SimpleUploadedFile('diagram.png', _png_bytes(), content_type='image/png'),
        },
        format='multipart',
    )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Content access matrix
# ---------------------------------------------------------------------------


def test_invited_student_can_fetch_published_question_visual(private_storage):
    teacher = _teacher()
    session = _session(teacher, published=True)
    storage_name = _uploaded_storage_name(session, teacher)
    student = baker.make('accounts.User', role='STUDENT', phone='09120000003')
    ClassInvitation.objects.create(session=session, phone=student.phone, invite_code='t-visual-1')

    response = _client(student).get(_content_url(session, storage_name))

    assert response.status_code == 200
    assert response['Content-Type'].startswith('image/png')
    assert b''.join(response.streaming_content) == _png_bytes()


def test_uninvited_student_cannot_fetch_visual(private_storage):
    teacher = _teacher()
    session = _session(teacher, published=True)
    storage_name = _uploaded_storage_name(session, teacher)
    student = baker.make('accounts.User', role='STUDENT', phone='09120000004')

    response = _client(student).get(_content_url(session, storage_name))

    assert response.status_code == 404


def test_unpublished_session_hides_visual_from_invited_student(private_storage):
    teacher = _teacher()
    session = _session(teacher, published=False)
    storage_name = _uploaded_storage_name(session, teacher)
    student = baker.make('accounts.User', role='STUDENT', phone='09120000005')
    ClassInvitation.objects.create(session=session, phone=student.phone, invite_code='t-visual-2')

    response = _client(student).get(_content_url(session, storage_name))

    assert response.status_code == 404


def test_solution_visual_visible_to_student_only_after_finalize(private_storage):
    teacher = _teacher()
    session = _session(teacher, published=True)
    client = _client(teacher)
    response = client.post(
        _upload_url(session),
        {
            'question_id': 'q1',
            'role': 'solution',
            'image': SimpleUploadedFile('solution.jpg', _jpeg_bytes(), content_type='image/jpeg'),
        },
        format='multipart',
    )
    assert response.status_code == 201
    storage_name = response.data['visual']['url'].split('/visuals/teacher/')[1].split('/content/')[0]
    student = baker.make('accounts.User', role='STUDENT', phone='09120000006')
    ClassInvitation.objects.create(session=session, phone=student.phone, invite_code='t-visual-3')

    hidden = _client(student).get(_content_url(session, storage_name))
    assert hidden.status_code == 404

    StudentExamPrepAttempt.objects.create(
        session=session,
        student=student,
        answers={},
        finalized=True,
    )
    visible = _client(student).get(_content_url(session, storage_name))
    assert visible.status_code == 200
    assert visible['Content-Type'].startswith('image/jpeg')


def test_orphan_or_foreign_storage_name_is_not_served(private_storage):
    teacher = _teacher()
    session = _session(teacher)
    storage_name = _uploaded_storage_name(session, teacher)
    # Same session id but a filename that no visual references.
    bogus = storage_name[:-4] + 'dead.png'

    response = _client(teacher).get(_content_url(session, bogus))

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Service helpers (remove + typed errors)
# ---------------------------------------------------------------------------


def test_remove_teacher_visual_deletes_entry_and_stored_file(private_storage):
    teacher = _teacher()
    session = _session(teacher)
    png = _png_bytes()
    result = attach_teacher_visual(
        session,
        question_id='q1',
        role='question',
        image_content=png,
        image_name='diagram.png',
    )
    visual = result['visual']
    storage_name = visual['storageName']
    stored = (
        private_storage / 'exam-prep' / 'teacher-visuals'
        / str(session.id) / storage_name
    )
    assert stored.exists()

    removed = remove_teacher_visual(session, visual_id=visual['id'])

    assert removed is True
    assert _visuals_of(session, 'q1') == []
    assert not stored.exists()

    assert remove_teacher_visual(session, visual_id=visual['id']) is False


def test_delete_endpoint_removes_entry_and_stored_file(private_storage):
    teacher = _teacher()
    session = _session(teacher)
    storage_name = _uploaded_storage_name(session, teacher)
    visual_id = _visuals_of(session, 'q1')[0]['id']
    stored = (
        private_storage / 'exam-prep' / 'teacher-visuals'
        / str(session.id) / storage_name
    )
    assert stored.exists()

    response = _client(teacher).delete(
        _upload_url(session),
        {'visual_id': visual_id},
    )

    assert response.status_code == 204
    assert _visuals_of(session, 'q1') == []
    assert not stored.exists()


def test_delete_endpoint_guards_unknown_visual_and_foreign_owner(private_storage):
    teacher = _teacher()
    session = _session(teacher)
    storage_name = _uploaded_storage_name(session, teacher)
    visual_id = _visuals_of(session, 'q1')[0]['id']

    unknown = _client(teacher).delete(
        _upload_url(session),
        {'visual_id': 'teacher-00000000000000000000000000000000'},
    )
    assert unknown.status_code == 404

    stranger = _teacher()
    forbidden = _client(stranger).delete(
        _upload_url(session),
        {'visual_id': visual_id},
    )
    assert forbidden.status_code == 403

    stored = (
        private_storage / 'exam-prep' / 'teacher-visuals'
        / str(session.id) / storage_name
    )
    assert stored.exists()
    assert len(_visuals_of(session, 'q1')) == 1


def test_attach_rejects_non_exam_prep_session():
    teacher = _teacher()
    session = ClassCreationSession.objects.create(
        teacher=teacher,
        title='کلاس عادی',
        pipeline_type=ClassCreationSession.PipelineType.CLASS,
        status=ClassCreationSession.Status.TRANSCRIBED,
    )
    with pytest.raises(NotExamPrepSessionError):
        attach_teacher_visual(
            session,
            question_id='q1',
            role='question',
            image_content=_png_bytes(),
            image_name='diagram.png',
        )


def test_solution_upload_for_stem_is_allowed_and_persisted(private_storage):
    teacher = _teacher()
    session = _session(teacher)
    response = _client(teacher).post(
        _upload_url(session),
        {
            'question_id': 'q2',
            'role': 'solution',
            'image': SimpleUploadedFile('sol.jpg', _jpeg_bytes(), content_type='image/jpeg'),
        },
        format='multipart',
    )
    assert response.status_code == 201
    visuals = _visuals_of(session, 'q2')
    assert len(visuals) == 1
    assert visuals[0]['role'] == 'solution'
    assert visuals[0]['url'].endswith('/content/')


def test_student_detail_keeps_teacher_visual_url_and_serves_content(private_storage):
    teacher = _teacher()
    session = _session(teacher, published=True)
    attach_teacher_visual(
        session,
        question_id='q1',
        role='question',
        image_content=_png_bytes(),
        image_name='stem.png',
    )
    student = baker.make('accounts.User', role='STUDENT', phone='09120000013')
    ClassInvitation.objects.create(session=session, phone=student.phone, invite_code='t-visual-stem')
    client = _client(student)

    detail = client.get(f'/api/classes/student/exam-preps/{session.id}/')

    assert detail.status_code == 200
    q1 = next(q for q in detail.data['questions'] if q['question_id'] == 'q1')
    question_visuals = [v for v in q1['visuals'] if v['role'] == 'question']
    assert len(question_visuals) == 1
    teacher_url = question_visuals[0]['url']
    assert '/visuals/teacher/' in teacher_url

    content = client.get(teacher_url)

    assert content.status_code == 200
    assert content['Content-Type'].startswith('image/png')
    assert b''.join(content.streaming_content) == _png_bytes()

