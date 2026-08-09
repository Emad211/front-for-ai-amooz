"""Production-only AvalAI/Mistral OCR4 document transport.

This module contains no Exam Prep V4, benchmark, probe, or general-LLM dependency.
It owns the paid OCR boundary for the researched Exam Prep engine:

PDF bytes -> contiguous <=30-page mini PDFs -> OCR4 blocks -> validated physical pages.

Successful chunk responses are checkpointed in private storage only after exact
page-coverage validation. A later retry/re-run can reuse those chunks without
paying for them again. Only transport failures and the narrow transient HTTP
allow-list are retried; malformed 2xx responses and request/configuration errors
fail without a paid repeat.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import os
import random
import time
from typing import Any, Callable, Mapping, Protocol, Sequence

from pypdf import PdfReader, PdfWriter


AVALAI_OCR_ENDPOINT = "https://api.avalai.ir/v1/ocr"
MISTRAL_OCR4_MODEL = "mistral-ocr-4-0"
OCR4_HARD_MAX_PAGES = 30
OCR4_DEFAULT_CHUNK_BYTES = 28 * 1024 * 1024
OCR4_DEFAULT_RESPONSE_BYTES = 120 * 1024 * 1024
_RETRYABLE_HTTP_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
_CHECKPOINT_SCHEMA = 1


class MistralOCR4Error(RuntimeError):
    pass


class MistralOCR4ConfigurationError(MistralOCR4Error):
    pass


class MistralOCR4ProviderError(MistralOCR4Error):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retryable: bool = False,
        attempts: int = 1,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retryable = bool(retryable)
        self.attempts = max(1, int(attempts))
        self.request_id = request_id


class MistralOCR4CoverageError(MistralOCR4Error):
    pass


@dataclass(frozen=True, slots=True)
class MistralOCR4Config:
    model: str = MISTRAL_OCR4_MODEL
    endpoint: str = AVALAI_OCR_ENDPOINT
    max_pages_per_request: int = OCR4_HARD_MAX_PAGES
    max_chunk_bytes: int = OCR4_DEFAULT_CHUNK_BYTES
    max_response_bytes: int = OCR4_DEFAULT_RESPONSE_BYTES
    timeout_seconds: float = 600.0
    max_attempts: int = 2
    retry_backoff_seconds: float = 2.0
    retry_jitter_seconds: float = 0.5
    word_confidence: bool = True
    checkpoint_enabled: bool = True

    @classmethod
    def from_env(cls) -> "MistralOCR4Config":
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

        def boolean(name: str, default: bool) -> bool:
            raw = os.getenv(name)
            if raw is None:
                return default
            return str(raw).strip().lower() in {"1", "true", "yes", "on"}

        return cls(
            model=(os.getenv("EXAM_PREP_MISTRAL_OCR_MODEL") or MISTRAL_OCR4_MODEL).strip(),
            endpoint=(os.getenv("AVALAI_OCR_ENDPOINT") or AVALAI_OCR_ENDPOINT).strip(),
            max_pages_per_request=integer(
                "EXAM_PREP_MISTRAL_OCR_MAX_PAGES_PER_REQUEST",
                OCR4_HARD_MAX_PAGES,
            ),
            max_chunk_bytes=integer(
                "EXAM_PREP_MISTRAL_OCR_MAX_CHUNK_BYTES",
                OCR4_DEFAULT_CHUNK_BYTES,
            ),
            max_response_bytes=integer(
                "EXAM_PREP_MISTRAL_OCR_MAX_RESPONSE_BYTES",
                OCR4_DEFAULT_RESPONSE_BYTES,
            ),
            timeout_seconds=number("EXAM_PREP_MISTRAL_OCR_TIMEOUT_SECONDS", 600.0),
            max_attempts=integer("EXAM_PREP_MISTRAL_OCR_MAX_ATTEMPTS", 2),
            retry_backoff_seconds=number(
                "EXAM_PREP_MISTRAL_OCR_RETRY_BACKOFF_SECONDS", 2.0
            ),
            retry_jitter_seconds=number(
                "EXAM_PREP_MISTRAL_OCR_RETRY_JITTER_SECONDS", 0.5
            ),
            word_confidence=boolean("EXAM_PREP_MISTRAL_OCR_WORD_CONFIDENCE", True),
            checkpoint_enabled=boolean("EXAM_PREP_MISTRAL_OCR_CHECKPOINTS", True),
        )

    def validate(self) -> None:
        if not self.model:
            raise MistralOCR4ConfigurationError("An explicit OCR4 model is required.")
        if not self.endpoint.startswith(("https://", "http://")):
            raise MistralOCR4ConfigurationError("OCR4 endpoint must be HTTP(S).")
        if not 1 <= int(self.max_pages_per_request) <= OCR4_HARD_MAX_PAGES:
            raise MistralOCR4ConfigurationError(
                f"max_pages_per_request must be 1..{OCR4_HARD_MAX_PAGES}."
            )
        if int(self.max_chunk_bytes) < 1 or int(self.max_response_bytes) < 1:
            raise MistralOCR4ConfigurationError("OCR byte limits must be positive.")
        if float(self.timeout_seconds) < 1:
            raise MistralOCR4ConfigurationError("OCR timeout must be >= 1 second.")
        if not 1 <= int(self.max_attempts) <= 3:
            raise MistralOCR4ConfigurationError("OCR max_attempts must be 1..3.")
        if self.retry_backoff_seconds < 0 or self.retry_jitter_seconds < 0:
            raise MistralOCR4ConfigurationError("OCR retry delays cannot be negative.")

    @property
    def contract_fingerprint(self) -> str:
        payload = {
            "model": self.model,
            "endpoint": self.endpoint,
            "maxPages": int(self.max_pages_per_request),
            "maxChunkBytes": int(self.max_chunk_bytes),
            "maxResponseBytes": int(self.max_response_bytes),
            "wordConfidence": bool(self.word_confidence),
            "schema": 1,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()


@dataclass(frozen=True, slots=True)
class OCR4Chunk:
    index: int
    physical_pages: tuple[int, ...]
    data: bytes
    sha256: str


@dataclass(frozen=True, slots=True)
class OCR4ChunkResult:
    chunk: OCR4Chunk
    root: Mapping[str, Any]
    request_id: str
    resolved_model: str
    retry_count: int
    network_attempts: int
    latency_ms: float
    estimated_cost_unit: Decimal
    estimated_cost_irt: Decimal
    from_checkpoint: bool = False


@dataclass(frozen=True, slots=True)
class OCR4DocumentResult:
    source_sha256: str
    page_count: int
    pages: tuple[Mapping[str, Any], ...]
    chunks: tuple[OCR4ChunkResult, ...]
    resolved_models: tuple[str, ...]
    request_ids: tuple[str, ...]
    provider_call_count: int
    retry_count: int
    checkpoint_reuse_count: int
    estimated_cost_unit: Decimal
    estimated_cost_irt: Decimal
    latency_ms: float


@dataclass(frozen=True, slots=True)
class HTTPResponse:
    status_code: int
    headers: Mapping[str, str]
    body: bytes


Transport = Callable[[str, Mapping[str, str], Mapping[str, Any], float], HTTPResponse]
ChunkCallback = Callable[[OCR4ChunkResult], None]


class OCRCheckpointStore(Protocol):
    def load(self, *, source_sha256: str, contract_fingerprint: str, chunk: OCR4Chunk) -> bytes | None: ...
    def save(self, *, source_sha256: str, contract_fingerprint: str, chunk: OCR4Chunk, payload: bytes) -> None: ...
    def delete(self, *, source_sha256: str, contract_fingerprint: str, chunk: OCR4Chunk) -> None: ...


class PrivateOCRCheckpointStore:
    """Persist validated OCR responses in the repository's private media store."""

    prefix = "exam-prep/source/ocr4-checkpoints/v1"

    def _name(self, *, source_sha256: str, contract_fingerprint: str, chunk: OCR4Chunk) -> str:
        return (
            f"{self.prefix}/{source_sha256}/{contract_fingerprint}/"
            f"chunk-{chunk.index:03d}-{chunk.sha256[:16]}.json"
        )

    def _storage(self):
        from django.core.files.storage import storages

        return storages["answer_sources"]

    def load(self, *, source_sha256: str, contract_fingerprint: str, chunk: OCR4Chunk) -> bytes | None:
        storage = self._storage()
        name = self._name(
            source_sha256=source_sha256,
            contract_fingerprint=contract_fingerprint,
            chunk=chunk,
        )
        try:
            if not storage.exists(name):
                return None
            with storage.open(name, "rb") as handle:
                return handle.read()
        except Exception:
            return None

    def save(self, *, source_sha256: str, contract_fingerprint: str, chunk: OCR4Chunk, payload: bytes) -> None:
        from django.core.files.base import ContentFile

        storage = self._storage()
        name = self._name(
            source_sha256=source_sha256,
            contract_fingerprint=contract_fingerprint,
            chunk=chunk,
        )
        try:
            if storage.exists(name):
                storage.delete(name)
            storage.save(name, ContentFile(payload))
        except Exception as exc:
            raise MistralOCR4ConfigurationError("Could not persist private OCR checkpoint.") from exc

    def delete(self, *, source_sha256: str, contract_fingerprint: str, chunk: OCR4Chunk) -> None:
        storage = self._storage()
        name = self._name(
            source_sha256=source_sha256,
            contract_fingerprint=contract_fingerprint,
            chunk=chunk,
        )
        try:
            storage.delete(name)
        except Exception:
            pass


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value or "0"))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_pdf(data: bytes) -> PdfReader:
    if not data or not data.lstrip().startswith(b"%PDF"):
        raise MistralOCR4ConfigurationError("OCR source must be a PDF.")
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:
        raise MistralOCR4ConfigurationError("The supplied PDF cannot be opened.") from exc
    if not reader.pages:
        raise MistralOCR4ConfigurationError("The supplied PDF has no pages.")
    if getattr(reader, "is_encrypted", False):
        raise MistralOCR4ConfigurationError("Encrypted PDFs are not supported.")
    return reader


