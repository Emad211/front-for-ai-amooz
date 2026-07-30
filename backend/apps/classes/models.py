from django.conf import settings
from django.db import models
from django.db.models import UniqueConstraint
from django.utils import timezone
from core.storage_backends import answer_source_storage
import uuid


class ClassCreationSession(models.Model):
    class PipelineType(models.TextChoices):
        CLASS = 'class', 'Class Pipeline'
        EXAM_PREP = 'exam_prep', 'Exam Prep Pipeline'

    class Status(models.TextChoices):
        # Class pipeline statuses (5 steps)
        TRANSCRIBING = 'transcribing', 'Transcribing'
        TRANSCRIBED = 'transcribed', 'Transcribed'
        STRUCTURING = 'structuring', 'Structuring'
        STRUCTURED = 'structured', 'Structured'
        PREREQ_EXTRACTING = 'prereq_extracting', 'Prerequisites: Extracting'
        PREREQ_EXTRACTED = 'prereq_extracted', 'Prerequisites: Extracted'
        PREREQ_TEACHING = 'prereq_teaching', 'Prerequisites: Teaching'
        PREREQ_TAUGHT = 'prereq_taught', 'Prerequisites: Taught'
        RECAPPING = 'recapping', 'Recap: Generating'
        RECAPPED = 'recapped', 'Recap: Ready'
        # Exam prep pipeline statuses (2 steps)
        EXAM_TRANSCRIBING = 'exam_transcribing', 'Exam Prep: Transcribing'
        EXAM_TRANSCRIBED = 'exam_transcribed', 'Exam Prep: Transcribed'
        EXAM_STRUCTURING = 'exam_structuring', 'Exam Prep: Extracting Q&A'
        EXAM_STRUCTURED = 'exam_structured', 'Exam Prep: Ready'
        # Shared
        FAILED = 'failed', 'Failed'
        # Terminal state when the teacher cancels a running pipeline.
        CANCELLED = 'cancelled', 'Cancelled'

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='class_creation_sessions',
    )
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='classes',
        verbose_name='سازمان',
    )
    study_group = models.ForeignKey(
        'organizations.StudyGroup',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='study_group_sessions',
        verbose_name='گروه آموزشی',
        help_text='گروه آموزشی (cohort) که این کلاس/آزمون متعلق به آن است.',
    )

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Pipeline type: class (5 steps) or exam_prep (2 steps)
    pipeline_type = models.CharField(
        max_length=16,
        choices=PipelineType.choices,
        default=PipelineType.CLASS,
        db_index=True,
    )

    # Course metadata set by teacher (shown in student Learn header).
    level = models.CharField(max_length=64, blank=True, default='')
    duration = models.CharField(max_length=64, blank=True, default='')

    # Optional scheduled time for a timed exam-prep session — teacher-set; drives
    # the student calendar (Exercise Hub, docs/features/exercise-hub.md).
    scheduled_at = models.DateTimeField(null=True, blank=True)

    class SourceType(models.TextChoices):
        MEDIA = 'media', 'Media (audio/video)'
        PDF = 'pdf', 'PDF'

    # Ingestion source: media (audio/video transcription) or pdf (hybrid
    # text + vision extraction). Both produce ``transcript_markdown`` so the
    # whole downstream pipeline is source-agnostic.
    source_type = models.CharField(
        max_length=16,
        choices=SourceType.choices,
        default=SourceType.MEDIA,
        db_index=True,
    )
    source_file = models.FileField(upload_to='class_creation/source/')
    source_mime_type = models.CharField(max_length=127, blank=True)
    source_original_name = models.CharField(max_length=255, blank=True)
    # Number of pages for PDF sources (0 for media).
    source_page_count = models.PositiveIntegerField(default=0)

    status = models.CharField(max_length=32, choices=Status.choices, default=Status.TRANSCRIBING, db_index=True)

    transcript_markdown = models.TextField(blank=True)

    # Client-provided id for retry safety (frontend/network retries).
    client_request_id = models.UUIDField(null=True, blank=True, default=None)
    workflow_state = models.JSONField(default=dict, blank=True)
    review_ready_notified_at = models.DateTimeField(null=True, blank=True)
    pending_exercises = models.JSONField(default=list, blank=True)

    structure_json = models.TextField(blank=True)

    # Exam prep specific: extracted Q&A in JSON format
    exam_prep_json = models.TextField(blank=True)

    recap_markdown = models.TextField(blank=True)
    llm_provider = models.CharField(max_length=32, blank=True)
    llm_model = models.CharField(max_length=128, blank=True)

    # When published, the session becomes visible as an active class (MVP).
    is_published = models.BooleanField(default=False, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)

    error_detail = models.TextField(blank=True)

    # --- Pipeline cancellation support -------------------------------------
    # The id of the Celery task currently driving this session's pipeline
    # (full-pipeline coordinator or a single step). Persisted at dispatch so a
    # cancel request can ``app.control.revoke`` the exact running task.
    celery_task_id = models.CharField(max_length=255, blank=True, default='')
    # Cooperative-cancellation flag. The full-pipeline tasks check this at every
    # step boundary and abort gracefully if set — a safety net in case revoke
    # cannot kill an in-flight step (or the task is re-queued by ``acks_late``).
    cancel_requested = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.id} ({self.status})"

    # --- Status groupings ---------------------------------------------------
    # Terminal states: the pipeline is no longer running, so cancellation is a
    # no-op (or invalid). Everything else is an "active"/in-progress state.
    TERMINAL_STATUSES = frozenset({
        Status.RECAPPED,
        Status.EXAM_STRUCTURED,
        Status.FAILED,
        Status.CANCELLED,
    })

    @property
    def is_active_pipeline(self) -> bool:
        """True while the pipeline is still running (i.e. cancellable)."""
        return self.status not in self.TERMINAL_STATUSES

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=['teacher', 'client_request_id'],
                name='uniq_class_creation_teacher_client_request_id',
            )
        ]
        indexes = [
            # Composite index for the hot student list query:
            # filter(is_published=True, pipeline_type=...).order_by('-published_at')
            models.Index(
                fields=['is_published', 'pipeline_type', '-published_at'],
                name='idx_session_pub_type_pubat',
            ),
        ]


