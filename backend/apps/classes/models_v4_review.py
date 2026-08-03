"""Immutable teacher exception-review decisions for Exam Prep V4."""
from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.classes.models_v4_records import ExamExtractionLifecycle


class ExamReviewDecision(models.Model):
    """One teacher override bound to exact current extraction fingerprints."""

    class Action(models.TextChoices):
        MATCH = 'match', 'Match to question'
        OUT_OF_SCOPE = 'out_of_scope', 'Confirm out of scope'
        IGNORE = 'ignore', 'Ignore answer record'

    project = models.ForeignKey(
        'classes.ExamProject',
        on_delete=models.CASCADE,
        related_name='review_decisions_v4',
    )
    match_decision = models.ForeignKey(
        'classes.ExamMatchDecision',
        on_delete=models.RESTRICT,
        related_name='teacher_reviews',
    )
    answer_record = models.ForeignKey(
        'classes.ExamAnswerSolutionRecord',
        on_delete=models.RESTRICT,
        related_name='teacher_reviews',
    )
    question_record = models.ForeignKey(
        'classes.ExamQuestionRecord',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='teacher_review_matches',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='exam_v4_review_decisions',
    )
    revision = models.PositiveIntegerField(default=1)
    action = models.CharField(max_length=24, choices=Action.choices)
    note = models.CharField(max_length=500, blank=True, default='')
    question_set_fingerprint = models.CharField(max_length=64)
    answer_set_fingerprint = models.CharField(max_length=64)
    source_match_fingerprint = models.CharField(max_length=64)
    fingerprint = models.CharField(max_length=64, db_index=True)
    lifecycle_status = models.CharField(
        max_length=16,
        choices=ExamExtractionLifecycle.choices,
        default=ExamExtractionLifecycle.ACCEPTED,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'classes'
        constraints = [
            models.UniqueConstraint(
                fields=['answer_record', 'revision'],
                name='uniq_exam_v4_review_answer_revision',
            ),
            models.CheckConstraint(
                condition=Q(revision__gte=1),
                name='exam_v4_review_revision_gte_1',
            ),
            models.CheckConstraint(
                condition=(
                    Q(action='match', question_record__isnull=False)
                    | Q(
                        action__in=['out_of_scope', 'ignore'],
                        question_record__isnull=True,
                    )
                ),
                name='exam_v4_review_action_question',
            ),
        ]
        indexes = [
            models.Index(
                fields=['project', 'lifecycle_status', 'action', '-updated_at'],
                name='exam_v4_review_current_idx',
            ),
        ]
        ordering = ['revision', 'id']

    def clean(self) -> None:
        super().clean()
        if self.match_decision_id and self.project_id:
            if self.match_decision.project_id != self.project_id:
                raise ValidationError(
                    {'match_decision': 'Review match decision must belong to the project.'}
                )
        if self.answer_record_id and self.project_id:
            if self.answer_record.project_id != self.project_id:
                raise ValidationError(
                    {'answer_record': 'Review answer must belong to the project.'}
                )
        if self.question_record_id and self.project_id:
            if self.question_record.project_id != self.project_id:
                raise ValidationError(
                    {'question_record': 'Review question must belong to the project.'}
                )
        if self.match_decision_id and self.answer_record_id:
            if self.match_decision.answer_record_id != self.answer_record_id:
                raise ValidationError(
                    {'answer_record': 'Review answer must match the source decision.'}
                )
        if self.action == self.Action.MATCH and not self.question_record_id:
            raise ValidationError(
                {'question_record': 'Manual match requires one question.'}
            )
        if self.action != self.Action.MATCH and self.question_record_id:
            raise ValidationError(
                {'question_record': 'Only manual match may bind a question.'}
            )
