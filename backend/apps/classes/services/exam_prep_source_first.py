"""Source-first ingestion primitives for Persian exam PDFs.

The PDF page (and every crop derived from its coordinates) is the authority.
AvalAI/Mistral OCR 4 is used here only as a bounded geometry and text-evidence
provider.  This module deliberately does not turn OCR confidence into a truth
score and does not silently overwrite source evidence.

The live runner is resumable at the physical-PDF-chunk boundary.  A 55-page
document is normally sent as two requests (30 + 25 pages) under the current
AvalAI route limit.  Transport retries are opt-in and are limited to statuses
documented as transient by the provider; malformed requests and credential
errors fail without spending another request.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import os
from pathlib import Path
import random
import tempfile
import time
from typing import Any, Callable, Mapping, MutableMapping, Sequence

from pypdf import PdfReader, PdfWriter

from apps.classes.services.exam_prep_avalai_ocr_errors import (
    classify_avalai_ocr_failure,
)
from apps.classes.services.exam_prep_mistral_layout_analysis import (
    analyze_ocr_document,
)
from apps.classes.services.exam_prep_mistral_solution_headings import (
    audit_solution_headings,
)
from apps.classes.services.exam_prep_v4_avalai_ocr import (
    AVALAI_OCR_ENDPOINT,
    AVALAI_OCR_PINNED_MODEL,
    AvalAIOCRLimits,
    AvalAIOCRResult,
    OCRHTTPResponse,
    parse_ocr_response,
    build_ocr_payload,
)


OCR4_HARD_MAX_PAGES = 30
OCR4_DEFAULT_CHUNK_BYTES = 28 * 1024 * 1024
OCR4_DEFAULT_RESPONSE_BYTES = 120 * 1024 * 1024
OCR4_PAGE_PRICE_UNIT = Decimal("0.004")
# AvalAI's documented retry guidance covers rate limiting, gateway/server
# failures and timeouts.  Keep this allow-list narrower than generic HTTP
# folklore so a conflict/early-data response cannot silently create a paid
# duplicate request.
_RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})


class SourceFirstError(RuntimeError):
    """Base error for source-first OCR preparation."""


class SourceFirstConfigurationError(SourceFirstError):
    """The local input or request contract is invalid."""


class SourceFirstProviderError(SourceFirstError):
    """An OCR provider failure with content-free retry metadata."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retryable: bool = False,
        attempts: int = 1,
        classification: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retryable = bool(retryable)
        self.attempts = int(attempts)
        self.classification = dict(classification or {})


class SourceFirstCoverageError(SourceFirstError):
    """OCR returned missing or duplicate physical pages."""


@dataclass(frozen=True, slots=True)
class SourceFirstOCRConfig:
    model: str = AVALAI_OCR_PINNED_MODEL
    endpoint: str = AVALAI_OCR_ENDPOINT
    max_pages_per_request: int = OCR4_HARD_MAX_PAGES
    max_chunk_bytes: int = OCR4_DEFAULT_CHUNK_BYTES
    max_response_bytes: int = OCR4_DEFAULT_RESPONSE_BYTES
    timeout_seconds: float = 600.0
    max_attempts: int = 1
    retry_backoff_seconds: float = 2.0
    retry_jitter_seconds: float = 0.5
    word_confidence: bool = True

    @classmethod
    def from_env(cls) -> "SourceFirstOCRConfig":
        def integer(name: str, default: int) -> int:
            try:
                return int(os.getenv(name, str(default)))
            except (TypeError, ValueError):
                return default

        def number(name: str, default: float) -> float:
            try:
                return float(os.getenv(name, str(default)))
            except (TypeError, ValueError):
                return default

        raw_word = (os.getenv("EXAM_PREP_SOURCE_FIRST_WORD_CONFIDENCE", "1") or "1")
        return cls(
            model=(os.getenv("EXAM_PREP_SOURCE_FIRST_MODEL") or AVALAI_OCR_PINNED_MODEL).strip(),
            endpoint=(os.getenv("AVALAI_OCR_ENDPOINT") or AVALAI_OCR_ENDPOINT).strip(),
            max_pages_per_request=integer(
                "EXAM_PREP_SOURCE_FIRST_MAX_PAGES_PER_REQUEST",
                OCR4_HARD_MAX_PAGES,
            ),
            max_chunk_bytes=integer(
                "EXAM_PREP_SOURCE_FIRST_MAX_CHUNK_BYTES",
                OCR4_DEFAULT_CHUNK_BYTES,
            ),
            max_response_bytes=integer(
                "EXAM_PREP_SOURCE_FIRST_MAX_RESPONSE_BYTES",
                OCR4_DEFAULT_RESPONSE_BYTES,
            ),
            timeout_seconds=number("EXAM_PREP_SOURCE_FIRST_TIMEOUT_SECONDS", 600.0),
            max_attempts=integer("EXAM_PREP_SOURCE_FIRST_MAX_ATTEMPTS", 1),
            retry_backoff_seconds=number(
                "EXAM_PREP_SOURCE_FIRST_RETRY_BACKOFF_SECONDS",
                2.0,
            ),
            retry_jitter_seconds=number(
                "EXAM_PREP_SOURCE_FIRST_RETRY_JITTER_SECONDS",
                0.5,
            ),
            word_confidence=raw_word.strip().lower() in {"1", "true", "yes", "on"},
        )

    def validate(self) -> None:
        if not self.model:
            raise SourceFirstConfigurationError("An explicit OCR4 model is required.")
        if not self.endpoint.startswith(("https://", "http://")):
            raise SourceFirstConfigurationError("OCR4 endpoint must be an HTTP(S) URL.")
        if not 1 <= int(self.max_pages_per_request) <= OCR4_HARD_MAX_PAGES:
            raise SourceFirstConfigurationError(
                f"max_pages_per_request must be between 1 and {OCR4_HARD_MAX_PAGES}."
            )
        if int(self.max_chunk_bytes) < 1:
            raise SourceFirstConfigurationError("max_chunk_bytes must be positive.")
        if int(self.max_response_bytes) < 1:
            raise SourceFirstConfigurationError("max_response_bytes must be positive.")
        if float(self.timeout_seconds) < 1:
            raise SourceFirstConfigurationError("timeout_seconds must be at least one second.")
        if not 1 <= int(self.max_attempts) <= 3:
            raise SourceFirstConfigurationError("max_attempts must be between 1 and 3.")
        if float(self.retry_backoff_seconds) < 0 or float(self.retry_jitter_seconds) < 0:
            raise SourceFirstConfigurationError("Retry delays may not be negative.")

    @property
    def contract_fingerprint(self) -> str:
        payload = {
            "model": self.model,
            "endpoint": self.endpoint,
            "maxPages": self.max_pages_per_request,
            "maxChunkBytes": self.max_chunk_bytes,
            "maxResponseBytes": self.max_response_bytes,
            "wordConfidence": self.word_confidence,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


@dataclass(frozen=True, slots=True)
class OCR4Chunk:
    index: int
    physical_pages: tuple[int, ...]
    data: bytes
    sha256: str

    @property
    def expected_cost_unit(self) -> Decimal:
        return OCR4_PAGE_PRICE_UNIT * len(self.physical_pages)


@dataclass(frozen=True, slots=True)
class OCR4ChunkResult:
    chunk: OCR4Chunk
    root: Mapping[str, Any]
    parsed: AvalAIOCRResult
    retry_count: int = 0
    estimated_cost_unit: Decimal = Decimal("0")
    estimated_cost_irt: Decimal = Decimal("0")


@dataclass(frozen=True, slots=True)
class OCR4DocumentResult:
    source_sha256: str
    page_count: int
    pages: tuple[Mapping[str, Any], ...]
    chunks: tuple[OCR4ChunkResult, ...]
    resolved_models: tuple[str, ...]
    retry_count: int
    estimated_cost_unit: Decimal
    estimated_cost_irt: Decimal
    latency_ms: float


@dataclass(frozen=True, slots=True)
class SourceFirstAdapterStats:
    ocr_calls: int
    retries: int
    fallback_count: int
    bbox_calls: int = 0


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value or "0"))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    temporary.replace(path)