def _selected_pdf_bytes(reader: PdfReader, pages: Sequence[int]) -> bytes:
    writer = PdfWriter()
    try:
        for page_number in pages:
            writer.add_page(reader.pages[int(page_number) - 1])
        output = io.BytesIO()
        writer.write(output)
        return output.getvalue()
    except Exception as exc:
        raise MistralOCR4ConfigurationError("Could not build a local OCR PDF chunk.") from exc


def plan_pdf_chunks(
    data: bytes,
    *,
    max_pages_per_request: int = OCR4_HARD_MAX_PAGES,
    max_chunk_bytes: int = OCR4_DEFAULT_CHUNK_BYTES,
) -> tuple[OCR4Chunk, ...]:
    """Plan all contiguous chunks before making the first paid request."""

    if not 1 <= int(max_pages_per_request) <= OCR4_HARD_MAX_PAGES:
        raise MistralOCR4ConfigurationError(
            f"max_pages_per_request must be 1..{OCR4_HARD_MAX_PAGES}."
        )
    if int(max_chunk_bytes) < 1:
        raise MistralOCR4ConfigurationError("max_chunk_bytes must be positive.")
    reader = _read_pdf(data)
    total = len(reader.pages)
    chunks: list[OCR4Chunk] = []
    start = 1
    index = 1
    while start <= total:
        low = start
        high = min(total, start + int(max_pages_per_request) - 1)
        best: tuple[tuple[int, ...], bytes] | None = None
        while low <= high:
            end = (low + high) // 2
            pages = tuple(range(start, end + 1))
            chunk_pdf = _selected_pdf_bytes(reader, pages)
            if len(chunk_pdf) <= int(max_chunk_bytes):
                best = (pages, chunk_pdf)
                low = end + 1
            else:
                high = end - 1
        if best is None:
            single = _selected_pdf_bytes(reader, (start,))
            raise MistralOCR4ConfigurationError(
                f"Physical page {start} alone is {len(single)} bytes, above the OCR chunk limit."
            )
        pages, chunk_pdf = best
        chunks.append(
            OCR4Chunk(
                index=index,
                physical_pages=pages,
                data=chunk_pdf,
                sha256=_sha256(chunk_pdf),
            )
        )
        start = pages[-1] + 1
        index += 1
    return tuple(chunks)


