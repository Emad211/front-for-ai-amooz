"""Pure utility functions for normalizing exam-prep data.

Kept separate from views/tasks to avoid circular imports.
"""

from __future__ import annotations

import json


def normalize_exam_prep_questions(exam_prep_obj: dict) -> tuple[dict, bool]:
    """Ensure each question has a unique, non-empty question_id."""
    changed = False
    if not isinstance(exam_prep_obj, dict):
        return exam_prep_obj, False

    exam_prep = exam_prep_obj.get('exam_prep')
    if not isinstance(exam_prep, dict):
        return exam_prep_obj, False

    questions = exam_prep.get('questions')
    if not isinstance(questions, list):
        return exam_prep_obj, False

    used_ids: set[str] = set()
    for idx, q in enumerate(questions):
        if not isinstance(q, dict):
            continue
        qid = str(q.get('question_id') or '').strip()
        if not qid or qid in used_ids:
            base = f"q-{idx + 1}"
            qid = base
            suffix = 1
            while qid in used_ids:
                suffix += 1
                qid = f"{base}-{suffix}"
            q['question_id'] = qid
            changed = True
        used_ids.add(qid)

    return exam_prep_obj, changed


def normalize_exam_prep_json(raw_value: object) -> tuple[str | None, bool]:
    """Normalize exam_prep_json and return JSON string + changed flag."""
    if raw_value is None:
        return None, False

    obj: object = raw_value
    if isinstance(raw_value, str):
        s = raw_value.strip()
        if not s:
            return s, False
        try:
            obj = json.loads(s)
        except Exception:
            return raw_value, False

    if not isinstance(obj, dict):
        try:
            return json.dumps(obj, ensure_ascii=False), False
        except Exception:
            return None, False

    normalized, changed = normalize_exam_prep_questions(obj)
    return json.dumps(normalized, ensure_ascii=False), changed
