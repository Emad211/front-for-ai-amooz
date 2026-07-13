"""Serializers for the Exercise Hub teacher API (camelCase output).

Kept separate from the large ``serializers.py`` to keep the exercise feature
cohesive. Design: docs/features/exercise-hub.md.
"""
from __future__ import annotations

import json

from rest_framework import serializers

from .models import (
    ClassExercise,
    ClassExerciseAsset,
    ClassExerciseQuestion,
    ClassExerciseSection,
)
from .services.exercise_workflow import (
    ANSWER_LAYOUT_CHOICES,
    SOURCE_ROLE_CHOICES,
    WRITING_MODE_CHOICES,
    serialize_workflow_fields,
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
    workflowStage = serializers.SerializerMethodField()
    workflowMessage = serializers.SerializerMethodField()
    progressPercent = serializers.SerializerMethodField()
    workflowWarnings = serializers.SerializerMethodField()
    readyForReview = serializers.SerializerMethodField()
    reviewReadyNotifiedAt = serializers.SerializerMethodField()

    def _wf(self, obj):
        return serialize_workflow_fields(obj)

    def get_workflowStage(self, obj):
        return self._wf(obj)['workflowStage']

    def get_workflowMessage(self, obj):
        return self._wf(obj)['workflowMessage']

    def get_progressPercent(self, obj):
        return self._wf(obj)['progressPercent']

    def get_workflowWarnings(self, obj):
        return self._wf(obj)['workflowWarnings']

    def get_readyForReview(self, obj):
        return self._wf(obj)['readyForReview']

    def get_reviewReadyNotifiedAt(self, obj):
        return self._wf(obj)['reviewReadyNotifiedAt']

    class Meta:
        model = ClassExercise
        fields = [
            'id', 'title', 'description', 'status', 'deadline',
            'assistantEnabled', 'allowLate', 'createdAt', 'updatedAt',
            'workflowStage', 'workflowMessage', 'progressPercent',
            'workflowWarnings', 'readyForReview', 'reviewReadyNotifiedAt',
        ]


class ExerciseDetailSerializer(ExerciseListSerializer):
    sections = ExerciseSectionSerializer(many=True, read_only=True)
    questions = serializers.SerializerMethodField()
    assets = ExerciseAssetSerializer(many=True, read_only=True)

    def get_questions(self, obj):
        questions = ClassExerciseQuestion.objects.filter(
            section__exercise=obj,
        ).order_by('section__order', 'order', 'id')
        return ExerciseQuestionSerializer(questions, many=True).data

    class Meta(ExerciseListSerializer.Meta):
        fields = ExerciseListSerializer.Meta.fields + ['questions', 'sections', 'assets']


class ExerciseCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    no_deadline = serializers.BooleanField(required=True)
    deadline = serializers.DateTimeField(required=False, allow_null=True)
    allow_late = serializers.BooleanField(required=False, default=False)
    assistant_enabled = serializers.BooleanField(required=False, default=True)
    teacher_note = serializers.CharField(required=False, allow_blank=True, default='')
    sources = serializers.CharField(required=False, allow_blank=True, default='[]')

    def validate_sources(self, value):
        raw = value
        if isinstance(raw, str):
            try:
                raw = json.loads(raw or '[]')
            except json.JSONDecodeError as exc:
                raise serializers.ValidationError('metadata فایل‌ها نامعتبر است.') from exc
        if not isinstance(raw, list) or not raw:
            raise serializers.ValidationError('حداقل یک منبع برای تمرین لازم است.')
        seen: set[str] = set()
        out: list[dict] = []
        for idx, item in enumerate(raw, start=1):
            if not isinstance(item, dict):
                raise serializers.ValidationError(f'منبع شمارهٔ {idx} نامعتبر است.')
            key = str(item.get('clientFileKey') or '').strip()
            if not key:
                raise serializers.ValidationError(f'منبع شمارهٔ {idx} کلید فایل ندارد.')
            if key in seen:
                raise serializers.ValidationError('کلید فایل‌ها باید یکتا باشد.')
            seen.add(key)
            role = str(item.get('role') or 'auto')
            writing_mode = str(item.get('writingMode') or item.get('writing_mode') or 'auto')
            answer_layout = str(item.get('answerLayout') or item.get('answer_layout') or 'auto')
            if role not in SOURCE_ROLE_CHOICES:
                raise serializers.ValidationError(f'نقش منبع برای فایل {key} نامعتبر است.')
            if writing_mode not in WRITING_MODE_CHOICES:
                raise serializers.ValidationError(f'نوع نوشتار برای فایل {key} نامعتبر است.')
            if answer_layout not in ANSWER_LAYOUT_CHOICES:
                raise serializers.ValidationError(f'چیدمان پاسخ‌ها برای فایل {key} نامعتبر است.')
            out.append({
                'clientFileKey': key,
                'role': role,
                'writingMode': writing_mode,
                'answerLayout': answer_layout,
            })
        return out

    def validate(self, attrs):
        no_deadline = attrs.get('no_deadline')
        deadline = attrs.get('deadline')
        if no_deadline:
            if attrs.get('allow_late'):
                raise serializers.ValidationError({
                    'allow_late': 'ارسال دیرهنگام فقط برای تمرین دارای مهلت قابل فعال‌سازی است.',
                })
            attrs['deadline'] = None
        elif deadline is None:
            raise serializers.ValidationError({'deadline': 'برای این تمرین باید مهلت ارسال تعیین شود.'})
        return attrs


class ExerciseUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255, required=False)
    deadline = serializers.DateTimeField(required=False, allow_null=True)
    allow_late = serializers.BooleanField(required=False)
    assistant_enabled = serializers.BooleanField(required=False)

    def validate(self, attrs):
        exercise = self.context.get('exercise')
        current_deadline = getattr(exercise, 'deadline', None)
        deadline = attrs.get('deadline', current_deadline)
        allow_late = attrs.get('allow_late', getattr(exercise, 'allow_late', False))
        if deadline is None and attrs.get('allow_late') is True:
            raise serializers.ValidationError({
                'allow_late': 'ارسال دیرهنگام فقط برای تمرین دارای مهلت قابل فعال‌سازی است.',
            })
        if 'deadline' in attrs and deadline is None and allow_late:
            attrs['allow_late'] = False
        return attrs


class SectionUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate(self, attrs):
        if 'assistant_enabled' in self.initial_data:
            raise serializers.ValidationError({
                'assistant_enabled': 'تنظیم دستیار برای بخش‌ها حذف شده است؛ تنظیم سطح تمرین را تغییر دهید.',
            })
        return attrs


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
