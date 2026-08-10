"""Deterministic post-merge safety invariants for Stage 4.

A provider may return fluent structured text that is unrelated to the source
crop. Two source-independent checks catch this before later consensus guards:

* fields that were *not* authorized for repair act as source anchors. A primary
  transcription that materially disagrees with those trusted fields has no
  authority to repair sibling fields from the same crop;
* a repaired solution body may not contradict the trusted native answer label or
  an explicit leading question number.

This module makes no provider calls and never reconstructs source content. Unsafe
primary edits are rolled back field-family-wise to the pre-Stage4 question.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

from . import exam_prep_mistral_stage4 as legacy
from .exam_prep_page_records import PageAssemblyResult
from .exam_prep_question_verifier import rebuild_assembly_quality
from .exam_prep_utils import clean_exam_markdown


_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_ANCHOR_TEXT_SIMILARITY_MIN = 0.45
_LEADING_QUESTION_RE = re.compile(r"^\s*(\d{1,3})\s*[-–—.:)]")
_LEADING_OPTION_RE = re.compile(
    r"^\s*(?:\d{1,3}\s*[-–—.:)]\s*)?"
    r"(?:پاسخ\s*[:\-–—]?\s*)?"
    r"(?:گزینه|گزینۀ)\s*([1-4])\b"
)


def _number(value: Any) -> int:
    try:
        return int(str(value or "").translate(_DIGITS))
    except (TypeError, ValueError):
        return 0


def _question_map(result: PageAssemblyResult) -> dict[int, dict[str, Any]]:
    output: dict[int, dict[str, Any]] = {}
    for raw in (result.projection.get("exam_prep") or {}).get("questions") or []:
        if not isinstance(raw, Mapping):
            continue
        number = _number(raw.get("source_question_number"))
        if number > 0:
            output[number] = dict(raw)
    return output


def _is_repair_status(value: Any) -> bool:
    return str(value or "").startswith("repaired") or str(value or "").startswith(
        "partial_repair"
    )


def _anchor_conflicts(row: Mapping[str, Any]) -> list[str]:
    if str(row.get("kind") or "") != "question" or not _is_repair_status(row.get("status")):
        return []
    needed = {str(field) for field in (row.get("neededFields") or []) if str(field)}
    agreements = row.get("candidateFieldAgreement")
    if not isinstance(agreements, Mapping):
        return []

    conflicts: list[str] = []
    for field, raw in agreements.items():
        field = str(field or "")
        if not field or field in needed or not isinstance(raw, Mapping):
            continue
        # Non-needed fields are not permission to repair; they are an independent
        # source anchor from the same crop. Numeric/math conflicts are hard vetoes.
        if bool(raw.get("criticalConflict")):
            conflicts.append(field)
            continue
        # Pure prose differences do not set criticalConflict in the shared field
        # comparator. A very low literal overlap still proves that this is not a
        # transcription of the same visible field.
        try:
            similarity = float(raw.get("textSimilarity") or 0)
        except (TypeError, ValueError):
            similarity = 0.0
        if similarity < _ANCHOR_TEXT_SIMILARITY_MIN:
            conflicts.append(field)
    return sorted(set(conflicts))


def _leading_solution_evidence(body: Any) -> tuple[int, str]:
    text = clean_exam_markdown(body or "").translate(_DIGITS)
    prefix = text[:220].strip()
    question_number = 0
    option_label = ""
    number_match = _LEADING_QUESTION_RE.match(prefix)
    if number_match:
        question_number = int(number_match.group(1))
    option_match = _LEADING_OPTION_RE.match(prefix)
    if option_match:
        option_label = option_match.group(1)
    return question_number, option_label


def _solution_invariant_conflicts(
    row: Mapping[str, Any],
    *,
    original_question: Mapping[str, Any],
    current_question: Mapping[str, Any],
) -> list[str]:
    if str(row.get("kind") or "") != "solution" or not _is_repair_status(row.get("status")):
        return []
    needed = {str(field) for field in (row.get("neededFields") or []) if str(field)}
    if "teacher_solution_markdown" not in needed:
        return []

    body = current_question.get("teacher_solution_markdown")
    leading_number, leading_label = _leading_solution_evidence(body)
    target_number = _number(row.get("questionNumber"))
    conflicts: list[str] = []
    if leading_number and target_number and leading_number != target_number:
        conflicts.append("leading_question_number")

    issues = {str(code) for code in (original_question.get("issues") or []) if str(code)}
    if "native_pdf_answer_label_authority" in issues and leading_label:
        native_label = str(original_question.get("correct_option_label") or "").translate(_DIGITS).strip()
        if native_label in {"1", "2", "3", "4"} and leading_label != native_label:
            conflicts.append("native_answer_label")
    return conflicts


def _rollback_kind(
    original: Mapping[str, Any],
    current: Mapping[str, Any],
    *,
    kind: str,
) -> dict[str, Any]:
    restored = dict(current)
    if kind == "question":
        restored["question_text_markdown"] = original.get("question_text_markdown") or ""
        restored["options"] = [dict(item) for item in (original.get("options") or []) if isinstance(item, Mapping)]
    else:
        restored["teacher_solution_markdown"] = original.get("teacher_solution_markdown") or ""
    return legacy._mark_unresolved(restored)


def enforce_source_invariants(
    original: PageAssemblyResult,
    updated: PageAssemblyResult,
    audit: Mapping[str, Any],
) -> tuple[PageAssemblyResult, dict[str, Any]]:
    """Rollback direct repairs whose same-crop source invariants fail."""

    original_questions = _question_map(original)
    current_questions = _question_map(updated)
    rows = [dict(row) for row in (audit.get("regions") or []) if isinstance(row, Mapping)]
    stats = dict(audit.get("stats") or {})
    repaired = int(stats.get("repaired") or 0)
    partial = int(stats.get("partialRepairs") or 0)
    verified = int(stats.get("verified") or 0)
    unresolved = int(stats.get("unresolved") or 0)
    guarded = anchor_rollbacks = solution_rollbacks = 0

    for row in rows:
        if not _is_repair_status(row.get("status")):
            continue
        number = _number(row.get("questionNumber"))
        original_question = original_questions.get(number)
        current_question = current_questions.get(number)
        if original_question is None or current_question is None:
            continue

        anchor_conflicts = _anchor_conflicts(row)
        solution_conflicts = _solution_invariant_conflicts(
            row,
            original_question=original_question,
            current_question=current_question,
        )
        if not anchor_conflicts and not solution_conflicts:
            continue

        guarded += 1
        kind = str(row.get("kind") or "")
        current_questions[number] = _rollback_kind(
            original_question,
            current_question,
            kind=kind,
        )
        old_status = str(row.get("status") or "")
        repaired = max(0, repaired - 1)
        if old_status.startswith("partial_repair"):
            partial = max(0, partial - 1)
        # Every direct repaired branch in the page-batch orchestrator also counts
        # as verified. Removing its source authority removes that verified vote.
        verified = max(0, verified - 1)
        unresolved += 1

        if anchor_conflicts:
            anchor_rollbacks += 1
            row["status"] = "source_anchor_conflict_rolled_back"
            row["reason"] = "non_needed_source_field_disagrees"
            row["sourceAnchorConflictFields"] = anchor_conflicts
        else:
            solution_rollbacks += 1
            row["status"] = "solution_source_invariant_rolled_back"
            row["reason"] = "solution_body_contradicts_trusted_source_structure"
            row["solutionInvariantConflicts"] = solution_conflicts

    projection = dict(updated.projection)
    exam = dict(projection.get("exam_prep") or {})
    rebuilt: list[dict[str, Any]] = []
    for raw in exam.get("questions") or []:
        if not isinstance(raw, Mapping):
            continue
        number = _number(raw.get("source_question_number"))
        rebuilt.append(dict(current_questions.get(number, raw)))
    exam["questions"] = rebuilt
    projection["exam_prep"] = exam
    guarded_result = updated.model_copy(update={"projection": projection})
    guarded_result = rebuild_assembly_quality(guarded_result)

    stats.update(
        {
            "repaired": repaired,
            "partialRepairs": partial,
            "verified": verified,
            "unresolved": unresolved,
            "sourceInvariantGuardedTargets": guarded,
            "sourceAnchorRollbacks": anchor_rollbacks,
            "solutionInvariantRollbacks": solution_rollbacks,
        }
    )
    output_audit = dict(audit)
    output_audit["stats"] = stats
    output_audit["regions"] = rows
    policy = dict(output_audit.get("policy") or {})
    policy["nonNeededFieldsAreSourceAnchors"] = True
    policy["nativeAnswerLabelConstrainsSolutionBody"] = True
    output_audit["policy"] = policy
    return guarded_result, output_audit


__all__ = [
    "_anchor_conflicts",
    "_leading_solution_evidence",
    "_solution_invariant_conflicts",
    "enforce_source_invariants",
]
