import pytest

from apps.classes.services.exam_prep_question_cleanup import cleanup_assembled_question


pytestmark = pytest.mark.unit


def _options():
    return [
        {'label': '1', 'text_markdown': 'گزینه اول'},
        {'label': '2', 'text_markdown': 'گزینه دوم'},
        {'label': '3', 'text_markdown': 'گزینه سوم'},
        {'label': '4', 'text_markdown': 'گزینه چهارم'},
    ]


def test_repeated_number_and_options_are_removed_from_stem():
    question = {
        'question_id': 'default-q-25',
        'source_question_number': '25',
        'question_text_markdown': (
            '۲۵- در رابطه با یاخته‌ها کدام گزینه صحیح است؟\n'
            '1) گزینه اول\n'
            '2) گزینه دوم\n'
            '3) گزینه سوم\n'
            '4) گزینه چهارم'
        ),
        'options': _options(),
        'correct_option_label': '1',
        'teacher_solution_markdown': 'راه حل',
    }

    cleaned, changed = cleanup_assembled_question(question)

    assert changed is True
    assert cleaned['question_text_markdown'] == 'در رابطه با یاخته‌ها کدام گزینه صحیح است؟'
    assert cleaned['options'] == _options()
    assert cleaned['cleanup_metadata']['question_number_prefix_removed'] is True
    assert cleaned['cleanup_metadata']['duplicated_option_block_removed'] is True


def test_count_question_uses_numeric_choice_and_removes_answer_leak():
    question = {
        'question_id': 'default-q-50',
        'source_question_number': '50',
        'question_text_markdown': (
            'چند مورد درباره جانداران فتوسنتزکننده درست است؟\n\n'
            'موارد الف، ب و د درست هستند.\n\n'
            'الف) عبارت اول\n'
            'ب) عبارت دوم\n'
            'ج) عبارت سوم\n'
            'د) عبارت چهارم'
        ),
        'options': [],
        'correct_option_label': 'د',
        'teacher_solution_markdown': 'موارد الف، ب و د درست هستند.',
        'final_answer_markdown': '',
    }

    cleaned, changed = cleanup_assembled_question(question)

    assert changed is True
    assert 'موارد الف، ب و د درست هستند' not in cleaned['question_text_markdown']
    assert [item['label'] for item in cleaned['options']] == ['1', '2', '3', '4']
    assert cleaned['correct_option_label'] == '3'
    assert cleaned['cleanup_metadata']['inferred_true_statements'] == ['الف', 'ب', 'د']


def test_count_question_is_not_invented_without_explicit_answer_evidence():
    question = {
        'question_id': 'default-q-48',
        'source_question_number': '48',
        'question_text_markdown': (
            'چند مورد درست است؟\n'
            'الف) عبارت اول\n'
            'ب) عبارت دوم\n'
            'ج) عبارت سوم\n'
            'د) عبارت چهارم'
        ),
        'options': [],
        'correct_option_label': 'الف',
        'teacher_solution_markdown': 'توضیحی که تعداد موارد صحیح را مشخص نمی‌کند.',
    }

    cleaned, _changed = cleanup_assembled_question(question)

    assert cleaned['options'] == []
    assert cleaned['correct_option_label'] == 'الف'
    assert cleaned['cleanup_metadata']['inferred_true_statements'] == []
