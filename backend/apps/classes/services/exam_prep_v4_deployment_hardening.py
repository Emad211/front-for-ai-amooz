"""Deadline-focused production hardening for source-aware Exam Prep V4.

This module intentionally keeps the existing V4 persistence model intact while
closing two release-critical gaps:

1. use conservative OCR4 solution-heading evidence to correct numeric answer
   labels without another provider call;
2. allow a teacher to correct semantic projection text while keeping V4 record
   identity, option labels and protected source-crop references immutable.

The installer patches the already-shipped service seams at Django startup.  It
is deliberately small and removable after the deployment is validated and the
same behavior can be folded into the owning modules.
"""
from __future__ import annotations

import json
from typing import Any, Mapping

from django.db import transaction
from django.utils import timezone

from apps.classes.models_v4 import ExamProject
from apps.classes.models_v4_projection import ExamV4Projection
from apps.classes.services import exam_prep_source_first as source_first
from apps.classes.services import exam_prep_v4_projection as projection
from apps.classes.services.exam_prep_mistral_solution_headings import (
    normalize_solution_option_label,
)


_ORIGINAL_BUILD_LEGACY_PROJECTION = projection.build_legacy_projection
_INSTALLED = False


def _json_clone(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _visual_identity(value: Any) -> tuple[tuple[Any, ...], ...]:
    rows: list[tuple[Any, ...]] = []
    if not isinstance(value, list):
        return ()
    for item in value:
        if not isinstance(item, Mapping):
            continue
        rows.append(
            (
                str(item.get('id') or ''),
                str(item.get('role') or ''),
                str(item.get('optionLabel') or ''),
                str(item.get('selectedVariant') or ''),
                str(item.get('url') or ''),
            )
        )
    return tuple(rows)


def merge_teacher_curated_projection(
    current_payload: Mapping[str, Any],
    generated_payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Copy teacher semantic corrections onto a fresh V4 projection safely.

    Structural/source identity is immutable.  A teacher may correct text,
    formulae, option text, the selected correct option, and solution text after
    comparing them with the protected source crops.
    """

    current = projection._normalized_payload(dict(current_payload))
    generated = projection._normalized_payload(dict(generated_payload))
    current_exam = current.get('exam_prep') if isinstance(current, Mapping) else None
    generated_exam = generated.get('exam_prep') if isinstance(generated, Mapping) else None
    current_questions = current_exam.get('questions') if isinstance(current_exam, Mapping) else None
    generated_questions = generated_exam.get('questions') if isinstance(generated_exam, Mapping) else None
    if not isinstance(current_questions, list) or not isinstance(generated_questions, list):
        raise projection.ProjectionIntegrityError('Projection questions are unavailable for safe curation.')
    if len(current_questions) != len(generated_questions):
        raise projection.ProjectionIntegrityError(
            'V4 question count/order is source-owned and cannot be changed in the legacy editor.'
        )

    merged = _json_clone(generated)
    merged_questions = merged['exam_prep']['questions']
    for index, (current_question, generated_question) in enumerate(
        zip(current_questions, generated_questions, strict=True)
    ):
        if not isinstance(current_question, Mapping) or not isinstance(generated_question, Mapping):
            raise projection.ProjectionIntegrityError('A projected question has an invalid shape.')
        if str(current_question.get('question_id') or '') != str(generated_question.get('question_id') or ''):
            raise projection.ProjectionIntegrityError(
                f'Question identity changed at position {index + 1}; rebuild from source instead.'
            )
        if str(current_question.get('type') or '') != str(generated_question.get('type') or ''):
            raise projection.ProjectionIntegrityError('V4 question type is source-owned.')
        if _visual_identity(current_question.get('visuals')) != _visual_identity(
            generated_question.get('visuals')
        ):
            raise projection.ProjectionIntegrityError(
                'Protected source visual references cannot be changed by projection editing.'
            )

        current_options = current_question.get('options') or []
        generated_options = generated_question.get('options') or []
        if not isinstance(current_options, list) or not isinstance(generated_options, list):
            raise projection.ProjectionIntegrityError('Projected options have an invalid shape.')
        current_labels = [
            str(item.get('label') or '') if isinstance(item, Mapping) else ''
            for item in current_options
        ]
        generated_labels = [
            str(item.get('label') or '') if isinstance(item, Mapping) else ''
            for item in generated_options
        ]
        if current_labels != generated_labels:
            raise projection.ProjectionIntegrityError(
                'V4 option count/order/labels are source-owned and cannot be changed.'
            )

        target = merged_questions[index]
        target['question_text_markdown'] = str(
            current_question.get('question_text_markdown') or ''
        ).strip()
        target['teacher_solution_markdown'] = str(
            current_question.get('teacher_solution_markdown') or ''
        ).strip()
        target['final_answer_markdown'] = str(
            current_question.get('final_answer_markdown') or ''
        ).strip()
        for option_index, option in enumerate(current_options):
            target['options'][option_index]['text_markdown'] = str(
                option.get('text_markdown') if isinstance(option, Mapping) else ''
            ).strip()

        selected = str(current_question.get('correct_option_label') or '').strip()
        if generated_labels and selected not in generated_labels:
            raise projection.ProjectionIntegrityError(
                f'Correct option for question {index + 1} must use an existing source option label.'
            )
        target['correct_option_label'] = selected or None
        correct_text = ''
        if selected:
            for option in target['options']:
                if str(option.get('label') or '') == selected:
                    correct_text = str(option.get('text_markdown') or '')
                    break
        target['correct_option_text_markdown'] = correct_text or None

    return merged


def _parse_payload(raw: str) -> dict[str, Any] | None:
    if not raw.strip():
        return None
    try:
        value = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise projection.ProjectionIntegrityError('The current projection JSON is invalid.') from exc
    if not isinstance(value, dict):
        raise projection.ProjectionIntegrityError('The current projection must be a JSON object.')
    return value


@transaction.atomic
def build_legacy_projection_with_teacher_curation(*, teacher, project_id: int) -> dict[str, Any]:
    """Rebuild source identity, then re-apply only teacher-owned semantic fields."""

    existing = (
        ExamV4Projection.objects.select_for_update()
        .select_related('session')
        .filter(project_id=project_id, project__teacher=teacher)
        .first()
    )
    curated_raw = existing.session.exam_prep_json if existing is not None else ''
    curated = _parse_payload(curated_raw or '')

    # The original builder deliberately rejects edited payloads.  Clear the
    # projection inside this outer transaction so it can rebuild the canonical
    # source identity. Any error below rolls the temporary write back.
    if existing is not None and curated is not None:
        existing.session.exam_prep_json = ''
        existing.session.save(update_fields=['exam_prep_json', 'updated_at'])

    result = _ORIGINAL_BUILD_LEGACY_PROJECTION(
        teacher=teacher,
        project_id=project_id,
    )
    if curated is None:
        return result

    current_projection = (
        ExamV4Projection.objects.select_for_update()
        .select_related('session', 'project')
        .get(project_id=project_id)
    )
    generated = _parse_payload(current_projection.session.exam_prep_json or '')
    if generated is None:
        raise projection.ProjectionIntegrityError('Fresh V4 projection payload is unavailable.')

    if projection._hash_payload(projection._normalized_payload(curated)) == projection._hash_payload(
        projection._normalized_payload(generated)
    ):
        return result

    merged = merge_teacher_curated_projection(curated, generated)
    merged_json = json.dumps(
        merged,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    )
    fingerprint = projection._hash_payload(merged)
    current_projection.session.exam_prep_json = merged_json
    current_projection.session.save(update_fields=['exam_prep_json', 'updated_at'])
    current_projection.projection_fingerprint = fingerprint
    current_projection.save(update_fields=['projection_fingerprint', 'updated_at'])

    project = ExamProject.objects.select_for_update().get(id=project_id, teacher=teacher)
    state = dict(project.workflow_state) if isinstance(project.workflow_state, dict) else {}
    state.update(
        {
            'projectionFingerprintPrefix': fingerprint[:12],
            'teacherCuratedProjection': True,
            'teacherCuratedAt': timezone.now().isoformat(),
            'lastEventAt': timezone.now().isoformat(),
        }
    )
    project.reviewed_projection_fingerprint = fingerprint
    project.workflow_state = state
    project.save(
        update_fields=[
            'reviewed_projection_fingerprint',
            'workflow_state',
            'updated_at',
        ]
    )
    return {
        **result,
        'projectionFingerprint': fingerprint,
        'reused': False,
        'teacherCurated': True,
    }


def _direct_solution_option_map(analysis: Mapping[str, Any]) -> dict[int, str]:
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
            option = normalize_solution_option_label(region.get('correctOptionLabel'))
            if number is None or option is None:
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


def _numeric_label(value: Any) -> str | None:
    raw = str(value or '').strip().translate(
        str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')
    )
    digits = ''.join(character for character in raw if character.isdigit())
    if not digits:
        return None
    try:
        parsed = int(digits)
    except ValueError:
        return None
    return str(parsed) if parsed in {1, 2, 3, 4, 10, 20, 30, 40} else None


def _apply_source_option_labels(raw: Any, option_map: Mapping[int, str]) -> Any:
    if not isinstance(raw, Mapping) or not isinstance(raw.get('answers'), list):
        return raw
    result = dict(raw)
    answers: list[Any] = []
    for item in raw['answers']:
        if not isinstance(item, Mapping):
            answers.append(item)
            continue
        row = dict(item)
        number = source_first._region_number({'questionNumber': row.get('printedNumber')})
        source_label = option_map.get(number) if number is not None else None
        existing = row.get('correctOption')
        # Never translate between numeric and alphabetic label systems.  The
        # projection validates that a label exists in the question options.
        if source_label and (not str(existing or '').strip() or _numeric_label(existing) is not None):
            if str(existing or '').strip() != source_label:
                row['correctOption'] = source_label
                warnings = [str(value) for value in (row.get('warnings') or [])]
                if 'source_heading_correct_option_applied' not in warnings:
                    warnings.append('source_heading_correct_option_applied')
                row['warnings'] = warnings
        answers.append(row)
    result['answers'] = answers
    return result


def _source_option_map_for_adapter(adapter: Any, document: Any) -> dict[int, str]:
    try:
        _result, analysis = adapter._ensure_document(document)
    except source_first.SourceFirstError:
        return {}
    return _direct_solution_option_map(analysis)


def _extract_answer_solutions_batch(self, *, document, items, batch_index):
    raw = self.fallback.extract_answer_solutions_batch(
        document=document,
        items=items,
        batch_index=batch_index,
    )
    return _apply_source_option_labels(raw, _source_option_map_for_adapter(self, document))


def _extract_answer_solution(self, *, document, block, evidence_blocks, images):
    raw = self.fallback.extract_answer_solution(
        document=document,
        block=block,
        evidence_blocks=evidence_blocks,
        images=images,
    )
    return _apply_source_option_labels(raw, _source_option_map_for_adapter(self, document))


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    projection.build_legacy_projection = build_legacy_projection_with_teacher_curation
    source_first.MistralSourceFirstAdapter.extract_answer_solutions_batch = _extract_answer_solutions_batch
    source_first.MistralSourceFirstAdapter.extract_answer_solution = _extract_answer_solution
    _INSTALLED = True


__all__ = [
    'build_legacy_projection_with_teacher_curation',
    'install',
    'merge_teacher_curated_projection',
]
