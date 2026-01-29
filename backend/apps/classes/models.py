from django.conf import settings
from django.db import models
from django.db.models import UniqueConstraint
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

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='class_creation_sessions',
    )

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Pipeline type: class (5 steps) or exam_prep (2 steps)
    pipeline_type = models.CharField(
        max_length=16,
        choices=PipelineType.choices,
        default=PipelineType.CLASS,
    )

    # Course metadata set by teacher (shown in student Learn header).
    level = models.CharField(max_length=64, blank=True, default='')
    duration = models.CharField(max_length=64, blank=True, default='')

    source_file = models.FileField(upload_to='class_creation/source/')
    source_mime_type = models.CharField(max_length=127, blank=True)
    source_original_name = models.CharField(max_length=255, blank=True)

    status = models.CharField(max_length=32, choices=Status.choices, default=Status.TRANSCRIBING)

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
