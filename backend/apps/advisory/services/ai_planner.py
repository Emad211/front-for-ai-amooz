"""Risman steps 5+6 (wave R3) — the AI plan-draft service.

The single ق۱′ LLM exception inside advisory: an advisor types (or speaks) a
free-form request — «زهرا این هفته روزی دو ساعت ریاضی بخواند» — and the model
returns a structured one-week draft that lands in the existing DRAFT slot.

Contract (roadmap §گام ۵):

* the model may only pick from the student's ACTIVE subject selection — a
  foreign ``subjectId`` is a 400, never a silent rewrite;
* hard caps: dayOffset 0..6, plannedMinutes 15..480 per row, topic ≤200 chars,
  Σ plannedMinutes ≤3600, ≥1 row;
* the draft always lands through :func:`study_plans.save_draft` so every
  planner constraint (ownership of subjects, duplicate rows, engagement start,
  published overlap) applies unchanged — and the result is **always DRAFT,
  never auto-published**;
* provider/parse failures are :class:`AIUnavailable` → the view's pinned 502;
  semantic violations are :class:`AIPlannerError` → 400 with Persian wording;
* voice (step 6) rides the same text path: ``transcribe_media_bytes`` first,
  then everything above. Size capped at 5 MB.
"""

from __future__ import annotations

import json

from django.utils import timezone
from pydantic import BaseModel

from apps.advisory.services import calendar, scope, study_plans
from apps.commons.structured_llm import generate_structured
from apps.commons.llm_prompts import PROMPTS

MAX_PROMPT_CHARS = 2000
MAX_TOTAL_MINUTES = 3600
MIN_ITEM_MINUTES = 15
MAX_ITEM_MINUTES = 480
MAX_VOICE_BYTES = 5 * 1024 * 1024  # 5 MB — voice notes, not lectures

_PLAN_FEATURE = 'ai_plan_draft'


class AIPlannerError(Exception):
    """400 — the request (or the model's answer) violates a pinned rule."""


class AIUnavailable(AIPlannerError):
    """502 — the provider could not be reached or returned unusable output."""

    def __init__(self):
        super().__init__('سرویس هوش مصنوعی در دسترس نیست.')


class AudioMissing(AIPlannerError):
    """400 — ``voice=true`` arrived without an ``audio`` file."""

    def __init__(self):
        super().__init__('فایل صوتی ارسال نشد.')


class AudioTooLarge(AIPlannerError):
    """400 — the uploaded voice note exceeds the 5 MB cap."""

    def __init__(self):
        super().__init__('حجم فایل صوتی حداکثر ۵ مگابایت است.')


# ── Pydantic wire schema (the model's side of the contract) ──────────────────

class _AIPlanItem(BaseModel):
    dayOffset: int
    subjectId: int
    plannedMinutes: int
    topic: str | None = None


class _AIPlanDraft(BaseModel):
    items: list[_AIPlanItem]


def _subject_catalog(engagement) -> list[dict]:
    """The student's ACTIVE selections as ``{id, name}`` — the model's menu."""
    rows = (
        scope.student_subjects(engagement)
        .filter(is_active=True)
        .select_related('subject')
    )
    return [{'id': row.subject_id, 'name': row.subject.name} for row in rows]


def _render_prompt(free_prompt: str, subjects: list[dict], week_start) -> str:
    """Fill the ``ai_plan_draft`` template.

    Sequential ``replace`` (not ``str.format``) on purpose: the template's
    output-schema example contains literal JSON braces that ``format`` would
    choke on. The three placeholders are guarded by test_ai_planner.py.
    """
    return (
        PROMPTS[_PLAN_FEATURE]
        .replace('{week_start_iso}', week_start.isoformat())
        .replace('{free_prompt}', free_prompt)
        .replace('{subjects_json}', json.dumps(subjects, ensure_ascii=False))
    )


