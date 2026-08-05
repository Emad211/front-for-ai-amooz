"""Targeted source verification for suspicious assembled exam questions.

This is intentionally not a whole-document pass. Each call receives one current
question and at most two of its own source pages. Clean questions incur no extra
provider cost.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field

from apps.chatbot.services.llm_client import part_from_bytes
from apps.commons.llm_prompts import PROMPTS
from apps.commons.models import LLMUsageLog
from apps.commons.structured_llm import StructuredOutputError, generate_structured

from .exam_prep_page_extractor import RenderedExamPage
from .exam_prep_page_output import is_critical_page_issue
from .exam_prep_page_records import AssemblyIssue, PageAssemblyResult, PageOption
from .exam_prep_text_quality import (
    has_broken_persian_text,
    has_duplicate_clean_and_broken_text,
    native_text_for_model,
)
from .exam_prep_utils import clean_exam_markdown


_REPAIRABLE_QUESTION_CODES = frozenset(
    {
        "missing_question_text",
        "missing_options",
        "missing_option_text",
        "missing_solution_text",
        "placeholder_option_text",
        "unexpected_option_count",
        "duplicate_option_label",
        "correct_option_not_in_options",
        "broken_persian_text",
        "duplicate_mixed_text",
        "solution_semantic_mismatch_candidate",
    }
)
_VISUAL_REFERENCE_RE = re.compile(
    r"(?:"
    r"(?:با\s+توجه\s+به|مطابق|براساس)\s+(?:شکل|نمودار|تصویر)\s*(?:مقابل|زیر|بالا|رو\s*به\s*رو)?"
    r"|شکل\s*(?:مقابل|زیر|بالا|رو\s*به\s*رو)"
    r"|نمودار\s+(?:مقابل|زیر|بالا|نشان\s+داده\s+شده)"
    r"|طیف\s+طول\s+موج\s+(?:مرئی\s+)?(?:مقابل|نمایش\s+داده\s+شده)"
    r")",
    flags=re.IGNORECASE,
)
_COUNT_QUESTION_RE = re.compile(
    r"(?:چند\s+(?:مورد|عبارت|گزینه)|تعداد\s+(?:موارد|عبارت|گزینه))",
    flags=re.IGNORECASE,
)
_WORD_RE = re.compile(r"[\u0600-\u06FFa-zA-Z0-9]{3,}")
_STOP_WORDS = frozenset(
    {
        "است",
        "هست",
        "شود",
        "شده",
        "برای",
        "این",
        "آن",
        "کدام",
        "گزینه",
        "مورد",
        "درست",
        "نادرست",
        "درباره",
        "مطابق",
        "کتاب",
        "درسی",
        "بررسی",
        "سایر",
        "میباشد",
        "میشود",
    }
)
_MARKER_ONLY_RE = re.compile(
    r"^\s*(?:گزین[ههۀ]\s*)?[«»\"'()\[\]]*\s*"
    r"[1-6۱-۶١-٦]\s*[«»\"'()\[\].:،-]*\s*$"
)


class VerifiedQuestionRepair(BaseModel):
    model_config = ConfigDict(extra="ignore")

    question_number: int = Field(ge=1)
    source_supported: bool = False
    question_text_markdown: str = ""
    options: list[PageOption] = Field(default_factory=list)
    correct_option_label: str | None = None
    teacher_solution_markdown: str = ""
    final_answer_markdown: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    issues: list[str] = Field(default_factory=list)


def _positive_int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _number(question: dict[str, Any]) -> int:
    try:
        return int(question.get("source_question_number") or 0)
    except (TypeError, ValueError):
        return 0


def _tokens(value: Any) -> set[str]:
    return {
        token.casefold()
        for token in _WORD_RE.findall(clean_exam_markdown(value))
        if token.casefold() not in _STOP_WORDS
    }


def solution_mismatch_candidate(question: dict[str, Any]) -> bool:
    solution = clean_exam_markdown(question.get("teacher_solution_markdown") or "")
    if len(solution) < 120 or has_broken_persian_text(solution):
        return False
    source = " ".join(
        [
            clean_exam_markdown(question.get("question_text_markdown") or ""),
            *(
                clean_exam_markdown(option.get("text_markdown") or "")
                for option in (question.get("options") or [])
                if isinstance(option, dict)
            ),
        ]
    )
    source_tokens = _tokens(source)
    solution_tokens = _tokens(solution)
    if len(source_tokens) < 5 or len(solution_tokens) < 5:
        return False
    overlap = len(source_tokens & solution_tokens)
    return (
        overlap < 2
        and overlap / max(1, min(len(source_tokens), len(solution_tokens))) < 0.05
    )


def canonical_question_issues(question: dict[str, Any]) -> list[str]:
    existing = [
        clean_exam_markdown(code).strip()
        for code in (question.get("issues") or [])
        if clean_exam_markdown(code).strip()
    ]
    text = clean_exam_markdown(question.get("question_text_markdown") or "")
    options = [
        item
        for item in (question.get("options") or [])
        if isinstance(item, dict)
    ]
    labels = [clean_exam_markdown(item.get("label") or "") for item in options]
    issues: list[str] = [
        code
        for code in existing
        if code not in _REPAIRABLE_QUESTION_CODES
    ]
    if not text:
        issues.append("missing_question_text")
    if len(options) < 2:
        issues.append("missing_options")
    elif len(options) > 6:
        issues.append("unexpected_option_count")
    if labels and len(labels) != len(set(labels)):
        issues.append("duplicate_option_label")
    if options and any(
        not clean_exam_markdown(item.get("text_markdown") or "")
        for item in options
    ):
        issues.append("missing_option_text")
    if (
        options
        and all(
            _MARKER_ONLY_RE.fullmatch(
                clean_exam_markdown(item.get("text_markdown") or "")
            )
            for item in options
        )
        and _COUNT_QUESTION_RE.search(text) is None
    ):
        issues.append("placeholder_option_text")
    correct = clean_exam_markdown(question.get("correct_option_label") or "")
    if correct and labels and correct not in labels:
        issues.append("correct_option_not_in_options")
    solution = clean_exam_markdown(question.get("teacher_solution_markdown") or "")
    if "missing_solution_text" in existing and len(solution) < 24:
        issues.append("missing_solution_text")
    text_values = [
        text,
        *(
            clean_exam_markdown(item.get("text_markdown") or "")
            for item in options
        ),
        solution,
        clean_exam_markdown(question.get("final_answer_markdown") or ""),
    ]
    if any(has_broken_persian_text(value) for value in text_values):
        issues.append("broken_persian_text")
    if any(has_duplicate_clean_and_broken_text(value) for value in text_values):
        issues.append("duplicate_mixed_text")
    if _VISUAL_REFERENCE_RE.search(text):
        issues.append("visual_evidence_required")
    if not question.get("source_verified") and solution_mismatch_candidate(question):
        issues.append("solution_semantic_mismatch_candidate")
    return list(dict.fromkeys(issues))


def question_needs_targeted_repair(question: dict[str, Any]) -> bool:
    return bool(
        set(canonical_question_issues(question))
        & _REPAIRABLE_QUESTION_CODES
    )


def _page_parts(pages: Iterable[RenderedExamPage]) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    for page in list(pages)[:2]:
        native = native_text_for_model(page.native_text, max_chars=12_000)
        parts.append(
            {
                "type": "text",
                "text": (
                    f"SOURCE_PAGE_NUMBER: {page.page_number}\n"
                    "SOURCE_NATIVE_TEXT_BEGIN\n"
                    f"{native}\n"
                    "SOURCE_NATIVE_TEXT_END"
                ),
            }
        )
        parts.append(
            part_from_bytes(data=page.image, mime_type=page.mime_type)
        )
    return parts


def verify_and_repair_question(
    question: dict[str, Any],
    *,
    source_pages: list[RenderedExamPage],
    model: str,
) -> VerifiedQuestionRepair:
    number = _number(question)
    if number < 1:
        raise ValueError("A positive source question number is required.")
    current = json.dumps(question, ensure_ascii=False, separators=(",", ":"))
    result = generate_structured(
        schema=VerifiedQuestionRepair,
        messages=[
            {
                "role": "system",
                "content": PROMPTS["exam_prep_question_repair"]["default"],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"REQUESTED_QUESTION_NUMBER: {number}\n"
                            "CURRENT_ASSEMBLED_QUESTION_BEGIN\n"
                            f"{current}\n"
                            "CURRENT_ASSEMBLED_QUESTION_END\n"
                            f"CURRENT_ISSUES: {', '.join(canonical_question_issues(question))}"
                        ),
                    },
                    *_page_parts(source_pages),
                ],
            },
        ],
        model=model,
        feature=LLMUsageLog.Feature.PDF_EXTRACTION,
        timeout=float(
            os.getenv("EXAM_PREP_QUESTION_REPAIR_TIMEOUT_SECONDS", "180")
        ),
        temperature=0,
        max_repair=1,
        strict_json_schema=True,
        sensitive=True,
        max_output_tokens=_positive_int_env(
            "EXAM_PREP_QUESTION_REPAIR_MAX_OUTPUT_TOKENS",
            12_000,
        ),
        detail="exam_prep_question_source_repair",
        tracking_context={
            "stage": "question_source_repair",
            "question_number": number,
            "source_page_count": min(2, len(source_pages)),
        },
        provider_attempts=1,
    )
    if result.question_number != number:
        raise StructuredOutputError(
            f"Question repair returned {result.question_number}, expected {number}.",
            error_kind="question_number_mismatch",
        )
    return result


def _apply_repair(
    question: dict[str, Any],
    repair: VerifiedQuestionRepair,
) -> dict[str, Any]:
    if not repair.source_supported or repair.confidence < 0.72:
        return {
            **question,
            "issues": list(
                dict.fromkeys(
                    [
                        *canonical_question_issues(question),
                        "targeted_repair_unresolved",
                    ]
                )
            ),
        }
    updated = {
        **question,
        "question_text_markdown": (
            clean_exam_markdown(repair.question_text_markdown)
            or question.get("question_text_markdown", "")
        ),
        "options": (
            [item.model_dump() for item in repair.options]
            or question.get("options", [])
        ),
        "correct_option_label": (
            clean_exam_markdown(repair.correct_option_label)
            or question.get("correct_option_label")
        ),
        "teacher_solution_markdown": (
            clean_exam_markdown(repair.teacher_solution_markdown)
            or question.get("teacher_solution_markdown", "")
        ),
        "final_answer_markdown": (
            clean_exam_markdown(repair.final_answer_markdown)
            or question.get("final_answer_markdown", "")
        ),
        "confidence": max(
            float(question.get("confidence") or 0.0),
            repair.confidence,
        ),
        "source_verified": True,
    }
    updated["issues"] = list(
        dict.fromkeys(
            [
                *canonical_question_issues(updated),
                *repair.issues,
            ]
        )
    )
    return updated


def rebuild_assembly_quality(
    result: PageAssemblyResult,
) -> PageAssemblyResult:
    projection = dict(result.projection)
    exam = dict(projection.get("exam_prep") or {})
    questions = []
    issues: list[AssemblyIssue] = []
    matched_answers = 0
    for question in exam.get("questions") or []:
        if not isinstance(question, dict):
            continue
        updated = {
            **question,
            "issues": canonical_question_issues(question),
        }
        questions.append(updated)
        number = _number(updated)
        scope = str(updated.get("scope_key") or "default")
        pages = [
            int(value)
            for value in (updated.get("source_pages") or [])
            if str(value).isdigit()
        ]
        for code in updated["issues"]:
            issues.append(
                AssemblyIssue(
                    code=code,
                    scope_key=scope,
                    question_number=number,
                    source_pages=pages,
                )
            )
        if any(
            clean_exam_markdown(updated.get(field) or "")
            for field in (
                "correct_option_label",
                "correct_option_text_markdown",
                "teacher_solution_markdown",
                "final_answer_markdown",
            )
        ):
            matched_answers += 1
    for scope, numbers in result.question_number_gaps.items():
        for number in numbers:
            issues.append(
                AssemblyIssue(
                    code="missing_question_number",
                    scope_key=scope,
                    question_number=number,
                    source_pages=[],
                )
            )
    exam["questions"] = questions
    projection["exam_prep"] = exam
    review_count = sum(
        bool(question.get("issues"))
        for question in questions
    )
    publication_ready = bool(questions) and not any(
        is_critical_page_issue(issue.code)
        for issue in issues
    )
    return result.model_copy(
        update={
            "projection": projection,
            "issues": issues,
            "question_count": len(questions),
            "questions_needing_review": review_count,
            "matched_answer_count": matched_answers,
            "publication_ready": publication_ready,
        }
    )


def repair_suspicious_questions(
    result: PageAssemblyResult,
    *,
    source_pages_by_number: dict[int, RenderedExamPage],
    model: str,
) -> tuple[PageAssemblyResult, dict[str, int]]:
    projection = dict(result.projection)
    exam = dict(projection.get("exam_prep") or {})
    questions = [
        item
        for item in (exam.get("questions") or [])
        if isinstance(item, dict)
    ]
    maximum = _positive_int_env(
        "EXAM_PREP_MAX_TARGETED_QUESTION_REPAIRS",
        30,
    )
    repaired = 0
    unresolved = 0
    attempted = 0
    updated_questions: list[dict[str, Any]] = []
    for question in questions:
        if (
            not question_needs_targeted_repair(question)
            or attempted >= maximum
        ):
            updated_questions.append(
                {
                    **question,
                    "issues": canonical_question_issues(question),
                }
            )
            continue
        page_numbers = []
        for value in question.get("source_pages") or []:
            try:
                page_number = int(value)
            except (TypeError, ValueError):
                continue
            if (
                page_number not in page_numbers
                and page_number in source_pages_by_number
            ):
                page_numbers.append(page_number)
        pages = [
            source_pages_by_number[number]
            for number in page_numbers[:2]
        ]
        if not pages:
            updated_questions.append(
                {
                    **question,
                    "issues": list(
                        dict.fromkeys(
                            [
                                *canonical_question_issues(question),
                                "targeted_repair_no_source_page",
                            ]
                        )
                    ),
                }
            )
            unresolved += 1
            continue
        attempted += 1
        try:
            repair = verify_and_repair_question(
                question,
                source_pages=pages,
                model=model,
            )
            updated = _apply_repair(question, repair)
        except Exception:
            updated = {
                **question,
                "issues": list(
                    dict.fromkeys(
                        [
                            *canonical_question_issues(question),
                            "targeted_repair_failed",
                        ]
                    )
                ),
            }
        remaining = (
            set(canonical_question_issues(updated))
            & _REPAIRABLE_QUESTION_CODES
        )
        if remaining:
            unresolved += 1
        else:
            repaired += 1
        updated_questions.append(updated)
    exam["questions"] = updated_questions
    projection["exam_prep"] = exam
    rebuilt = rebuild_assembly_quality(
        result.model_copy(update={"projection": projection})
    )
    return rebuilt, {
        "attempted": attempted,
        "repaired": repaired,
        "unresolved": unresolved,
    }
