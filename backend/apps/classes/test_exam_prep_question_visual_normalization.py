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

    normalized, _changed = normalize_exam_prep_questions(payload)
    question = normalized['exam_prep']['questions'][0]

    assert [item['label'] for item in question['options']] == ['1', '2', '3', '4']
    assert [item['text_markdown'] for item in question['options']] == ['', '', '', '']
    assert question['correct_option_label'] == '2'


def test_empty_text_question_with_question_visual_is_kept():
    """A teacher-edit save must not delete an image-only OCR question.

    Regression: uploading a stem image to one question and saving ran
    ``normalize_exam_prep_question`` which dropped every question whose
    extracted text was empty - wiping whole image-based questions (and their
    visuals) from the exam on the next save.
    """
    payload = {
        'exam_prep': {
            'questions': [
                {
                    'question_id': 'img-q-1',
                    'question_text_markdown': '',
                    'options': [],
                    'correct_option_label': None,
                    'visuals': [
                        {
                            'id': 'teacher-abc',
                            'role': 'question',
                            'url': '/api/classes/exam-prep-sessions/9/visuals/teacher/abc.jpg/content/',
                        }
                    ],
                }
            ]
        }
    }

    normalized, changed = normalize_exam_prep_questions(payload)
    questions = normalized['exam_prep']['questions']

    assert len(questions) == 1
    assert questions[0]['question_id'] == 'img-q-1'
    assert [item['role'] for item in questions[0]['visuals']] == ['question']
    assert changed is True


def test_empty_text_question_without_visual_is_still_dropped():
    payload = {
        'exam_prep': {
            'questions': [
                {
                    'question_id': 'empty-q-1',
                    'question_text_markdown': '   ',
                    'options': [],
                }
            ]
        }
    }

    normalized, _changed = normalize_exam_prep_questions(payload)

    assert normalized['exam_prep']['questions'] == []

