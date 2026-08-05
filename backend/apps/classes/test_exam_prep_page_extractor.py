import pytest

from apps.classes.services import exam_prep_page_extractor as extractor
from apps.classes.services.exam_prep_page_records import (
    PageExtraction,
    PageOption,
    PageRecord,
    assemble_page_extractions,
)
from apps.commons.llm_prompts import PROMPTS
from apps.commons.models import LLMUsageLog


pytestmark = pytest.mark.unit


def _page(number: int = 1, *, mime_type: str = 'image/png', **kwargs):
    return extractor.RenderedExamPage(
        page_number=number,
        image=b'\x89PNG\r\npage-bytes',
        mime_type=mime_type,
        **kwargs,
    )


def _question_page(number: int, question_number: int):
    return PageExtraction(
        page_number=number,
        records=[
            PageRecord(
                scope_key='exam-a',
                question_number=question_number,
                record_type='question',
                question_text_markdown='متن سؤال',
                options=[
                    PageOption(label='1', text_markdown='گزینه یک'),
                    PageOption(label='2', text_markdown='گزینه دو'),
                    PageOption(label='3', text_markdown='گزینه سه'),
                    PageOption(label='4', text_markdown='گزینه چهار'),
                ],
                confidence=0.97,
            )
        ],
    )


def _solution_page(number: int, question_number: int):
    return PageExtraction(
        page_number=number,
        records=[
            PageRecord(
                scope_key='exam-a',
                question_number=question_number,
                record_type='solution',
                correct_option_label='2',
                teacher_solution_markdown='حل تشریحی',
                final_answer_markdown='گزینه ۲',
                confidence=0.94,
            )
        ],
    )


def _clear_model_env(monkeypatch):
    for name in ('EXAM_PREP_PAGE_MODEL', 'PDF_VISION_MODEL', 'MODEL_NAME'):
        monkeypatch.delenv(name, raising=False)


def test_page_prompt_is_registered_and_record_first():
    prompt = PROMPTS['exam_prep_page_extraction']['default']

    assert 'exactly ONE rendered PDF page' in prompt
    assert 'Extract every visible numbered question' in prompt
    assert 'question_number' in prompt
    assert 'continues_on_next_page' in prompt
    assert 'CONTINUATION_HINT' in prompt
    assert 'context-only' in prompt


def test_page_model_uses_explicit_then_specific_then_shared_env(monkeypatch):
    _clear_model_env(monkeypatch)
    monkeypatch.setenv('MODEL_NAME', 'models/shared-model')
    monkeypatch.setenv('PDF_VISION_MODEL', 'models/pdf-model')
    monkeypatch.setenv('EXAM_PREP_PAGE_MODEL', 'models/page-model')

    assert extractor.select_exam_prep_page_model('models/explicit-model') == 'explicit-model'
    assert extractor.select_exam_prep_page_model() == 'page-model'
    monkeypatch.delenv('EXAM_PREP_PAGE_MODEL')
    assert extractor.select_exam_prep_page_model() == 'pdf-model'
    monkeypatch.delenv('PDF_VISION_MODEL')
    assert extractor.select_exam_prep_page_model() == 'shared-model'


def test_page_model_fails_without_configuration(monkeypatch):
    _clear_model_env(monkeypatch)

    with pytest.raises(extractor.ExamPrepPageConfigurationError):
        extractor.select_exam_prep_page_model()


