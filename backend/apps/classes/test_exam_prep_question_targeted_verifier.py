import io

import pytest
from PIL import Image

from apps.classes.services import exam_prep_question_targeted_verifier as verifier
from apps.classes.services.exam_prep_page_extractor import RenderedExamPage
from apps.classes.services.exam_prep_page_records import PageOption, assemble_page_extractions
from apps.classes.services.exam_prep_page_source import (
    SourceBBox,
    SourcePageExtraction,
    SourcePageRecord,
    attach_source_regions,
)
from apps.classes.services.exam_prep_question_verifier import rebuild_assembly_quality


pytestmark = pytest.mark.unit


def _png():
    image = Image.new('RGB', (800, 1000), 'white')
    output = io.BytesIO()
    image.save(output, format='PNG')
    image.close()
    return output.getvalue()


def _question_record(number, *, page_number):
    return SourcePageExtraction(
        page_number=page_number,
        records=[
            SourcePageRecord(
                question_number=number,
                record_type='question',
                source_bbox=SourceBBox(x0=0.05, y0=0.1, x1=0.95, y1=0.55),
                question_text_markdown=f'کدام گزینه درباره سؤال {number} درست است؟',
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


def _answer_record(number, *, page_number, solution):
    return SourcePageExtraction(
        page_number=page_number,
        records=[
            SourcePageRecord(
                question_number=number,
                record_type='solution',
                source_bbox=SourceBBox(x0=0.52, y0=0.12, x1=0.98, y1=0.6),
                correct_option_label='2',
                teacher_solution_markdown=solution,
                confidence=0.9,
            )
        ],
    )


def _result(*, suspicious=False, two_questions=False):
    pages = [
        _question_record(1, page_number=2),
        _answer_record(1, page_number=9, solution='راه حل تشریحی کامل و مرتبط با سؤال اول.'),
    ]
    if two_questions:
        pages.extend(
            [
                _question_record(2, page_number=3),
                _answer_record(
                    2,
                    page_number=10,
                    solution='راه حل تشریحی کامل و مرتبط با سؤال دوم.',
                ),
            ]
        )
    result = assemble_page_extractions(pages, title='آزمون')
    result = attach_source_regions(result, pages=pages)
    result = rebuild_assembly_quality(result)
    if suspicious:
        projection = dict(result.projection)
        exam = dict(projection['exam_prep'])
        questions = [dict(item) for item in exam['questions']]
        target_index = 1 if two_questions else 0
        questions[target_index]['teacher_solution_markdown'] = ''
        questions[target_index]['issues'] = ['missing_solution_text']
        exam['questions'] = questions
        projection['exam_prep'] = exam
        result = result.model_copy(update={'projection': projection})
    return result


def _pages():
    image = _png()
    return {
        number: RenderedExamPage(
            page_number=number,
            image=image,
            native_text=f'متن منبع صفحه {number}',
        )
        for number in (2, 3, 9, 10)
    }


def _audit(*, match=True):
    return verifier.VerifiedQuestionAudit(
        question_number=1,
        source_supported=True,
        fields_match_source=match,
        question_text_markdown='کدام گزینه درباره سؤال 1 درست است؟',
        options=[
            PageOption(label='1', text_markdown='گزینه اول'),
            PageOption(label='2', text_markdown='گزینه دوم'),
            PageOption(label='3', text_markdown='گزینه سوم'),
            PageOption(label='4', text_markdown='گزینه چهارم'),
        ],
        correct_option_label='2',
        teacher_solution_markdown='راه حل تشریحی کامل و اصلاح‌شده از روی منبع.',
        final_answer_markdown='گزینه ۲',
        confidence=0.96,
    )


def test_clean_question_makes_no_provider_call(monkeypatch):
    monkeypatch.setattr(
        verifier,
        '_verify_question_once',
        lambda *_args, **_kwargs: pytest.fail('clean question must not call provider'),
    )

    result, stats = verifier.verify_suspicious_questions(
        _result(),
        source_pages_by_number=_pages(),
        model='fake-model',
    )

    question = result.projection['exam_prep']['questions'][0]
    assert stats['attempted'] == 0
    assert stats['retried'] == 0
    assert question['verification_metadata']['required'] is False
    assert 'source_verification_failed' not in question['issues']
    assert result.publication_ready is True


def test_suspicious_question_gets_exactly_one_call_and_can_be_repaired(monkeypatch):
    calls = []

    def fake_verify(question, *, crops, model):
        calls.append((question, crops, model))
        return _audit(match=False)

    monkeypatch.setattr(verifier, '_verify_question_once', fake_verify)

    result, stats = verifier.verify_suspicious_questions(
        _result(suspicious=True),
        source_pages_by_number=_pages(),
        model='fake-model',
    )

    question = result.projection['exam_prep']['questions'][0]
    assert len(calls) == 1
    assert stats['attempted'] == 1
    assert stats['retried'] == 0
    assert stats['verified'] == 1
    assert question['source_verified'] is True
    assert question['teacher_solution_markdown'].startswith('راه حل تشریحی کامل')
    assert 'missing_solution_text' not in question['issues']


def test_provider_failure_is_not_retried(monkeypatch):
    calls = []

    def fail_once(*_args, **_kwargs):
        calls.append(1)
        raise RuntimeError('provider failed')

    monkeypatch.setattr(verifier, '_verify_question_once', fail_once)

    result, stats = verifier.verify_suspicious_questions(
        _result(suspicious=True),
        source_pages_by_number=_pages(),
        model='fake-model',
    )

    question = result.projection['exam_prep']['questions'][0]
    assert len(calls) == 1
    assert stats['attempted'] == 1
    assert stats['retried'] == 0
    assert stats['unresolved'] == 1
    assert 'source_verification_failed' in question['issues']


def test_only_suspicious_question_pages_are_rerendered():
    result = _result(suspicious=True, two_questions=True)

    assert verifier.targeted_source_page_numbers(result) == {3, 10}
