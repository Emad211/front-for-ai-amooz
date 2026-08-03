"""Evidence-bound block models for the Exam Prep V4 extraction pipeline.

Blocks are semantic candidates detected inside confirmed source-map segments.
They never replace source pages: every block is composed of one or more ordered
fragments bound to immutable ``ExamSourcePage`` rows and normalized bounding
boxes.
"""
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class ExamSourceBlockKind(models.TextChoices):
    QUESTION = 'question', 'Question'
    ANSWER_SOLUTION = 'answer_solution', 'Answer and solution'
    ANSWER_KEY = 'answer_key', 'Answer key'
    INLINE_QUESTION_ANSWER = 'inline_question_answer', 'Inline question and answer'
    CONTINUATION = 'continuation', 'Continuation candidate'
    IGNORED = 'ignored', 'Ignored'
    UNKNOWN = 'unknown', 'Unknown'


class ExamSourceBlock(models.Model):
    """One ordered logical block bound to a confirmed Source Map revision."""

    class Status(models.TextChoices):
        ACCEPTED = 'accepted', 'Accepted'
        SUPERSEDED = 'superseded', 'Superseded'
        FAILED = 'failed', 'Failed'

    document = models.ForeignKey(
        'classes.ExamSourceDocument',
        on_delete=models.CASCADE,
        related_name='source_blocks',
    )
    segment = models.ForeignKey(
        'classes.ExamSourceSegment',
        on_delete=models.CASCADE,
        related_name='source_blocks',
    )
    revision = models.PositiveIntegerField(default=1)
    order = models.PositiveIntegerField(default=0)
    kind = models.CharField(
        max_length=32,
        choices=ExamSourceBlockKind.choices,
        default=ExamSourceBlockKind.UNKNOWN,
        db_index=True,
    )
    printed_number = models.CharField(max_length=64, blank=True, default='')
    confidence = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=0,
    )
    source_map_fingerprint = models.CharField(max_length=64, db_index=True)
    set_fingerprint = models.CharField(max_length=64, db_index=True)
    fingerprint = models.CharField(max_length=64, db_index=True)
    continuation_of = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='continuations',
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.ACCEPTED,
        db_index=True,
    )
    metadata = models.JSONField(default=dict, blank=True)
    error_code = models.CharField(max_length=64, blank=True, default='')
    error_detail = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'classes'
        constraints = [
            models.UniqueConstraint(
                fields=['document', 'revision', 'order'],
                name='uniq_exam_v4_block_order',
            ),
            models.CheckConstraint(
                condition=Q(revision__gte=1),
                name='exam_v4_block_revision_gte_1',
            ),
            models.CheckConstraint(
                condition=Q(confidence__gte=0) & Q(confidence__lte=1),
                name='exam_v4_block_confidence_range',
            ),
            models.CheckConstraint(
                condition=~Q(id=F('continuation_of')),
                name='exam_v4_block_not_self_continuation',
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    'document',
                    'source_map_fingerprint',
                    'status',
                    'order',
                ],
                name='exam_v4_block_current_idx',
            ),
            models.Index(
                fields=['segment', 'kind', 'order'],
                name='exam_v4_block_segment_idx',
            ),
        ]
        ordering = ['revision', 'order', 'id']

    def clean(self) -> None:
        super().clean()
        if self.document_id and self.segment_id:
            if self.segment.document_id != self.document_id:
                raise ValidationError(
                    {'segment': 'Block segment must belong to the same source document.'}
                )
        if self.continuation_of_id:
            parent = self.continuation_of
            if parent.document_id != self.document_id:
                raise ValidationError(
                    {'continuation_of': 'Continuation parent must belong to the same document.'}
                )
            if parent.revision != self.revision:
                raise ValidationError(
                    {'continuation_of': 'Continuation parent must belong to the same block revision.'}
                )

    def __str__(self) -> str:
        return (
            f'ExamSourceBlock<{self.document_id}:{self.revision}:'
            f'{self.order}:{self.kind}>'
        )


class ExamSourceBlockFragment(models.Model):
    """One ordered page crop belonging to a logical source block."""

    block = models.ForeignKey(
        ExamSourceBlock,
        on_delete=models.CASCADE,
        related_name='fragments',
    )
    page = models.ForeignKey(
        'classes.ExamSourcePage',
        on_delete=models.CASCADE,
        related_name='block_fragments',
    )
    order = models.PositiveIntegerField(default=0)
    x0 = models.DecimalField(max_digits=7, decimal_places=6)
    y0 = models.DecimalField(max_digits=7, decimal_places=6)
    x1 = models.DecimalField(max_digits=7, decimal_places=6)
    y1 = models.DecimalField(max_digits=7, decimal_places=6)
    column_index = models.PositiveSmallIntegerField(null=True, blank=True)
    is_continuation = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'classes'
        constraints = [
            models.UniqueConstraint(
                fields=['block', 'order'],
                name='uniq_exam_v4_block_fragment_order',
            ),
            models.CheckConstraint(
                condition=Q(x0__gte=0) & Q(x0__lte=1),
                name='exam_v4_fragment_x0_range',
            ),
            models.CheckConstraint(
                condition=Q(y0__gte=0) & Q(y0__lte=1),
                name='exam_v4_fragment_y0_range',
            ),
            models.CheckConstraint(
                condition=Q(x1__gte=0) & Q(x1__lte=1),
                name='exam_v4_fragment_x1_range',
            ),
            models.CheckConstraint(
                condition=Q(y1__gte=0) & Q(y1__lte=1),
                name='exam_v4_fragment_y1_range',
            ),
            models.CheckConstraint(
                condition=Q(x1__gt=F('x0')),
                name='exam_v4_fragment_positive_width',
            ),
            models.CheckConstraint(
                condition=Q(y1__gt=F('y0')),
                name='exam_v4_fragment_positive_height',
            ),
        ]
        indexes = [
            models.Index(
                fields=['page', 'order'],
                name='exam_v4_fragment_page_idx',
            ),
        ]
        ordering = ['order', 'id']

    def clean(self) -> None:
        super().clean()
        if self.block_id and self.page_id:
            if self.block.document_id != self.page.document_id:
                raise ValidationError(
                    {'page': 'Block fragment page must belong to the block document.'}
                )

    def __str__(self) -> str:
        return f'ExamSourceBlockFragment<{self.block_id}:{self.order}:{self.page_id}>'