class ExamPrepExtractionArtifact(models.Model):
    """Durable, reviewable state for inventory-first exam extraction."""

    class Status(models.TextChoices):
        COLLECTING_PAGES = 'collecting_pages', 'Collecting source pages'
        INVENTORY = 'inventory', 'Building page inventory'
        EXTRACTING = 'extracting', 'Extracting questions and answers'
        MATCHING = 'matching', 'Matching answers'
        VISUALS = 'visuals', 'Processing visuals'
        READY = 'ready', 'Ready for review'
        FAILED = 'failed', 'Failed'

    session = models.OneToOneField(
        ClassCreationSession,
        on_delete=models.CASCADE,
        related_name='exam_extraction_artifact',
    )
    pipeline_version = models.PositiveSmallIntegerField(default=2)
    revision = models.PositiveIntegerField(default=1)
    active_task_id = models.CharField(max_length=255, blank=True, default='')
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.COLLECTING_PAGES,
        db_index=True,
    )
    source_fingerprint = models.CharField(max_length=64, blank=True, default='')
    source_blocks = models.JSONField(default=list, blank=True)
    page_manifest = models.JSONField(default=dict, blank=True)
    question_records = models.JSONField(default=list, blank=True)
    answer_records = models.JSONField(default=list, blank=True)
    audit = models.JSONField(default=dict, blank=True)
    failed_chunks = models.JSONField(default=list, blank=True)
    prompt_version = models.CharField(max_length=32, blank=True, default='')
    provider = models.CharField(max_length=32, blank=True, default='')
    model_name = models.CharField(max_length=128, blank=True, default='')
    error_code = models.CharField(max_length=64, blank=True, default='')
    error_detail = models.TextField(blank=True, default='')
    teacher_reviewed_at = models.DateTimeField(null=True, blank=True)
    teacher_reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_exam_prep_extractions',
    )
    reviewed_revision = models.PositiveIntegerField(null=True, blank=True)
    reviewed_projection_fingerprint = models.CharField(
        max_length=64, blank=True, default=''
    )
    source_retain_until = models.DateTimeField(null=True, blank=True)
    heartbeat_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['status', 'updated_at'], name='exam_art_status_updated_idx'),
        ]


