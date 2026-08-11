"""Page-batched Stage-4 verification and conservative field repair.

Risk selection stays per OCR region, while all suspicious crops from one physical
page share one Gemini request. Valid sibling items survive partial provider
output. A wholly unusable batch may be split once into two bounded sub-batches;
there is no recursive retry.

The Mistral candidate is never sent to Gemini. Provider output is sanitized and
merged field-by-field; source uncertainty can block only the field it affects.
Stage-3 visual evidence is never replaced here.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import os
import re
from typing import Any, Mapping, Sequence

from . import exam_prep_mistral_stage4 as legacy
from .exam_prep_mistral_page_batch_transcriber import (
    BatchItem,
    PageBatchEnvelopeError,
    PageBatchResult,
    transcribe_page_batch,
)
from .exam_prep_mistral_region_transcriber import secondary_model, transcribe_source_region
from .exam_prep_mistral_risk_engine import RegionRiskDecision
from .exam_prep_mistral_risk_engine_v2 import score_region_risks
from .exam_prep_mistral_stage4_field_safety import (
    candidate_fields,
    compare_field_maps,
    comparisons_safe_dict,
    critical_conflict,
    payload_fields,
    sanitize_source_markdown,
    uncertain_fields,
)
from .exam_prep_page_records import PageAssemblyResult
from .exam_prep_question_verifier import rebuild_assembly_quality
from .exam_prep_utils import clean_exam_markdown


_STAGE4_BLOCKER = "stage4_verification_unresolved"
_CORRUPTION_SIGNALS = frozenset(
    {"source_corruption", "symbol_substitution_proxy", "pathological_repetition"}
)
_STRUCTURAL_SOURCE_SIGNALS = frozenset(
    {"missing_invalid_answer", "ocr_disagreement", "heading_conflict"}
)
_OPTION_ISSUES = frozenset(
    {
        "mistral_question_option_parse_failed",
        "missing_options",
        "missing_option_text",
        "missing_options_text",
        "placeholder_option_text",
        "unexpected_option_count",
        "duplicate_option_label",
    }
)
_STEM_ISSUES = frozenset({"missing_question_text", "broken_persian_text", "duplicate_mixed_text"})
_LABEL_ISSUES = frozenset(
    {
        "mistral_solution_heading_unresolved",
        "missing_answer",
        "missing_correct_option_label",
        "correct_option_not_in_options",
        "conflicting_correct_option",
        "conflicting_correct_option_text",
        "count_answer_unresolved",
    }
)
_SOLUTION_BODY_ISSUES = frozenset(
    {"missing_solution_text", "broken_persian_text", "duplicate_mixed_text"}
)
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_PLACEHOLDER = "[?]"

# Current official standard token prices (USD / 1M tokens) for the models used by
# this stage. Provider-returned estimated_cost remains authoritative when present.
_GEMINI_INPUT_PER_M = 0.50
_GEMINI_OUTPUT_PER_M = 3.00
_GPT54_MINI_INPUT_PER_M = 0.75
_GPT54_MINI_OUTPUT_PER_M = 4.50


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


def _budget_reserve(kind: str) -> float:
    name = (
        "EXAM_PREP_STAGE4_PRIMARY_RESERVE_USD"
        if kind == "primary"
        else "EXAM_PREP_STAGE4_SECONDARY_RESERVE_USD"
    )
    default = 0.006 if kind == "primary" else 0.012
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(0.001, min(0.05, value))


def _normalize_label(value: Any) -> str:
    text = clean_exam_markdown(value or "").translate(_DIGITS)
    match = re.search(r"[1-4]", text)
    return match.group(0) if match else ""


def _question_map(result: PageAssemblyResult) -> dict[int, dict[str, Any]]:
    return legacy._question_map(result)


def _gemini_cost(value: PageBatchResult | PageBatchEnvelopeError) -> float:
    estimated = getattr(value, "estimated_cost", {}) or {}
    try:
        provider = float(estimated.get("unit") or 0)
    except (TypeError, ValueError):
        provider = 0.0
    if provider > 0:
        return provider
    usage = getattr(value, "usage", {}) or {}
    input_tokens = int(usage.get("inputTokens") or 0)
    output_tokens = int(usage.get("outputTokens") or 0)
    reasoning_tokens = int(usage.get("reasoningTokens") or 0)
    return (
        input_tokens * _GEMINI_INPUT_PER_M
        + (output_tokens + reasoning_tokens) * _GEMINI_OUTPUT_PER_M
    ) / 1_000_000.0


def _secondary_cost(result: Any) -> float:
    return (
        int(getattr(result, "input_tokens", 0) or 0) * _GPT54_MINI_INPUT_PER_M
        + int(getattr(result, "output_tokens", 0) or 0) * _GPT54_MINI_OUTPUT_PER_M
    ) / 1_000_000.0


def _budget_allows(spent: float, limit: float | None, kind: str) -> bool:
    if limit is None:
        return True
    return spent + _budget_reserve(kind) <= max(0.0, float(limit)) + 1e-12


def _sanitize_item(item: BatchItem) -> tuple[dict[str, Any], set[str], tuple[str, ...]]:
    """Return canonical source fields, blocked fields and sanitizer audit flags."""

    blocked = set(uncertain_fields(item))
    sanitizer_flags: list[str] = []
    stem, flags = sanitize_source_markdown(item.question_text_markdown)
    sanitizer_flags.extend(flags)
    body, flags = sanitize_source_markdown(item.teacher_solution_markdown)
    sanitizer_flags.extend(flags)

    options: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in item.options:
        label = _normalize_label(raw.label)
        text, flags = sanitize_source_markdown(raw.text_markdown)
        sanitizer_flags.extend(flags)
        if label in {"1", "2", "3", "4"} and label not in seen:
            seen.add(label)
            options.append({"label": label, "text_markdown": text})
        if _PLACEHOLDER in text and label in {"1", "2", "3", "4"}:
            blocked.add(f"option_{label}")
    options.sort(key=lambda row: int(row["label"]))

    if _PLACEHOLDER in stem:
        blocked.add("question_text_markdown")
    if _PLACEHOLDER in body:
        blocked.add("teacher_solution_markdown")
    label = _normalize_label(item.correct_option_label)
    if _PLACEHOLDER in str(item.correct_option_label or ""):
        blocked.add("correct_option_label")

    payload = {
        "question_text_markdown": stem,
        "options": options,
        "correct_option_label": label,
        "teacher_solution_markdown": body,
        "final_answer_markdown": f"گزینه {label}" if label else "",
    }
    return payload, blocked, tuple(dict.fromkeys(sanitizer_flags))


def _valid_source_fields(
    decision: RegionRiskDecision,
    payload: Mapping[str, Any],
) -> set[str]:
    fields = payload_fields(payload, kind=decision.kind)
    return {field for field, value in fields.items() if clean_exam_markdown(value or "")}


def _needed_fields(
    decision: RegionRiskDecision,
    question: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> set[str]:
    """Select only fields for which this risk provides a reason to overwrite source."""

    issues = {str(code) for code in (question.get("issues") or []) if str(code)}
    issues.update(str(code) for code in decision.region_issues if str(code))
    signals = set(decision.signals)
    available = _valid_source_fields(decision, payload)

    if decision.kind == "question":
        needed: set[str] = set()
        if not clean_exam_markdown(question.get("question_text_markdown") or "") or issues & _STEM_ISSUES:
            needed.add("question_text_markdown")
        option_map = {
            str(item.get("label") or "").translate(_DIGITS).strip(): clean_exam_markdown(
                item.get("text_markdown") or ""
            )
            for item in (question.get("options") or [])
            if isinstance(item, Mapping)
        }
        if issues & _OPTION_ISSUES or set(option_map) != {"1", "2", "3", "4"}:
            needed.update({"option_1", "option_2", "option_3", "option_4"})
        else:
            for label in ("1", "2", "3", "4"):
                if not option_map.get(label):
                    needed.add(f"option_{label}")
        if signals & (_CORRUPTION_SIGNALS | {"ocr_disagreement"}):
            needed.update(available)
        return needed & available

    needed = set()
    existing_label = _normalize_label(question.get("correct_option_label"))
    if existing_label not in {"1", "2", "3", "4"} or issues & _LABEL_ISSUES:
        needed.add("correct_option_label")
    if not clean_exam_markdown(question.get("teacher_solution_markdown") or "") or issues & _SOLUTION_BODY_ISSUES:
        needed.add("teacher_solution_markdown")
    if signals & _CORRUPTION_SIGNALS:
        needed.add("teacher_solution_markdown")
    if signals & {"ocr_disagreement"}:
        needed.update(available)
    if signals & {"missing_invalid_answer", "heading_conflict"}:
        needed.add("correct_option_label")
    return needed & available


def _apply_fields(
    question: dict[str, Any],
    *,
    decision: RegionRiskDecision,
    payload: Mapping[str, Any],
    accepted_fields: set[str],
) -> dict[str, Any]:
    """Patch only accepted text fields. Visuals/contracts are untouched."""

    updated = dict(question)
    if decision.kind == "question":
        if "question_text_markdown" in accepted_fields:
            updated["question_text_markdown"] = clean_exam_markdown(
                payload.get("question_text_markdown") or ""
            )
        existing = {
            str(raw.get("label") or "").translate(_DIGITS).strip(): dict(raw)
            for raw in (question.get("options") or [])
            if isinstance(raw, Mapping)
            and str(raw.get("label") or "").translate(_DIGITS).strip() in {"1", "2", "3", "4"}
        }
        source = {
            str(raw.get("label") or "").translate(_DIGITS).strip(): dict(raw)
            for raw in (payload.get("options") or [])
            if isinstance(raw, Mapping)
            and str(raw.get("label") or "").translate(_DIGITS).strip() in {"1", "2", "3", "4"}
        }
        for label in ("1", "2", "3", "4"):
            if f"option_{label}" in accepted_fields and label in source:
                existing[label] = {
                    "label": label,
                    "text_markdown": clean_exam_markdown(source[label].get("text_markdown") or ""),
                }
        if existing:
            updated["options"] = [existing[label] for label in ("1", "2", "3", "4") if label in existing]
        stale = set()
        if "question_text_markdown" in accepted_fields:
            stale.update(_STEM_ISSUES)
        if any(field.startswith("option_") for field in accepted_fields):
            stale.update(_OPTION_ISSUES)
    else:
        stale = set()
        if "correct_option_label" in accepted_fields:
            label = _normalize_label(payload.get("correct_option_label"))
            if label in {"1", "2", "3", "4"}:
                updated["correct_option_label"] = label
                updated["final_answer_markdown"] = f"گزینه {label}"
                stale.update(_LABEL_ISSUES)
        if "teacher_solution_markdown" in accepted_fields:
            body = clean_exam_markdown(payload.get("teacher_solution_markdown") or "")
            if body:
                updated["teacher_solution_markdown"] = body
                stale.update(_SOLUTION_BODY_ISSUES)

    updated["issues"] = [
        str(code)
        for code in (updated.get("issues") or [])
        if str(code) not in stale and str(code) != _STAGE4_BLOCKER
    ]
    return updated


def _mark_unresolved(question: dict[str, Any]) -> dict[str, Any]:
    return legacy._mark_unresolved(question)


def _secondary_payload(decision: RegionRiskDecision, image: bytes):
    result = transcribe_source_region(
        image=image,
        kind=decision.kind,
        question_number=decision.question_number,
        page_number=decision.page_number,
        model=secondary_model(),
        thinking_minimal=False,
    )
    payload = legacy._proposal(decision, result)
    if payload is None:
        return result, None, ()
    flags: list[str] = []
    if decision.kind == "question":
        stem, f = sanitize_source_markdown(payload.get("question_text_markdown") or "")
        flags.extend(f)
        options = []
        for raw in payload.get("options") or []:
            if not isinstance(raw, Mapping):
                continue
            text, f = sanitize_source_markdown(raw.get("text_markdown") or "")
            flags.extend(f)
            options.append({"label": raw.get("label"), "text_markdown": text})
        payload = {**payload, "question_text_markdown": stem, "options": options}
    else:
        body, f = sanitize_source_markdown(payload.get("teacher_solution_markdown") or "")
        flags.extend(f)
        payload = {**payload, "teacher_solution_markdown": body}
    return result, payload, tuple(dict.fromkeys(flags))


def _primary_safe(item: BatchItem) -> dict[str, Any]:
    return {
        "targetId": item.target_id,
        "kind": item.kind,
        "questionNumber": item.question_number,
        "sourceVisualRequired": bool(item.source_visual_required),
        "visualType": item.visual_type,
        "transcriptionUncertain": bool(item.transcription_uncertain),
        "uncertainFields": sorted(uncertain_fields(item)),
    }


def _call_primary(
    *,
    page_number: int,
    targets: Sequence[tuple[RegionRiskDecision, bytes]],
    spent: float,
    budget: float | None,
) -> tuple[PageBatchResult | None, PageBatchEnvelopeError | Exception | None, float]:
    if not _budget_allows(spent, budget, "primary"):
        return None, RuntimeError("stage4_cost_budget"), spent
    try:
        result = transcribe_page_batch(page_number=page_number, targets=targets)
        return result, None, spent + _gemini_cost(result)
    except PageBatchEnvelopeError as exc:
        return None, exc, spent + _gemini_cost(exc)
    except Exception as exc:
        return None, exc, spent


def _retry_missing_targets(
    *,
    page_number: int,
    rendered: Sequence[tuple[RegionRiskDecision, bytes]],
    failed_target_ids: set[str],
    spent: float,
    budget: float | None,
    audits: list[dict[str, Any]],
) -> tuple[PageBatchResult | None, int, int, float]:
    """Retry only the targets a successful batch call omitted or invalidated.

    A batch call can return HTTP 200 with valid JSON overall while still
    dropping or malforming one or two of several requested items — the model
    does not always return every item in a large batch. That partial gap
    previously had no retry path at all and went straight to
    ``provider_failed``. One small follow-up call carrying only the missing
    targets (not the whole page) recovers most of these cheaply.
    """

    retry_targets = [item for item in rendered if item[0].target_id in failed_target_ids]
    if not retry_targets:
        return None, 0, 0, spent
    retry, retry_error, spent = _call_primary(
        page_number=page_number, targets=retry_targets, spent=spent, budget=budget
    )
    if retry is None:
        if isinstance(retry_error, RuntimeError) and str(retry_error) == "stage4_cost_budget":
            audits.append(
                {
                    "pageNumber": page_number,
                    "status": "retry_budget_blocked",
                    "targetCount": len(retry_targets),
                }
            )
            return None, 0, 0, spent
        reason = getattr(
            retry_error, "reason_code", type(retry_error).__name__ if retry_error else "unknown"
        )
        audits.append(
            {
                "pageNumber": page_number,
                "status": "retry_failed",
                "targetCount": len(retry_targets),
                "reason": str(reason),
            }
        )
        return None, 1, 1, spent
    audits.append({**retry.safe_dict(), "status": "retry_success"})
    return retry, 1, 1, spent


def _page_results_with_one_split(
    *,
    page_number: int,
    rendered: Sequence[tuple[RegionRiskDecision, bytes]],
    spent: float,
    budget: float | None,
) -> tuple[list[PageBatchResult], set[str], list[dict[str, Any]], float, int, int]:
    """Call one page once; only an envelope failure may split once into two calls."""

    requested = {decision.target_id for decision, _ in rendered}
    audits: list[dict[str, Any]] = []
    results: list[PageBatchResult] = []
    primary_calls = split_calls = 0

    first, error, spent = _call_primary(
        page_number=page_number, targets=rendered, spent=spent, budget=budget
    )
    if first is not None:
        primary_calls += 1
        results.append(first)
        audits.append({**first.safe_dict(), "status": "success"})
        failed = set(first.missing_target_ids) | set(first.invalid_target_ids)
        if not failed:
            return results, failed, audits, spent, primary_calls, split_calls

        retry_result, retry_calls, retry_split, spent = _retry_missing_targets(
            page_number=page_number,
            rendered=rendered,
            failed_target_ids=failed,
            spent=spent,
            budget=budget,
            audits=audits,
        )
        primary_calls += retry_calls
        split_calls += retry_split
        if retry_result is not None:
            results.append(retry_result)
            failed = failed - set(item.target_id for item in retry_result.items)
        return results, failed, audits, spent, primary_calls, split_calls

    if isinstance(error, RuntimeError) and str(error) == "stage4_cost_budget":
        audits.append({"pageNumber": page_number, "status": "budget_blocked", "targetCount": len(rendered)})
        return results, requested, audits, spent, primary_calls, split_calls

    primary_calls += 1
    reason = getattr(error, "reason_code", type(error).__name__ if error else "unknown")
    audits.append(
        {
            "pageNumber": page_number,
            "status": "envelope_failed",
            "targetCount": len(rendered),
            "reason": str(reason),
        }
    )
    if len(rendered) <= 1:
        return results, requested, audits, spent, primary_calls, split_calls

    midpoint = max(1, len(rendered) // 2)
    failed: set[str] = set()
    for part_index, part in enumerate((rendered[:midpoint], rendered[midpoint:]), start=1):
        if not part:
            continue
        child, child_error, spent = _call_primary(
            page_number=page_number, targets=part, spent=spent, budget=budget
        )
        if child is None:
            if isinstance(child_error, RuntimeError) and str(child_error) == "stage4_cost_budget":
                child_reason = "cost_budget"
            else:
                primary_calls += 1
                split_calls += 1
                child_reason = getattr(
                    child_error,
                    "reason_code",
                    type(child_error).__name__ if child_error else "unknown",
                )
            failed.update(decision.target_id for decision, _ in part)
            audits.append(
                {
                    "pageNumber": page_number,
                    "status": "split_failed",
                    "splitPart": part_index,
                    "targetCount": len(part),
                    "reason": str(child_reason),
                }
            )
            continue
        primary_calls += 1
        split_calls += 1
        results.append(child)
        failed.update(child.missing_target_ids)
        failed.update(child.invalid_target_ids)
        audits.append({**child.safe_dict(), "status": "split_success", "splitPart": part_index})
    return results, failed, audits, spent, primary_calls, split_calls


@dataclass(frozen=True, slots=True)
class PageBatchStats:
    regions: int
    clean: int
    suspicious: int
    page_batches: int
    primary_calls: int
    split_calls: int
    primary_targets: int
    secondary_calls: int
    verified: int
    repaired: int
    partial_repairs: int
    unresolved: int
    deferred: int
    primary_cost_usd: float
    secondary_cost_usd: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "regions": self.regions,
            "clean": self.clean,
            "suspicious": self.suspicious,
            "pageBatches": self.page_batches,
            "primaryCalls": self.primary_calls,
            "splitCalls": self.split_calls,
            "primaryTargets": self.primary_targets,
            "secondaryCalls": self.secondary_calls,
            "verified": self.verified,
            "repaired": self.repaired,
            "partialRepairs": self.partial_repairs,
            "unresolved": self.unresolved,
            "deferred": self.deferred,
            "primaryCostUsd": round(self.primary_cost_usd, 8),
            "secondaryCostUsd": round(self.secondary_cost_usd, 8),
            "totalLlmCostUsd": round(self.primary_cost_usd + self.secondary_cost_usd, 8),
        }


def verify_and_repair_risky_regions_page_batched(
    result: PageAssemblyResult,
    *,
    pdf_data: bytes,
    layout: Mapping[str, Any],
    recovered_solution_targets: Sequence[int] | set[int] = (),
    unresolved_solution_targets: Sequence[int] | set[int] = (),
    should_cancel=None,
    max_cost_usd: float | None = None,
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
    verified = repaired = partial_repairs = unresolved = deferred = secondary_calls = 0
    page_batches = primary_calls = split_calls = 0
    primary_cost = secondary_cost = 0.0
    spent = 0.0
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
        for decision in targets:
            try:
                crop = legacy._render_crop(pdf_data, decision)
            except Exception as exc:
                question = questions.get(decision.question_number)
                if question is not None:
                    questions[decision.question_number] = _mark_unresolved(question)
                rows[decision.target_id].update(
                    {"status": "provider_failed", "reason": f"crop:{type(exc).__name__}"}
                )
                unresolved += 1
                continue
            rendered.append((decision, crop))
            crop_by_target[decision.target_id] = crop
        if not rendered:
            continue

        before = spent
        results, provider_failed_ids, audits, spent, calls, splits = _page_results_with_one_split(
            page_number=page_number,
            rendered=rendered,
            spent=spent,
            budget=max_cost_usd,
        )
        page_batches += 1
        primary_calls += calls
        split_calls += splits
        primary_cost += max(0.0, spent - before)
        page_audit.extend(audits)

        item_by_target: dict[str, BatchItem] = {}
        for batch in results:
            for item in batch.items:
                item_by_target[item.target_id] = item

        for decision, _crop in rendered:
            question = questions.get(decision.question_number)
            if question is None:
                continue
            row = rows[decision.target_id]
            item = item_by_target.get(decision.target_id)
            if item is None:
                questions[decision.question_number] = _mark_unresolved(question)
                if decision.target_id in provider_failed_ids:
                    if any(a.get("status") == "budget_blocked" for a in audits):
                        row.update({"status": "deferred_cost_cap", "reason": "total_cost_budget"})
                        deferred += 1
                    else:
                        row.update({"status": "provider_failed", "reason": "missing_or_invalid_batch_item"})
                        unresolved += 1
                else:
                    row.update({"status": "provider_failed", "reason": "missing_batch_item"})
                    unresolved += 1
                continue

            row["primary"] = _primary_safe(item)
            payload, blocked_fields, sanitizer_flags = _sanitize_item(item)
            if sanitizer_flags:
                row["sanitizerFlags"] = list(sanitizer_flags)
            if "*" in blocked_fields:
                needed = _needed_fields(decision, question, payload)
                questions[decision.question_number] = _mark_unresolved(question)
                row.update(
                    {
                        "status": "source_uncertain",
                        "reason": "coarse_uncertainty",
                        "blockedFields": ["*"],
                        "neededFields": sorted(needed),
                    }
                )
                unresolved += 1
                continue

            needed = _needed_fields(decision, question, payload)
            valid = _valid_source_fields(decision, payload)
            accepted = (needed & valid) - blocked_fields
            blocked_needed = needed & blocked_fields
            row["neededFields"] = sorted(needed)
            if blocked_fields:
                row["blockedFields"] = sorted(blocked_fields)

            primary_fields = payload_fields(payload, kind=decision.kind)
            candidate = candidate_fields(question, kind=decision.kind)
            comparison = compare_field_maps(candidate, primary_fields)
            row["candidateFieldAgreement"] = comparisons_safe_dict(comparison)
            signals = set(decision.signals)

            if blocked_needed:
                if accepted:
                    question = _apply_fields(
                        question,
                        decision=decision,
                        payload=payload,
                        accepted_fields=accepted,
                    )
                    questions[decision.question_number] = _mark_unresolved(question)
                    row["status"] = "partial_repair_source_uncertain"
                    repaired += 1
                    partial_repairs += 1
                else:
                    questions[decision.question_number] = _mark_unresolved(question)
                    row["status"] = "source_uncertain"
                unresolved += 1
                continue

            # Proven candidate corruption/structural failure: repair only fields
            # for which the evidence actually gives a reason to overwrite source.
            if signals & (_CORRUPTION_SIGNALS | _STRUCTURAL_SOURCE_SIGNALS):
                if accepted:
                    questions[decision.question_number] = _apply_fields(
                        question,
                        decision=decision,
                        payload=payload,
                        accepted_fields=accepted,
                    )
                    row["status"] = "repaired_primary_fields"
                    repaired += 1
                else:
                    row["status"] = "verified_primary_no_field_change"
                verified += 1
                continue

            # Visual-only or other non-textual suspicion is not permission to
            # overwrite text. Hard math only escalates on a real field conflict.
            relevant = {
                field: agreement
                for field, agreement in comparison.items()
                if field not in blocked_fields
            }
            if not decision.hard_math or not critical_conflict(relevant):
                if accepted:
                    questions[decision.question_number] = _apply_fields(
                        question,
                        decision=decision,
                        payload=payload,
                        accepted_fields=accepted,
                    )
                    row["status"] = "repaired_primary_fields"
                    repaired += 1
                else:
                    row["status"] = "verified_primary_preserved_candidate"
                verified += 1
                continue

            conflict_fields = {
                field for field, agreement in relevant.items() if agreement.critical_conflict
            }
            row["hardConflictFields"] = sorted(conflict_fields)
            if secondary_calls >= maximum_secondary or not _budget_allows(spent, max_cost_usd, "secondary"):
                questions[decision.question_number] = _mark_unresolved(question)
                reason = "secondary_cap" if secondary_calls >= maximum_secondary else "total_cost_budget"
                row.update({"status": "unresolved", "reason": reason})
                unresolved += 1
                if reason == "total_cost_budget":
                    deferred += 1
                continue

            try:
                secondary, second_payload, secondary_sanitizer = _secondary_payload(
                    decision, crop_by_target[decision.target_id]
                )
                secondary_calls += 1
                secondary_cost_delta = _secondary_cost(secondary)
                secondary_cost += secondary_cost_delta
                spent += secondary_cost_delta
                row["secondary"] = secondary.safe_dict()
                if secondary_sanitizer:
                    row["secondarySanitizerFlags"] = list(secondary_sanitizer)
            except Exception as exc:
                questions[decision.question_number] = _mark_unresolved(question)
                row.update({"status": "secondary_failed", "reason": type(exc).__name__})
                unresolved += 1
                continue

            # An uncertain second opinion has no authority. It contributes no
            # vote; this hard conflict therefore remains fail-closed.
            if second_payload is None or secondary.transcript.get("transcriptionUncertain"):
                questions[decision.question_number] = _mark_unresolved(question)
                row["status"] = "secondary_no_vote"
                unresolved += 1
                continue

            second_fields = payload_fields(second_payload, kind=decision.kind)
            primary_second = compare_field_maps(primary_fields, second_fields)
            candidate_second = compare_field_maps(candidate, second_fields)
            row["secondaryPrimaryFieldAgreement"] = comparisons_safe_dict(primary_second)
            row["secondaryCandidateFieldAgreement"] = comparisons_safe_dict(candidate_second)
            primary_wins = all(
                field in primary_second and not primary_second[field].critical_conflict
                for field in conflict_fields
            )
            candidate_wins = all(
                field in candidate_second and not candidate_second[field].critical_conflict
                for field in conflict_fields
            )
            if primary_wins and not candidate_wins:
                fields_to_apply = (accepted | (conflict_fields & valid)) - blocked_fields
                if fields_to_apply:
                    questions[decision.question_number] = _apply_fields(
                        question,
                        decision=decision,
                        payload=payload,
                        accepted_fields=fields_to_apply,
                    )
                    row["status"] = "repaired_two_model_field_consensus"
                    repaired += 1
                else:
                    row["status"] = "verified_primary_no_field_change"
                verified += 1
            elif candidate_wins and not primary_wins:
                row["status"] = "verified_secondary_preserved_candidate"
                verified += 1
            elif primary_wins and candidate_wins:
                row["status"] = "verified_semantic_consensus_preserved_candidate"
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
        primary_calls=primary_calls,
        split_calls=split_calls,
        primary_targets=len(suspicious),
        secondary_calls=secondary_calls,
        verified=verified,
        repaired=repaired,
        partial_repairs=partial_repairs,
        unresolved=unresolved,
        deferred=deferred,
        primary_cost_usd=primary_cost,
        secondary_cost_usd=secondary_cost,
    )
    audit = {
        "schemaVersion": 3,
        "policy": {
            "candidateMistralShown": False,
            "grouping": "physical_page_multi_crop",
            "fullPageImageSent": False,
            "partialItemValidation": True,
            "wholeEnvelopeSplitRetryMax": 1,
            "nativeGeminiStructuredOutput": True,
            "primaryThinking": "minimal",
            "automaticJsonRepair": False,
            "fieldSelectiveMerge": True,
            "fieldLevelUncertainty": True,
            "secondaryOnlyForUnresolvedHardMath": True,
            "secondaryUncertainHasAuthority": False,
            "modelConfidenceAuthority": False,
            "visualEvidenceMutableByVerifier": False,
            "maxCostUsd": None if max_cost_usd is None else round(float(max_cost_usd), 8),
        },
        "stats": stats.as_dict(),
        "pageBatches": page_audit,
        "regions": [rows[item.target_id] for item in decisions],
    }
    return updated, audit


__all__ = ["PageBatchStats", "verify_and_repair_risky_regions_page_batched"]
