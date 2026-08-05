"""Free deterministic integrity pass for assembled exam questions."""
from __future__ import annotations

from difflib import SequenceMatcher
import json
import re
from typing import Any

from . import exam_prep_page_output
from .exam_prep_page_records import PageAssemblyResult
from .exam_prep_question_full_verifier import _rebuild_result
from .exam_prep_utils import clean_exam_markdown


_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_OPTION_ANSWER_RE = re.compile(
    r"(?:پاسخ\s*(?:صحیح|درست)?\s*[:：\-–—]*\s*)?"
    r"گزین(?:ه(?:\u0654)?|ۀ)\s*[«\"'()\[\]]*\s*"
    r"(?P<label>[0-9۰-۹٠-٩]+|[الفبجده])",
    flags=re.IGNORECASE,
)
_INTEGRITY_CRITICAL_CODES = {
    "serialized_option_payload",
    "missing_correct_option_label",
    "duplicate_solution_across_questions",
}
exam_prep_page_output.CRITICAL_ISSUE_CODES = frozenset(
    set(exam_prep_page_output.CRITICAL_ISSUE_CODES) | _INTEGRITY_CRITICAL_CODES
)

_OWN_CODES = {
    "serialized_option_payload",
    "missing_correct_option_label",
    "duplicate_solution_across_questions",
}


def _normalize_label(value: Any) -> str:
    text = clean_exam_markdown(value or "").translate(_DIGITS).strip()
    text = text.strip(" «»\"'()[]{}.:：،,-–—")
    return str(int(text)) if text.isdigit() else text


