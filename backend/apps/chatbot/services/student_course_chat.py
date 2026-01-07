from __future__ import annotations

import json
from typing import Any, Literal, Optional, TypedDict

from apps.commons.llm_prompts import PROMPTS
from apps.classes.models import ClassCreationSession, ClassUnit

from .llm_client import generate_json, generate_text, part_from_bytes
from .memory_service import MemoryService


ChatResponseType = Literal['text', 'widget']


class TextResponse(TypedDict):
    type: Literal['text']
    content: str
    suggestions: list[str]


class WidgetResponse(TypedDict, total=False):
    type: Literal['widget']
    widget_type: str
    data: Any
    text: str
    suggestions: list[str]


ChatResponse = TextResponse | WidgetResponse


DEFAULT_SUGGESTIONS = [
    'مفهومش رو توضیح بده',
    'جزییات بیشتر می‌خواهم',
    'مثال درسی بزن',
]


def _safe_template_replace(template: str, values: dict[str, Any]) -> str:
    """Safely replace `{name}` placeholders without invoking Python's `.format`.

    Prompt templates may contain JSON examples like `{ "intent": ... }`. Using
    `.format(...)` would treat those braces as placeholders and can crash.
    """

    out = str(template or '')
    for key, val in (values or {}).items():
        if not isinstance(key, str):
            continue
        out = out.replace('{' + key + '}', str(val))
    return out


def build_thread_id(*, session_id: int, lesson_id: Optional[str], student_id: int) -> str:
    lid = (lesson_id or 'root').strip() or 'root'
    return f'{session_id}:{lid}:{student_id}'


def _safe_str(x: Any) -> str:
    return ('' if x is None else str(x)).strip()


def build_structured_blocks_json(*, session: ClassCreationSession) -> dict[str, Any]:
    outline: list[dict[str, Any]] = []

    for section in session.sections.order_by('order').prefetch_related('units').all():
        units: list[dict[str, Any]] = []
        for unit in section.units.order_by('order').all():
            units.append(
                {
                    'id': str(unit.id),
                    'title': unit.title,
                    'content_markdown': (unit.content_markdown or unit.source_markdown or '').strip(),
                }
            )
        outline.append(
            {
                'id': (section.external_id or str(section.id)).strip(),
                'title': section.title,
                'units': units,
            }
        )

    return {
        'root_object': {
            'id': 'root',
            'title': session.title,
            'summary': (session.description or '').strip(),
        },
        'outline': outline,
    }


def _get_unit_content(*, session: ClassCreationSession, lesson_id: Optional[str]) -> tuple[str, str]:
    """Return (unit_title, unit_content_markdown)."""
    lid = (lesson_id or '').strip()
    if not lid:
        return session.title, ''

    try:
        unit = ClassUnit.objects.filter(session=session, id=int(lid)).first()
    except Exception:
        unit = None

    if unit is None:
        return session.title, ''

    content = (unit.content_markdown or unit.source_markdown or '').strip()
    return unit.title, content


