import pytest

from apps.classes.services import exam_prep_page_extractor as extractor
from apps.classes.services.exam_prep_page_records import (
    PageExtraction,
    PageOption,
    PageRecord,
)


pytestmark = pytest.mark.unit


def _rendered_page(number=11):
    return extractor.RenderedExamPage(
        page_number=number,
        image=b'\x89PNG\r\npage',
        mime_type='image/png',
    )


def test_misclassified_answer_heading_becomes_solution(monkeypatch):
    raw = PageExtraction(
        page_number=11,
        records=[
            PageRecord(
                question_number=18,
                record_type='question',
                question_text_markdown='۱۸- گزینه «۳»\nهر چه کود بیشتری استفاده شود...',
                options=[],
                confidence=0.9,
            )
        ],
    )
    monkeypatch.setattr(extractor, 'generate_structured', lambda **_kwargs: raw)

    result = extractor.extract_exam_prep_page(
        _rendered_page(11),
        model='vision-model',
    )

    record = result.records[0]
    assert record.record_type == 'solution'
    assert record.question_text_markdown == ''
    assert record.options == []
    assert record.correct_option_label == '3'
    assert record.teacher_solution_markdown == 'هر چه کود بیشتری استفاده شود...'


def test_ordinary_question_containing_word_option_is_untouched(monkeypatch):
    raw = PageExtraction(
        page_number=4,
        records=[
            PageRecord(
                question_number=18,
                record_type='question',
                question_text_markdown='کدام گزینه به درستی بیان شده است؟',
                options=[
                    PageOption(label='1', text_markdown='گزینه اول'),
                    PageOption(label='2', text_markdown='گزینه دوم'),
                    PageOption(label='3', text_markdown='گزینه سوم'),
                    PageOption(label='4', text_markdown='گزینه چهارم'),
                ],
                confidence=0.9,
            )
        ],
    )
    monkeypatch.setattr(extractor, 'generate_structured', lambda **_kwargs: raw)

    result = extractor.extract_exam_prep_page(
        _rendered_page(4),
        model='vision-model',
    )

    record = result.records[0]
    assert record.record_type == 'question'
    assert record.question_text_markdown == 'کدام گزینه به درستی بیان شده است؟'
    assert len(record.options) == 4
    assert record.correct_option_label is None


def test_answer_heading_with_different_number_is_not_reassigned(monkeypatch):
    raw = PageExtraction(
        page_number=11,
        records=[
            PageRecord(
                question_number=18,
                record_type='question',
                question_text_markdown='۱۹- گزینه ۳',
                options=[],
                confidence=0.5,
            )
        ],
    )
    monkeypatch.setattr(extractor, 'generate_structured', lambda **_kwargs: raw)

    result = extractor.extract_exam_prep_page(
        _rendered_page(11),
        model='vision-model',
    )

    record = result.records[0]
    assert record.record_type == 'question'
    assert record.question_text_markdown == '۱۹- گزینه ۳'
    assert record.correct_option_label is None
