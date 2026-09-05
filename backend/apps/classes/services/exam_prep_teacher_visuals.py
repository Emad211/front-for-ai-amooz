"""Teacher-scoped visual attachments for legacy Exam Prep sessions.

A teacher fixing OCR-flawed questions of an extracted ``ClassCreationSession``
(``pipeline_type == EXAM_PREP``) can attach their own image to a question
stem, an option, or the solution.  The reference lives inside
``session.exam_prep_json`` (``{"exam_prep": {"questions": [...]}}``) as a
``teacher-*`` entry in the question's ``visuals`` array, mirroring the
source-first visual entry keys used across the product (``id``, ``role``,
``optionLabel``, ``altText``, ``url`` — see ``frontend/src/lib/exam-visuals.ts``).

The image bytes themselves are never stored in the database.  They land in the
same private ``answer_sources`` storage used by ``ExamPrepVisualAsset`` (S3/MinIO
in production, local filesystem in development) under
``exam-prep/teacher-visuals/<session_id>/<uuid>.<ext>`` so worker and teacher
uploads share one storage family.  Only the stored filename is referenced from
the JSON via the visual ``url``; the authenticated content view rebuilds the
private object name from the session id and that filename.
"""
from __future__ import annotations

import io
import json
import re
import uuid
from typing import Any

from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.db import transaction

from core.storage_backends import delete_answer_source_file

from ..models import ClassCreationSession
from .file_validation import is_real_image

# Maximum accepted image upload (bytes).
TEACHER_VISUAL_MAX_UPLOAD_BYTES = 5 * 1024 * 1024

#: Roles a teacher may attach an image for (stem / option / solution).
TEACHER_VISUAL_ROLES: frozenset[str] = frozenset({'question', 'solution', 'option'})

#: Visual ids created by teachers always carry this prefix so the product can
#: distinguish hand-uploaded images from worker source crops / stored assets.
TEACHER_VISUAL_ID_PREFIX = 'teacher-'

#: Storage prefix used for teacher uploads (kept private like other exam-prep
#: source files; never served through the public media proxy).
TEACHER_VISUAL_STORAGE_PREFIX = 'exam-prep/teacher-visuals'

#: Canonical extension + content type per detected image format.
_FORMAT_EXT = {
    'PNG': ('png', 'image/png'),
    'JPEG': ('jpg', 'image/jpeg'),
    'WEBP': ('webp', 'image/webp'),
}

#: Accepted filename extensions and the image format group they imply.
_EXT_GROUP = {
    'png': 'PNG',
    'jpg': 'JPEG',
    'jpeg': 'JPEG',
    'webp': 'WEBP',
}

_CONTENT_TYPE_BY_EXT = {
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.webp': 'image/webp',
}

#: storage_name carried in the content URL must be a single opaque path segment
#: (``<uuid4-hex>.<ext>``) so traversal or cross-session names are impossible.
_STORAGE_NAME_RE = re.compile(r'^[0-9a-f]{32}\.(?:png|jpe?g|webp)$')


class TeacherVisualError(ValueError):
    """Base class for teacher-visual service errors (typed, translated by views)."""


class NotExamPrepSessionError(TeacherVisualError):
    """The session is not a legacy EXAM_PREP ClassCreationSession."""


class InvalidTeacherVisualRoleError(TeacherVisualError):
    """The requested visual role is not in TEACHER_VISUAL_ROLES."""


class UnknownTeacherVisualQuestionError(TeacherVisualError):
    """No question with the requested question_id exists in the session JSON."""


class InvalidTeacherVisualUploadError(TeacherVisualError):
    """The uploaded bytes are not an allowed image (type/size/extension)."""


def _question_id(value: Any) -> str:
    return str(value or '').strip()


def _question_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    exam_prep = payload.get('exam_prep')
    questions = exam_prep.get('questions') if isinstance(exam_prep, dict) else None
    if questions is None:
        raise NotExamPrepSessionError('ساختار سؤال‌ها در جلسه یافت نشد.')
    if not isinstance(questions, list):
        raise NotExamPrepSessionError('ساختار سؤال‌های جلسه نامعتبر است.')
    return questions


