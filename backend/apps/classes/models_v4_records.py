"""Typed private extraction records and deterministic match decisions for V4."""
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.classes.models_v4_blocks import ExamSourceBlock


class ExamExtractionLifecycle(models.TextChoices):
    ACCEPTED = 'accepted', 'Accepted'
    SUPERSEDED = 'superseded', 'Superseded'
    FAILED = 'failed', 'Failed'


class ExamQuestionRecord(models.Model):
    """One exact printed question extracted from one question-bearing block."""

    project = models.ForeignKey(
        'classes.ExamProject',
        on_delete=models.CASCADE,
        related_name='question_records_v4',
    )
    document = models.ForeignKey(
        'classes.ExamSourceDocument',
        on_delete=models.CASCADE,
        related_name='question_records_v4',
    )
    source_block = models.ForeignKey(
        ExamSourceBlock,
        on_delete=models.RESTRICT,
        related_name='question_records',
    )
    revision = models.PositiveIntegerField(default=1)
    order = models.PositiveIntegerField(default=0)
    section_key = models.CharField(max_length=128, blank=True, default='')
    printed_number = models.CharField(max_length=64, blank=True, default='')
    question_text = models.TextField()
    options = models.JSONField(default=list, blank=True)
    confidence = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    block_set_fingerprint = models.CharField(max_length=64, db_index=True)
    set_fingerprint = models.CharField(max_length=64, db_index=True)
    fingerprint = models.CharField(max_length=64, db_index=True)
    lifecycle_status = models.CharField(
        max_length=16,
        choices=ExamExtractionLifecycle.choices,
        default=ExamExtractionLifecycle.ACCEPTED,
        db_index=True,
    )
    warnings = models.JSONField(default=list, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    error_code = models.CharField(max_length=64, blank=True, default='')
    error_detail = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'classes'
        constraints = [
            models.UniqueConstraint(
                fields=['document', 'revision', 'order'],
                name='uniq_exam_v4_question_order',
            ),
            models.UniqueConstraint(
                fields=['source_block', 'revision'],
                name='uniq_exam_v4_question_block_revision',
            ),
            models.CheckConstraint(
                condition=Q(revision__gte=1),
                name='exam_v4_question_revision_gte_1',
            ),
            models.CheckConstraint(
                condition=Q(confidence__gte=0) & Q(confidence__lte=1),
                name='exam_v4_question_confidence_range',
            ),
            models.CheckConstraint(
                condition=~Q(question_text=''),
                name='exam_v4_question_text_not_empty',
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    'project',
                    'lifecycle_status',
                    'section_key',
                    'printed_number',
                ],
                name='exam_v4_question_lookup_idx',
            ),
            models.Index(
                fields=['document', 'block_set_fingerprint', 'revision', 'order'],
                name='exam_v4_question_current_idx',
            ),
        ]
        ordering = ['revision', 'order', 'id']

    def clean(self) -> None:
        super().clean()
        if self.document_id and self.project_id:
            if self.document.project_id != self.project_id:
                raise ValidationError(
                    {'document': 'Question document must belong to the record project.'}
                )
        if self.source_block_id and self.document_id:
            if self.source_block.document_id != self.document_id:
                raise ValidationError(
                    {'source_block': 'Question block must belong to the record document.'}
                )


class ExamQuestionRecordEvidence(models.Model):
    record = models.ForeignKey(
        ExamQuestionRecord,
        on_delete=models.CASCADE,
        related_name='evidence_links',
    )
    block = models.ForeignKey(
        ExamSourceBlock,
        on_delete=models.RESTRICT,
        related_name='question_evidence_links',
    )
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'classes'
        constraints = [
            models.UniqueConstraint(
                fields=['record', 'order'],
                name='uniq_exam_v4_question_evidence_order',
            ),
            models.UniqueConstraint(
                fields=['record', 'block'],
                name='uniq_exam_v4_question_evidence_block',
            ),
        ]
        ordering = ['order', 'id']

    def clean(self) -> None:
        super().clean()
        if self.record_id and self.block_id:
            if self.record.document_id != self.block.document_id:
                raise ValidationError(
                    {'block': 'Question evidence block must belong to the record document.'}
                )