def _decoded_option_payload(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not (text.startswith("{") and text.endswith("}")):
        return None
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _normalize_options(question: dict[str, Any]) -> tuple[list[dict[str, str]], bool]:
    changed = False
    output: list[dict[str, str]] = []
    for index, raw in enumerate(question.get("options") or [], start=1):
        if not isinstance(raw, dict):
            text = clean_exam_markdown(raw)
            if text:
                output.append({"label": str(index), "text_markdown": text})
            changed = True
            continue
        label = _normalize_label(raw.get("label") or index) or str(index)
        text = clean_exam_markdown(raw.get("text_markdown") or "")
        payload = _decoded_option_payload(text)
        if payload is not None:
            nested_text = clean_exam_markdown(
                payload.get("text_markdown")
                or payload.get("text")
                or payload.get("value")
                or ""
            )
            nested_label = _normalize_label(
                payload.get("label") or payload.get("option_label") or label
            )
            if nested_text:
                text = nested_text
                label = nested_label or label
                changed = True
        output.append({"label": label, "text_markdown": text})
    return output, changed


def _infer_correct_label(question: dict[str, Any], labels: set[str]) -> str | None:
    for field_name in (
        "teacher_solution_markdown",
        "final_answer_markdown",
        "correct_option_text_markdown",
    ):
        text = clean_exam_markdown(question.get(field_name) or "")
        match = _OPTION_ANSWER_RE.search(text[:500])
        if match:
            label = _normalize_label(match.group("label"))
            if not labels or label in labels:
                return label
    return None


def _normalized_similarity_text(value: Any) -> str:
    text = clean_exam_markdown(value or "").casefold().translate(_DIGITS)
    return " ".join(text.split())


def _apply_duplicate_solution_issues(questions: list[dict[str, Any]]) -> None:
    for index, question in enumerate(questions):
        solution = _normalized_similarity_text(question.get("teacher_solution_markdown"))
        if len(solution) < 180:
            continue
        q_text = _normalized_similarity_text(question.get("question_text_markdown"))
        for previous in questions[:index]:
            previous_solution = _normalized_similarity_text(
                previous.get("teacher_solution_markdown")
            )
            if len(previous_solution) < 180:
                continue
            if SequenceMatcher(None, solution, previous_solution).ratio() < 0.93:
                continue
            previous_q = _normalized_similarity_text(previous.get("question_text_markdown"))
            if SequenceMatcher(None, q_text, previous_q).ratio() >= 0.70:
                continue
            issues = list(question.get("issues") or [])
            if "duplicate_solution_across_questions" not in issues:
                issues.append("duplicate_solution_across_questions")
            question["issues"] = issues
            break


def apply_projection_integrity(
    result: PageAssemblyResult,
) -> tuple[PageAssemblyResult, dict[str, int]]:
    """Normalize free defects and add source-sensitive integrity issues."""

    questions: list[dict[str, Any]] = []
    serialized_fixed = inferred_keys = 0
    for raw_question in (result.projection.get("exam_prep") or {}).get("questions") or []:
        if not isinstance(raw_question, dict):
            continue
        question = dict(raw_question)
        issues = [
            clean_exam_markdown(code).strip()
            for code in (question.get("issues") or [])
            if clean_exam_markdown(code).strip() and clean_exam_markdown(code).strip() not in _OWN_CODES
        ]
        options, changed = _normalize_options(question)
        question["options"] = options
        serialized_fixed += int(changed)
        if any(
            isinstance(item, dict)
            and _decoded_option_payload(item.get("text_markdown")) is not None
            for item in options
        ):
            issues.append("serialized_option_payload")

        labels = {
            _normalize_label(item.get("label"))
            for item in options
            if isinstance(item, dict) and _normalize_label(item.get("label"))
        }
        correct = _normalize_label(question.get("correct_option_label"))
        if not correct:
            inferred = _infer_correct_label(question, labels)
            if inferred:
                correct = inferred
                inferred_keys += 1
        question["correct_option_label"] = correct or None
        if len(options) >= 2 and not correct:
            issues.append("missing_correct_option_label")
        elif correct and labels and correct not in labels:
            if "correct_option_not_in_options" not in issues:
                issues.append("correct_option_not_in_options")
        question["issues"] = list(dict.fromkeys(issues))
        questions.append(question)

    _apply_duplicate_solution_issues(questions)
    rebuilt = _rebuild_result(result, questions=questions)
    gradable = sum(
        bool(clean_exam_markdown(question.get("correct_option_label") or ""))
        for question in questions
        if len(question.get("options") or []) >= 2
    )
    missing = sum("missing_correct_option_label" in (question.get("issues") or []) for question in questions)
    duplicates = sum("duplicate_solution_across_questions" in (question.get("issues") or []) for question in questions)
    return rebuilt, {
        "serializedOptionsFixed": serialized_fixed,
        "inferredCorrectOptionCount": inferred_keys,
        "gradableAnswerKeyCount": gradable,
        "missingCorrectOptionCount": missing,
        "duplicateSolutionCount": duplicates,
    }


def promote_integrity_audit(
    audit: dict[str, Any],
    *,
    integrity_stats: dict[str, int],
) -> dict[str, Any]:
    critical_codes = _INTEGRITY_CRITICAL_CODES
    output = dict(audit)
    issues = []
    for raw in audit.get("issues") or []:
        issue = dict(raw) if isinstance(raw, dict) else {}
        if issue.get("code") in critical_codes:
            issue["severity"] = "critical"
        issues.append(issue)
    output["issues"] = issues
    critical_count = sum(issue.get("severity") == "critical" for issue in issues)
    critical_questions = {
        (str(issue.get("scopeKey") or "default"), int(issue.get("questionNumber") or 0))
        for issue in issues
        if issue.get("severity") == "critical" and int(issue.get("questionNumber") or 0) > 0
    }
    question_count = int(output.get("questionCount") or 0)
    output["criticalIssueCount"] = critical_count
    output["questionsNeedingReview"] = len(critical_questions)
    output["usableQuestionCount"] = max(0, question_count - len(critical_questions))
    output["status"] = "passed" if question_count > 0 and critical_count == 0 else "needs_review"
    output.update(integrity_stats)
    return output


def augment_transcript_summary(transcript: str, integrity_stats: dict[str, int]) -> str:
    marker = "- کلید پاسخ متصل‌شده:"
    lines = transcript.splitlines()
    insert_at = next((index + 1 for index, line in enumerate(lines) if line.startswith(marker)), None)
    if insert_at is None:
        return transcript
    extra = [
        f"- کلیدهای قابل نمره‌دهی: **{int(integrity_stats.get('gradableAnswerKeyCount', 0))}**",
        f"- سؤال‌های فاقد کلید قابل نمره‌دهی: **{int(integrity_stats.get('missingCorrectOptionCount', 0))}**",
        f"- گزینه‌های JSON اصلاح‌شده: **{int(integrity_stats.get('serializedOptionsFixed', 0))}**",
        f"- راه‌حل‌های تکراری مشکوک: **{int(integrity_stats.get('duplicateSolutionCount', 0))}**",
    ]
    lines[insert_at:insert_at] = extra
    return "\n".join(lines).rstrip() + "\n"