def parse_exam_prep_payload(session: ClassCreationSession) -> dict[str, Any]:
    """Parse ``session.exam_prep_json`` into its container dict.

    Raises :class:`NotExamPrepSessionError` when the session is not an
    EXAM_PREP session or its stored JSON is not the expected object.
    """
    if session.pipeline_type != ClassCreationSession.PipelineType.EXAM_PREP:
        raise NotExamPrepSessionError('این جلسه یک جلسه آمادگی آزمون نیست.')
    try:
        payload = json.loads(session.exam_prep_json or '')
    except (json.JSONDecodeError, TypeError) as exc:
        raise NotExamPrepSessionError('محتوای استخراج‌شده جلسه قابل خواندن نیست.') from exc
    if not isinstance(payload, dict):
        raise NotExamPrepSessionError('محتوای استخراج‌شده جلسه قابل خواندن نیست.')
    exam_prep = payload.get('exam_prep')
    if not isinstance(exam_prep, dict):
        payload['exam_prep'] = {}
    _question_list(payload)  # validate the questions container early
    return payload


def available_question_ids(session: ClassCreationSession) -> list[str]:
    """Return the stored question ids (used for unknown-question error text)."""
    try:
        payload = parse_exam_prep_payload(session)
    except TeacherVisualError:
        return []
    return [_question_id(q.get('question_id')) for q in _question_list(payload)]


def _find_question(payload: dict[str, Any], question_id: str) -> dict[str, Any] | None:
    wanted = str(question_id or '').strip()
    for question in _question_list(payload):
        if not isinstance(question, dict):
            continue
        if _question_id(question.get('question_id')) == wanted:
            return question
    return None


def _classify_image(data: bytes) -> tuple[str, str]:
    """Return ``(canonical_ext, content_type)`` for an allowed image upload.

    The MIME type is derived from the actual image bytes (Pillow), never from
    the browser-supplied content type.  A filename whose extension does not
    match the detected format is rejected as well.
    """
    if not data:
        raise InvalidTeacherVisualUploadError('فایل تصویر خالی است.')
    if len(data) > TEACHER_VISUAL_MAX_UPLOAD_BYTES:
        raise InvalidTeacherVisualUploadError(
            'حجم تصویر بیش از ۵ مگابایت است.'
        )
    if not is_real_image(data):
        raise InvalidTeacherVisualUploadError('فایل انتخاب‌شده یک تصویر معتبر نیست.')
    try:
        from PIL import Image

        with Image.open(io.BytesIO(data)) as image:
            detected_format = str(getattr(image, 'format', '') or '').upper()
    except Exception:
        detected_format = ''
    if detected_format not in _FORMAT_EXT:
        raise InvalidTeacherVisualUploadError('فقط تصویر PNG، JPEG یا WEBP پذیرفته می‌شود.')
    return _FORMAT_EXT[detected_format]


def _normalized_image_extension(image_name: str, canonical_ext: str) -> str:
    """Validate the uploaded filename extension against the detected format."""
    name = str(image_name or '').strip().lower()
    name = name.rsplit('/', 1)[-1].rsplit('\\', 1)[-1]
    ext = name.rsplit('.', 1)[-1] if '.' in name else ''
    if ext not in _EXT_GROUP:
        raise InvalidTeacherVisualUploadError('پسوند فایل تصویر نامعتبر است.')
    if _EXT_GROUP[ext] != _EXT_GROUP[canonical_ext]:
        raise InvalidTeacherVisualUploadError('پسوند فایل با نوع تصویر همخوانی ندارد.')
    return canonical_ext


def _validate_option_label(role: str, option_label: Any) -> str | None:
    if role != 'option':
        return None
    label = str(option_label or '').strip()
    if not label:
        raise InvalidTeacherVisualRoleError(
            'برای تصویر گزینه، مشخص کردن برچسب گزینه (option_label) الزامی است.'
        )
    if len(label) > 64:
        raise InvalidTeacherVisualRoleError('برچسب گزینه بیش از حد طولانی است.')
    return label


def teacher_visual_content_url(session_id: int, storage_name: str) -> str:
    """Relative authenticated content URL for a stored teacher visual."""
    return (
        f'/api/classes/exam-prep-sessions/{session_id}/'
        f'visuals/teacher/{storage_name}/content/'
    )


