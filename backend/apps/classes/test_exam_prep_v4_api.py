import io
import json
import uuid

import pytest
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker
from PIL import Image
from rest_framework.test import APIClient

from apps.classes.models_v4 import ExamProject, ExamSourceDocument
from apps.organizations.models import (
    Organization,
    OrganizationMembership,
    StudyGroup,
    StudyGroupTeacher,
)


pytestmark = pytest.mark.django_db
URL = '/api/classes/exam-prep-v4/projects/'


@pytest.fixture
def private_storage(tmp_path, monkeypatch):
    storage = FileSystemStorage(location=tmp_path / 'private')
    monkeypatch.setattr(
        ExamSourceDocument._meta.get_field('source_file'),
        'storage',
        storage,
    )
    return storage


def _auth(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _user(role='TEACHER'):
    return baker.make('accounts.User', role=role)


def _pdf(tone=240):
    image = Image.new('RGB', (320, 480), (tone, tone, tone))
    output = io.BytesIO()
    image.save(output, format='PDF', resolution=96)
    return output.getvalue()


def _file(name, tone=240):
    return SimpleUploadedFile(
        name,
        _pdf(tone),
        content_type='application/pdf',
    )


def _ids(count):
    return [
        {
            'clientRequestId': str(uuid.uuid4()),
            'clientDocumentId': str(uuid.uuid4()),
            'title': f'آزمون {index + 1}',
        }
        for index in range(count)
    ]


def _post(client, files, metadata=None, **extra):
    payload = {'files': files, **extra}
    if metadata is not None:
        payload['metadata'] = json.dumps(metadata, ensure_ascii=False)
    return client.post(URL, payload, format='multipart')


def test_route_requires_authentication(settings):
    settings.EXAM_PREP_V4_ENABLED = True

    response = APIClient().post(URL, {}, format='multipart')

    assert response.status_code == 401


def test_student_cannot_use_teacher_intake(settings):
    settings.EXAM_PREP_V4_ENABLED = True

    response = _post(_auth(_user('STUDENT')), [_file('student.pdf')], _ids(1))

    assert response.status_code == 403
    assert ExamProject.objects.count() == 0


def test_authenticated_teacher_gets_404_while_feature_is_disabled(settings):
    settings.EXAM_PREP_V4_ENABLED = False

    response = _post(_auth(_user()), [_file('one.pdf')], _ids(1))

    assert response.status_code == 404
    assert ExamProject.objects.count() == 0


def test_three_equal_pdfs_create_three_projects_and_dispatch_three_documents(
    private_storage,
    monkeypatch,
    settings,
):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher = _user()
    same_pdf = _pdf(230)
    metadata = _ids(3)
    dispatched = []
    monkeypatch.setattr(
        'apps.classes.views_v4.dispatch_exam_prep_v4_sources',
        lambda document_ids: dispatched.append(list(document_ids)) or 'group-1',
    )

    response = _post(
        _auth(teacher),
        [
            SimpleUploadedFile(f'exam-{index}.pdf', same_pdf, content_type='application/pdf')
            for index in range(1, 4)
        ],
        metadata,
    )

    assert response.status_code == 202
    assert response.data['dispatchId'] == 'group-1'
    assert len(response.data['projects']) == 3
    project_ids = [item['id'] for item in response.data['projects']]
    document_ids = [item['documentId'] for item in response.data['projects']]
    assert len(set(project_ids)) == 3
    assert len(set(document_ids)) == 3
    assert dispatched == [document_ids]
    assert ExamProject.objects.filter(teacher=teacher).count() == 3
    assert ExamSourceDocument.objects.filter(project__teacher=teacher).count() == 3
    assert all(item['status'] == ExamProject.Status.UPLOADING for item in response.data['projects'])
    assert all(item['reusedSource'] is False for item in response.data['projects'])
    hashes = set(
        ExamSourceDocument.objects.values_list('source_sha256', flat=True)
    )
    assert len(hashes) == 1


def test_invalid_sibling_pdf_rejects_whole_batch_without_rows_or_dispatch(
    private_storage,
    monkeypatch,
    settings,
):
    settings.EXAM_PREP_V4_ENABLED = True
    dispatched = []
    monkeypatch.setattr(
        'apps.classes.views_v4.dispatch_exam_prep_v4_sources',
        lambda document_ids: dispatched.append(list(document_ids)),
    )
    invalid = SimpleUploadedFile(
        'bad.pdf',
        b'not-pdf',
        content_type='application/pdf',
    )

    response = _post(
        _auth(_user()),
        [_file('good.pdf'), invalid],
        _ids(2),
    )

    assert response.status_code == 400
    assert ExamProject.objects.count() == 0
    assert ExamSourceDocument.objects.count() == 0
    assert dispatched == []


def test_metadata_count_must_match_files(settings):
    settings.EXAM_PREP_V4_ENABLED = True

    response = _post(
        _auth(_user()),
        [_file('one.pdf'), _file('two.pdf')],
        _ids(1),
    )

    assert response.status_code == 400
    assert 'metadata' in response.data['errors']


def test_same_ids_and_bytes_retry_same_project_without_new_blob(
    private_storage,
    monkeypatch,
    settings,
):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher = _user()
    metadata = _ids(1)
    dispatches = []
    monkeypatch.setattr(
        'apps.classes.views_v4.dispatch_exam_prep_v4_sources',
        lambda document_ids: dispatches.append(list(document_ids)) or f'group-{len(dispatches)}',
    )

    first = _post(_auth(teacher), [_file('retry.pdf', 225)], metadata)
    second = _post(_auth(teacher), [_file('retry.pdf', 225)], metadata)

    assert first.status_code == second.status_code == 202
    assert second.data['projects'][0]['id'] == first.data['projects'][0]['id']
    assert second.data['projects'][0]['documentId'] == first.data['projects'][0]['documentId']
    assert second.data['projects'][0]['reusedSource'] is True
    assert ExamProject.objects.filter(teacher=teacher).count() == 1
    assert ExamSourceDocument.objects.filter(project__teacher=teacher).count() == 1
    assert len(dispatches) == 2


def test_ready_retry_does_not_dispatch_or_report_uploading(
    private_storage,
    monkeypatch,
    settings,
):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher = _user()
    metadata = _ids(1)
    dispatches = []
    monkeypatch.setattr(
        'apps.classes.views_v4.dispatch_exam_prep_v4_sources',
        lambda document_ids: dispatches.append(list(document_ids)) or 'group',
    )
    first = _post(_auth(teacher), [_file('ready.pdf')], metadata)
    project = ExamProject.objects.get(id=first.data['projects'][0]['id'])
    document = ExamSourceDocument.objects.get(id=first.data['projects'][0]['documentId'])
    project.status = ExamProject.Status.AWAITING_SOURCE_CONFIRMATION
    project.workflow_state = {'stage': 'awaiting_source_confirmation'}
    project.save(update_fields=['status', 'workflow_state', 'updated_at'])
    document.status = ExamSourceDocument.Status.AWAITING_CONFIRMATION
    document.classification_fingerprint = 'a' * 64
    document.save(
        update_fields=['status', 'classification_fingerprint', 'updated_at']
    )

    retry = _post(_auth(teacher), [_file('ready.pdf')], metadata)

    assert retry.status_code == 202
    assert retry.data['dispatchId'] is None
    assert retry.data['projects'][0]['status'] == ExamProject.Status.AWAITING_SOURCE_CONFIRMATION
    assert retry.data['projects'][0]['documentStatus'] == ExamSourceDocument.Status.AWAITING_CONFIRMATION
    assert retry.data['projects'][0]['classificationAlreadyAvailable'] is True
    assert len(dispatches) == 1


def test_same_request_with_different_bytes_returns_409_and_preserves_source(
    private_storage,
    monkeypatch,
    settings,
):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher = _user()
    metadata = _ids(1)
    monkeypatch.setattr(
        'apps.classes.views_v4.dispatch_exam_prep_v4_sources',
        lambda _ids: 'group',
    )
    first = _post(_auth(teacher), [_file('same.pdf', 240)], metadata)
    document = ExamSourceDocument.objects.get(id=first.data['projects'][0]['documentId'])
    original_sha = document.source_sha256
    original_name = document.source_file.name

    response = _post(_auth(teacher), [_file('same.pdf', 180)], metadata)

    assert response.status_code == 409
    assert response.data['code'] == 'idempotency_conflict'
    document.refresh_from_db()
    assert document.source_sha256 == original_sha
    assert document.source_file.name == original_name
    assert private_storage.exists(original_name)


def test_dispatch_failure_preserves_private_source_and_retry_requeues(
    private_storage,
    monkeypatch,
    settings,
):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher = _user()
    metadata = _ids(1)
    calls = []

    def dispatch(document_ids):
        calls.append(list(document_ids))
        if len(calls) == 1:
            raise RuntimeError('broker unavailable')
        return 'group-retry'

    monkeypatch.setattr(
        'apps.classes.views_v4.dispatch_exam_prep_v4_sources',
        dispatch,
    )

    failed = _post(_auth(teacher), [_file('broker.pdf')], metadata)
    assert failed.status_code == 503
    project = ExamProject.objects.get(id=failed.data['projects'][0]['id'])
    document = ExamSourceDocument.objects.get(id=failed.data['projects'][0]['documentId'])
    assert project.status == ExamProject.Status.FAILED
    assert project.error_code == 'dispatch_failed'
    assert document.status == ExamSourceDocument.Status.FAILED
    assert private_storage.exists(document.source_file.name)

    retry = _post(_auth(teacher), [_file('broker.pdf')], metadata)
    assert retry.status_code == 202
    assert retry.data['dispatchId'] == 'group-retry'
    project.refresh_from_db()
    document.refresh_from_db()
    assert project.status == ExamProject.Status.UPLOADING
    assert project.error_code == ''
    assert document.status == ExamSourceDocument.Status.UPLOADED
    assert document.error_code == ''
    assert retry.data['projects'][0]['reusedSource'] is True


def test_unauthorized_organization_scope_returns_404_without_rows(settings):
    settings.EXAM_PREP_V4_ENABLED = True
    owner = _user()
    outsider = _user()
    organization = Organization.objects.create(
        owner=owner,
        name='مدرسه',
        slug='private-school',
    )

    response = _post(
        _auth(outsider),
        [_file('org.pdf')],
        _ids(1),
        organizationId=str(organization.id),
    )

    assert response.status_code == 404
    assert ExamProject.objects.count() == 0


def test_assigned_teacher_can_create_project_in_study_group(
    private_storage,
    monkeypatch,
    settings,
):
    settings.EXAM_PREP_V4_ENABLED = True
    owner = _user()
    teacher = _user()
    organization = Organization.objects.create(
        owner=owner,
        name='مدرسه',
        slug='assigned-school',
    )
    OrganizationMembership.objects.create(
        user=teacher,
        organization=organization,
        org_role=OrganizationMembership.OrgRole.TEACHER,
    )
    group = StudyGroup.objects.create(
        organization=organization,
        name='دوازدهم',
    )
    StudyGroupTeacher.objects.create(
        study_group=group,
        teacher=teacher,
        assigned_by=owner,
    )
    monkeypatch.setattr(
        'apps.classes.views_v4.dispatch_exam_prep_v4_sources',
        lambda _ids: 'group-org',
    )

    response = _post(
        _auth(teacher),
        [_file('org.pdf')],
        _ids(1),
        organizationId=str(organization.id),
        studyGroupId=str(group.id),
    )

    assert response.status_code == 202
    project = ExamProject.objects.get(id=response.data['projects'][0]['id'])
    assert project.organization_id == organization.id
    assert project.study_group_id == group.id
