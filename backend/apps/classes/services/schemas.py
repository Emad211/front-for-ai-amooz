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

from typing import List, Optional

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