def _read_pdf(path: Path) -> tuple[PdfReader, bytes]:
    try:
        data = path.read_bytes()
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:
        raise SourceFirstConfigurationError("The supplied PDF cannot be opened.") from exc
    if not reader.pages:
        raise SourceFirstConfigurationError("The supplied PDF has no pages.")
    if getattr(reader, "is_encrypted", False):
        raise SourceFirstConfigurationError("Encrypted PDFs are not supported by source-first OCR.")
    return reader, data


def _selected_pdf_bytes(reader: PdfReader, pages: Sequence[int]) -> bytes:
    writer = PdfWriter()
    try:
        for page_number in pages:
            writer.add_page(reader.pages[int(page_number) - 1])
        buffer = io.BytesIO()
        writer.write(buffer)
        return buffer.getvalue()
    except Exception as exc:
        raise SourceFirstConfigurationError("Could not build a local PDF chunk.") from exc


def plan_pdf_chunks(
    pdf_path: str | Path,
    *,
    max_pages_per_request: int = OCR4_HARD_MAX_PAGES,
    max_chunk_bytes: int = OCR4_DEFAULT_CHUNK_BYTES,
) -> tuple[OCR4Chunk, ...]:
    """Plan contiguous one-based chunks before any network request."""

    if not 1 <= int(max_pages_per_request) <= OCR4_HARD_MAX_PAGES:
        raise SourceFirstConfigurationError(
            f"max_pages_per_request must be between 1 and {OCR4_HARD_MAX_PAGES}."
        )
    if int(max_chunk_bytes) < 1:
        raise SourceFirstConfigurationError("max_chunk_bytes must be positive.")
    path = Path(pdf_path).expanduser().resolve()
    if not path.is_file() or path.suffix.lower() != ".pdf":
        raise SourceFirstConfigurationError("pdf_path must point to an existing PDF.")
    reader, _source = _read_pdf(path)
    total = len(reader.pages)
    chunks: list[OCR4Chunk] = []
    start = 1
    chunk_index = 1
    while start <= total:
        low = start
        high = min(total, start + int(max_pages_per_request) - 1)
        best: tuple[tuple[int, ...], bytes] | None = None
        while low <= high:
            end = (low + high) // 2
            pages = tuple(range(start, end + 1))
            data = _selected_pdf_bytes(reader, pages)
            if len(data) <= int(max_chunk_bytes):
                best = (pages, data)
                low = end + 1
            else:
                high = end - 1
        if best is None:
            single_pages = (start,)
            single = _selected_pdf_bytes(reader, single_pages)
            raise SourceFirstConfigurationError(
                f"Physical page {start} alone is {len(single)} bytes, above the "
                f"chunk limit {int(max_chunk_bytes)}."
            )
        pages, data = best
        chunks.append(
            OCR4Chunk(
                index=chunk_index,
                physical_pages=pages,
                data=data,
                sha256=_sha256(data),
            )
        )
        start = pages[-1] + 1
        chunk_index += 1
    return tuple(chunks)


def _requests_post():
    try:
        import requests
    except ImportError as exc:  # pragma: no cover - deployment dependency
        raise SourceFirstConfigurationError(
            "The 'requests' package is required for live AvalAI OCR."
        ) from exc
    return requests.post, requests.RequestException


def _transport_result(response: Any) -> OCRHTTPResponse:
    return OCRHTTPResponse(
        status_code=int(response.status_code),
        headers=dict(getattr(response, "headers", {}) or {}),
        body=bytes(getattr(response, "content", b"")),
    )


def _retry_delay(
    *,
    headers: Mapping[str, Any],
    config: SourceFirstOCRConfig,
    attempt: int,
    random_value: Callable[[], float],
) -> float:
    """Honor a bounded provider Retry-After before local exponential backoff."""

    for key, value in headers.items():
        if str(key).lower() != "retry-after":
            continue
        try:
            return max(0.0, min(60.0, float(str(value).strip())))
        except (TypeError, ValueError):
            break
    delay = float(config.retry_backoff_seconds) * attempt
    delay += float(config.retry_jitter_seconds) * float(random_value())
    return max(0.0, min(60.0, delay))


