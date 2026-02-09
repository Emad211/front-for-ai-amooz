"""Chat history service pagination tests.

Verifies that the paginated list_messages implementation returns bounded
results and supports cursor-based pagination.
"""
from __future__ import annotations

import pytest
from model_bakery import baker

from apps.classes.models import (
    ClassCreationSession,
    StudentCourseChatMessage,
    StudentCourseChatThread,
)
from apps.classes.services.student_chat_history import (
    append_message,
    get_or_create_thread,
    list_messages,
)
from apps.classes.services.student_exam_chat_history import (
    append_message as append_exam_message,
    get_or_create_thread as get_or_create_exam_thread,
    list_messages as list_exam_messages,
)


@pytest.mark.django_db
class TestCourseChatHistoryPagination:
    """Test paginated list_messages in student_chat_history service."""

    def _create_thread_with_messages(self, count: int):
        session = baker.make('classes.ClassCreationSession')
        student = baker.make('accounts.User', role='student')
        thread = get_or_create_thread(
            session=session, student_id=student.id, lesson_id='L1',
        )
        for i in range(count):
            append_message(
                thread=thread,
                role='user',
                message_type='text',
                content=f'Message {i}',
            )
        return session, student, thread

    def test_default_limit_caps_results(self):
        """Without explicit limit, list_messages returns at most 100 items."""
        session, student, thread = self._create_thread_with_messages(150)

        msgs = list_messages(
            session_id=session.id,
            student_id=student.id,
            lesson_id='L1',
        )

        assert len(msgs) == 100

    def test_custom_limit(self):
        session, student, thread = self._create_thread_with_messages(50)

        msgs = list_messages(
            session_id=session.id,
            student_id=student.id,
            lesson_id='L1',
            limit=10,
        )

        assert len(msgs) == 10

    def test_before_id_pagination(self):
        """Cursor-based pagination returns messages before a given ID."""
        session, student, thread = self._create_thread_with_messages(20)

        all_msgs = list_messages(
            session_id=session.id,
            student_id=student.id,
            lesson_id='L1',
            limit=20,
        )
        assert len(all_msgs) == 20

        # Get 5 messages before the 10th one.
        mid_id = all_msgs[10]['id']
        page = list_messages(
            session_id=session.id,
            student_id=student.id,
            lesson_id='L1',
            before_id=mid_id,
            limit=5,
        )

        assert len(page) == 5
        for msg in page:
            assert msg['id'] < mid_id

    def test_messages_ordered_ascending(self):
        session, student, thread = self._create_thread_with_messages(10)

        msgs = list_messages(
            session_id=session.id,
            student_id=student.id,
            lesson_id='L1',
        )

        ids = [m['id'] for m in msgs]
        assert ids == sorted(ids), 'Messages should be in ascending order'

    def test_empty_when_no_messages(self):
        session = baker.make('classes.ClassCreationSession')
        student = baker.make('accounts.User', role='student')

        msgs = list_messages(
            session_id=session.id,
            student_id=student.id,
        )

        assert msgs == []

    def test_filter_by_lesson_id(self):
        session = baker.make('classes.ClassCreationSession')
        student = baker.make('accounts.User', role='student')

        t1 = get_or_create_thread(session=session, student_id=student.id, lesson_id='L1')
        t2 = get_or_create_thread(session=session, student_id=student.id, lesson_id='L2')

        for _ in range(3):
            append_message(thread=t1, role='user', message_type='text', content='L1 msg')
        for _ in range(5):
            append_message(thread=t2, role='user', message_type='text', content='L2 msg')

        msgs_l1 = list_messages(
            session_id=session.id,
            student_id=student.id,
            lesson_id='L1',
        )
        msgs_l2 = list_messages(
            session_id=session.id,
            student_id=student.id,
            lesson_id='L2',
        )

        assert len(msgs_l1) == 3
        assert len(msgs_l2) == 5


@pytest.mark.django_db
class TestExamChatHistoryPagination:
    """Test paginated list_messages in student_exam_chat_history service."""

    def _create_thread_with_messages(self, count: int):
        session = baker.make('classes.ClassCreationSession')
        student = baker.make('accounts.User', role='student')
        thread = get_or_create_exam_thread(
            session=session, student_id=student.id, question_id='Q1',
        )
        for i in range(count):
            append_exam_message(
                thread=thread,
                role='user',
                message_type='text',
                content=f'Message {i}',
            )
        return session, student, thread

    def test_default_limit(self):
        session, student, thread = self._create_thread_with_messages(150)

        msgs = list_exam_messages(
            session_id=session.id,
            student_id=student.id,
            question_id='Q1',
        )

        assert len(msgs) == 100

    def test_before_id_pagination(self):
        session, student, thread = self._create_thread_with_messages(20)

        all_msgs = list_exam_messages(
            session_id=session.id,
            student_id=student.id,
            question_id='Q1',
            limit=20,
        )

        mid_id = all_msgs[10]['id']
        page = list_exam_messages(
            session_id=session.id,
            student_id=student.id,
            question_id='Q1',
            before_id=mid_id,
            limit=5,
        )

        assert len(page) == 5
        for msg in page:
            assert msg['id'] < mid_id


@pytest.mark.django_db
class TestGetOrCreateThread:
    """Test thread get_or_create without unnecessary locking."""

    def test_creates_new_thread(self):
        session = baker.make('classes.ClassCreationSession')
        student = baker.make('accounts.User', role='student')

        thread = get_or_create_thread(
            session=session, student_id=student.id, lesson_id='L1',
        )

        assert thread.pk is not None
        assert thread.session_id == session.id
        assert thread.student_id == student.id

    def test_get_existing_thread(self):
        session = baker.make('classes.ClassCreationSession')
        student = baker.make('accounts.User', role='student')

        t1 = get_or_create_thread(
            session=session, student_id=student.id, lesson_id='L1',
        )
        t2 = get_or_create_thread(
            session=session, student_id=student.id, lesson_id='L1',
        )

        assert t1.pk == t2.pk

    def test_no_unnecessary_update_on_get(self):
        """get_or_create_thread should NOT write updated_at on read."""
        session = baker.make('classes.ClassCreationSession')
        student = baker.make('accounts.User', role='student')

        t1 = get_or_create_thread(
            session=session, student_id=student.id, lesson_id='L1',
        )
        t1.refresh_from_db()
        original_updated = t1.updated_at

        # Second call should be a pure read.
        t2 = get_or_create_thread(
            session=session, student_id=student.id, lesson_id='L1',
        )
        t2.refresh_from_db()

        # updated_at should not have changed (auto_now only fires on save).
        assert t2.updated_at == original_updated