class ExamPrepExtractionUnit(models.Model):
    """One durable, retryable V3 extraction operation."""

    class Stage(models.TextChoices):
        OCR = 'ocr', 'OCR'
        MANIFEST = 'manifest', 'Manifest'
        QUESTIONS = 'questions', 'Questions'
        ANSWERS = 'answers', 'Answers'
        VISUALS = 'visuals', 'Visuals'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        ACCEPTED = 'accepted', 'Accepted'
        RETRYABLE = 'retryable', 'Retryable'
        QUARANTINED = 'quarantined', 'Quarantined'
        FAILED = 'failed', 'Failed'
        SUPERSEDED = 'superseded', 'Superseded'

    artifact = models.ForeignKey(
        ExamPrepExtractionArtifact,
        on_delete=models.CASCADE,
        related_name='units',
    )
    stage = models.CharField(max_length=16, choices=Stage.choices, db_index=True)
    unit_key = models.CharField(max_length=160)
    revision = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    source_page = models.PositiveIntegerField(null=True, blank=True)
    source_timestamp_ms = models.PositiveBigIntegerField(null=True, blank=True)
    source_segment = models.PositiveIntegerField(null=True, blank=True)
    input_fingerprint = models.CharField(max_length=64)
    output_payload = models.JSONField(default=dict, blank=True)
    quality_report = models.JSONField(default=dict, blank=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    processing_task_id = models.CharField(max_length=255, blank=True, default='')
    provider = models.CharField(max_length=32, blank=True, default='')
    model_name = models.CharField(max_length=128, blank=True, default='')
    prompt_version = models.CharField(max_length=32, blank=True, default='')
    response_id = models.CharField(max_length=255, blank=True, default='')
    finish_reason = models.CharField(max_length=64, blank=True, default='')
    input_length = models.PositiveIntegerField(default=0)
    output_length = models.PositiveIntegerField(default=0)
    duration_ms = models.PositiveIntegerField(default=0)
    error_code = models.CharField(max_length=64, blank=True, default='')
    error_detail = models.TextField(blank=True, default='')
    heartbeat_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=['artifact', 'stage', 'unit_key', 'revision'],
                name='uniq_exam_extract_unit_revision',
            ),
        ]
        indexes = [
            models.Index(
                fields=['artifact', 'stage', 'status'],
                name='exam_unit_art_stage_status_idx',
            ),
            models.Index(
                fields=['status', 'heartbeat_at'],
                name='exam_unit_status_heartbeat_idx',
            ),
        ]