def _invoke_transport(
    transport: Callable[..., Any],
    endpoint: str,
    headers: Mapping[str, str],
    payload: Mapping[str, Any],
    timeout: float,
) -> Any:
    """Support both requests-style and the repository's positional test seam."""

    try:
        return transport(
            endpoint,
            headers=headers,
            json=payload,
            timeout=timeout,
        )
    except TypeError as keyword_error:
        try:
            return transport(endpoint, headers, payload, timeout)
        except TypeError:
            raise keyword_error


def _request_chunk(
    chunk: OCR4Chunk,
    *,
    config: SourceFirstOCRConfig,
    api_key: str,
    transport: Callable[..., Any] | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    random_value: Callable[[], float] = random.random,
) -> OCR4ChunkResult:
    """Fetch one chunk, retrying only transport/transient provider failures."""

    config.validate()
    if not api_key.strip():
        raise SourceFirstConfigurationError("AVALAI_API_KEY is required for live OCR.")
    if transport is None:
        transport, request_exception = _requests_post()
    else:
        request_exception = Exception
    limits = AvalAIOCRLimits(
        max_input_bytes=int(config.max_chunk_bytes),
        max_response_bytes=int(config.max_response_bytes),
        max_pages=len(chunk.physical_pages),
        timeout_seconds=float(config.timeout_seconds),
    )
    payload = build_ocr_payload(
        data=chunk.data,
        media_type="application/pdf",
        model=config.model,
        mode="blocks",
        pages=None,
        limits=limits,
    )
    payload.update(
        {
            "include_image_base64": False,
            "extract_header": True,
            "extract_footer": True,
            "table_format": "html",
            "confidence_scores_granularity": (
                "word" if config.word_confidence else "page"
            ),
        }
    )
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
    }
    last_status: int | None = None
    last_body: bytes = b""
    last_headers: Mapping[str, Any] = {}
    started = time.monotonic()
    for attempt in range(1, int(config.max_attempts) + 1):
        try:
            response = _invoke_transport(
                transport,
                config.endpoint,
                headers,
                payload,
                float(config.timeout_seconds),
            )
            parsed_response = _transport_result(response)
            last_status = parsed_response.status_code
            last_body = parsed_response.body
            last_headers = parsed_response.headers
        except request_exception as exc:
            classification = classify_avalai_ocr_failure(status_code=None, body=None)
            if attempt >= int(config.max_attempts):
                raise SourceFirstProviderError(
                    "AvalAI OCR transport failed after the configured attempts.",
                    retryable=True,
                    attempts=attempt,
                    classification=classification,
                ) from exc
            delay = _retry_delay(
                headers={},
                config=config,
                attempt=attempt,
                random_value=random_value,
            )
            if delay:
                sleeper(delay)
            continue

        classification = classify_avalai_ocr_failure(
            status_code=last_status,
            body=last_body,
        )
        if not 200 <= int(last_status or 0) < 300:
            retryable = int(last_status or 0) in _RETRYABLE_STATUS and bool(
                classification.get("retryable")
            )
            if retryable and attempt < int(config.max_attempts):
                delay = _retry_delay(
                    headers=last_headers,
                    config=config,
                    attempt=attempt,
                    random_value=random_value,
                )
                if delay:
                    sleeper(delay)
                continue
            raise SourceFirstProviderError(
                f"AvalAI OCR returned HTTP {last_status}.",
                status_code=last_status,
                retryable=retryable,
                attempts=attempt,
                classification=classification,
            )

        try:
            parsed = parse_ocr_response(
                response=parsed_response,
                expected_pages=tuple(range(len(chunk.physical_pages))),
                limits=limits,
                latency_ms=(time.monotonic() - started) * 1000,
            )
        except Exception as exc:
            # A syntactically valid HTTP response with malformed content is not a
            # transport retry. Repeating it would pay for the same bad evidence.
            raise SourceFirstProviderError(
                "AvalAI OCR returned an invalid page/block response.",
                status_code=last_status,
                retryable=False,
                attempts=attempt,
                classification={"category": "invalid_response", "retryable": False},
            ) from exc
        root = json.loads(last_body)
        estimated = root.get("estimated_cost") if isinstance(root, Mapping) else {}
        estimated = estimated if isinstance(estimated, Mapping) else {}
        estimated_unit = _decimal(estimated.get("unit"))
        if estimated_unit <= 0:
            estimated_unit = chunk.expected_cost_unit
        return OCR4ChunkResult(
            chunk=chunk,
            root=root,
            parsed=parsed,
            retry_count=attempt - 1,
            estimated_cost_unit=estimated_unit,
            estimated_cost_irt=_decimal(estimated.get("irt")),
        )
    raise SourceFirstProviderError("AvalAI OCR request did not complete.")


def _physical_pages_from_chunk(result: OCR4ChunkResult) -> tuple[Mapping[str, Any], ...]:
    """Copy local provider page indexes onto their one-based source pages."""

    raw_pages = result.root.get("pages") if isinstance(result.root, Mapping) else None
    if not isinstance(raw_pages, list):
        raise SourceFirstCoverageError("OCR response has no pages list.")
    by_index: dict[int, Mapping[str, Any]] = {}
    for raw in raw_pages:
        if not isinstance(raw, Mapping) or not isinstance(raw.get("index"), int):
            continue
        index = int(raw["index"])
        if index in by_index:
            raise SourceFirstCoverageError("OCR response contains duplicate page indexes.")
        by_index[index] = raw
    expected = set(range(len(result.chunk.physical_pages)))
    if set(by_index) != expected:
        missing = sorted(expected - set(by_index))
        extra = sorted(set(by_index) - expected)
        raise SourceFirstCoverageError(
            f"OCR chunk page coverage mismatch (missing={missing}, extra={extra})."
        )
    output: list[Mapping[str, Any]] = []
    for local, physical in enumerate(result.chunk.physical_pages):
        copied = dict(by_index[local])
        copied["index"] = physical - 1
        copied["sourcePhysicalPage"] = physical
        output.append(copied)
    return tuple(output)