def _resolve_draft(payload: _AIPlanDraft, subjects: list[dict]) -> list[dict]:
    """Hard-resolve the model's JSON into ``save_draft`` item dicts.

    Every violation raises a Persian 400 — the model is a draftsman, not an
    authority: it never widens its own caps or invents subjects.
    """
    if not payload.items:
        raise AIPlannerError('هوش مصنوعی هیچ ردیفی پیشنهاد نداد؛ دوباره تلاش کنید.')

    known = {s['id'] for s in subjects}
    items: list[dict] = []
    total = 0
    for raw in payload.items:
        if not (0 <= raw.dayOffset <= 6):
            raise AIPlannerError('روز پیشنهادی باید بین ۰ تا ۶ باشد.')
        if not (MIN_ITEM_MINUTES <= raw.plannedMinutes <= MAX_ITEM_MINUTES):
            raise AIPlannerError('دقیقه‌ی هر ردیف باید بین ۱۵ تا ۴۸۰ باشد.')
        topic = (raw.topic or '').strip()
        if len(topic) > 200:
            raise AIPlannerError('موضوع نمی‌تواند بیش از ۲۰۰ نویسه باشد.')
        if raw.subjectId not in known:
            raise AIPlannerError('هوش مصنوعی فقط مجاز به انتخاب درس‌های شماست.')
        total += raw.plannedMinutes
        if total > MAX_TOTAL_MINUTES:
            raise AIPlannerError('مجموع دقیقه‌های پیشنهادی از سقف هفتگی (۳۶۰۰) گذشت.')
        item = {
            'day_offset': raw.dayOffset,
            'subject_id': raw.subjectId,
            'planned_minutes': raw.plannedMinutes,
            'topic': topic or None,
        }
        # Collapse duplicate (day, subject) rows by keeping the larger block —
        # the planner's duplicate rule stays intact without a second round-trip.
        for existing in items:
            if (
                existing['day_offset'] == item['day_offset']
                and existing['subject_id'] == item['subject_id']
            ):
                existing['planned_minutes'] = max(
                    existing['planned_minutes'], item['planned_minutes']
                )
                existing['topic'] = existing['topic'] or item['topic']
                break
        else:
            items.append(item)
    return items


def _generate(engagement, free_prompt: str, user):
    """Shared text pipeline: prompt → generate_structured → resolve → DRAFT."""
    free_prompt = (free_prompt or '').strip()
    if not free_prompt:
        raise AIPlannerError('متن درخواست را بنویسید.')
    if len(free_prompt) > MAX_PROMPT_CHARS:
        raise AIPlannerError('متن درخواست حداکثر ۲۰۰۰ نویسه است.')

    subjects = _subject_catalog(engagement)
    if not subjects:
        raise AIPlannerError('ابتدا درس‌های دانش‌آموز را انتخاب کنید.')

    week_start = calendar.week_start_of(timezone.localdate())
    prompt = _render_prompt(free_prompt, subjects, week_start)

    try:
        payload = generate_structured(
            schema=_AIPlanDraft,
            messages=[{'role': 'user', 'content': prompt}],
            feature=_PLAN_FEATURE,
            temperature=0.2,
            tracking_context={
                'engagement_id': engagement.pk,
                'user_id': getattr(user, 'pk', None),
            },
        )
    except AIPlannerError:
        raise
    except Exception:
        # Provider outage, timeout, or unrepairable JSON — one message either
        # way; internals are logged inside structured_llm, never re-raised here.
        raise AIUnavailable()

    items = _resolve_draft(payload, subjects)
    try:
        return study_plans.save_draft(
            engagement,
            start_date=week_start,
            duration_days=7,
            items=items,
        )
    except study_plans.StudyPlanError as exc:
        # Planner invariants (start ≥ engagement, overlap with PUBLISHED, …)
        # surface verbatim: the advisor already knows these Persian messages.
        raise AIPlannerError(str(exc))


def draft_plan_from_text(engagement, free_prompt: str, user=None):
    """Step 5 — text request → a DRAFT plan in the engagement's draft slot."""
    return _generate(engagement, free_prompt, user)


def draft_plan_from_voice(engagement, *, data: bytes, mime_type: str, user=None):
    """Step 6 — voice note → transcript → the same text pipeline."""
    if not data:
        raise AudioMissing()
    if len(data) > MAX_VOICE_BYTES:
        raise AudioTooLarge()

    from apps.classes.services.transcription import transcribe_media_bytes

    try:
        transcript, _provider, _model = transcribe_media_bytes(
            data=data,
            mime_type=mime_type or '',
        )
    except AIPlannerError:
        raise
    except Exception:
        raise AIUnavailable()

    transcript = (transcript or '').strip()
    if not transcript:
        raise AIPlannerError('صدای ارسالی قابل تشخیص نبود؛ دوباره تلاش کنید.')
    return _generate(engagement, transcript, user)