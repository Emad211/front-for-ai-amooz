from __future__ import annotations

import pytest

from apps.classes.services import exam_prep_source_first as source_first
from apps.classes.services import exam_prep_v4_projection as projection
from apps.classes.services.exam_prep_v4_deployment_hardening import (
    _apply_source_option_labels,
    _direct_solution_option_map,
    merge_teacher_curated_projection,
)


def _payload() -> dict:
    return {
        'exam_prep': {
            'title': 'آزمون',
            'questions': [
                {
                    'question_id': 'v4-fixed-id',
                    'question_text_markdown': 'متن اولیه',
                    'type': 'multiple_choice',
                    'options': [
                        {'label': '1', 'text_markdown': 'الف'},
                        {'label': '2', 'text_markdown': 'ب'},
                    ],
                    'correct_option_label': '1',
                    'correct_option_text_markdown': 'الف',
                    'teacher_solution_markdown': 'راه حل اولیه',
                    'final_answer_markdown': '1',
                    'visuals': [
                        {
                            'id': 'v4-question-10',
                            'role': 'question',
                            'optionLabel': None,
                            'selectedVariant': 'source',
                            'url': '/api/classes/exam-prep-source-crops/7/question/10/',
                        },
                        {
                            'id': 'v4-solution-20',
                            'role': 'solution',
                            'optionLabel': None,
                            'selectedVariant': 'source',
                            'url': '/api/classes/exam-prep-source-crops/7/solution/20/',
                        },
                    ],
                }
            ],
        }
    }


def test_teacher_curation_changes_semantics_but_preserves_source_identity():
    generated = _payload()
    current = _payload()
    question = current['exam_prep']['questions'][0]
    question['question_text_markdown'] = 'متن اصلاح شده با $x^2$'
    question['options'][1]['text_markdown'] = 'گزینه ب اصلاح شد'
    question['correct_option_label'] = '2'
    question['teacher_solution_markdown'] = 'راه حل اصلاح شده'
    question['final_answer_markdown'] = '2'

    merged = merge_teacher_curated_projection(current, generated)
    result = merged['exam_prep']['questions'][0]

    assert result['question_id'] == 'v4-fixed-id'
    assert result['visuals'] == generated['exam_prep']['questions'][0]['visuals']
    assert [item['label'] for item in result['options']] == ['1', '2']
    assert result['question_text_markdown'] == 'متن اصلاح شده با $x^2$'
    assert result['options'][1]['text_markdown'] == 'گزینه ب اصلاح شد'
    assert result['correct_option_label'] == '2'
    assert result['correct_option_text_markdown'] == 'گزینه ب اصلاح شد'
    assert result['teacher_solution_markdown'] == 'راه حل اصلاح شده'


def test_teacher_curation_rejects_source_or_structure_mutation():
    generated = _payload()

    changed_id = _payload()
    changed_id['exam_prep']['questions'][0]['question_id'] = 'forged'
    with pytest.raises(projection.ProjectionIntegrityError):
        merge_teacher_curated_projection(changed_id, generated)

    changed_visual = _payload()
    changed_visual['exam_prep']['questions'][0]['visuals'][0]['url'] = '/forged'
    with pytest.raises(projection.ProjectionIntegrityError):
        merge_teacher_curated_projection(changed_visual, generated)

    changed_label = _payload()
    changed_label['exam_prep']['questions'][0]['options'][0]['label'] = '9'
    with pytest.raises(projection.ProjectionIntegrityError):
        merge_teacher_curated_projection(changed_label, generated)


def test_direct_solution_option_map_uses_only_structurally_safe_headings():
    analysis = {
        'pages': [
            {
                'regions': [
                    {
                        'kind': 'solution',
                        'questionNumber': 12,
                        'correctOptionLabel': 30,
                        'numberRecoveredFromSequence': False,
                        'issues': [],
                    },
                    {
                        'kind': 'solution',
                        'questionNumber': 13,
                        'correctOptionLabel': 20,
                        'numberRecoveredFromSequence': True,
                        'issues': [],
                    },
                    {
                        'kind': 'solution',
                        'questionNumber': 14,
                        'correctOptionLabel': 4,
                        'numberRecoveredFromSequence': False,
                        'issues': ['heading_sequence_gap'],
                    },
                ]
            }
        ]
    }

    assert _direct_solution_option_map(analysis) == {12: '3'}


def test_direct_solution_option_map_fails_closed_on_conflict():
    analysis = {
        'pages': [
            {
                'regions': [
                    {
                        'kind': 'solution',
                        'questionNumber': 8,
                        'correctOptionLabel': 2,
                        'numberRecoveredFromSequence': False,
                        'issues': [],
                    },
                    {
                        'kind': 'solution',
                        'questionNumber': 8,
                        'correctOptionLabel': 3,
                        'numberRecoveredFromSequence': False,
                        'issues': [],
                    },
                ]
            }
        ]
    }
    assert _direct_solution_option_map(analysis) == {}


def test_source_heading_repairs_only_numeric_answer_label_system():
    raw = {
        'answers': [
            {'printedNumber': '12', 'correctOption': '4', 'warnings': []},
            {'printedNumber': '13', 'correctOption': 'ب', 'warnings': []},
            {'printedNumber': '14', 'correctOption': None, 'warnings': []},
        ]
    }
    repaired = _apply_source_option_labels(raw, {12: '3', 13: '2', 14: '1'})

    assert repaired['answers'][0]['correctOption'] == '3'
    assert 'source_heading_correct_option_applied' in repaired['answers'][0]['warnings']
    assert repaired['answers'][1]['correctOption'] == 'ب'
    assert repaired['answers'][2]['correctOption'] == '1'


def test_startup_installs_release_hooks():
    assert projection.build_legacy_projection.__name__ == 'build_legacy_projection_with_teacher_curation'
    assert (
        source_first.MistralSourceFirstAdapter.extract_answer_solutions_batch.__name__
        == '_extract_answer_solutions_batch'
    )