def merge_chunk_results(
    *,
    source_sha256: str,
    page_count: int,
    chunk_results: Sequence[OCR4ChunkResult],
) -> OCR4DocumentResult:
    """Merge chunks and fail closed on any missing/duplicate physical page."""

    pages: list[Mapping[str, Any]] = []
    seen: set[int] = set()
    models: set[str] = set()
    retries = 0
    cost_unit = Decimal("0")
    cost_irt = Decimal("0")
    latency = 0.0
    for result in sorted(chunk_results, key=lambda item: item.chunk.index):
        for page in _physical_pages_from_chunk(result):
            physical = int(page["sourcePhysicalPage"])
            if physical in seen:
                raise SourceFirstCoverageError(
                    f"OCR document contains duplicate physical page {physical}."
                )
            seen.add(physical)
            pages.append(page)
        if result.parsed.model:
            models.add(result.parsed.model)
        retries += int(result.retry_count)
        cost_unit += result.estimated_cost_unit
        cost_irt += result.estimated_cost_irt
        latency += float(result.parsed.latency_ms)
    expected = set(range(1, int(page_count) + 1))
    if seen != expected:
        raise SourceFirstCoverageError(
            f"OCR document coverage mismatch (missing={sorted(expected - seen)[:20]}, "
            f"extra={sorted(seen - expected)[:20]})."
        )
    pages.sort(key=lambda item: int(item["sourcePhysicalPage"]))
    return OCR4DocumentResult(
        source_sha256=source_sha256,
        page_count=int(page_count),
        pages=tuple(pages),
        chunks=tuple(sorted(chunk_results, key=lambda item: item.chunk.index)),
        resolved_models=tuple(sorted(models)),
        retry_count=retries,
        estimated_cost_unit=cost_unit,
        estimated_cost_irt=cost_irt,
        latency_ms=round(latency, 2),
    )


def fetch_document_ocr4(
    pdf_path: str | Path,
    *,
    config: SourceFirstOCRConfig | None = None,
    api_key: str | None = None,
    transport: Callable[..., Any] | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    random_value: Callable[[], float] = random.random,
    chunk_callback: Callable[[OCR4ChunkResult], None] | None = None,
    selected_chunks: Sequence[OCR4Chunk] | None = None,
) -> OCR4DocumentResult:
    """Fetch a complete PDF through bounded OCR4 chunks.

    ``chunk_callback`` is invoked only after a chunk has passed page-coverage
    validation, which makes it safe for callers to checkpoint raw responses.
    """

    selected = config or SourceFirstOCRConfig.from_env()
    selected.validate()
    path = Path(pdf_path).expanduser().resolve()
    reader, source_bytes = _read_pdf(path)
    chunks = tuple(selected_chunks or plan_pdf_chunks(
        path,
        max_pages_per_request=selected.max_pages_per_request,
        max_chunk_bytes=selected.max_chunk_bytes,
    ))
    if not chunks:
        raise SourceFirstConfigurationError("No OCR chunks were planned.")
    key = str(api_key or os.getenv("AVALAI_API_KEY") or "").strip()
    # Keep the reader reference alive until all chunk bytes are constructed; it
    # also makes the page-count check explicit for callers passing a plan.
    del reader
    results: list[OCR4ChunkResult] = []
    for chunk in chunks:
        result = _request_chunk(
            chunk,
            config=selected,
            api_key=key,
            transport=transport,
            sleeper=sleeper,
            random_value=random_value,
        )
        results.append(result)
        if chunk_callback is not None:
            chunk_callback(result)
    return merge_chunk_results(
        source_sha256=_sha256(source_bytes),
        page_count=len(PdfReader(io.BytesIO(source_bytes)).pages),
        chunk_results=results,
    )


def _normalized_page_root(result: OCR4DocumentResult) -> dict[str, Any]:
    return {
        "pages": [dict(page) for page in result.pages],
        "model": ",".join(result.resolved_models),
        "usage_info": {
            "pages_processed": result.page_count,
            "doc_size_bytes": sum(len(item.chunk.data) for item in result.chunks),
        },
        "estimated_cost": {
            "unit": format(result.estimated_cost_unit, "f"),
            "irt": format(result.estimated_cost_irt, "f"),
        },
    }


def analyze_source_result(result: OCR4DocumentResult) -> dict[str, Any]:
    """Run deterministic layout analysis while preserving raw page evidence."""

    root = _normalized_page_root(result)
    analysis = analyze_ocr_document(
        root,
        original_page_numbers=list(range(1, result.page_count + 1)),
    )
    analysis["solutionHeadingAudit"] = audit_solution_headings(
        root,
        original_page_numbers=list(range(1, result.page_count + 1)),
    )
    return analysis


def _segment_page_numbers(segment: Any, pages: Sequence[Any]) -> tuple[int, ...]:
    metadata = getattr(segment, "metadata", None)
    raw = metadata.get("pageNumbers") if isinstance(metadata, Mapping) else None
    if isinstance(raw, list) and raw:
        try:
            return tuple(int(value) for value in raw)
        except (TypeError, ValueError):
            pass
    by_number = {int(page.page_number): index for index, page in enumerate(pages)}
    start = int(segment.start_page)
    end = int(segment.end_page)
    if start not in by_number or end not in by_number:
        return ()
    low, high = sorted((by_number[start], by_number[end]))
    sequence = tuple(int(page.page_number) for page in pages[low : high + 1])
    return sequence if by_number[start] <= by_number[end] else tuple(reversed(sequence))


def _region_kind_for_role(role: str, region_kind: str) -> str | None:
    # The confirmed source-map role is authoritative. OCR's inferred page role
    # is never allowed to change it.
    role = str(getattr(role, "value", role) or "").strip().lower()
    if role == "questions":
        return "question" if region_kind == "question" else None
    if role == "answer_solutions":
        return "answer_solution" if region_kind == "solution" else None
    if role == "answer_key":
        return "answer_key" if region_kind == "solution" else None
    if role == "inline_question_answer":
        return "inline_question_answer" if region_kind in {"question", "solution"} else None
    return None


_UNSAFE_REGION_ISSUES = frozenset(
    {
        # These indicate that the deterministic heading/number contract is not
        # reliable enough to create a source block.  Visual warnings are kept
        # as review evidence and do not, by themselves, discard a crop.
        "heading_sequence_gap",
        "ambiguous_heading",
        "duplicate_heading",
    }
)


