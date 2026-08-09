"""Deterministic validation for teacher-edited page-first projections."""
from __future__ import annotations

from collections import Counter, defaultdict
import json
from typing import Any

from .exam_prep_mistral_visual_review import (
    VISUAL_CRITICAL_ISSUE_CODES,
    visual_metadata_issue_codes,
)
from .exam_prep_page_output import is_critical_page_issue
from .exam_prep_question_verifier import canonical_question_issues
from .exam_prep_utils import clean_exam_markdown


_DIGIT_TRANSLATION = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)

# These codes describe an uncertain source/model judgement rather than a
# deterministic malformed question. A teacher can explicitly acknowledge them.
# Structural checks and Stage-3 visual sanity are always recomputed and cannot
# be bypassed merely by removing a stored issue string.
_TEACHER_OVERRIDABLE_CODES = frozenset(
    {
        "source_verification_failed",
        "targeted_repair_unresolved",
        "targeted_repair_failed",
        "targeted_repair_no_source_page",
        "solution_semantic_mismatch_candidate",
        "duplicate_solution_across_questions",
        "table_incomplete",
        "count_answer_unresolved",
    }
)


def _questions(projection: object) -> list[dict[str, Any]]:
    if not isinstance(projection, dict):
        return []
    exam = projection.get("exam_prep")
    if not isinstance(exam, dict):
        return []
    raw = exam.get("questions")
    return [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []


def _question_number(question: dict[str, Any]) -> int | None:
    raw = question.get("source_question_number")
    if raw in (None, ""):
        raw = question.get("question_number")
    text = str(raw or "").translate(_DIGIT_TRANSLATION)
    digits = "".join(char for char in text if char.isdigit())
    if not digits:
        return None
    value = int(digits)
    return value if value > 0 else None


def _source_pages(question: dict[str, Any]) -> list[int]:
    pages: list[int] = []
    for value in question.get("source_pages") or []:
        try:
            page = int(value)
        except (TypeError, ValueError):
            continue
        if page > 0 and page not in pages:
            pages.append(page)
    return pages


def _teacher_reviewed_codes(question: dict[str, Any]) -> set[str]:
    raw = question.get("teacher_reviewed_issue_codes")
    if not isinstance(raw, list):
        return set()
    return {
        code
        for value in raw
        if (code := clean_exam_markdown(value).strip())
    }


def _has_question_visual(question: dict[str, Any]) -> bool:
    return any(
        isinstance(item, dict)
        and item.get("role") != "solution"
        and (item.get("id") or item.get("dataUrl"))
        for item in (question.get("visuals") or [])
    )


def _teacher_can_override(
    code: str,
    *,
    question: dict[str, Any],
    reviewed_codes: set[str],
) -> bool:
    if code in VISUAL_CRITICAL_ISSUE_CODES:
        return False
    if code not in reviewed_codes:
        return False
    if code == "visual_evidence_required":
        return _has_question_visual(question)
    if code == "count_answer_unresolved":
        return bool(
            clean_exam_markdown(question.get("correct_option_label") or "")
            or clean_exam_markdown(question.get("final_answer_markdown") or "")
        )
    return code in _TEACHER_OVERRIDABLE_CODES


def audit_page_first_projection(projection: object) -> dict[str, Any]:
    """Re-audit normalized teacher JSON with production semantic/visual rules."""

    questions = _questions(projection)
    issues: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int, tuple[int, ...]]] = set()
    ids: Counter[str] = Counter()
    numbers_by_scope: dict[str, list[int]] = defaultdict(list)
    answer_key_count = 0
    solution_count = 0

    def add_issue(
        code: str,
        *,
        scope: str,
        number: int,
        pages: list[int] | None = None,
    ) -> None:
        key = (code, scope, number, tuple(pages or []))
        if key in seen:
            return
        seen.add(key)
        issues.append(
            {
                "code": code,
                "severity": (
                    "critical"
                    if is_critical_page_issue(code)
                    or code in VISUAL_CRITICAL_ISSUE_CODES
                    else "warning"
                ),
                "scopeKey": scope,
                "questionNumber": number,
                "sourcePages": list(pages or []),
            }
        )

    if not questions:
        add_issue("no_questions", scope="default", number=0)

    for index, question in enumerate(questions, start=1):
        scope = clean_exam_markdown(question.get("scope_key") or "default").strip() or "default"
        number = _question_number(question) or index
        pages = _source_pages(question)
        reviewed_codes = _teacher_reviewed_codes(question)
        question_id = clean_exam_markdown(question.get("question_id") or "").strip()
        if question_id:
            ids[question_id] += 1
        else:
            add_issue("missing_question_id", scope=scope, number=number, pages=pages)

        parsed_number = _question_number(question)
        if parsed_number is not None:
            numbers_by_scope[scope].append(parsed_number)

        derived_codes = list(
            dict.fromkeys(
                [
                    *canonical_question_issues(question),
                    *visual_metadata_issue_codes(question),
                ]
            )
        )
        for code in derived_codes:
            if _teacher_can_override(
                code,
                question=question,
                reviewed_codes=reviewed_codes,
            ):
                continue
            if (
                code == "visual_evidence_required"
                and _has_question_visual(question)
                and not visual_metadata_issue_codes(question)
            ):
                continue
            add_issue(code, scope=scope, number=number, pages=pages)

        if any(
            clean_exam_markdown(question.get(field) or "")
            for field in (
                "correct_option_label",
                "correct_option_text_markdown",
                "final_answer_markdown",
            )
        ):
            answer_key_count += 1
        elif clean_exam_markdown(question.get("teacher_solution_markdown") or ""):
            answer_key_count += 1
        else:
            add_issue("missing_answer", scope=scope, number=number, pages=pages)

        if len(clean_exam_markdown(question.get("teacher_solution_markdown") or "")) >= 24:
            solution_count += 1

    for question_id, count in ids.items():
        if count <= 1:
            continue
        for question in questions:
            if clean_exam_markdown(question.get("question_id") or "").strip() == question_id:
                add_issue(
                    "duplicate_question_id",
                    scope=clean_exam_markdown(question.get("scope_key") or "default").strip() or "default",
                    number=_question_number(question) or 0,
                    pages=_source_pages(question),
                )
                break

    gaps: dict[str, list[int]] = {}
    for scope, values in numbers_by_scope.items():
        counts = Counter(values)
        for number, count in counts.items():
            if count > 1:
                add_issue("duplicate_question_number", scope=scope, number=number)
        unique = sorted(counts)
        if len(unique) >= 2 and unique[-1] - unique[0] <= 500:
            missing = [
                number
                for number in range(unique[0], unique[-1] + 1)
                if number not in counts
            ]
            if missing:
                gaps[scope] = missing
                for number in missing:
                    add_issue("missing_question_number", scope=scope, number=number)

    critical_count = sum(issue["severity"] == "critical" for issue in issues)
    critical_keys = {
        (str(issue.get("scopeKey") or "default"), int(issue.get("questionNumber") or 0))
        for issue in issues
        if issue["severity"] == "critical" and int(issue.get("questionNumber") or 0) > 0
    }
    return {
        "status": "passed" if questions and critical_count == 0 else "needs_review",
        "questionCount": len(questions),
        "usableQuestionCount": max(0, len(questions) - len(critical_keys)),
        "questionsNeedingReview": len(critical_keys),
        "matchedAnswerCount": answer_key_count,
        "matchedSolutionCount": solution_count,
        "answerKeyOnlyCount": max(0, answer_key_count - solution_count),
        "outOfScopeAnswerCount": 0,
        "criticalIssueCount": critical_count,
        "issues": issues,
        "failedPageNumbers": [],
        "questionNumberGaps": gaps,
    }


