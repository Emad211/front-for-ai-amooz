"""Additive source-domain models for Exam Prep V4.

These models intentionally live outside the legacy ``models.py`` while V4 is
built behind a feature boundary. ``ClassesConfig.ready`` imports this module so
Django registers the models under the existing ``classes`` app label.

Canonical design: docs/features/exam-prep-v4-source-aware-split-pipeline.md
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from core.storage_backends import answer_source_storage


class ExamSourceRole(models.TextChoices):
    COVER = 'cover', 'Cover'
    QUESTIONS = 'questions', 'Questions'
    ANSWER_SOLUTIONS = 'answer_solutions', 'Answers and solutions'
    ANSWER_KEY = 'answer_key', 'Answer key'
    INLINE_QUESTION_ANSWER = 'inline_question_answer', 'Question with inline answer'
    IGNORED = 'ignored', 'Ignored'
    UNKNOWN = 'unknown', 'Unknown'


class ExamProject(models.Model):
    """One independent V4 exam draft.

    One uploaded PDF creates one project by default. Multiple documents can
    belong to a project only through a later explicit grouping workflow.
    """

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        UPLOADING = 'uploading', 'Uploading'
        CLASSIFYING = 'classifying', 'Classifying sources'
        AWAITING_SOURCE_CONFIRMATION = (
            'awaiting_source_confirmation',
            'Awaiting source confirmation',
        )
        SEGMENTING = 'segmenting', 'Segmenting source pages'
        EXTRACTING_QUESTIONS = 'extracting_questions', 'Extracting questions'
        EXTRACTING_ANSWERS = 'extracting_answers', 'Extracting answers and solutions'
        MATCHING = 'matching', 'Matching records'
        AWAITING_REVIEW = 'awaiting_review', 'Awaiting teacher review'
        READY_TO_PUBLISH = 'ready_to_publish', 'Ready to publish'
        PUBLISHED = 'published', 'Published'
        CANCELLED = 'cancelled', 'Cancelled'
        FAILED = 'failed', 'Failed'

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='exam_v4_projects',
    )
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='exam_v4_projects',
    )
    study_group = models.ForeignKey(
        'organizations.StudyGroup',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='exam_v4_projects',
    )
    client_request_id = models.UUIDField(null=True, blank=True, default=None)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    engine_version = models.PositiveSmallIntegerField(default=4, editable=False)
    revision = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=40,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    workflow_state = models.JSONField(default=dict, blank=True)
    error_code = models.CharField(max_length=64, blank=True, default='')
    error_detail = models.TextField(blank=True, default='')
    cancel_requested = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    reviewed_revision = models.PositiveIntegerField(null=True, blank=True)
    reviewed_projection_fingerprint = models.CharField(
        max_length=64,
        blank=True,
        default='',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['teacher', 'client_request_id'],
                name='uniq_exam_v4_teacher_request',
            ),
            models.CheckConstraint(
                condition=Q(engine_version=4),
                name='exam_v4_engine_version_4',
            ),
            models.CheckConstraint(
                condition=Q(revision__gte=1),
                name='exam_v4_revision_gte_1',
            ),
        ]
        indexes = [
            models.Index(
                fields=['teacher', 'status', '-updated_at'],
                name='exam_v4_owner_status_idx',
            ),
            models.Index(
                fields=['organization', 'status', '-updated_at'],
                name='exam_v4_org_status_idx',
            ),
        ]

    def __str__(self) -> str:
        return f'ExamProject<{self.pk}:{self.status}>'


class ExamSourceDocument(models.Model):
    """One uploaded PDF source belonging to exactly one V4 exam project."""

    class Status(models.TextChoices):
        PENDING_UPLOAD = 'pending_upload', 'Pending upload'
        UPLOADED = 'uploaded', 'Uploaded'
        RENDERING = 'rendering', 'Rendering pages'
        CLASSIFYING = 'classifying', 'Classifying pages'
        AWAITING_CONFIRMATION = 'awaiting_confirmation', 'Awaiting confirmation'
        CONFIRMED = 'confirmed', 'Confirmed'
        FAILED = 'failed', 'Failed'

    project = models.ForeignKey(
        ExamProject,
        on_delete=models.CASCADE,
        related_name='source_documents',
    )
    client_document_id = models.UUIDField(default=uuid.uuid4)
    upload_order = models.PositiveIntegerField(default=0)
    original_name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=127, default='application/pdf')
    source_file = models.FileField(
        upload_to='exam-prep-v4/source/documents/',
        storage=answer_source_storage,
        blank=True,
    )
    source_sha256 = models.CharField(max_length=64, blank=True, default='', db_index=True)
    byte_size = models.PositiveBigIntegerField(default=0)
    page_count = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.PENDING_UPLOAD,
        db_index=True,
    )
    classification_revision = models.PositiveIntegerField(default=1)
    classification_fingerprint = models.CharField(max_length=64, blank=True, default='')
    source_map_fingerprint = models.CharField(max_length=64, blank=True, default='')
    classification_metadata = models.JSONField(default=dict, blank=True)
    teacher_confirmed_at = models.DateTimeField(null=True, blank=True)
    teacher_confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='confirmed_exam_v4_sources',
    )
    teacher_confirmed_revision = models.PositiveIntegerField(null=True, blank=True)
    teacher_confirmed_fingerprint = models.CharField(
        max_length=64,
        blank=True,
        default='',
    )
    source_retain_until = models.DateTimeField(null=True, blank=True)
    error_code = models.CharField(max_length=64, blank=True, default='')
    error_detail = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['project', 'client_document_id'],
                name='uniq_exam_v4_project_document',
            ),
            models.UniqueConstraint(
                fields=['project', 'upload_order'],
                name='uniq_exam_v4_project_upload_order',
            ),
            models.CheckConstraint(
                condition=Q(classification_revision__gte=1),
                name='exam_v4_doc_revision_gte_1',
            ),
            models.CheckConstraint(
                condition=(
                    Q(teacher_confirmed_revision__isnull=True)
                    | Q(teacher_confirmed_revision__gte=1)
                ),
                name='exam_v4_confirmed_revision_gte_1',
            ),
        ]
        indexes = [
            models.Index(
                fields=['project', 'status', 'upload_order'],
                name='exam_v4_doc_status_idx',
            ),
        ]
        ordering = ['upload_order', 'id']

    def __str__(self) -> str:
        return f'ExamSourceDocument<{self.pk}:{self.original_name}>'


class ExamSourcePage(models.Model):
    """Durable source metadata and private render for one PDF page."""

    class Orientation(models.IntegerChoices):
        DEG_0 = 0, '0°'
        DEG_90 = 90, '90°'
        DEG_180 = 180, '180°'
        DEG_270 = 270, '270°'

    document = models.ForeignKey(
        ExamSourceDocument,
        on_delete=models.CASCADE,
        related_name='pages',
    )
    page_number = models.PositiveIntegerField()
    display_order = models.PositiveIntegerField()
    rendered_file = models.FileField(
        upload_to='exam-prep-v4/source/pages/',
        storage=answer_source_storage,
        blank=True,
    )
    thumbnail_file = models.FileField(
        upload_to='exam-prep-v4/source/thumbnails/',
        storage=answer_source_storage,
        blank=True,
    )
    content_type = models.CharField(max_length=100, default='image/png')
    byte_size = models.PositiveBigIntegerField(default=0)
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True, default='', db_index=True)
    perceptual_hash = models.CharField(max_length=64, blank=True, default='', db_index=True)
    native_text_sample = models.TextField(blank=True, default='')
    native_text_length = models.PositiveIntegerField(default=0)
    predicted_role = models.CharField(
        max_length=32,
        choices=ExamSourceRole.choices,
        default=ExamSourceRole.UNKNOWN,
        db_index=True,
    )
    predicted_confidence = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=0,
    )
    teacher_role = models.CharField(
        max_length=32,
        choices=ExamSourceRole.choices,
        blank=True,
        default='',
    )
    orientation = models.PositiveSmallIntegerField(
        choices=Orientation.choices,
        default=Orientation.DEG_0,
    )
    duplicate_of = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='duplicates',
    )
    classification_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['document', 'page_number'],
                name='uniq_exam_v4_document_page',
            ),
            models.UniqueConstraint(
                fields=['document', 'display_order'],
                name='uniq_exam_v4_document_order',
            ),
            models.CheckConstraint(
                condition=Q(page_number__gte=1),
                name='exam_v4_page_number_gte_1',
            ),
            models.CheckConstraint(
                condition=Q(display_order__gte=1),
                name='exam_v4_display_order_gte_1',
            ),
            models.CheckConstraint(
                condition=Q(predicted_confidence__gte=0)
                & Q(predicted_confidence__lte=1),
                name='exam_v4_page_confidence_range',
            ),
            models.CheckConstraint(
                condition=~Q(id=F('duplicate_of')),
                name='exam_v4_page_not_self_duplicate',
            ),
        ]
        indexes = [
            models.Index(
                fields=['document', 'predicted_role', 'page_number'],
                name='exam_v4_page_role_idx',
            ),
            models.Index(
                fields=['document', 'display_order'],
                name='exam_v4_page_order_idx',
            ),
        ]
        ordering = ['page_number']

    def save(self, *args, **kwargs) -> None:
        if not self.display_order:
            self.display_order = self.page_number
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        if self.display_order and self.display_order < 1:
            raise ValidationError(
                {'display_order': 'Virtual display order must be positive.'}
            )
        if self.duplicate_of_id:
            own_project_id = self.document.project_id
            duplicate_project_id = self.duplicate_of.document.project_id
            if own_project_id != duplicate_project_id:
                raise ValidationError(
                    {'duplicate_of': 'Duplicate pages must belong to the same exam project.'}
                )

    @property
    def effective_role(self) -> str:
        return self.teacher_role or self.predicted_role

    def __str__(self) -> str:
        return f'ExamSourcePage<{self.document_id}:{self.page_number}@{self.display_order}>'


class ExamSourceSegment(models.Model):
    """A virtual, contiguous page range routed to one specialized pipeline."""

    class Status(models.TextChoices):
        PROPOSED = 'proposed', 'Proposed'
        CONFIRMED = 'confirmed', 'Confirmed'
        PROCESSING = 'processing', 'Processing'
        COMPLETE = 'complete', 'Complete'
        FAILED = 'failed', 'Failed'
        SUPERSEDED = 'superseded', 'Superseded'

    document = models.ForeignKey(
        ExamSourceDocument,
        on_delete=models.CASCADE,
        related_name='segments',
    )
    revision = models.PositiveIntegerField(default=1)
    order = models.PositiveIntegerField(default=0)
    start_page = models.PositiveIntegerField()
    end_page = models.PositiveIntegerField()
    role = models.CharField(
        max_length=32,
        choices=ExamSourceRole.choices,
        default=ExamSourceRole.UNKNOWN,
        db_index=True,
    )
    predicted_role = models.CharField(
        max_length=32,
        choices=ExamSourceRole.choices,
        default=ExamSourceRole.UNKNOWN,
    )
    predicted_confidence = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=0,
    )
    teacher_confirmed = models.BooleanField(default=False)
    section_key = models.CharField(max_length=160, blank=True, default='')
    expected_number_start = models.PositiveIntegerField(null=True, blank=True)
    expected_number_end = models.PositiveIntegerField(null=True, blank=True)
    fingerprint = models.CharField(max_length=64, blank=True, default='')
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PROPOSED,
        db_index=True,
    )
    metadata = models.JSONField(default=dict, blank=True)
    error_code = models.CharField(max_length=64, blank=True, default='')
    error_detail = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['document', 'revision', 'order'],
                name='uniq_exam_v4_segment_order',
            ),
            models.CheckConstraint(
                condition=Q(revision__gte=1),
                name='exam_v4_segment_revision_gte_1',
            ),
            models.CheckConstraint(
                condition=Q(start_page__gte=1),
                name='exam_v4_segment_start_gte_1',
            ),
            models.CheckConstraint(
                condition=Q(end_page__gte=1),
                name='exam_v4_segment_end_gte_1',
            ),
            models.CheckConstraint(
                condition=Q(predicted_confidence__gte=0)
                & Q(predicted_confidence__lte=1),
                name='exam_v4_segment_conf_range',
            ),
            models.CheckConstraint(
                condition=(
                    Q(expected_number_start__isnull=True)
                    | Q(expected_number_end__isnull=True)
                    | Q(expected_number_end__gte=F('expected_number_start'))
                ),
                name='exam_v4_segment_number_range',
            ),
        ]
        indexes = [
            models.Index(
                fields=['document', 'revision', 'role', 'order'],
                name='exam_v4_segment_role_idx',
            ),
            models.Index(
                fields=['status', 'updated_at'],
                name='exam_v4_segment_status_idx',
            ),
        ]
        ordering = ['revision', 'order', 'id']

    def clean(self) -> None:
        super().clean()
        if self.document_id and self.document.page_count:
            if self.start_page > self.document.page_count:
                raise ValidationError(
                    {'start_page': 'Segment start page must belong to the source document.'}
                )
            if self.end_page > self.document.page_count:
                raise ValidationError(
                    {'end_page': 'Segment end page must belong to the source document.'}
                )

    def __str__(self) -> str:
        return (
            f'ExamSourceSegment<{self.document_id}:'
            f'{self.start_page}->{self.end_page}:{self.role}>'
        )
