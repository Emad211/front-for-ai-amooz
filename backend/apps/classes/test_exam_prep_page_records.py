import pytest
from pydantic import ValidationError

from apps.classes.services.exam_prep_page_records import (
    PageExtraction,
    PageOption,
    PageRecord,
    assemble_page_extractions,
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
    assert any(issue.code == 'conflicting_correct_option' for issue in result.issues)


def test_answer_without_question_is_preserved_for_review():
    result = assemble_page_extractions(
        [PageExtraction(page_number=9, records=[_solution(12)])]
    )

    question = result.projection['exam_prep']['questions'][0]
    assert question['source_question_number'] == '12'
    assert question['question_text_markdown'] == ''
    assert 'missing_question_text' in question['issues']
    assert 'missing_options' in question['issues']
    assert 'missing_answer' not in question['issues']
    assert result.questions_needing_review == 1


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
