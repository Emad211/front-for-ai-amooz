"""Pure normalization for stored and newly extracted exam-prep questions."""

from __future__ import annotations

import json
import re
from typing import Any

from .text_sanitize import sanitize_llm_markdown


_OPTION_LABELS = ("الف", "ب", "ج", "د", "ه", "و")
_PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_BROKEN_TAB_COMMAND_RE = re.compile(r"\t(?=(?:ext|imes|heta|an|au|o|op)\b)")
_BROKEN_CR_COMMAND_RE = re.compile(r"\r(?=(?:ight|ho|angle|rightarrow|rm|mathrm)\b)")
_BROKEN_N_COMMAND_RE = re.compile(
    r"\n(?=(?:eq|e|ot|abla|u|leq|geq|parallel|mid|subseteq|supseteq|rightarrow|leftarrow|exists|in)\b)"
)
_DOUBLE_LATEX_ESCAPE_RE = re.compile(
    r"\\\\(?=(?:[\[\](){}%]|(?:frac|sqrt|begin|end|text|cdot|times|sum|int|"
    r"alpha|beta|gamma|delta|theta|lambda|mu|pi|sigma|phi|omega|neq|leq|geq|"
    r"infty|implies|rightarrow|leftarrow|right|left|sin|cos|tan|log|lim|cup|cap)\b))"
)
_ESCAPED_NEWLINE_BEFORE_OPTION_RE = re.compile(
    r"\\n(?=\s*[\(\[]?\s*(?:الف|ب|ج|د|ه|و|[A-Fa-f]|[1-6۱-۶])\s*[\)\].:،-])"
)


def clean_exam_markdown(value: Any) -> str:
    """Repair JSON-mangled LaTeX while preserving real Markdown newlines."""
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\f", "\\f").replace("\b", "\\b")
    text = _BROKEN_TAB_COMMAND_RE.sub(r"\\t", text).replace("\t", " ")
    text = _BROKEN_CR_COMMAND_RE.sub(r"\\r", text).replace("\r", "\n")
    text = _BROKEN_N_COMMAND_RE.sub(r"\\n", text)
    text = _DOUBLE_LATEX_ESCAPE_RE.sub(r"\\", text)
    text = _ESCAPED_NEWLINE_BEFORE_OPTION_RE.sub("\n", text)
    return sanitize_llm_markdown(text)


def _normalize_option(raw: Any, index: int) -> dict[str, str] | None:
    fallback_label = _OPTION_LABELS[index] if index < len(_OPTION_LABELS) else str(index + 1)
    if isinstance(raw, dict):
        label = clean_exam_markdown(raw.get("label")) or fallback_label
        text = clean_exam_markdown(
            raw.get("text_markdown") or raw.get("text") or raw.get("value")
        )
    else:
        label = fallback_label
        text = clean_exam_markdown(raw)
    return {"label": label, "text_markdown": text} if text else None


def _flexible_text_pattern(value: str) -> str:
    return r"\s+".join(re.escape(part) for part in value.split())


def _marker_pattern(label: str, index: int) -> str:
    number = str(index + 1)
    persian_number = _PERSIAN_DIGITS[index + 1] if index + 1 < len(_PERSIAN_DIGITS) else number
    latin = chr(ord("A") + index) if index < 6 else ""
    variants = {label, number, persian_number, latin, latin.lower()}
    joined = "|".join(re.escape(item) for item in variants if item)
    return rf"[\(\[]?\s*(?:{joined})\s*[\)\].:،-]\s*"


