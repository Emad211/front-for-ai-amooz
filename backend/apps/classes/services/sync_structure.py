from __future__ import annotations

import json
from typing import Any

from django.db import transaction

from apps.classes.models import (
    ClassCreationSession,
    ClassLearningObjective,
    ClassSection,
    ClassUnit,
)


def _safe_str(x: Any) -> str:
    return ('' if x is None else str(x)).strip()


def _derive_section_id(section: dict[str, Any], idx: int) -> str:
    return _safe_str(section.get('id')) or f'sec-{idx + 1}'


def _derive_unit_id(section_id: str, unit: dict[str, Any], idx: int) -> str:
    return _safe_str(unit.get('id')) or f'{section_id}-u-{idx + 1}'


@transaction.atomic
def sync_structure_from_session(*, session: ClassCreationSession) -> None:
    raw = (session.structure_json or '').strip()
    if not raw:
        # If structure_json is cleared, remove normalized rows.
        ClassLearningObjective.objects.filter(session=session).delete()
        ClassUnit.objects.filter(session=session).delete()
        ClassSection.objects.filter(session=session).delete()
        return

    try:
        structure = json.loads(raw)
    except Exception:
        # Keep the raw JSON on session, but don't mutate normalized tables.
        return

    root = structure.get('root_object') if isinstance(structure, dict) else None
    outline = structure.get('outline') if isinstance(structure, dict) else None

    # Objectives
    what = []
    if isinstance(root, dict) and isinstance(root.get('what_you_will_learn'), list):
        what = [x for x in root.get('what_you_will_learn') if _safe_str(x)]

    obj_ids_to_keep: list[int] = []
    for i, text in enumerate(what):
        obj, _ = ClassLearningObjective.objects.update_or_create(
            session=session,
            order=i + 1,
            defaults={'text': _safe_str(text)},
        )
        obj_ids_to_keep.append(obj.id)

    ClassLearningObjective.objects.filter(session=session).exclude(id__in=obj_ids_to_keep).delete()

    # Sections + Units
    sections = outline if isinstance(outline, list) else []

    section_ids_to_keep: list[int] = []
    unit_ids_to_keep: list[int] = []

    for s_idx, sec in enumerate(sections):
        if not isinstance(sec, dict):
            continue
        external_id = _derive_section_id(sec, s_idx)
        section_obj, _ = ClassSection.objects.update_or_create(
            session=session,
            external_id=external_id,
            defaults={
                'order': s_idx + 1,
                'title': _safe_str(sec.get('title')) or f'فصل {s_idx + 1}',
            },
        )
        section_ids_to_keep.append(section_obj.id)

        units = sec.get('units') if isinstance(sec.get('units'), list) else []
        for u_idx, unit in enumerate(units):
            if not isinstance(unit, dict):
                continue
            unit_external_id = _derive_unit_id(external_id, unit, u_idx)

            unit_obj, _ = ClassUnit.objects.update_or_create(
                session=session,
                external_id=unit_external_id,
                defaults={
                    'section': section_obj,
                    'order': u_idx + 1,
                    'title': _safe_str(unit.get('title')) or f'درس {u_idx + 1}',
                    'merrill_type': _safe_str(unit.get('merrill_type')),
                    'source_markdown': _safe_str(unit.get('source_markdown')),
                    'content_markdown': _safe_str(unit.get('content_markdown')),
                    'image_ideas': unit.get('image_ideas') if isinstance(unit.get('image_ideas'), list) else [],
                },
            )
            unit_ids_to_keep.append(unit_obj.id)

    ClassUnit.objects.filter(session=session).exclude(id__in=unit_ids_to_keep).delete()
    ClassSection.objects.filter(session=session).exclude(id__in=section_ids_to_keep).delete()