class ExamPrepVisualAsset(models.Model):
    """Original source crop and optional generated candidate for one visual."""

    class Role(models.TextChoices):
        QUESTION = 'question', 'Question'
        OPTION = 'option', 'Option'
        SOLUTION = 'solution', 'Solution'

    class Status(models.TextChoices):
        SOURCE_READY = 'source_ready', 'Source crop ready'
        GENERATING = 'generating', 'Generating candidate'
        GENERATED = 'generated', 'Candidate generated'
        VERIFIED = 'verified', 'Candidate verified'
        NEEDS_REVIEW = 'needs_review', 'Needs teacher review'
        FAILED = 'failed', 'Failed'

    class SelectedVariant(models.TextChoices):
        SOURCE = 'source', 'Original source'
        GENERATED = 'generated', 'Generated candidate'

    class SourceKind(models.TextChoices):
        PDF_PAGE = 'pdf_page', 'PDF page'
        VIDEO_FRAME = 'video_frame', 'Video frame'
        SOURCE_IMAGE = 'source_image', 'Source image'

    artifact = models.ForeignKey(
        ExamPrepExtractionArtifact,
        on_delete=models.CASCADE,
        related_name='visual_assets',
    )
    asset_key = models.CharField(max_length=64)
    question_key = models.CharField(max_length=160, blank=True, default='')
    role = models.CharField(max_length=16, choices=Role.choices)
    option_label = models.CharField(max_length=16, blank=True, default='')
    source_kind = models.CharField(max_length=24, choices=SourceKind.choices)
    source_page = models.PositiveIntegerField(null=True, blank=True)
    source_timestamp_ms = models.PositiveBigIntegerField(null=True, blank=True)
    source_bbox = models.JSONField(default=dict, blank=True)
    order = models.PositiveIntegerField(default=0)
    source_file = models.FileField(
        upload_to='exam-prep/visuals/source/',
        storage=answer_source_storage,
    )
    source_content_type = models.CharField(max_length=100, default='image/png')
    source_byte_size = models.PositiveBigIntegerField(default=0)
    source_sha256 = models.CharField(max_length=64)
    generated_file = models.FileField(
        upload_to='exam-prep/visuals/generated/',
        storage=answer_source_storage,
        blank=True,
    )
    generated_content_type = models.CharField(max_length=100, blank=True, default='')
    generated_byte_size = models.PositiveBigIntegerField(default=0)
    generated_sha256 = models.CharField(max_length=64, blank=True, default='')
    alt_text = models.TextField(blank=True, default='')
    visual_spec = models.JSONField(default=dict, blank=True)
    verification = models.JSONField(default=dict, blank=True)
    fingerprint = models.CharField(max_length=64)
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.SOURCE_READY,
        db_index=True,
    )
    selected_variant = models.CharField(
        max_length=16,
        choices=SelectedVariant.choices,
        default=SelectedVariant.SOURCE,
    )
    teacher_approved_generated = models.BooleanField(default=False)
    generation_provider = models.CharField(max_length=32, blank=True, default='')
    generation_model = models.CharField(max_length=128, blank=True, default='')
    generation_prompt_version = models.CharField(max_length=32, blank=True, default='')
    error_detail = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=['artifact', 'asset_key'],
                name='uniq_exam_visual_asset_key',
            ),
        ]
        indexes = [
            models.Index(
                fields=['artifact', 'question_key', 'order'],
                name='exam_visual_question_order_idx',
            ),
            models.Index(
                fields=['source_file'],
                name='exam_visual_src_file_idx',
            ),
            models.Index(
                fields=['generated_file'],
                name='exam_visual_gen_file_idx',
            ),
        ]

class ClassInvitation(models.Model):
    session = models.ForeignKey(
        ClassCreationSession,
        on_delete=models.CASCADE,
        related_name='invites',
    )
    phone = models.CharField(max_length=32, db_index=True)
    invite_code = models.CharField(max_length=64, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.session_id}:{self.phone}"

    class Meta:
        constraints = [
            UniqueConstraint(fields=['session', 'phone'], name='uniq_class_invite_session_phone'),
            UniqueConstraint(fields=['session', 'invite_code'], name='uniq_class_invite_session_code'),
        ]


class StudentInviteCode(models.Model):
    """A permanent invite code per phone number.

    This is the single source of truth for invite codes across all pipelines.
    """

    phone = models.CharField(max_length=32, unique=True)
    code = models.CharField(max_length=64, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.phone}:{self.code}"


class Enrollment(models.Model):
    """A real student↔class link, created when a student joins/opens a class.

    Historically the platform had no enrollment table: a student's class list
    was derived purely from ``ClassInvitation.phone == user.phone`` and teacher
    rosters showed invite rows (phone-as-name, progress hardcoded to 0). This
    model records the actual student User behind an invite, plus a
    ``last_activity_at`` heartbeat so rosters can show real "active/inactive"
    status and join dates. Per-unit completion lives in ``StudentUnitProgress``;
    quiz/exam scores live in their existing per-student tables.
    """

    session = models.ForeignKey(
        ClassCreationSession,
        on_delete=models.CASCADE,
        related_name='enrollments',
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='enrollments',
    )

    joined_at = models.DateTimeField(auto_now_add=True)
    # Heartbeat updated on any meaningful student action (open content, chat,
    # quiz/exam attempt). NULL until the first tracked action. Drives the
    # active/inactive status shown on teacher rosters.
    last_activity_at = models.DateTimeField(null=True, blank=True, db_index=True)

    def __str__(self) -> str:
        return f"{self.session_id}:{self.student_id}"

    class Meta:
        constraints = [
            UniqueConstraint(fields=['session', 'student'], name='uniq_enrollment_session_student'),
        ]
        indexes = [
            models.Index(fields=['student', 'session']),
        ]


