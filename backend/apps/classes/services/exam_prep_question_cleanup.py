"""Deterministic cleanup for canonical assembled exam questions.

Only layout artifacts are changed here. Scientific wording is never rewritten
from general knowledge; OCR/spelling corrections remain source-verifier work.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

from .exam_prep_utils import clean_exam_markdown


_DIGIT_TRANSLATION = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)
_LATIN_TO_PERSIAN = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
_ARABIC_TO_PERSIAN = str.maketrans({
    "ك": "ک",
    "ي": "ی",
    "ى": "ی",
    "ۀ": "هٔ",
})
_OPTION_LINE_RE = re.compile(
    r"^\s*[\(\[]?\s*(?P<label>[1-6۱-۶١-٦الفبجدهو])\s*"
    r"[\)\].:：،\-–—]\s*(?P<text>.+?)\s*$",
    flags=re.IGNORECASE,
)
_STATEMENT_LINE_RE = re.compile(
    r"(?m)^\s*(?P<label>[الفبجدهو])\s*[\)\].:：،\-–—]\s*",
)
_COUNT_QUESTION_RE = re.compile(
    r"(?:چند\s+(?:مورد|عبارت|گزینه)|تعداد\s+(?:موارد|عبارت|گزینه))",
    flags=re.IGNORECASE,
)
_ANSWER_LEAK_RE = re.compile(
    r"(?:موارد?|عبارت(?:‌|\s)?های?)\s*[«\"']?\s*"
    r"(?P<letters>[الفبجدهو](?:[\s،,و]+[الفبجدهو]){0,5})"
    r"\s*[»\"']?\s*(?:درست|صحیح)\s*(?:هستند|است|می[‌\s]?باشند)",
    flags=re.IGNORECASE,
)


def normalize_persian_layout_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", clean_exam_markdown(value))
    text = text.translate(_ARABIC_TO_PERSIAN)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _latin(value: Any) -> str:
    return str(value or "").translate(_DIGIT_TRANSLATION)


def _normalized(value: Any) -> str:
    text = normalize_persian_layout_text(value).casefold()
    text = re.sub(r"[\s\u200c]+", "", text)
    text = re.sub(r"[^\w\u0600-\u06ff]", "", text)
    return text


def _normalized_label(value: Any) -> str:
    text = normalize_persian_layout_text(value).strip(" «»\"'()[]{}.:،,-–—")
    latin = _latin(text)
    return str(int(latin)) if latin.isdigit() else text


def strip_repeated_question_number(text: str, number: int) -> tuple[str, bool]:
    if number < 1:
        return text, False
    variants = {str(number), str(number).translate(_LATIN_TO_PERSIAN)}
    number_pattern = "|".join(re.escape(item) for item in variants)
    pattern = re.compile(
        rf"^\s*(?:(?:س[ؤو]ال)\s*)?(?:{number_pattern})\s*[-–—ـ.:：)\]]\s*",
        flags=re.IGNORECASE,
    )
    cleaned, count = pattern.subn("", text, count=1)
    return cleaned.lstrip(), bool(count)


def strip_duplicated_option_lines(
    text: str,
    options: list[dict[str, Any]],
) -> tuple[str, bool]:
    """Remove lines already represented in canonical options.

    At least two exact label/text matches are required, preventing accidental
    removal of a single numbered statement from the actual stem.
    """

    expected = {
        _normalized_label(option.get("label")): _normalized(option.get("text_markdown"))
        for option in options
        if isinstance(option, dict)
        and _normalized_label(option.get("label"))
        and _normalized(option.get("text_markdown"))
    }
    if len(expected) < 2:
        return text, False

    lines = text.splitlines()
    matched_indices: list[int] = []
    matched_labels: set[str] = set()
    for index, line in enumerate(lines):
        match = _OPTION_LINE_RE.match(line)
        if match is None:
            continue
        label = _normalized_label(match.group("label"))
        candidate = _normalized(match.group("text"))
        if label in expected and candidate == expected[label]:
            matched_indices.append(index)
            matched_labels.add(label)
    if len(matched_labels) < 2:
        return text, False

    cleaned = "\n".join(
        line for index, line in enumerate(lines) if index not in matched_indices
    )
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned, True


def _letters_from_answer_phrase(value: str) -> tuple[str, ...]:
    match = _ANSWER_LEAK_RE.search(value)
    if match is None:
        return ()
    letters = re.findall(r"[الفبجدهو]", match.group("letters"))
    return tuple(dict.fromkeys(letters))


def remove_answer_leak(text: str) -> tuple[str, tuple[str, ...], bool]:
    match = _ANSWER_LEAK_RE.search(text)
    if match is None:
        return text, (), False
    letters = tuple(dict.fromkeys(re.findall(r"[الفبجدهو]", match.group("letters"))))
    cleaned = (text[: match.start()] + text[match.end() :]).strip(" \t\r\n.؛،-")
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned, letters, True


def _statement_labels(text: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(match.group("label") for match in _STATEMENT_LINE_RE.finditer(text)))


def _numeric_options(count: int) -> list[dict[str, str]]:
    return [
        {"label": str(index), "text_markdown": str(index)}
        for index in range(1, count + 1)
    ]


def normalize_count_question(question: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    text = normalize_persian_layout_text(question.get("question_text_markdown") or "")
    if _COUNT_QUESTION_RE.search(text) is None:
        return question, False

    solution = normalize_persian_layout_text(question.get("teacher_solution_markdown") or "")
    final_answer = normalize_persian_layout_text(question.get("final_answer_markdown") or "")
    text, leaked_letters, leak_removed = remove_answer_leak(text)
    inferred_letters = (
        leaked_letters
        or _letters_from_answer_phrase(solution)
        or _letters_from_answer_phrase(final_answer)
    )
    inferred_count = len(inferred_letters) if inferred_letters else None
    statements = _statement_labels(text)
    options = [item for item in (question.get("options") or []) if isinstance(item, dict)]
    labels = [_normalized_label(item.get("label")) for item in options]
    numeric_labels = all(label.isdigit() for label in labels) if labels else False
    changed = leak_removed

    # Only synthesize the standard 1..N choices when the source clearly contains
    # N lettered statements and the existing choices are missing/non-numeric.
    if (
        len(statements) in {3, 4}
        and inferred_count is not None
        and inferred_count > 0
        and (len(options) < 2 or not numeric_labels)
    ):
        options = _numeric_options(len(statements))
        labels = [item["label"] for item in options]
        changed = True

    correct = _normalized_label(question.get("correct_option_label"))
    if inferred_count is not None and inferred_count > 0:
        inferred_label = str(inferred_count)
        if inferred_label in labels and correct != inferred_label:
            correct = inferred_label
            changed = True

    updated = {
        **question,
        "question_text_markdown": text,
        "options": options,
        "correct_option_label": correct or None,
    }
    metadata = dict(updated.get("cleanup_metadata") or {})
    metadata.update(
        {
            "count_question": True,
            "statement_labels": list(statements),
            "inferred_true_statements": list(inferred_letters),
            "answer_leak_removed": leak_removed,
        }
    )
    updated["cleanup_metadata"] = metadata
    return updated, changed


def cleanup_assembled_question(question: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    updated = dict(question)
    changed = False
    try:
        number = int(updated.get("source_question_number") or 0)
    except (TypeError, ValueError):
        number = 0

    text = normalize_persian_layout_text(updated.get("question_text_markdown") or "")
    text, stripped_number = strip_repeated_question_number(text, number)
    options = [
        {
            **item,
            "label": _normalized_label(item.get("label")),
            "text_markdown": normalize_persian_layout_text(item.get("text_markdown") or ""),
        }
        for item in (updated.get("options") or [])
        if isinstance(item, dict)
    ]
    text, stripped_options = strip_duplicated_option_lines(text, options)
    if stripped_number or stripped_options:
        changed = True

    updated.update(
        {
            "question_text_markdown": text,
            "options": options,
            "teacher_solution_markdown": normalize_persian_layout_text(
                updated.get("teacher_solution_markdown") or ""
            ),
            "final_answer_markdown": normalize_persian_layout_text(
                updated.get("final_answer_markdown") or ""
            ),
            "correct_option_label": _normalized_label(
                updated.get("correct_option_label")
            )
            or None,
        }
    )
    metadata = dict(updated.get("cleanup_metadata") or {})
    metadata.update(
        {
            "question_number_prefix_removed": stripped_number,
            "duplicated_option_block_removed": stripped_options,
        }
    )
    updated["cleanup_metadata"] = metadata
    updated, count_changed = normalize_count_question(updated)
    return updated, changed or count_changed or updated != question
