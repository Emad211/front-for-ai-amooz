import pytest
from pydantic import ValidationError

from apps.classes.services.exam_prep_page_records import (
    PageExtraction,
    PageOption,
    PageRecord,
    assemble_page_extractions,
    build_page_first_audit,
    render_page_first_transcript,
)


pytestmark = pytest.mark.unit


def _question(
    number: int,
    *,
    scope: str = 'default',
    text: str = 'متن سؤال',
    continues_from_previous_page: bool = False,
    continues_on_next_page: bool = False,
):
    return PageRecord(
        scope_key=scope,
        question_number=number,
        record_type='question',
        question_text_markdown=text,
        options=[
            PageOption(label='1', text_markdown='گزینه یک'),
            PageOption(label='2', text_markdown='گزینه دو'),
            PageOption(label='3', text_markdown='گزینه سه'),
            PageOption(label='4', text_markdown='گزینه چهار'),
        ],
        continues_from_previous_page=continues_from_previous_page,
        continues_on_next_page=continues_on_next_page,
        confidence=0.96,
    )


def _solution(
    number: int,
    *,
    scope: str = 'default',
    correct: str = '2',
    text: str = 'حل تشریحی سؤال',
):
    return PageRecord(
        scope_key=scope,
        question_number=number,
        record_type='solution',
        correct_option_label=correct,
        teacher_solution_markdown=text,
        final_answer_markdown=f'گزینه {correct}',
        confidence=0.93,
    )


def test_question_and_solution_join_by_scope_and_number():
    result = assemble_page_extractions(
        [
            PageExtraction(page_number=2, records=[_question(51)]),
            PageExtraction(page_number=10, records=[_solution(51)]),
        ],
        title='آزمون زیست',
    )

    assert result.question_count == 1
    assert result.questions_needing_review == 0
    assert result.matched_answer_count == 1
    assert result.orphan_answers == []
    assert result.publication_ready is True
    assert result.issues == []
    question = result.projection['exam_prep']['questions'][0]
    assert question['question_id'] == 'default-q-51'
    assert question['source_question_number'] == '51'
    assert question['source_pages'] == [2, 10]
    assert question['correct_option_label'] == '2'
    assert question['teacher_solution_markdown'] == 'حل تشریحی سؤال'
    assert len(question['options']) == 4


def test_same_number_in_different_scopes_never_collides():
    result = assemble_page_extractions(
        [
            PageExtraction(
                page_number=1,
                records=[_question(1, scope='آزمون-الف'), _solution(1, scope='آزمون-الف')],
            ),
            PageExtraction(
                page_number=2,
                records=[_question(1, scope='آزمون-ب'), _solution(1, scope='آزمون-ب')],
            ),
        ]
    )

    questions = result.projection['exam_prep']['questions']
    assert result.question_count == 2
    assert [question['scope_key'] for question in questions] == ['آزمون-الف', 'آزمون-ب']
    assert len({question['question_id'] for question in questions}) == 2


def test_answer_page_may_appear_before_question_page():
    result = assemble_page_extractions(
        [
            PageExtraction(page_number=1, records=[_solution(8, correct='4')]),
            PageExtraction(page_number=9, records=[_question(8)]),
        ]
    )

    assert result.question_count == 1
    assert result.orphan_answers == []
    question = result.projection['exam_prep']['questions'][0]
    assert question['correct_option_label'] == '4'
    assert question['source_pages'] == [1, 9]


def test_continuation_fragments_join_in_page_order():
    first = _question(
        7,
        text='نیمه اول متن سؤال',
        continues_on_next_page=True,
    )
    first.options = []
    second = _question(
        7,
        text='نیمه دوم متن سؤال',
        continues_from_previous_page=True,
    )

    result = assemble_page_extractions(
        [
            PageExtraction(page_number=4, records=[first]),
            PageExtraction(page_number=5, records=[second, _solution(7)]),
        ]
    )

    question = result.projection['exam_prep']['questions'][0]
    assert question['question_text_markdown'] == 'نیمه اول متن سؤال\n\nنیمه دوم متن سؤال'
    assert question['source_pages'] == [4, 5]
    assert question['issues'] == []


def test_conflicting_answers_are_not_silently_overwritten():
    result = assemble_page_extractions(
        [
            PageExtraction(page_number=1, records=[_question(3)]),
            PageExtraction(
                page_number=8,
                records=[_solution(3, correct='2'), _solution(3, correct='4')],
            ),
        ]
    )

    question = result.projection['exam_prep']['questions'][0]
    assert question['correct_option_label'] == '2'
    assert 'conflicting_correct_option' in question['issues']
    assert result.questions_needing_review == 1
    assert result.publication_ready is False
    assert any(issue.code == 'conflicting_correct_option' for issue in result.issues)


def test_answer_without_question_is_orphan_and_never_fabricates_question():
    result = assemble_page_extractions(
        [PageExtraction(page_number=9, records=[_solution(12)])]
    )

    assert result.question_count == 0
    assert result.projection['exam_prep']['questions'] == []
    assert len(result.orphan_answers) == 1
    orphan = result.orphan_answers[0]
    assert orphan.question_number == 12
    assert orphan.correct_option_label == '2'
    assert orphan.source_pages == [9]
    assert result.publication_ready is False


