from __future__ import annotations

from typing import Any, Iterable, Optional

from django.db import transaction
from django.utils import timezone

from ..models import ClassCreationSession, StudentCourseChatMessage, StudentCourseChatThread


def build_db_thread_key(*, session_id: int, student_id: int, lesson_id: Optional[str]) -> str:
    lid = (lesson_id or '').strip() or 'root'
    return f"course-chat:{session_id}:{lid}:{student_id}"


@transaction.atomic
def get_or_create_thread(*, session: ClassCreationSession, student_id: int, lesson_id: Optional[str]) -> StudentCourseChatThread:
    lid = (lesson_id or '').strip()
    thread_key = build_db_thread_key(session_id=session.id, student_id=student_id, lesson_id=lesson_id)

    obj, created = StudentCourseChatThread.objects.select_for_update().get_or_create(
        thread_key=thread_key,
        defaults={
            'session': session,
            'student_id': student_id,
            'lesson_id': lid,
        },
    )

    # If session/student/lesson were created under a different key format in the future,
    # keep thread_key as the source of truth.
    if not created and obj.updated_at:
        StudentCourseChatThread.objects.filter(id=obj.id).update(updated_at=timezone.now())

    return obj


def append_message(
    *,
    thread: StudentCourseChatThread,
    role: str,
    message_type: str,
    content: str = '',
    payload: Optional[dict[str, Any]] = None,
    suggestions: Optional[list[str]] = None,
    lesson_id: Optional[str] = None,
) -> StudentCourseChatMessage:
    lid = (lesson_id or thread.lesson_id or '').strip()
    return StudentCourseChatMessage.objects.create(
        thread=thread,
        role=role,
        message_type=message_type,
        content=(content or ''),
        payload=payload or {},
        suggestions=suggestions or [],
        lesson_id=lid,
    )


def list_messages(
    *,
    session_id: int,
    student_id: int,
    lesson_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    qs = StudentCourseChatMessage.objects.filter(
        thread__session_id=session_id,
        thread__student_id=student_id,
    ).select_related('thread')

    lid = (lesson_id or '').strip()
    if lid:
        qs = qs.filter(thread__lesson_id=lid)

    rows: Iterable[StudentCourseChatMessage] = qs.order_by('created_at').all()

    out: list[dict[str, Any]] = []
    for msg in rows:
        out.append(
            {
                'id': msg.id,
                'role': msg.role,
                'type': msg.message_type,
                'content': msg.content,
                'payload': msg.payload,
                'suggestions': msg.suggestions,
                'lesson_id': msg.lesson_id,
                'created_at': msg.created_at.isoformat(),
            }
        )

    return out
