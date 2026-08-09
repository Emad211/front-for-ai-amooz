"""Page-batched Stage-4 verification and repair.

Risk selection remains per OCR region, but provider transport is grouped by
physical source page.  All suspicious crops from one page are sent to Gemini in
one native structured-output request.  This keeps crop isolation while avoiding
one reasoning pass per region.

The Mistral candidate is never sent to Gemini.  It is used only after the
source-only read for deterministic merge/disagreement decisions.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
import os
import re
from typing import Any, Mapping, Sequence

from . import exam_prep_mistral_stage4 as legacy
from .exam_prep_mistral_direct_transcription import numeric_signature
from .exam_prep_mistral_page_batch_transcriber import (
    BatchItem,
    PageBatchResult,
    transcribe_page_batch,
)
from .exam_prep_mistral_region_transcriber import secondary_model, transcribe_source_region
from .exam_prep_mistral_risk_engine import RegionRiskDecision
from .exam_prep_mistral_risk_engine_v2 import score_region_risks
from .exam_prep_page_records import PageAssemblyResult
from .exam_prep_question_verifier import rebuild_assembly_quality
from .exam_prep_utils import clean_exam_markdown


_STAGE4_BLOCKER = "stage4_verification_unresolved"
_CORRUPTION_SIGNALS = frozenset(
    {
        "source_corruption",
        "symbol_substitution_proxy",
        "pathological_repetition",
    }
)
_STRUCTURAL_SOURCE_SIGNALS = frozenset(
    {
        "missing_invalid_answer",
        "ocr_disagreement",
        "heading_conflict",
    }
)
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _secondary_cap() -> int:
    try:
        value = int(os.getenv("EXAM_PREP_STAGE4_MAX_SECONDARY_CALLS", "6"))
    except (TypeError, ValueError):
        value = 6
    return max(0, min(12, value))


def _page_batch_cap() -> int:
    try:
        value = int(os.getenv("EXAM_PREP_STAGE4_MAX_PAGE_BATCH_CALLS", "24"))
    except (TypeError, ValueError):
        value = 24
    return max(1, min(40, value))


def _normalize_label(value: Any) -> str:
    text = clean_exam_markdown(value or "").translate(_DIGITS)
    match = re.search(r"[1-4]", text)
    return match.group(0) if match else ""


def _question_map(result: PageAssemblyResult) -> dict[int, dict[str, Any]]:
    return legacy._question_map(result)


def _question_payload(item: BatchItem) -> dict[str, Any] | None:
    stem = clean_exam_markdown(item.question_text_markdown)
    if not stem:
        return None
    options: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in item.options:
        label = _normalize_label(raw.label)
        text = clean_exam_markdown(raw.text_markdown)
        if label not in {"1", "2", "3", "4"} or label in seen:
            continue
        seen.add(label)
        options.append({"label": label, "text_markdown": text})
    options.sort(key=lambda row: int(row["label"]))
    if {row["label"] for row in options} != {"1", "2", "3", "4"}:
        return None
    if any(not row["text_markdown"] for row in options) and not item.source_visual_required:
        return None
    return {"question_text_markdown": stem, "options": options}


def _solution_payload(
    item: BatchItem,
    *,
    question: Mapping[str, Any],
    decision: RegionRiskDecision,
) -> dict[str, Any] | None:
    body = clean_exam_markdown(item.teacher_solution_markdown)
    if not body:
        return None
    label = _normalize_label(item.correct_option_label)
    existing = _normalize_label(question.get("correct_option_label"))
    requires_source_label = bool(
        set(decision.signals) & {"missing_invalid_answer", "heading_conflict"}
    )
    if label not in {"1", "2", "3", "4"}:
        if requires_source_label:
            return None
        label = existing
    return {
        "correct_option_label": label,
        "teacher_solution_markdown": body,
        "final_answer_markdown": f"گزینه {label}" if label else "",
    }


def _payload(decision: RegionRiskDecision, item: BatchItem, question: Mapping[str, Any]):
    if item.transcription_uncertain:
        return None
    if decision.kind == "question":
        return _question_payload(item)
    return _solution_payload(item, question=question, decision=decision)


def _payload_text(decision: RegionRiskDecision, payload: Mapping[str, Any]) -> str:
    if decision.kind == "question":
        return legacy._question_payload_text(payload)
    return legacy._solution_payload_text(payload)


def _numeric_similarity(left: str, right: str) -> float:
    a = numeric_signature(left)
    b = numeric_signature(right)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _secondary_payload(decision: RegionRiskDecision, image: bytes):
    result = transcribe_source_region(
        image=image,
        kind=decision.kind,
        question_number=decision.question_number,
        page_number=decision.page_number,
        model=secondary_model(),
        thinking_minimal=False,
    )
    return result, legacy._proposal(decision, result)


def _primary_safe(item: BatchItem) -> dict[str, Any]:
    return {
        "targetId": item.target_id,
        "kind": item.kind,
        "questionNumber": item.question_number,
        "sourceVisualRequired": bool(item.source_visual_required),
        "visualType": item.visual_type,
        "transcriptionUncertain": bool(item.transcription_uncertain),
    }


def _apply(question: dict[str, Any], decision: RegionRiskDecision, payload: Mapping[str, Any]):
    return legacy._apply_proposal(question, decision=decision, payload=payload)


def _mark_unresolved(question: dict[str, Any]):
    return legacy._mark_unresolved(question)


@dataclass(frozen=True, slots=True)
class PageBatchStats:
    regions: int
    clean: int
    suspicious: int
    page_batches: int
    primary_targets: int
    secondary_calls: int
    verified: int
    repaired: int
    unresolved: int
    deferred: int

    def as_dict(self) -> dict[str, int]:
        return {
            "regions": self.regions,
            "clean": self.clean,
            "suspicious": self.suspicious,
            "pageBatches": self.page_batches,
            "primaryCalls": self.page_batches,
            "primaryTargets": self.primary_targets,
            "secondaryCalls": self.secondary_calls,
            "verified": self.verified,
            "repaired": self.repaired,
            "unresolved": self.unresolved,
            "deferred": self.deferred,
        }


def verify_and_repair_risky_regions_page_batched(
    result: PageAssemblyResult,
    *,
    pdf_data: bytes,
    layout: Mapping[str, Any],
    recovered_solution_targets: Sequence[int] | set[int] = (),
    unresolved_solution_targets: Sequence[int] | set[int] = (),
    should_cancel=None,
) -> tuple[PageAssemblyResult, dict[str, Any]]:
    decisions = score_region_risks(
        projection=result.projection,
        layout=layout,
        recovered_solution_targets=recovered_solution_targets,
        unresolved_solution_targets=unresolved_solution_targets,
    )
    suspicious = [item for item in decisions if item.suspicious]
    grouped: dict[int, list[RegionRiskDecision]] = defaultdict(list)
    for item in suspicious:
        grouped[item.page_number].append(item)

    questions = _question_map(result)
    rows: dict[str, dict[str, Any]] = {
        item.target_id: {
            **item.safe_dict(),
            "status": "pending" if item.suspicious else "clean",
        }
        for item in decisions
    }
    page_audit: list[dict[str, Any]] = []
    verified = repaired = unresolved = deferred = secondary_calls = page_batches = 0
    maximum_pages = _page_batch_cap()
    maximum_secondary = _secondary_cap()

    for page_index, page_number in enumerate(sorted(grouped)):
        if should_cancel is not None and should_cancel():
            raise RuntimeError("Cancellation requested during Stage-4 page batching.")
        targets = grouped[page_number]
        if page_index >= maximum_pages:
            for decision in targets:
                question = questions.get(decision.question_number)
                if question is not None:
                    questions[decision.question_number] = _mark_unresolved(question)
                rows[decision.target_id].update(
                    {"status": "deferred_cost_cap", "reason": "page_batch_cap"}
                )
                deferred += 1
            continue

        rendered: list[tuple[RegionRiskDecision, bytes]] = []
        crop_by_target: dict[str, bytes] = {}
        try:
            for decision in targets:
                crop = legacy._render_crop(pdf_data, decision)
                rendered.append((decision, crop))
                crop_by_target[decision.target_id] = crop
            batch: PageBatchResult = transcribe_page_batch(
                page_number=page_number,
                targets=rendered,
            )
            page_batches += 1
            page_audit.append(batch.safe_dict())
        except Exception as exc:
            for decision in targets:
                question = questions.get(decision.question_number)
                if question is not None:
                    questions[decision.question_number] = _mark_unresolved(question)
                rows[decision.target_id].update(
                    {"status": "provider_failed", "reason": type(exc).__name__}
                )
                unresolved += 1
            page_audit.append(
                {
                    "pageNumber": page_number,
                    "targetCount": len(targets),
                    "status": "failed",
                    "reason": type(exc).__name__,
                }
            )
            continue

        item_by_target = {item.target_id: item for item in batch.items}
        for decision in targets:
            question = questions.get(decision.question_number)
            if question is None:
                continue
            row = rows[decision.target_id]
            item = item_by_target[decision.target_id]
            row["primary"] = _primary_safe(item)
            payload = _payload(decision, item, question)
            if payload is None:
                if decision.hard_math and secondary_calls < maximum_secondary:
                    try:
                        secondary, second_payload = _secondary_payload(
                            decision,
                            crop_by_target[decision.target_id],
                        )
                        secondary_calls += 1
                        row["secondary"] = secondary.safe_dict()
                    except Exception as exc:
                        second_payload = None
                        row.update({"status": "secondary_failed", "reason": type(exc).__name__})
                    if second_payload is not None and not secondary.transcript.get("transcriptionUncertain"):
                        questions[decision.question_number] = _apply(
                            question,
                            decision,
                            second_payload,
                        )
                        row["status"] = "repaired_secondary_source"
                        repaired += 1
                        verified += 1
                        continue
                questions[decision.question_number] = _mark_unresolved(question)
                if row.get("status") == "pending":
                    row["status"] = "source_uncertain" if item.transcription_uncertain else "primary_invalid"
                unresolved += 1
                continue

            primary_text = _payload_text(decision, payload)
            candidate_text = decision.candidate_text
            signals = set(decision.signals)
            numeric_same = numeric_signature(primary_text) == numeric_signature(candidate_text)
            row["candidateNumericAgreement"] = bool(numeric_same)

            # Known corruption means disagreement with Mistral is expected, not a
            # reason to buy a second opinion. A valid, non-uncertain source read
            # repairs the corrupted candidate directly.
            if signals & (_CORRUPTION_SIGNALS | _STRUCTURAL_SOURCE_SIGNALS):
                questions[decision.question_number] = _apply(question, decision, payload)
                row["status"] = "repaired_primary_source"
                repaired += 1
                verified += 1
                continue

            if not decision.hard_math:
                questions[decision.question_number] = _apply(question, decision, payload)
                row["status"] = "repaired_primary_source"
                repaired += 1
                verified += 1
                continue

            if numeric_same:
                row["status"] = "verified_primary_preserved_candidate"
                verified += 1
                continue

            # Hard math with no pre-proven corruption: only here is a paid second
            # opinion justified.
            if secondary_calls >= maximum_secondary:
                questions[decision.question_number] = _mark_unresolved(question)
                row.update({"status": "unresolved", "reason": "secondary_cap"})
                unresolved += 1
                continue
            try:
                secondary, second_payload = _secondary_payload(
                    decision,
                    crop_by_target[decision.target_id],
                )
                secondary_calls += 1
                row["secondary"] = secondary.safe_dict()
            except Exception as exc:
                questions[decision.question_number] = _mark_unresolved(question)
                row.update({"status": "secondary_failed", "reason": type(exc).__name__})
                unresolved += 1
                continue
            if second_payload is None or secondary.transcript.get("transcriptionUncertain"):
                questions[decision.question_number] = _mark_unresolved(question)
                row["status"] = "secondary_uncertain"
                unresolved += 1
                continue

            second_text = _payload_text(decision, second_payload)
            primary_second_numeric = _numeric_similarity(primary_text, second_text)
            candidate_second_numeric = _numeric_similarity(candidate_text, second_text)
            row["secondaryPrimaryNumericSimilarity"] = round(primary_second_numeric, 6)
            row["secondaryCandidateNumericSimilarity"] = round(candidate_second_numeric, 6)
            if primary_second_numeric >= 0.90:
                questions[decision.question_number] = _apply(question, decision, payload)
                row["status"] = "repaired_two_model_numeric_consensus"
                repaired += 1
                verified += 1
            elif candidate_second_numeric >= 0.95:
                row["status"] = "verified_secondary_preserved_candidate"
                verified += 1
            else:
                questions[decision.question_number] = _mark_unresolved(question)
                row["status"] = "second_opinion_disagreement"
                unresolved += 1

    projection = dict(result.projection)
    exam = dict(projection.get("exam_prep") or {})
    ordered: list[dict[str, Any]] = []
    for raw in exam.get("questions") or []:
        if not isinstance(raw, Mapping):
            continue
        number = legacy._question_number(raw)
        question = dict(questions.get(number, raw))
        metadata = dict(question.get("stage4_verification") or {})
        metadata["regions"] = [
            row for row in rows.values() if int(row.get("questionNumber") or 0) == number
        ]
        metadata["hasSuspiciousRegion"] = any(
            bool(row.get("suspicious")) for row in metadata["regions"]
        )
        question["stage4_verification"] = metadata
        ordered.append(question)
    exam["questions"] = ordered
    projection["exam_prep"] = exam
    updated = result.model_copy(update={"projection": projection})
    updated = rebuild_assembly_quality(updated)

    stats = PageBatchStats(
        regions=len(decisions),
        clean=len(decisions) - len(suspicious),
        suspicious=len(suspicious),
        page_batches=page_batches,
        primary_targets=len(suspicious),
        secondary_calls=secondary_calls,
        verified=verified,
        repaired=repaired,
        unresolved=unresolved,
        deferred=deferred,
    )
    audit = {
        "schemaVersion": 2,
        "policy": {
            "candidateMistralShown": False,
            "grouping": "physical_page",
            "oneRequestContainsAllSuspiciousCropsFromPage": True,
            "fullPageImageSent": False,
            "nativeGeminiStructuredOutput": True,
            "primaryThinking": "minimal",
            "automaticPrimaryRetry": False,
            "automaticPaidRepair": False,
            "secondaryOnlyForUnresolvedHardMath": True,
            "modelConfidenceAuthority": False,
            "visualEvidenceMutableByVerifier": False,
        },
        "stats": stats.as_dict(),
        "pageBatches": page_audit,
        "regions": [rows[item.target_id] for item in decisions],
    }
    return updated, audit


__all__ = ["PageBatchStats", "verify_and_repair_risky_regions_page_batched"]
