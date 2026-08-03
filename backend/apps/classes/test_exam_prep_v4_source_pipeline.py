import io

import pytest
from django.test import override_settings
from model_bakery import baker
from PIL import Image

from apps.classes.models_v4 import ExamProject, ExamSourceDocument
from apps.classes.services import exam_prep_v4_source_pipeline as pipeline
from apps.classes.services.exam_prep_v4_classification import PersistedClassification
from apps.classes.services.exam_prep_v4_fast_classifier import (
    FastClassifierResult,
    RenderedPageInput,
)
from apps.classes.services.exam_prep_v4_pdf_source import PreparedDocument
from apps.classes.services.exam_prep_v4_projects import ExamPrepV4Disabled


pytestmark = pytest.mark.django_db


def _document():
    teacher = baker.make('accounts.User', role='TEACHER')
    project = ExamProject.objects.create(teacher=teacher, title='آزمون')
    document = ExamSourceDocument.objects.create(
        project=project,
        original_name='exam.pdf',
        page_count=2,
    )
    return project, document


def _jpeg(tone):
    image = Image.new('RGB', (240, 320), (tone, tone, tone))
    output = io.BytesIO()
    image.save(output, format='JPEG')
    return output.getvalue()


def _prepared(document_id):
    return PreparedDocument(
        document_id=document_id,
        source_sha256='a' * 64,
        page_count=2,
        pages=(),
        reused=False,
    )


def _classified(document_id):
    return FastClassifierResult(
        model='fast-model',
        prompt_version='test-v1',
        input_fingerprint='b' * 64,
        classification=PersistedClassification(
            document_id=document_id,
            revision=1,
            fingerprint='b' * 64,
            pages=(),
            segments=(),
            issues=(),
            reused=False,
        ),
    )


@override_settings(EXAM_PREP_V4_ENABLED=False)
def test_source_pipeline_is_inaccessible_while_v4_is_disabled(monkeypatch):
    _, document = _document()
    calls = []
    monkeypatch.setattr(
        pipeline,
        'prepare_pdf_source_from_path',
        lambda **_kwargs: calls.append('prepare'),
    )

    with pytest.raises(ExamPrepV4Disabled):
        pipeline.prepare_and_classify_pdf_source(
            document_id=document.id,
            source_path='unused.pdf',
        )

    assert calls == []


@override_settings(EXAM_PREP_V4_ENABLED=True)
def test_source_pipeline_prepares_then_classifies_with_private_page_inputs(monkeypatch):
    project, document = _document()
    calls = []
    page_inputs = (
        RenderedPageInput(1, _jpeg(240), 'image/jpeg', 'عنوان آزمون'),
        RenderedPageInput(2, _jpeg(220), 'image/jpeg', '۱- متن سؤال'),
    )

    def fake_prepare(**kwargs):
        calls.append(('prepare', kwargs))
        ExamSourceDocument.objects.filter(id=document.id).update(
            status=ExamSourceDocument.Status.UPLOADED,
            source_sha256='a' * 64,
        )
        return _prepared(document.id)

    def fake_load(**kwargs):
        calls.append(('load', kwargs))
        return page_inputs

    def fake_classify(**kwargs):
        calls.append(('classify', kwargs))
        current_document = ExamSourceDocument.objects.get(id=document.id)
        current_project = ExamProject.objects.get(id=project.id)
        assert current_document.status == ExamSourceDocument.Status.CLASSIFYING
        assert current_project.status == ExamProject.Status.CLASSIFYING
        ExamSourceDocument.objects.filter(id=document.id).update(
            status=ExamSourceDocument.Status.AWAITING_CONFIRMATION,
        )
        ExamProject.objects.filter(id=project.id).update(
            status=ExamProject.Status.AWAITING_SOURCE_CONFIRMATION,
        )
        return _classified(document.id)

    monkeypatch.setattr(pipeline, 'prepare_pdf_source_from_path', fake_prepare)
    monkeypatch.setattr(pipeline, 'load_classification_page_inputs', fake_load)
    monkeypatch.setattr(pipeline, 'classify_document_pages_fast', fake_classify)

    result = pipeline.prepare_and_classify_pdf_source(
        document_id=document.id,
        source_path='/tmp/source.pdf',
        original_name='teacher.pdf',
        model='fast-model',
    )

    assert result.prepared.document_id == document.id
    assert result.classified.model == 'fast-model'
    assert [call[0] for call in calls] == ['prepare', 'load', 'classify']
    classify_kwargs = calls[-1][1]
    assert classify_kwargs['document_id'] == document.id
    assert classify_kwargs['expected_revision'] == 1
    assert classify_kwargs['model'] == 'fast-model'
    assert classify_kwargs['native_text_samples'] == {
        1: 'عنوان آزمون',
        2: '۱- متن سؤال',
    }
    assert len(classify_kwargs['contact_sheets']) == 1
    assert classify_kwargs['contact_sheets'][0].page_numbers == (1, 2)


@override_settings(EXAM_PREP_V4_ENABLED=True)
def test_source_pipeline_records_classifier_failure_on_document_and_project(monkeypatch):
    project, document = _document()
    page_inputs = (
        RenderedPageInput(1, _jpeg(240)),
        RenderedPageInput(2, _jpeg(220)),
    )
    monkeypatch.setattr(
        pipeline,
        'prepare_pdf_source_from_path',
        lambda **_kwargs: _prepared(document.id),
    )
    monkeypatch.setattr(
        pipeline,
        'load_classification_page_inputs',
        lambda **_kwargs: page_inputs,
    )
    monkeypatch.setattr(
        pipeline,
        'classify_document_pages_fast',
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError('provider unavailable')),
    )

    with pytest.raises(RuntimeError, match='provider unavailable'):
        pipeline.prepare_and_classify_pdf_source(
            document_id=document.id,
            source_path='/tmp/source.pdf',
            model='fast-model',
        )

    document.refresh_from_db()
    project.refresh_from_db()
    assert document.status == ExamSourceDocument.Status.FAILED
    assert document.error_code == 'RuntimeError'
    assert 'provider unavailable' in document.error_detail
    assert project.status == ExamProject.Status.FAILED
    assert project.error_code == 'RuntimeError'
    assert project.workflow_state['stage'] == 'failed'


@override_settings(EXAM_PREP_V4_ENABLED=True)
def test_source_pipeline_records_preparation_failure(monkeypatch):
    project, document = _document()
    monkeypatch.setattr(
        pipeline,
        'prepare_pdf_source_from_path',
        lambda **_kwargs: (_ for _ in ()).throw(ValueError('invalid source')),
    )

    with pytest.raises(ValueError, match='invalid source'):
        pipeline.prepare_and_classify_pdf_source(
            document_id=document.id,
            source_path='/tmp/source.pdf',
        )

    document.refresh_from_db()
    project.refresh_from_db()
    assert document.status == ExamSourceDocument.Status.FAILED
    assert document.error_code == 'ValueError'
    assert project.status == ExamProject.Status.FAILED