class ExamAnswerSolutionRecord(models.Model):
    """Correct answer and complete source solution kept as one evidence-bound record."""

    project = models.ForeignKey(
        'classes.ExamProject',
        on_delete=models.CASCADE,
        related_name='answer_solution_records_v4',
    )
    document = models.ForeignKey(
        'classes.ExamSourceDocument',
        on_delete=models.CASCADE,
        related_name='answer_solution_records_v4',
    )
    source_block = models.ForeignKey(
        ExamSourceBlock,
        on_delete=models.RESTRICT,
        related_name='answer_solution_records',
    )
    revision = models.PositiveIntegerField(default=1)
    order = models.PositiveIntegerField(default=0)
    section_key = models.CharField(max_length=128, blank=True, default='')
    printed_number = models.CharField(max_length=64, blank=True, default='')
    correct_option = models.CharField(max_length=32, blank=True, default='')
    final_answer = models.TextField(blank=True, default='')
    solution_text = models.TextField(blank=True, default='')
    confidence = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    block_set_fingerprint = models.CharField(max_length=64, db_index=True)
    set_fingerprint = models.CharField(max_length=64, db_index=True)
    fingerprint = models.CharField(max_length=64, db_index=True)
    lifecycle_status = models.CharField(
        max_length=16,
        choices=ExamExtractionLifecycle.choices,
        default=ExamExtractionLifecycle.ACCEPTED,
        db_index=True,
    )
    warnings = models.JSONField(default=list, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    error_code = models.CharField(max_length=64, blank=True, default='')
    error_detail = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'classes'
        constraints = [
            models.UniqueConstraint(
                fields=['document', 'revision', 'order'],
                name='uniq_exam_v4_answer_order',
            ),
            models.UniqueConstraint(
                fields=['source_block', 'revision'],
                name='uniq_exam_v4_answer_block_revision',
            ),
            models.CheckConstraint(
                condition=Q(revision__gte=1),
                name='exam_v4_answer_revision_gte_1',
            ),
            models.CheckConstraint(
                condition=Q(confidence__gte=0) & Q(confidence__lte=1),
                name='exam_v4_answer_confidence_range',
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(correct_option='')
                    | ~Q(final_answer='')
                    | ~Q(solution_text='')
                ),
                name='exam_v4_answer_content_not_empty',
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    'project',
                    'lifecycle_status',
                    'section_key',
                    'printed_number',
                ],
                name='exam_v4_answer_lookup_idx',
            ),
            models.Index(
                fields=['document', 'block_set_fingerprint', 'revision', 'order'],
                name='exam_v4_answer_current_idx',
            ),
        ]
        ordering = ['revision', 'order', 'id']

    def clean(self) -> None:
        super().clean()
        if self.document_id and self.project_id:
            if self.document.project_id != self.project_id:
                raise ValidationError(
                    {'document': 'Answer document must belong to the record project.'}
                )
        if self.source_block_id and self.document_id:
            if self.source_block.document_id != self.document_id:
                raise ValidationError(
                    {'source_block': 'Answer block must belong to the record document.'}
                )


class ExamAnswerSolutionRecordEvidence(models.Model):
    record = models.ForeignKey(
        ExamAnswerSolutionRecord,
        on_delete=models.CASCADE,
        related_name='evidence_links',
    )
    block = models.ForeignKey(
        ExamSourceBlock,
        on_delete=models.RESTRICT,
        related_name='answer_solution_evidence_links',
    )
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'classes'
        constraints = [
            models.UniqueConstraint(
                fields=['record', 'order'],
                name='uniq_exam_v4_answer_evidence_order',
            ),
            models.UniqueConstraint(
                fields=['record', 'block'],
                name='uniq_exam_v4_answer_evidence_block',
            ),
        ]
        ordering = ['order', 'id']

    def clean(self) -> None:
        super().clean()
        if self.record_id and self.block_id:
            if self.record.document_id != self.block.document_id:
                raise ValidationError(
                    {'block': 'Answer evidence block must belong to the record document.'}
                )