def _strip_complete_option_suffix(question_text: str, options: list[dict[str, str]]) -> str:
    """Remove a duplicated trailing option block only when every option matches.

    Requiring ordered labels/numbers plus exact option text avoids deleting a
    legitimate mention such as ``گزینه الف`` from the question stem.
    """
    if len(options) < 2:
        return question_text

    first = options[0]
    first_pattern = re.compile(
        _marker_pattern(first["label"], 0) + _flexible_text_pattern(first["text_markdown"]),
        re.IGNORECASE,
    )
    for candidate in first_pattern.finditer(question_text):
        if candidate.start() < 5:
            continue
        cursor = candidate.end()
        matched = True
        for index, option in enumerate(options[1:], start=1):
            pattern = re.compile(
                _marker_pattern(option["label"], index)
                + _flexible_text_pattern(option["text_markdown"]),
                re.IGNORECASE,
            )
            found = pattern.search(question_text, cursor)
            if found is None:
                matched = False
                break
            cursor = found.end()
        if matched and re.fullmatch(r"[\s,،;؛|/-]*", question_text[cursor:]):
            return question_text[: candidate.start()].rstrip()
    return question_text


def normalize_exam_prep_question(raw: Any, *, index: int) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None

    question_text = clean_exam_markdown(raw.get("question_text_markdown"))
    if not question_text:
        return None

    options: list[dict[str, str]] = []
    raw_options = raw.get("options")
    if isinstance(raw_options, list):
        for option_index, option in enumerate(raw_options):
            normalized = _normalize_option(option, option_index)
            if normalized:
                options.append(normalized)
    question_text = _strip_complete_option_suffix(question_text, options)

    correct_label = clean_exam_markdown(raw.get("correct_option_label")) or None
    if correct_label and correct_label not in {option["label"] for option in options}:
        correct_label = None

    confidence = None
    if raw.get("confidence") is not None:
        try:
            confidence = max(0.0, min(1.0, float(raw["confidence"])))
        except (TypeError, ValueError):
            pass

    issues = raw.get("issues")
    normalized_issues = (
        [cleaned for item in issues if (cleaned := clean_exam_markdown(item))]
        if isinstance(issues, list)
        else []
    )
    return {
        **raw,
        "question_id": clean_exam_markdown(raw.get("question_id")) or f"q-{index}",
        "question_text_markdown": question_text,
        "options": options,
        "correct_option_label": correct_label,
        "correct_option_text_markdown": clean_exam_markdown(
            raw.get("correct_option_text_markdown")
        )
        or None,
        "teacher_solution_markdown": clean_exam_markdown(raw.get("teacher_solution_markdown")),
        "final_answer_markdown": clean_exam_markdown(raw.get("final_answer_markdown")),
        "confidence": confidence,
        "issues": normalized_issues,
    }


def normalize_exam_prep_questions(exam_prep_obj: dict) -> tuple[dict, bool]:
    """Normalize every question and assign unique IDs, in place."""
    if not isinstance(exam_prep_obj, dict):
        return exam_prep_obj, False
    exam_prep = exam_prep_obj.get("exam_prep")
    if not isinstance(exam_prep, dict) or not isinstance(exam_prep.get("questions"), list):
        return exam_prep_obj, False

    original = exam_prep["questions"]
    questions = [
        normalized
        for index, raw in enumerate(original, start=1)
        if (normalized := normalize_exam_prep_question(raw, index=index)) is not None
    ]
    used_ids: set[str] = set()
    for index, question in enumerate(questions, start=1):
        question_id = question["question_id"]
        if question_id in used_ids:
            question_id = f"q-{index}"
            while question_id in used_ids:
                question_id += "-duplicate"
            question["question_id"] = question_id
        used_ids.add(question_id)

    changed = questions != original
    exam_prep["questions"] = questions
    return exam_prep_obj, changed


def normalize_exam_prep_json(raw_value: object) -> tuple[str | None, bool]:
    if raw_value is None:
        return None, False
    value: object = raw_value
    if isinstance(value, str):
        if not value.strip():
            return value, False
        try:
            value = json.loads(value)
        except Exception:
            return raw_value, False
    if not isinstance(value, dict):
        try:
            return json.dumps(value, ensure_ascii=False), False
        except Exception:
            return None, False
    normalized, changed = normalize_exam_prep_questions(value)
    return json.dumps(normalized, ensure_ascii=False), changed
