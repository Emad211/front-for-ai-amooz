"""Deterministic validation for teacher-edited page-first exam projections.

This module consumes only the existing canonical ``exam_prep_json`` shape. It
never calls a model, reads a source file, or creates legacy extraction artifacts.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import json
from typing import Any

from .exam_prep_utils import clean_exam_markdown


CRITICAL_CODES = frozenset(
    {
        'no_questions',
        'missing_question_id',
        'duplicate_question_id',
        'duplicate_question_number',
        'missing_question_number',
        'missing_question_text',
        'missing_options',
        'duplicate_option_label',
        'missing_option_text',
        'missing_answer',
        'correct_option_not_in_options',
        'failed_chunk',
    }
)


def _questions(projection: object) -> list[dict[str, Any]]:
    if not isinstance(projection, dict):
        return []
    exam = projection.get('exam_prep')
    if not isinstance(exam, dict):
        return []
    raw = exam.get('questions')
    return [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []


def _question_number(question: dict[str, Any]) -> int | None:
    raw = question.get('source_question_number')
    if raw in (None, ''):
        raw = question.get('question_number')
    text = str(raw or '').translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789'))
    digits = ''.join(char for char in text if char.isdigit())
    if not digits:
        return None
    value = int(digits)
    return value if value > 0 else None


def audit_page_first_projection(projection: object) -> dict[str, Any]:
    """Return the existing frontend audit shape for canonical exam JSON."""

    questions = _questions(projection)
    issues: list[dict[str, Any]] = []
    ids: Counter[str] = Counter()
    numbers_by_scope: dict[str, list[int]] = defaultdict(list)
    matched_answers = 0

    def add_issue(code: str, *, scope: str, number: int, pages: list[int] | None = None) -> None:
        issues.append(
            {
                'code': code,
                'severity': 'critical' if code in CRITICAL_CODES else 'warning',
                'scopeKey': scope,
                'questionNumber': number,
                'sourcePages': list(pages or []),
            }
        )

    if not questions:
        add_issue('no_questions', scope='default', number=0)

    for index, question in enumerate(questions, start=1):
        scope = clean_exam_markdown(question.get('scope_key') or 'default').strip() or 'default'
        number = _question_number(question) or index
        pages = [
            int(value)
            for value in (question.get('source_pages') or [])
            if str(value).isdigit() and int(value) > 0
        ]
        question_id = clean_exam_markdown(question.get('question_id') or '').strip()
        if question_id:
            ids[question_id] += 1
        else:
            add_issue('missing_question_id', scope=scope, number=number, pages=pages)

        parsed_number = _question_number(question)
        if parsed_number is not None:
            numbers_by_scope[scope].append(parsed_number)

        if not clean_exam_markdown(question.get('question_text_markdown') or '').strip():
            add_issue('missing_question_text', scope=scope, number=number, pages=pages)

        options = question.get('options')
        valid_options = [item for item in options if isinstance(item, dict)] if isinstance(options, list) else []
        if len(valid_options) < 2:
            add_issue('missing_options', scope=scope, number=number, pages=pages)
        labels: list[str] = []
        for option in valid_options:
            label = clean_exam_markdown(option.get('label') or '').strip()
            text = clean_exam_markdown(option.get('text_markdown') or '').strip()
            if label:
                labels.append(label)
            if not text:
                add_issue('missing_option_text', scope=scope, number=number, pages=pages)
        if len(labels) != len(set(labels)):
            add_issue('duplicate_option_label', scope=scope, number=number, pages=pages)

        correct = clean_exam_markdown(question.get('correct_option_label') or '').strip()
        answer_present = bool(
            correct
            or clean_exam_markdown(question.get('correct_option_text_markdown') or '').strip()
            or clean_exam_markdown(question.get('final_answer_markdown') or '').strip()
            or clean_exam_markdown(question.get('teacher_solution_markdown') or '').strip()
        )
        if not answer_present:
            add_issue('missing_answer', scope=scope, number=number, pages=pages)
        else:
            matched_answers += 1
        if correct and labels and correct not in labels:
            add_issue('correct_option_not_in_options', scope=scope, number=number, pages=pages)

    for question_id, count in ids.items():
        if count > 1:
            for question in questions:
                if clean_exam_markdown(question.get('question_id') or '').strip() == question_id:
                    add_issue(
                        'duplicate_question_id',
                        scope=clean_exam_markdown(question.get('scope_key') or 'default').strip() or 'default',
                        number=_question_number(question) or 0,
                        pages=list(question.get('source_pages') or []),
                    )
                    break

    gaps: dict[str, list[int]] = {}
    for scope, values in numbers_by_scope.items():
        counts = Counter(values)
        for number, count in counts.items():
            if count > 1:
                add_issue('duplicate_question_number', scope=scope, number=number)
        unique = sorted(counts)
        if len(unique) >= 2 and unique[-1] - unique[0] <= 500:
            missing = [number for number in range(unique[0], unique[-1] + 1) if number not in counts]
            if missing:
                gaps[scope] = missing
                for number in missing:
                    add_issue('missing_question_number', scope=scope, number=number)

    critical_count = sum(issue['severity'] == 'critical' for issue in issues)
    return {
        'status': 'passed' if questions and critical_count == 0 else 'needs_review',
        'questionCount': len(questions),
        'matchedAnswerCount': matched_answers,
        'outOfScopeAnswerCount': 0,
        'criticalIssueCount': critical_count,
        'issues': issues,
        'failedPageNumbers': [],
        'questionNumberGaps': gaps,
    }


def retain_failed_page_evidence(
    audit: dict[str, Any],
    failed_page_numbers: object,
) -> dict[str, Any]:
    """Keep source failures critical until a fresh pipeline run succeeds.

    A teacher may repair visible JSON, but that cannot prove a failed physical
    page contained no additional trailing question. Only reprocessing the source
    may clear this evidence.
    """

    pages: list[int] = []
    if isinstance(failed_page_numbers, (list, tuple, set)):
        for value in failed_page_numbers:
            try:
                number = int(value)
            except (TypeError, ValueError):
                continue
            if number > 0 and number not in pages:
                pages.append(number)
    pages.sort()
    if not pages:
        return audit

    updated = dict(audit)
    issues = [dict(item) for item in (audit.get('issues') or []) if isinstance(item, dict)]
    existing_pages = {
        tuple(item.get('sourcePages') or [])
        for item in issues
        if item.get('code') == 'failed_chunk'
    }
    for page_number in pages:
        if (page_number,) in existing_pages:
            continue
        issues.append(
            {
                'code': 'failed_chunk',
                'severity': 'critical',
                'scopeKey': 'default',
                'questionNumber': 0,
                'sourcePages': [page_number],
            }
        )
    updated['issues'] = issues
    updated['failedPageNumbers'] = pages
    updated['criticalIssueCount'] = sum(
        item.get('severity') == 'critical' for item in issues
    )
    updated['status'] = 'needs_review'
    return updated


def render_projection_transcript(projection: object, audit: dict[str, Any]) -> str:
    """Render edited canonical JSON into readable Markdown for the existing UI."""

    questions = _questions(projection)
    exam = projection.get('exam_prep') if isinstance(projection, dict) else {}
    title = clean_exam_markdown(exam.get('title') if isinstance(exam, dict) else '') or 'آمادگی آزمون'
    lines = [
        f'# {title}',
        '',
        '## خلاصهٔ استخراج',
        '',
        f"- تعداد سؤال‌ها: **{len(questions)}**",
        f"- پاسخ‌های ثبت‌شده: **{int(audit.get('matchedAnswerCount') or 0)}**",
        f"- موارد بحرانی: **{int(audit.get('criticalIssueCount') or 0)}**",
    ]
    failed_pages = audit.get('failedPageNumbers') or []
    if failed_pages:
        lines.append(
            f"- صفحه‌های نیازمند بازپردازش: **{'، '.join(map(str, failed_pages))}**"
        )
    lines.extend(['', '---', ''])
    for index, question in enumerate(questions, start=1):
        number = _question_number(question) or index
        lines.extend(
            [
                f'## سؤال {number}',
                '',
                clean_exam_markdown(question.get('question_text_markdown') or '_صورت سؤال ثبت نشده است._'),
                '',
            ]
        )
        for option in question.get('options') or []:
            if not isinstance(option, dict):
                continue
            label = clean_exam_markdown(option.get('label') or '')
            text = clean_exam_markdown(option.get('text_markdown') or '')
            if label and text:
                lines.append(f'{label}) {text}')
        correct = clean_exam_markdown(question.get('correct_option_label') or '')
        if correct:
            lines.extend(['', f'**پاسخ صحیح:** گزینه {correct}'])
        solution = clean_exam_markdown(question.get('teacher_solution_markdown') or '')
        if solution:
            lines.extend(['', '**راه‌حل تشریحی:**', '', solution])
        pages = question.get('source_pages') or []
        if pages:
            lines.extend(['', f"_صفحات منبع: {', '.join(map(str, pages))}_"])
        lines.extend(['', '---', ''])
    return '\n'.join(lines).strip() + '\n'


def parse_projection(raw: object) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}
