import json

import pytest
from model_bakery import baker

from apps.accounts.models import User
from apps.classes.models import ClassCreationSession


@pytest.mark.django_db
class TestStudentExamPrepChatDoesNotLeakCorrectAnswer:
    def _make_exam_prep_session(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        session = baker.make(
            ClassCreationSession,
            teacher=teacher,
            title='Exam Prep',
            description='D',
            is_published=True,
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        )
        session.exam_prep_json = json.dumps(
            {
                'exam_prep': {
                    'questions': [
                        {
                            'question_id': 'q1',
                            'question_text_markdown': 'Q1',
                            'options': [
                                {'label': 'الف', 'text_markdown': '1'},
                                {'label': 'ب', 'text_markdown': '2'},
                            ],
                            'correct_option_label': 'ب',
                            'teacher_solution_markdown': 'SOLUTION: answer is ب',
                        }
                    ]
                }
            },
            ensure_ascii=False,
        )
        session.save(update_fields=['exam_prep_json'])
        return session

    def test_build_exam_question_context_never_includes_correct_answer(self):
        from apps.chatbot.services.student_exam_prep_chat import build_exam_question_context

        session = self._make_exam_prep_session()

        ctx_checked = build_exam_question_context(session=session, question_id='q1', is_checked=True)
        ctx_unchecked = build_exam_question_context(session=session, question_id='q1', is_checked=False)

        # Should never include any explicit "correct answer" fields/markers.
        assert 'Correct Answer' not in ctx_checked
        assert 'correct_option_label' not in ctx_checked
        assert 'teacher_solution' not in ctx_checked
        assert 'SOLUTION: answer is ب' not in ctx_checked

        assert 'Correct Answer' not in ctx_unchecked
        assert 'SOLUTION: answer is ب' not in ctx_unchecked

        # Still includes the question/options context.
        assert 'Question:' in ctx_checked
        assert 'Options:' in ctx_checked

    def test_handle_exam_prep_message_prompt_does_not_contain_correct_answer(self, monkeypatch):
        from apps.chatbot.services import student_exam_prep_chat as se

        session = self._make_exam_prep_session()
        captured = {'prompt': ''}

        def _fake_generate_json(*, feature, contents):
            captured['prompt'] = str(contents)
            return {'content': 'OK', 'suggestions': []}

        monkeypatch.setattr(se, 'generate_json', _fake_generate_json)

        resp = se.handle_exam_prep_message(
            session=session,
            student_id=1,
            question_id='q1',
            user_message='می‌خوام چک کنم',
            student_selected='الف',
            is_checked=True,
            is_correct=False,
        )

        assert resp['type'] == 'text'
        assert resp['content'] == 'OK'

        # Prompt must not contain correct answer/solution, even when checked.
        assert 'Correct Answer' not in captured['prompt']
        assert 'SOLUTION: answer is ب' not in captured['prompt']
        # Also avoid leaking the correct label explicitly.
        assert 'answer is ب' not in captured['prompt']
