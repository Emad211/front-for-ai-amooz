"""Deterministic validation for teacher-edited page-first projections."""
from __future__ import annotations

from collections import Counter, defaultdict
import json
import re
from typing import Any

from .exam_prep_page_output import is_critical_page_issue
from .exam_prep_utils import clean_exam_markdown


_DIGIT_TRANSLATION = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)
_MARKER_ONLY_RE = re.compile(
    r"^\s*(?:گزین[ههۀ]\s*)?[«»\"'()\[\]{}]*\s*"
    r"(?:[0-9۰-۹٠-٩]+|[الفبجدهو])"
    r"\s*[«»\"'()\[\]{}.:：،,\-–—]*\s*$",
    flags=re.IGNORECASE,
)
_COUNT_QUESTION_RE = re.compile(
    r"(?:چند\s+(?:مورد|عبارت|گزینه)|تعداد\s+(?:موارد|عبارت|گزینه))",
    flags=re.IGNORECASE,
)
_VISUAL_REFERENCE_RE = re.compile(
    r"(?:شکل\s*(?:رو\s*به\s*رو|مقابل|زیر|بالا)?|"
    r"نمودار|طیف\s+طول\s+موج|تصویر\s*(?:مقابل|زیر)?|"
    r"با\s+توجه\s+به\s+شکل)",
    flags=re.IGNORECASE,
)
CRITICAL_CODES = frozenset(
    {
        "no_questions",
        "missing_question_id",
        "duplicate_question_id",
        "duplicate_question_number",
        "missing_question_number",
        "missing_question_text",
        "missing_options",
        "missing_option_text",
        "missing_options_text",
        "placeholder_option_text",
        "unexpected_option_count",
        "duplicate_option_label",
        "missing_answer",
        "correct_option_not_in_options",
        "visual_evidence_required",
        "failed_chunk",
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


def _option_text_is_marker_only(value: Any) -> bool:
    return _MARKER_ONLY_RE.fullmatch(clean_exam_markdown(value)) is not None


def audit_page_first_projection(projection: object) -> dict[str, Any]:
    """Re-audit normalized teacher JSON with the same fail-closed semantics."""

    questions = _questions(projection)
    issues: list[dict[str, Any]] = []
    seen_issues: set[tuple[str, str, int, tuple[int, ...]]] = set()
    ids: Counter[str] = Counter()
    numbers_by_scope: dict[str, list[int]] = defaultdict(list)
    matched_answers = 0

    def add_issue(
        code: str,
        *,
        scope: str,
        number: int,
        pages: list[int] | None = None,
    ) -> None:
        page_tuple = tuple(pages or [])
        key = (code, scope, number, page_tuple)
        if key in seen_issues:
            return
        seen_issues.add(key)
        issues.append(
            {
                "code": code,
                "severity": (
                    "critical"
                    if code in CRITICAL_CODES or is_critical_page_issue(code)
                    else "warning"
                ),
                "scopeKey": scope,
                "questionNumber": number,
                "sourcePages": list(page_tuple),
            }
        )

    if not questions:
        add_issue("no_questions", scope="default", number=0)

    for index, question in enumerate(questions, start=1):
        scope = (
            clean_exam_markdown(question.get("scope_key") or "default").strip()
            or "default"
        )
        number = _question_number(question) or index
        pages = []
        for value in question.get("source_pages") or []:
            try:
                page = int(value)
            except (TypeError, ValueError):
                continue
            if page > 0 and page not in pages:
                pages.append(page)

        question_id = clean_exam_markdown(question.get("question_id") or "").strip()
        if question_id:
            ids[question_id] += 1
        else:
            add_issue(
                "missing_question_id",
                scope=scope,
                number=number,
                pages=pages,
            )

        parsed_number = _question_number(question)
        if parsed_number is not None:
            numbers_by_scope[scope].append(parsed_number)

        question_text = clean_exam_markdown(
            question.get("question_text_markdown") or ""
        ).strip()
        if not question_text:
            add_issue(
                "missing_question_text",
                scope=scope,
                number=number,
                pages=pages,
            )

        options = question.get("options")
        valid_options = (
            [item for item in options if isinstance(item, dict)]
            if isinstance(options, list)
            else []
        )
        if len(valid_options) < 2:
            add_issue("missing_options", scope=scope, number=number, pages=pages)
        elif len(valid_options) > 6:
            add_issue(
                "unexpected_option_count",
                scope=scope,
                number=number,
                pages=pages,
            )

        labels: list[str] = []
        option_texts: list[str] = []
        for option in valid_options:
            label = clean_exam_markdown(option.get("label") or "").strip()
            text = clean_exam_markdown(
                option.get("text_markdown") or ""
            ).strip()
            if label:
                labels.append(label)
            option_texts.append(text)
            if not text:
                add_issue(
                    "missing_option_text",
                    scope=scope,
                    number=number,
                    pages=pages,
                )
        if len(labels) != len(set(labels)):
            add_issue(
                "duplicate_option_label",
                scope=scope,
                number=number,
                pages=pages,
            )
        if (
            option_texts
            and all(_option_text_is_marker_only(value) for value in option_texts)
            and _COUNT_QUESTION_RE.search(question_text) is None
        ):
            add_issue(
                "placeholder_option_text",
                scope=scope,
                number=number,
                pages=pages,
            )
        if _VISUAL_REFERENCE_RE.search(question_text):
            add_issue(
                "visual_evidence_required",
                scope=scope,
                number=number,
                pages=pages,
            )

        for raw_issue in question.get("issues") or []:
            code = clean_exam_markdown(raw_issue).strip()
            if code:
                add_issue(code, scope=scope, number=number, pages=pages)

        correct = clean_exam_markdown(
            question.get("correct_option_label") or ""
        ).strip()
        answer_present = bool(
            correct
            or clean_exam_markdown(
                question.get("correct_option_text_markdown") or ""
            ).strip()
            or clean_exam_markdown(
                question.get("final_answer_markdown") or ""
            ).strip()
            or clean_exam_markdown(
                question.get("teacher_solution_markdown") or ""
            ).strip()
        )
        if not answer_present:
            add_issue("missing_answer", scope=scope, number=number, pages=pages)
        else:
            matched_answers += 1
        if correct and labels and correct not in labels:
            add_issue(
                "correct_option_not_in_options",
                scope=scope,
                number=number,
                pages=pages,
            )

    for question_id, count in ids.items():
        if count <= 1:
            continue
        for question in questions:
            if (
                clean_exam_markdown(question.get("question_id") or "").strip()
                == question_id
            ):
                add_issue(
                    "duplicate_question_id",
                    scope=(
                        clean_exam_markdown(
                            question.get("scope_key") or "default"
                        ).strip()
                        or "default"
                    ),
                    number=_question_number(question) or 0,
                    pages=list(question.get("source_pages") or []),
                )
                break

    gaps: dict[str, list[int]] = {}
    for scope, values in numbers_by_scope.items():
        counts = Counter(values)
        for number, count in counts.items():
            if count > 1:
                add_issue(
                    "duplicate_question_number",
                    scope=scope,
                    number=number,
                )
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
                    add_issue(
                        "missing_question_number",
                        scope=scope,
                        number=number,
                    )

    critical_count = sum(
        issue["severity"] == "critical"
        for issue in issues
    )
    critical_question_keys = {
        (
            str(issue.get("scopeKey") or "default"),
            int(issue.get("questionNumber") or 0),
        )
        for issue in issues
        if issue["severity"] == "critical"
        and int(issue.get("questionNumber") or 0) > 0
    }
    return {
        "status": (
            "passed"
            if questions and critical_count == 0
            else "needs_review"
        ),
        "questionCount": len(questions),
        "usableQuestionCount": max(
            0,
            len(questions) - len(critical_question_keys),
        ),
        "questionsNeedingReview": len(critical_question_keys),
        "matchedAnswerCount": matched_answers,
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
    """Keep source failures critical until a fresh pipeline run succeeds."""

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
    issues = [
        dict(item)
        for item in (audit.get("issues") or [])
        if isinstance(item, dict)
    ]
    existing_pages = {
        tuple(item.get("sourcePages") or [])
        for item in issues
        if item.get("code") == "failed_chunk"
    }
    for page_number in pages:
        if (page_number,) in existing_pages:
            continue
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
    updated["criticalIssueCount"] = sum(
        item.get("severity") == "critical"
        for item in issues
    )
    updated["status"] = "needs_review"
    return updated


def render_projection_transcript(
    projection: object,
    audit: dict[str, Any],
) -> str:
    """Render edited canonical JSON into readable, truthful Markdown."""

    questions = _questions(projection)
    exam = projection.get("exam_prep") if isinstance(projection, dict) else {}
    title = (
        clean_exam_markdown(
            exam.get("title") if isinstance(exam, dict) else ""
        )
        or "آمادگی آزمون"
    )
    lines = [
        f"# {title}",
        "",
        "## خلاصهٔ استخراج",
        "",
        f"- سؤال‌های استخراج‌شده: **{len(questions)}**",
        f"- سؤال‌های آمادهٔ استفاده: **{int(audit.get('usableQuestionCount') or 0)}**",
        f"- سؤال‌های نیازمند بازبینی: **{int(audit.get('questionsNeedingReview') or 0)}**",
        f"- پاسخ‌های ثبت‌شده: **{int(audit.get('matchedAnswerCount') or 0)}**",
        f"- خطاهای بحرانی: **{int(audit.get('criticalIssueCount') or 0)}**",
    ]
    failed_pages = audit.get("failedPageNumbers") or []
    if failed_pages:
        lines.append(
            f"- صفحه‌های نیازمند بازپردازش: **{'، '.join(map(str, failed_pages))}**"
        )
    if audit.get("status") != "passed":
        lines.extend(
            [
                "",
                "> این خروجی تا رفع خطاهای بحرانی قابل انتشار نیست.",
            ]
        )
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
                clean_exam_markdown(
                    question.get("question_text_markdown")
                    or "_صورت سؤال ثبت نشده است._"
                ),
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
        correct = clean_exam_markdown(
            question.get("correct_option_label") or ""
        )
        if correct:
            lines.extend(["", f"**پاسخ صحیح:** گزینه {correct}"])
        solution = clean_exam_markdown(
            question.get("teacher_solution_markdown") or ""
        )
        if solution:
            lines.extend(["", "**راه‌حل تشریحی:**", "", solution])
        pages = question.get("source_pages") or []
        if pages:
            lines.extend(
                ["", f"_صفحات منبع: {', '.join(map(str, pages))}_"]
            )
        issue_codes = issues_by_number.get(number, [])
        if "visual_evidence_required" in issue_codes:
            lines.extend(
                [
                    "",
                    "_این سؤال به شکل، نمودار یا تصویر صفحهٔ منبع وابسته است و تا اتصال تصویر قابل انتشار نیست._",
                ]
            )
        if issue_codes:
            lines.extend(
                [
                    "",
                    f"_نیازمند بازبینی: {', '.join(issue_codes)}_",
                ]
            )
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