def test_question_text_and_options_only_come_from_question_records():
    answer_record = PageRecord.model_validate(
        {
            'question_number': 18,
            'record_type': 'solution',
            'question_text_markdown': '۱۸- گزینه «۳»',
            'teacher_solution_markdown': 'هر چه کود بیشتری استفاده شود...',
            'confidence': 95,
        }
    )
    result = assemble_page_extractions(
        [
            PageExtraction(page_number=4, records=[_question(18, text='کدام گزینه درست است؟')]),
            PageExtraction(page_number=11, records=[answer_record]),
        ]
    )

    question = result.projection['exam_prep']['questions'][0]
    assert question['question_text_markdown'] == 'کدام گزینه درست است؟'
    assert 'گزینه' not in question['question_text_markdown']
    assert question['correct_option_label'] == '3'
    assert question['teacher_solution_markdown'].startswith('هر چه کود')


def test_provider_option_strings_and_mapping_are_normalized_before_validation():
    page = PageExtraction.model_validate(
        {
            'page_number': '۶',
            'records': [
                {
                    'question_number': '۳۲',
                    'record_type': 'question',
                    'question_text_markdown': 'صورت سؤال ۳۲',
                    'options': [
                        '۱) گزینه نخست',
                        '۲) گزینه دوم',
                        '۳) گزینه سوم',
                        '۴) گزینه چهارم',
                    ],
                    'confidence': '96%',
                },
                {
                    'question_number': 33,
                    'record_type': 'question',
                    'question_text_markdown': 'صورت سؤال ۳۳',
                    'options': {
                        '1': 'الف',
                        '2': 'ب',
                        '3': 'ج',
                        '4': 'د',
                    },
                    'confidence': 0.9,
                },
            ],
        }
    )

    assert page.page_number == 6
    assert page.records[0].question_number == 32
    assert page.records[0].confidence == 0.96
    assert [option.label for option in page.records[0].options] == ['1', '2', '3', '4']
    assert [option.text_markdown for option in page.records[0].options] == [
        'گزینه نخست',
        'گزینه دوم',
        'گزینه سوم',
        'گزینه چهارم',
    ]
    assert [option.label for option in page.records[1].options] == ['1', '2', '3', '4']


def test_fifty_questions_ignore_answer_only_physics_tail():
    question_pages = []
    for page_number, start in enumerate(range(1, 51, 10), start=2):
        records = [_question(number) for number in range(start, min(start + 10, 51))]
        question_pages.append(PageExtraction(page_number=page_number, records=records))
    answer_records = [_solution(number, correct=str((number % 4) + 1)) for number in range(1, 55)]

    result = assemble_page_extractions(
        question_pages + [PageExtraction(page_number=16, records=answer_records)]
    )

    assert result.question_count == 50
    assert result.matched_answer_count == 50
    assert [item.question_number for item in result.orphan_answers] == [51, 52, 53, 54]
    assert result.question_number_gaps == {}
    assert result.publication_ready is True
    assert result.projection['exam_prep']['questions'][-1]['source_question_number'] == '50'


def test_internal_question_number_gap_is_critical():
    result = assemble_page_extractions(
        [
            PageExtraction(
                page_number=2,
                records=[_question(1), _solution(1), _question(3), _solution(3)],
            )
        ]
    )

    assert result.question_number_gaps == {'default': [2]}
    assert result.publication_ready is False
    audit = build_page_first_audit(result)
    assert audit['status'] == 'needs_review'
    assert any(issue['code'] == 'missing_question_number' for issue in audit['issues'])


def test_failed_pages_block_publication_but_out_of_scope_answers_do_not():
    result = assemble_page_extractions(
        [
            PageExtraction(page_number=2, records=[_question(1), _solution(1)]),
            PageExtraction(page_number=10, records=[_solution(51)]),
        ]
    )

    clean_audit = build_page_first_audit(result)
    failed_audit = build_page_first_audit(result, failed_page_numbers=[6, 7, 8])
    assert clean_audit['status'] == 'passed'
    assert clean_audit['outOfScopeAnswerCount'] == 1
    assert failed_audit['status'] == 'needs_review'
    assert failed_audit['failedPageNumbers'] == [6, 7, 8]


def test_readable_transcript_renders_canonical_dictionary_and_orphans():
    result = assemble_page_extractions(
        [
            PageExtraction(page_number=2, records=[_question(18)]),
            PageExtraction(page_number=11, records=[_solution(18, correct='3')]),
            PageExtraction(page_number=16, records=[_solution(51, correct='1')]),
        ],
        title='دفترچه اول زیست',
    )

    transcript = render_page_first_transcript(result, failed_page_numbers=[8])
    assert '# دفترچه اول زیست' in transcript
    assert '## سؤال 18' in transcript
    assert '**پاسخ صحیح:** گزینه 3' in transcript
    assert 'سؤال 51، گزینه 1' in transcript
    assert 'صفحه‌های پردازش‌نشده: **8**' in transcript


def test_question_number_is_required_by_the_page_contract():
    with pytest.raises(ValidationError):
        PageRecord(
            record_type='question',
            question_text_markdown='بدون شماره',
            options=[],
        )


def test_duplicate_page_numbers_fail_deterministically():
    page = PageExtraction(page_number=1, records=[_question(1), _solution(1)])
    with pytest.raises(ValueError, match='Duplicate page_number'):
        assemble_page_extractions([page, page])
