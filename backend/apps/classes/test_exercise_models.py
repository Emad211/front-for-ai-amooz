"""E1 — Exercise Hub models: constraints, FK on_delete, defaults, reveal helper.

Design: docs/features/exercise-hub.md. Pure model tests (unit), no LLM/API.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone
from model_bakery import baker

from apps.accounts.models import User
from apps.classes.models import (
    ClassCreationSession,
    ClassExercise,
    ClassExerciseAsset,
    ClassExerciseQuestion,
    ClassExerciseSection,
    StudentExerciseSubmission,
)

pytestmark = [pytest.mark.django_db, pytest.mark.unit]


class TestDefaults:
    def test_exercise_sane_defaults(self):
        ex = baker.make(ClassExercise)
        assert ex.status == ClassExercise.Status.DRAFT
        assert ex.assistant_enabled is True
        assert ex.allow_late is False
        assert ex.deadline is None

    def test_section_and_question_defaults(self):
        sec = baker.make(ClassExerciseSection)
        assert sec.assistant_enabled is True
        q = baker.make(ClassExerciseQuestion, section=sec)
        assert q.question_type == ClassExerciseQuestion.QuestionType.DESCRIPTIVE
        assert q.options == []

    def test_submission_defaults(self):
        sub = baker.make(StudentExerciseSubmission)
        assert sub.status == StudentExerciseSubmission.Status.SUBMITTED
        assert sub.answers == {} and sub.result == {}
        assert sub.is_late is False


class TestConstraints:
    def test_unique_section_order_per_exercise(self):
        ex = baker.make(ClassExercise)
        baker.make(ClassExerciseSection, exercise=ex, order=1)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                baker.make(ClassExerciseSection, exercise=ex, order=1)

    def test_same_order_allowed_across_exercises(self):
        ex1, ex2 = baker.make(ClassExercise), baker.make(ClassExercise)
        baker.make(ClassExerciseSection, exercise=ex1, order=1)
        sec2 = baker.make(ClassExerciseSection, exercise=ex2, order=1)
        assert sec2.pk is not None

    def test_unique_question_order_per_section(self):
        sec = baker.make(ClassExerciseSection)
        baker.make(ClassExerciseQuestion, section=sec, order=1)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                baker.make(ClassExerciseQuestion, section=sec, order=1)

    def test_unique_submission_per_student_and_exercise(self):
        ex = baker.make(ClassExercise)
        student = baker.make(User, role=User.Role.STUDENT)
        baker.make(StudentExerciseSubmission, exercise=ex, student=student)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                baker.make(StudentExerciseSubmission, exercise=ex, student=student)

    def test_same_student_different_exercises_ok(self):
        ex1, ex2 = baker.make(ClassExercise), baker.make(ClassExercise)
        student = baker.make(User, role=User.Role.STUDENT)
        baker.make(StudentExerciseSubmission, exercise=ex1, student=student)
        s2 = baker.make(StudentExerciseSubmission, exercise=ex2, student=student)
        assert s2.pk is not None


class TestCascade:
    def test_deleting_exercise_cascades_its_graph(self):
        ex = baker.make(ClassExercise)
        sec = baker.make(ClassExerciseSection, exercise=ex)
        q = baker.make(ClassExerciseQuestion, section=sec)
        asset = baker.make(ClassExerciseAsset, exercise=ex, kind='pdf')
        sub = baker.make(StudentExerciseSubmission, exercise=ex)
        ex.delete()
        assert not ClassExerciseSection.objects.filter(id=sec.id).exists()
        assert not ClassExerciseQuestion.objects.filter(id=q.id).exists()
        assert not ClassExerciseAsset.objects.filter(id=asset.id).exists()
        assert not StudentExerciseSubmission.objects.filter(id=sub.id).exists()

    def test_deleting_session_cascades_exercises(self):
        session = baker.make(ClassCreationSession, pipeline_type='class')
        ex = baker.make(ClassExercise, session=session)
        session.delete()
        assert not ClassExercise.objects.filter(id=ex.id).exists()

    def test_deleting_student_cascades_their_submissions(self):
        student = baker.make(User, role=User.Role.STUDENT)
        sub = baker.make(StudentExerciseSubmission, student=student)
        sub_id = sub.id
        student.delete()
        assert not StudentExerciseSubmission.objects.filter(id=sub_id).exists()

    def test_deleting_section_cascades_its_questions_only(self):
        ex = baker.make(ClassExercise)
        sec = baker.make(ClassExerciseSection, exercise=ex)
        q = baker.make(ClassExerciseQuestion, section=sec)
        sec.delete()
        assert not ClassExerciseQuestion.objects.filter(id=q.id).exists()
        assert ClassExercise.objects.filter(id=ex.id).exists()  # exercise untouched


class TestDeadlineRevealHelper:
    def test_no_deadline_is_not_passed(self):
        assert baker.make(ClassExercise, deadline=None).deadline_passed() is False

    def test_future_deadline_is_not_passed(self):
        future = timezone.now() + timedelta(days=1)
        assert baker.make(ClassExercise, deadline=future).deadline_passed() is False

    def test_past_deadline_is_passed(self):
        past = timezone.now() - timedelta(minutes=1)
        assert baker.make(ClassExercise, deadline=past).deadline_passed() is True
