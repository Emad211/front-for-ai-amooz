import pytest

from apps.classes.services.exam_prep_utils import normalize_exam_prep_questions


pytestmark = pytest.mark.unit


def test_visual_question_keeps_blank_labeled_options_and_correct_answer():
    payload = {
        'exam_prep': {
            'questions': [
                {
                    'question_id': 'default-q-44',
                    'question_text_markdown': 'کدام نمودار صحیح است؟',
                    'options': [
                        {'label': '1', 'text_markdown': ''},
                        {'label': '2', 'text_markdown': ''},
                        {'label': '3', 'text_markdown': ''},
                        {'label': '4', 'text_markdown': ''},
                    ],
                    'correct_option_label': '2',
                    'visuals': [
                        {
                            'id': 'inline-default-q-44',
                            'role': 'question',
                            'dataUrl': 'data:image/jpeg;base64,AA==',
                        }
                    ],
                }
            ]
        }
    }

    normalized, changed = normalize_exam_prep_questions(payload)
    question = normalized['exam_prep']['questions'][0]

    assert changed is False
    assert [item['label'] for item in question['options']] == ['1', '2', '3', '4']
    assert [item['text_markdown'] for item in question['options']] == ['', '', '', '']
    assert question['correct_option_label'] == '2'
