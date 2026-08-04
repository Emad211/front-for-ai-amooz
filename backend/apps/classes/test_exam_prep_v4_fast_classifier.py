import io

import pytest
from PIL import Image
from model_bakery import baker

from apps.classes.models_v4 import ExamProject, ExamSourceDocument
from apps.classes.services import exam_prep_v4_fast_classifier as fast
from apps.classes.services.exam_prep_v4_fast_classifier import (
    ContactSheet,
    FastClassificationEnvelope,
    FastClassifierConfigurationError,
    InvalidContactSheetInput,
    RenderedPageInput,
    build_contact_sheets,
    classify_document_pages_fast,
)
from apps.commons.llm_prompts import PROMPTS


pytestmark = pytest.mark.django_db


def _image_bytes(*, width=300, height=420, tone=240):
    image = Image.new('RGB', (width, height), (tone, tone, tone))
    output = io.BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()


def _document(*, page_count=3, source_sha256='a' * 64):
    teacher = baker.make('accounts.User', role='TEACHER')
    project = ExamProject.objects.create(teacher=teacher, title='آزمون')
    document = ExamSourceDocument.objects.create(
        project=project,
        original_name='exam.pdf',
        page_count=page_count,
        source_sha256=source_sha256,
    )
    return project, document


def _sheets(page_count):
    return build_contact_sheets(
        [
            RenderedPageInput(
                page_number=page_number,
                image=_image_bytes(tone=220 + page_number),
            )
            for page_number in range(1, page_count + 1)
        ],
        pages_per_sheet=12,
    )


def test_fast_classifier_prompt_is_registered_centrally():
    prompt = PROMPTS['exam_prep_v4_page_classification']['default']
    assert 'cover located in the middle' in prompt
    assert 'answer_solutions' in prompt
    assert 'Do not answer questions' in prompt


def test_contact_sheet_builder_is_bounded_numbered_and_deterministic():
    pages = [
        RenderedPageInput(page_number=page, image=_image_bytes(tone=200 + page))
        for page in range(1, 14)
    ]

    first = build_contact_sheets(pages, pages_per_sheet=12)
    second = build_contact_sheets(reversed(pages), pages_per_sheet=12)

    assert [sheet.page_numbers for sheet in first] == [
        tuple(range(1, 13)),
        (13,),
    ]
    assert [sheet.sha256 for sheet in first] == [sheet.sha256 for sheet in second]
    assert all(sheet.mime_type == 'image/jpeg' for sheet in first)
    for sheet in first:
        image = Image.open(io.BytesIO(sheet.image))
        image.verify()
        assert len(sheet.image) < 1_000_000


def test_contact_sheet_builder_rejects_duplicate_page_numbers():
    page = RenderedPageInput(page_number=1, image=_image_bytes())
    with pytest.raises(InvalidContactSheetInput, match='unique'):
        build_contact_sheets([page, page])


def test_contact_sheet_builder_rejects_unreadable_images():
    with pytest.raises(InvalidContactSheetInput, match='not a readable image'):
        build_contact_sheets(
            [RenderedPageInput(page_number=1, image=b'not-an-image')]
        )


def test_fast_classifier_requires_env_selected_model(monkeypatch):
    _, document = _document(page_count=1)
    monkeypatch.delenv('EXAM_PREP_V4_CLASSIFICATION_MODEL', raising=False)
    monkeypatch.delenv('PDF_VISION_MODEL', raising=False)
    monkeypatch.delenv('MODEL_NAME', raising=False)

    with pytest.raises(FastClassifierConfigurationError):
        classify_document_pages_fast(
            document_id=document.id,
            expected_revision=1,
            contact_sheets=_sheets(1),
        )


def test_fast_classifier_falls_back_to_generic_model_env(monkeypatch):
    monkeypatch.delenv('EXAM_PREP_V4_CLASSIFICATION_MODEL', raising=False)
    monkeypatch.delenv('PDF_VISION_MODEL', raising=False)
    monkeypatch.setenv('MODEL_NAME', 'models/generic-multimodal-model')

    assert fast._select_model() == 'generic-multimodal-model'


