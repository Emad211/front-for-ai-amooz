from django.conf import settings
from django.db import models
from django.db.models import UniqueConstraint
import uuid


class ClassCreationSession(models.Model):
    class Status(models.TextChoices):
        TRANSCRIBING = 'transcribing', 'Transcribing'
        TRANSCRIBED = 'transcribed', 'Transcribed'
        STRUCTURING = 'structuring', 'Structuring'
        STRUCTURED = 'structured', 'Structured'
        PREREQ_EXTRACTING = 'prereq_extracting', 'Prerequisites: Extracting'
        PREREQ_EXTRACTED = 'prereq_extracted', 'Prerequisites: Extracted'
        PREREQ_TEACHING = 'prereq_teaching', 'Prerequisites: Teaching'
        PREREQ_TAUGHT = 'prereq_taught', 'Prerequisites: Taught'
        FAILED = 'failed', 'Failed'

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='class_creation_sessions',
    )

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    source_file = models.FileField(upload_to='class_creation/source/')
    source_mime_type = models.CharField(max_length=127, blank=True)
    source_original_name = models.CharField(max_length=255, blank=True)

    status = models.CharField(max_length=32, choices=Status.choices, default=Status.TRANSCRIBING)

    transcript_markdown = models.TextField(blank=True)

    # Client-provided id for retry safety (frontend/network retries).
    client_request_id = models.UUIDField(null=True, blank=True, default=None)

    structure_json = models.TextField(blank=True)
    llm_provider = models.CharField(max_length=32, blank=True)
    llm_model = models.CharField(max_length=128, blank=True)

    # When published, the session becomes visible as an active class (MVP).
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)

    error_detail = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.id} ({self.status})"

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=['teacher', 'client_request_id'],
                name='uniq_class_creation_teacher_client_request_id',
            )
        ]


class ClassInvitation(models.Model):
    session = models.ForeignKey(
        ClassCreationSession,
        on_delete=models.CASCADE,
        related_name='invites',
    )
    phone = models.CharField(max_length=32)
    invite_code = models.CharField(max_length=64)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.session_id}:{self.phone}"

    class Meta:
        constraints = [
            UniqueConstraint(fields=['session', 'phone'], name='uniq_class_invite_session_phone'),
            UniqueConstraint(fields=['session', 'invite_code'], name='uniq_class_invite_session_code'),
        ]


class ClassLearningObjective(models.Model):
    session = models.ForeignKey(
        ClassCreationSession,
        on_delete=models.CASCADE,
        related_name='learning_objectives',
    )
    order = models.PositiveIntegerField()
    text = models.TextField()

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=['session', 'order'],
                name='uniq_class_objective_session_order',
            ),
        ]


class ClassSection(models.Model):
    session = models.ForeignKey(
        ClassCreationSession,
        on_delete=models.CASCADE,
        related_name='sections',
    )
    external_id = models.CharField(max_length=128)
    order = models.PositiveIntegerField()
    title = models.CharField(max_length=255)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=['session', 'external_id'],
                name='uniq_class_section_session_external_id',
            ),
        ]


class ClassUnit(models.Model):
    session = models.ForeignKey(
        ClassCreationSession,
        on_delete=models.CASCADE,
        related_name='units',
    )
    section = models.ForeignKey(
        ClassSection,
        on_delete=models.CASCADE,
        related_name='units',
    )
    external_id = models.CharField(max_length=128)
    order = models.PositiveIntegerField()
    title = models.CharField(max_length=255)
    merrill_type = models.CharField(max_length=64, blank=True)
    source_markdown = models.TextField(blank=True)
    content_markdown = models.TextField(blank=True)
    image_ideas = models.JSONField(default=list, blank=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=['session', 'external_id'],
                name='uniq_class_unit_session_external_id',
            ),
        ]


class ClassPrerequisite(models.Model):
    session = models.ForeignKey(
        ClassCreationSession,
        on_delete=models.CASCADE,
        related_name='prerequisites',
    )
    order = models.PositiveIntegerField()
    name = models.CharField(max_length=255)
    teaching_text = models.TextField(blank=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=['session', 'order'],
                name='uniq_class_prereq_session_order',
            ),
            UniqueConstraint(
                fields=['session', 'name'],
                name='uniq_class_prereq_session_name',
            ),
        ]
