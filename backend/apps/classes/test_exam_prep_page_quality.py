import pytest

from apps.classes.services.exam_prep_page_output import (
    build_strict_page_first_audit,
    render_strict_page_first_transcript,
)
from apps.classes.services.exam_prep_page_quality import (
    choose_better_page_extraction,
    parse_native_question_evidence,
    reconcile_page_extraction,
    summarize_page_quality,
)
from apps.classes.services.exam_prep_page_records import (
    PageExtraction,
    PageOption,
    PageRecord,
    assemble_page_extractions,
)


pytestmark = pytest.mark.unit


def _question(number, *, text='کدام گزینه درست است؟', options=None, issues=None):
    return PageRecord(
        question_number=number,
        record_type='question',
        question_text_markdown=text,
        options=options or [],
        confidence=0.9,
        issues=issues or [],
    )


def _native_page():
    return '''
-1 کدام گزینه درباره زیست فناوری نادرست است؟
1) گزینهٔ واقعی اول
2) گزینهٔ واقعی دوم
3) گزینهٔ واقعی سوم
4) گزینهٔ واقعی چهارم
-2 چند مورد درست است؟
1) ۱
2) ۲
3) ۳
4) صفر
'''


def test_native_text_parser_extracts_clear_question_option_blocks():
    evidence = parse_native_question_evidence(_native_page())

    assert sorted(evidence) == [1, 2]
    assert evidence[1].question_text.startswith('کدام گزینه')
    assert evidence[1].options == (
        ('1', 'گزینهٔ واقعی اول'),
        ('2', 'گزینهٔ واقعی دوم'),
        ('3', 'گزینهٔ واقعی سوم'),
        ('4', 'گزینهٔ واقعی چهارم'),
    )
    assert evidence[2].options[-1] == ('4', 'صفر')


def test_native_text_parser_accepts_number_before_dash():
    evidence = parse_native_question_evidence(
        '''
1- کدام عبارت درست است؟
1) متن نخست
2) متن دوم
'''
    )

    assert evidence[1].question_text == 'کدام عبارت درست است؟'
    assert evidence[1].options == (
        ('1', 'متن نخست'),
        ('2', 'متن دوم'),
    )


def test_native_text_replaces_marker_only_placeholder_options():
    page = PageExtraction(
        page_number=2,
        records=[
            _question(
                1,
                options=[
                    PageOption(label='1', text_markdown='1'),
                    PageOption(label='2', text_markdown='2'),
                    PageOption(label='3', text_markdown='3'),
                    PageOption(label='4', text_markdown='4'),
                ],
                issues=['missing_options_text'],
            )
        ],
    )

    repaired = reconcile_page_extraction(page, native_text=_native_page())

    record = repaired.records[0]
    assert [item.text_markdown for item in record.options] == [
        'گزینهٔ واقعی اول',
        'گزینهٔ واقعی دوم',
        'گزینهٔ واقعی سوم',
        'گزینهٔ واقعی چهارم',
    ]
    assert record.issues == []
    assert summarize_page_quality(repaired).critical_count == 0


def test_native_text_recovers_options_omitted_by_provider():
    page = PageExtraction(
        page_number=2,
        records=[_question(1, options=[])],
    )

    repaired = reconcile_page_extraction(page, native_text=_native_page())

    assert len(repaired.records[0].options) == 4
    assert repaired.records[0].issues == []


def test_interleaved_marker_and_text_options_collapse_to_four():
    page = PageExtraction(
        page_number=3,
        records=[
            _question(
                9,
                options=[
                    PageOption(label='1', text_markdown='1'),
                    PageOption(label='2', text_markdown='متن گزینه یک'),
                    PageOption(label='3', text_markdown='2'),
                    PageOption(label='4', text_markdown='متن گزینه دو'),
                    PageOption(label='5', text_markdown='3'),
                    PageOption(label='6', text_markdown='متن گزینه سه'),
                    PageOption(label='7', text_markdown='4'),
                    PageOption(label='8', text_markdown='متن گزینه چهار'),
                ],
            )
        ],
    )

    repaired = reconcile_page_extraction(page)

    assert [(item.label, item.text_markdown) for item in repaired.records[0].options] == [
        ('1', 'متن گزینه یک'),
        ('2', 'متن گزینه دو'),
        ('3', 'متن گزینه سه'),
        ('4', 'متن گزینه چهار'),
    ]
    assert repaired.records[0].issues == []


