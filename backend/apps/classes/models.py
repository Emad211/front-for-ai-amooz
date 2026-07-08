from django.conf import settings
from django.db import models
from django.db.models import UniqueConstraint
from django.utils import timezone
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
        """True once the reveal window opens (reference answers may be shown).

        Reference-answer reveal is gated on the deadline, NOT on grading, so an
        early submitter cannot see the answers while classmates are still within
        the deadline (owner decision 2026-07-05). A no-deadline exercise has no
        shared window — the caller reveals on the student's own GRADED submission.
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
