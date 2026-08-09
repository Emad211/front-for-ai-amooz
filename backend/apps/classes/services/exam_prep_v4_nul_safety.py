"""PostgreSQL-safe native-text extraction for Exam Prep V4.

Some PDFs with broken embedded font/text mappings make pypdf return U+0000
characters. PostgreSQL text columns cannot store NUL characters, so source
preparation used to fail before classification/OCR even started.

The rendered PDF remains authoritative. This hook removes only U+0000 from the
bounded native-text hint stored for page classification; all other characters,
newlines and tabs are preserved.
"""
from __future__ import annotations

import logging

from apps.classes.services import exam_prep_v4_pdf_source as pdf_source

logger = logging.getLogger(__name__)

_INSTALLED = False


def sanitize_postgres_text(value: object) -> str:
    """Remove only PostgreSQL-forbidden NUL characters from derived text."""

    return str(value or '').replace('\x00', '')


def safe_native_text(reader, index: int) -> tuple[str, int]:
    """Extract the bounded native-text hint without ever persisting U+0000."""

    try:
        raw = reader.pages[index].extract_text() or ''
    except Exception:
        raw = ''

    nul_count = raw.count('\x00')
    if nul_count:
        logger.warning(
            'exam_prep_v4.native_text_nul_removed pageNumber=%s nulCount=%s',
            index + 1,
            nul_count,
        )

    text = sanitize_postgres_text(raw).strip()
    sample_chars = pdf_source._setting_int(
        'EXAM_PREP_V4_NATIVE_TEXT_STORED_CHARS',
        4000,
        maximum=20_000,
    )
    return text[:sample_chars], len(text)


def install() -> None:
    """Patch the narrow source-preparation seam once per Django process."""

    global _INSTALLED
    if _INSTALLED:
        return
    pdf_source._native_text = safe_native_text
    _INSTALLED = True


__all__ = ['install', 'safe_native_text', 'sanitize_postgres_text']