def test_count_question_may_have_genuinely_numeric_options():
    page = PageExtraction(
        page_number=7,
        records=[
            _question(
                40,
                text='چند مورد از عبارت‌های زیر نادرست است؟',
                options=[
                    PageOption(label='1', text_markdown='۱'),
                    PageOption(label='2', text_markdown='۲'),
                    PageOption(label='3', text_markdown='۳'),
                    PageOption(label='4', text_markdown='۴'),
                ],
            )
        ],
    )

    repaired = reconcile_page_extraction(page)

    assert 'placeholder_option_text' not in repaired.records[0].issues
    assert summarize_page_quality(repaired).critical_count == 0


def test_non_count_marker_only_options_are_critical():
    page = PageExtraction(
        page_number=8,
        records=[
            _question(
                45,
                options=[
                    PageOption(label='1', text_markdown='1'),
                    PageOption(label='2', text_markdown='2'),
                    PageOption(label='3', text_markdown='3'),
                    PageOption(label='4', text_markdown='4'),
                ],
            )
        ],
    )

    repaired = reconcile_page_extraction(page)
    quality = summarize_page_quality(repaired)

    assert 'placeholder_option_text' in repaired.records[0].issues
    assert quality.repairable_critical_codes == ('placeholder_option_text',)


def test_visual_question_is_fail_closed_not_fake_complete():
    page = PageExtraction(
        page_number=8,
        records=[
            _question(
                44,
                text='با توجه به طیف طول موج نمایش داده شده، کدام نمودار درست است؟',
                options=[
                    PageOption(label='1', text_markdown='1'),
                    PageOption(label='2', text_markdown='2'),
                    PageOption(label='3', text_markdown='3'),
                    PageOption(label='4', text_markdown='4'),
                ],
            )
        ],
    )

    repaired = reconcile_page_extraction(page)
    quality = summarize_page_quality(repaired)

    assert 'visual_evidence_required' in repaired.records[0].issues
    assert quality.critical_count == 2
    assert quality.repairable_critical_count == 1


def test_stale_provider_structural_issue_is_recomputed_and_removed():
    page = PageExtraction(
        page_number=3,
        records=[
            PageRecord(
                question_number=9,
                record_type='question_answer',
                question_text_markdown='کدام گزینه درست است؟',
                options=[
                    PageOption(label='1', text_markdown='متن اول'),
                    PageOption(label='2', text_markdown='متن دوم'),
                    PageOption(label='3', text_markdown='متن سوم'),
                    PageOption(label='4', text_markdown='متن چهارم'),
                ],
                correct_option_label='4',
                confidence=0.9,
                issues=['correct_option_not_in_options'],
            )
        ],
    )

    repaired = reconcile_page_extraction(page)

    assert repaired.records[0].issues == []


def test_noop_reconciliation_preserves_page_identity():
    page = PageExtraction(
        page_number=3,
        records=[
            _question(
                9,
                options=[
                    PageOption(label='1', text_markdown='متن اول'),
                    PageOption(label='2', text_markdown='متن دوم'),
                ],
            )
        ],
    )

    assert reconcile_page_extraction(page) is page


def test_strict_audit_counts_extracted_and_usable_questions_separately():
    good = PageRecord(
        question_number=1,
        record_type='question_answer',
        question_text_markdown='کدام گزینه درست است؟',
        options=[
            PageOption(label='1', text_markdown='متن واقعی اول'),
            PageOption(label='2', text_markdown='متن واقعی دوم'),
        ],
        correct_option_label='1',
        confidence=0.9,
    )
    bad = _question(
        2,
        options=[
            PageOption(label='1', text_markdown='1'),
            PageOption(label='2', text_markdown='2'),
            PageOption(label='3', text_markdown='3'),
            PageOption(label='4', text_markdown='4'),
        ],
    )
    page = reconcile_page_extraction(
        PageExtraction(page_number=2, records=[good, bad])
    )
    result = assemble_page_extractions([page], title='آزمون')

    audit = build_strict_page_first_audit(result)
    transcript = render_strict_page_first_transcript(result)

    assert audit['questionCount'] == 2
    assert audit['usableQuestionCount'] == 1
    assert audit['questionsNeedingReview'] == 1
    assert audit['status'] == 'needs_review'
    assert 'سؤال‌های استخراج‌شده: **2**' in transcript
    assert 'سؤال‌های آمادهٔ استفاده: **1**' in transcript
    assert 'قابل انتشار نیست' in transcript


def test_better_candidate_prefers_fewer_semantic_failures():
    broken = reconcile_page_extraction(
        PageExtraction(
            page_number=2,
            records=[_question(1, options=[])],
        )
    )
    valid = reconcile_page_extraction(
        PageExtraction(
            page_number=2,
            records=[
                _question(
                    1,
                    options=[
                        PageOption(label='1', text_markdown='متن اول'),
                        PageOption(label='2', text_markdown='متن دوم'),
                    ],
                )
            ],
        )
    )

    assert choose_better_page_extraction(broken, valid) is valid