def test_extract_page_makes_one_structured_multimodal_request(monkeypatch):
    captured = []
    expected = _question_page(7, 51)

    def fake_generate_structured(**kwargs):
        captured.append(kwargs)
        return expected

    monkeypatch.setattr(extractor, 'generate_structured', fake_generate_structured)

    result = extractor.extract_exam_prep_page(
        _page(
            7,
            mime_type='image/jpg',
            native_text='متن همین صفحه',
            previous_native_text='انتهای صفحه قبل',
            next_native_text='ابتدای صفحه بعد',
        ),
        model='models/vision-model',
        scope_hint='exam-a',
        continuation_hint=50,
    )

    assert result is expected
    assert len(captured) == 1
    call = captured[0]
    assert call['schema'] is PageExtraction
    assert call['model'] == 'vision-model'
    assert call['feature'] == LLMUsageLog.Feature.PDF_EXTRACTION
    assert call['temperature'] == 0
    assert call['max_repair'] == 1
    assert call['strict_json_schema'] is True
    assert call['sensitive'] is True
    assert call['provider_attempts'] == 1
    assert call['detail'] == 'exam_prep_page_extraction'
    assert call['tracking_context'] == {
        'stage': 'page_extraction',
        'page_number': 7,
        'region': 'full_page',
    }

    user_parts = call['messages'][1]['content']
    assert user_parts[0]['type'] == 'text'
    prompt = user_parts[0]['text']
    assert 'PAGE_NUMBER: 7' in prompt
    assert 'REGION: full_page' in prompt
    assert 'SCOPE_HINT: exam-a' in prompt
    assert 'CONTINUATION_HINT: 50' in prompt
    assert 'متن همین صفحه' in prompt
    assert 'انتهای صفحه قبل' in prompt
    assert 'ابتدای صفحه بعد' in prompt
    assert user_parts[1]['type'] == 'image_url'
    assert user_parts[1]['image_url']['url'].startswith('data:image/jpeg;base64,')


def test_page_repair_attempts_can_be_disabled(monkeypatch):
    captured = []
    monkeypatch.setenv('EXAM_PREP_PAGE_REPAIR_ATTEMPTS', '0')
    monkeypatch.setattr(
        extractor,
        'generate_structured',
        lambda **kwargs: captured.append(kwargs) or _question_page(1, 1),
    )

    extractor.extract_exam_prep_page(_page(1), model='vision-model')

    assert captured[0]['max_repair'] == 0


def test_extract_page_rejects_provider_page_number_mismatch(monkeypatch):
    monkeypatch.setattr(
        extractor,
        'generate_structured',
        lambda **_kwargs: PageExtraction(page_number=8, records=[]),
    )

    with pytest.raises(extractor.ExtractedPageNumberMismatch, match='Expected page 7'):
        extractor.extract_exam_prep_page(_page(7), model='vision-model')


@pytest.mark.parametrize(
    'page',
    [
        extractor.RenderedExamPage(page_number=0, image=b'image'),
        extractor.RenderedExamPage(page_number=1, image=b''),
        extractor.RenderedExamPage(
            page_number=1,
            image=b'image',
            mime_type='application/pdf',
        ),
    ],
)
def test_invalid_rendered_page_fails_before_provider(monkeypatch, page):
    called = []
    monkeypatch.setattr(
        extractor,
        'generate_structured',
        lambda **_kwargs: called.append(True),
    )

    with pytest.raises(extractor.InvalidRenderedExamPage):
        extractor.extract_exam_prep_page(page, model='vision-model')
    assert called == []


def test_two_fake_page_calls_assemble_into_existing_exam_projection(monkeypatch):
    outputs = iter([
        _question_page(2, 51),
        _solution_page(10, 51),
    ])
    calls = []

    def fake_generate_structured(**kwargs):
        calls.append(kwargs)
        return next(outputs)

    monkeypatch.setattr(extractor, 'generate_structured', fake_generate_structured)

    extracted = [
        extractor.extract_exam_prep_page(_page(2), model='vision-model'),
        extractor.extract_exam_prep_page(_page(10), model='vision-model'),
    ]
    result = assemble_page_extractions(extracted, title='آزمون زیست')

    assert len(calls) == 2
    assert result.question_count == 1
    assert result.questions_needing_review == 0
    question = result.projection['exam_prep']['questions'][0]
    assert question['source_question_number'] == '51'
    assert question['source_pages'] == [2, 10]
    assert question['correct_option_label'] == '2'
    assert question['teacher_solution_markdown'] == 'حل تشریحی'
