"""Pure inventory, matching, and audit helpers for exam-prep extraction."""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from difflib import SequenceMatcher
import hashlib
import json
import re
from typing import Any, Iterable

from .exam_prep_utils import clean_exam_markdown


_PAGE_HEADING_RE = re.compile(r"(?m)^##\s*صفحه\s+([0-9۰-۹٠-٩]+)\s*$")
_DIGIT_TRANSLATION = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)


def normalize_source_number(value: Any) -> str:
    """Return a stable Latin-digit question number without assuming it starts at 1."""
    text = clean_exam_markdown(value).translate(_DIGIT_TRANSLATION).strip()
    text = re.sub(r"^[^\w\d]+|[^\w\d]+$", "", text)
    match = re.search(r"\d+", text)
    return str(int(match.group(0))) if match else text.casefold()


def normalize_section_key(value: Any) -> str:
    text = clean_exam_markdown(value).translate(_DIGIT_TRANSLATION).casefold()
    return re.sub(r"\s+", " ", text).strip()


def parse_source_blocks(transcript_markdown: str) -> list[dict[str, Any]]:
    """Split a PDF transcript on durable page headings; media becomes one block."""
    text = (transcript_markdown or "").strip()
    if not text:
        return []
    matches = list(_PAGE_HEADING_RE.finditer(text))
    if not matches:
        return [{"page_number": 1, "block_order": 0, "content": text}]

    blocks: list[dict[str, Any]] = []
    for order, match in enumerate(matches):
        start = match.end()
        end = matches[order + 1].start() if order + 1 < len(matches) else len(text)
        page_number = int(match.group(1).translate(_DIGIT_TRANSLATION))
        blocks.append(
            {
                "page_number": page_number,
                "block_order": order,
                "content": text[start:end].strip(),
            }
        )
    return blocks


