import io

import pytest
from PIL import Image

from apps.classes.services import exam_prep_question_full_verifier as verifier
from apps.classes.services.exam_prep_page_extractor import RenderedExamPage
from apps.classes.services.exam_prep_page_records import (
    PageOption,
    assemble_page_extractions,
)
from apps.classes.services.exam_prep_page_source import (
    SourceBBox,
    SourcePageExtraction,
    SourcePageRecord,
    attach_source_regions,
)


pytestmark = pytest.mark.unit


def _png():
    image = Image.new('RGB', (800, 1000), 'white')
    output = io.BytesIO()
    image.save(output, format='PNG')
    image.close()
    return output.getvalue()


def _result():
    question_page = SourcePageExtraction(
        page_number=2,
        records=[
            SourcePageRecord(
                question_number=1,
                record_type='question',
                source_bbox=SourceBBox(x0=0.05, y0=0.1, x1=0.95, y1=0.55),
                question_text_markdown='۱- کدام گزینه درست است؟',
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
    answer_page = SourcePageExtraction(
        page_number=9,
        records=[
            SourcePageRecord(
                question_number=1,
                record_type='solution',
                source_bbox=SourceBBox(x0=0.52, y0=0.12, x1=0.98, y1=0.6),
                correct_option_label='2',
                teacher_solution_markdown='راه حل تشریحی کامل و مرتبط با سؤال.',
                confidence=0.9,
            )
        ],
    )
    result = assemble_page_extractions([question_page, answer_page], title='آزمون')
    return attach_source_regions(result, pages=[question_page, answer_page])


def _pages():
    image = _png()
    return {
        2: RenderedExamPage(page_number=2, image=image, native_text='متن سؤال'),
        9: RenderedExamPage(page_number=9, image=image, native_text='متن پاسخ'),
    }


def _audit(*, match=True, visual=False, table=False, table_complete=True, solution='راه حل تشریحی کامل و مرتبط با سؤال.'):
    return verifier.VerifiedQuestionAudit(
        question_number=1,
        source_supported=True,
        fields_match_source=match,
        question_text_markdown='کدام گزینه درست است؟',
        options=[
            PageOption(label='1', text_markdown='گزینه اول'),
            PageOption(label='2', text_markdown='گزینه دوم'),
            PageOption(label='3', text_markdown='گزینه سوم'),
            PageOption(label='4', text_markdown='گزینه چهارم'),
        ],
        correct_option_label='2',
        teacher_solution_markdown=solution,
        final_answer_markdown='گزینه ۲',
        visual_required=visual,
        table_required=table,
        table_complete=table_complete,
        confidence=0.96,
    )


def test_every_question_is_verified_using_question_and_answer_crops(monkeypatch):
    calls = []

    def fake_verify(question, *, crops, model, attempt):
        calls.append((question, crops, model, attempt))
        return _audit()

    monkeypatch.setattr(verifier, 'verify_question_once', fake_verify)

    result, stats = verifier.verify_all_questions(
        _result(),
        source_pages_by_number=_pages(),
        model='fake-model',
    )

    assert stats['attempted'] == 1
    assert stats['verified'] == 1
    assert stats['unresolved'] == 0
    assert len(calls) == 1
    assert [(crop.page_number, crop.role) for crop in calls[0][1]] == [
        (2, 'question'),
        (9, 'answer'),
    ]
    question = result.projection['exam_prep']['questions'][0]
    assert question['source_verified'] is True
    assert question['question_text_markdown'] == 'کدام گزینه درست است؟'
    assert question['issues'] == []


def test_mismatch_is_corrected_and_verified_once_more(monkeypatch):
    calls = []
    audits = [
        _audit(match=False, solution='راه حل اصلاح شده از روی منبع.'),
        _audit(match=True, solution='راه حل اصلاح شده از روی منبع.'),
    ]

    def fake_verify(question, *, crops, model, attempt):
        calls.append((attempt, question['teacher_solution_markdown']))
        return audits.pop(0)

    monkeypatch.setattr(verifier, 'verify_question_once', fake_verify)

    result, stats = verifier.verify_all_questions(
        _result(),
        source_pages_by_number=_pages(),
        model='fake-model',
    )

    assert [item[0] for item in calls] == [1, 2]
    assert stats['retried'] == 1
    assert stats['verified'] == 1
    assert stats['unresolved'] == 0
    question = result.projection['exam_prep']['questions'][0]
    assert question['teacher_solution_markdown'] == 'راه حل اصلاح شده از روی منبع.'
    assert question['source_verified'] is True


def test_visual_question_attaches_source_crop_and_does_not_keep_fake_graph_text(monkeypatch):
    visual_audit = _audit(visual=True)
    visual_audit.options = [
        PageOption(label='1', text_markdown='Graph 1'),
        PageOption(label='2', text_markdown='Graph 2'),
        PageOption(label='3', text_markdown='Graph 3'),
        PageOption(label='4', text_markdown='Graph 4'),
    ]
    monkeypatch.setattr(
        verifier,
        'verify_question_once',
        lambda *_args, **_kwargs: visual_audit,
    )

    result, stats = verifier.verify_all_questions(
        _result(),
        source_pages_by_number=_pages(),
        model='fake-model',
    )

    question = result.projection['exam_prep']['questions'][0]
    assert stats['visuals_attached'] == 1
    assert question['visuals'][0]['id'].startswith('inline-')
    assert question['visuals'][0]['dataUrl'].startswith('data:image/jpeg;base64,')
    assert [item['text_markdown'] for item in question['options']] == ['', '', '', '']
    assert 'visual_attachment_missing' not in question['issues']
    assert 'missing_option_text' not in question['issues']


def test_incomplete_table_remains_publication_blocking(monkeypatch):
    monkeypatch.setattr(
        verifier,
        'verify_question_once',
        lambda *_args, **_kwargs: _audit(table=True, table_complete=False),
    )

    result, _stats = verifier.verify_all_questions(
        _result(),
        source_pages_by_number=_pages(),
        model='fake-model',
    )

    question = result.projection['exam_prep']['questions'][0]
    assert 'table_incomplete' in question['issues']
    assert result.publication_ready is False
