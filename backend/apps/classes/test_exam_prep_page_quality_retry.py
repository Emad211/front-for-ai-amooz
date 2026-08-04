import pytest

from apps.classes.services import exam_prep_page_extractor as extractor
from apps.classes.services.exam_prep_page_records import (
    PageExtraction,
    PageOption,
    PageRecord,
)


pytestmark = pytest.mark.unit


def _page(*, native_text=''):
    return extractor.RenderedExamPage(
        page_number=2,
        image=b'\x89PNG\r\npage',
        mime_type='image/png',
        native_text=native_text,
    )


def _question(options, *, text='کدام گزینه درست است؟'):
    return PageExtraction(
        page_number=2,
        records=[
            PageRecord(
                question_number=1,
                record_type='question',
                question_text_markdown=text,
                options=options,
                confidence=0.9,
            )
        ],
    )


def _valid_options():
    return [
        PageOption(label='1', text_markdown='گزینه اول'),
        PageOption(label='2', text_markdown='گزینه دوم'),
        PageOption(label='3', text_markdown='گزینه سوم'),
        PageOption(label='4', text_markdown='گزینه چهارم'),
    ]


def _placeholder_options():
    return [
        PageOption(label='1', text_markdown='1'),
        PageOption(label='2', text_markdown='2'),
        PageOption(label='3', text_markdown='3'),
        PageOption(label='4', text_markdown='4'),
    ]


def test_semantic_failure_triggers_one_fresh_quality_pass(monkeypatch):
    monkeypatch.setenv('EXAM_PREP_PAGE_QUALITY_REPAIR_ATTEMPTS', '1')
    calls = []
    results = [
        _question(_placeholder_options()),
        _question(_valid_options()),
    ]

    def fake_generate_structured(**kwargs):
        calls.append(kwargs)
        return results.pop(0)

    monkeypatch.setattr(extractor, 'generate_structured', fake_generate_structured)

    result = extractor.extract_exam_prep_page(_page(), model='vision-model')

    assert len(calls) == 2
    assert calls[0]['detail'] == 'exam_prep_page_extraction'
    assert calls[1]['detail'] == 'exam_prep_page_quality_repair'
    assert calls[1]['tracking_context']['quality_pass'] == 1
    assert [item.text_markdown for item in result.records[0].options] == [
        'گزینه اول',
        'گزینه دوم',
        'گزینه سوم',
        'گزینه چهارم',
    ]
    assert result.records[0].issues == []


def test_native_text_repairs_first_pass_without_extra_provider_call(monkeypatch):
    monkeypatch.setenv('EXAM_PREP_PAGE_QUALITY_REPAIR_ATTEMPTS', '1')
    calls = []

    def fake_generate_structured(**kwargs):
        calls.append(kwargs)
        return _question(_placeholder_options())

    monkeypatch.setattr(extractor, 'generate_structured', fake_generate_structured)
    native = '''
-1 کدام گزینه درست است؟
1) گزینه اول
2) گزینه دوم
3) گزینه سوم
4) گزینه چهارم
'''

    result = extractor.extract_exam_prep_page(
        _page(native_text=native),
        model='vision-model',
    )

    assert len(calls) == 1
    user_text = calls[0]['messages'][1]['content'][0]['text']
    assert 'NATIVE_TEXT_EVIDENCE_BEGIN' in user_text
    assert 'گزینه چهارم' in user_text
    assert [item.text_markdown for item in result.records[0].options] == [
        'گزینه اول',
        'گزینه دوم',
        'گزینه سوم',
        'گزینه چهارم',
    ]


def test_visual_only_failure_does_not_waste_quality_retry(monkeypatch):
    monkeypatch.setenv('EXAM_PREP_PAGE_QUALITY_REPAIR_ATTEMPTS', '2')
    calls = []

    def fake_generate_structured(**kwargs):
        calls.append(kwargs)
        return _question(
            _valid_options(),
            text='با توجه به شکل مقابل کدام گزینه درست است؟',
        )

    monkeypatch.setattr(extractor, 'generate_structured', fake_generate_structured)

    result = extractor.extract_exam_prep_page(_page(), model='vision-model')

    assert len(calls) == 1
    assert result.records[0].issues == ['visual_evidence_required']


def test_quality_repair_never_replaces_better_first_pass(monkeypatch):
    monkeypatch.setenv('EXAM_PREP_PAGE_QUALITY_REPAIR_ATTEMPTS', '1')
    calls = []
    results = [
        _question(_placeholder_options()),
        _question([]),
    ]

    def fake_generate_structured(**kwargs):
        calls.append(kwargs)
        return results.pop(0)

    monkeypatch.setattr(extractor, 'generate_structured', fake_generate_structured)

    result = extractor.extract_exam_prep_page(_page(), model='vision-model')

    assert len(calls) == 2
    assert len(result.records[0].options) == 4
    assert 'placeholder_option_text' in result.records[0].issues