def chunk_source_blocks(
    blocks: Iterable[dict[str, Any]], *, max_chars: int
) -> list[list[dict[str, Any]]]:
    """Pack source blocks into bounded chunks, splitting only oversized blocks."""
    payload_overhead = 96
    content_limit = max(1, max_chars - payload_overhead)
    expanded: list[dict[str, Any]] = []
    for block in blocks:
        content = str(block.get("content") or "")
        if len(content) <= content_limit:
            expanded.append(block)
            continue

        start = 0
        segment_index = 0
        while start < len(content):
            end = min(start + content_limit, len(content))
            if end < len(content):
                paragraph_break = content.rfind("\n\n", start, end)
                line_break = content.rfind("\n", start, end)
                word_break = content.rfind(" ", start, end)
                preferred_break = max(paragraph_break, line_break, word_break)
                if preferred_break > start + (content_limit // 2):
                    end = preferred_break
            segment = content[start:end].strip()
            if segment:
                expanded.append(
                    {
                        **block,
                        "segment_index": segment_index,
                        "content": segment,
                    }
                )
                segment_index += 1
            start = end
            while start < len(content) and content[start].isspace():
                start += 1

    chunks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_size = 0
    for block in expanded:
        block_size = len(str(block.get("content") or "")) + payload_overhead
        if current and current_size + block_size > max_chars:
            chunks.append(current)
            current = []
            current_size = 0
        current.append(block)
        current_size += block_size
    if current:
        chunks.append(current)
    return chunks


def _question_key(record: dict[str, Any]) -> str:
    section = normalize_section_key(record.get("section_key"))
    number = normalize_source_number(record.get("source_question_number"))
    if number:
        return f"{section}::{number}"
    text = _normalized_text(record.get("question_text_markdown"))
    return f"{section}::text:{hashlib.sha256(text.encode()).hexdigest()[:20]}"


def question_record_key(record: dict[str, Any]) -> str:
    """Public stable lookup key for visual/API joins."""
    return _question_key(record)


def _normalized_text(value: Any) -> str:
    text = clean_exam_markdown(value).translate(_DIGIT_TRANSLATION).casefold()
    return re.sub(r"\W+", "", text)


def _records_equivalent(left: dict[str, Any], right: dict[str, Any]) -> bool:
    a = _normalized_text(left.get("question_text_markdown"))
    b = _normalized_text(right.get("question_text_markdown"))
    return bool(a and b) and SequenceMatcher(None, a, b).ratio() >= 0.86


def _record_completeness(record: dict[str, Any]) -> tuple[int, int]:
    return (
        len(record.get("options") or []),
        len(clean_exam_markdown(record.get("question_text_markdown"))),
    )


def _stable_question_id(record: dict[str, Any]) -> str:
    seed = json.dumps(
        {
            "section": normalize_section_key(record.get("section_key")),
            "number": normalize_source_number(record.get("source_question_number")),
            "text": _normalized_text(record.get("question_text_markdown")),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return f"q-{hashlib.sha256(seed.encode()).hexdigest()[:16]}"


def deduplicate_question_records(
    records: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Remove overlap duplicates and retain conflicting duplicate numbers for audit."""
    chosen: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    conflicts: list[dict[str, Any]] = []
    for raw in records:
        record = deepcopy(raw)
        record["source_question_number_normalized"] = normalize_source_number(
            record.get("source_question_number")
        )
        record["section_key_normalized"] = normalize_section_key(record.get("section_key"))
        key = _question_key(record)
        existing = chosen.get(key)
        if existing is None:
            chosen[key] = record
            order.append(key)
            continue
        shares_source_page = bool(
            set(existing.get("source_pages") or []).intersection(
                record.get("source_pages") or []
            )
        )
        if shares_source_page and _records_equivalent(existing, record):
            source_pages = sorted(
                set((existing.get("source_pages") or []) + (record.get("source_pages") or []))
            )
            if _record_completeness(record) > _record_completeness(existing):
                chosen[key] = record
            chosen[key]["source_pages"] = source_pages
            continue
        conflicts.append(
            {
                "code": "duplicate_question_number",
                "severity": "critical",
                "questionKey": key,
                "sourcePages": sorted(
                    set((existing.get("source_pages") or []) + (record.get("source_pages") or []))
                ),
            }
        )
    return [chosen[key] for key in order], conflicts


def _merge_answer(target: dict[str, Any], answer: dict[str, Any]) -> list[str]:
    conflicts: list[str] = []
    for field in (
        "correct_option_label",
        "correct_option_text_markdown",
        "final_answer_markdown",
    ):
        old = clean_exam_markdown(target.get(field))
        new = clean_exam_markdown(answer.get(field))
        if old and new and _normalized_text(old) != _normalized_text(new):
            conflicts.append(field)
        elif not old and new:
            target[field] = new
    old_solution = clean_exam_markdown(target.get("teacher_solution_markdown"))
    new_solution = clean_exam_markdown(answer.get("teacher_solution_markdown"))
    if len(new_solution) > len(old_solution):
        target["teacher_solution_markdown"] = new_solution
    return conflicts


def deduplicate_answer_records(
    records: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Merge compatible answer-key/detail records before question matching."""
    chosen: dict[tuple[str, str], dict[str, Any]] = {}
    unnumbered: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for raw in records:
        record = deepcopy(raw)
        number = normalize_source_number(record.get("source_question_number"))
        section = normalize_section_key(record.get("section_key"))
        if not number:
            unnumbered.append(record)
            continue
        key = (section, number)
        existing = chosen.get(key)
        if existing is None:
            chosen[key] = record
            continue
        conflicts = _merge_answer(existing, record)
        existing["source_pages"] = sorted(
            set((existing.get("source_pages") or []) + (record.get("source_pages") or []))
        )
        existing["visual_hints"] = list(
            dict.fromkeys(
                [*(existing.get("visual_hints") or []), *(record.get("visual_hints") or [])]
            )
        )
        existing["confidence"] = max(
            float(existing.get("confidence") or 0),
            float(record.get("confidence") or 0),
        )
        if conflicts:
            issues.append(
                {
                    "code": "conflicting_answers",
                    "severity": "critical",
                    "questionKey": f"{section}::{number}",
                    "fields": conflicts,
                    "sourcePages": existing["source_pages"],
                }
            )
    return [*chosen.values(), *unnumbered], issues


def annotate_answer_match_status(
    records: Iterable[dict[str, Any]],
    unmatched: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return one durable answer inventory row per extracted answer."""
    unmatched_by_key = {
        (
            normalize_section_key(record.get("section_key")),
            normalize_source_number(record.get("source_question_number")),
            tuple(sorted(record.get("source_pages") or [])),
            int(record.get("block_order") or 0),
        ): record.get("match_status") or "unmatched"
        for record in unmatched
    }
    annotated = []
    for raw in records:
        record = deepcopy(raw)
        key = (
            normalize_section_key(record.get("section_key")),
            normalize_source_number(record.get("source_question_number")),
            tuple(sorted(record.get("source_pages") or [])),
            int(record.get("block_order") or 0),
        )
        record["match_status"] = unmatched_by_key.get(key, "matched")
        annotated.append(record)
    return annotated


def match_answers_to_questions(
    question_records: Iterable[dict[str, Any]],
    answer_records: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Join independently extracted answers without inventing question records."""
    questions = [deepcopy(record) for record in question_records]
    by_composite: dict[tuple[str, str], list[int]] = defaultdict(list)
    by_number: dict[str, list[int]] = defaultdict(list)
    for index, question in enumerate(questions):
        number = normalize_source_number(question.get("source_question_number"))
        section = normalize_section_key(question.get("section_key"))
        if number:
            by_composite[(section, number)].append(index)
            by_number[number].append(index)

    unmatched: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    matched_indexes: set[int] = set()

    for raw in answer_records:
        answer = deepcopy(raw)
        number = normalize_source_number(answer.get("source_question_number"))
        section = normalize_section_key(answer.get("section_key"))
        candidates = by_composite.get((section, number), []) if number else []
        provenance = "section_number"
        if len(candidates) != 1 and number and len(by_number.get(number, [])) == 1:
            candidates = by_number[number]
            provenance = "unique_number"
        if not candidates and not number:
            page_set = set(answer.get("source_pages") or [])
            preceding = [
                index
                for index, question in enumerate(questions)
                if page_set.intersection(question.get("source_pages") or [])
                and int(question.get("block_order") or 0) <= int(answer.get("block_order") or 0)
            ]
            if preceding:
                candidates = [max(preceding, key=lambda i: int(questions[i].get("block_order") or 0))]
                provenance = "same_page_adjacency"

        if len(candidates) != 1:
            answer["match_status"] = "out_of_scope" if number and number not in by_number else "unmatched"
            unmatched.append(answer)
            continue

        index = candidates[0]
        question = questions[index]
        conflicts = _merge_answer(question, answer)
        question["match_provenance"] = provenance
        question["answer_source_pages"] = answer.get("source_pages") or []
        matched_indexes.add(index)
        if conflicts:
            issues.append(
                {
                    "code": "conflicting_answers",
                    "severity": "critical",
                    "questionKey": _question_key(question),
                    "fields": conflicts,
                }
            )

    for index, question in enumerate(questions):
        question["question_id"] = question.get("question_id") or _stable_question_id(question)
        question.setdefault("visuals", [])
        if index not in matched_indexes:
            issues.append(
                {
                    "code": "missing_answer",
                    "severity": "critical",
                    "questionKey": _question_key(question),
                }
            )
    return questions, unmatched, issues


def build_exam_projection(
    *, title: str, questions: Iterable[dict[str, Any]]
) -> dict[str, Any]:
    """Build the backward-compatible public projection without fabricating solutions."""
    projected = []
    for raw in questions:
        question = deepcopy(raw)
        projected.append(
            {
                "question_id": question["question_id"],
                "question_text_markdown": clean_exam_markdown(
                    question.get("question_text_markdown")
                ),
                "options": question.get("options") or [],
                "correct_option_label": question.get("correct_option_label") or None,
                "correct_option_text_markdown": question.get(
                    "correct_option_text_markdown"
                )
                or None,
                "teacher_solution_markdown": clean_exam_markdown(
                    question.get("teacher_solution_markdown")
                ),
                "final_answer_markdown": clean_exam_markdown(
                    question.get("final_answer_markdown")
                ),
                "confidence": question.get("confidence"),
                "issues": question.get("issues") or [],
                "visuals": question.get("visuals") or [],
                "_source": {
                    "questionNumber": question.get("source_question_number"),
                    "sectionKey": question.get("section_key") or "",
                    "pages": question.get("source_pages") or [],
                    "matchProvenance": question.get("match_provenance") or "",
                },
            }
        )
    return {"exam_prep": {"title": clean_exam_markdown(title), "questions": projected}}


def build_extraction_audit(
    *,
    questions: list[dict[str, Any]],
    unmatched_answers: list[dict[str, Any]],
    issues: Iterable[dict[str, Any]],
    failed_chunks: Iterable[dict[str, Any]] = (),
    page_manifest: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    all_issues = [deepcopy(issue) for issue in issues]
    for chunk in failed_chunks:
        all_issues.append(
            {
                "code": "failed_chunk",
                "severity": "critical",
                "detail": deepcopy(chunk),
            }
        )
    for answer in unmatched_answers:
        if answer.get("match_status") == "unmatched":
            all_issues.append(
                {
                    "code": "unmatched_answer",
                    "severity": "critical",
                    "sourceQuestionNumber": answer.get("source_question_number"),
                    "sourcePages": answer.get("source_pages") or [],
                }
            )
    if not questions:
        all_issues.append({"code": "no_questions", "severity": "critical"})

    manifest_pages = {
        int(page["page_number"])
        for page in page_manifest
        if isinstance(page, dict) and page.get("page_number")
    }
    covered_pages = {
        int(page)
        for question in questions
        for page in question.get("source_pages") or []
    }
    critical = [issue for issue in all_issues if issue.get("severity") == "critical"]
    return {
        "status": "passed" if not critical else "needs_review",
        "questionCount": len(questions),
        "matchedAnswerCount": sum(
            1 for question in questions if question.get("match_provenance")
        ),
        "outOfScopeAnswerCount": sum(
            1 for answer in unmatched_answers if answer.get("match_status") == "out_of_scope"
        ),
        "criticalIssueCount": len(critical),
        "issues": all_issues,
        "manifestPageCount": len(manifest_pages),
        "questionSourcePageCount": len(covered_pages),
    }


_NON_CONTENT_CRITICAL_CODES = {
    "failed_chunk",
    "invalid_visual_bbox",
    "missing_visual_asset",
    "unmatched_visual",
    "unprocessed_source_block",
    "visual_processing_failed",
}


def rebuild_audit_after_teacher_review(
    *,
    projection: dict[str, Any],
    previous_audit: dict[str, Any],
    available_visual_ids: set[int],
) -> dict[str, Any]:
    """Recheck teacher-editable content without concealing pipeline failures."""
    questions = (projection.get("exam_prep") or {}).get("questions") or []
    issues = [
        deepcopy(issue)
        for issue in previous_audit.get("issues") or []
        if issue.get("code") in _NON_CONTENT_CRITICAL_CODES
    ]
    seen_ids: set[str] = set()

    for index, question in enumerate(questions, start=1):
        question_id = str(question.get("question_id") or "").strip()
        if not question_id or question_id in seen_ids:
            issues.append(
                {
                    "code": "duplicate_or_missing_question_id",
                    "severity": "critical",
                    "questionIndex": index,
                }
            )
        seen_ids.add(question_id)

        if not str(question.get("question_text_markdown") or "").strip():
            issues.append(
                {
                    "code": "missing_question_text",
                    "severity": "critical",
                    "questionId": question_id,
                }
            )

        options = question.get("options") or []
        if options and len(options) < 2:
            issues.append(
                {
                    "code": "incomplete_options",
                    "severity": "critical",
                    "questionId": question_id,
                }
            )

        has_answer = any(
            str(question.get(field) or "").strip()
            for field in (
                "correct_option_label",
                "correct_option_text_markdown",
                "final_answer_markdown",
                "teacher_solution_markdown",
            )
        )
        if not has_answer:
            issues.append(
                {
                    "code": "missing_answer",
                    "severity": "critical",
                    "questionId": question_id,
                }
            )

        for visual in question.get("visuals") or []:
            try:
                visual_id = int(visual.get("id"))
            except (AttributeError, TypeError, ValueError):
                visual_id = 0
            if visual_id not in available_visual_ids:
                issues.append(
                    {
                        "code": "missing_visual_asset",
                        "severity": "critical",
                        "questionId": question_id,
                        "visualId": visual_id or None,
                    }
                )

    if not questions:
        issues.append({"code": "no_questions", "severity": "critical"})

    critical = [issue for issue in issues if issue.get("severity") == "critical"]
    return {
        **previous_audit,
        "status": "passed" if not critical else "needs_review",
        "questionCount": len(questions),
        "criticalIssueCount": len(critical),
        "issues": issues,
        "teacherReviewed": True,
    }