def _region_number(region: Mapping[str, Any]) -> int | None:
    value = region.get("questionNumber")
    translated = str(value or "").translate(
        str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    )
    digits = "".join(character for character in translated if character.isdigit())
    if not digits:
        return None
    try:
        number = int(digits)
    except ValueError:
        return None
    return number if number > 0 else None


def _structurally_safe_region(region: Mapping[str, Any]) -> bool:
    if _region_number(region) is None:
        return False
    if bool(region.get("numberRecoveredFromSequence")):
        return False
    issues = {
        str(value)
        for value in (region.get("issues") or [])
        if value is not None
    }
    return not issues.intersection(_UNSAFE_REGION_ISSUES)


def _rotate_normalized_bbox(
    box: Sequence[float],
    orientation: int,
) -> tuple[float, float, float, float]:
    """Map a raw-PDF bbox into the orientation used by V4 page crops."""

    x0, y0, x1, y1 = (float(value) for value in box)
    angle = int(orientation or 0) % 360
    if angle == 90:
        return (1.0 - y1, x0, 1.0 - y0, x1)
    if angle == 180:
        return (1.0 - x1, 1.0 - y1, 1.0 - x0, 1.0 - y0)
    if angle == 270:
        return (y0, 1.0 - x1, y1, 1.0 - x0)
    return (x0, y0, x1, y1)


def build_segment_blocks(
    analysis: Mapping[str, Any],
    *,
    segment: Any,
    pages: Sequence[Any],
) -> dict[str, Any]:
    """Convert deterministic regions into the V4 block-detector contract."""

    segment_page_sequence = _segment_page_numbers(segment, pages)
    allowed_pages = set(segment_page_sequence)
    if not allowed_pages:
        return {"blocks": []}
    page_objects = {
        int(getattr(page, "page_number")): page for page in pages
    }
    page_rank = {
        number: int(getattr(page_objects[number], "display_order", None) or index)
        for index, number in enumerate(segment_page_sequence)
        if number in page_objects
    }
    role = str(getattr(segment, "role", "") or "")
    # Build a candidate set first.  A partial set is more dangerous than no
    # OCR proposal: the V4 pipeline treats returned blocks as a complete
    # segment proposal.  In that case the caller must use its existing
    # structured detector for the whole segment.
    candidates: list[tuple[int, float, float, Mapping[str, Any], int]] = []
    candidate_keys: set[tuple[str, int]] = set()
    records: list[dict[str, Any]] = []
    for page in analysis.get("pages") or []:
        if not isinstance(page, Mapping):
            continue
        physical = int(page.get("originalPageNumber") or 0)
        if physical not in allowed_pages:
            continue
        for region in page.get("regions") or []:
            if not isinstance(region, Mapping):
                continue
            kind = _region_kind_for_role(role, str(region.get("kind") or ""))
            # A mixed page may contain a region belonging to another inferred
            # role.  The confirmed segment role remains authoritative, so such
            # a region is ignored rather than making an otherwise safe segment
            # fail.
            if kind is None:
                continue
            raw_box = region.get("bbox")
            if not isinstance(raw_box, (list, tuple)) or len(raw_box) != 4:
                return {"blocks": []}
            try:
                region_y0 = float(raw_box[1])
                region_x0 = float(raw_box[0])
            except (TypeError, ValueError):
                continue
            if not _structurally_safe_region(region):
                return {"blocks": []}
            number = _region_number(region)
            assert number is not None  # guarded by _structurally_safe_region
            key = (kind, number)
            if key in candidate_keys:
                return {"blocks": []}
            candidate_keys.add(key)
            candidates.append(
                (
                    page_rank.get(physical, 10**9),
                    region_y0,
                    region_x0,
                    region,
                    physical,
                )
            )
    for _page_order, _y0, _x0, region, physical in sorted(candidates, key=lambda item: item[:3]):
        kind = _region_kind_for_role(role, str(region.get("kind") or ""))
        box = region.get("bbox")
        if kind is None or not isinstance(box, (list, tuple)) or len(box) != 4:
            return {"blocks": []}
        try:
            x0, y0, x1, y1 = (float(value) for value in box)
        except (TypeError, ValueError):
            return {"blocks": []}
        x0, y0, x1, y1 = _rotate_normalized_bbox(
            (x0, y0, x1, y1),
            int(getattr(page_objects.get(physical), "orientation", 0) or 0),
        )
        x0, y0, x1, y1 = max(0.0, x0), max(0.0, y0), min(1.0, x1), min(1.0, y1)
        if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
            return {"blocks": []}
        printed = str(region.get("questionNumber") or "").strip()
        # A region with no deterministic number is not persisted as a new
        # item. It is left to the existing detector for safe fallback.
        if not printed:
            return {"blocks": []}
        records.append(
            {
                "order": len(records),
                "kind": kind,
                "printedNumber": printed,
                # OCR confidence is intentionally not treated as correctness;
                # this value only satisfies the existing proposal contract.
                "confidence": 0.0,
                "fragments": [
                    {
                        "order": 0,
                        "pageNumber": physical,
                        "x0": x0,
                        "y0": y0,
                        "x1": x1,
                        "y1": y1,
                        "columnIndex": 0,
                        "isContinuation": False,
                    }
                ],
            }
        )
    if not records or {
        physical for _rank, _y, _x, _region, physical in candidates
    } != allowed_pages:
        return {"blocks": []}
    return {"blocks": records}


