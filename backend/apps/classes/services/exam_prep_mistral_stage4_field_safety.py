"""Deterministic field-level safety helpers for Stage-4 repair.

This module has no provider calls. It keeps Stage 4 conservative:
- source text is sanitized before it can enter the canonical projection;
- comparisons happen per canonical field instead of one flattened blob;
- numeric/math comparison tolerates harmless RTL/order variation without losing
  variable-to-value bindings;
- model uncertainty is attached to the exact field it affects.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re
from typing import Any, Mapping

from .exam_prep_mistral_direct_transcription import (
    normalize_text_for_similarity,
    numeric_signature,
    text_similarity,
)
from .exam_prep_utils import clean_exam_markdown


_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*\]\((?:https?://|data:)[^)]+\)", re.IGNORECASE)
_URL_RE = re.compile(r"https?://[^\s)\]}]+", re.IGNORECASE)
_AUTHOR_PREFIX_RE = re.compile(
    r"^\s*(?:مؤلف|مولف|نویسنده|حل\s*کننده|حل‌کننده|پاسخگو|طراح)\s*[:：\-–—]",
    re.IGNORECASE,
)
_PAGE_META_RE = re.compile(
    r"^\s*[\[(].{0,100}(?:صفحه(?:‌|\s)?های?|صفحات)\s*[:：]?\s*[0-9۰-۹٠-٩]",
    re.IGNORECASE,
)
_SOLUTION_HEADING_PREFIX_RE = re.compile(
    r"^\s*[#*_`«»\"'()]*\s*[0-9۰-۹٠-٩]{1,3}\s*[»\"'()]*\s*"
    r"(?:[-–—ـ]\s*)?گزین(?:ه|ۀ|هٔ)\s*[«»\"'()]*\s*"
    r"[0-9۰-۹٠-٩]{1,2}\s*[»\"'()]*\s*",
    re.IGNORECASE,
)
_MATH_TOKEN_RE = re.compile(r"\\?[A-Za-z][A-Za-z0-9_]*|[Α-Ωα-ω]+|[=+\-*/^<>≤≥]")
_KEYED_NUMERIC_RE = re.compile(
    r"(?P<key>\\?[A-Za-zΑ-Ωα-ω][A-Za-z0-9_Α-Ωα-ω]*)\s*=\s*"
    r"(?P<number>[+\-]?\d+(?:[./]\d+)?(?:[eE][+\-]?\d+)?)"
)
_IGNORED_MATH_TOKENS = frozenset(
    {
        "frac",
        "text",
        "mathrm",
        "operatorname",
        "left",
        "right",
        "begin",
        "end",
        "quad",
        "qquad",
        "cdot",
        "times",
        "displaystyle",
    }
)


@dataclass(frozen=True, slots=True)
class FieldAgreement:
    field: str
    numeric_equal: bool
    keyed_numeric_compared: bool
    keyed_numeric_equal: bool
    math_token_similarity: float
    text_similarity: float
    critical_conflict: bool

    def safe_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "numericEqual": self.numeric_equal,
            "keyedNumericCompared": self.keyed_numeric_compared,
            "keyedNumericEqual": self.keyed_numeric_equal,
            "mathTokenSimilarity": round(self.math_token_similarity, 6),
            "textSimilarity": round(self.text_similarity, 6),
            "criticalConflict": self.critical_conflict,
        }


def sanitize_source_markdown(value: Any) -> tuple[str, tuple[str, ...]]:
    """Strip deterministic non-source payloads before canonical persistence."""

    text = str(value or "")
    flags: list[str] = []
    text, heading_count = _SOLUTION_HEADING_PREFIX_RE.subn("", text, count=1)
    if heading_count:
        flags.append("removed_solution_heading")
    if _MARKDOWN_IMAGE_RE.search(text):
        text = _MARKDOWN_IMAGE_RE.sub("", text)
        flags.append("removed_markdown_image")
    if _URL_RE.search(text):
        text = _URL_RE.sub("", text)
        flags.append("removed_url")

    kept: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            kept.append("")
            continue
        if _AUTHOR_PREFIX_RE.search(stripped):
            flags.append("removed_author_metadata")
            continue
        if _PAGE_META_RE.search(stripped) and len(stripped) <= 160:
            flags.append("removed_page_metadata")
            continue
        kept.append(line)
    return clean_exam_markdown("\n".join(kept)), tuple(dict.fromkeys(flags))


def uncertain_fields(item: Any) -> frozenset[str]:
    fields: set[str] = set()
    for span in getattr(item, "uncertain_spans", ()) or ():
        field = str(getattr(span, "field", "") or "").strip()
        if field:
            fields.add(field)
    if bool(getattr(item, "transcription_uncertain", False)) and not fields:
        fields.add("*")
    return frozenset(fields)


def _numeric_counter(value: Any) -> Counter[str]:
    return Counter(numeric_signature(str(value or "")))


def _keyed_numeric_counter(value: Any) -> Counter[tuple[str, str]]:
    text = clean_exam_markdown(value or "").translate(_DIGITS)
    output: Counter[tuple[str, str]] = Counter()
    for match in _KEYED_NUMERIC_RE.finditer(text):
        key = match.group("key").lstrip("\\").lower()
        number = match.group("number")
        output[(key, number)] += 1
    return output


def _math_counter(value: Any) -> Counter[str]:
    text = normalize_text_for_similarity(str(value or ""))
    output: Counter[str] = Counter()
    for raw in _MATH_TOKEN_RE.findall(text):
        token = raw.lstrip("\\").lower()
        if token in _IGNORED_MATH_TOKENS:
            continue
        output[token] += 1
    return output


def _counter_similarity(left: Counter, right: Counter) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    keys = set(left) | set(right)
    common = sum(min(left[key], right[key]) for key in keys)
    total = sum(max(left[key], right[key]) for key in keys)
    return common / total if total else 1.0


def compare_field(field: str, left: Any, right: Any) -> FieldAgreement:
    """Compare one semantic field without depending on harmless RTL ordering.

    ``correct_option_label`` is structural answer evidence, not a hard-math text
    field. Label problems are already handled by the Stage-4 structural signals
    (missing/invalid answer and heading conflict), so a label-only mismatch must
    never buy a GPT second opinion for an otherwise healthy solution body.
    """

    a = clean_exam_markdown(left or "").translate(_DIGITS)
    b = clean_exam_markdown(right or "").translate(_DIGITS)
    numeric_left = _numeric_counter(a)
    numeric_right = _numeric_counter(b)
    numeric_equal = numeric_left == numeric_right
    keyed_left = _keyed_numeric_counter(a)
    keyed_right = _keyed_numeric_counter(b)
    keyed_compared = bool(keyed_left and keyed_right)
    keyed_equal = keyed_left == keyed_right if keyed_compared else True
    math_left = _math_counter(a)
    math_right = _math_counter(b)
    math_similarity = _counter_similarity(math_left, math_right)
    similarity = float(text_similarity(a, b))

    if field == "correct_option_label":
        conflict = False
    elif bool(a) != bool(b):
        conflict = True
    elif numeric_left or numeric_right:
        conflict = (not numeric_equal) or (keyed_compared and not keyed_equal)
    elif math_left or math_right:
        conflict = math_similarity < 0.72
    else:
        # Pure prose wording differences are not a paid hard-math trigger.
        conflict = False
    return FieldAgreement(
        field=field,
        numeric_equal=numeric_equal,
        keyed_numeric_compared=keyed_compared,
        keyed_numeric_equal=keyed_equal,
        math_token_similarity=math_similarity,
        text_similarity=similarity,
        critical_conflict=conflict,
    )


def candidate_fields(question: Mapping[str, Any], *, kind: str) -> dict[str, str]:
    if kind == "question":
        output = {
            "question_text_markdown": clean_exam_markdown(
                question.get("question_text_markdown") or ""
            )
        }
        for raw in question.get("options") or []:
            if not isinstance(raw, Mapping):
                continue
            label = str(raw.get("label") or "").translate(_DIGITS).strip()
            if label in {"1", "2", "3", "4"}:
                output[f"option_{label}"] = clean_exam_markdown(raw.get("text_markdown") or "")
        return output
    return {
        "correct_option_label": str(question.get("correct_option_label") or "")
        .translate(_DIGITS)
        .strip(),
        "teacher_solution_markdown": clean_exam_markdown(
            question.get("teacher_solution_markdown") or ""
        ),
    }


def payload_fields(payload: Mapping[str, Any], *, kind: str) -> dict[str, str]:
    if kind == "question":
        output = {
            "question_text_markdown": clean_exam_markdown(
                payload.get("question_text_markdown") or ""
            )
        }
        for raw in payload.get("options") or []:
            if not isinstance(raw, Mapping):
                continue
            label = str(raw.get("label") or "").translate(_DIGITS).strip()
            if label in {"1", "2", "3", "4"}:
                output[f"option_{label}"] = clean_exam_markdown(raw.get("text_markdown") or "")
        return output
    return {
        "correct_option_label": str(payload.get("correct_option_label") or "")
        .translate(_DIGITS)
        .strip(),
        "teacher_solution_markdown": clean_exam_markdown(
            payload.get("teacher_solution_markdown") or ""
        ),
    }


def compare_field_maps(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> dict[str, FieldAgreement]:
    fields = sorted(set(left) | set(right))
    return {
        field: compare_field(field, left.get(field, ""), right.get(field, ""))
        for field in fields
    }


def critical_conflict(comparison: Mapping[str, FieldAgreement]) -> bool:
    return any(item.critical_conflict for item in comparison.values())


def comparisons_safe_dict(
    comparison: Mapping[str, FieldAgreement],
) -> dict[str, dict[str, Any]]:
    return {field: item.safe_dict() for field, item in comparison.items()}


__all__ = [
    "FieldAgreement",
    "candidate_fields",
    "compare_field",
    "compare_field_maps",
    "comparisons_safe_dict",
    "critical_conflict",
    "payload_fields",
    "sanitize_source_markdown",
    "uncertain_fields",
]