def retain_failed_page_evidence(
    audit: dict[str, Any],
    failed_page_numbers: object,
) -> dict[str, Any]:
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
    issues = [dict(item) for item in (audit.get("issues") or []) if isinstance(item, dict)]
    existing_pages = {
        tuple(item.get("sourcePages") or [])
        for item in issues
        if item.get("code") == "failed_chunk"
    }
    for page_number in pages:
        if (page_number,) not in existing_pages:
            issues.append(
                {
                    "code": "failed_chunk",
                    "severity": "critical",
                    "scopeKey": "default",
                    "questionNumber": 0,
                    "sourcePages": [page_number],
                }
            )
    updated["issues"] = issues
    updated["failedPageNumbers"] = pages
    updated["criticalIssueCount"] = sum(item.get("severity") == "critical" for item in issues)
    updated["status"] = "needs_review"
    return updated


def render_projection_transcript(projection: object, audit: dict[str, Any]) -> str:
    questions = _questions(projection)
    exam = projection.get("exam_prep") if isinstance(projection, dict) else {}
    title = clean_exam_markdown(exam.get("title") if isinstance(exam, dict) else "") or "آمادگی آزمون"
    lines = [
        f"# {title}",
        "",
        "## خلاصهٔ استخراج",
        "",
        f"- سؤال‌های استخراج‌شده: **{len(questions)}**",
        f"- سؤال‌های آمادهٔ استفاده: **{int(audit.get('usableQuestionCount') or 0)}**",
        f"- سؤال‌های نیازمند بازبینی: **{int(audit.get('questionsNeedingReview') or 0)}**",
        f"- کلید پاسخ ثبت‌شده: **{int(audit.get('matchedAnswerCount') or 0)}**",
        f"- راه‌حل تشریحی ثبت‌شده: **{int(audit.get('matchedSolutionCount') or 0)}**",
        f"- خطاهای بحرانی: **{int(audit.get('criticalIssueCount') or 0)}**",
    ]
    failed_pages = audit.get("failedPageNumbers") or []
    if failed_pages:
        lines.append(f"- صفحه‌های نیازمند بازپردازش: **{'، '.join(map(str, failed_pages))}**")
    if audit.get("status") != "passed":
        lines.extend(["", "> این خروجی تا رفع خطاهای بحرانی قابل انتشار نیست."])
    lines.extend(["", "---", ""])

    issues_by_number: dict[int, list[str]] = defaultdict(list)
    for issue in audit.get("issues") or []:
        if not isinstance(issue, dict):
            continue
        number = int(issue.get("questionNumber") or 0)
        code = clean_exam_markdown(issue.get("code") or "").strip()
        if number > 0 and code and code not in issues_by_number[number]:
            issues_by_number[number].append(code)

    for index, question in enumerate(questions, start=1):
        number = _question_number(question) or index
        lines.extend(
            [
                f"## سؤال {number}",
                "",
                clean_exam_markdown(question.get("question_text_markdown") or "_صورت سؤال ثبت نشده است._"),
                "",
            ]
        )
        for option in question.get("options") or []:
            if not isinstance(option, dict):
                continue
            label = clean_exam_markdown(option.get("label") or "")
            text = clean_exam_markdown(option.get("text_markdown") or "")
            if label and text:
                lines.append(f"{label}) {text}")
        correct = clean_exam_markdown(question.get("correct_option_label") or "")
        if correct:
            lines.extend(["", f"**پاسخ صحیح:** گزینه {correct}"])
        solution = clean_exam_markdown(question.get("teacher_solution_markdown") or "")
        if solution:
            lines.extend(["", "**راه‌حل تشریحی:**", "", solution])
        pages = _source_pages(question)
        if pages:
            lines.extend(["", f"_صفحات منبع: {', '.join(map(str, pages))}_"])
        codes = issues_by_number.get(number, [])
        if codes:
            lines.extend(["", f"_نیازمند بازبینی: {', '.join(codes)}_"])
        lines.extend(["", "---", ""])
    return "\n".join(lines).strip() + "\n"


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
