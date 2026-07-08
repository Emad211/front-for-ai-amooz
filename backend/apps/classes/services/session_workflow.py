from __future__ import annotations

from typing import Any


WORKFLOW_STAGE_PROGRESS = {
    'queued': 5,
    'reading_source': 15,
    'transcribing': 30,
    'structuring': 50,
    'extracting_prerequisites': 65,
    'teaching_prerequisites': 80,
    'building_recap': 92,
    'extracting_questions': 80,
    'ready_for_review': 100,
    'cancelled': 0,
    'failed': 0,
}

WORKFLOW_STAGE_MESSAGE = {
    'queued': 'در صف پردازش قرار گرفت.',
    'reading_source': 'منبع جلسه دریافت شد و در حال آماده‌سازی است.',
    'transcribing': 'در حال تبدیل فایل به متن هستیم.',
    'structuring': 'در حال ساختاردهی محتوای جلسه هستیم.',
    'extracting_prerequisites': 'در حال استخراج پیش‌نیازها هستیم.',
    'teaching_prerequisites': 'در حال تولید آموزش پیش‌نیازها هستیم.',
    'building_recap': 'در حال ساخت جمع‌بندی جلسه هستیم.',
    'extracting_questions': 'در حال استخراج سوالات و پاسخ‌ها هستیم.',
    'ready_for_review': 'پیش‌نویس آمادهٔ بازبینی است.',
    'cancelled': 'پردازش متوقف شد.',
    'failed': 'در پردازش خطا رخ داد.',
}


def _clean_pending_exercises(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            out.append(item)
    return out


def _clean_warning_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = " ".join(str(item or '').split()).strip()
        if text and text not in out:
            out.append(text)
    return out[:6]


def normalize_session_workflow_state(value: Any) -> dict[str, Any]:
    data = value if isinstance(value, dict) else {}
    stage = str(data.get('stage') or 'queued')
    if stage not in WORKFLOW_STAGE_PROGRESS:
        stage = 'queued'
    return {
        'stage': stage,
        'progressPercent': int(data.get('progressPercent') or WORKFLOW_STAGE_PROGRESS[stage]),
        'message': str(data.get('message') or WORKFLOW_STAGE_MESSAGE[stage]),
        'warnings': _clean_warning_list(data.get('warnings')),
        'readyForReview': bool(data.get('readyForReview')) if stage != 'ready_for_review' else True,
        'pendingExercises': _clean_pending_exercises(data.get('pendingExercises')),
    }


def build_session_workflow_state(
    stage: str,
    *,
    message: str | None = None,
    warnings: list[str] | None = None,
    ready_for_review: bool | None = None,
    pending_exercises: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if stage not in WORKFLOW_STAGE_PROGRESS:
        raise ValueError(f'unknown workflow stage: {stage}')
    state = normalize_session_workflow_state({'stage': stage})
    if message is not None:
        state['message'] = str(message).strip() or WORKFLOW_STAGE_MESSAGE[stage]
    if warnings is not None:
        state['warnings'] = _clean_warning_list(warnings)
    if ready_for_review is not None:
        state['readyForReview'] = bool(ready_for_review)
    if pending_exercises is not None:
        state['pendingExercises'] = _clean_pending_exercises(pending_exercises)
    return state


def update_session_workflow_state(
    session,
    stage: str,
    *,
    message: str | None = None,
    warnings: list[str] | None = None,
    ready_for_review: bool | None = None,
    pending_exercises: list[dict[str, Any]] | None = None,
    save: bool = True,
) -> dict[str, Any]:
    state = build_session_workflow_state(
        stage,
        message=message,
        warnings=warnings,
        ready_for_review=ready_for_review,
        pending_exercises=pending_exercises,
    )
    session.workflow_state = state
    if save:
        session.save(update_fields=['workflow_state', 'updated_at'])
    return state


def serialize_session_workflow_fields(session) -> dict[str, Any]:
    state = normalize_session_workflow_state(getattr(session, 'workflow_state', None))
    notified_at = getattr(session, 'review_ready_notified_at', None)
    return {
        'workflowStage': state['stage'],
        'workflowMessage': state['message'],
        'progressPercent': state['progressPercent'],
        'workflowWarnings': state['warnings'],
        'readyForReview': state['readyForReview'],
        'reviewReadyNotifiedAt': notified_at.isoformat() if notified_at else None,
        'pendingExercises': state['pendingExercises'],
    }