def _normalize_suggestions(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        s = _safe_str(item)
        if s:
            out.append(s)
    return out


def _tool_widget(*, widget_type: str, data: Any, text: str = '', suggestions: Optional[list[str]] = None) -> WidgetResponse:
    return {
        'type': 'widget',
        'widget_type': widget_type,
        'data': data,
        'text': text,
        'suggestions': suggestions or [],
    }


def _text_response(*, content: str, suggestions: Optional[list[str]] = None) -> TextResponse:
    return {
        'type': 'text',
        'content': content,
        'suggestions': suggestions or [],
    }


def _run_intent_classifier(*, user_message: str) -> str:
    prompt = _safe_template_replace(PROMPTS['chat_intent'], {'user_message': user_message})
    obj = generate_json(feature='chat_intent', contents=prompt)
    intent = _safe_str(obj.get('intent'))
    return intent or 'ask_question'


def _run_chat_system_prompt(*, unit_content: str, history_str: str, user_message: str, student_name: str = '') -> TextResponse:
    prompt = _safe_template_replace(
        PROMPTS['chat_system_prompt'],
        {
            'unit_content': unit_content,
            'history_str': history_str,
            'user_message': user_message,
            'student_name': student_name or 'دانشجو',
        },
    )
    obj = generate_json(feature='chat_system_prompt', contents=prompt)
    content = _safe_str(obj.get('content'))
    suggestions = _normalize_suggestions(obj.get('suggestions'))

    if content:
        return _text_response(content=content, suggestions=suggestions)

    # Fallback: if the provider fails to output JSON, return a best-effort text answer.
    try:
        raw = generate_text(contents=prompt).text
        raw = _safe_str(raw)
        if raw:
            return _text_response(content=raw, suggestions=DEFAULT_SUGGESTIONS)
    except Exception:
        pass

    return _text_response(content='متوجه شدم. سوالت رو یک‌بار کوتاه‌تر می‌گی؟', suggestions=DEFAULT_SUGGESTIONS)


def _run_tool_prompt_json(*, feature: str, strategy: str, payload: dict[str, Any]) -> dict[str, Any]:
    template = PROMPTS[feature][strategy]
    # Some prompts include placeholders like {num_questions} and may also contain JSON
    # braces. We must NOT call Python's `.format` on the full template.
    prompt = _safe_template_replace(str(template), payload)

    if 'STRUCTURED_BLOCKS_JSON' in prompt and isinstance(payload.get('structured_blocks_json'), str):
        prompt = prompt.replace('STRUCTURED_BLOCKS_JSON', payload['structured_blocks_json'])
    if 'UNIT_CONTENT_MARKDOWN' in prompt and isinstance(payload.get('unit_content_markdown'), str):
        prompt = prompt.replace('UNIT_CONTENT_MARKDOWN', payload['unit_content_markdown'])
    # Ensure math is always expressed in LaTeX so frontend KaTeX can render.
    prompt = (
        str(prompt).strip()
        + "\n\nIMPORTANT: For any math/science notation, ALWAYS use LaTeX. Inline: $...$ and display: $$...$$."
    )
    return generate_json(feature=feature, contents=prompt)


def _system_tool_to_widget(feature: str) -> str:
    mapping = {
        'flash_cards': 'flashcard',
        'fetch_quizzes': 'quiz',
        'match_games': 'match_game',
        'practice_tests': 'practice_test',
        'meril': 'scenario',
        'detailed_notes': 'notes',
        'image_plan': 'image',
    }
    return mapping.get(feature, feature)


def handle_student_message(
    *,
    session: ClassCreationSession,
    student_id: int,
    lesson_id: Optional[str],
    user_message: str,
    page_context: str = '',
    page_material: str = '',
    student_name: str = '',
) -> ChatResponse:
    message = (user_message or '').strip()
    if not message:
        return _text_response(content='پیامت خالیه. لطفاً سوالت رو بنویس.', suggestions=[])

    thread_id = build_thread_id(session_id=session.id, lesson_id=lesson_id, student_id=student_id)
    memory = MemoryService(thread_id=thread_id)

    unit_title, unit_content = _get_unit_content(session=session, lesson_id=lesson_id)

    # If the UI sends a richer page_material/context, prioritize it (legacy behavior).
    if (page_material or '').strip():
        unit_content = (page_material or '').strip()
    if (page_context or '').strip():
        unit_content = f"STUDENT_UI_CONTEXT:\n{page_context.strip()}\n\nSTUDENT_IS_READING:\n{unit_content}".strip()

    # Special command protocol (legacy).
    if message.startswith('SYSTEM_UNIT_START:'):
        unit_title = message.split(':', 1)[1].strip() or unit_title
        prompt = _safe_template_replace(PROMPTS['chat_unit_intro']['default'], {'unit_title': unit_title})
        intro = generate_text(contents=prompt).text.strip()
        memory.add(role='assistant', content=intro)
        return _text_response(content=intro, suggestions=DEFAULT_SUGGESTIONS)

    if message.startswith('SYSTEM_TOOL:'):
        tool = message.split(':', 1)[1].strip()
        return handle_system_tool(session=session, student_id=student_id, lesson_id=lesson_id, tool=tool)

    # Normal conversational path.
    summary, history_str = memory.get_history_for_llm()

    memory.add(role='user', content=message)

    intent = _run_intent_classifier(user_message=message)

    structure = build_structured_blocks_json(session=session)
    structured_json = json.dumps(structure, ensure_ascii=False)

    if intent == 'request_quiz':
        obj = _run_tool_prompt_json(
            feature='fetch_quizzes',
            strategy='multiple_choice',
            payload={'num_questions': 3, 'structured_blocks_json': structured_json},
        )
        memory.add(role='assistant', content='کوئیز آماده شد.')
        return _tool_widget(widget_type='quiz', data=obj, text='کوئیز آماده شد.', suggestions=DEFAULT_SUGGESTIONS)

    if intent == 'request_flashcard':
        obj = _run_tool_prompt_json(
            feature='flash_cards',
            strategy='standard_qa',
            payload={'num_flashcards': 10, 'structured_blocks_json': structured_json},
        )
        memory.add(role='assistant', content='فلش‌کارت‌ها آماده شد.')
        return _tool_widget(widget_type='flashcard', data=obj, text='فلش‌کارت‌ها آماده شد.', suggestions=DEFAULT_SUGGESTIONS)

    if intent == 'request_match_game':
        obj = _run_tool_prompt_json(
            feature='match_games',
            strategy='term_definition',
            payload={'num_pairs': 5, 'structured_blocks_json': structured_json},
        )
        memory.add(role='assistant', content='بازی تطبیق آماده شد.')
        return _tool_widget(widget_type='match_game', data=obj, text='بازی تطبیق آماده شد.', suggestions=DEFAULT_SUGGESTIONS)

    if intent == 'request_practice_test':
        obj = _run_tool_prompt_json(
            feature='practice_tests',
            strategy='mixed_questions',
            payload={'num_questions': 5, 'structured_blocks_json': structured_json},
        )
        memory.add(role='assistant', content='آزمون تمرینی آماده شد.')
        return _tool_widget(widget_type='practice_test', data=obj, text='آزمون تمرینی آماده شد.', suggestions=DEFAULT_SUGGESTIONS)

    if intent == 'request_scenario':
        obj = _run_tool_prompt_json(
            feature='meril',
            strategy='problem_centered',
            payload={'structured_blocks_json': structured_json},
        )
        memory.add(role='assistant', content='سناریو آماده شد.')
        return _tool_widget(widget_type='scenario', data=obj, text='سناریو آماده شد.', suggestions=DEFAULT_SUGGESTIONS)

    if intent == 'request_notes':
        template = PROMPTS['notes_ai']['detailed_notes']
        prompt = template.replace('STRUCTURED_BLOCKS_JSON', structured_json)
        obj = generate_json(feature='notes_ai', contents=prompt)
        memory.add(role='assistant', content='جزوه و نکات آماده شد.')
        return _tool_widget(widget_type='notes', data=obj, text='جزوه و نکات آماده شد.', suggestions=DEFAULT_SUGGESTIONS)

    if intent == 'request_image':
        template = PROMPTS['image_plan']['default']
        prompt = _safe_template_replace(str(template), {'unit_content': unit_content, 'user_message': message})
        obj = generate_json(feature='image_plan', contents=prompt)
        memory.add(role='assistant', content='ایده‌ی تصویر آماده شد.')
        return _tool_widget(widget_type='image', data=obj, text='ایده‌ی تصویر آماده شد.', suggestions=DEFAULT_SUGGESTIONS)

    # Default: tutoring chat.
    resp = _run_chat_system_prompt(unit_content=unit_content, history_str=history_str, user_message=message, student_name=student_name)
    memory.add(role='assistant', content=resp['content'])
    return resp


def handle_system_tool(
    *,
    session: ClassCreationSession,
    student_id: int,
    lesson_id: Optional[str],
    tool: str,
) -> ChatResponse:
    tool = (tool or '').strip()
    structure = build_structured_blocks_json(session=session)
    structured_json = json.dumps(structure, ensure_ascii=False)

    if tool == 'flash_cards':
        obj = _run_tool_prompt_json(
            feature='flash_cards',
            strategy='standard_qa',
            payload={'num_flashcards': 10, 'structured_blocks_json': structured_json},
        )
        return _tool_widget(widget_type='flashcard', data=obj, text='فلش‌کارت‌ها آماده شد.', suggestions=DEFAULT_SUGGESTIONS)

    if tool == 'fetch_quizzes':
        obj = _run_tool_prompt_json(
            feature='fetch_quizzes',
            strategy='multiple_choice',
            payload={'num_questions': 3, 'structured_blocks_json': structured_json},
        )
        return _tool_widget(widget_type='quiz', data=obj, text='کوئیز آماده شد.', suggestions=DEFAULT_SUGGESTIONS)

    if tool == 'match_games':
        obj = _run_tool_prompt_json(
            feature='match_games',
            strategy='term_definition',
            payload={'num_pairs': 5, 'structured_blocks_json': structured_json},
        )
        return _tool_widget(widget_type='match_game', data=obj, text='بازی تطبیق آماده شد.', suggestions=DEFAULT_SUGGESTIONS)

    # Unknown tool: treat as chat.
    return _text_response(content='این ابزار را نمی‌شناسم. می‌خوای سوالت رو با متن بپرسی؟', suggestions=DEFAULT_SUGGESTIONS)


def describe_image_for_chat(*, unit_content: str, user_message: str, image_bytes: bytes, mime_type: str) -> str:
    prompt = _safe_template_replace(
        PROMPTS['chat_image_description']['default'],
        {'unit_content': unit_content, 'user_message': user_message},
    )
    media_part = part_from_bytes(data=image_bytes, mime_type=mime_type)
    return generate_text(contents=[prompt, media_part]).text.strip()


def handle_student_image_upload(
    *,
    session: ClassCreationSession,
    student_id: int,
    lesson_id: Optional[str],
    user_message: str,
    page_context: str,
    page_material: str,
    image_bytes: bytes,
    mime_type: str,
) -> TextResponse:
    thread_id = build_thread_id(session_id=session.id, lesson_id=lesson_id, student_id=student_id)
    memory = MemoryService(thread_id=thread_id)

    unit_title, unit_content = _get_unit_content(session=session, lesson_id=lesson_id)

    if (page_material or '').strip():
        unit_content = (page_material or '').strip()
    if (page_context or '').strip():
        unit_content = f"STUDENT_UI_CONTEXT:\n{page_context.strip()}\n\nSTUDENT_IS_READING:\n{unit_content}".strip()

    caption = (user_message or '').strip()
    if caption:
        memory.add(role='user', content=caption)

    description = describe_image_for_chat(
        unit_content=unit_content,
        user_message=caption,
        image_bytes=image_bytes,
        mime_type=mime_type,
    )

    memory.add(role='assistant', content=description)
    return _text_response(content=description, suggestions=DEFAULT_SUGGESTIONS)


def handle_student_audio_upload(
    *,
    session: ClassCreationSession,
    student_id: int,
    lesson_id: Optional[str],
    user_message: str,
    page_context: str,
    page_material: str,
    transcript_markdown: str,
) -> ChatResponse:
    caption = (user_message or '').strip()
    transcript = (transcript_markdown or '').strip()
    combined = caption
    if transcript:
        combined = (combined + '\n\n[VOICE_TRANSCRIPT]\n' + transcript).strip()
    if not combined:
        combined = '[VOICE_TRANSCRIPT]'

    return handle_student_message(
        session=session,
        student_id=student_id,
        lesson_id=lesson_id,
        user_message=combined,
        page_context=page_context,
        page_material=page_material,
    )
