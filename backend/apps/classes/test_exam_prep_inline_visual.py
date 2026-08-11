import base64
import hashlib
import io
import json

import pytest
from model_bakery import baker
from PIL import Image
from rest_framework.test import APIClient

from apps.classes.models import ClassCreationSession, ClassInvitation, StudentExamPrepAttempt
from apps.classes.services.exam_prep_mistral_production import PRODUCTION_ENGINE
from apps.classes import views_exam_prep_inline_visual as visual_view


pytestmark = pytest.mark.django_db


def _image_data_url():
    image = Image.new('RGB', (24, 24), 'white')
    output = io.BytesIO()
    image.save(output, format='JPEG')
    image.close()
    return 'data:image/jpeg;base64,' + base64.b64encode(output.getvalue()).decode('ascii')


def _session(*, published=True, role='question'):
    teacher = baker.make('accounts.User', role='TEACHER')
    session = ClassCreationSession.objects.create(
        teacher=teacher,
        title='آزمون',
        pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        status=ClassCreationSession.Status.EXAM_STRUCTURED,
        is_published=published,
        exam_prep_json=json.dumps(
            {
                'exam_prep': {
                    'title': 'آزمون',
                    'questions': [
                        {
                            'question_id': 'default-q-1',
                            'question_text_markdown': 'سؤال',
                            'options': [],
                            'visuals': [
                                {
                                    'id': 'inline-default-q-1',
                                    'role': role,
                                    'dataUrl': _image_data_url(),
                                }
                            ],
                        }
                    ],
                }
            },
            ensure_ascii=False,
        ),
    )
    return session, teacher


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _url(session):
    return (
        f'/api/classes/exam-prep-sessions/{session.id}/visuals/'
        'inline-default-q-1/content/'
    )


class _Storage:
    def __init__(self, files):
        self.files = files

    def open(self, name, mode):
        assert mode == 'rb'
        return io.BytesIO(self.files[name])


class _Storages:
    def __init__(self, files):
        self.storage = _Storage(files)

    def __getitem__(self, alias):
        assert alias == 'answer_sources'
        return self.storage


def _stored_session(*, published=False, role='question'):
    teacher = baker.make('accounts.User', role='TEACHER')
    payload = b'\x89PNG\r\nproduction-visual'
    source_sha256 = 'a' * 64
    payload_sha256 = hashlib.sha256(payload).hexdigest()
    asset_id = 'inline-mistral-v1-stored-question'
    storage_path = (
        f'exam-prep/source/visuals/v1/{source_sha256}/'
        f'p001-q001-{role}-{payload_sha256[:16]}.png'
    )
    visual = {
        'id': asset_id,
        'role': role,
        'optionLabel': None,
        'storagePath': storage_path,
        'contentType': 'image/png',
        'byteSize': len(payload),
        'sha256': payload_sha256,
    }
    registry_entry = {
        **visual,
        'questionId': 'default-q-1',
        'sourceSha256': source_sha256,
    }
    session = ClassCreationSession.objects.create(
        teacher=teacher,
        title='آزمون ذخیره‌شده',
        pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        status=ClassCreationSession.Status.EXAM_STRUCTURED,
        is_published=published,
        exam_prep_json=json.dumps(
            {
                'exam_prep': {
                    'questions': [
                        {
                            'question_id': 'default-q-1',
                            'question_text_markdown': 'سؤال',
                            'options': [],
                            'visuals': [visual],
                        }
                    ]
                }
            },
            ensure_ascii=False,
        ),
        workflow_state={
            'engine': PRODUCTION_ENGINE,
            'readyForReview': True,
            'extractionAudit': {
                'visualAssetRegistry': {asset_id: registry_entry},
            },
        },
    )
    return session, teacher, payload, registry_entry


def _stored_url(session, asset_id='inline-mistral-v1-stored-question'):
    return f'/api/classes/exam-prep-sessions/{session.id}/visuals/{asset_id}/content/'


def test_teacher_can_read_inline_verified_crop():
    session, teacher = _session(published=False)

    response = _client(teacher).get(_url(session))

    assert response.status_code == 200
    assert response['Content-Type'] == 'image/jpeg'
    assert response['Cache-Control'] == 'private, no-store, max-age=0'
    assert response['Pragma'] == 'no-cache'
    assert response.content


def test_invited_student_can_read_published_question_crop():
    session, _teacher = _session(published=True)
    student = baker.make('accounts.User', role='STUDENT', phone='09120000001')
    ClassInvitation.objects.create(
        session=session,
        phone=student.phone,
        invite_code='inline-visual-student',
    )

    response = _client(student).get(_url(session))

    assert response.status_code == 200
    assert response['Content-Type'] == 'image/jpeg'


