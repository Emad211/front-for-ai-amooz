"""Single-region finalization for the Mistral OCR Exam Prep pipeline.

Stage 4's deterministic risk score is useful metadata, but it is not an
accuracy gate: calibrated semantic OCR failures can receive a clean score.
Stage 5 therefore gives every numbered question and solution region one cheap,
source-only read. Each provider request contains exactly one crop.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from decimal import Decimal
import io
import math
import os
import re
from time import monotonic
from typing import Any, Mapping, Sequence

from django.db import close_old_connections
from PIL import Image

from apps.chatbot.services.llm_client import _strip_model_prefix
from apps.commons.token_tracker import (
    get_current_session_id,
    get_current_user,
    llm_tracking_context,
)

from .exam_prep_mistral_region_transcriber import (
    RegionTranscriptionEmptyContent,
    RegionTranscriptionNonconformingContent,
    RegionTranscriptionResult,
    transcribe_source_region,
)
from .exam_prep_mistral_direct_transcription import (
    normalize_text_for_similarity,
    numeric_signature,
    text_similarity,
)
from .exam_prep_mistral_risk_engine import RegionRiskDecision
from .exam_prep_mistral_stage4 import (
    _agreement,
    _crop_dpi,
    _crop_padding,
    _max_crop_dimension,
    _proposal,
    _proposal_text,
)
from .exam_prep_mistral_stage4_field_safety import (
    candidate_fields,
    compare_field,
    payload_fields,
    sanitize_source_markdown,
)
from .exam_prep_mistral_solution_headings import parse_solution_heading
from .exam_prep_mistral_stage5_runtime import (
    Stage5BudgetLedger,
    Stage5CostBudgetExceeded,
    current_stage5_task_deadline,
)
from .exam_prep_page_output import is_review_blocking_issue
from .exam_prep_page_records import PageAssemblyResult
from .exam_prep_question_verifier import rebuild_assembly_quality


DEFAULT_PRIMARY_MODEL = "gpt-5.4-mini"
DEFAULT_MAIN_MODEL = "gemini-3.6-flash"
DEFAULT_TIEBREAKER_MODEL = ""
_STAGE5_BLOCKER = "stage5_finalization_blocked"
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_QUESTION_HEADING_RE = re.compile(
    r"^\s*(?:[#>*_`]+\s*)*([0-9۰-۹٠-٩]{1,4})(?:\s*[*_`]+)?\s*[-–—ـ:.)]"
)
_STRONG_VISUAL_TYPES = frozenset(
    {"diagram", "graph", "chemical_structure", "table", "spatial_layout"}
)
_LATEX_FRACTION_RE = re.compile(
    r"(?P<outer>[+-]?)\s*\\(?:d|t)?frac\s*"
    r"\{\s*(?P<inner>[+-]?\d+)\s*\}\s*\{\s*(?P<den>\d+)\s*\}"
)
_CANON_NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9])[-+]?\d+(?:/\d+|[\.,]\d+)?(?:\^[-+]?\d+)?"
)
_CANON_KEYED_RE = re.compile(
    r"(?P<key>\\?[A-Za-zΑ-Ωα-ω][A-Za-z0-9_Α-Ωα-ω]*)\s*=\s*"
    r"(?P<number>[-+]?\d+(?:/\d+|[\.,]\d+)?(?:\^[-+]?\d+)?)"
)
_FORMAT_RETRY_FAILURES = (
    RegionTranscriptionEmptyContent,
    RegionTranscriptionNonconformingContent,
)


class _Stage5DeadlineExceeded(RuntimeError):
    pass


def _model(name: str, default: str) -> str:
    return _strip_model_prefix((os.getenv(name) or default).strip())


def primary_model() -> str:
    return _model("EXAM_PREP_STAGE5_PRIMARY_MODEL", DEFAULT_PRIMARY_MODEL)


def main_model() -> str:
    return _model("EXAM_PREP_STAGE5_MAIN_MODEL", DEFAULT_MAIN_MODEL)


def tiebreaker_model() -> str:
    return _model("EXAM_PREP_STAGE5_TIEBREAKER_MODEL", DEFAULT_TIEBREAKER_MODEL)


def _int_env(name: str, default: int, *, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _float_env(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(30.0, min(180.0, value))


def _primary_cap() -> int:
    return _int_env("EXAM_PREP_STAGE5_MAX_PRIMARY_CALLS", 400, minimum=1, maximum=800)


def _main_cap() -> int:
    return _int_env("EXAM_PREP_STAGE5_MAX_MAIN_CALLS", 40, minimum=0, maximum=300)


def _max_output_tokens() -> int:
    return _int_env("EXAM_PREP_STAGE5_MAX_OUTPUT_TOKENS", 2500, minimum=1000, maximum=5000)


def _max_concurrency() -> int:
    return _int_env("EXAM_PREP_STAGE5_MAX_CONCURRENCY", 4, minimum=1, maximum=8)


def _max_wall_seconds() -> int:
    return _int_env(
        "EXAM_PREP_STAGE5_MAX_WALL_SECONDS",
        1800,
        minimum=300,
        maximum=2700,
    )


def _model_timeout(model: str) -> float:
    if model == main_model():
        return _float_env("EXAM_PREP_STAGE5_MAIN_TIMEOUT_SECONDS", 120.0)
    return _float_env("EXAM_PREP_STAGE5_PRIMARY_TIMEOUT_SECONDS", 60.0)


def _question_number(value: Any) -> int:
    try:
        return int(str(value or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")))
    except (TypeError, ValueError):
        return 0


def _question_map(result: PageAssemblyResult) -> dict[int, dict[str, Any]]:
    exam = result.projection.get("exam_prep")
    questions = exam.get("questions") if isinstance(exam, Mapping) else []
    return {
        number: dict(raw)
        for raw in questions or []
        if isinstance(raw, Mapping)
        and (number := _question_number(raw.get("source_question_number"))) > 0
    }


def _fields_equivalent(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    if set(left) != set(right):
        return False
    return all(
        normalize_text_for_similarity(str(left.get(field) or ""))
        == normalize_text_for_similarity(str(right.get(field) or ""))
        for field in left
    )


def _canonical_numeric_text(value: Any) -> str:
    text = normalize_text_for_similarity(str(value or ""))

    def replace_fraction(match: re.Match[str]) -> str:
        outer_negative = match.group("outer") == "-"
        inner = int(match.group("inner"))
        numerator = abs(inner)
        negative = outer_negative ^ (inner < 0)
        sign = "-" if negative else ""
        return f" {sign}{numerator}/{match.group('den')} "

    return _LATEX_FRACTION_RE.sub(replace_fraction, text)


def _canonical_numeric_counter(value: Any) -> Counter[str]:
    return Counter(_CANON_NUMBER_RE.findall(_canonical_numeric_text(value)))


def _canonical_keyed_counter(value: Any) -> Counter[tuple[str, str]]:
    output: Counter[tuple[str, str]] = Counter()
    for match in _CANON_KEYED_RE.finditer(_canonical_numeric_text(value)):
        output[(match.group("key").lstrip("\\").lower(), match.group("number"))] += 1
    return output


def _field_agrees(field: str, left: Any, right: Any) -> bool:
    a = str(left or "")
    b = str(right or "")
    if normalize_text_for_similarity(a) == normalize_text_for_similarity(b):
        return True
    if not a.strip() or not b.strip():
        return False
    comparison = compare_field(field, a, b)
    numeric_left = _canonical_numeric_counter(a)
    numeric_right = _canonical_numeric_counter(b)
    if numeric_left != numeric_right:
        return False
    if numeric_left:
        keyed_left = _canonical_keyed_counter(a)
        keyed_right = _canonical_keyed_counter(b)
        if (keyed_left or keyed_right) and keyed_left != keyed_right:
            return False
        standard_consensus = (
            comparison.math_token_similarity >= 0.72
            and comparison.text_similarity >= 0.86
        )
        order_tolerant_math_consensus = (
            comparison.math_token_similarity >= 0.90
            and comparison.text_similarity >= 0.70
        )
        return standard_consensus or order_tolerant_math_consensus
    return float(text_similarity(a, b)) >= 0.98


def _candidate_corroborated(
    candidate: Mapping[str, Any], *evidence_maps: Mapping[str, Any]
) -> bool:
    return bool(candidate) and all(
        any(field in evidence and _field_agrees(field, value, evidence[field]) for evidence in evidence_maps)
        for field, value in candidate.items()
    )


def _field_maps_agree(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return bool(left) and set(left) == set(right) and all(
        _field_agrees(field, left[field], right[field]) for field in left
    )


def _transcript_text(transcript: RegionTranscriptionResult) -> str:
    return str(transcript.transcript.get("transcriptionMarkdown") or "").strip()


def _target_heading_confirmed(
    decision: RegionRiskDecision, transcript: RegionTranscriptionResult
) -> bool:
    text = _transcript_text(transcript)
    if decision.kind == "solution":
        parsed = parse_solution_heading(text[:240])
        return bool(parsed and parsed.get("rawQuestionNumber") == decision.question_number)
    match = _QUESTION_HEADING_RE.match(text)
    return bool(match and int(match.group(1).translate(_DIGITS)) == decision.question_number)


def _strong_visual_required(transcript: RegionTranscriptionResult) -> bool:
    return bool(transcript.transcript.get("sourceVisualRequired")) and str(
        transcript.transcript.get("visualType") or "none"
    ).lower() in _STRONG_VISUAL_TYPES


def _grouped_visual_options_complete(question: Mapping[str, Any]) -> bool:
    contract = question.get("visualSourceContract")
    required = {
        str(value)
        for value in (contract.get("requiredAssetIds") if isinstance(contract, Mapping) else [])
        if str(value)
    }
    labels: set[str] = set()
    for raw in question.get("visuals") or []:
        if not isinstance(raw, Mapping) or str(raw.get("id") or "") not in required:
            continue
        if bool(raw.get("reviewOnly")):
            continue
        sanity = raw.get("sanity")
        if isinstance(sanity, Mapping) and str(sanity.get("status") or "") == "failed":
            continue
        if str(raw.get("visualMode") or "") != "grouped_options":
            continue
        labels.update(str(value).translate(_DIGITS) for value in raw.get("groupedOptionLabels") or [])
    return labels == {"1", "2", "3", "4"}


def _visual_only_question_verified(
    question: Mapping[str, Any], decision: RegionRiskDecision, transcript: RegionTranscriptionResult
) -> bool:
    if decision.kind != "question" or not _target_heading_confirmed(decision, transcript):
        return False
    if transcript.transcript.get("transcriptionUncertain") or not _strong_visual_required(transcript):
        return False
    options = [raw for raw in question.get("options") or [] if isinstance(raw, Mapping)]
    if {str(raw.get("label") or "").translate(_DIGITS) for raw in options} != {"1", "2", "3", "4"}:
        return False
    if any(str(raw.get("text_markdown") or "").strip() for raw in options):
        return False
    if not (_visual_evidence_complete(question, kind="question") and _grouped_visual_options_complete(question)):
        return False
    source = _QUESTION_HEADING_RE.sub("", _transcript_text(transcript), count=1).strip()
    candidate = str(question.get("question_text_markdown") or "")
    return numeric_signature(source) == numeric_signature(candidate) and text_similarity(source, candidate) >= 0.94


def _source_text_fields(fields: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(field): sanitize_source_markdown(value)[0]
        for field, value in fields.items()
        if str(field) != "correct_option_label"
    }


def _required_kinds(question: Mapping[str, Any]) -> frozenset[str]:
    kinds = {"question"}
    for raw in question.get("source_regions") or []:
        if not isinstance(raw, Mapping):
            continue
        value = str(raw.get("kind") or raw.get("role") or raw.get("record_type") or "").lower()
        if "solution" in value or "answer" in value:
            kinds.add("solution")
    if str(question.get("teacher_solution_markdown") or "").strip():
        kinds.add("solution")
    return frozenset(kinds)


def _visual_evidence_complete(question: Mapping[str, Any], *, kind: str) -> bool:
    contract = question.get("visualSourceContract")
    required_ids = {
        str(value)
        for value in (contract.get("requiredAssetIds") if isinstance(contract, Mapping) else [])
        if str(value)
    }
    if not required_ids:
        return False
    allowed_roles = {"question", "option"} if kind == "question" else {"solution"}
    for raw in question.get("visuals") or []:
        if not isinstance(raw, Mapping):
            continue
        if str(raw.get("id") or "") not in required_ids:
            continue
        if str(raw.get("role") or "").lower() not in allowed_roles:
            continue
        sanity = raw.get("sanity")
        if isinstance(sanity, Mapping) and str(sanity.get("status") or "") == "failed":
            continue
        if bool(raw.get("reviewOnly")):
            continue
        return True
    return False


def _payload_answer_label(payload: Mapping[str, Any] | None) -> str:
    if not isinstance(payload, Mapping):
        return ""
    label = str(payload.get("correct_option_label") or "").translate(
        str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
    ).strip()
    return label if label in {"1", "2", "3", "4"} else ""


def _answer_label_conflict(
    question: Mapping[str, Any],
    *,
    decision: RegionRiskDecision,
    payload: Mapping[str, Any] | None,
) -> bool:
    if decision.kind != "solution":
        return False
    observed = _payload_answer_label(payload)
    native = str(question.get("correct_option_label") or "").translate(
        str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
    ).strip()
    return bool(observed and observed != native)


def _apply_source_payload(
    question: Mapping[str, Any],
    *,
    decision: RegionRiskDecision,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    updated = dict(question)
    if decision.kind == "question":
        updated["question_text_markdown"] = sanitize_source_markdown(
            payload.get("question_text_markdown") or ""
        )[0]
        options: list[dict[str, Any]] = []
        for raw in payload.get("options") or []:
            if not isinstance(raw, Mapping):
                continue
            option = dict(raw)
            option["text_markdown"] = sanitize_source_markdown(
                option.get("text_markdown") or ""
            )[0]
            options.append(option)
        updated["options"] = options
    else:
        updated["teacher_solution_markdown"] = sanitize_source_markdown(
            payload.get("teacher_solution_markdown") or ""
        )[0]
    return updated


def _sanitize_question(question: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    updated = dict(question)
    flags: list[str] = []
    for field in ("question_text_markdown", "teacher_solution_markdown", "final_answer_markdown"):
        value, found = sanitize_source_markdown(updated.get(field) or "")
        updated[field] = value
        flags.extend(found)
    options: list[dict[str, Any]] = []
    for raw in updated.get("options") or []:
        if not isinstance(raw, Mapping):
            continue
        option = dict(raw)
        value, found = sanitize_source_markdown(option.get("text_markdown") or "")
        option["text_markdown"] = value
        flags.extend(found)
        options.append(option)
    updated["options"] = options
    return updated, list(dict.fromkeys(flags))


def _transcribe(
    *,
    decision: RegionRiskDecision,
    crop: bytes,
    model: str,
) -> RegionTranscriptionResult:
    return transcribe_source_region(
        image=crop,
        kind=decision.kind,
        question_number=decision.question_number,
        page_number=decision.page_number,
        model=model,
        thinking_minimal=model.startswith("gemini-"),
        timeout=_model_timeout(model),
        max_output_tokens=_max_output_tokens(),
    )


def _render_page_image(document: Any, page_number: int) -> Image.Image:
    if page_number < 1 or page_number > len(document):
        raise ValueError("Stage-5 source page is outside the PDF")
    page = document[page_number - 1]
    try:
        bitmap = page.render(scale=float(_crop_dpi()) / 72.0)
        try:
            return bitmap.to_pil().convert("RGB")
        finally:
            bitmap.close()
    finally:
        page.close()


def _crop_page_image(image: Image.Image, decision: RegionRiskDecision) -> bytes:
    pad = _crop_padding()
    x0, y0, x1, y1 = decision.bbox
    box = (
        max(0.0, x0 - pad),
        max(0.0, y0 - pad),
        min(1.0, x1 + pad),
        min(1.0, y1 + pad),
    )
    width, height = image.size
    left = max(0, min(width - 1, int(math.floor(box[0] * width))))
    top = max(0, min(height - 1, int(math.floor(box[1] * height))))
    right = max(left + 1, min(width, int(math.ceil(box[2] * width))))
    bottom = max(top + 1, min(height, int(math.ceil(box[3] * height))))
    crop = image.crop((left, top, right, bottom)).convert("RGB")
    try:
        maximum = _max_crop_dimension()
        if max(crop.size) > maximum:
            ratio = maximum / max(crop.size)
            resized = crop.resize(
                (max(1, round(crop.width * ratio)), max(1, round(crop.height * ratio))),
                Image.Resampling.LANCZOS,
            )
            crop.close()
            crop = resized
        output = io.BytesIO()
        crop.save(output, format="PNG", optimize=True)
        return output.getvalue()
    finally:
        crop.close()


def _render_crops(
    pdf_data: bytes,
    indexed_decisions: Sequence[tuple[int, RegionRiskDecision]],
    *,
    should_cancel=None,
    deadline_at: float | None = None,
) -> dict[int, bytes | Exception]:
    if not indexed_decisions:
        return {}
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pypdfium2 is required for Stage-5 source crops") from exc

    grouped: dict[int, list[tuple[int, RegionRiskDecision]]] = defaultdict(list)
    for index, decision in indexed_decisions:
        grouped[decision.page_number].append((index, decision))

    outcomes: dict[int, bytes | Exception] = {}
    document = pdfium.PdfDocument(pdf_data)
    try:
        for page_number in sorted(grouped):
            if should_cancel is not None and should_cancel():
                raise RuntimeError("Cancellation requested during Stage-5 finalization.")
            page_items = grouped[page_number]
            if deadline_at is not None and monotonic() >= deadline_at:
                for index, _decision in page_items:
                    outcomes[index] = _Stage5DeadlineExceeded()
                continue
            try:
                image = _render_page_image(document, page_number)
            except Exception as exc:
                for index, _decision in page_items:
                    outcomes[index] = exc
                continue
            try:
                for index, decision in page_items:
                    try:
                        outcomes[index] = _crop_page_image(image, decision)
                    except Exception as exc:
                        outcomes[index] = exc
            finally:
                image.close()
    finally:
        document.close()
    return outcomes


def _transcribe_many(
    items: Sequence[tuple[int, RegionRiskDecision, bytes]],
    *,
    model: str,
    should_cancel=None,
    deadline_at: float | None = None,
    budget: Stage5BudgetLedger | None = None,
    on_progress=None,
) -> dict[int, RegionTranscriptionResult | Exception]:
    ordered_items = list(items)
    if not ordered_items:
        return {}
    if should_cancel is not None and should_cancel():
        raise RuntimeError("Cancellation requested during Stage-5 finalization.")
    if deadline_at is not None and monotonic() >= deadline_at:
        return {index: _Stage5DeadlineExceeded() for index, _decision, _crop in ordered_items}

    current_user = get_current_user()
    current_session_id = get_current_session_id()

    def run_one(item: tuple[int, RegionRiskDecision, bytes]):
        index, decision, crop = item
        close_old_connections()
        try:
            with llm_tracking_context(user=current_user, session_id=current_session_id):
                try:
                    value: RegionTranscriptionResult | Exception = _transcribe(
                        decision=decision,
                        crop=crop,
                        model=model,
                    )
                except Exception as exc:
                    value = exc
            return index, value
        finally:
            close_old_connections()

    outcomes: dict[int, RegionTranscriptionResult | Exception] = {}
    pending: dict[Future, tuple[int, Any]] = {}
    workers = min(_max_concurrency(), len(ordered_items))
    executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="exam-stage5")
    next_position = 0
    deadline_hit = False
    budget_hit = False

    def fill_window() -> None:
        nonlocal next_position, deadline_hit, budget_hit
        while len(pending) < workers:
            if should_cancel is not None and should_cancel():
                raise RuntimeError("Cancellation requested during Stage-5 finalization.")
            if deadline_at is not None and monotonic() >= deadline_at:
                deadline_hit = True
                return
            if next_position >= len(ordered_items):
                return
            item = ordered_items[next_position]
            reservation = budget.reserve(model) if budget is not None else None
            if budget is not None and reservation is None:
                if pending:
                    return
                budget_hit = True
                remaining = ordered_items[next_position:]
                budget.record_blocked(len(remaining))
                for index, _decision, _crop in remaining:
                    outcomes[index] = Stage5CostBudgetExceeded()
                next_position = len(ordered_items)
                return
            next_position += 1
            try:
                future = executor.submit(run_one, item)
            except Exception:
                if budget is not None and reservation is not None:
                    budget.release(reservation)
                raise
            pending[future] = (item[0], reservation)

    try:
        fill_window()
        while pending:
            completed, _not_done = wait(pending, timeout=1.0, return_when=FIRST_COMPLETED)
            if should_cancel is not None and should_cancel():
                raise RuntimeError("Cancellation requested during Stage-5 finalization.")
            if deadline_at is not None and monotonic() >= deadline_at:
                deadline_hit = True
            for future in completed:
                _pending_index, reservation = pending.pop(future)
                index, value = future.result()
                if budget is not None and reservation is not None:
                    budget.settle(reservation, value)
                outcomes[index] = value
                if on_progress is not None:
                    # Best-effort heartbeat: a progress-sink failure must never
                    # abort the paid fan-out or leak a partial-run exception.
                    try:
                        on_progress(len(outcomes), len(ordered_items))
                    except Exception:
                        pass
            if not deadline_hit and not budget_hit:
                fill_window()
    except Exception:
        for future in pending:
            future.cancel()
        executor.shutdown(wait=True, cancel_futures=True)
        raise
    else:
        executor.shutdown(wait=True)

    return {
        index: outcomes.get(index, _Stage5DeadlineExceeded())
        for index, _decision, _crop in ordered_items
    }


def _retry_format_failures_once(
    items: Sequence[tuple[int, RegionRiskDecision, bytes]],
    outcomes: Mapping[int, RegionTranscriptionResult | Exception],
    *,
    model: str,
    call_limit: int,
    calls_so_far: int,
    should_cancel=None,
    deadline_at: float | None = None,
    budget: Stage5BudgetLedger | None = None,
) -> tuple[dict[int, RegionTranscriptionResult | Exception], int, set[int]]:
    headroom = max(0, int(call_limit) - int(calls_so_far))
    retry_items = [
        item for item in items if isinstance(outcomes.get(item[0]), _FORMAT_RETRY_FAILURES)
    ][:headroom]
    if not retry_items:
        return dict(outcomes), 0, set()
    retry_outcomes = _transcribe_many(
        retry_items,
        model=model,
        should_cancel=should_cancel,
        deadline_at=deadline_at,
        budget=budget,
    )
    retry_calls = sum(
        not isinstance(value, (_Stage5DeadlineExceeded, Stage5CostBudgetExceeded))
        for value in retry_outcomes.values()
    )
    merged = dict(outcomes)
    merged.update(retry_outcomes)
    return merged, retry_calls, {index for index, _decision, _crop in retry_items}


def _bounded_recheck(
    items: Sequence[tuple[int, RegionRiskDecision, bytes]],
    *,
    model: str,
    call_limit: int,
    calls_so_far: int,
    should_cancel=None,
    deadline_at: float | None = None,
    budget: Stage5BudgetLedger | None = None,
) -> tuple[dict[int, RegionTranscriptionResult | Exception], int]:
    headroom = max(0, int(call_limit) - int(calls_so_far))
    selected = list(items)[:headroom]
    if not selected:
        return {}, 0
    outcomes = _transcribe_many(
        selected,
        model=model,
        should_cancel=should_cancel,
        deadline_at=deadline_at,
        budget=budget,
    )
    calls = sum(
        not isinstance(value, (_Stage5DeadlineExceeded, Stage5CostBudgetExceeded))
        for value in outcomes.values()
    )
    return outcomes, calls


def finalize_stage5_regions(
    result: PageAssemblyResult,
    *,
    pdf_data: bytes,
    decisions: Sequence[RegionRiskDecision],
    should_cancel=None,
    required_targets: set[tuple[int, str]] | frozenset[tuple[int, str]] | None = None,
    max_cost_usd: Decimal | float | str | None = None,
    on_region_complete=None,
) -> tuple[PageAssemblyResult, dict[str, Any]]:
    started_at = monotonic()
    max_wall_seconds = _max_wall_seconds()
    deadline_at = started_at + max_wall_seconds
    task_deadline_at = current_stage5_task_deadline()
    if task_deadline_at is not None:
        deadline_at = min(deadline_at, task_deadline_at)
    questions = _question_map(result)
    primary_name = primary_model()
    main_name = main_model()
    tie_name = tiebreaker_model()
    if not primary_name or not main_name or primary_name == main_name:
        raise ValueError("Stage-5 primary and main models must be distinct and non-empty.")
    cost_ledger = (
        Stage5BudgetLedger(max_cost_usd=max_cost_usd, max_output_tokens=_max_output_tokens())
        if max_cost_usd is not None
        else None
    )

    target_filter: frozenset[tuple[int, str]] | None = None
    if required_targets is not None:
        normalized_targets = {
            (int(number), str(kind).strip().lower())
            for number, kind in required_targets
        }
        if not normalized_targets or any(
            number < 1 or kind not in {"question", "solution"}
            for number, kind in normalized_targets
        ):
            raise ValueError("Stage-5 targeted evaluation requires valid region targets.")
        target_filter = frozenset(normalized_targets)
        decisions = [
            decision
            for decision in decisions
            if (decision.question_number, decision.kind) in target_filter
        ]

    primary_limit = _primary_cap()
    main_limit = _main_cap()
    preflight_exceeded = len(decisions) > primary_limit
    primary_calls = main_calls = tiebreaker_calls = verified = repaired = 0
    primary_format_retries = main_format_retries = 0
    primary_degraded_rechecks = main_disagreement_rechecks = 0
    successful_input_tokens = successful_output_tokens = successful_total_tokens = 0

    decision_counts: dict[tuple[int, str], int] = {}
    for decision in decisions:
        key = (decision.question_number, decision.kind)
        decision_counts[key] = decision_counts.get(key, 0) + 1

    rows: list[dict[str, Any]] = []
    missing_regions = 0
    required_by_question: dict[int, set[str]] = {}
    if target_filter is None:
        required_by_question = {
            number: set(_required_kinds(question)) for number, question in questions.items()
        }
    else:
        for number, kind in target_filter:
            required_by_question.setdefault(number, set()).add(kind)
    for number, kinds in sorted(required_by_question.items()):
        for kind in sorted(kinds):
            if decision_counts.get((number, kind), 0) == 0:
                rows.append(
                    {
                        "targetId": f"missing-{kind}-{number}",
                        "questionNumber": number,
                        "kind": kind,
                        "status": "blocked_missing_region",
                    }
                )
                missing_regions += 1

    eligible: list[tuple[int, RegionRiskDecision, dict[str, Any], dict[str, Any]]] = []
    for index, decision in enumerate(decisions):
        if should_cancel is not None and should_cancel():
            raise RuntimeError("Cancellation requested during Stage-5 finalization.")
        row = {**decision.safe_dict(), "status": "pending"}
        rows.append(row)
        if preflight_exceeded:
            row["status"] = "blocked_primary_cost_cap"
            continue
        if decision_counts.get((decision.question_number, decision.kind), 0) > 1:
            row["status"] = "blocked_duplicate_region"
            continue
        question = questions.get(decision.question_number)
        if question is None:
            row["status"] = "blocked_missing_question"
            continue
        eligible.append((index, decision, question, row))

    states: dict[int, dict[str, Any]] = {}
    primary_items: list[tuple[int, RegionRiskDecision, bytes]] = []
    if eligible:
        crop_outcomes = _render_crops(
            pdf_data,
            [(index, decision) for index, decision, _question, _row in eligible],
            should_cancel=should_cancel,
            deadline_at=deadline_at,
        )
        for index, decision, question, row in eligible:
            crop_value = crop_outcomes.get(index)
            if isinstance(crop_value, Exception) or not isinstance(crop_value, bytes):
                row["status"] = (
                    "blocked_stage5_deadline"
                    if isinstance(crop_value, _Stage5DeadlineExceeded)
                    else "blocked_crop_failed"
                )
                row["reason"] = type(crop_value).__name__
                continue
            candidate = _source_text_fields(candidate_fields(question, kind=decision.kind))
            states[index] = {
                "decision": decision,
                "question": question,
                "row": row,
                "crop": crop_value,
                "candidate": candidate,
                "primaryPayload": None,
                "primaryFields": {},
                "primaryLabelConflict": False,
            }
            primary_items.append((index, decision, crop_value))

    primary_outcomes = _transcribe_many(
        primary_items,
        model=primary_name,
        should_cancel=should_cancel,
        deadline_at=deadline_at,
        budget=cost_ledger,
        on_progress=on_region_complete,
    )
    primary_calls = sum(
        not isinstance(value, (_Stage5DeadlineExceeded, Stage5CostBudgetExceeded))
        for value in primary_outcomes.values()
    )
    primary_outcomes, primary_format_retries, primary_retry_indexes = _retry_format_failures_once(
        primary_items,
        primary_outcomes,
        model=primary_name,
        call_limit=primary_limit,
        calls_so_far=primary_calls,
        should_cancel=should_cancel,
        deadline_at=deadline_at,
        budget=cost_ledger,
    )
    primary_calls += primary_format_retries
    for index in primary_retry_indexes:
        if index in states:
            states[index]["row"]["primaryFormatRetry"] = True

    main_candidates: list[tuple[int, RegionRiskDecision, bytes]] = []
    for index, decision, crop in primary_items:
        state = states[index]
        question = state["question"]
        row = state["row"]
        primary_value = primary_outcomes[index]
        if isinstance(primary_value, Exception):
            if isinstance(primary_value, _Stage5DeadlineExceeded):
                row["status"] = "blocked_stage5_deadline"
                continue
            if isinstance(primary_value, Stage5CostBudgetExceeded):
                row["status"] = "blocked_stage5_cost_budget"
                continue
            row["primaryFailure"] = type(primary_value).__name__
            main_candidates.append((index, decision, crop))
            continue

        primary = primary_value
        row["primary"] = primary.safe_dict()
        successful_input_tokens += primary.input_tokens
        successful_output_tokens += primary.output_tokens
        successful_total_tokens += primary.total_tokens
        primary_target_confirmed = _target_heading_confirmed(decision, primary)
        row["primaryTargetConfirmed"] = primary_target_confirmed
        primary_visual_missing = _strong_visual_required(primary) and not _visual_evidence_complete(
            question, kind=decision.kind
        )

        if _visual_only_question_verified(question, decision, primary):
            row["status"] = "verified_visual_source"
            row["resolutionTargetConfirmed"] = True
            verified += 1
            continue

        primary_payload = _proposal(decision, primary) if primary_target_confirmed else None
        if not primary_target_confirmed:
            row["primaryFailure"] = "target_heading_mismatch"
        elif primary_visual_missing:
            row["primaryFailure"] = "visual_evidence_missing"
        primary_fields = (
            _source_text_fields(payload_fields(primary_payload, kind=decision.kind))
            if primary_payload is not None
            else {}
        )
        primary_label_conflict = _answer_label_conflict(
            question, decision=decision, payload=primary_payload
        )
        state["primaryPayload"] = primary_payload
        state["primaryFields"] = primary_fields
        state["primaryLabelConflict"] = primary_label_conflict
        state["primaryVisualMissing"] = primary_visual_missing
        if primary_payload is not None:
            similarity, numeric_same = _agreement(
                _proposal_text(decision, primary_payload), decision.candidate_text
            )
            row["candidateSimilarity"] = similarity
            row["numericAgreement"] = numeric_same
        if (
            primary_payload is not None
            and not primary_visual_missing
            and _candidate_corroborated(state["candidate"], primary_fields)
            and not primary_label_conflict
        ):
            row["status"] = "verified_source"
            row["resolutionTargetConfirmed"] = True
            verified += 1
            continue
        main_candidates.append((index, decision, crop))

    selected_main = main_candidates[:main_limit]
    for index, _decision, _crop in main_candidates[main_limit:]:
        states[index]["row"]["status"] = "blocked_main_cost_cap"

    main_outcomes = _transcribe_many(
        selected_main,
        model=main_name,
        should_cancel=should_cancel,
        deadline_at=deadline_at,
        budget=cost_ledger,
    )
    main_calls = sum(
        not isinstance(value, (_Stage5DeadlineExceeded, Stage5CostBudgetExceeded))
        for value in main_outcomes.values()
    )
    main_outcomes, main_format_retries, main_retry_indexes = _retry_format_failures_once(
        selected_main,
        main_outcomes,
        model=main_name,
        call_limit=main_limit,
        calls_so_far=main_calls,
        should_cancel=should_cancel,
        deadline_at=deadline_at,
        budget=cost_ledger,
    )
    main_calls += main_format_retries
    for index in main_retry_indexes:
        if index in states:
            states[index]["row"]["mainFormatRetry"] = True

    for index, decision, _crop in selected_main:
        state = states[index]
        question = state["question"]
        row = state["row"]
        main_value = main_outcomes[index]
        main_payload: Mapping[str, Any] | None = None
        main_fields: dict[str, Any] = {}
        if isinstance(main_value, Exception):
            if isinstance(main_value, _Stage5DeadlineExceeded):
                row["status"] = "blocked_stage5_deadline"
                continue
            if isinstance(main_value, Stage5CostBudgetExceeded):
                row["status"] = "blocked_stage5_cost_budget"
                continue
            row["mainFailure"] = type(main_value).__name__
        else:
            main = main_value
            row["main"] = main.safe_dict()
            successful_input_tokens += main.input_tokens
            successful_output_tokens += main.output_tokens
            successful_total_tokens += main.total_tokens
            main_target_confirmed = _target_heading_confirmed(decision, main)
            row["mainTargetConfirmed"] = main_target_confirmed
            if _visual_only_question_verified(question, decision, main):
                row["status"] = "verified_visual_source_main"
                row["resolutionTargetConfirmed"] = True
                verified += 1
                continue
            main_visual_missing = _strong_visual_required(main) and not _visual_evidence_complete(
                question, kind=decision.kind
            )
            main_payload = _proposal(decision, main) if main_target_confirmed else None
            if not main_target_confirmed:
                row["mainFailure"] = "target_heading_mismatch"
            elif main_visual_missing:
                row["mainFailure"] = "visual_evidence_missing"
                main_payload = None
            if main_payload is not None:
                main_fields = _source_text_fields(payload_fields(main_payload, kind=decision.kind))
            else:
                row["mainFailure"] = "uncertain_or_invalid"

        main_label_conflict = _answer_label_conflict(
            question, decision=decision, payload=main_payload
        )
        state["mainPayload"] = main_payload
        state["mainFields"] = main_fields
        state["mainLabelConflict"] = main_label_conflict

        if (
            main_payload is not None
            and _candidate_corroborated(state["candidate"], main_fields)
            and not main_label_conflict
        ):
            row["status"] = "verified_source_main"
            row["resolutionTargetConfirmed"] = True
            verified += 1
            continue
        if (
            main_payload is not None
            and _candidate_corroborated(state["candidate"], state["primaryFields"], main_fields)
            and not main_label_conflict
            and not state["primaryLabelConflict"]
        ):
            row["status"] = "verified_source_consensus" if state["primaryFields"] else "verified_source_main"
            row["resolutionTargetConfirmed"] = True
            verified += 1
            continue
        if (
            state["primaryPayload"] is not None
            and main_payload is not None
            and _field_maps_agree(state["primaryFields"], main_fields)
        ):
            if state["primaryLabelConflict"] or main_label_conflict:
                row["status"] = "blocked_answer_label_conflict"
                continue
            current_question = questions.get(decision.question_number, question)
            questions[decision.question_number] = _apply_source_payload(
                current_question, decision=decision, payload=main_payload
            )
            row["status"] = "repaired_source"
            row["resolutionTargetConfirmed"] = True
            verified += 1
            repaired += 1
            continue

        if state.get("primaryVisualMissing") and main_payload is None:
            row["status"] = "blocked_visual_evidence_missing"
        else:
            row["status"] = "blocked_model_disagreement" if main_payload is not None else "blocked_main_failed"

    degraded_items = [
        (index, decision, crop)
        for index, decision, crop in selected_main
        if states[index]["row"].get("status") == "blocked_main_failed"
        and isinstance(main_outcomes.get(index), RegionTranscriptionNonconformingContent)
        and states[index].get("primaryPayload") is not None
        and not states[index].get("primaryVisualMissing")
        and not states[index].get("primaryLabelConflict")
    ]
    degraded_outcomes, degraded_calls = _bounded_recheck(
        degraded_items,
        model=primary_name,
        call_limit=primary_limit,
        calls_so_far=primary_calls,
        should_cancel=should_cancel,
        deadline_at=deadline_at,
        budget=cost_ledger,
    )
    primary_calls += degraded_calls
    primary_degraded_rechecks += degraded_calls
    for index, decision, _crop in degraded_items:
        if index not in degraded_outcomes:
            continue
        state = states[index]
        row = state["row"]
        question = state["question"]
        row["primaryDegradedRecheck"] = True
        value = degraded_outcomes[index]
        if isinstance(value, Exception):
            row["primaryDegradedRecheckFailure"] = type(value).__name__
            continue
        successful_input_tokens += value.input_tokens
        successful_output_tokens += value.output_tokens
        successful_total_tokens += value.total_tokens
        row["primaryDegradedRecheckEvidence"] = value.safe_dict()
        if not _target_heading_confirmed(decision, value):
            row["primaryDegradedRecheckFailure"] = "target_heading_mismatch"
            continue
        if _strong_visual_required(value) and not _visual_evidence_complete(question, kind=decision.kind):
            row["primaryDegradedRecheckFailure"] = "visual_evidence_missing"
            continue
        payload = _proposal(decision, value)
        if payload is None:
            row["primaryDegradedRecheckFailure"] = "uncertain_or_invalid"
            continue
        fields = _source_text_fields(payload_fields(payload, kind=decision.kind))
        label_conflict = _answer_label_conflict(question, decision=decision, payload=payload)
        if label_conflict or not _field_maps_agree(state["primaryFields"], fields):
            row["primaryDegradedRecheckFailure"] = "primary_recheck_disagreement"
            continue
        if _candidate_corroborated(state["candidate"], state["primaryFields"], fields):
            row["status"] = "verified_source_primary_recheck"
        else:
            current_question = questions.get(decision.question_number, question)
            questions[decision.question_number] = _apply_source_payload(
                current_question, decision=decision, payload=payload
            )
            row["status"] = "repaired_source_primary_recheck"
            repaired += 1
        row["resolutionTargetConfirmed"] = True
        verified += 1

    disagreement_items = [
        (index, decision, crop)
        for index, decision, crop in selected_main
        if states[index]["row"].get("status") == "blocked_model_disagreement"
        and states[index].get("primaryPayload") is not None
        and not states[index].get("primaryVisualMissing")
        and not states[index].get("primaryLabelConflict")
    ]
    disagreement_outcomes, disagreement_calls = _bounded_recheck(
        disagreement_items,
        model=main_name,
        call_limit=main_limit,
        calls_so_far=main_calls,
        should_cancel=should_cancel,
        deadline_at=deadline_at,
        budget=cost_ledger,
    )
    main_calls += disagreement_calls
    main_disagreement_rechecks += disagreement_calls
    for index, decision, _crop in disagreement_items:
        if index not in disagreement_outcomes:
            continue
        state = states[index]
        row = state["row"]
        question = state["question"]
        row["mainDisagreementRecheck"] = True
        value = disagreement_outcomes[index]
        if isinstance(value, Exception):
            row["mainDisagreementRecheckFailure"] = type(value).__name__
            continue
        successful_input_tokens += value.input_tokens
        successful_output_tokens += value.output_tokens
        successful_total_tokens += value.total_tokens
        row["mainDisagreementRecheckEvidence"] = value.safe_dict()
        if not _target_heading_confirmed(decision, value):
            row["mainDisagreementRecheckFailure"] = "target_heading_mismatch"
            continue
        if _strong_visual_required(value) and not _visual_evidence_complete(question, kind=decision.kind):
            row["mainDisagreementRecheckFailure"] = "visual_evidence_missing"
            continue
        payload = _proposal(decision, value)
        if payload is None:
            row["mainDisagreementRecheckFailure"] = "uncertain_or_invalid"
            continue
        fields = _source_text_fields(payload_fields(payload, kind=decision.kind))
        label_conflict = _answer_label_conflict(question, decision=decision, payload=payload)
        if label_conflict or not _field_maps_agree(state["primaryFields"], fields):
            row["mainDisagreementRecheckFailure"] = "still_disagrees"
            continue
        current_question = questions.get(decision.question_number, question)
        questions[decision.question_number] = _apply_source_payload(
            current_question, decision=decision, payload=payload
        )
        row["status"] = "repaired_source_main_recheck"
        row["resolutionTargetConfirmed"] = True
        verified += 1
        repaired += 1

    if cost_ledger is not None and cost_ledger.charged > cost_ledger.cap:
        for row in rows:
            if not str(row.get("status") or "").startswith("blocked_"):
                row["preBudgetStatus"] = row.get("status")
                row["status"] = "blocked_stage5_cost_budget"
                row["reason"] = "reservation_underestimated"

    blocked = sum(str(row.get("status") or "").startswith("blocked_") for row in rows)
    blocked_questions = {
        int(row.get("questionNumber") or 0)
        for row in rows
        if str(row.get("status") or "").startswith("blocked_")
    }
    projection = dict(result.projection)
    exam = dict(projection.get("exam_prep") or {})
    ordered: list[dict[str, Any]] = []
    sanitized_questions = 0
    for raw in exam.get("questions") or []:
        if not isinstance(raw, Mapping):
            continue
        number = _question_number(raw.get("source_question_number"))
        if target_filter is not None and number not in required_by_question:
            ordered.append(dict(raw))
            continue
        question = dict(questions.get(number, raw))
        issues = [str(code) for code in (question.get("issues") or []) if str(code)]
        if number in blocked_questions:
            if _STAGE5_BLOCKER not in issues:
                issues.append(_STAGE5_BLOCKER)
        else:
            issues = [code for code in issues if code != _STAGE5_BLOCKER]
        question["issues"] = issues
        question["stage5_finalization"] = {
            "regions": [row for row in rows if int(row.get("questionNumber") or 0) == number],
            "blocked": number in blocked_questions,
        }
        question, sanitizer_flags = _sanitize_question(question)
        if sanitizer_flags:
            sanitized_questions += 1
            question["stage5_finalization"]["finalSanitizerFlags"] = sanitizer_flags
        ordered.append(question)
    exam["questions"] = ordered
    projection["exam_prep"] = exam
    updated = result.model_copy(update={"projection": projection})
    updated = rebuild_assembly_quality(updated)
    grouped_numbers = {
        _question_number(question.get("source_question_number"))
        for question in ordered
        if _grouped_visual_options_complete(question)
    }
    if grouped_numbers:
        exam = dict(updated.projection.get("exam_prep") or {})
        cleaned_questions: list[dict[str, Any]] = []
        stale = {"missing_options", "missing_option_text", "missing_options_text"}
        for raw in exam.get("questions") or []:
            question = dict(raw)
            if _question_number(question.get("source_question_number")) in grouped_numbers:
                question["issues"] = [code for code in question.get("issues") or [] if str(code) not in stale]
            cleaned_questions.append(question)
        exam["questions"] = cleaned_questions
        projection = dict(updated.projection)
        projection["exam_prep"] = exam
        remaining_issues = [
            issue for issue in updated.issues
            if not (issue.question_number in grouped_numbers and issue.code in stale)
        ]
        updated = updated.model_copy(
            update={
                "projection": projection,
                "issues": remaining_issues,
                "questions_needing_review": sum(bool(question.get("issues")) for question in cleaned_questions),
                "publication_ready": bool(cleaned_questions)
                and not any(is_review_blocking_issue(issue.code) for issue in remaining_issues)
                and not any(
                    is_review_blocking_issue(code)
                    for question in cleaned_questions
                    for code in question.get("issues") or []
                ),
            }
        )

    elapsed_seconds = max(0.0, monotonic() - started_at)
    deadline_blocked = sum(
        str(row.get("status") or "") == "blocked_stage5_deadline" for row in rows
    )
    audit = {
        "schemaVersion": 1,
        "policy": {
            "candidateMistralShown": False,
            "oneRegionOneImageOneCall": False,
            "oneRegionOneImagePerAttempt": True,
            "maxFormatRetriesPerRegion": 1,
            "maxPrimaryDegradedRechecksPerRegion": 1,
            "maxMainDisagreementRechecksPerRegion": 1,
            "degradedProviderAcceptanceRequiresRepeatFieldAgreement": True,
            "disagreementRecheckAcceptanceRequiresCrossModelFieldAgreement": True,
            "formatRetryFailureTypes": [
                "RegionTranscriptionEmptyContent",
                "RegionTranscriptionNonconformingContent",
            ],
            "allRegionsReceivePrimary": target_filter is None,
            "targetedEvaluation": target_filter is not None,
            "primaryModel": primary_name,
            "primaryThinking": "provider_default",
            "mainModel": main_name,
            "mainThinking": "minimal",
            "tiebreakerModel": tie_name,
            "visualEvidenceMutableByVerifier": False,
            "nativeAnswerMutableByVerifier": False,
            "globalFinalSanitizer": True,
            "providerIoConcurrency": _max_concurrency(),
        },
        "stats": {
            "regions": len(decisions),
            "missingRegions": missing_regions,
            "primaryCalls": primary_calls,
            "mainCalls": main_calls,
            "primaryFormatRetries": primary_format_retries,
            "mainFormatRetries": main_format_retries,
            "formatRetries": primary_format_retries + main_format_retries,
            "primaryDegradedRechecks": primary_degraded_rechecks,
            "mainDisagreementRechecks": main_disagreement_rechecks,
            "tiebreakerCalls": tiebreaker_calls,
            "verified": verified,
            "repaired": repaired,
            "blocked": blocked,
            "successfulInputTokens": successful_input_tokens,
            "successfulOutputTokens": successful_output_tokens,
            "successfulTotalTokens": successful_total_tokens,
            "finalSanitizerQuestionCount": sanitized_questions,
        },
        "budget": {
            "primaryCap": primary_limit,
            "mainCap": main_limit,
            "maxOutputTokensPerCall": _max_output_tokens(),
            "primaryTimeoutSeconds": _model_timeout(primary_name),
            "mainTimeoutSeconds": _model_timeout(main_name),
            "preflightExceeded": preflight_exceeded,
            "maxConcurrency": _max_concurrency(),
            "maxWallSeconds": max_wall_seconds,
            "effectiveMaxWallSeconds": round(max(0.0, deadline_at - started_at), 3),
            "taskDeadlineApplied": task_deadline_at is not None,
            "elapsedSeconds": round(elapsed_seconds, 3),
            "deadlineExceeded": deadline_blocked > 0,
            **(cost_ledger.safe_dict() if cost_ledger is not None else {"costCapEnabled": False}),
        },
        "regions": rows,
    }
    return updated, audit


__all__ = [
    "DEFAULT_MAIN_MODEL",
    "DEFAULT_PRIMARY_MODEL",
    "DEFAULT_TIEBREAKER_MODEL",
    "finalize_stage5_regions",
    "main_model",
    "primary_model",
    "tiebreaker_model",
]
