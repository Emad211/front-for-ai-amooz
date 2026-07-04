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
        PDF_EXTRACTION = 'pdf_extraction', 'PDF Extraction (Vision)'
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
        CHAT_SYSTEM_PROMPT = 'chat_system_prompt', 'Chat System Prompt'
        MEMORY_SUMMARY = 'memory_summary', 'Memory Summarization'
        # Chat widgets / learning tools
        FLASH_CARDS = 'flash_cards', 'Flash Cards'
        FETCH_QUIZZES = 'fetch_quizzes', 'Quiz Widget'
        MATCH_GAMES = 'match_games', 'Match Game'
        PRACTICE_TESTS = 'practice_tests', 'Practice Test'
        MERIL = 'meril', 'Merrill Content'
        NOTES_AI = 'notes_ai', 'AI Notes'
        IMAGE_PLAN = 'image_plan', 'Image Plan'
        EXAM_PREP_HANDWRITING_VISION = 'exam_prep_handwriting_vision', 'Exam Prep Handwriting Vision'
        JSON_REPAIR = 'json_repair', 'JSON Repair'
        # Exercise Hub (docs/features/exercise-hub.md)
        EXERCISE_INGEST = 'exercise_ingest', 'Exercise Ingest (Vision/PDF)'
        EXERCISE_STRUCTURE = 'exercise_structure', 'Exercise Structure'
        EXERCISE_GRADING = 'exercise_grading', 'Exercise Grading'
        EXERCISE_HANDWRITING_VISION = 'exercise_handwriting_vision', 'Exercise Handwriting Vision'
        CHAT_EXERCISE = 'chat_exercise', 'Exercise Assistant Chat'
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
        max_length=40,
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

    # Estimated cost in Toman, snapshotted at write time using the live
    # USD→Toman rate so historical totals never drift with today's FX.
    estimated_cost_toman = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text='Cost in Toman, computed at call time from the live USD rate.',
    )
    # The USD→Toman rate that was applied for this row (audit trail).
    usd_toman_rate = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text='USDT→Toman rate applied when this row was written.',
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
            # Hot path for the per-user × per-task breakdown over a date range.
            models.Index(fields=['user', 'feature', 'created_at'], name='idx_llm_user_feat_created'),
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


def _strip_models_prefix(name: str) -> str:
    """Drop a leading 'models/' so DB and hardcoded keys match the wire model."""
    name = name or ''
    return name[7:] if name.startswith('models/') else name


class ModelPrice(models.Model):
    """Admin-editable per-model price table (USD per 1M tokens).

    Cost is computed in USD from these rates, then converted to Toman at
    call time using the live exchange rate.  This lets an admin update the
    real Avalai rates from the panel without a redeploy.  Lookup picks the
    active row with the latest ``effective_from`` for a (provider, model);
    a blank ``provider`` row acts as a fallback for any provider.
    """

    provider = models.CharField(
        max_length=32,
        blank=True,
        default='',
        help_text="Provider key (e.g. 'avalai', 'gapgpt', 'gemini'). Blank = any provider.",
    )
    model_name = models.CharField(
        max_length=100,
        help_text="Model name without the 'models/' prefix, e.g. 'gemini-2.5-flash'.",
    )

    input_usd_per_1m = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    output_usd_per_1m = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    audio_input_usd_per_1m = models.DecimalField(
        max_digits=12, decimal_places=6, null=True, blank=True,
    )
    cached_input_usd_per_1m = models.DecimalField(
        max_digits=12, decimal_places=6, null=True, blank=True,
    )

    is_active = models.BooleanField(default=True, db_index=True)
    effective_from = models.DateTimeField(default=timezone.now, db_index=True)
    note = models.CharField(max_length=255, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['provider', 'model_name', '-effective_from']
        constraints = [
            models.UniqueConstraint(
                fields=['provider', 'model_name', 'effective_from'],
                name='uniq_model_price_provider_model_effective',
            ),
        ]

    def __str__(self) -> str:
        prov = self.provider or 'any'
        return f'{prov}:{self.model_name} (in={self.input_usd_per_1m}, out={self.output_usd_per_1m})'

    def as_pricing_dict(self) -> dict[str, float]:
        d: dict[str, float] = {
            'input': float(self.input_usd_per_1m or 0),
            'output': float(self.output_usd_per_1m or 0),
        }
        if self.audio_input_usd_per_1m is not None:
            d['audio_input'] = float(self.audio_input_usd_per_1m)
        if self.cached_input_usd_per_1m is not None:
            d['input_cached'] = float(self.cached_input_usd_per_1m)
        return d

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        invalidate_price_cache()

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        invalidate_price_cache()


# ---------------------------------------------------------------------------
# Price resolution (DB-backed, cached) with hardcoded fallback
# ---------------------------------------------------------------------------

_PRICE_CACHE_KEY = 'llm_model_price_table_v1'
_PRICE_CACHE_TTL = 60  # seconds


def invalidate_price_cache() -> None:
    """Drop the in-process price table cache (called on ModelPrice writes)."""
    try:
        from django.core.cache import cache
        cache.delete(_PRICE_CACHE_KEY)
    except Exception:
        pass


def _load_price_table() -> dict[tuple[str, str], dict[str, float]]:
    """Return active ModelPrice rows as a lookup, cached briefly.

    Keys are ``(provider_lower, model_key)`` and ``('', model_key)``; later
    ``effective_from`` rows override earlier ones.  Returns ``{}`` if the DB
    is unavailable (e.g. during initial migrations) so callers fall back to
    the hardcoded table.
    """
    try:
        from django.core.cache import cache
    except Exception:
        cache = None

    if cache is not None:
        try:
            cached = cache.get(_PRICE_CACHE_KEY)
            if cached is not None:
                return cached
        except Exception:
            cache = None  # cache backend unavailable — skip caching entirely

    table: dict[tuple[str, str], dict[str, float]] = {}
    try:
        now = timezone.now()
        rows = (
            ModelPrice.objects
            .filter(is_active=True, effective_from__lte=now)
            .order_by('effective_from')
        )
        for row in rows:
            pricing = row.as_pricing_dict()
            model_key = _strip_models_prefix(row.model_name)
            table[('', model_key)] = pricing
            if row.provider:
                table[(row.provider.lower(), model_key)] = pricing
    except Exception:
        return {}

    if cache is not None:
        try:
            cache.set(_PRICE_CACHE_KEY, table, _PRICE_CACHE_TTL)
        except Exception:
            pass
    return table


def get_pricing(model: str, provider: str = '') -> dict[str, float]:
    """Resolve the pricing dict for a (model, provider), DB first then code."""
    model_key = _strip_models_prefix(model)
    table = _load_price_table()
    prov = (provider or '').lower()

    if prov and (prov, model_key) in table:
        return table[(prov, model_key)]
    if ('', model_key) in table:
        return table[('', model_key)]

    # Hardcoded fallback (try both prefixed and stripped keys).
    if model in MODEL_PRICING:
        return MODEL_PRICING[model]
    if model_key in MODEL_PRICING:
        return MODEL_PRICING[model_key]
    return DEFAULT_PRICING


def estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    *,
    provider: str = '',
    audio_input_tokens: int = 0,
    cached_input_tokens: int = 0,
    audio_cached_tokens: int = 0,
) -> float:
    """Return estimated cost in USD for a given LLM call.

    Differentiates between text/image/video input, audio input, cached
    input, and output tokens using per-model pricing resolved from the
    DB price table (``ModelPrice``) with a hardcoded fallback.  Output
    already includes thinking/reasoning tokens for both Gemini and OpenAI.
    """
    pricing = get_pricing(model, provider)
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
