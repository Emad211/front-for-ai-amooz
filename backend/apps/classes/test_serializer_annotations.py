"""Serializer annotation and correctness tests.

Verifies that serializers correctly use annotated fields and produce
expected output shapes.
"""
from __future__ import annotations

import pytest
from django.db.models import Count
from model_bakery import baker

from apps.classes.models import ClassCreationSession, ClassInvitation, Enrollment
from apps.classes.serializers import (
    ClassCreationSessionDetailSerializer,
    ClassCreationSessionListSerializer,
    ExamPrepSessionDetailSerializer,
)


@pytest.mark.django_db
class TestClassCreationSessionListSerializer:
    """Test the list serializer uses annotated counts."""

    def test_uses_annotation_not_n_plus_one(self):
        teacher = baker.make('accounts.User', role='teacher')
        session = baker.make(
            'classes.ClassCreationSession',
            teacher=teacher,
            pipeline_type='class',
        )
        students = baker.make('accounts.User', role='student', _quantity=3)
        for student in students:
            baker.make('classes.Enrollment', session=session, student=student)
        section = baker.make(
            'classes.ClassSection', session=session, order=1,
        )
        baker.make(
            'classes.ClassUnit', session=session, section=section, _quantity=5,
        )

        # Annotate as the view does.
        qs = ClassCreationSession.objects.filter(id=session.id).annotate(
            _invites_count=Count('enrollments__student_id', distinct=True),
            _students_count=Count('enrollments__student_id', distinct=True),
            _lessons_count=Count('units', distinct=True),
        )
        data = ClassCreationSessionListSerializer(qs.first()).data

        assert data['invites_count'] == 3
        assert data['students_count'] == 3
        assert data['lessons_count'] == 5

    def test_output_shape(self):
        teacher = baker.make('accounts.User', role='teacher')
        session = baker.make(
            'classes.ClassCreationSession',
            teacher=teacher,
            pipeline_type='class',
        )
        qs = ClassCreationSession.objects.filter(id=session.id).annotate(
            _invites_count=Count('enrollments__student_id', distinct=True),
            _students_count=Count('enrollments__student_id', distinct=True),
            _lessons_count=Count('units', distinct=True),
        )
        data = ClassCreationSessionListSerializer(qs.first()).data

        assert 'id' in data
        assert 'status' in data
        assert 'title' in data
        assert 'invites_count' in data
        assert 'lessons_count' in data
        assert 'is_published' in data
        assert 'created_at' in data


@pytest.mark.django_db
class TestClassCreationSessionDetailSerializer:
    """Test the detail serializer uses annotation when available."""

    def test_uses_annotation_when_available(self):
        session = baker.make('classes.ClassCreationSession')
        students = baker.make('accounts.User', role='student', _quantity=4)
        for student in students:
            baker.make('classes.Enrollment', session=session, student=student)

        qs = ClassCreationSession.objects.filter(id=session.id).annotate(
            _students_count=Count('enrollments__student_id', distinct=True),
        )
        data = ClassCreationSessionDetailSerializer(qs.first()).data

        assert data['invites_count'] == 4
        assert data['students_count'] == 4

    def test_falls_back_to_count_without_annotation(self):
        session = baker.make('classes.ClassCreationSession')
        students = baker.make('accounts.User', role='student', _quantity=2)
        for student in students:
            baker.make('classes.Enrollment', session=session, student=student)

        # No annotation — will fall back to .count().
        data = ClassCreationSessionDetailSerializer(session).data

        assert data['invites_count'] == 2
        assert data['students_count'] == 2

    def test_invitation_without_enrollment_is_not_counted(self):
        session = baker.make('classes.ClassCreationSession')
        baker.make('classes.ClassInvitation', session=session)

        data = ClassCreationSessionDetailSerializer(session).data

        assert data['students_count'] == 0
        assert data['invites_count'] == 0


@pytest.mark.django_db
class TestExamPrepSessionDetailSerializer:
    """Test exam prep serializer annotation fallback."""

    def test_uses_annotation_when_available(self):
        session = baker.make(
            'classes.ClassCreationSession',
            pipeline_type='exam_prep',
        )
        baker.make('classes.ClassInvitation', session=session, _quantity=3)

        qs = ClassCreationSession.objects.filter(id=session.id).annotate(
            _invites_count=Count('invites'),
        )
        data = ExamPrepSessionDetailSerializer(qs.first()).data

        assert data['invites_count'] == 3

    def test_falls_back_without_annotation(self):
        session = baker.make(
            'classes.ClassCreationSession',
            pipeline_type='exam_prep',
        )
        baker.make('classes.ClassInvitation', session=session, _quantity=1)

        data = ExamPrepSessionDetailSerializer(session).data

        assert data['invites_count'] == 1

    def test_exam_prep_data_parsed(self):
        session = baker.make(
            'classes.ClassCreationSession',
            pipeline_type='exam_prep',
            exam_prep_json='{"questions": [{"q": "test?"}]}',
        )
        data = ExamPrepSessionDetailSerializer(session).data

        assert data['exam_prep_data'] is not None
        assert 'questions' in data['exam_prep_data']

    def test_exam_prep_data_empty(self):
        session = baker.make(
            'classes.ClassCreationSession',
            pipeline_type='exam_prep',
            exam_prep_json='',
        )
        data = ExamPrepSessionDetailSerializer(session).data

        assert data['exam_prep_data'] is None

    def test_usage_summary_sums_only_this_sessions_logs(self):
        session = baker.make(
            'classes.ClassCreationSession',
            pipeline_type='exam_prep',
        )
        other = baker.make(
            'classes.ClassCreationSession',
            pipeline_type='exam_prep',
        )
        baker.make(
            'commons.LLMUsageLog',
            session_id=session.id,
            input_tokens=100,
            output_tokens=40,
            total_tokens=140,
            estimated_cost_usd='0.010000',
            estimated_cost_toman='7000.00',
        )
        baker.make(
            'commons.LLMUsageLog',
            session_id=session.id,
            input_tokens=60,
            output_tokens=10,
            total_tokens=70,
            estimated_cost_usd='0.005000',
            estimated_cost_toman='3500.00',
        )
        # A different session's usage must not leak into this rollup.
        baker.make(
            'commons.LLMUsageLog',
            session_id=other.id,
            total_tokens=9999,
            estimated_cost_toman='999999.00',
        )

        summary = ExamPrepSessionDetailSerializer(session).data['usageSummary']

        assert summary['totalTokens'] == 210
        assert summary['inputTokens'] == 160
        assert summary['outputTokens'] == 50
        assert summary['calls'] == 2
        assert summary['costUsd'] == pytest.approx(0.015)
        assert summary['costToman'] == pytest.approx(10500.0)
        # Token counts are ints, costs are floats (Decimal columns coerced).
        assert isinstance(summary['totalTokens'], int)
        assert isinstance(summary['costToman'], float)

    def test_usage_summary_is_all_zero_without_logs(self):
        session = baker.make(
            'classes.ClassCreationSession',
            pipeline_type='exam_prep',
        )

        summary = ExamPrepSessionDetailSerializer(session).data['usageSummary']

        assert summary == {
            'totalTokens': 0,
            'inputTokens': 0,
            'outputTokens': 0,
            'costUsd': 0,
            'costToman': 0,
            'calls': 0,
        }
