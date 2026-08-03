"""Canonical, content-free contracts for Exam Prep V4 source maps."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from typing import Any

from apps.classes.models_v4 import ExamSourcePage, ExamSourceRole


SOURCE_MAP_SCHEMA_VERSION = 2
_ALLOWED_ROLES = frozenset(ExamSourceRole.values)
_ALLOWED_ORIENTATIONS = frozenset(ExamSourcePage.Orientation.values)


class InvalidSourceMapContract(ValueError):
    pass


def normalize_source_map_pages(
    pages: Iterable[Mapping[str, Any]],
    *,
    page_count: int,
) -> tuple[dict[str, Any], ...]:
    """Validate a complete page map and return it in virtual display order."""

    if page_count < 1:
        raise InvalidSourceMapContract('Source document must contain at least one page.')

    by_page_number: dict[int, dict[str, Any]] = {}
    display_orders: set[int] = set()
    for raw in pages:
        try:
            page_number = int(raw['pageNumber'])
            display_order = int(raw['displayOrder'])
            role = str(raw['role']).strip().lower()
            orientation = int(raw.get('orientation', 0))
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidSourceMapContract('Invalid source-map page record.') from exc

        if not 1 <= page_number <= page_count:
            raise InvalidSourceMapContract('Source-map page number is outside the document.')
        if not 1 <= display_order <= page_count:
            raise InvalidSourceMapContract('Virtual display order is outside the document.')
        if page_number in by_page_number:
            raise InvalidSourceMapContract('Each source page must appear exactly once.')
        if display_order in display_orders:
            raise InvalidSourceMapContract('Each virtual display position must appear exactly once.')
        if role not in _ALLOWED_ROLES:
            raise InvalidSourceMapContract('Unsupported source-map role.')
        if orientation not in _ALLOWED_ORIENTATIONS:
            raise InvalidSourceMapContract('Unsupported source-page orientation.')

        display_orders.add(display_order)
        by_page_number[page_number] = {
            'pageNumber': page_number,
            'displayOrder': display_order,
            'role': role,
            'orientation': orientation,
        }

    expected = set(range(1, page_count + 1))
    if set(by_page_number) != expected:
        raise InvalidSourceMapContract('A complete source map must include every page exactly once.')
    if display_orders != expected:
        raise InvalidSourceMapContract(
            'Virtual display order must be a complete one-based sequence.'
        )

    return tuple(
        sorted(
            by_page_number.values(),
            key=lambda item: (item['displayOrder'], item['pageNumber']),
        )
    )


def source_map_fingerprint(
    pages: Iterable[Mapping[str, Any]],
    *,
    page_count: int,
) -> str:
    """Return a stable SHA-256 over virtual order, roles, and orientation."""

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
    """Build a canonical map while preserving immutable physical page identity."""

    return tuple(
        {
            'pageNumber': page.page_number,
            'displayOrder': page.display_order,
            'role': page.effective_role,
            'orientation': page.orientation,
        }
        for page in sorted(
            pages,
            key=lambda item: (item.display_order, item.page_number),
        )
    )
