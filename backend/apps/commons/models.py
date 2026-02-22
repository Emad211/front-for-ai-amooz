"""Token usage tracking for all LLM calls."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class LLMUsageLog(models.Model):
    """Logs every LLM API call with token counts and estimated cost."""

    class Feature(models.TextChoices):
        # Pipeline steps
        TRANSCRIPTION = 'transcription', 'Transcription'
        STRUCTURE = 'structure', 'Structure'
        PREREQ_EXTRACT = 'prereq_extract', 'Prerequisite Extraction'
        PREREQ_TEACH = 'prereq_teach', 'Prerequisite Teaching'
        RECAP = 'recap', 'Recap Generation'
        EXAM_PREP_STRUCTURE = 'exam_prep_structure', 'Exam Prep Structure'
        # Quiz / Exam
        QUIZ_GENERATION = 'quiz_generation', 'Quiz Generation'
        QUIZ_GRADING = 'quiz_grading', 'Quiz Grading'
        FINAL_EXAM_GENERATION = 'final_exam_generation', 'Final Exam Generation'
        HINT_GENERATION = 'hint_generation', 'Hint Generation'
        # Chatbot
        CHAT_COURSE = 'chat_course', 'Course Chat'
        CHAT_EXAM_PREP = 'chat_exam_prep', 'Exam Prep Chat'
        CHAT_INTENT = 'chat_intent', 'Chat Intent Classifier'
        CHAT_WIDGET = 'chat_widget', 'Chat Widget'
        CHAT_VISION = 'chat_vision', 'Chat Vision'
        MEMORY_SUMMARY = 'memory_summary', 'Memory Summarization'
        JSON_REPAIR = 'json_repair', 'JSON Repair'
        # Other
        OTHER = 'other', 'Other'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='llm_usage_logs',
        db_index=True,
    )
    feature = models.CharField(
        max_length=30,
        choices=Feature.choices,
        default=Feature.OTHER,
        db_index=True,
    )
    provider = models.CharField(max_length=20, default='unknown')
    model_name = models.CharField(max_length=100, default='unknown')

    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)

    # Type-specific token counts for precise cost calculation
    audio_input_tokens = models.PositiveIntegerField(
        default=0, help_text='Audio input tokens (charged at audio rate)'
    )
    cached_input_tokens = models.PositiveIntegerField(
        default=0, help_text='Cached input tokens (text/image/video + audio)'
    )
    thinking_tokens = models.PositiveIntegerField(
        default=0, help_text='Thinking/reasoning tokens (charged as output)'
    )

    # Estimated cost in USD (based on model pricing)
    estimated_cost_usd = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=0,
    )

    # Optional context
    session_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    detail = models.CharField(max_length=200, blank=True, default='')

    duration_ms = models.PositiveIntegerField(default=0, help_text='LLM call duration in milliseconds')

    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['feature', 'created_at']),
            models.Index(fields=['session_id', 'created_at']),
        ]

    def __str__(self) -> str:
        username = self.user.username if self.user else 'system'
        return f'{username} | {self.feature} | {self.total_tokens} tokens | ${self.estimated_cost_usd}'


# ---------------------------------------------------------------------------
# Pricing table (per 1M tokens, USD) — Gemini 2.5 Flash (2025-06)
# ---------------------------------------------------------------------------

MODEL_PRICING: dict[str, dict[str, float]] = {
    # Google Gemini 2.5 Flash — official pricing
    'models/gemini-2.5-flash': {
        'input': 0.30,           # text / image / video input
        'audio_input': 1.00,     # audio input
        'output': 2.50,          # output (including thinking tokens)
        'input_cached': 0.03,    # cached text / image / video
        'audio_input_cached': 0.10,  # cached audio
    },
    'gemini-2.5-flash': {
        'input': 0.30,
        'audio_input': 1.00,
        'output': 2.50,
        'input_cached': 0.03,
        'audio_input_cached': 0.10,
    },
    # Gemini 2.0 Flash
    'models/gemini-2.0-flash': {'input': 0.10, 'output': 0.40},
    'gemini-2.0-flash': {'input': 0.10, 'output': 0.40},
    # Gemini 2.0 Flash Lite
    'models/gemini-2.0-flash-lite': {'input': 0.075, 'output': 0.30},
    'gemini-2.0-flash-lite': {'input': 0.075, 'output': 0.30},
    # Gemini 1.5 Flash
    'models/gemini-1.5-flash': {'input': 0.075, 'output': 0.30},
    'gemini-1.5-flash': {'input': 0.075, 'output': 0.30},
    # Gemini 1.5 Pro
    'models/gemini-1.5-pro': {'input': 1.25, 'output': 5.00},
    'gemini-1.5-pro': {'input': 1.25, 'output': 5.00},
}

# Default fallback pricing (conservative)
DEFAULT_PRICING = {'input': 0.30, 'output': 2.50}


def estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    *,
    audio_input_tokens: int = 0,
    cached_input_tokens: int = 0,
    audio_cached_tokens: int = 0,
) -> float:
    """Return estimated cost in USD for a given LLM call.

    Differentiates between text/image/video input, audio input, cached
    input, and output tokens using per-model pricing from MODEL_PRICING.
    """
    pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)
    per_m = 1_000_000

    # Text/image/video input (subtract audio and cached from total)
    text_input = max(0, input_tokens - audio_input_tokens - cached_input_tokens)
    cost = text_input * pricing.get('input', 0.30) / per_m

    # Audio input
    cost += audio_input_tokens * pricing.get('audio_input', pricing.get('input', 0.30)) / per_m

    # Cached text/image/video
    text_cached = max(0, cached_input_tokens - audio_cached_tokens)
    cost += text_cached * pricing.get('input_cached', pricing.get('input', 0.30) * 0.1) / per_m

    # Cached audio
    cost += audio_cached_tokens * pricing.get('audio_input_cached', pricing.get('audio_input', pricing.get('input', 0.30)) * 0.1) / per_m

    # Output (including thinking tokens)
    cost += output_tokens * pricing.get('output', 2.50) / per_m

    return round(cost, 8)


# ---------------------------------------------------------------------------
# Support Tickets
# ---------------------------------------------------------------------------

TICKET_DEPARTMENTS = [
    ('technical', 'پشتیبانی فنی'),
    ('education', 'آموزش'),
    ('financial', 'مالی'),
    ('suggestions', 'پیشنهادات'),
    ('other', 'سایر'),
]

DEPARTMENT_LABELS = dict(TICKET_DEPARTMENTS)


class Ticket(models.Model):
    """Support ticket opened by any user."""

    class Status(models.TextChoices):
        OPEN = 'open', 'باز'
        PENDING = 'pending', 'در انتظار'
        ANSWERED = 'answered', 'پاسخ داده شده'
        CLOSED = 'closed', 'بسته شده'

    class Priority(models.TextChoices):
        LOW = 'low', 'کم'
        MEDIUM = 'medium', 'متوسط'
        HIGH = 'high', 'زیاد'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tickets',
    )
    subject = models.CharField(max_length=255)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    priority = models.CharField(
        max_length=16,
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )
    department = models.CharField(
        max_length=32,
        choices=TICKET_DEPARTMENTS,
        default='other',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self) -> str:
        return f'TKT-{self.pk:03d} {self.subject}'


class TicketMessage(models.Model):
    """Single message inside a ticket thread."""

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='messages')
    content = models.TextField()
    is_admin = models.BooleanField(default=False)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']


# ---------------------------------------------------------------------------
# Admin key/value settings
# ---------------------------------------------------------------------------

class AdminSetting(models.Model):
    """Simple key-value store for admin-configurable settings."""

    key = models.CharField(max_length=100, unique=True)
    value = models.TextField(default='')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.key

    # ---------- helpers ----------

    DEFAULTS: dict[str, str] = {
        'auto_backup': 'true',
        'backup_window': '03:00-04:00',
        'backup_retention_days': '14',
        'maintenance_auto_approve': 'false',
        'alert_email': '',
    }

    @classmethod
    def get(cls, key: str) -> str:
        try:
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            return cls.DEFAULTS.get(key, '')

    @classmethod
    def get_all(cls) -> dict[str, str]:
        stored = {s.key: s.value for s in cls.objects.all()}
        merged = {**cls.DEFAULTS, **stored}
        return merged

    @classmethod
    def set_many(cls, data: dict[str, str]) -> None:
        for key, val in data.items():
            cls.objects.update_or_create(key=key, defaults={'value': str(val)})
