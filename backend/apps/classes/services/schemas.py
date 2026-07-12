"""Pydantic schemas for validating LLM pipeline JSON outputs.

These models are intentionally LENIENT: ``extra='allow'`` everywhere and most
fields optional. The goal is to catch the *real* failure modes of free-text LLM
JSON — a non-object top level, prose instead of JSON, a missing/!=list ``outline``,
units that aren't objects — WITHOUT rejecting valid-but-richer outputs (the model
is free to add fields). Validation is used as a gate; the original parsed dict is
preserved downstream so we never mutate the model's data shape.

Source of truth for the contract: ``PROMPTS['structure_content']`` in
``apps/commons/llm_prompts``.
"""
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class StructureUnit(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: Optional[str] = None
    title: Optional[str] = None
    merrill_type: Optional[str] = None
    source_markdown: Optional[str] = None
    content_markdown: Optional[str] = None
    image_ideas: List[str] = Field(default_factory=list)


class StructureSection(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: Optional[str] = None
    title: Optional[str] = None
    # The core invariant the pipeline relies on: a section carries a list of units.
    units: List[StructureUnit] = Field(default_factory=list)


class StructureRootObject(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: Optional[str] = None
    main_problem: Optional[str] = None
    target_audience_level: Optional[str] = None
    estimated_time: Optional[str] = None
    summary: Optional[str] = None
    what_you_will_learn: List[str] = Field(default_factory=list)


class StructureOutput(BaseModel):
    """Top-level shape of Step-2 structure JSON: ``root_object`` + ``outline``.

    The strongest guarantee we enforce is that ``outline`` is a list of section
    objects, each with a ``units`` list — which is exactly what asset reinjection
    and ``sync_structure_from_session`` iterate over. Everything else stays soft.
    """

    model_config = ConfigDict(extra="allow")

    root_object: Optional[StructureRootObject] = None
    outline: List[StructureSection] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Exercise Hub — exercise structure extraction (services/exercise_ingest.py).
# Contract source of truth: ``PROMPTS['exercise_structure']['default']``.
# Load-bearing invariant: ``questions`` is one ordered list. Legacy
# ``sections[].questions`` remains accepted only during the compatibility window.
# ---------------------------------------------------------------------------


class ExerciseQuestionOut(BaseModel):
    model_config = ConfigDict(extra="allow")

    question_id: Optional[str] = None
    question_text_markdown: Optional[str] = None
    question_type: Optional[str] = None
    options: Optional[List[Any]] = None
    points: Optional[float] = None
    reference_answer_markdown: Optional[str] = None


class ExerciseSectionOut(BaseModel):
    model_config = ConfigDict(extra="allow")

    section_id: Optional[str] = None
    title: Optional[str] = None
    questions: List[ExerciseQuestionOut] = Field(default_factory=list)


class ExerciseStructureOutput(BaseModel):
    """Flat exercise structure with a temporary legacy-sections fallback."""

    model_config = ConfigDict(extra="allow")

    exercise_title: Optional[str] = None
    questions: List[ExerciseQuestionOut] = Field(default_factory=list)
    # Compatibility only: old workers/mocks may still return section-shaped JSON.
    sections: List[ExerciseSectionOut] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Exercise Hub — teacher reference-answer ingest (services/exercise_ingest.py).
# Contract: ``PROMPTS['exercise_reference_ingest']['default']``.
# It accepts messy OCR/source text where questions and teacher answers may be
# mixed, separated, numbered, or answer-only. Matching is applied server-side.
# ---------------------------------------------------------------------------


class ExerciseReferenceIngestItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    item_id: Optional[str] = None
    question_number: Optional[int] = None
    question_text_markdown: Optional[str] = None
    question_type: Optional[str] = None
    options: Optional[List[Any]] = None
    points: Optional[float] = None
    reference_answer_markdown: Optional[str] = None
    confidence: Optional[float] = None
    notes: Optional[str] = None


class ExerciseReferenceIngestOutput(BaseModel):
    """Top-level teacher reference ingest JSON.

    ``items`` is the only load-bearing invariant; each item may become a new
    question, update an existing question, or be returned as skipped when the
    target question is ambiguous.
    """

    model_config = ConfigDict(extra="allow")

    mode_detected: Optional[str] = None
    items: List[ExerciseReferenceIngestItem] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Exercise Hub — grading output (services/exercise_grading.py). Same score shape
# as the final exam, so ``compute_weak_points_from`` reuses the parser.
# Contract: ``PROMPTS['exercise_grading']['default']``.
# ---------------------------------------------------------------------------


class ExerciseGradedQuestion(BaseModel):
    model_config = ConfigDict(extra="allow")

    question_id: Optional[str] = None
    score_points: Optional[float] = None
    max_points: Optional[float] = None
    label: Optional[str] = None
    feedback: Optional[str] = None
    missing_points: List[str] = Field(default_factory=list)


class ExerciseGradingOutput(BaseModel):
    """Batch grading result: a list of per-question scores. The load-bearing
    invariant is that ``per_question`` is a list."""

    model_config = ConfigDict(extra="allow")

    per_question: List[ExerciseGradedQuestion] = Field(default_factory=list)


class HandwritingTranscriptionOutput(BaseModel):
    """Vision transcription of a student's handwritten answer photo(s).
    Contract: ``PROMPTS['exercise_handwriting_vision']['default']``. ``text`` is
    deliberately REQUIRED (unlike the lenient siblings) so a missing key triggers
    ``generate_structured``'s repair round-trip instead of silently yielding an
    empty transcription."""

    model_config = ConfigDict(extra="allow")

    text: str


class AssistantChatOutput(BaseModel):
    """Exercise assistant reply shape (same as the exam-prep chat widget)."""

    model_config = ConfigDict(extra="allow")

    content: Optional[str] = None
    suggestions: List[str] = Field(default_factory=list)