class MistralSourceFirstAdapter:
    """Lazy, document-cached OCR4 geometry adapter with safe fallback.

    The adapter delegates all semantic extraction methods to ``fallback``. It
    only supplies block proposals, and only when every selected segment region
    is deterministically numbered; otherwise that segment uses the existing
    detector. This keeps OCR text/formula instability out of persisted records.
    """

    def __init__(
        self,
        *,
        fallback: Any,
        config: SourceFirstOCRConfig | None = None,
        api_key: str | None = None,
        transport: Callable[..., Any] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.fallback = fallback
        self.config = config or SourceFirstOCRConfig.from_env()
        self.config.validate()
        self.api_key = api_key
        self.transport = transport
        self.sleeper = sleeper
        self._document_cache: dict[str, tuple[OCR4DocumentResult, dict[str, Any]]] = {}
        self._document_errors: dict[str, SourceFirstError] = {}
        self.ocr_calls = 0
        self.ocr_retries = 0
        self.ocr_fallback_segments = 0

    @property
    def provider_calls(self) -> int:
        return int(getattr(self.fallback, "provider_calls", 0)) + self.ocr_calls

    @property
    def stats(self) -> SourceFirstAdapterStats:
        return SourceFirstAdapterStats(
            ocr_calls=self.ocr_calls,
            retries=self.ocr_retries,
            fallback_count=self.ocr_fallback_segments,
        )

    def __getattr__(self, name: str):
        return getattr(self.fallback, name)

    def _document_key(self, document: Any) -> str:
        source_sha = str(getattr(document, "source_sha256", "") or "")
        fingerprint = str(getattr(document, "source_map_fingerprint", "") or "")
        revision = str(getattr(document, "classification_revision", "") or "")
        return (
            f"{getattr(document, 'id', '')}:{source_sha}:{revision}:"
            f"{fingerprint}:{self.config.contract_fingerprint}"
        )

    def _source_path(self, document: Any) -> Path:
        source = getattr(document, "source_file", None)
        if source is None:
            raise SourceFirstConfigurationError("The source document has no private PDF.")
        suffix = Path(str(getattr(document, "original_name", "source.pdf"))).suffix or ".pdf"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
            temporary = Path(handle.name)
            try:
                if hasattr(source, "open"):
                    with source.open("rb") as stream:
                        while True:
                            data = stream.read(1024 * 1024)
                            if not data:
                                break
                            handle.write(data)
                elif isinstance(source, (str, Path)):
                    handle.write(Path(source).read_bytes())
                else:
                    handle.write(bytes(source))
            except Exception:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
                raise
        return temporary

    def _ensure_document(self, document: Any) -> tuple[OCR4DocumentResult, dict[str, Any]]:
        key = self._document_key(document)
        cached = self._document_cache.get(key)
        if cached is not None:
            return cached
        previous_error = self._document_errors.get(key)
        if previous_error is not None:
            raise previous_error
        path = self._source_path(document)
        try:
            try:
                result = fetch_document_ocr4(
                    path,
                    config=self.config,
                    api_key=self.api_key,
                    transport=self.transport,
                    sleeper=self.sleeper,
                )
            except SourceFirstConfigurationError:
                raise
            except SourceFirstError as exc:
                self._document_errors[key] = exc
                raise
            expected_sha = str(getattr(document, "source_sha256", "") or "").strip()
            if expected_sha and result.source_sha256 != expected_sha:
                error = SourceFirstCoverageError(
                    "The uploaded source hash changed during OCR preparation."
                )
                self._document_errors[key] = error
                raise error
        finally:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        self.ocr_calls += len(result.chunks)
        self.ocr_retries += result.retry_count
        analysis = analyze_source_result(result)
        self._document_cache[key] = (result, analysis)
        return result, analysis

    def detect_segment_blocks(self, *, document, segment, pages, images):
        kwargs = {
            "document": document,
            "segment": segment,
            "pages": pages,
            "images": images,
        }
        try:
            _result, analysis = self._ensure_document(document)
            raw = build_segment_blocks(analysis, segment=segment, pages=pages)
            records = raw.get("blocks") if isinstance(raw, Mapping) else None
            if not isinstance(records, list) or not records:
                self.ocr_fallback_segments += 1
                return self.fallback.detect_segment_blocks(**kwargs)
            # A numbered block set must cover only this segment's pages. The
            # pipeline adds segmentOrder and performs the final contract parse.
            return raw
        except SourceFirstConfigurationError:
            raise
        except SourceFirstError:
            self.ocr_fallback_segments += 1
            return self.fallback.detect_segment_blocks(**kwargs)


def safe_document_metrics(result: OCR4DocumentResult, analysis: Mapping[str, Any]) -> dict[str, Any]:
    """Content-free metrics suitable for logs/status counters."""

    totals = analysis.get("totals") if isinstance(analysis, Mapping) else {}
    totals = totals if isinstance(totals, Mapping) else {}
    return {
        "ocrSourcePages": result.page_count,
        "ocrSourceChunksPlanned": len(result.chunks),
        "ocrSourceChunksCompleted": len(result.chunks),
        "ocrSourceRetries": result.retry_count,
        "ocrSourceResolvedModels": list(result.resolved_models),
        "ocrSourceQuestionRegions": int(totals.get("questionRegions") or 0),
        "ocrSourceSolutionRegions": int(totals.get("solutionRegions") or 0),
        "ocrSourceRegionsNeedingAttention": int(
            totals.get("regionsNeedingLocalAttention") or 0
        ),
        "ocrSourceEstimatedCostUnit": format(result.estimated_cost_unit, "f"),
    }


def _render_page_jpeg(pdf_path: Path, page_number: int, *, dpi: int) -> bytes:
    """Render one source page without relying on a filesystem PDF path in callers."""

    try:
        import pypdfium2 as pdfium
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - deployment dependency
        raise SourceFirstConfigurationError(
            "pypdfium2 and Pillow are required to render source crops."
        ) from exc
    try:
        document = pdfium.PdfDocument(str(pdf_path))
        page = document[int(page_number) - 1]
        try:
            bitmap = page.render(scale=float(dpi) / 72.0)
            try:
                image = bitmap.to_pil().convert("RGB")
            finally:
                bitmap.close()
        finally:
            page.close()
            document.close()
    except Exception as exc:  # pragma: no cover - renderer/provider workstation
        raise SourceFirstConfigurationError(
            f"Could not render physical page {page_number}."
        ) from exc
    try:
        # Keep the page artifact bounded. The original PDF remains the exact
        # source; JPEG is only a review/crop convenience representation.
        image.thumbnail((2400, 2400), Image.Resampling.LANCZOS)
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=90, optimize=True)
        return output.getvalue()
    finally:
        image.close()