def _build_payload(chunk: OCR4Chunk, config: MistralOCR4Config) -> dict[str, Any]:
    encoded = base64.b64encode(chunk.data).decode("ascii")
    return {
        "model": config.model,
        "document": {
            "type": "document_url",
            "document_url": f"data:application/pdf;base64,{encoded}",
        },
        "include_image_base64": False,
        "extract_header": True,
        "extract_footer": True,
        "table_format": "html",
        "include_blocks": True,
        "confidence_scores_granularity": "word" if config.word_confidence else "page",
    }


def _default_transport(
    url: str,
    headers: Mapping[str, str],
    payload: Mapping[str, Any],
    timeout: float,
) -> HTTPResponse:
    try:
        import requests

        response = requests.post(
            url,
            headers=dict(headers),
            json=dict(payload),
            timeout=timeout,
        )
    except Exception as exc:
        raise MistralOCR4ProviderError(
            "AvalAI OCR transport failed.", retryable=True
        ) from exc
    return HTTPResponse(
        status_code=int(response.status_code),
        headers=dict(response.headers),
        body=bytes(response.content),
    )


def _request_id(headers: Mapping[str, Any], root: Mapping[str, Any] | None = None) -> str:
    for key, value in headers.items():
        if str(key).lower() == "x-request-id" and str(value).strip():
            return str(value).strip()
    if isinstance(root, Mapping):
        for key in ("request_id", "id"):
            value = root.get(key)
            if str(value or "").strip():
                return str(value).strip()
    return ""


