import pytest

from apps.classes.services import exam_prep_question_verifier as verifier
from apps.classes.services.exam_prep_page_extractor import RenderedExamPage
from apps.classes.services.exam_prep_page_records import (
    PageExtraction,
    PageOption,
    PageRecord,
    assemble_page_extractions,
)


pytestmark = pytest.mark.unit


def _question_dict(*, solution=''):
    return {
        'question_id': 'default-q-17',
        'scope_key': 'default',
        'section_key': 'default',
        'source_question_number': '17',
        'question_text_markdown': 'در ارتباط با تولید انسولین کدام گزینه صحیح است؟',
        'options': [
            {'label': '1', 'text_markdown': 'متن یک'},
            {'label': '2', 'text_markdown': 'متن دو'},
            {'label': '3', 'text_markdown': 'متن سه'},
            {'label': '4', 'text_markdown': 'متن چهار'},
        ],
        'correct_option_label': '4',
        'teacher_solution_markdown': solution,
        'final_answer_markdown': 'گزینه ۴',
        'confidence': 0.8,
        'issues': [],
        'source_pages': [4, 11],
    }


def test_broken_persian_and_missing_solution_are_repairable():
    question = _question_dict()
    question['question_text_markdown'] = '؟ﺖﺳا ﺢﻴﺤﺻ ﻪﻨﻳﺰﮔ ماﺪﻛ'
    question['issues'] = ['missing_solution_text']

    issues = verifier.canonical_question_issues(question)

    assert 'broken_persian_text' in issues
    assert 'missing_solution_text' in issues
    assert verifier.question_needs_targeted_repair(question) is True


def test_unrelated_long_solution_is_marked_as_mismatch_candidate():
    question = _question_dict(
        solution=(
            'عامل بیماری ایدز نوعی ویروس است و یاخته‌های دستگاه ایمنی و '
            'لنفوسیت کمک‌کننده را آلوده می‌کند. تشخیص افراد آلوده پیش از بروز '
            'علائم با بررسی ماده وراثتی ویروس انجام می‌شود و واکسن مؤثری ندارد.'
        )
    )

    assert verifier.solution_mismatch_candidate(question) is True
    assert 'solution_semantic_mismatch_candidate' in verifier.canonical_question_issues(question)


def test_targeted_repair_updates_only_suspicious_question(monkeypatch):
    page = PageExtraction(
        page_number=4,
        records=[
            PageRecord(
                question_number=17,
                record_type='question_answer',
                question_text_markdown='در ارتباط با تولید انسولین کدام گزینه صحیح است؟',
                options=[
                    PageOption(label='1', text_markdown='متن یک'),
                    PageOption(label='2', text_markdown='متن دو'),
                    PageOption(label='3', text_markdown='متن سه'),
                    PageOption(label='4', text_markdown='متن چهار'),
                ],
                correct_option_label='4',
                confidence=0.8,
                issues=['missing_solution_text'],
            )
        ],
    )
    assembled = assemble_page_extractions([page], title='آزمون')
    source = RenderedExamPage(
        page_number=4,
        image=b'\x89PNG\r\nsource',
        native_text='متن منبع',
    )
    monkeypatch.setattr(
        verifier,
        'verify_and_repair_question',
        lambda *_args, **_kwargs: verifier.VerifiedQuestionRepair(
            question_number=17,
            source_supported=True,
            question_text_markdown='در ارتباط با تولید انسولین کدام گزینه صحیح است؟',
            options=[
                PageOption(label='1', text_markdown='متن یک'),
                PageOption(label='2', text_markdown='متن دو'),
                PageOption(label='3', text_markdown='متن سه'),
                PageOption(label='4', text_markdown='متن چهار'),
            ],
            correct_option_label='4',
            teacher_solution_markdown='راه‌حل کامل و مرتبط با تولید زنجیره‌های A و B انسولین.',
            final_answer_markdown='گزینه ۴',
            confidence=0.95,
        ),
    )

    repaired, stats = verifier.repair_suspicious_questions(
        assembled,
        source_pages_by_number={4: source},
        model='fake-model',
    )

    question = repaired.projection['exam_prep']['questions'][0]
    assert stats == {'attempted': 1, 'repaired': 1, 'unresolved': 0}
    assert question['teacher_solution_markdown'].startswith('راه‌حل کامل')
    assert 'missing_solution_text' not in question['issues']
    assert question['source_verified'] is True
