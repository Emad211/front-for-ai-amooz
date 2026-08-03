import io

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from model_bakery import baker
from PIL import Image
from rest_framework.test import APIClient

from apps.classes.models_v4 import (
    ExamProject,
    ExamSourceDocument,
    ExamSourcePage,
)


pytestmark = pytest.mark.django_db


def _user(role='TEACHER'):
    return baker.make('accounts.User', role=role)


def _auth(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _jpeg() -> bytes:
    image = Image.new('RGB', (120, 180), (245, 245, 245))
    output = io.BytesIO()
    image.save(output, format='JPEG', quality=70)
    return output.getvalue()


@pytest.fixture
def private_storage(tmp_path, monkeypatch):
    storage = FileSystemStorage(location=tmp_path / 'private')
    monkeypatch.setattr(
        ExamSourcePage._meta.get_field('thumbnail_file'),
        'storage',
        storage,
    )
    return storage


def _source_page(
    *,
    teacher=None,
    project=None,
    document=None,
    page_number=1,
    with_thumbnail=True,
    thumbnail_bytes=None,
):
    teacher = teacher or _user()
    project = project or ExamProject.objects.create(
        teacher=teacher,
        title='آزمون',
    )
    document = document or ExamSourceDocument.objects.create(
        project=project,
        original_name='private-exam.pdf',
        page_count=max(1, page_number),
    )
    page = ExamSourcePage.objects.create(
        document=document,
        page_number=page_number,
        predicted_role='questions',
        predicted_confidence=0.9,
    )
    data = thumbnail_bytes or _jpeg()
    if with_thumbnail:
        page.thumbnail_file.save(
            'deep/private/object/teacher-secret-thumbnail.jpg',
            ContentFile(data),
            save=True,
        )
    return teacher, project, document, page, data


def _url(project, document, page_number):
    return (
        f'/api/classes/exam-prep-v4/projects/{project.id}/'
        f'documents/{document.id}/pages/{page_number}/thumbnail/'
    )


def _stream_body(response) -> bytes:
    return b''.join(response.streaming_content)


def test_thumbnail_requires_authentication(private_storage, settings):
    settings.EXAM_PREP_V4_ENABLED = True
    _teacher, project, document, page, _data = _source_page()

    response = APIClient().get(_url(project, document, page.page_number))

    assert response.status_code == 401


def test_student_cannot_read_teacher_thumbnail(private_storage, settings):
    settings.EXAM_PREP_V4_ENABLED = True
    _teacher, project, document, page, _data = _source_page()

    response = _auth(_user('STUDENT')).get(
        _url(project, document, page.page_number)
    )

    assert response.status_code == 403


def test_disabled_v4_hides_thumbnail_route(private_storage, settings):
    settings.EXAM_PREP_V4_ENABLED = False
    teacher, project, document, page, _data = _source_page()

    response = _auth(teacher).get(_url(project, document, page.page_number))

    assert response.status_code == 404


def test_owner_streams_private_jpeg_with_non_cacheable_headers(
    private_storage,
    settings,
    django_assert_num_queries,
):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher, project, document, page, data = _source_page()
    secret_name = page.thumbnail_file.name

    with django_assert_num_queries(1):
        response = _auth(teacher).get(
            _url(project, document, page.page_number)
        )

    assert response.status_code == 200
    assert response.streaming is True
    assert response['Content-Type'] == 'image/jpeg'
    assert response['Content-Length'] == str(len(data))
    assert response['Content-Disposition'] == 'inline; filename="page-1.jpg"'
    assert response['Cache-Control'] == 'private, no-store, max-age=0'
    assert response['Pragma'] == 'no-cache'
    assert response['Expires'] == '0'
    assert response['X-Content-Type-Options'] == 'nosniff'
    assert response['Cross-Origin-Resource-Policy'] == 'same-origin'
    assert response['Referrer-Policy'] == 'no-referrer'
    vary = {item.strip() for item in response.get('Vary', '').split(',')}
    assert {'Authorization', 'Cookie'}.issubset(vary)

    headers = '\n'.join(f'{key}: {value}' for key, value in response.items())
    assert secret_name not in headers
    assert 'teacher-secret-thumbnail' not in headers
    assert _stream_body(response) == data


def test_another_teacher_gets_404_without_storage_access(
    private_storage,
    monkeypatch,
    settings,
    django_assert_num_queries,
):
    settings.EXAM_PREP_V4_ENABLED = True
    _owner, project, document, page, _data = _source_page()
    opened = []
    real_open = private_storage.open

    def tracked_open(*args, **kwargs):
        opened.append(args[0] if args else None)
        return real_open(*args, **kwargs)

    monkeypatch.setattr(private_storage, 'open', tracked_open)

    with django_assert_num_queries(1):
        response = _auth(_user()).get(
            _url(project, document, page.page_number)
        )

    assert response.status_code == 404
    assert opened == []


def test_wrong_project_document_and_page_ancestry_all_return_404(
    private_storage,
    settings,
):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher = _user()
    _t, first_project, first_document, first_page, _data = _source_page(
        teacher=teacher,
        page_number=1,
    )
    _t, second_project, second_document, second_page, _data = _source_page(
        teacher=teacher,
        page_number=2,
    )
    client = _auth(teacher)

    urls = [
        _url(second_project, first_document, first_page.page_number),
        _url(first_project, second_document, second_page.page_number),
        _url(first_project, first_document, second_page.page_number),
    ]

    assert [client.get(url).status_code for url in urls] == [404, 404, 404]


def test_page_without_thumbnail_is_hidden(settings):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher, project, document, page, _data = _source_page(
        with_thumbnail=False
    )

    response = _auth(teacher).get(_url(project, document, page.page_number))

    assert response.status_code == 404


def test_named_but_missing_private_blob_returns_404_without_key_leak(
    private_storage,
    settings,
):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher, project, document, page, _data = _source_page()
    secret_name = page.thumbnail_file.name
    private_storage.delete(secret_name)

    response = _auth(teacher).get(_url(project, document, page.page_number))

    assert response.status_code == 404
    payload = bytes(response.content).decode('utf-8', errors='ignore')
    headers = '\n'.join(f'{key}: {value}' for key, value in response.items())
    assert secret_name not in payload
    assert secret_name not in headers
    assert 'teacher-secret-thumbnail' not in payload


def test_storage_failure_is_indistinguishable_from_missing_page(
    private_storage,
    monkeypatch,
    settings,
):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher, project, document, page, _data = _source_page()

    def failing_open(*_args, **_kwargs):
        raise RuntimeError('s3://private-bucket/highly-secret-object.jpg')

    monkeypatch.setattr(private_storage, 'open', failing_open)

    response = _auth(teacher).get(_url(project, document, page.page_number))

    assert response.status_code == 404
    payload = bytes(response.content).decode('utf-8', errors='ignore')
    assert 'private-bucket' not in payload
    assert 'highly-secret-object' not in payload


def test_generic_media_route_still_denies_v4_thumbnail(
    private_storage,
    settings,
):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher, _project, _document, page, _data = _source_page()

    response = _auth(teacher).get(f'/media/{page.thumbnail_file.name}')

    assert response.status_code == 404