def _crop_jpeg(
    page_bytes: bytes,
    bbox: Sequence[float],
    *,
    padding: float = 0.012,
) -> bytes:
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover
        raise SourceFirstConfigurationError("Pillow is required for source crops.") from exc
    if len(bbox) != 4:
        raise SourceFirstConfigurationError("A source crop requires four bbox coordinates.")
    with Image.open(io.BytesIO(page_bytes)) as source:
        image = source.convert("RGB")
        width, height = image.size
        x0, y0, x1, y1 = (float(value) for value in bbox)
        pad_x = max(0.0, float(padding)) * width
        pad_y = max(0.0, float(padding)) * height
        left = max(0, min(width - 1, round(x0 * width - pad_x)))
        top = max(0, min(height - 1, round(y0 * height - pad_y)))
        right = max(left + 1, min(width, round(x1 * width + pad_x)))
        bottom = max(top + 1, min(height, round(y1 * height + pad_y)))
        crop = image.crop((left, top, right, bottom))
        crop.thumbnail((2400, 2400), Image.Resampling.LANCZOS)
        output = io.BytesIO()
        crop.save(output, format="JPEG", quality=92, optimize=True)
        crop.close()
        return output.getvalue()


def _item_id(kind: str, number: Any, seen: MutableMapping[str, int]) -> str:
    prefix = "q" if kind == "question" else "s" if kind == "solution" else "i"
    raw = str(number or "unknown").translate(
        str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    )
    raw = "".join(ch for ch in raw if ch.isdigit()) or "unknown"
    base = f"{prefix}-{int(raw):03d}" if raw.isdigit() else f"{prefix}-{raw}"
    occurrence = int(seen.get(base, 0))
    seen[base] = occurrence + 1
    return base if occurrence == 0 else f"{base}-dup{occurrence + 1}"