def _retry_after(headers: Mapping[str, Any], config: MistralOCR4Config, attempt: int, random_value: Callable[[], float]) -> float:
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


def _response_root(response: HTTPResponse, config: MistralOCR4Config) -> Mapping[str, Any]:
    if len(response.body) > int(config.max_response_bytes):
        raise MistralOCR4ProviderError(
            "AvalAI OCR response exceeded the configured byte limit.",
            status_code=response.status_code,
            retryable=False,
            request_id=_request_id(response.headers),
        )
    try:
        root = json.loads(response.body)
    except (TypeError, ValueError, UnicodeDecodeError) as exc:
        raise MistralOCR4ProviderError(
            "AvalAI OCR returned a non-JSON response.",
            status_code=response.status_code,
            retryable=False,
            request_id=_request_id(response.headers),
        ) from exc
    if not isinstance(root, Mapping):
        raise MistralOCR4ProviderError(
            "AvalAI OCR response root is not an object.",
            status_code=response.status_code,
            retryable=False,
            request_id=_request_id(response.headers),
        )
    return root


def _validate_chunk_root(root: Mapping[str, Any], chunk: OCR4Chunk) -> None:
    pages = root.get("pages")
    if not isinstance(pages, list):
        raise MistralOCR4CoverageError("OCR response has no pages list.")
    seen: set[int] = set()
    for page in pages:
        if not isinstance(page, Mapping) or not isinstance(page.get("index"), int):
            raise MistralOCR4CoverageError("OCR response contains a page without integer index.")
        index = int(page["index"])
        if index in seen:
            raise MistralOCR4CoverageError("OCR response contains duplicate page indexes.")
        seen.add(index)
    expected = set(range(len(chunk.physical_pages)))
    if seen != expected:
        raise MistralOCR4CoverageError(
            f"OCR chunk page coverage mismatch (missing={sorted(expected-seen)}, extra={sorted(seen-expected)})."
        )


