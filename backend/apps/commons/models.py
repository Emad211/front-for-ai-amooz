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
# Pricing table (per 1M tokens, USD) — update as rates change
# ---------------------------------------------------------------------------

MODEL_PRICING: dict[str, dict[str, float]] = {
    # Google Gemini
    'models/gemini-2.5-flash': {'input': 0.15, 'output': 0.60},
    'gemini-2.5-flash': {'input': 0.15, 'output': 0.60},
    'models/gemini-2.0-flash': {'input': 0.10, 'output': 0.40},
    'gemini-2.0-flash': {'input': 0.10, 'output': 0.40},
    'models/gemini-2.0-flash-lite': {'input': 0.075, 'output': 0.30},
    'gemini-2.0-flash-lite': {'input': 0.075, 'output': 0.30},
    'models/gemini-1.5-flash': {'input': 0.075, 'output': 0.30},
    'gemini-1.5-flash': {'input': 0.075, 'output': 0.30},
    'models/gemini-1.5-pro': {'input': 1.25, 'output': 5.00},
    'gemini-1.5-pro': {'input': 1.25, 'output': 5.00},
}

# Default fallback pricing (conservative)
DEFAULT_PRICING = {'input': 0.15, 'output': 0.60}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return estimated cost in USD for a given call."""
    pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)
    cost = (input_tokens * pricing['input'] / 1_000_000) + (output_tokens * pricing['output'] / 1_000_000)
    return round(cost, 6)
