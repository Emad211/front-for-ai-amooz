"""Serializer annotation and correctness tests.

Verifies that serializers correctly use annotated fields and produce
expected output shapes.
"""
from __future__ import annotations

import pytest
from django.db.models import Count
from model_bakery import baker

from apps.classes.models import ClassCreationSession, ClassInvitation
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
        baker.make('classes.ClassInvitation', session=session, _quantity=3)
        section = baker.make(
            'classes.ClassSection', session=session, order=1,
        )
        baker.make(
            'classes.ClassUnit', session=session, section=section, _quantity=5,
        )

        # Annotate as the view does.
        qs = ClassCreationSession.objects.filter(id=session.id).annotate(
            _invites_count=Count('invites', distinct=True),
            _lessons_count=Count('units', distinct=True),
        )
        data = ClassCreationSessionListSerializer(qs.first()).data

        assert data['invites_count'] == 3
        assert data['lessons_count'] == 5

    def test_output_shape(self):
        teacher = baker.make('accounts.User', role='teacher')
        session = baker.make(
            'classes.ClassCreationSession',
            teacher=teacher,
            pipeline_type='class',
        )
        qs = ClassCreationSession.objects.filter(id=session.id).annotate(
            _invites_count=Count('invites', distinct=True),
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
        baker.make('classes.ClassInvitation', session=session, _quantity=4)

        qs = ClassCreationSession.objects.filter(id=session.id).annotate(
            _invites_count=Count('invites'),
        )
        data = ClassCreationSessionDetailSerializer(qs.first()).data

        assert data['invites_count'] == 4

    def test_falls_back_to_count_without_annotation(self):
        session = baker.make('classes.ClassCreationSession')
        baker.make('classes.ClassInvitation', session=session, _quantity=2)

        # No annotation — will fall back to .count().
        data = ClassCreationSessionDetailSerializer(session).data

        assert data['invites_count'] == 2


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