class TeacherStudentAccess(models.Model):
    """Teacher-scoped access state without disabling the platform account."""

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='managed_student_access',
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='teacher_access_states',
    )
    is_suspended = models.BooleanField(default=False)
    suspended_at = models.DateTimeField(null=True, blank=True)
    reason = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            UniqueConstraint(fields=['teacher', 'student'], name='uniq_teacher_student_access'),
        ]
        indexes = [models.Index(fields=['teacher', 'is_suspended'], name='classes_tea_teacher_38d252_idx')]

    def __str__(self) -> str:
        return f"{self.teacher_id}:{self.student_id}:{'suspended' if self.is_suspended else 'active'}"


class StudentUnitProgress(models.Model):
    """Per-unit completion for a student inside a class session.

    Keyed by the unit's stable ``external_id`` (e.g. ``"u-1"``) rather than a FK
    to ``ClassUnit`` so it survives structure re-syncs and works directly from
    the structure JSON the student UI renders. ``completedLessons`` for a
    roster = count of these rows; ``totalLessons`` = ``ClassUnit`` count (or the
    unit count parsed from ``structure_json``).
    """

    session = models.ForeignKey(
        ClassCreationSession,
        on_delete=models.CASCADE,
        related_name='unit_progress',
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='unit_progress',
    )
    unit_external_id = models.CharField(max_length=128)

    completed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.session_id}:{self.student_id}:{self.unit_external_id}"

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=['session', 'student', 'unit_external_id'],
                name='uniq_unit_progress_session_student_unit',
            ),
        ]
        indexes = [
            models.Index(fields=['session', 'student']),
        ]


class StudentExamPrepAttempt(models.Model):
    session = models.ForeignKey(
        ClassCreationSession,
        on_delete=models.CASCADE,
        related_name='exam_prep_attempts',
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='exam_prep_attempts',
    )
    answers = models.JSONField(default=dict)
    score_0_100 = models.IntegerField(null=True, blank=True)
    total_questions = models.IntegerField(default=0)
    correct_count = models.IntegerField(default=0)
    finalized = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.session_id}:{self.student_id}:{self.score_0_100}"

    class Meta:
        constraints = [
            UniqueConstraint(fields=['session', 'student'], name='uniq_exam_prep_attempt_session_student'),
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


class ClassAnnouncement(models.Model):
    class Priority(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'

    session = models.ForeignKey(
        ClassCreationSession,
        on_delete=models.CASCADE,
        related_name='announcements',
    )
    title = models.CharField(max_length=255)
    content = models.TextField()
    priority = models.CharField(max_length=16, choices=Priority.choices, default=Priority.MEDIUM)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']


class ClassSectionQuiz(models.Model):
    session = models.ForeignKey(
        ClassCreationSession,
        on_delete=models.CASCADE,
        related_name='section_quizzes',
    )
    section = models.ForeignKey(
        ClassSection,
        on_delete=models.CASCADE,
        related_name='quizzes',
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='class_section_quizzes',
    )

    questions = models.JSONField(default=dict, blank=True)

    last_score_0_100 = models.PositiveIntegerField(null=True, blank=True)
    last_passed = models.BooleanField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=['session', 'section', 'student'],
                name='uniq_class_section_quiz_session_section_student',
            ),
        ]


class ClassSectionQuizAttempt(models.Model):
    quiz = models.ForeignKey(
        ClassSectionQuiz,
        on_delete=models.CASCADE,
        related_name='attempts',
    )

    answers = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict, blank=True)

    score_0_100 = models.PositiveIntegerField()
    passed = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)


class ClassFinalExam(models.Model):
    session = models.ForeignKey(
        ClassCreationSession,
        on_delete=models.CASCADE,
        related_name='final_exams',
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='class_final_exams',
    )

    exam = models.JSONField(default=dict, blank=True)

    last_score_0_100 = models.PositiveIntegerField(null=True, blank=True)
    last_passed = models.BooleanField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=['session', 'student'],
                name='uniq_class_final_exam_session_student',
            ),
        ]


class ClassFinalExamAttempt(models.Model):
    exam = models.ForeignKey(
        ClassFinalExam,
        on_delete=models.CASCADE,
        related_name='attempts',
    )

    answers = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict, blank=True)

    score_0_100 = models.PositiveIntegerField()
    passed = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)


