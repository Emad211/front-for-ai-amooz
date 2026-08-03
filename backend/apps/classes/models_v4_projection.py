"""Backward-compatible projection state for Exam Prep V4."""
from __future__ import annotations

from django.db import models
from django.db.models import Q


class ExamV4Projection(models.Model):
    class Status(models.TextChoices):
        READY = 'ready', 'Ready'
        PUBLISHED = 'published', 'Published'
        SUPERSEDED = 'superseded', 'Superseded'
        FAILED = 'failed', 'Failed'

    project = models.OneToOneField(
        'classes.ExamProject',
        on_delete=models.CASCADE,
        related_name='legacy_projection_v4',
    )
    session = models.OneToOneField(
        'classes.ClassCreationSession',
        on_delete=models.CASCADE,
        related_name='source_exam_v4_projection',
    )
    revision = models.PositiveIntegerField(default=1)
    question_set_fingerprint = models.CharField(max_length=64)
    answer_set_fingerprint = models.CharField(max_length=64)
    review_set_fingerprint = models.CharField(max_length=64)
    projection_fingerprint = models.CharField(max_length=64, db_index=True)
    question_count = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.READY,
        db_index=True,
    )
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'classes'
        constraints = [
            models.CheckConstraint(
                condition=Q(revision__gte=1),
                name='exam_v4_projection_revision_gte_1',
            ),
        ]
        indexes = [
            models.Index(
                fields=['status', '-updated_at'],
                name='exam_v4_projection_status_idx',
            ),
        ]