def teacher_visual_storage_path(session_id: int, storage_name: str) -> str:
    """Rebuild the private object name from the session and the stored filename."""
    return f'{TEACHER_VISUAL_STORAGE_PREFIX}/{session_id}/{storage_name}'


def teacher_visual_content_type(storage_name: str) -> str | None:
    """Content type implied by the stored filename extension (never by size)."""
    if not _STORAGE_NAME_RE.fullmatch(str(storage_name or '')):
        return None
    ext = storage_name.rsplit('.', 1)[-1]
    return _CONTENT_TYPE_BY_EXT.get(f'.{ext}')


def _visual_entry(
    *,
    session_id: int,
    role: str,
    option_label: str | None,
    storage_name: str,
    visual_id: str,
) -> dict[str, Any]:
    return {
        'id': visual_id,
        'role': role,
        'optionLabel': option_label,
        'altText': None,
        'url': teacher_visual_content_url(session_id, storage_name),
        # Internal filename used by remove_teacher_visual and the content view;
        # not part of the frontend contract but harmless and self-describing.
        'storageName': storage_name,
    }


def attach_teacher_visual(
    session: ClassCreationSession,
    *,
    question_id: str,
    role: str,
    image_content: bytes,
    image_name: str,
    option_label: str | None = None,
) -> dict[str, Any]:
    """Persist a teacher image and attach it to one question of the session.

    Validates the request, stores the image under
    ``exam-prep/teacher-visuals/<session_id>/<uuid>.<ext>`` in the private
    ``answer_sources`` storage, and appends a ``teacher-*`` entry to the owning
    question's ``visuals`` array inside ``session.exam_prep_json`` (atomic).

    Returns ``{'visual': <new entry>, 'question': <updated question dict>}``.

    Raises a :class:`TeacherVisualError` subclass for every rejected input;
    ownership (``session.teacher == request.user``) is checked by the caller.
    """
    normalized_role = str(role or '').strip()
    if normalized_role not in TEACHER_VISUAL_ROLES:
        raise InvalidTeacherVisualRoleError(
            'نقش تصویر باید question، option یا solution باشد.'
        )
    normalized_option_label = _validate_option_label(normalized_role, option_label)
    wanted_question_id = _question_id(question_id)
    if not wanted_question_id:
        raise UnknownTeacherVisualQuestionError('شناسه سؤال ارسال نشده است.')

    # Fail fast before touching storage when the target question does not exist
    # or the session is not a usable EXAM_PREP payload.
    parse_exam_prep_payload(session)
    if _find_question(parse_exam_prep_payload(session), wanted_question_id) is None:
        ids = ', '.join(available_question_ids(session)[:200]) or '—'
        raise UnknownTeacherVisualQuestionError(
            f'سؤال با شناسه «{wanted_question_id}» یافت نشد. شناسه‌های موجود: {ids}'
        )

    canonical_ext, _content_type = _classify_image(image_content)
    ext = _normalized_image_extension(image_name, canonical_ext)
    visual_id = f'{TEACHER_VISUAL_ID_PREFIX}{uuid.uuid4().hex}'
    storage_name = f'{visual_id[len(TEACHER_VISUAL_ID_PREFIX):]}.{ext}'
    storage_path = teacher_visual_storage_path(session.id, storage_name)

    saved_path = storages['answer_sources'].save(
        storage_path,
        ContentFile(image_content),
    )
    try:
        with transaction.atomic():
            locked = ClassCreationSession.objects.select_for_update().get(pk=session.pk)
            payload = parse_exam_prep_payload(locked)
            question = _find_question(payload, wanted_question_id)
            if question is None:
                ids = ', '.join(available_question_ids(locked)[:200]) or '—'
                raise UnknownTeacherVisualQuestionError(
                    f'سؤال با شناسه «{wanted_question_id}» یافت نشد. '
                    f'شناسه‌های موجود: {ids}'
                )
            visuals = question.get('visuals')
            if not isinstance(visuals, list):
                visuals = []
                question['visuals'] = visuals
            visual = _visual_entry(
                session_id=locked.id,
                role=normalized_role,
                option_label=normalized_option_label,
                storage_name=storage_name,
                visual_id=visual_id,
            )
            visuals.append(visual)
            locked.exam_prep_json = json.dumps(payload, ensure_ascii=False)
            locked.save(update_fields=['exam_prep_json', 'updated_at'])
    except Exception:
        # Never leave an orphan private object behind when the JSON update fails.
        delete_answer_source_file(saved_path)
        raise
    return {'visual': visual, 'question': question}