def write_source_first_bundle(
    *,
    pdf_path: str | Path,
    result: OCR4DocumentResult,
    analysis: Mapping[str, Any],
    output_dir: str | Path,
    render_dpi: int = 200,
    write_page_images: bool = True,
    max_pages_per_chunk: int = OCR4_HARD_MAX_PAGES,
    max_chunk_bytes: int = OCR4_DEFAULT_CHUNK_BYTES,
) -> dict[str, Any]:
    """Write a private, inspectable source-first bundle and safe manifest.

    ``manifest.json`` contains OCR text and must stay private. The accompanying
    ``manifest.safe.json`` contains only counts, hashes, model IDs, and costs.
    """

    if int(render_dpi) < 96 or int(render_dpi) > 300:
        raise SourceFirstConfigurationError("render_dpi must be between 96 and 300.")
    path = Path(pdf_path).expanduser().resolve()
    output = Path(output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    pages_dir = output / "pages"
    items_dir = output / "items"
    pages_dir.mkdir(exist_ok=True)
    items_dir.mkdir(exist_ok=True)

    raw_root = _normalized_page_root(result)
    _atomic_json(output / "response.raw.json", raw_root)
    _atomic_json(output / "analysis.json", dict(analysis))
    page_by_number = {
        int(page["sourcePhysicalPage"]): page for page in result.pages
    }
    rendered: dict[int, bytes] = {}
    page_records: list[dict[str, Any]] = []
    if write_page_images:
        for physical in range(1, result.page_count + 1):
            data = _render_page_jpeg(path, physical, dpi=int(render_dpi))
            rendered[physical] = data
            (pages_dir / f"page-{physical:03d}.jpg").write_bytes(data)

    analysis_pages = {
        int(page.get("originalPageNumber") or 0): page
        for page in analysis.get("pages") or []
        if isinstance(page, Mapping)
    }
    seen_ids: dict[str, int] = {}
    items: list[dict[str, Any]] = []
    for physical in range(1, result.page_count + 1):
        raw_page = page_by_number.get(physical, {})
        analyzed_page = analysis_pages.get(physical, {})
        page_item_ids: list[str] = []
        for region in analyzed_page.get("regions") or []:
            if not isinstance(region, Mapping):
                continue
            kind = str(region.get("kind") or "").strip().lower()
            if kind not in {"question", "solution"}:
                continue
            page_role = str(analyzed_page.get("pageRole") or "other").strip().lower()
            # Keep mixed pages for solution evidence (some answer pages begin
            # with a short question-like heading), but never count a question
            # heading found on a solution page as a second question document.
            if kind == "question" and page_role != "question":
                continue
            if kind == "solution" and page_role not in {"solution", "mixed"}:
                continue
            item_id = _item_id(kind, region.get("questionNumber"), seen_ids)
            page_item_ids.append(item_id)
            bbox = list(region.get("bbox") or [])
            crop_path = None
            if write_page_images and len(bbox) == 4 and physical in rendered:
                crop = _crop_jpeg(rendered[physical], bbox)
                crop_file = items_dir / f"{item_id}.source.jpg"
                crop_file.write_bytes(crop)
                crop_path = str(crop_file.relative_to(output))
            issues = sorted({str(value) for value in region.get("issues") or []})
            visual_required = bool(
                region.get("visuals")
                or region.get("uncoveredGraphics")
                or any(
                    issue
                    in {
                        "visual_reference_without_ocr_visual",
                        "caption_visual_count_mismatch",
                        "visual_options_grouped_in_single_block",
                        "table_contains_visual_or_empty_cells",
                        "uncovered_graphics_in_region",
                    }
                    for issue in issues
                )
            )
            text = str(region.get("text") or "")
            # Formula/visual/source corruption are review flags, not automatic
            # rejection decisions. No OCR confidence is exposed as correctness.
            needs_review = bool(
                issues
                or visual_required
                or any(signal in text for signal in ("$$", "\\(", "\\frac", "√", "∑"))
            )
            items.append(
                {
                    "itemId": item_id,
                    "kind": kind,
                    "printedNumber": region.get("questionNumber"),
                    "physicalPageNumbers": [physical],
                    "pageRole": page_role,
                    "bbox": bbox,
                    "sourceCrop": crop_path,
                    "ocrText": text,
                    "correctOptionLabel": region.get("correctOptionLabel"),
                    "visualRequired": visual_required,
                    "visuals": list(region.get("visuals") or []),
                    "uncoveredGraphics": list(region.get("uncoveredGraphics") or []),
                    "qualityFlags": issues,
                    "needsHumanReview": needs_review,
                    "authority": "source_crop_and_original_pdf",
                }
            )
        page_record = {
            "physicalPageNumber": physical,
            "providerPageIndex": int(raw_page.get("index") or physical - 1),
            "pageRole": analyzed_page.get("pageRole", "other"),
            "sourceImage": (
                str((pages_dir / f"page-{physical:03d}.jpg").relative_to(output))
                if write_page_images
                else None
            ),
            "markdown": str(raw_page.get("markdown") or ""),
            "itemIds": page_item_ids,
            "issues": list(analyzed_page.get("issues") or []),
        }
        page_records.append(page_record)

    totals = analysis.get("totals") if isinstance(analysis, Mapping) else {}
    totals = totals if isinstance(totals, Mapping) else {}
    heading_audit = analysis.get("solutionHeadingAudit")
    heading_audit = heading_audit if isinstance(heading_audit, Mapping) else {}
    manifest: dict[str, Any] = {
        "schemaVersion": 1,
        "pipeline": "exam_prep_source_first",
        "privateBundle": True,
        "authority": {
            "originalPdf": True,
            "renderedPageAndItemCrops": True,
            "ocrMarkdownAndBlocks": "derived_evidence_only",
            "visualCompleteness": "source_crop_review_required",
            "providerImageBlocksAreNotComplete": True,
            "confidenceIsNotCorrectness": True,
        },
        "source": {
            "filename": path.name,
            "sha256": result.source_sha256,
            "pageCount": result.page_count,
        },
        "model": {
            "requested": result.chunks[0].parsed.model if result.chunks else "",
            "resolved": list(result.resolved_models),
        },
        "chunks": [
            {
                "chunkIndex": item.chunk.index,
                "physicalPages": list(item.chunk.physical_pages),
                "pdfBytes": len(item.chunk.data),
                "pdfSha256": item.chunk.sha256,
                "requestId": item.parsed.request_id,
                "latencyMs": item.parsed.latency_ms,
                "retryCount": item.retry_count,
                "estimatedCostUnit": format(item.estimated_cost_unit, "f"),
                "estimatedCostIrt": format(item.estimated_cost_irt, "f"),
            }
            for item in result.chunks
        ],
        "pages": page_records,
        "items": items,
        "metrics": {
            "questionRegions": int(totals.get("questionRegions") or 0),
            "solutionRegions": int(totals.get("solutionRegions") or 0),
            "regionsNeedingLocalAttention": int(
                totals.get("regionsNeedingLocalAttention") or 0
            ),
            "itemCount": len(items),
            "itemsNeedingHumanReview": sum(
                bool(item["needsHumanReview"]) for item in items
            ),
            "retryCount": result.retry_count,
            "estimatedCostUnit": format(result.estimated_cost_unit, "f"),
            "estimatedCostIrt": format(result.estimated_cost_irt, "f"),
            "solutionHeadingCandidates": int(heading_audit.get("rawCandidateCount") or 0),
            "solutionHeadingAccepted": int(heading_audit.get("acceptedHeadingCount") or 0),
            "solutionHeadingUniqueQuestions": int(
                heading_audit.get("uniqueAcceptedQuestionCount") or 0
            ),
            "solutionHeadingMissingCount": len(
                heading_audit.get("missingSolutionHeadingNumbers") or []
            ),
            "solutionHeadingInvalidOptionCount": len(
                heading_audit.get("invalidOptionLabels") or []
            ),
        },
    }
    _atomic_json(output / "manifest.json", manifest)
    total_blocks = sum(
        len(page.get("blocks") or [])
        for page in result.pages
        if isinstance(page, Mapping)
    )
    word_confidence_returned = any(
        isinstance(page.get("confidence_scores"), Mapping)
        and bool((page.get("confidence_scores") or {}).get("word_confidence_scores"))
        for page in result.pages
        if isinstance(page, Mapping)
    )
    acceptance = {
        "allPhysicalPagesReturned": len(page_records) == result.page_count,
        "blocksReturned": total_blocks > 0,
        "chunkPageLimitRespected": all(
            len(item.chunk.physical_pages) <= int(max_pages_per_chunk)
            for item in result.chunks
        ),
        "chunkByteLimitRespected": all(
            len(item.chunk.data) <= int(max_chunk_bytes)
            for item in result.chunks
        ),
    }
    safe = {
        "schemaVersion": 1,
        "pipeline": "exam_prep_source_first",
        "privateBundle": True,
        "visualCompletenessAuthority": "source_crop_review_required",
        "providerImageBlocksAreNotComplete": True,
        "sourceSha256": result.source_sha256,
        "pageCount": result.page_count,
        "resolvedModels": list(result.resolved_models),
        "chunkCount": len(result.chunks),
        "chunkPageCounts": [len(item.chunk.physical_pages) for item in result.chunks],
        "retryCount": result.retry_count,
        "questionRegions": int(totals.get("questionRegions") or 0),
        "solutionRegions": int(totals.get("solutionRegions") or 0),
        "itemCount": len(items),
        "itemsNeedingHumanReview": sum(bool(item["needsHumanReview"]) for item in items),
        "solutionHeadingCandidates": int(heading_audit.get("rawCandidateCount") or 0),
        "solutionHeadingAccepted": int(heading_audit.get("acceptedHeadingCount") or 0),
        "solutionHeadingUniqueQuestions": int(
            heading_audit.get("uniqueAcceptedQuestionCount") or 0
        ),
        "solutionHeadingMissingCount": len(
            heading_audit.get("missingSolutionHeadingNumbers") or []
        ),
        "solutionHeadingInvalidOptionCount": len(
            heading_audit.get("invalidOptionLabels") or []
        ),
        "estimatedCostUnit": format(result.estimated_cost_unit, "f"),
        "estimatedCostIrt": format(result.estimated_cost_irt, "f"),
        **acceptance,
        "wordConfidenceReturned": word_confidence_returned,
        "acceptancePassed": all(acceptance.values()),
        "authorityContractPassed": all(
            item.get("authority") == "source_crop_and_original_pdf" for item in items
        ),
    }
    _atomic_json(output / "manifest.safe.json", safe)
    return manifest
