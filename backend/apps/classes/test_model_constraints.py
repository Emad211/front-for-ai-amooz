"""Model constraint and field validation tests.

Verifies UniqueConstraints, indexes, and field-level validation at the
database level — catching issues that ORM-only tests miss.
"""
from __future__ import annotations

import pytest
from django.db import IntegrityError
from model_bakery import baker

from apps.classes.models import (
    ClassAnnouncement,
    ClassCreationSession,
    ClassFinalExam,
    ClassInvitation,
    ClassPrerequisite,
    ClassSection,
    ClassSectionQuiz,
    ClassUnit,
    StudentExamPrepAttempt,
    StudentInviteCode,
    StudentCourseChatThread,
)


@pytest.mark.django_db
class TestClassCreationSessionConstraints:
    """Test unique constraint on (teacher, client_request_id)."""

    def test_unique_teacher_client_request_id(self):
        import uuid
        teacher = baker.make('accounts.User', role='teacher')
        crid = uuid.uuid4()
        baker.make(
            'classes.ClassCreationSession',
            teacher=teacher,
            client_request_id=crid,
        )
        with pytest.raises(IntegrityError):
            baker.make(
                'classes.ClassCreationSession',
                teacher=teacher,
                client_request_id=crid,
            )

    def test_different_teachers_same_client_request_id_ok(self):
        import uuid
        crid = uuid.uuid4()
        t1 = baker.make('accounts.User', role='teacher')
        t2 = baker.make('accounts.User', role='teacher')
        baker.make('classes.ClassCreationSession', teacher=t1, client_request_id=crid)
        # Different teacher — no conflict.
        s2 = baker.make('classes.ClassCreationSession', teacher=t2, client_request_id=crid)
        assert s2.pk is not None

    def test_status_choices_valid(self):
        valid = {c[0] for c in ClassCreationSession.Status.choices}
        assert 'transcribing' in valid
        assert 'failed' in valid
        assert 'exam_structured' in valid

    def test_pipeline_type_choices(self):
        valid = {c[0] for c in ClassCreationSession.PipelineType.choices}
        assert valid == {'class', 'exam_prep'}


@pytest.mark.django_db
class TestClassInvitationConstraints:
    """Test unique constraints and index presence on ClassInvitation."""

    def test_unique_session_phone(self):
        session = baker.make('classes.ClassCreationSession')
        ClassInvitation.objects.create(
            session=session, phone='09121111111', invite_code='A',
        )
        with pytest.raises(IntegrityError):
            ClassInvitation.objects.create(
                session=session, phone='09121111111', invite_code='B',
            )

    def test_unique_session_invite_code(self):
        session = baker.make('classes.ClassCreationSession')
        ClassInvitation.objects.create(
            session=session, phone='09121111111', invite_code='SAME',
        )
        with pytest.raises(IntegrityError):
            ClassInvitation.objects.create(
                session=session, phone='09122222222', invite_code='SAME',
            )

    def test_different_sessions_same_phone_ok(self):
        s1 = baker.make('classes.ClassCreationSession')
        s2 = baker.make('classes.ClassCreationSession')
        ClassInvitation.objects.create(session=s1, phone='09121111111', invite_code='A')
        inv2 = ClassInvitation.objects.create(session=s2, phone='09121111111', invite_code='B')
        assert inv2.pk is not None

    def test_phone_field_has_db_index(self):
        """Verify the phone field has db_index=True for fast lookups."""
        field = ClassInvitation._meta.get_field('phone')
        assert field.db_index is True

    def test_invite_code_field_has_db_index(self):
        field = ClassInvitation._meta.get_field('invite_code')
        assert field.db_index is True


