import io
import uuid

import pytest
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker
from PIL import Image
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from apps.classes.models import ClassCreationSession
from apps.classes.models_v4 import ExamProject, ExamSourceDocument
from apps.classes.models_v4_bridge import ExamV4SessionBridge
from apps.classes.views_v4_compat import ExamPrepSourceAwareStep1View


pytestmark = pytest.mark.django_db
LEGACY_V4_STEP1_PATH = '/internal-tests/exam-prep-v4-step-1/'


@pytest.fixture
def private_storage(tmp_path, monkeypatch):
    storage = FileSystemStorage(location=tmp_path / 'private')
    monkeypatch.setattr(
        ExamSourceDocument._meta.get_field('source_file'),
        'storage',
        storage,
    )
    return storage


def _teacher():
    return baker.make('accounts.User', role='TEACHER')


def _auth(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _post_legacy_v4(user, data):
    """Exercise the retained V4 view without claiming the production route."""

    request = APIRequestFactory().post(
        LEGACY_V4_STEP1_PATH,
        data,
        format='multipart',
    )
    force_authenticate(request, user=user)
    return ExamPrepSourceAwareStep1View.as_view()(request)


def _pdf():
    image = Image.new('RGB', (320, 480), (240, 240, 240))
    output = io.BytesIO()
    image.save(output, format='PDF', resolution=96)
    return output.getvalue()


def _upload(name='exam.pdf'):
    return SimpleUploadedFile(name, _pdf(), content_type='application/pdf')


def test_legacy_v4_view_creates_source_aware_project_and_session(
    private_storage,
    monkeypatch,
    settings,
):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher = _teacher()
    request_id = uuid.uuid4()
    dispatched = []
    monkeypatch.setattr(
        'apps.classes.views_v4_compat.dispatch_exam_prep_v4_sources',
        lambda document_ids: dispatched.append(list(document_ids)) or 'group-1',
    )

    response = _post_legacy_v4(
        teacher,
        {
            'title': 'آمادگی زیست',
            'description': 'آزمون آزمایشی',
            'file': _upload(),
            'client_request_id': str(request_id),
        },
    )

    assert response.status_code == 202
    session = ClassCreationSession.objects.get(id=response.data['id'])
    project = ExamProject.objects.get(teacher=teacher)
    bridge = ExamV4SessionBridge.objects.get(project=project)
    document = project.source_documents.get()
    assert bridge.session_id == session.id
    assert session.pipeline_type == ClassCreationSession.PipelineType.EXAM_PREP
    assert session.source_type == ClassCreationSession.SourceType.PDF
    assert session.client_request_id == request_id
    assert session.workflow_state['sourceAwareProjectId'] == project.id
    assert dispatched == [[document.id]]


def test_legacy_v4_view_rejects_non_pdf(monkeypatch, settings):
    settings.EXAM_PREP_V4_ENABLED = True
    monkeypatch.setattr(
        'apps.classes.views_v4_compat.dispatch_exam_prep_v4_sources',
        lambda document_ids: 'unused',
    )
    upload = SimpleUploadedFile('voice.mp3', b'audio', content_type='audio/mpeg')

    response = _post_legacy_v4(
        _teacher(),
        {'title': 'آزمون', 'file': upload},
    )

    assert response.status_code == 400
    assert ExamProject.objects.count() == 0
    assert ClassCreationSession.objects.count() == 0


def test_legacy_session_project_bridge_is_owner_scoped(
    private_storage,
    monkeypatch,
    settings,
):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher = _teacher()
    other = _teacher()
    monkeypatch.setattr(
        'apps.classes.views_v4_compat.dispatch_exam_prep_v4_sources',
        lambda document_ids: 'group-1',
    )
    created = _post_legacy_v4(
        teacher,
        {'title': 'آزمون', 'file': _upload()},
    )
    session_id = created.data['id']

    own = _auth(teacher).get(
        f'/api/classes/exam-prep-v4/sessions/{session_id}/project/'
    )
    denied = _auth(other).get(
        f'/api/classes/exam-prep-v4/sessions/{session_id}/project/'
    )

    assert own.status_code == 200
    assert own.data['sessionId'] == session_id
    assert own.data['documentId'] is not None
    assert denied.status_code == 404


def test_legacy_project_progress_is_mirrored_into_existing_session(
    private_storage,
    monkeypatch,
    settings,
):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher = _teacher()
    monkeypatch.setattr(
        'apps.classes.views_v4_compat.dispatch_exam_prep_v4_sources',
        lambda document_ids: 'group-1',
    )
    created = _post_legacy_v4(
        teacher,
        {'title': 'آزمون', 'file': _upload()},
    )
    session = ClassCreationSession.objects.get(id=created.data['id'])
    project = ExamProject.objects.get(teacher=teacher)

    project.status = ExamProject.Status.AWAITING_REVIEW
    project.workflow_state = {
        'stage': 'awaiting_review',
        'message': 'آماده بازبینی',
        'progressPercent': 80,
        'warningCount': 2,
    }
    project.save(update_fields=['status', 'workflow_state', 'updated_at'])

    session.refresh_from_db()
    assert session.status == ClassCreationSession.Status.EXAM_TRANSCRIBED
    assert session.workflow_state['stage'] == 'ready_for_review'
    assert session.workflow_state['readyForReview'] is True
    assert session.workflow_state['progressPercent'] == 80


def test_legacy_cancel_propagates_to_source_aware_project(
    private_storage,
    monkeypatch,
    settings,
):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher = _teacher()
    monkeypatch.setattr(
        'apps.classes.views_v4_compat.dispatch_exam_prep_v4_sources',
        lambda document_ids: 'group-1',
    )
    monkeypatch.setattr(
        'apps.classes.services.exam_prep_v4_create_flow.current_app.control.revoke',
        lambda *_args, **_kwargs: None,
    )
    created = _post_legacy_v4(
        teacher,
        {'title': 'آزمون', 'file': _upload()},
    )
    session = ClassCreationSession.objects.get(id=created.data['id'])
    project = ExamProject.objects.get(teacher=teacher)
    project.status = ExamProject.Status.SEGMENTING
    project.workflow_state = {'stage': 'extraction_started', 'taskId': 'task-1'}
    project.save(update_fields=['status', 'workflow_state', 'updated_at'])

    session.status = ClassCreationSession.Status.CANCELLED
    session.save(update_fields=['status', 'updated_at'])

    project.refresh_from_db()
    assert project.cancel_requested is True
    assert project.workflow_state['cancellationRequested'] is True


def test_legacy_v4_dispatch_failure_returns_retryable_error_and_unlocks_session(
    private_storage,
    monkeypatch,
    settings,
):
    settings.EXAM_PREP_V4_ENABLED = True
    teacher = _teacher()

    def fail_dispatch(_document_ids):
        raise RuntimeError('broker unavailable')

    monkeypatch.setattr(
        'apps.classes.views_v4_compat.dispatch_exam_prep_v4_sources',
        fail_dispatch,
    )

    response = _post_legacy_v4(
        teacher,
        {
            'title': 'آزمون خطای صف',
            'file': _upload(),
            'client_request_id': str(uuid.uuid4()),
        },
    )

    assert response.status_code == 503
    assert response.data['code'] == 'source_dispatch_failed'
    session = ClassCreationSession.objects.get(id=response.data['sessionId'])
    project = ExamProject.objects.get(teacher=teacher)
    assert session.status == ClassCreationSession.Status.FAILED
    assert project.status == ExamProject.Status.FAILED
    assert project.error_code == 'source_dispatch_failed'
