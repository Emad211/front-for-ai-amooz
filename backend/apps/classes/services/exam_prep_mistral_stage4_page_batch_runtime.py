"""Production wrapper for page-batched Stage 4 candidate comparisons.

The underlying page-batch orchestrator is kept compact and stable. This wrapper
installs deterministic production guards before exposing it:

* use lexical-only JSON normalization that preserves raw LaTeX source text;
* compare exactly the canonical candidate field-set rather than a flattened blob;
* never let an LLM overwrite a label locked by trusted native PDF evidence;
* do not broaden an option-only OCR disagreement into a stem replacement;
* treat absent provider fields as unavailable evidence;
* split a failed page batch only when the provider explicitly reports output
  truncation. STOP+malformed JSON, network, HTTP and timeouts are never retried;
* reserve budget by crop-count before a primary call;
* open a per-run, concurrency-safe primary circuit after two consecutive
  image-provenance failures so a broken multimodal route cannot consume the rest
  of the PDF budget.
"""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import replace
import os
from typing import Any, Mapping

from . import exam_prep_mistral_page_batch_transcriber as _page_transport
from . import exam_prep_mistral_stage4_page_batch as _impl
from . import exam_prep_mistral_stage4 as _legacy
from .exam_prep_mistral_json_lexical import decode_structured_json_text
from .exam_prep_mistral_page_batch_transcriber import PageBatchEnvelopeError
from .exam_prep_mistral_risk_engine_v2 import score_region_risks as _score
from .exam_prep_utils import clean_exam_markdown


_page_transport._decode_structured_text = decode_structured_json_text
_PROVENANCE_FAILURE_PREFIX = "image_modality_unproven:"
_PROVENANCE_FAILURE_LIMIT = 2
_PROVENANCE_STATE: ContextVar[dict[str, int | bool] | None] = ContextVar(
    "exam_prep_stage4_provenance_state",
    default=None,
)