def test_unrelated_student_cannot_read_crop():
    session, _teacher = _session(published=True)
    student = baker.make('accounts.User', role='STUDENT', phone='09120000002')

    response = _client(student).get(_url(session))

    assert response.status_code == 404


def test_solution_crop_is_hidden_from_student():
    session, _teacher = _session(published=True, role='solution')
    student = baker.make('accounts.User', role='STUDENT', phone='09120000003')
    ClassInvitation.objects.create(
        session=session,
        phone=student.phone,
        invite_code='inline-solution-student',
    )

    response = _client(student).get(_url(session))

    assert response.status_code == 404


def test_solution_crop_is_available_only_after_student_finalizes():
    session, _teacher = _session(published=True, role='solution')
    student = baker.make('accounts.User', role='STUDENT', phone='09120000013')
    ClassInvitation.objects.create(
        session=session,
        phone=student.phone,
        invite_code='inline-solution-finalized',
    )
    StudentExamPrepAttempt.objects.create(
        session=session,
        student=student,
        answers={},
        finalized=True,
    )

    response = _client(student).get(_url(session))

    assert response.status_code == 200


def test_teacher_can_read_registry_bound_stage3_crop(monkeypatch):
    session, teacher, payload, entry = _stored_session()
    monkeypatch.setattr(
        visual_view,
        'storages',
        _Storages({entry['storagePath']: payload}),
    )

    response = _client(teacher).get(_stored_url(session))

    assert response.status_code == 200
    assert response.content == payload
    assert response['Content-Type'] == 'image/png'


def test_stage3_crop_rejects_editable_storage_path_tampering(monkeypatch):
    session, teacher, payload, entry = _stored_session()
    other_path = entry['storagePath'].replace('p001-', 'p999-')
    parsed = json.loads(session.exam_prep_json)
    parsed['exam_prep']['questions'][0]['visuals'][0]['storagePath'] = other_path
    session.exam_prep_json = json.dumps(parsed, ensure_ascii=False)
    session.save(update_fields=['exam_prep_json'])
    monkeypatch.setattr(
        visual_view,
        'storages',
        _Storages({entry['storagePath']: payload, other_path: payload}),
    )

    response = _client(teacher).get(_stored_url(session))

    assert response.status_code == 404


def test_stage3_crop_rejects_blob_hash_mismatch(monkeypatch):
    session, teacher, _payload, entry = _stored_session()
    monkeypatch.setattr(
        visual_view,
        'storages',
        _Storages({entry['storagePath']: b'tampered-blob'}),
    )

    response = _client(teacher).get(_stored_url(session))

    assert response.status_code == 404


def test_stage3_solution_registry_role_is_hidden_from_student(monkeypatch):
    session, _teacher, payload, entry = _stored_session(
        published=True,
        role='solution',
    )
    student = baker.make('accounts.User', role='STUDENT', phone='09120000004')
    ClassInvitation.objects.create(
        session=session,
        phone=student.phone,
        invite_code='stored-solution-student',
    )
    monkeypatch.setattr(
        visual_view,
        'storages',
        _Storages({entry['storagePath']: payload}),
    )

    response = _client(student).get(_stored_url(session))

    assert response.status_code == 404


def test_delete_mistral_session_removes_registry_visuals(monkeypatch):
    session, teacher, _payload, entry = _stored_session()
    deleted = []
    monkeypatch.setattr(
        'core.storage_backends.delete_answer_source_file',
        lambda name: deleted.append(name) or True,
    )

    response = _client(teacher).delete(
        f'/api/classes/exam-prep-sessions/{session.id}/'
    )

    assert response.status_code == 204
    assert deleted == [entry['storagePath']]
    assert not ClassCreationSession.objects.filter(id=session.id).exists()


def test_delete_mistral_session_is_fail_closed_when_visual_cleanup_fails(monkeypatch):
    session, teacher, _payload, entry = _stored_session()
    deleted = []
    monkeypatch.setattr(
        'core.storage_backends.delete_answer_source_file',
        lambda name: deleted.append(name) or False,
    )

    response = _client(teacher).delete(
        f'/api/classes/exam-prep-sessions/{session.id}/'
    )

    assert response.status_code == 503
    assert deleted == [entry['storagePath']]
    assert ClassCreationSession.objects.filter(id=session.id).exists()


def test_delete_mistral_session_is_fail_closed_when_registry_is_missing():
    session, teacher, _payload, _entry = _stored_session()
    workflow = dict(session.workflow_state)
    workflow['extractionAudit'] = {}
    session.workflow_state = workflow
    session.save(update_fields=['workflow_state'])

    response = _client(teacher).delete(
        f'/api/classes/exam-prep-sessions/{session.id}/'
    )

    assert response.status_code == 503
    assert ClassCreationSession.objects.filter(id=session.id).exists()
