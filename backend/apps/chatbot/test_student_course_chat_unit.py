import json

import pytest
from model_bakery import baker

from apps.classes.models import ClassCreationSession
from apps.accounts.models import User


@pytest.mark.django_db
class TestStudentCourseChatUnitRouting:
    def _make_session(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        return baker.make(ClassCreationSession, teacher=teacher, title='Course', description='D')

    def test_empty_message_returns_error_text(self):
        from apps.chatbot.services.student_course_chat import handle_student_message

        session = self._make_session()
        resp = handle_student_message(session=session, student_id=1, lesson_id=None, user_message='   ')
        assert resp['type'] == 'text'
        assert 'خالیه' in resp['content']

    def test_system_unit_start_returns_intro_and_default_suggestions(self, monkeypatch):
        from apps.chatbot.services import student_course_chat as sc

        session = self._make_session()

        monkeypatch.setattr(sc, 'generate_text', lambda *, contents, model=None: type('R', (), {'text': 'INTRO'})())

        resp = sc.handle_student_message(session=session, student_id=1, lesson_id='1', user_message='SYSTEM_UNIT_START:Unit')
        assert resp['type'] == 'text'
        # SYSTEM_UNIT_START now silently acknowledges context (no intro generated).
        assert resp['content'] == ''
        assert resp['suggestions'] == []

    def test_system_tool_maps_to_widget(self, monkeypatch):
        from apps.chatbot.services import student_course_chat as sc

        session = self._make_session()

        monkeypatch.setattr(sc, 'generate_json', lambda *, feature, contents: {'ok': True, 'feature': feature})

        resp = sc.handle_student_message(session=session, student_id=1, lesson_id=None, user_message='SYSTEM_TOOL:flash_cards')
        assert resp['type'] == 'widget'
        assert resp['widget_type'] == 'flashcard'

    def test_intent_routes_to_quiz_widget(self, monkeypatch):
        from apps.chatbot.services import student_course_chat as sc

        session = self._make_session()

        def _fake_generate_json(*, feature, contents):
            if feature == 'chat_intent':
                return {'intent': 'request_quiz'}
            return {'questions': [{'question': 'q1', 'options': ['a', 'b'], 'answer': 'a'}]}

        monkeypatch.setattr(sc, 'generate_json', _fake_generate_json)

        resp = sc.handle_student_message(session=session, student_id=1, lesson_id=None, user_message='کوئیز بده')
        assert resp['type'] == 'widget'
        assert resp['widget_type'] == 'quiz'
        assert 'data' in resp

    def test_intent_routes_to_flashcard_widget(self, monkeypatch):
        from apps.chatbot.services import student_course_chat as sc

        session = self._make_session()

        def _fake_generate_json(*, feature, contents):
            if feature == 'chat_intent':
                return {'intent': 'request_flashcard'}
            return {'flashcards': [{'front': 'f', 'back': 'b'}]}

        monkeypatch.setattr(sc, 'generate_json', _fake_generate_json)

        resp = sc.handle_student_message(session=session, student_id=1, lesson_id=None, user_message='فلش کارت بده')
        assert resp['type'] == 'widget'
        assert resp['widget_type'] == 'flashcard'

    def test_intent_routes_to_match_game_widget(self, monkeypatch):
        from apps.chatbot.services import student_course_chat as sc

        session = self._make_session()

        def _fake_generate_json(*, feature, contents):
            if feature == 'chat_intent':
                return {'intent': 'request_match_game'}
            return {'pairs': [{'term': 't', 'definition': 'd'}]}

        monkeypatch.setattr(sc, 'generate_json', _fake_generate_json)

        resp = sc.handle_student_message(session=session, student_id=1, lesson_id=None, user_message='بازی تطبیق بده')
        assert resp['type'] == 'widget'
        assert resp['widget_type'] == 'match_game'

    def test_default_intent_uses_chat_system_prompt_and_returns_text(self, monkeypatch):
        from apps.chatbot.services import student_course_chat as sc

        session = self._make_session()

        def _fake_generate_json(*, feature, contents):
            if feature == 'chat_intent':
                return {'intent': 'ask_question'}
            if feature == 'chat_system_prompt':
                return {'content': 'ANSWER', 'suggestions': ['s1', 's2']}
            return {}

        monkeypatch.setattr(sc, 'generate_json', _fake_generate_json)

        resp = sc.handle_student_message(session=session, student_id=1, lesson_id=None, user_message='سوال')
        assert resp['type'] == 'text'
        assert resp['content'] == 'ANSWER'
        assert resp['suggestions'] == ['s1', 's2']

    def test_page_material_overrides_unit_content_in_prompt(self, monkeypatch):
        from apps.chatbot.services import student_course_chat as sc

        session = self._make_session()
        captured = {'prompt': ''}

        def _fake_generate_json(*, feature, contents):
            if feature == 'chat_intent':
                return {'intent': 'ask_question'}
            if feature == 'chat_system_prompt':
                captured['prompt'] = str(contents)
                return {'content': 'OK', 'suggestions': []}
            return {}

        monkeypatch.setattr(sc, 'generate_json', _fake_generate_json)

        resp = sc.handle_student_message(
            session=session,
            student_id=1,
            lesson_id=None,
            user_message='سوال',
            page_context='CTX',
            page_material='MATERIAL',
        )
        assert resp['type'] == 'text'
        assert 'CTX' in captured['prompt']
        assert 'MATERIAL' in captured['prompt']


@pytest.mark.django_db
class TestToolPromptTokenReplacement:
    def _make_session(self):
        teacher = baker.make(User, role=User.Role.TEACHER)
        return baker.make(ClassCreationSession, teacher=teacher, title='Course', description='D')

    def test_structured_blocks_token_is_replaced(self, monkeypatch):
        from apps.chatbot.services import student_course_chat as sc

        session = self._make_session()

        # Override prompt template for a single tool.
        monkeypatch.setitem(sc.PROMPTS['flash_cards'], 'standard_qa', 'STRUCTURED_BLOCKS_JSON')

        captured = {'contents': ''}

        def _fake_generate_json(*, feature, contents):
            captured['contents'] = str(contents)
            return {'flashcards': []}

        monkeypatch.setattr(sc, 'generate_json', _fake_generate_json)

        resp = sc.handle_system_tool(session=session, student_id=1, lesson_id=None, tool='flash_cards')
        assert resp['type'] == 'widget'
        assert resp['widget_type'] == 'flashcard'
        # Should contain JSON, not the literal token.
        assert 'STRUCTURED_BLOCKS_JSON' not in captured['contents']
        assert '"outline"' in captured['contents']

    def test_placeholder_format_is_applied(self, monkeypatch):
        from apps.chatbot.services import student_course_chat as sc

        session = self._make_session()

        monkeypatch.setitem(sc.PROMPTS['fetch_quizzes'], 'multiple_choice', 'COUNT={num_questions}')

        captured = {'contents': ''}

        def _fake_generate_json(*, feature, contents):
            captured['contents'] = str(contents)
            return {'questions': []}

        monkeypatch.setattr(sc, 'generate_json', _fake_generate_json)

        resp = sc.handle_system_tool(session=session, student_id=1, lesson_id=None, tool='fetch_quizzes')
        assert resp['type'] == 'widget'
        assert resp['widget_type'] == 'quiz'
        assert 'COUNT=3' in captured['contents']