def _number(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float_env(name: str, default: float, *, low: float, high: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(low, min(high, value))


def _question_map(projection: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    exam = projection.get("exam_prep")
    questions = exam.get("questions") if isinstance(exam, Mapping) else []
    output: dict[int, Mapping[str, Any]] = {}
    for question in questions or []:
        if not isinstance(question, Mapping):
            continue
        number = _number(question.get("source_question_number"))
        if number > 0:
            output[number] = question
    return output


def _normalized_score_region_risks(*, projection, **kwargs):
    decisions = _score(projection=projection, **kwargs)
    questions = _question_map(projection)
    output = []
    for decision in decisions:
        question = questions.get(decision.question_number)
        if question is None:
            output.append(decision)
            continue
        if decision.kind == "question":
            candidate = _legacy._question_payload_text(question)
        else:
            candidate = _legacy._solution_payload_text(question)
        output.append(replace(decision, candidate_text=candidate))
    return output


def _needed_fields(decision, question, payload):
    """Return source fields that are actually allowed to change."""

    issues = {str(code) for code in (question.get("issues") or []) if str(code)}
    issues.update(str(code) for code in decision.region_issues if str(code))
    signals = set(decision.signals)
    available = _impl._valid_source_fields(decision, payload)

    if decision.kind == "question":
        needed: set[str] = set()
        if (
            not clean_exam_markdown(question.get("question_text_markdown") or "")
            or issues & _impl._STEM_ISSUES
        ):
            needed.add("question_text_markdown")
        option_map = {
            str(item.get("label") or "").translate(_impl._DIGITS).strip(): clean_exam_markdown(
                item.get("text_markdown") or ""
            )
            for item in (question.get("options") or [])
            if isinstance(item, Mapping)
        }
        if issues & _impl._OPTION_ISSUES or set(option_map) != {"1", "2", "3", "4"}:
            needed.update({"option_1", "option_2", "option_3", "option_4"})
        else:
            for label in ("1", "2", "3", "4"):
                if not option_map.get(label):
                    needed.add(f"option_{label}")

        if signals & _impl._CORRUPTION_SIGNALS:
            needed.update(available)
        elif "ocr_disagreement" in signals and not (issues & _impl._OPTION_ISSUES):
            needed.update(available)
        return needed

    needed: set[str] = set()
    native_label_locked = "native_pdf_answer_label_authority" in issues
    existing_label = _impl._normalize_label(question.get("correct_option_label"))
    if not native_label_locked and (
        existing_label not in {"1", "2", "3", "4"} or issues & _impl._LABEL_ISSUES
    ):
        needed.add("correct_option_label")
    if (
        not clean_exam_markdown(question.get("teacher_solution_markdown") or "")
        or issues & _impl._SOLUTION_BODY_ISSUES
    ):
        needed.add("teacher_solution_markdown")
    if signals & _impl._CORRUPTION_SIGNALS:
        needed.add("teacher_solution_markdown")
    if "ocr_disagreement" in signals:
        needed.update(available)
    if not native_label_locked and signals & {"missing_invalid_answer", "heading_conflict"}:
        needed.add("correct_option_label")
    if native_label_locked:
        needed.discard("correct_option_label")
    return needed


_ORIGINAL_SANITIZE_ITEM = _impl._sanitize_item


def _sanitize_item_with_absence(item):
    payload, blocked, flags = _ORIGINAL_SANITIZE_ITEM(item)
    blocked = set(blocked)
    if item.kind == "question":
        if not clean_exam_markdown(payload.get("question_text_markdown") or ""):
            blocked.add("question_text_markdown")
        labels = {
            str(raw.get("label") or "").translate(_impl._DIGITS).strip()
            for raw in (payload.get("options") or [])
            if isinstance(raw, Mapping) and clean_exam_markdown(raw.get("text_markdown") or "")
        }
        for label in ("1", "2", "3", "4"):
            if label not in labels:
                blocked.add(f"option_{label}")
    else:
        if _impl._normalize_label(payload.get("correct_option_label")) not in {"1", "2", "3", "4"}:
            blocked.add("correct_option_label")
        if not clean_exam_markdown(payload.get("teacher_solution_markdown") or ""):
            blocked.add("teacher_solution_markdown")
    return payload, blocked, flags


def _primary_reserve(target_count: int) -> float:
    base = _float_env(
        "EXAM_PREP_STAGE4_PRIMARY_RESERVE_BASE_USD", 0.0028, low=0.001, high=0.02
    )
    per_extra = _float_env(
        "EXAM_PREP_STAGE4_PRIMARY_RESERVE_PER_EXTRA_TARGET_USD",
        0.00205,
        low=0.0002,
        high=0.01,
    )
    return min(0.025, base + per_extra * max(0, int(target_count) - 1))


def _budget_reserve(kind: str) -> float:
    if kind == "secondary":
        return _float_env(
            "EXAM_PREP_STAGE4_SECONDARY_RESERVE_USD", 0.0045, low=0.001, high=0.03
        )
    return _primary_reserve(2)


def _call_primary_budgeted(*, page_number, targets, spent, budget):
    reserve = _primary_reserve(len(targets))
    if budget is not None and spent + reserve > max(0.0, float(budget)) + 1e-12:
        return None, RuntimeError("stage4_cost_budget"), spent
    try:
        result = _impl.transcribe_page_batch(page_number=page_number, targets=targets)
        return result, None, spent + _impl._gemini_cost(result)
    except PageBatchEnvelopeError as exc:
        return None, exc, spent + _impl._gemini_cost(exc)
    except Exception as exc:
        return None, exc, spent


def _is_truncation_error(error: Any) -> bool:
    if not isinstance(error, PageBatchEnvelopeError):
        return False
    finish = str(getattr(error, "finish_reason", "") or "").strip().upper()
    return finish in {"MAX_TOKENS", "LENGTH", "MAX_OUTPUT_TOKENS"}


def _provenance_state() -> dict[str, int | bool]:
    state = _PROVENANCE_STATE.get()
    if state is None:
        state = {"consecutiveFailures": 0, "circuitOpen": False, "blockedPages": 0}
        _PROVENANCE_STATE.set(state)
    return state


def _record_primary_outcome(result, error) -> None:
    state = _provenance_state()
    if result is not None:
        state["consecutiveFailures"] = 0
        return
    reason = str(getattr(error, "reason_code", "") or "")
    if reason.startswith(_PROVENANCE_FAILURE_PREFIX):
        failures = int(state.get("consecutiveFailures") or 0) + 1
        state["consecutiveFailures"] = failures
        if failures >= _PROVENANCE_FAILURE_LIMIT:
            state["circuitOpen"] = True
    else:
        # Only consecutive image-provenance failures open the circuit.
        state["consecutiveFailures"] = 0


def _retry_missing_targets_budgeted(*, page_number, rendered, failed_target_ids, spent, budget, audits):
    """Retry only the targets a successful batch call omitted or invalidated.

    A batch call can return HTTP 200 with valid JSON overall while still
    dropping or malforming one or two of several requested items — the model
    does not always return every item in a large batch. That partial gap
    previously had no retry path at all and went straight to
    ``provider_failed``. One small follow-up call carrying only the missing
    targets (not the whole page) recovers most of these cheaply. This is a
    distinct scenario from a full envelope failure (malformed JSON/timeout),
    which remains intentionally non-retried.
    """

    retry_targets = [item for item in rendered if item[0].target_id in failed_target_ids]
    if not retry_targets:
        return None, 0, 0, spent
    retry, retry_error, spent = _impl._call_primary(
        page_number=page_number, targets=retry_targets, spent=spent, budget=budget
    )
    _record_primary_outcome(retry, retry_error)
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
                "finishReason": str(getattr(retry_error, "finish_reason", "") or ""),
            }
        )
        return None, 1, 1, spent
    audits.append({**retry.safe_dict(), "status": "retry_success"})
    return retry, 1, 1, spent


def _page_results_with_structured_split_only(*, page_number, rendered, spent, budget):
    requested = {decision.target_id for decision, _ in rendered}
    audits = []
    results = []
    primary_calls = split_calls = 0
    state = _provenance_state()

    if bool(state.get("circuitOpen")):
        state["blockedPages"] = int(state.get("blockedPages") or 0) + 1
        audits.append(
            {
                "pageNumber": page_number,
                "status": "primary_circuit_open",
                "targetCount": len(rendered),
                "reason": "image_provenance_circuit_open",
            }
        )
        return results, requested, audits, spent, primary_calls, split_calls

    first, error, spent = _impl._call_primary(
        page_number=page_number,
        targets=rendered,
        spent=spent,
        budget=budget,
    )
    _record_primary_outcome(first, error)
    if first is not None:
        primary_calls += 1
        results.append(first)
        audits.append({**first.safe_dict(), "status": "success"})
        failed = set(first.missing_target_ids) | set(first.invalid_target_ids)
        if not failed or bool(_provenance_state().get("circuitOpen")):
            return results, failed, audits, spent, primary_calls, split_calls
        retry_result, retry_calls, retry_split, spent = _retry_missing_targets_budgeted(
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
        audits.append(
            {"pageNumber": page_number, "status": "budget_blocked", "targetCount": len(rendered)}
        )
        return results, requested, audits, spent, primary_calls, split_calls

    primary_calls += 1
    reason = getattr(error, "reason_code", type(error).__name__ if error else "unknown")
    finish_reason = str(getattr(error, "finish_reason", "") or "")
    base_audit = {
        "pageNumber": page_number,
        "targetCount": len(rendered),
        "reason": str(reason),
        "finishReason": finish_reason,
    }
    if bool(state.get("circuitOpen")):
        base_audit["circuitOpened"] = True
    if not _is_truncation_error(error):
        audits.append({**base_audit, "status": "provider_failed_no_retry"})
        return results, requested, audits, spent, primary_calls, split_calls

    audits.append({**base_audit, "status": "truncated_envelope_split"})
    if len(rendered) <= 1:
        return results, requested, audits, spent, primary_calls, split_calls

    midpoint = max(1, len(rendered) // 2)
    failed: set[str] = set()
    for part_index, part in enumerate((rendered[:midpoint], rendered[midpoint:]), start=1):
        if not part:
            continue
        child, child_error, spent = _impl._call_primary(
            page_number=page_number, targets=part, spent=spent, budget=budget
        )
        _record_primary_outcome(child, child_error)
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
                    "finishReason": str(getattr(child_error, "finish_reason", "") or ""),
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


_impl.score_region_risks = _normalized_score_region_risks
_impl._needed_fields = _needed_fields
_impl._sanitize_item = _sanitize_item_with_absence
_impl._budget_reserve = _budget_reserve
_impl._call_primary = _call_primary_budgeted
_impl._page_results_with_one_split = _page_results_with_structured_split_only


def verify_and_repair_risky_regions_page_batched(*args, **kwargs):
    """Run one isolated Stage-4 primary circuit per PDF invocation."""

    state = {"consecutiveFailures": 0, "circuitOpen": False, "blockedPages": 0}
    token = _PROVENANCE_STATE.set(state)
    try:
        result, audit = _impl.verify_and_repair_risky_regions_page_batched(*args, **kwargs)
    finally:
        _PROVENANCE_STATE.reset(token)

    output_audit = dict(audit)
    stats = dict(output_audit.get("stats") or {})
    stats["imageProvenanceCircuitOpened"] = bool(state.get("circuitOpen"))
    stats["imageProvenanceCircuitBlockedPages"] = int(state.get("blockedPages") or 0)
    output_audit["stats"] = stats
    policy = dict(output_audit.get("policy") or {})
    policy["imageProvenanceRequired"] = True
    policy["imageProvenanceCircuitFailureLimit"] = _PROVENANCE_FAILURE_LIMIT
    output_audit["policy"] = policy
    return result, output_audit


PageBatchStats = _impl.PageBatchStats

__all__ = [
    "PageBatchStats",
    "_PROVENANCE_FAILURE_LIMIT",
    "_page_results_with_structured_split_only",
    "verify_and_repair_risky_regions_page_batched",
]
