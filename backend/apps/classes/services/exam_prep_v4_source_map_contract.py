"""Canonical, content-free contracts for Exam Prep V4 source maps."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from typing import Any

from apps.classes.models_v4 import ExamSourcePage, ExamSourceRole


SOURCE_MAP_SCHEMA_VERSION = 1
_ALLOWED_ROLES = frozenset(ExamSourceRole.values)
_ALLOWED_ORIENTATIONS = frozenset(ExamSourcePage.Orientation.values)


class InvalidSourceMapContract(ValueError):
    pass


def normalize_source_map_pages(
    pages: Iterable[Mapping[str, Any]],
    *,
    page_count: int,
) -> tuple[dict[str, Any], ...]:
    """Validate and normalize a complete one-based structural page map."""

    if page_count < 1:
        raise InvalidSourceMapContract('Source document must contain at least one page.')

    normalized: dict[int, dict[str, Any]] = {}
    for raw in pages:
        try:
            page_number = int(raw['pageNumber'])
            role = str(raw['role']).strip().lower()
            orientation = int(raw.get('orientation', 0))
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidSourceMapContract('Invalid source-map page record.') from exc

        if not 1 <= page_number <= page_count:
            raise InvalidSourceMapContract('Source-map page number is outside the document.')
        if page_number in normalized:
            raise InvalidSourceMapContract('Each source page must appear exactly once.')
        if role not in _ALLOWED_ROLES:
            raise InvalidSourceMapContract('Unsupported source-map role.')
        if orientation not in _ALLOWED_ORIENTATIONS:
            raise InvalidSourceMapContract('Unsupported source-page orientation.')

        normalized[page_number] = {
            'pageNumber': page_number,
            'role': role,
            'orientation': orientation,
        }

    expected = set(range(1, page_count + 1))
    if set(normalized) != expected:
        raise InvalidSourceMapContract('A complete source map must include every page exactly once.')

    return tuple(normalized[number] for number in range(1, page_count + 1))


def source_map_fingerprint(
    pages: Iterable[Mapping[str, Any]],
    *,
    page_count: int,
) -> str:
    """Return a stable SHA-256 over structural page roles and orientations only."""

    normalized = normalize_source_map_pages(pages, page_count=page_count)
    payload = {
        'schemaVersion': SOURCE_MAP_SCHEMA_VERSION,
        'pageCount': page_count,
        'pages': normalized,
    }
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(',', ':'),
        ).encode('utf-8')
    ).hexdigest()


def structural_page_map_from_models(pages) -> tuple[dict[str, Any], ...]:
    """Build the canonical structural page map from ordered page model rows."""

    return tuple(
        {
            'pageNumber': page.page_number,
            'role': page.effective_role,
            'orientation': page.orientation,
        }
        for page in pages
    )
