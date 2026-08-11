"""Strict audit and readable output for the simple page-first pipeline."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from .exam_prep_page_records import DEFAULT_SCOPE_KEY, PageAssemblyResult
from .exam_prep_utils import clean_exam_markdown


CRITICAL_ISSUE_CODES = frozenset(
    {
        "no_questions",
        "missing_question_id",
        "duplicate_question_id",
        "duplicate_question_number",
        "missing_question_text",
        "missing_options",
        "missing_option_text",
        "missing_options_text",
        "missing_solution_text",
        "placeholder_option_text",
        "unexpected_option_count",
        "duplicate_option_label",
        "missing_answer",
        "missing_previous_continuation",
        "missing_next_continuation",
        "conflicting_correct_option",
        "conflicting_correct_option_text",
        "correct_option_not_in_options",
        "missing_question_number",
        "visual_evidence_required",
        "broken_persian_text",
        "duplicate_mixed_text",
        "solution_semantic_mismatch_candidate",
        "targeted_repair_unresolved",
        "targeted_repair_failed",
        "targeted_repair_no_source_page",
        "source_verification_failed",
        "table_incomplete",
        "count_answer_unresolved",
        "visual_attachment_missing",
        "stage4_verification_unresolved",
        "stage5_finalization_blocked",
        "failed_chunk",
    }
)


def is_critical_page_issue(code: object) -> bool:
    normalized = clean_exam_markdown(code).strip()
    return bool(
        normalized in CRITICAL_ISSUE_CODES
        or normalized.startswith("conflicting_option:")
    )


def _question_counts(result: PageAssemblyResult) -> tuple[int, int]:
    answer_keys = 0
    worked_solutions = 0
    for question in (result.projection.get("exam_prep") or {}).get("questions") or []:
        if not isinstance(question, dict):
            continue
        if any(
            clean_exam_markdown(question.get(field) or "")
            for field in (
                "correct_option_label",
                "correct_option_text_markdown",
                "final_answer_markdown",
            )
        ):
            answer_keys += 1
        if len(clean_exam_markdown(question.get("teacher_solution_markdown") or "")) >= 24:
            worked_solutions += 1
    return answer_keys, worked_solutions


def build_strict_page_first_audit(
    result: PageAssemblyResult,
    *,
    failed_page_numbers: list[int] | None = None,
) -> dict[str, Any]:
    failed_pages = sorted(
        {
            int(number)
            for number in (failed_page_numbers or [])
            if int(number) > 0
        }
    )
    issues = [
        {
            "code": issue.code,
            "severity": "critical" if is_critical_page_issue(issue.code) else "warning",
            "scopeKey": issue.scope_key,
            "questionNumber": issue.question_number,
            "sourcePages": issue.source_pages,
        }
        for issue in result.issues
    ]
    for page_number in failed_pages:
        issues.append(
            {
                "code": "failed_chunk",
                "severity": "critical",
                "scopeKey": DEFAULT_SCOPE_KEY,
                "questionNumber": 0,
                "sourcePages": [page_number],
            }
        )
    for orphan in result.orphan_answers:
        issues.append(
            {
                "code": "out_of_scope_answer",
                "severity": "warning",
                "scopeKey": orphan.scope_key,
                "questionNumber": orphan.question_number,
                "sourcePages": orphan.source_pages,
            }
        )

    critical_question_keys = {
        (str(issue.get("scopeKey") or DEFAULT_SCOPE_KEY), int(issue.get("questionNumber") or 0))
        for issue in issues
        if issue.get("severity") == "critical" and int(issue.get("questionNumber") or 0) > 0
    }
    critical_count = sum(issue.get("severity") == "critical" for issue in issues)
    questions_needing_review = len(critical_question_keys)
    usable_questions = max(0, result.question_count - questions_needing_review)
    answer_key_count, solution_count = _question_counts(result)
    return {
        "status": "passed" if result.question_count > 0 and critical_count == 0 else "needs_review",
        "questionCount": result.question_count,
        "usableQuestionCount": usable_questions,
        "questionsNeedingReview": questions_needing_review,
        "matchedAnswerCount": answer_key_count,
        "matchedSolutionCount": solution_count,
        "answerKeyOnlyCount": max(0, answer_key_count - solution_count),
        "outOfScopeAnswerCount": len(result.orphan_answers),
        "criticalIssueCount": critical_count,
        "issues": issues,
        "failedPageNumbers": failed_pages,
        "questionNumberGaps": result.question_number_gaps,
    }


def _issues_by_question(audit: dict[str, Any]) -> dict[tuple[str, int], list[str]]:
    grouped: dict[tuple[str, int], list[str]] = defaultdict(list)
    for issue in audit.get("issues") or []:
        if not isinstance(issue, dict):
            continue
        number = int(issue.get("questionNumber") or 0)
        if number < 1:
            continue
        key = (str(issue.get("scopeKey") or DEFAULT_SCOPE_KEY), number)
        code = clean_exam_markdown(issue.get("code") or "").strip()
        if code and code not in grouped[key]:
            grouped[key].append(code)
    return grouped


def render_strict_page_first_transcript(
    result: PageAssemblyResult,
    *,
    failed_page_numbers: list[int] | None = None,
    targeted_repair_stats: dict[str, int] | None = None,
) -> str:
    audit = build_strict_page_first_audit(
        result,
        failed_page_numbers=failed_page_numbers,
    )
    verification = dict(targeted_repair_stats or {})
    exam = result.projection.get("exam_prep") or {}
    title = clean_exam_markdown(exam.get("title") or "آمادگی آزمون")
    lines = [
        f"# {title}",
        "",
        "## خلاصهٔ استخراج",
        "",
        f"- سؤال‌های استخراج‌شده: **{result.question_count}**",
        f"- سؤال‌های آمادهٔ استفاده: **{audit['usableQuestionCount']}**",
        f"- سؤال‌های نیازمند بازبینی: **{audit['questionsNeedingReview']}**",
        f"- کلید پاسخ متصل‌شده: **{audit['matchedAnswerCount']}**",
        f"- راه‌حل تشریحی متصل‌شده: **{audit['matchedSolutionCount']}**",
        f"- سؤال‌های دارای فقط کلید پاسخ: **{audit['answerKeyOnlyCount']}**",
        f"- پاسخ‌های بدون صورت سؤال که کنار گذاشته شدند: **{len(result.orphan_answers)}**",
        f"- خطاهای بحرانی: **{audit['criticalIssueCount']}**",
    ]
    if verification:
        lines.extend(
            [
                f"- سؤال‌های بررسی‌شده با منبع: **{int(verification.get('attempted', 0))}**",
                f"- سؤال‌های تأییدشده: **{int(verification.get('verified', 0))}**",
                f"- سؤال‌های اصلاح‌شده از روی منبع: **{int(verification.get('repaired', 0))}**",
                f"- تلاش‌های مجدد: **{int(verification.get('retried', 0))}**",
                f"- بررسی‌های حل‌نشده: **{int(verification.get('unresolved', 0))}**",
                f"- تصاویر منبع متصل‌شده: **{int(verification.get('visuals_attached', 0))}**",
                f"- جدول‌های کامل تأییدشده: **{int(verification.get('tables_verified', 0))}**",
            ]
        )
    if audit["failedPageNumbers"]:
        pages = "، ".join(str(number) for number in audit["failedPageNumbers"])
        lines.append(f"- صفحه‌های پردازش‌نشده: **{pages}**")
    if audit["status"] != "passed":
        lines.extend(["", "> این خروجی تا رفع خطاهای بحرانی قابل انتشار نیست."])
    lines.extend(["", "---", ""])

    grouped_issues = _issues_by_question(audit)
    for question in exam.get("questions") or []:
        number_text = clean_exam_markdown(question.get("source_question_number") or "؟")
        try:
            number = int(number_text)
        except (TypeError, ValueError):
            number = 0
        scope = str(question.get("scope_key") or DEFAULT_SCOPE_KEY)
        issue_codes = grouped_issues.get((scope, number), [])
        lines.extend(
            [
                f"## سؤال {number_text}",
                "",
                clean_exam_markdown(
                    question.get("question_text_markdown")
                    or "_صورت سؤال استخراج نشده است._"
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
            elif label and question.get("visuals"):
                lines.append(f"{label}) _گزینه در تصویر منبع نمایش داده شده است._")
        correct = clean_exam_markdown(question.get("correct_option_label") or "")
        if correct:
            lines.extend(["", f"**پاسخ صحیح:** گزینه {correct}"])
        solution = clean_exam_markdown(question.get("teacher_solution_markdown") or "")
        if solution:
            lines.extend(["", "**راه‌حل تشریحی:**", "", solution])
        source_pages = question.get("source_pages") or []
        if source_pages:
            lines.extend(["", f"_صفحات منبع: {', '.join(map(str, source_pages))}_"])
        if question.get("visuals"):
            lines.extend(["", "_تصویر اصلی مرتبط با سؤال از صفحهٔ منبع متصل شده است._"])
        elif "visual_evidence_required" in issue_codes or "visual_attachment_missing" in issue_codes:
            lines.extend(
                [
                    "",
                    "_این سؤال به شکل، نمودار یا تصویر وابسته است و تصویر منبع آن متصل نشده است._",
                ]
            )
        if issue_codes:
            lines.extend(["", f"_نیازمند بازبینی: {', '.join(issue_codes)}_"])
        lines.extend(["", "---", ""])

    if result.orphan_answers:
        lines.extend(
            [
                "## پاسخ‌های بدون صورت سؤال",
                "",
                "این رکوردها عمداً سؤال جدید نساختند:",
                "",
            ]
        )
        for orphan in result.orphan_answers:
            answer = (
                f"، گزینه {orphan.correct_option_label}"
                if orphan.correct_option_label
                else ""
            )
            pages = "، ".join(map(str, orphan.source_pages)) or "نامشخص"
            lines.append(
                f"- سؤال {orphan.question_number}{answer} — صفحات پاسخ: {pages}"
            )
        lines.append("")

    return "\n".join(lines).strip() + "\n"


# Generic names for pipelines that consume the canonical PageAssemblyResult
# contract without using the legacy page-first extraction architecture.
build_strict_exam_audit = build_strict_page_first_audit
render_strict_exam_transcript = render_strict_page_first_transcript