def _checkpoint_payload(
    *,
    source_sha256: str,
    contract_fingerprint: str,
    result: OCR4ChunkResult,
) -> bytes:
    payload = {
        "schemaVersion": _CHECKPOINT_SCHEMA,
        "sourceSha256": source_sha256,
        "contractFingerprint": contract_fingerprint,
        "chunkIndex": result.chunk.index,
        "chunkSha256": result.chunk.sha256,
        "physicalPages": list(result.chunk.physical_pages),
        "requestId": result.request_id,
        "resolvedModel": result.resolved_model,
        "latencyMs": result.latency_ms,
        "estimatedCostUnit": format(result.estimated_cost_unit, "f"),
        "estimatedCostIrt": format(result.estimated_cost_irt, "f"),
        "root": result.root,
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _checkpoint_result(
    raw: bytes,
    *,
    source_sha256: str,
    contract_fingerprint: str,
    chunk: OCR4Chunk,
    max_bytes: int,
) -> OCR4ChunkResult:
    if not raw or len(raw) > max_bytes + 4 * 1024 * 1024:
        raise MistralOCR4CoverageError("OCR checkpoint is empty or oversized.")
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError, UnicodeDecodeError) as exc:
        raise MistralOCR4CoverageError("OCR checkpoint is not valid JSON.") from exc
    if not isinstance(payload, Mapping):
        raise MistralOCR4CoverageError("OCR checkpoint root is invalid.")
    expected = {
        "schemaVersion": _CHECKPOINT_SCHEMA,
        "sourceSha256": source_sha256,
        "contractFingerprint": contract_fingerprint,
        "chunkIndex": chunk.index,
        "chunkSha256": chunk.sha256,
        "physicalPages": list(chunk.physical_pages),
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            raise MistralOCR4CoverageError(f"OCR checkpoint contract mismatch: {key}.")
    root = payload.get("root")
    if not isinstance(root, Mapping):
        raise MistralOCR4CoverageError("OCR checkpoint has no response root.")
    _validate_chunk_root(root, chunk)
    return OCR4ChunkResult(
        chunk=chunk,
        root=dict(root),
        request_id=str(payload.get("requestId") or ""),
        resolved_model=str(payload.get("resolvedModel") or ""),
        retry_count=0,
        network_attempts=0,
        latency_ms=float(payload.get("latencyMs") or 0.0),
        estimated_cost_unit=_decimal(payload.get("estimatedCostUnit")),
        estimated_cost_irt=_decimal(payload.get("estimatedCostIrt")),
        from_checkpoint=True,
    )


def _fetch_chunk(
    chunk: OCR4Chunk,
    *,
    config: MistralOCR4Config,
    api_key: str,
    transport: Transport,
    sleeper: Callable[[float], None],
    random_value: Callable[[], float],
) -> OCR4ChunkResult:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = _build_payload(chunk, config)
    started = time.monotonic()
    for attempt in range(1, int(config.max_attempts) + 1):
        try:
            response = transport(config.endpoint, headers, payload, float(config.timeout_seconds))
        except MistralOCR4ProviderError as exc:
            if attempt >= int(config.max_attempts) or not exc.retryable:
                raise MistralOCR4ProviderError(
                    str(exc),
                    status_code=exc.status_code,
                    retryable=exc.retryable,
                    attempts=attempt,
                    request_id=exc.request_id,
                ) from exc
            delay = _retry_after({}, config, attempt, random_value)
            if delay:
                sleeper(delay)
            continue
        except Exception as exc:
            if attempt >= int(config.max_attempts):
                raise MistralOCR4ProviderError(
                    "AvalAI OCR transport failed after configured attempts.",
                    retryable=True,
                    attempts=attempt,
                ) from exc
            delay = _retry_after({}, config, attempt, random_value)
            if delay:
                sleeper(delay)
            continue

        status = int(response.status_code)
        request_id = _request_id(response.headers)
        if not 200 <= status < 300:
            retryable = status in _RETRYABLE_HTTP_STATUSES
            if retryable and attempt < int(config.max_attempts):
                delay = _retry_after(response.headers, config, attempt, random_value)
                if delay:
                    sleeper(delay)
                continue
            raise MistralOCR4ProviderError(
                f"AvalAI OCR returned HTTP {status}.",
                status_code=status,
                retryable=retryable,
                attempts=attempt,
                request_id=request_id,
            )

        root = _response_root(response, config)
        try:
            _validate_chunk_root(root, chunk)
        except MistralOCR4CoverageError as exc:
            raise MistralOCR4ProviderError(
                "AvalAI OCR returned invalid page coverage.",
                status_code=status,
                retryable=False,
                attempts=attempt,
                request_id=_request_id(response.headers, root),
            ) from exc
        estimated = root.get("estimated_cost")
        estimated = estimated if isinstance(estimated, Mapping) else {}
        return OCR4ChunkResult(
            chunk=chunk,
            root=dict(root),
            request_id=_request_id(response.headers, root),
            resolved_model=str(root.get("model") or config.model),
            retry_count=attempt - 1,
            network_attempts=attempt,
            latency_ms=round((time.monotonic() - started) * 1000, 2),
            estimated_cost_unit=_decimal(estimated.get("unit")),
            estimated_cost_irt=_decimal(estimated.get("irt")),
            from_checkpoint=False,
        )
    raise MistralOCR4ProviderError("AvalAI OCR chunk did not complete.")


def _physical_pages(result: OCR4ChunkResult) -> tuple[Mapping[str, Any], ...]:
    pages = result.root.get("pages")
    assert isinstance(pages, list)
    by_index = {int(page["index"]): page for page in pages if isinstance(page, Mapping)}
    output: list[Mapping[str, Any]] = []
    for local_index, physical_page in enumerate(result.chunk.physical_pages):
        copied = dict(by_index[local_index])
        copied["index"] = physical_page - 1
        copied["sourcePhysicalPage"] = physical_page
        output.append(copied)
    return tuple(output)


def fetch_ocr4_document(
    data: bytes,
    *,
    config: MistralOCR4Config | None = None,
    api_key: str | None = None,
    checkpoint_store: OCRCheckpointStore | None = None,
    transport: Transport | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    random_value: Callable[[], float] = random.random,
    chunk_callback: ChunkCallback | None = None,
) -> OCR4DocumentResult:
    """Fetch a complete PDF with validated resume-at-chunk semantics."""

    selected = config or MistralOCR4Config.from_env()
    selected.validate()
    reader = _read_pdf(data)
    page_count = len(reader.pages)
    source_sha = _sha256(data)
    chunks = plan_pdf_chunks(
        data,
        max_pages_per_request=selected.max_pages_per_request,
        max_chunk_bytes=selected.max_chunk_bytes,
    )
    key = str(api_key or os.getenv("AVALAI_API_KEY") or "").strip()
    if not key:
        raise MistralOCR4ConfigurationError("AVALAI_API_KEY is required for live OCR.")
    selected_transport = transport or _default_transport
    store = checkpoint_store
    if selected.checkpoint_enabled and store is None:
        store = PrivateOCRCheckpointStore()

    results: list[OCR4ChunkResult] = []
    for chunk in chunks:
        result: OCR4ChunkResult | None = None
        if selected.checkpoint_enabled and store is not None:
            raw = store.load(
                source_sha256=source_sha,
                contract_fingerprint=selected.contract_fingerprint,
                chunk=chunk,
            )
            if raw:
                try:
                    result = _checkpoint_result(
                        raw,
                        source_sha256=source_sha,
                        contract_fingerprint=selected.contract_fingerprint,
                        chunk=chunk,
                        max_bytes=selected.max_response_bytes,
                    )
                except MistralOCR4CoverageError:
                    store.delete(
                        source_sha256=source_sha,
                        contract_fingerprint=selected.contract_fingerprint,
                        chunk=chunk,
                    )
                    result = None
        if result is None:
            result = _fetch_chunk(
                chunk,
                config=selected,
                api_key=key,
                transport=selected_transport,
                sleeper=sleeper,
                random_value=random_value,
            )
            if selected.checkpoint_enabled and store is not None:
                store.save(
                    source_sha256=source_sha,
                    contract_fingerprint=selected.contract_fingerprint,
                    chunk=chunk,
                    payload=_checkpoint_payload(
                        source_sha256=source_sha,
                        contract_fingerprint=selected.contract_fingerprint,
                        result=result,
                    ),
                )
        results.append(result)
        if chunk_callback is not None:
            chunk_callback(result)

    pages: list[Mapping[str, Any]] = []
    seen: set[int] = set()
    for result in results:
        for page in _physical_pages(result):
            physical = int(page["sourcePhysicalPage"])
            if physical in seen:
                raise MistralOCR4CoverageError(
                    f"OCR document contains duplicate physical page {physical}."
                )
            seen.add(physical)
            pages.append(page)
    expected = set(range(1, page_count + 1))
    if seen != expected:
        raise MistralOCR4CoverageError(
            f"OCR document coverage mismatch (missing={sorted(expected-seen)}, extra={sorted(seen-expected)})."
        )
    pages.sort(key=lambda page: int(page["sourcePhysicalPage"]))
    return OCR4DocumentResult(
        source_sha256=source_sha,
        page_count=page_count,
        pages=tuple(pages),
        chunks=tuple(results),
        resolved_models=tuple(sorted({r.resolved_model for r in results if r.resolved_model})),
        request_ids=tuple(r.request_id for r in results if r.request_id),
        provider_call_count=sum(r.network_attempts for r in results),
        retry_count=sum(r.retry_count for r in results),
        checkpoint_reuse_count=sum(r.from_checkpoint for r in results),
        estimated_cost_unit=sum((r.estimated_cost_unit for r in results), Decimal("0")),
        estimated_cost_irt=sum((r.estimated_cost_irt for r in results), Decimal("0")),
        latency_ms=round(sum(r.latency_ms for r in results if not r.from_checkpoint), 2),
    )


def document_root(result: OCR4DocumentResult) -> dict[str, Any]:
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


__all__ = [
    "AVALAI_OCR_ENDPOINT",
    "MISTRAL_OCR4_MODEL",
    "HTTPResponse",
    "MistralOCR4Config",
    "MistralOCR4ConfigurationError",
    "MistralOCR4CoverageError",
    "MistralOCR4Error",
    "MistralOCR4ProviderError",
    "OCR4Chunk",
    "OCR4ChunkResult",
    "OCR4DocumentResult",
    "OCRCheckpointStore",
    "PrivateOCRCheckpointStore",
    "document_root",
    "fetch_ocr4_document",
    "plan_pdf_chunks",
]
