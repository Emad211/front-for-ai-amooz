"""Inventory-first exam-prep extraction.

Question and answer records are generated in separate calls. Joining, duplicate
handling, stable IDs, and the publish audit are deterministic server logic.
"""

from __future__ import annotations

import json
import os
from typing import Any, Type

from pydantic import BaseModel

from apps.commons.llm_prompts import PROMPTS
from apps.commons.llm_provider import preferred_provider
from apps.commons.models import LLMUsageLog
from apps.commons.structured_llm import generate_structured

from .exam_prep_inventory import (
    annotate_answer_match_status,
    build_exam_projection,
    build_extraction_audit,
    chunk_source_blocks,
    deduplicate_answer_records,
    deduplicate_question_records,
    match_answers_to_questions,
    parse_source_blocks,
)
from .schemas import (
    ExamPrepAnswerInventoryOutput,
    ExamPrepPageManifestOutput,
    ExamPrepQuestionInventoryOutput,
)
from .text_sanitize import sanitize_llm_markdown


PIPELINE_VERSION = 2
PROMPT_VERSION = "exam-inventory-v2"


def inventory_enabled() -> bool:
    return (os.getenv("EXAM_PREP_EXTRACTION_V2", "false") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _select_model() -> str:
    for name in ("EXAM_PREP_STRUCTURE_MODEL", "STRUCTURE_MODEL", "REWRITE_MODEL", "MODEL_NAME"):
        if value := (os.getenv(name) or "").strip():
            return value
    raise RuntimeError("No exam-prep structure model configured in ENV.")


def _block_payload(blocks: list[dict[str, Any]], manifest_by_page: dict[int, dict]) -> str:
    payload = []
    for block in blocks:
        page_number = int(block["page_number"])
        payload.append(
            {
                "page_number": page_number,
                "block_order": int(block["block_order"]),
                "segment_index": int(block.get("segment_index") or 0),
                "manifest": manifest_by_page.get(page_number, {}),
                "content": block["content"],
            }
        )
    return json.dumps(payload, ensure_ascii=False)


def _call(
    *,
    schema: Type[BaseModel],
    prompt_key: str,
    blocks: list[dict[str, Any]],
    manifest_by_page: dict[int, dict],
    model: str,
) -> BaseModel:
    return generate_structured(
        schema=schema,
        messages=[
            {"role": "system", "content": PROMPTS[prompt_key]["default"]},
            {
                "role": "user",
                "content": "SOURCE_BLOCKS:\n" + _block_payload(blocks, manifest_by_page),
            },
        ],
        model=model,
        feature=LLMUsageLog.Feature.EXAM_PREP_STRUCTURE,
        timeout=int(os.getenv("LLM_TIMEOUT_SECONDS", "600")),
        temperature=0,
    )


def _normalize_record_pages(
    record: dict[str, Any], blocks: list[dict[str, Any]]
) -> dict[str, Any]:
    allowed_pages = {int(block["page_number"]) for block in blocks}
    pages = [
        int(page)
        for page in record.get("source_pages") or []
        if str(page).isdigit() and int(page) in allowed_pages
    ]
    if not pages and len(allowed_pages) == 1:
        pages = list(allowed_pages)
    record["source_pages"] = sorted(set(pages))
    if pages:
        block_order_by_page = {
            int(block["page_number"]): int(block["block_order"]) for block in blocks
        }
        record["block_order"] = min(block_order_by_page[page] for page in pages)
    return record


def _candidate_blocks(
    blocks: list[dict[str, Any]],
    manifest_by_page: dict[int, dict],
    *,
    kind: str,
) -> list[dict[str, Any]]:
    # Audio/video transcripts and single-image sources have no meaningful page
    # boundary. Their one logical block may contain both questions and answers,
    # so a page-level classifier is only a hint and must not suppress a phase.
    if len(blocks) == 1:
        return list(blocks)

    accepted = {"mixed", kind}
    selected = []
    for block in blocks:
        manifest = manifest_by_page.get(int(block["page_number"]), {})
        section_type = manifest.get("section_type")
        confidence = float(manifest.get("confidence") or 0)
        # Low-confidence classification is never allowed to discard source data.
        if section_type in accepted or section_type in (None, "other") or confidence < 0.7:
            selected.append(block)
    return selected


def extract_exam_prep_inventory(
    *, transcript_markdown: str
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str, str]:
    """Return projection, durable artifact payload, audit, provider, and model."""
    transcript = sanitize_llm_markdown(transcript_markdown)
    blocks = parse_source_blocks(transcript)
    if not blocks:
        raise RuntimeError("هیچ محتوایی برای استخراج آمادگی آزمون وجود ندارد.")

    model = _select_model()
    provider = preferred_provider()
    max_chars = max(4_000, min(_env_int("EXAM_PREP_INVENTORY_CHUNK_CHARS", 16_000), 32_000))
    chunks = chunk_source_blocks(blocks, max_chars=max_chars)
    failed_chunks: list[dict[str, Any]] = []

    manifest_items: list[dict[str, Any]] = []
    title = ""
    for index, chunk in enumerate(chunks):
        try:
            result = _call(
                schema=ExamPrepPageManifestOutput,
                prompt_key="exam_prep_page_manifest",
                blocks=chunk,
                manifest_by_page={},
                model=model,
            )
            title = title or result.title.strip()
            manifest_items.extend(item.model_dump() for item in result.pages)
        except Exception as exc:
            failed_chunks.append(
                {"phase": "manifest", "chunk": index, "pages": [b["page_number"] for b in chunk], "error": str(exc)}
            )

    manifest_by_page = {
        int(item["page_number"]): item
        for item in manifest_items
        if int(item["page_number"]) in {int(block["page_number"]) for block in blocks}
    }
    for block in blocks:
        page = int(block["page_number"])
        manifest_by_page.setdefault(
            page,
            {
                "page_number": page,
                "section_type": "other",
                "section_key": "",
                "question_numbers": [],
                "answer_numbers": [],
                "has_visuals": False,
                "confidence": 0,
            },
        )

    question_records: list[dict[str, Any]] = []
    answer_records: list[dict[str, Any]] = []
    phase_specs = (
        (
            "questions",
            ExamPrepQuestionInventoryOutput,
            "exam_prep_question_inventory",
            "questions",
            question_records,
        ),
        (
            "answers",
            ExamPrepAnswerInventoryOutput,
            "exam_prep_answer_inventory",
            "answers",
            answer_records,
        ),
    )
    for phase, schema, prompt_key, field_name, destination in phase_specs:
        candidates = _candidate_blocks(blocks, manifest_by_page, kind=phase)
        for index, chunk in enumerate(chunk_source_blocks(candidates, max_chars=max_chars)):
            try:
                result = _call(
                    schema=schema,
                    prompt_key=prompt_key,
                    blocks=chunk,
                    manifest_by_page=manifest_by_page,
                    model=model,
                )
                destination.extend(
                    _normalize_record_pages(item.model_dump(), chunk)
                    for item in getattr(result, field_name)
                )
            except Exception as exc:
                failed_chunks.append(
                    {"phase": phase, "chunk": index, "pages": [b["page_number"] for b in chunk], "error": str(exc)}
                )

    deduplicated, duplicate_issues = deduplicate_question_records(question_records)
    deduplicated_answers, answer_duplicate_issues = deduplicate_answer_records(
        answer_records
    )
    matched, unmatched, match_issues = match_answers_to_questions(
        deduplicated, deduplicated_answers
    )
    audit = build_extraction_audit(
        questions=matched,
        unmatched_answers=unmatched,
        issues=[*duplicate_issues, *answer_duplicate_issues, *match_issues],
        failed_chunks=failed_chunks,
        page_manifest=list(manifest_by_page.values()),
    )
    if not matched and failed_chunks:
        raise RuntimeError("استخراج سؤال‌ها کامل نشد و برای تلاش مجدد در صف قرار می‌گیرد.")

    projection = build_exam_projection(title=title, questions=matched)
    artifact = {
        "pipeline_version": PIPELINE_VERSION,
        "page_manifest": {"title": title, "pages": list(manifest_by_page.values())},
        "question_records": matched,
        "answer_records": annotate_answer_match_status(
            deduplicated_answers,
            unmatched,
        ),
        "failed_chunks": failed_chunks,
        "prompt_version": PROMPT_VERSION,
    }
    return projection, artifact, audit, provider, model
