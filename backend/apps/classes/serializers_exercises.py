"""Serializers for the Exercise Hub teacher API (camelCase output).

Kept separate from the large ``serializers.py`` to keep the exercise feature
cohesive. Design: docs/features/exercise-hub.md.
"""
from __future__ import annotations

from rest_framework import serializers

from .models import (
    ClassExercise,
    ClassExerciseAsset,
    ClassExerciseQuestion,
    ClassExerciseSection,
)


class ExerciseAssetSerializer(serializers.ModelSerializer):
    fileUrl = serializers.SerializerMethodField()

    class Meta:
        model = ClassExerciseAsset
        fields = ['id', 'kind', 'order', 'fileUrl']

    def get_fileUrl(self, obj) -> str:
        try:
            return obj.file.url
        except Exception:
            return ''


class ExerciseQuestionSerializer(serializers.ModelSerializer):
    questionMarkdown = serializers.CharField(source='question_markdown', read_only=True)
    questionType = serializers.CharField(source='question_type', read_only=True)
    referenceAnswerMarkdown = serializers.CharField(source='reference_answer_markdown', read_only=True)
    maxPoints = serializers.DecimalField(source='max_points', max_digits=6, decimal_places=2, read_only=True)
    gradingNotes = serializers.CharField(source='grading_notes', read_only=True)

    class Meta:
        model = ClassExerciseQuestion
        fields = [
            'id', 'order', 'questionMarkdown', 'questionType', 'options',
            'referenceAnswerMarkdown', 'maxPoints', 'gradingNotes',
        ]


class ExerciseSectionSerializer(serializers.ModelSerializer):
    assistantEnabled = serializers.BooleanField(source='assistant_enabled', read_only=True)
    questions = ExerciseQuestionSerializer(many=True, read_only=True)

    class Meta:
        model = ClassExerciseSection
        fields = ['id', 'order', 'title', 'assistantEnabled', 'questions']


class ExerciseListSerializer(serializers.ModelSerializer):
    assistantEnabled = serializers.BooleanField(source='assistant_enabled', read_only=True)
    allowLate = serializers.BooleanField(source='allow_late', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = ClassExercise
        fields = [
            'id', 'title', 'description', 'status', 'deadline',
            'assistantEnabled', 'allowLate', 'createdAt', 'updatedAt',
        ]


class ExerciseDetailSerializer(ExerciseListSerializer):
    sections = ExerciseSectionSerializer(many=True, read_only=True)
    assets = ExerciseAssetSerializer(many=True, read_only=True)

    class Meta(ExerciseListSerializer.Meta):
        fields = ExerciseListSerializer.Meta.fields + ['sections', 'assets']


class ExerciseCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default='')


class ExerciseUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255, required=False)
    deadline = serializers.DateTimeField(required=False, allow_null=True)
    allow_late = serializers.BooleanField(required=False)
    assistant_enabled = serializers.BooleanField(required=False)


class SectionUpdateSerializer(serializers.Serializer):
    assistant_enabled = serializers.BooleanField(required=False)
    title = serializers.CharField(max_length=255, required=False, allow_blank=True)


class QuestionWriteSerializer(serializers.Serializer):
    section_id = serializers.IntegerField(required=False)
    question_markdown = serializers.CharField(required=False, allow_blank=True)
    question_type = serializers.ChoiceField(
        choices=ClassExerciseQuestion.QuestionType.choices, required=False,
    )
    options = serializers.ListField(required=False)
    reference_answer_markdown = serializers.CharField(required=False, allow_blank=True)
    max_points = serializers.DecimalField(max_digits=6, decimal_places=2, required=False)
    grading_notes = serializers.CharField(required=False, allow_blank=True)