def _visual_storage_name(visual: dict[str, Any]) -> str | None:
    """Recover the stored filename for a teacher visual entry (safe fallbacks)."""
    for candidate in (visual.get('storageName'), visual.get('storage_name')):
        if isinstance(candidate, str) and _STORAGE_NAME_RE.fullmatch(candidate):
            return candidate
    raw_url = str(visual.get('url') or '')
    if '/visuals/teacher/' in raw_url:
        candidate = raw_url.rsplit('/visuals/teacher/', 1)[1].split('/content/', 1)[0]
        if _STORAGE_NAME_RE.fullmatch(candidate):
            return candidate
    return None


def remove_teacher_visual(
    session: ClassCreationSession,
    *,
    visual_id: str,
) -> bool:
    """Remove one ``teacher-*`` visual entry and its stored private file.

    Returns ``True`` when the entry existed and was removed from the owning
    question; ``False`` when no matching teacher visual was found.  The stored
    file is deleted best-effort after the JSON update commits.
    """
    wanted_id = str(visual_id or '').strip()
    if not wanted_id.startswith(TEACHER_VISUAL_ID_PREFIX):
        return False
    parse_exam_prep_payload(session)

    with transaction.atomic():
        locked = ClassCreationSession.objects.select_for_update().get(pk=session.pk)
        payload = parse_exam_prep_payload(locked)
        found_storage_name: str | None = None
        for question in _question_list(payload):
            if not isinstance(question, dict):
                continue
            visuals = question.get('visuals')
            if not isinstance(visuals, list):
                continue
            for visual in visuals:
                if not isinstance(visual, dict):
                    continue
                if str(visual.get('id') or '').strip() == wanted_id:
                    found_storage_name = _visual_storage_name(visual)
                    visuals.remove(visual)
                    break
            if found_storage_name is not None:
                break
        if found_storage_name is None:
            return False
        locked.exam_prep_json = json.dumps(payload, ensure_ascii=False)
        locked.save(update_fields=['exam_prep_json', 'updated_at'])

    if found_storage_name is not None:
        delete_answer_source_file(
            teacher_visual_storage_path(locked.id, found_storage_name)
        )
    return True


def find_teacher_visual_reference(
    session: ClassCreationSession,
    storage_name: str,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Return the ``(question, visual)`` referencing a teacher storage filename.

    Used by the content view so only visuals the session itself references can
    be served (no orphan or cross-session private objects).
    """
    if not _STORAGE_NAME_RE.fullmatch(str(storage_name or '')):
        return None
    try:
        payload = parse_exam_prep_payload(session)
    except TeacherVisualError:
        return None
    canonical_url = teacher_visual_content_url(session.id, storage_name)
    for question in _question_list(payload):
        if not isinstance(question, dict):
            continue
        for visual in question.get('visuals') or []:
            if not isinstance(visual, dict):
                continue
            visual_id = str(visual.get('id') or '')
            if not visual_id.startswith(TEACHER_VISUAL_ID_PREFIX):
                continue
            if str(visual.get('url') or '') == canonical_url or (
                _visual_storage_name(visual) == storage_name
            ):
                return question, visual
    return None


__all__ = [
    'TEACHER_VISUAL_MAX_UPLOAD_BYTES',
    'TEACHER_VISUAL_ROLES',
    'TEACHER_VISUAL_ID_PREFIX',
    'TEACHER_VISUAL_STORAGE_PREFIX',
    'TeacherVisualError',
    'NotExamPrepSessionError',
    'InvalidTeacherVisualRoleError',
    'UnknownTeacherVisualQuestionError',
    'InvalidTeacherVisualUploadError',
    'parse_exam_prep_payload',
    'available_question_ids',
    'attach_teacher_visual',
    'remove_teacher_visual',
    'find_teacher_visual_reference',
    'teacher_visual_content_url',
    'teacher_visual_storage_path',
    'teacher_visual_content_type',
]
