from __future__ import annotations

from typing import Any


WORKFLOW_STAGE_PROGRESS = {
    'queued': 5,
    'reading_sources': 20,
    'ocr_and_transcription': 40,
    'extracting_questions': 60,
    'matching_reference_answers': 80,
    'building_review_draft': 95,
    'ready_for_review': 100,
    'failed': 0,
}

WORKFLOW_STAGE_MESSAGE = {
    'queued': 'در صف ساخت پیش‌نویس تمرین قرار گرفت.',
    'reading_sources': 'منابع تمرین دریافت شد و در حال آماده‌سازی است.',
    'ocr_and_transcription': 'در حال خواندن فایل‌ها و تبدیل آن‌ها به متن هستیم.',
    'extracting_questions': 'در حال استخراج سوال‌ها و ساختار تمرین هستیم.',
    'matching_reference_answers': 'در حال تطبیق پاسخ‌های مرجع با سوال‌ها هستیم.',
    'building_review_draft': 'در حال ساخت پیش‌نویس قابل بازبینی هستیم.',
    'ready_for_review': 'پیش‌نویس تمرین آمادهٔ بازبینی است.',
    'failed': 'در ساخت پیش‌نویس تمرین خطا رخ داد.',
}

SOURCE_ROLE_AUTO = 'auto'
SOURCE_ROLE_QUESTION_ONLY = 'question_only'
SOURCE_ROLE_QUESTION_AND_ANSWER = 'question_and_answer'
SOURCE_ROLE_ANSWER_ONLY = 'answer_only'
SOURCE_ROLE_CHOICES = {
    SOURCE_ROLE_AUTO,
    SOURCE_ROLE_QUESTION_ONLY,
    SOURCE_ROLE_QUESTION_AND_ANSWER,
    SOURCE_ROLE_ANSWER_ONLY,
}

WRITING_MODE_AUTO = 'auto'
WRITING_MODE_TYPED = 'typed'
WRITING_MODE_HANDWRITTEN = 'handwritten'
WRITING_MODE_MIXED = 'mixed'
WRITING_MODE_CHOICES = {
    WRITING_MODE_AUTO,
    WRITING_MODE_TYPED,
    WRITING_MODE_HANDWRITTEN,
    WRITING_MODE_MIXED,
}

ANSWER_LAYOUT_AUTO = 'auto'
ANSWER_LAYOUT_INLINE = 'inline'
ANSWER_LAYOUT_END = 'end'
ANSWER_LAYOUT_SEPARATE = 'separate'
ANSWER_LAYOUT_CHOICES = {
    ANSWER_LAYOUT_AUTO,
    ANSWER_LAYOUT_INLINE,
    ANSWER_LAYOUT_END,
    ANSWER_LAYOUT_SEPARATE,
}


def _clean_warning_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = str(item or '').strip()
        if text:
            out.append(text)
    return out


def normalize_workflow_state(value: Any) -> dict[str, Any]:
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
    }


def build_workflow_state(
    stage: str,
    *,
    message: str | None = None,
    warnings: list[str] | None = None,
    ready_for_review: bool | None = None,
) -> dict[str, Any]:
    if stage not in WORKFLOW_STAGE_PROGRESS:
        raise ValueError(f'unknown workflow stage: {stage}')
    state = normalize_workflow_state({'stage': stage})
    if message is not None:
        state['message'] = str(message).strip() or WORKFLOW_STAGE_MESSAGE[stage]
    if warnings is not None:
        state['warnings'] = _clean_warning_list(warnings)
    if ready_for_review is not None:
        state['readyForReview'] = bool(ready_for_review)
    return state


def update_workflow_state(
    exercise,
    stage: str,
    *,
    message: str | None = None,
    warnings: list[str] | None = None,
    ready_for_review: bool | None = None,
    save: bool = True,
) -> dict[str, Any]:
    state = build_workflow_state(
        stage,
        message=message,
        warnings=warnings,
        ready_for_review=ready_for_review,
    )
    exercise.workflow_state = state
    if save:
        exercise.save(update_fields=['workflow_state', 'updated_at'])
    return state


def serialize_workflow_fields(exercise) -> dict[str, Any]:
    state = normalize_workflow_state(getattr(exercise, 'workflow_state', None))
    notified_at = getattr(exercise, 'review_ready_notified_at', None)
    return {
        'workflowStage': state['stage'],
        'workflowMessage': state['message'],
        'progressPercent': state['progressPercent'],
        'workflowWarnings': state['warnings'],
        'readyForReview': state['readyForReview'],
        'reviewReadyNotifiedAt': notified_at.isoformat() if notified_at else None,
    }


def normalize_source_config(item: dict[str, Any], *, asset_order: int, asset_name: str, asset_kind: str) -> dict[str, Any]:
    role = str(item.get('role') or SOURCE_ROLE_AUTO)
    writing_mode = str(item.get('writingMode') or item.get('writing_mode') or WRITING_MODE_AUTO)
    answer_layout = str(item.get('answerLayout') or item.get('answer_layout') or ANSWER_LAYOUT_AUTO)
    return {
        'clientFileKey': str(item.get('clientFileKey') or '').strip(),
        'assetOrder': asset_order,
        'assetName': asset_name,
        'assetKind': asset_kind,
        'role': role if role in SOURCE_ROLE_CHOICES else SOURCE_ROLE_AUTO,
        'writingMode': writing_mode if writing_mode in WRITING_MODE_CHOICES else WRITING_MODE_AUTO,
        'answerLayout': answer_layout if answer_layout in ANSWER_LAYOUT_CHOICES else ANSWER_LAYOUT_AUTO,
    }


def source_entries(intake_config: Any) -> list[dict[str, Any]]:
    if not isinstance(intake_config, dict):
        return []
    raw = intake_config.get('sources')
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def source_orders_for_roles(intake_config: Any, allowed_roles: set[str]) -> list[int]:
    orders: list[int] = []
    for item in source_entries(intake_config):
        try:
            order = int(item.get('assetOrder'))
        except (TypeError, ValueError):
            continue
        role = str(item.get('role') or SOURCE_ROLE_AUTO)
        if role in allowed_roles:
            orders.append(order)
    return sorted(set(orders))