class StudentCourseChatThread(models.Model):
    """A per-student chat thread inside a single class session.

    We keep one thread per (session, student, lesson_id). When lesson_id is NULL,
    this represents a course-level thread.
    """

    session = models.ForeignKey(
        ClassCreationSession,
        on_delete=models.CASCADE,
        related_name='student_chat_threads',
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='student_course_chat_threads',
    )
    lesson_id = models.CharField(max_length=64, blank=True, default='')
    thread_key = models.CharField(max_length=255, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=['session', 'student', 'lesson_id'],
                name='uniq_student_course_chat_thread_session_student_lesson',
            ),
        ]


class StudentCourseChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = 'user', 'User'
        ASSISTANT = 'assistant', 'Assistant'
        SYSTEM = 'system', 'System'

    class MessageType(models.TextChoices):
        TEXT = 'text', 'Text'
        WIDGET = 'widget', 'Widget'

    thread = models.ForeignKey(
        StudentCourseChatThread,
        on_delete=models.CASCADE,
        related_name='messages',
    )

    role = models.CharField(max_length=16, choices=Role.choices)
    message_type = models.CharField(max_length=16, choices=MessageType.choices)

    # For text messages.
    content = models.TextField(blank=True)

    # For widget responses and any structured extra info.
    payload = models.JSONField(default=dict, blank=True)
    suggestions = models.JSONField(default=list, blank=True)

    # Keep the UI context to help grouping and searching later.
    lesson_id = models.CharField(max_length=64, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['thread', 'created_at']),
            models.Index(fields=['lesson_id', 'created_at']),
        ]


# ═══════════════════════════════════════════════════════════════════════════
# Exercise Hub («بخش تمرین») — teacher-authored per-class exercises.
# Design: docs/features/exercise-hub.md · docs/adr/ADR-0004-exercise-hub.md
# All models FK to ClassCreationSession so ownership (teacher), phone-scope
# (student via invites) and the publish gate derive from the parent session.
# ═══════════════════════════════════════════════════════════════════════════


class ClassExercise(models.Model):
    """One teacher-authored exercise attached to a class session.

    Lifecycle: DRAFT → (extract) EXTRACTING → EXTRACTED → (publish) PUBLISHED;
    FAILED is a re-runnable terminal for a failed extraction.
    """

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        EXTRACTING = 'extracting', 'Extracting'
        EXTRACTED = 'extracted', 'Extracted'
        PUBLISHED = 'published', 'Published'
        CANCELLED = 'cancelled', 'Cancelled'
        FAILED = 'failed', 'Failed'

    session = models.ForeignKey(
        ClassCreationSession,
        on_delete=models.CASCADE,
        related_name='exercises',
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True,
    )
    # First real deadline field in the platform. Null = always-open exercise.
    deadline = models.DateTimeField(null=True, blank=True)
    # Whether late submissions are accepted after the deadline (flagged is_late).
    allow_late = models.BooleanField(default=False)
    # Exercise-level assistant switch. Effective per section = this AND section flag.
    assistant_enabled = models.BooleanField(default=True)
    # Snapshot of the teacher's one-step intake payload (kept small on purpose).
    intake_config = models.JSONField(default=dict, blank=True)
    # Durable UI workflow state for the async draft-building flow.
    workflow_state = models.JSONField(default=dict, blank=True)
    # Persisted Celery task id for the extraction run (hard-revoke on re-run).
    extract_task_id = models.CharField(max_length=255, blank=True, default='')
    # Cooperative-cancellation flag for the extraction task; a re-delivered task
    # must see this and stop even if hard revoke missed the running worker child.
    cancel_requested = models.BooleanField(default=False)
    # One-shot ready-for-review notification guard/version for the teacher feed + SMS.
    review_ready_notified_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.session_id}:{self.title}"

    def deadline_passed(self) -> bool:
        """Return whether the configured deadline has elapsed.

        This is only a temporal helper. Callers that reveal reference answers
        must also apply the late-submission policy via the central reveal gate.
        """
        return self.deadline is not None and self.deadline < timezone.now()

    class Meta:
        indexes = [
            models.Index(fields=['session', 'status']),
        ]


