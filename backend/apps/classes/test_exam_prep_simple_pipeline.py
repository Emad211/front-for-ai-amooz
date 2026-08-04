import io
import json
import uuid

import pytest
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import resolve
from model_bakery import baker
from PIL import Image
from rest_framework.test import APIClient

from apps.classes.models import ClassCreationSession, ExamPrepExtractionArtifact
from apps.classes.models_v4 import ExamProject
from apps.classes.services import exam_prep_pipeline
from apps.classes.services.exam_prep_page_extractor import RenderedExamPage
from apps.classes.services.exam_prep_page_records import (
    PageExtraction,
    PageOption,
    PageRecord,
)
from apps.classes.services.exam_prep_pipeline import ExamPrepPipelineResult
from apps.classes import tasks_exam_prep
from apps.classes.views_exam_prep import ExamPrepPdfStep1View


pytestmark = pytest.mark.django_db
STEP1_URL = '/api/classes/exam-prep-sessions/step-1/'


@pytest.fixture
def source_storage(tmp_path, monkeypatch):
    storage = FileSystemStorage(location=tmp_path / 'media')
    monkeypatch.setattr(
        ClassCreationSession._meta.get_field('source_file'),
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


def _pdf_bytes(page_count=2):
    images = [
        Image.new('RGB', (320, 480), (240 - index, 240 - index, 240 - index))
        for index in range(page_count)
    ]
    output = io.BytesIO()
    images[0].save(
        output,
        format='PDF',
        resolution=96,
        save_all=True,
        append_images=images[1:],
    )
    return output.getvalue()


def _upload(name='exam.pdf', page_count=2):
    return SimpleUploadedFile(
        name,
        _pdf_bytes(page_count),
        content_type='application/pdf',
    )


def _projection(question_number=51):
    return {
        'exam_prep': {
            'title': 'آزمون زیست',
            'questions': [
                {
                    'question_id': f'default-q-{question_number}',
                    'scope_key': 'default',
                    'section_key': 'default',
                    'source_question_number': str(question_number),
                    'question_text_markdown': 'متن سؤال',
                    'options': [
                        {'label': '1', 'text_markdown': 'گزینه یک'},
                        {'label': '2', 'text_markdown': 'گزینه دو'},
                        {'label': '3', 'text_markdown': 'گزینه سه'},
                        {'label': '4', 'text_markdown': 'گزینه چهار'},
                    ],
                    'correct_option_label': '2',
                    'correct_option_text_markdown': '',
                    'teacher_solution_markdown': 'حل تشریحی',
                    'final_answer_markdown': 'گزینه ۲',
                    'confidence': 0.92,
                    'issues': [],
                    'source_pages': [1, 2],
                }
            ],
        }
    }


def test_existing_step1_url_resolves_to_simple_intake():
    match = resolve(STEP1_URL)
    assert match.func.view_class is ExamPrepPdfStep1View


def test_step1_creates_only_normal_session_and_dispatches_simple_task(
    source_storage,
    monkeypatch,
):
    teacher = _teacher()
    captured = []
    monkeypatch.setattr(
        tasks_exam_prep.process_exam_prep_pdf_session,
        'apply_async',
        lambda **kwargs: captured.append(kwargs),
    )
    request_id = uuid.uuid4()

    response = _auth(teacher).post(
        STEP1_URL,
        {
            'title': 'آزمون زیست',
            'description': 'توضیح',
            'file': _upload(),
            'client_request_id': str(request_id),
            'run_full_pipeline': 'true',
        },
        format='multipart',
    )

    assert response.status_code == 202
    session = ClassCreationSession.objects.get(id=response.data['id'])
    assert session.pipeline_type == ClassCreationSession.PipelineType.EXAM_PREP
    assert session.source_type == ClassCreationSession.SourceType.PDF
    assert session.status == ClassCreationSession.Status.EXAM_TRANSCRIBING
    assert session.client_request_id == request_id
    assert session.source_file
    assert session.celery_task_id
    assert session.workflow_state['stage'] == 'queued'
    assert ExamPrepExtractionArtifact.objects.filter(session=session).count() == 0
    assert ExamProject.objects.filter(teacher=teacher).count() == 0
    assert captured == [
        {
            'args': [session.id],
            'task_id': session.celery_task_id,
            'queue': 'pipeline',
            'retry': False,
        }
    ]


def test_step1_same_request_and_file_is_idempotent(source_storage, monkeypatch):
    teacher = _teacher()
    calls = []
    monkeypatch.setattr(
        tasks_exam_prep.process_exam_prep_pdf_session,
        'apply_async',
        lambda **kwargs: calls.append(kwargs),
    )
    request_id = uuid.uuid4()
    payload = {
        'title': 'آزمون زیست',
        'file': _upload(),
        'client_request_id': str(request_id),
    }
    first = _auth(teacher).post(STEP1_URL, payload, format='multipart')
    second = _auth(teacher).post(
        STEP1_URL,
        {
            'title': 'آزمون زیست',
            'file': _upload(),
            'client_request_id': str(request_id),
        },
        format='multipart',
    )

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.data['id'] == second.data['id']
    assert ClassCreationSession.objects.filter(teacher=teacher).count() == 1
    assert len(calls) == 1


def test_step1_rejects_non_pdf_before_session_creation(source_storage):
    response = _auth(_teacher()).post(
        STEP1_URL,
        {
            'title': 'آزمون',
            'file': SimpleUploadedFile(
                'voice.mp3',
                b'not a pdf',
                content_type='audio/mpeg',
            ),
        },
        format='multipart',
    )

    assert response.status_code == 400
    assert ClassCreationSession.objects.count() == 0


def test_step1_broker_failure_marks_session_terminal(source_storage, monkeypatch):
    def fail_dispatch(**_kwargs):
        raise RuntimeError('broker unavailable')

    monkeypatch.setattr(
        tasks_exam_prep.process_exam_prep_pdf_session,
        'apply_async',
        fail_dispatch,
    )
    response = _auth(_teacher()).post(
        STEP1_URL,
        {'title': 'آزمون', 'file': _upload()},
        format='multipart',
    )

    assert response.status_code == 503
    session = ClassCreationSession.objects.get(id=response.data['sessionId'])
    assert session.status == ClassCreationSession.Status.FAILED
    assert session.celery_task_id == ''
    assert session.workflow_state['stage'] == 'failed'


def test_task_writes_projection_directly_to_existing_session(
    source_storage,
    monkeypatch,
):
    session = ClassCreationSession.objects.create(
        teacher=_teacher(),
        title='آزمون زیست',
        pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        source_type=ClassCreationSession.SourceType.PDF,
        source_file=_upload(page_count=2),
        source_mime_type='application/pdf',
        status=ClassCreationSession.Status.EXAM_TRANSCRIBING,
    )
    fake_result = ExamPrepPipelineResult(
        projection=_projection(),
        issues=[],
        page_count=2,
        question_count=1,
        questions_needing_review=0,
        model='vision-model',
    )
    monkeypatch.setattr(
        tasks_exam_prep,
        'run_exam_prep_pdf_pipeline',
        lambda **_kwargs: fake_result,
    )

    result = tasks_exam_prep.process_exam_prep_pdf_session.run(session.id)

    session.refresh_from_db()
    assert result['status'] == 'ready_for_review'
    assert session.status == ClassCreationSession.Status.EXAM_STRUCTURED
    assert json.loads(session.exam_prep_json) == _projection()
    assert session.source_page_count == 2
    assert session.llm_model == 'vision-model'
    assert session.workflow_state['stage'] == 'ready_for_review'
    assert session.workflow_state['readyForReview'] is True
    assert ExamPrepExtractionArtifact.objects.filter(session=session).count() == 0
    assert ExamProject.objects.filter(teacher=session.teacher).count() == 0


def test_task_honors_cancellation_before_provider(source_storage, monkeypatch):
    session = ClassCreationSession.objects.create(
        teacher=_teacher(),
        title='آزمون',
        pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        source_type=ClassCreationSession.SourceType.PDF,
        source_file=_upload(page_count=1),
        status=ClassCreationSession.Status.EXAM_TRANSCRIBING,
        cancel_requested=True,
    )
    calls = []
    monkeypatch.setattr(
        tasks_exam_prep,
        'run_exam_prep_pdf_pipeline',
        lambda **kwargs: calls.append(kwargs),
    )

    result = tasks_exam_prep.process_exam_prep_pdf_session.run(session.id)

    session.refresh_from_db()
    assert result['status'] == 'cancelled'
    assert session.status == ClassCreationSession.Status.CANCELLED
    assert calls == []


def test_renderer_preserves_every_physical_page():
    pages = exam_prep_pipeline.render_exam_prep_pdf(_pdf_bytes(page_count=3))

    assert [page.page_number for page in pages] == [1, 2, 3]
    assert all(page.mime_type == 'image/png' for page in pages)
    assert all(page.image.startswith(b'\x89PNG') for page in pages)


def test_pipeline_calls_extractor_once_per_page_and_assembles(monkeypatch):
    rendered = [
        RenderedExamPage(page_number=1, image=b'page-1'),
        RenderedExamPage(page_number=2, image=b'page-2'),
    ]
    monkeypatch.setattr(exam_prep_pipeline, 'render_exam_prep_pdf', lambda _data: rendered)
    calls = []

    def fake_extract(page, **kwargs):
        calls.append((page.page_number, kwargs))
        if page.page_number == 1:
            return PageExtraction(
                page_number=1,
                records=[
                    PageRecord(
                        question_number=51,
                        record_type='question',
                        question_text_markdown='متن سؤال',
                        options=[
                            PageOption(label='1', text_markdown='یک'),
                            PageOption(label='2', text_markdown='دو'),
                        ],
                        confidence=0.95,
                    )
                ],
            )
        return PageExtraction(
            page_number=2,
            records=[
                PageRecord(
                    question_number=51,
                    record_type='solution',
                    correct_option_label='2',
                    teacher_solution_markdown='حل',
                    confidence=0.9,
                )
            ],
        )

    monkeypatch.setattr(exam_prep_pipeline, 'extract_exam_prep_page', fake_extract)
    progress = []
    result = exam_prep_pipeline.run_exam_prep_pdf_pipeline(
        data=b'%PDF fake',
        title='آزمون',
        model='vision-model',
        on_page_complete=lambda done, total: progress.append((done, total)),
    )

    assert [number for number, _kwargs in calls] == [1, 2]
    assert all(kwargs['model'] == 'vision-model' for _number, kwargs in calls)
    assert progress == [(1, 2), (2, 2)]
    assert result.question_count == 1
    assert result.projection['exam_prep']['questions'][0]['correct_option_label'] == '2'
