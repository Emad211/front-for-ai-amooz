from __future__ import annotations

import json
from typing import Any, Optional

from apps.commons.llm_prompts import PROMPTS
from apps.classes.models import ClassCreationSession

from .llm_client import generate_json, generate_text, part_from_bytes
from .memory_service import MemoryService


def _safe_str(value: Any) -> str:
    return ('' if value is None else str(value)).strip()


def _safe_template_replace(template: str, values: dict[str, Any]) -> str:
    out = str(template or '')
    for key, val in (values or {}).items():
        if not isinstance(key, str):
            continue
        out = out.replace('{' + key + '}', str(val))
    return out


def build_exam_thread_id(*, session_id: int, question_id: Optional[str], student_id: int) -> str:
    qid = (question_id or '').strip() or 'root'
    return f'exam-prep:{session_id}:{qid}:{student_id}'


def _load_exam_prep_json(session: ClassCreationSession) -> dict[str, Any]:
    raw = session.exam_prep_json
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    return {}


def _extract_question(*, session: ClassCreationSession, question_id: Optional[str]) -> dict[str, Any]:
    qid = (question_id or '').strip()
    data = _load_exam_prep_json(session)
    exam_prep = data.get('exam_prep') if isinstance(data, dict) else None
    questions = []
    if isinstance(exam_prep, dict):
        questions = exam_prep.get('questions') if isinstance(exam_prep.get('questions'), list) else []
    if not qid:
        return {}
    for q in questions or []:
        if not isinstance(q, dict):
            continue
        cand = str(q.get('question_id') or q.get('id') or '').strip()
        if cand == qid:
            return q
    return {}


def build_exam_question_context(*, session: ClassCreationSession, question_id: Optional[str], is_checked: bool) -> str:
    q = _extract_question(session=session, question_id=question_id)
    if not q:
        return f"Exam Title: {session.title}\nQuestion: <not found>"

    question_text = _safe_str(q.get('question_text_markdown') or q.get('question_text') or q.get('question') or '')
    options_raw = q.get('options')
    options = []
    if isinstance(options_raw, list):
        for opt in options_raw:
            if not isinstance(opt, dict):
                continue
            options.append({
                'label': _safe_str(opt.get('label')),
                'text': _safe_str(opt.get('text_markdown') or opt.get('text') or ''),
            })

    context = "\n".join([
        f"Question ID: {_safe_str(q.get('question_id') or q.get('id') or question_id or 'N/A')}",
        f"Question: {question_text or 'N/A'}",
        f"Options: {json.dumps(options, ensure_ascii=False)}",
    ])

    # Security/UX requirement:
    # Never include the correct answer (or a teacher solution that reveals it) in the LLM context.
    # We only pass correctness as a boolean (is_correct) separately.
    _ = is_checked
    return context


def _history_for_prompt(memory: MemoryService) -> str:
    summary, history_str = memory.get_history_for_llm()
    summary = _safe_str(summary)
    history_str = _safe_str(history_str)
    if summary and history_str:
        return f"SUMMARY:\n{summary}\n\nRECENT:\n{history_str}"
    if summary:
        return f"SUMMARY:\n{summary}"
    return history_str or 'اولین پیام'


def describe_exam_prep_handwriting(*, question_context: str, user_message: str, image_bytes: bytes, mime_type: str) -> str:
    prompt = _safe_template_replace(
        PROMPTS['exam_prep_handwriting_vision']['default'],
        {'question_context': question_context, 'user_message': user_message or '<no caption>'},
    )
    media_part = part_from_bytes(data=image_bytes, mime_type=mime_type)

    obj = generate_json(feature='exam_prep_handwriting_vision', contents=[prompt, media_part])
    description = _safe_str(obj.get('description_markdown'))
    extracted = _safe_str(obj.get('extracted_text_markdown'))
    clean_steps = _safe_str(obj.get('clean_steps_markdown'))

    if description:
        return description

    combined = "\n\n".join([p for p in [extracted, clean_steps] if p])
    if combined:
        return combined

    # Fallback to plain text if JSON parsing failed.
    try:
        return generate_text(contents=[prompt, media_part]).text.strip()
    except Exception:
        return ''


def handle_exam_prep_message(
    *,
    session: ClassCreationSession,
    student_id: int,
    question_id: Optional[str],
    user_message: str,
    student_selected: str = '',
    is_checked: bool = False,
    is_correct: bool = False,
    image_description: str = '',
) -> dict[str, Any]:
    message = _safe_str(user_message)
    if not message:
        return {'type': 'text', 'content': 'پیامت خالیه. لطفاً سوالت رو بنویس.', 'suggestions': []}

    thread_id = build_exam_thread_id(session_id=session.id, question_id=question_id, student_id=student_id)
    memory = MemoryService(thread_id=thread_id)

    if message:
        memory.add(role='user', content=message)
    if image_description:
        memory.add(role='user', content=f"[IMAGE UPLOAD]\n{image_description}")

    question_context = build_exam_question_context(session=session, question_id=question_id, is_checked=is_checked)
    history = _history_for_prompt(memory)

    prompt = _safe_template_replace(
        PROMPTS['exam_prep_chat']['default'],
        {
            'question_context': question_context or '<empty>',
            'student_selected': student_selected or 'هنوز انتخاب نکرده',
            'is_checked': str(bool(is_checked)),
            'is_correct': str(bool(is_correct)),
            'image_description': image_description or 'تصویری ارسال نشده',
            'history': history or 'اولین پیام',
            'user_message': message,
        },
    )

    obj = generate_json(feature='exam_prep_chat', contents=prompt)
    content = _safe_str(obj.get('content'))
    suggestions_raw = obj.get('suggestions')
    suggestions = [s for s in (suggestions_raw or []) if _safe_str(s)] if isinstance(suggestions_raw, list) else []

    if content.startswith('{') and 'content' in content:
        try:
            nested = json.loads(content)
        except Exception:
            nested = None
        if isinstance(nested, dict):
            nested_content = _safe_str(nested.get('content'))
            if nested_content:
                content = nested_content
            nested_suggestions = nested.get('suggestions')
            if isinstance(nested_suggestions, list):
                suggestions = [s for s in nested_suggestions if _safe_str(s)]

    if not content:
        try:
            content = generate_text(contents=prompt).text.strip()
        except Exception:
            content = ''

    if not content:
        content = 'می‌خوای قدم‌به‌قدم با هم پیش بریم؟ ازت یه نکته می‌پرسم تا مسیر حل روشن‌تر بشه.'

    memory.add(role='assistant', content=content)

    return {
        'type': 'text',
        'content': content,
        'suggestions': suggestions,
    }
