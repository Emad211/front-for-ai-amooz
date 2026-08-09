"""Correct the release hardening's OCR4 option-label normalization seam."""
from __future__ import annotations

from typing import Any, Mapping

from apps.classes.services import exam_prep_source_first as source_first
from apps.classes.services import exam_prep_v4_deployment_hardening as hardening
from apps.classes.services.exam_prep_mistral_solution_headings import (
    normalize_solution_option_label,
)


def _integer(value: Any) -> int | None:
    raw = str(value or '').translate(
        str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')
    )
    digits = ''.join(character for character in raw if character.isdigit())
    return int(digits) if digits else None


def direct_solution_option_map(analysis: Mapping[str, Any]) -> dict[int, str]:
    accepted: dict[int, str] = {}
    conflicts: set[int] = set()
    for page in analysis.get('pages') or []:
        if not isinstance(page, Mapping):
            continue
        for region in page.get('regions') or []:
            if not isinstance(region, Mapping) or str(region.get('kind') or '') != 'solution':
                continue
            if not source_first._structurally_safe_region(region):
                continue
            number = source_first._region_number(region)
            raw_option = _integer(region.get('correctOptionLabel'))
            option, _normalized, valid = normalize_solution_option_label(raw_option)
            if number is None or option is None or not valid:
                continue
            label = str(option)
            previous = accepted.get(number)
            if previous is not None and previous != label:
                conflicts.add(number)
                continue
            accepted[number] = label
    for number in conflicts:
        accepted.pop(number, None)
    return accepted


def install() -> None:
    # _source_option_map_for_adapter resolves this module global at call time,
    # so replacing it here repairs both batch and single-answer paths.
    hardening._direct_solution_option_map = direct_solution_option_map


__all__ = ['direct_solution_option_map', 'install']