class ExamMatchDecision(models.Model):
    class Decision(models.TextChoices):
        MATCHED = 'matched', 'Matched'
        OUT_OF_SCOPE = 'out_of_scope', 'Out of scope'
        UNRESOLVED = 'unresolved', 'Unresolved'
        AMBIGUOUS = 'ambiguous', 'Ambiguous'
        CONFLICT = 'conflict', 'Conflict'

    class Method(models.TextChoices):
        EXACT_SCOPE_NUMBER = 'exact_scope_number', 'Exact scope and number'
        UNIQUE_NUMBER = 'unique_number', 'Unique project number'
        NONE = 'none', 'No automatic method'

    project = models.ForeignKey(
        'classes.ExamProject',
        on_delete=models.CASCADE,
        related_name='match_decisions_v4',
    )
    answer_record = models.ForeignKey(
        ExamAnswerSolutionRecord,
        on_delete=models.CASCADE,
        related_name='match_decisions',
    )
    question_record = models.ForeignKey(
        ExamQuestionRecord,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='match_decisions',
    )
    revision = models.PositiveIntegerField(default=1)
    order = models.PositiveIntegerField(default=0)
    decision = models.CharField(max_length=24, choices=Decision.choices)
    method = models.CharField(
        max_length=32,
        choices=Method.choices,
        default=Method.NONE,
    )
    normalized_section = models.CharField(max_length=128, blank=True, default='')
    normalized_number = models.CharField(max_length=64, blank=True, default='')
    reason_code = models.CharField(max_length=64, blank=True, default='')
    question_set_fingerprint = models.CharField(max_length=64)
    answer_set_fingerprint = models.CharField(max_length=64)
    set_fingerprint = models.CharField(max_length=64, db_index=True)
    fingerprint = models.CharField(max_length=64, db_index=True)
    lifecycle_status = models.CharField(
        max_length=16,
        choices=ExamExtractionLifecycle.choices,
        default=ExamExtractionLifecycle.ACCEPTED,
        db_index=True,
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'classes'
        constraints = [
            models.UniqueConstraint(
                fields=['project', 'revision', 'order'],
                name='uniq_exam_v4_match_order',
            ),
            models.UniqueConstraint(
                fields=['answer_record', 'revision'],
                name='uniq_exam_v4_match_answer_revision',
            ),
            models.CheckConstraint(
                condition=Q(revision__gte=1),
                name='exam_v4_match_revision_gte_1',
            ),
        ]
        indexes = [
            models.Index(
                fields=['project', 'lifecycle_status', 'decision', 'order'],
                name='exam_v4_match_current_idx',
            ),
        ]
        ordering = ['revision', 'order', 'id']

    def clean(self) -> None:
        super().clean()
        if self.answer_record_id and self.project_id:
            if self.answer_record.project_id != self.project_id:
                raise ValidationError(
                    {'answer_record': 'Answer record must belong to the match project.'}
                )
        if self.question_record_id and self.project_id:
            if self.question_record.project_id != self.project_id:
                raise ValidationError(
                    {'question_record': 'Question record must belong to the match project.'}
                )
        if self.decision == self.Decision.MATCHED and not self.question_record_id:
            raise ValidationError(
                {'question_record': 'Matched decisions require a question record.'}
            )
        if self.decision != self.Decision.MATCHED and self.question_record_id:
            raise ValidationError(
                {'question_record': 'Only matched decisions may bind a question.'}
            )