def test_fast_classifier_requires_complete_non_overlapping_sheet_coverage():
    _, document = _document(page_count=2)
    image = _image_bytes()

    with pytest.raises(InvalidContactSheetInput, match='do not cover'):
        classify_document_pages_fast(
            document_id=document.id,
            expected_revision=1,
            contact_sheets=(
                ContactSheet(
                    page_numbers=(1,),
                    image=image,
                    mime_type='image/png',
                    sha256='b' * 64,
                ),
            ),
            model='fast-model',
        )

    with pytest.raises(InvalidContactSheetInput, match='more than one'):
        classify_document_pages_fast(
            document_id=document.id,
            expected_revision=1,
            contact_sheets=(
                ContactSheet((1,), image, 'image/png', 'c' * 64),
                ContactSheet((1, 2), image, 'image/png', 'd' * 64),
            ),
            model='fast-model',
        )


def test_fast_classifier_uses_one_multimodal_call_and_tolerant_persistence(
    monkeypatch,
):
    project, document = _document(page_count=3)
    captured = {}

    def fake_generate_structured(**kwargs):
        captured.update(kwargs)
        return FastClassificationEnvelope(
            pages=[
                {'page_number': 1, 'role': 'cover', 'confidence': 0.99},
                {'page_number': 2, 'role': 'questions', 'confidence': 0.92},
                {'page_number': 3, 'role': 'invalid-role', 'confidence': 0.8},
            ]
        )

    monkeypatch.setattr(fast, 'generate_structured', fake_generate_structured)

    result = classify_document_pages_fast(
        document_id=document.id,
        expected_revision=1,
        contact_sheets=_sheets(3),
        native_text_samples={1: 'عنوان آزمون', 2: '۱- متن سؤال'},
        model='models/fast-classifier',
    )

    document.refresh_from_db()
    project.refresh_from_db()
    assert result.model == 'fast-classifier'
    assert result.classification.reused is False
    assert [page.predicted_role for page in document.pages.order_by('page_number')] == [
        'cover',
        'questions',
        'unknown',
    ]
    assert {issue.code for issue in result.classification.issues} == {
        'invalid_page_record',
        'missing_page_prediction',
    }
    assert project.status == ExamProject.Status.AWAITING_SOURCE_CONFIRMATION

    assert captured['provider_attempts'] == 1
    assert captured['temperature'] == 0
    assert captured['max_repair'] == 1
    assert captured['sensitive'] is True
    assert captured['detail'] == 'exam_prep_v4_page_classification'
    assert captured['tracking_context'] == {
        'exam_project_id': project.id,
        'source_document_id': document.id,
        'revision': 1,
        'page_count': 3,
        'stage': 'page_classification',
        'prompt_version': fast.PROMPT_VERSION,
    }
    user_parts = captured['messages'][1]['content']
    assert any(part.get('type') == 'image_url' for part in user_parts)
    assert not any('source_sha256' in str(value) for value in captured['tracking_context'].values())


def test_unchanged_warm_classification_skips_new_llm_call(monkeypatch):
    _, document = _document(page_count=2)
    calls = []

    def fake_generate_structured(**_kwargs):
        calls.append(1)
        return FastClassificationEnvelope(
            pages=[
                {'page_number': 1, 'role': 'cover'},
                {'page_number': 2, 'role': 'questions'},
            ]
        )

    monkeypatch.setattr(fast, 'generate_structured', fake_generate_structured)
    sheets = _sheets(2)

    first = classify_document_pages_fast(
        document_id=document.id,
        expected_revision=1,
        contact_sheets=sheets,
        native_text_samples={1: 'cover', 2: 'questions'},
        model='fast-model',
    )
    second = classify_document_pages_fast(
        document_id=document.id,
        expected_revision=1,
        contact_sheets=sheets,
        native_text_samples={1: 'cover', 2: 'questions'},
        model='fast-model',
    )

    assert first.input_fingerprint == second.input_fingerprint
    assert first.classification.reused is False
    assert second.classification.reused is True
    assert len(calls) == 1


def test_native_text_sample_is_bounded_before_llm_call(monkeypatch):
    _, document = _document(page_count=1)
    captured = {}
    monkeypatch.setenv('EXAM_PREP_V4_CLASSIFICATION_TEXT_SAMPLE_CHARS', '12')

    def fake_generate_structured(**kwargs):
        captured.update(kwargs)
        return FastClassificationEnvelope(
            pages=[{'page_number': 1, 'role': 'questions'}]
        )

    monkeypatch.setattr(fast, 'generate_structured', fake_generate_structured)
    classify_document_pages_fast(
        document_id=document.id,
        expected_revision=1,
        contact_sheets=_sheets(1),
        native_text_samples={1: '1234567890abcdefghijk'},
        model='fast-model',
    )

    catalog_text = captured['messages'][1]['content'][0]['text']
    assert '1234567890ab' in catalog_text
    assert '1234567890abc' not in catalog_text