class ClassExerciseAsset(models.Model):
    """A source file (PDF or image) uploaded for an exercise's extraction."""

    class Kind(models.TextChoices):
        PDF = 'pdf', 'PDF'
        IMAGE = 'image', 'Image'

    exercise = models.ForeignKey(
        ClassExercise,
        on_delete=models.CASCADE,
        related_name='assets',
    )
    kind = models.CharField(max_length=8, choices=Kind.choices)
    file = models.FileField(upload_to='exercises/source/')
    order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'id']


class ClassExerciseSection(models.Model):
    """A section of an exercise (a group of questions)."""

    exercise = models.ForeignKey(
        ClassExercise,
        on_delete=models.CASCADE,
        related_name='sections',
    )
    order = models.PositiveIntegerField()
    title = models.CharField(max_length=255, blank=True, default='')
    # Section-level assistant switch (AND-ed with the exercise-level flag).
    assistant_enabled = models.BooleanField(default=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=['exercise', 'order'],
                name='uniq_exercise_section_order',
            ),
        ]
        ordering = ['order', 'id']


class ClassExerciseQuestion(models.Model):
    """One question inside a section, with the teacher's reference answer + points."""

    class QuestionType(models.TextChoices):
        DESCRIPTIVE = 'descriptive', 'Descriptive'
        MULTIPLE_CHOICE = 'multiple_choice', 'Multiple Choice'
        FILL_BLANK = 'fill_blank', 'Fill in the Blank'

    section = models.ForeignKey(
        ClassExerciseSection,
        on_delete=models.CASCADE,
        related_name='questions',
    )
    order = models.PositiveIntegerField()
    question_markdown = models.TextField()
    question_type = models.CharField(
        max_length=20, choices=QuestionType.choices, default=QuestionType.DESCRIPTIVE,
    )
    # For MCQ/fill-blank: the option list (deterministic grading uses this).
    options = models.JSONField(default=list, blank=True)
    # The teacher's reference answer — the grading rubric. Mandatory to publish.
    reference_answer_markdown = models.TextField(blank=True, default='')
    max_points = models.DecimalField(max_digits=6, decimal_places=2, default=1)
    grading_notes = models.TextField(blank=True, default='')

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=['section', 'order'],
                name='uniq_exercise_question_order',
            ),
        ]
        ordering = ['order', 'id']


class StudentExerciseSubmission(models.Model):
    """A student's single submission to an exercise (unique per student+exercise)."""

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'  # autosaved, not yet finally submitted
        SUBMITTED = 'submitted', 'Submitted'
        GRADING = 'grading', 'Grading'
        GRADED = 'graded', 'Graded'
        GRADING_FAILED = 'grading_failed', 'Grading Failed'

    exercise = models.ForeignKey(
        ClassExercise,
        on_delete=models.CASCADE,
        related_name='submissions',
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='exercise_submissions',
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.SUBMITTED, db_index=True,
    )
    # {question_id: {text: str, images: [storage_path, ...]}}
    answers = models.JSONField(default=dict, blank=True)
    # {per_question: [{question_id, llm_score, llm_feedback, teacher_score,
    #                  teacher_feedback, max_points, label}]}
    result = models.JSONField(default=dict, blank=True)
    score_points = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    max_points = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    is_late = models.BooleanField(default=False)
    grading_task_id = models.CharField(max_length=255, blank=True, default='')
    graded_at = models.DateTimeField(null=True, blank=True)
    overridden_at = models.DateTimeField(null=True, blank=True)
    current_attempt = models.ForeignKey(
        'StudentExerciseAttempt',
        on_delete=models.SET_NULL,
        related_name='+',
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.exercise_id}:{self.student_id}:{self.status}"

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=['exercise', 'student'],
                name='uniq_exercise_submission_student',
            ),
        ]
        indexes = [
            models.Index(fields=['exercise', 'status']),
            models.Index(fields=['student', 'status']),
        ]