@pytest.mark.django_db
class TestStudentInviteCodeConstraints:
    """Test uniqueness of phone and code on StudentInviteCode."""

    def test_unique_phone(self):
        StudentInviteCode.objects.create(phone='09121111111', code='ABC')
        with pytest.raises(IntegrityError):
            StudentInviteCode.objects.create(phone='09121111111', code='DEF')

    def test_unique_code(self):
        StudentInviteCode.objects.create(phone='09121111111', code='ABC')
        with pytest.raises(IntegrityError):
            StudentInviteCode.objects.create(phone='09122222222', code='ABC')


@pytest.mark.django_db
class TestExamPrepAttemptConstraints:
    """Test unique constraint on (session, student) for exam prep attempts."""

    def test_unique_session_student(self):
        session = baker.make('classes.ClassCreationSession')
        student = baker.make('accounts.User', role='student')
        StudentExamPrepAttempt.objects.create(session=session, student=student)
        with pytest.raises(IntegrityError):
            StudentExamPrepAttempt.objects.create(session=session, student=student)


@pytest.mark.django_db
class TestChatThreadConstraints:
    """Test unique constraint on (session, student, lesson_id)."""

    def test_unique_thread_key(self):
        session = baker.make('classes.ClassCreationSession')
        student = baker.make('accounts.User', role='student')
        StudentCourseChatThread.objects.create(
            session=session,
            student=student,
            lesson_id='L1',
            thread_key='course-chat:1:L1:1',
        )
        with pytest.raises(IntegrityError):
            StudentCourseChatThread.objects.create(
                session=session,
                student=student,
                lesson_id='L1',
                thread_key='course-chat:1:L1:1',
            )

    def test_different_lessons_same_student_ok(self):
        session = baker.make('classes.ClassCreationSession')
        student = baker.make('accounts.User', role='student')
        t1 = StudentCourseChatThread.objects.create(
            session=session, student=student,
            lesson_id='L1', thread_key=f'course-chat:{session.id}:L1:{student.id}',
        )
        t2 = StudentCourseChatThread.objects.create(
            session=session, student=student,
            lesson_id='L2', thread_key=f'course-chat:{session.id}:L2:{student.id}',
        )
        assert t1.pk != t2.pk


@pytest.mark.django_db
class TestSectionQuizConstraints:
    """Test unique constraint on (session, section, student)."""

    def test_unique_session_section_student(self):
        session = baker.make('classes.ClassCreationSession')
        section = baker.make('classes.ClassSection', session=session, order=1)
        student = baker.make('accounts.User', role='student')

        ClassSectionQuiz.objects.create(
            session=session, section=section, student=student,
        )
        with pytest.raises(IntegrityError):
            ClassSectionQuiz.objects.create(
                session=session, section=section, student=student,
            )


@pytest.mark.django_db
class TestFinalExamConstraints:
    """Test unique constraint on (session, student)."""

    def test_unique_session_student(self):
        session = baker.make('classes.ClassCreationSession')
        student = baker.make('accounts.User', role='student')
        ClassFinalExam.objects.create(session=session, student=student)
        with pytest.raises(IntegrityError):
            ClassFinalExam.objects.create(session=session, student=student)


@pytest.mark.django_db
class TestModelIndexPresence:
    """Verify that critical fields have db_index for performance."""

    def test_session_status_indexed(self):
        field = ClassCreationSession._meta.get_field('status')
        assert field.db_index is True

    def test_session_is_published_indexed(self):
        field = ClassCreationSession._meta.get_field('is_published')
        assert field.db_index is True

    def test_session_pipeline_type_indexed(self):
        field = ClassCreationSession._meta.get_field('pipeline_type')
        assert field.db_index is True

    def test_session_published_at_indexed(self):
        field = ClassCreationSession._meta.get_field('published_at')
        assert field.db_index is True

    def test_composite_index_on_session(self):
        """Verify composite index exists for student list queries."""
        index_names = [idx.name for idx in ClassCreationSession._meta.indexes]
        assert any('pub_type_pubat' in name for name in index_names), (
            f'Expected composite index, found: {index_names}'
        )
