from __future__ import annotations

import io
import json
import sys
import types

import pytest
from django.test import override_settings
from django.urls import path
from model_bakery import baker
from PIL import Image
from rest_framework.test import APIClient

from apps.classes.models import ClassCreationSession, ClassInvitation
from apps.classes.views_exam_prep_inline_visual import InlineOrStoredExamVisualContentView

pytestmark = pytest.mark.django_db

_TEST_URL_MODULE = '__test_exam_prep_inline_stored_crop_urlconf__'


@pytest.fixture(scope='module', autouse=True)
def _inline_visual_urlconf():
    module = types.ModuleType(_TEST_URL_MODULE)
    module.urlpatterns = [
        path(
            'api/classes/exam-prep-sessions/<int:session_id>/visuals/<str:asset_id>/content/',
            InlineOrStoredExamVisualContentView.as_view(),
        ),
    ]
    sys.modules[_TEST_URL_MODULE] = module
    with override_settings(ROOT_URLCONF=_TEST_URL_MODULE):
        yield
    sys.modules.pop(_TEST_URL_MODULE, None)


@pytest.fixture
def private_storage(tmp_path, settings):
    configured = dict(settings.STORAGES)
    configured['answer_sources'] = {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
        'OPTIONS': {'location': str(tmp_path / 'private_answer_media')},
    }
    with override_settings(STORAGES=configured):
        yield tmp_path / 'private_answer_media'


def _png_bytes(color: str = 'green') -> bytes:
    output = io.BytesIO()
    Image.new('RGB', (24, 24), color).save(output, format='PNG')
    return output.getvalue()


def _teacher():
    return baker.make('accounts.User', role='TEACHER', phone='09120000011')


def _session(teacher):
    payload = {
        'exam_prep': {
            'title': 'آزمون کراپ',
            'questions': [
                {
                    'question_id': 'q1',
                    'question_text_markdown': 'سؤال تصویری',
                    'options': [],
                    'visuals': [
                        {
                            'id': 'inline-crop-1',
                            'role': 'question',
                            'storagePath': 'exam-prep/source/visuals/v1/session-9/p001-q1-question-1-aa.png',
                            'contentType': 'image/png',
                            'byteSize': 100,
                        }
                    ],
                }
            ],
        }
    }
    return ClassCreationSession.objects.create(
        teacher=teacher,
        title='آزمون کراپ',
        pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        status=ClassCreationSession.Status.EXAM_STRUCTURED,
        is_published=False,
        exam_prep_json=json.dumps(payload, ensure_ascii=False),
    )


def _content_url(session):
    return f'/api/classes/exam-prep-sessions/{session.id}/visuals/inline-crop-1/content/'


def _write_crop(private_storage):
    path = private_storage / 'exam-prep' / 'source' / 'visuals' / 'v1' / 'session-9'
    path.mkdir(parents=True, exist_ok=True)
    target = path / 'p001-q1-question-1-aa.png'
    target.write_bytes(_png_bytes())
    return target


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_owner_gets_pre_rendered_stored_crop(private_storage):
    teacher = _teacher()
    session = _session(teacher)
    _write_crop(private_storage)

    response = _client(teacher).get(_content_url(session))

    assert response.status_code == 200
    assert response['Content-Type'].startswith('image/png')
    assert response.content == _png_bytes()


def test_invited_student_gets_stored_crop_when_published(private_storage):
    teacher = _teacher()
    session = _session(teacher)
    _write_crop(private_storage)
    student = baker.make('accounts.User', role='STUDENT', phone='09120000012')
    ClassInvitation.objects.create(session=session, phone=student.phone, invite_code='crop-1')
    session.is_published = True
    session.save(update_fields=['is_published', 'updated_at'])

    response = _client(student).get(_content_url(session))

    assert response.status_code == 200
    assert response['Content-Type'].startswith('image/png')


def test_visual_without_stored_file_or_source_returns_not_found(private_storage):
    teacher = _teacher()
    session = _session(teacher)

    response = _client(teacher).get(_content_url(session))

    assert response.status_code == 404