class StudentExerciseAnswerSource(models.Model):
    """Server-owned OCR source for one question or a whole exercise draft."""

    class Scope(models.TextChoices):
        QUESTION = 'question', 'Question'
        EXERCISE = 'exercise', 'Exercise'

    class Status(models.TextChoices):
        QUEUED = 'queued', 'Queued'
        READING = 'reading', 'Reading'
        SEGMENTING = 'segmenting', 'Segmenting'
        MATCHING = 'matching', 'Matching'
        READY = 'ready', 'Ready'
        NEEDS_REVIEW = 'needs_review', 'Needs review'
        FAILED = 'failed', 'Failed'
        SUPERSEDED = 'superseded', 'Superseded'

    submission = models.ForeignKey(
        StudentExerciseSubmission,
        on_delete=models.CASCADE,
        related_name='answer_sources',
    )
    scope = models.CharField(max_length=12, choices=Scope.choices)
    target_question = models.ForeignKey(
        ClassExerciseQuestion,
        on_delete=models.CASCADE,
        related_name='+',
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.QUEUED, db_index=True,
    )
    revision = models.PositiveIntegerField(default=1)
    workflow_state = models.JSONField(default=dict, blank=True)
    source_fingerprint = models.CharField(max_length=80, blank=True, default='')
    raw_result = models.JSONField(default=dict, blank=True)
    reviewed_result = models.JSONField(default=dict, blank=True)
    processor_metadata = models.JSONField(default=dict, blank=True)
    processing_task_id = models.CharField(max_length=255, blank=True, default='')
    error_code = models.CharField(max_length=64, blank=True, default='')
    applied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(scope='question', target_question__isnull=False)
                    | models.Q(scope='exercise', target_question__isnull=True)
                ),
                name='answer_ocr_source_scope_target_valid',
            ),
            models.UniqueConstraint(
                fields=['submission', 'target_question'],
                condition=models.Q(scope='question'),
                name='uniq_question_answer_ocr_source',
            ),
            models.UniqueConstraint(
                fields=['submission'],
                condition=models.Q(scope='exercise'),
                name='uniq_exercise_answer_ocr_source',
            ),
        ]
        indexes = [models.Index(
            fields=['submission', 'status'], name='classes_stu_submiss_4a3ad0_idx',
        )]


class StudentExerciseAnswerAsset(models.Model):
    """Immutable uploaded page belonging to an OCR answer source."""

    source = models.ForeignKey(
        StudentExerciseAnswerSource,
        on_delete=models.CASCADE,
        related_name='assets',
    )
    file = models.FileField(
        upload_to='exercises/answers/sources/',
        storage=answer_source_storage,
    )
    order = models.PositiveIntegerField(default=0)
    content_type = models.CharField(max_length=100)
    byte_size = models.PositiveBigIntegerField(default=0)
    sha256 = models.CharField(max_length=64)
    is_active = models.BooleanField(default=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['source', 'order'], name='uniq_answer_source_asset_order',
            ),
        ]


class StudentExerciseAttempt(models.Model):
    """Immutable snapshot of one finalized exercise submission attempt."""

    class Status(models.TextChoices):
        SUBMITTED = 'submitted', 'Submitted'
        GRADING = 'grading', 'Grading'
        GRADED = 'graded', 'Graded'
        GRADING_FAILED = 'grading_failed', 'Grading Failed'

    submission = models.ForeignKey(
        StudentExerciseSubmission,
        on_delete=models.CASCADE,
        related_name='attempts',
    )
    attempt_number = models.PositiveIntegerField()
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.SUBMITTED,
        db_index=True,
    )
    answers = models.JSONField(default=dict, blank=True)
    question_snapshot = models.JSONField(default=list, blank=True)
    result = models.JSONField(default=dict, blank=True)
    question_fingerprints = models.JSONField(default=dict, blank=True)
    ocr_text = models.JSONField(default=dict, blank=True)
    grader_metadata = models.JSONField(default=dict, blank=True)
    score_points = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    max_points = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    is_late = models.BooleanField(default=False)
    grading_task_id = models.CharField(max_length=255, blank=True, default='')
    graded_at = models.DateTimeField(null=True, blank=True)
    overridden_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.submission_id}:attempt-{self.attempt_number}:{self.status}"

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=['submission', 'attempt_number'],
                name='uniq_exercise_submission_attempt_number',
            ),
            models.CheckConstraint(
                condition=models.Q(attempt_number__gte=1),
                name='exercise_attempt_number_gte_1',
            ),
        ]
        indexes = [
            models.Index(fields=['status', 'updated_at']),
        ]
        ordering = ['attempt_number']
