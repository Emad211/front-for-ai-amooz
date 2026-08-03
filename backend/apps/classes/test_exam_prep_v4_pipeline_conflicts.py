import io

import pytest
from django.test import override_settings
from model_bakery import baker
from PIL import Image

from apps.classes.models_v4 import ExamProject, ExamSourceDocument
from apps.classes.services import exam_prep_v4_source_pipeline as pipeline
from apps.classes.services.exam_prep_v4_classification import (
    ClassificationFingerprintConflict,
    PersistedClassification,
)
from apps.classes.services.exam_prep_v4_fast_classifier import (
    FastClassifierResult,
    RenderedPageInput,
)
from apps.classes.services.exam_prep_v4_pdf_source import (
    PreparedDocument,
    V4PdfSourceConflict,
)


pytestmark = pytest.mark.django_db


def _jpeg() -> bytes:
    image = Image.new('RGB', (160, 220), 'white')
    output = io.BytesIO()
    image.save(output, format='JPEG')
    return output.getvalue()


def _reviewable_document():
    teacher = baker.make('accounts.User', role='TEACHER')
    project = ExamProject.objects.create(
        teacher=teacher,
        title='آزمون',
        status=ExamProject.Status.AWAITING_SOURCE_CONFIRMATION,
        workflow_state={'stage': 'awaiting_source_confirmation'},
    )
    document = ExamSourceDocument.objects.create(
        project=project,
        original_name='exam.pdf',
        page_count=1,
        status=ExamSourceDocument.Status.AWAITING_CONFIRMATION,
        classification_fingerprint='a' * 64,
    )
    return project, document


def _prepared(document):
    return PreparedDocument(
        document_id=document.id,
        source_sha256='b' * 64,
        page_count=1,
        pages=(),
        reused=True,
    )


def _classified(document):
    return FastClassifierResult(
        model='fast-model',
        prompt_version='v1',
        input_fingerprint='a' * 64,
        classification=PersistedClassification(
            document_id=document.id,
            revision=document.classification_revision,
            fingerprint='a' * 64,
            pages=(),
            segments=(),
            issues=(),
            reused=True,
        ),
    )


@override_settings(EXAM_PREP_V4_ENABLED=True)
def test_warm_retry_does_not_regress_reviewable_status(monkeypatch):
    project, document = _reviewable_document()
    monkeypatch.setattr(
        pipeline,
        'prepare_pdf_source_from_path',
        lambda **_kwargs: _prepared(document),
    )
    monkeypatch.setattr(
        pipeline,
        'load_classification_page_inputs',
        lambda **_kwargs: (RenderedPageInput(1, _jpeg()),),
    )

    def classify(**_kwargs):
        document.refresh_from_db()
        project.refresh_from_db()
        assert document.status == ExamSourceDocument.Status.AWAITING_CONFIRMATION
        assert project.status == ExamProject.Status.AWAITING_SOURCE_CONFIRMATION
        return _classified(document)

    monkeypatch.setattr(pipeline, 'classify_document_pages_fast', classify)

    result = pipeline.prepare_and_classify_pdf_source(
        document_id=document.id,
        source_path='/tmp/not-used.pdf',
        model='fast-model',
    )

    document.refresh_from_db()
    project.refresh_from_db()
    assert result.classified.classification.reused is True
    assert document.status == ExamSourceDocument.Status.AWAITING_CONFIRMATION
    assert project.status == ExamProject.Status.AWAITING_SOURCE_CONFIRMATION
    assert project.workflow_state == {'stage': 'awaiting_source_confirmation'}


@override_settings(EXAM_PREP_V4_ENABLED=True)
def test_source_conflict_does_not_mark_valid_workflow_failed(monkeypatch):
    project, document = _reviewable_document()
    monkeypatch.setattr(
        pipeline,
        'prepare_pdf_source_from_path',
        lambda **_kwargs: (_ for _ in ()).throw(
            V4PdfSourceConflict('different source')
        ),
    )

    with pytest.raises(V4PdfSourceConflict, match='different source'):
        pipeline.prepare_and_classify_pdf_source(
            document_id=document.id,
            source_path='/tmp/not-used.pdf',
        )

    document.refresh_from_db()
    project.refresh_from_db()
    assert document.status == ExamSourceDocument.Status.AWAITING_CONFIRMATION
    assert document.error_code == ''
    assert project.status == ExamProject.Status.AWAITING_SOURCE_CONFIRMATION
    assert project.error_code == ''


@override_settings(EXAM_PREP_V4_ENABLED=True)
def test_fingerprint_conflict_does_not_mark_valid_workflow_failed(monkeypatch):
    project, document = _reviewable_document()
    monkeypatch.setattr(
        pipeline,
        'prepare_pdf_source_from_path',
        lambda **_kwargs: _prepared(document),
    )
    monkeypatch.setattr(
        pipeline,
        'load_classification_page_inputs',
        lambda **_kwargs: (RenderedPageInput(1, _jpeg()),),
    )
    monkeypatch.setattr(
        pipeline,
        'classify_document_pages_fast',
        lambda **_kwargs: (_ for _ in ()).throw(
            ClassificationFingerprintConflict('changed classifier input')
        ),
    )

    with pytest.raises(ClassificationFingerprintConflict):
        pipeline.prepare_and_classify_pdf_source(
            document_id=document.id,
            source_path='/tmp/not-used.pdf',
            model='different-model',
        )

    document.refresh_from_db()
    project.refresh_from_db()
    assert document.status == ExamSourceDocument.Status.AWAITING_CONFIRMATION
    assert document.error_code == ''
    assert project.status == ExamProject.Status.AWAITING_SOURCE_CONFIRMATION
    assert project.error_code == ''
