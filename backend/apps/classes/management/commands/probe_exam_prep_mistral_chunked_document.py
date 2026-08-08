from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
from typing import Any, Mapping

from django.core.management.base import BaseCommand, CommandError
from pypdf import PdfReader
import pypdfium2 as pdfium
import requests

from apps.classes.management.commands.probe_exam_prep_mistral_layout import (
    _selected_pdf_bytes,
    _write_page_bundle,
)
from apps.classes.management.commands.probe_exam_prep_mistral_word_confidence import (
    _confidence_aggregate,
)
from apps.classes.services.exam_prep_v4_avalai_ocr import (
    AVALAI_OCR_ENDPOINT,
    AVALAI_OCR_PINNED_MODEL,
    AvalAIOCRLimits,
    OCRHTTPResponse,
    build_ocr_payload,
    parse_ocr_response,
)


_AVALAI_AZURE_OCR4_MAX_PAGES = 30


def _safe_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in {"set-cookie", "authorization"}
    }


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value or "0"))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _plan_chunks(
    pdf_path: Path,
    *,
    page_count: int,
    max_pages: int,
    max_bytes: int,
) -> list[tuple[tuple[int, ...], bytes]]:
    chunks: list[tuple[tuple[int, ...], bytes]] = []
    start = 1
    while start <= page_count:
        upper = min(page_count, start + max_pages - 1)
        low = start
        high = upper
        best: tuple[tuple[int, ...], bytes] | None = None
        while low <= high:
            end = (low + high) // 2
            pages = tuple(range(start, end + 1))
            data, _total = _selected_pdf_bytes(pdf_path, pages)
            if len(data) <= max_bytes:
                best = (pages, data)
                low = end + 1
            else:
                high = end - 1
        if best is None:
            single, _total = _selected_pdf_bytes(pdf_path, (start,))
            raise CommandError(
                f"Physical page {start} alone is {len(single)} bytes and exceeds "
                f"the per-request diagnostic cap of {max_bytes} bytes."
            )
        chunks.append(best)
        start = best[0][-1] + 1
    return chunks


def _failure_archive(
    *,
    output_dir: Path,
    chunk_index: int,
    pages: tuple[int, ...],
    status_code: int | None,
    reason: str,
) -> str:
    (output_dir / "failure.json").write_text(
        json.dumps(
            {
                "privateDiagnosticBundle": True,
                "productionPipelineChanged": False,
                "failed": True,
                "failedChunkIndex": chunk_index,
                "failedOriginalPages": list(pages),
                "httpStatus": status_code,
                "reason": reason,
                "retryCount": 0,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return shutil.make_archive(str(output_dir), "zip", root_dir=output_dir)


class Command(BaseCommand):
    help = (
        "Process one full PDF through AvalAI Mistral OCR 4 using the minimum number "
        "of physical mini-PDF chunks required by the current 30-page Azure route. "
        "Each chunk uses blocks + word confidence, with no annotation and no retry."
    )

    def add_arguments(self, parser):
        parser.add_argument("--pdf", required=True)
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--model", default=AVALAI_OCR_PINNED_MODEL)
        parser.add_argument("--dpi", type=int, default=200)
        parser.add_argument("--timeout-seconds", type=float, default=600.0)
        parser.add_argument(
            "--max-pages-per-request",
            type=int,
            default=_AVALAI_AZURE_OCR4_MAX_PAGES,
        )
        parser.add_argument(
            "--max-chunk-bytes",
            type=int,
            default=28 * 1024 * 1024,
        )
        parser.add_argument(
            "--max-response-bytes",
            type=int,
            default=120 * 1024 * 1024,
        )
        parser.add_argument("--allow-private-transmission", action="store_true")

    def handle(self, *args, **options):
        if not options.get("allow_private_transmission"):
            raise CommandError("Live OCR requires --allow-private-transmission.")
        api_key = (os.getenv("AVALAI_API_KEY") or "").strip()
        if not api_key:
            raise CommandError("AVALAI_API_KEY is required.")

        pdf_path = Path(options["pdf"]).expanduser().resolve()
        if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
            raise CommandError("--pdf must point to an existing PDF file.")
        try:
            reader = PdfReader(str(pdf_path))
            page_count = len(reader.pages)
        except Exception as exc:
            raise CommandError("The supplied PDF cannot be opened.") from exc
        if page_count < 1:
            raise CommandError("The supplied PDF has no pages.")

        max_pages = int(options["max_pages_per_request"])
        if not 1 <= max_pages <= _AVALAI_AZURE_OCR4_MAX_PAGES:
            raise CommandError(
                "--max-pages-per-request must be between 1 and 30 for the current "
                "AvalAI/Azure OCR 4 route."
            )
        max_chunk_bytes = int(options["max_chunk_bytes"])
        if max_chunk_bytes < 1:
            raise CommandError("--max-chunk-bytes must be positive.")
        dpi = int(options["dpi"])
        if not 96 <= dpi <= 300:
            raise CommandError("--dpi must be between 96 and 300.")

        output_dir = Path(options["output_dir"]).expanduser().resolve()
        if output_dir.exists() and any(output_dir.iterdir()):
            raise CommandError("Output directory must be absent or empty.")
        output_dir.mkdir(parents=True, exist_ok=True)

        chunks = _plan_chunks(
            pdf_path,
            page_count=page_count,
            max_pages=max_pages,
            max_bytes=max_chunk_bytes,
        )
        endpoint = (os.getenv("AVALAI_OCR_ENDPOINT") or AVALAI_OCR_ENDPOINT).strip()
        model = str(options["model"] or "").strip()
        merged_pages: list[dict[str, Any]] = []
        chunk_summaries: list[dict[str, Any]] = []
        total_unit = Decimal("0")
        total_irt = Decimal("0")
        resolved_models: set[str] = set()
        total_latency_ms = 0.0

        global_request = {
            "privateDiagnosticBundle": True,
            "productionPipelineChanged": False,
            "model": model,
            "endpoint": endpoint,
            "originalPdfPageCount": page_count,
            "selectedOriginalPages": list(range(1, page_count + 1)),
            "maxPagesPerRequest": max_pages,
            "maxChunkBytes": max_chunk_bytes,
            "plannedRequestCount": len(chunks),
            "confidenceScoresGranularity": "word",
            "includeBlocks": True,
            "extractHeader": True,
            "extractFooter": True,
            "tableFormat": "html",
            "includeImageBase64": False,
        }
        (output_dir / "request.safe.json").write_text(
            json.dumps(global_request, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        for chunk_index, (pages, chunk_pdf) in enumerate(chunks, start=1):
            limits = AvalAIOCRLimits(
                max_input_bytes=max_chunk_bytes,
                max_response_bytes=int(options["max_response_bytes"]),
                max_pages=len(pages),
                timeout_seconds=float(options["timeout_seconds"]),
            )
            payload = build_ocr_payload(
                data=chunk_pdf,
                media_type="application/pdf",
                model=model,
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
                    "confidence_scores_granularity": "word",
                }
            )
            chunk_sha = hashlib.sha256(chunk_pdf).hexdigest()
            safe_request = {
                **payload,
                "document": {
                    "type": "document_url",
                    "document_url": "<redacted mini-PDF data URL>",
                    "selectedPdfBytes": len(chunk_pdf),
                    "selectedPdfSha256": chunk_sha,
                },
                "source": {
                    "chunkIndex": chunk_index,
                    "selectedOriginalPages": list(pages),
                },
            }
            (output_dir / f"request.chunk-{chunk_index:02d}.safe.json").write_text(
                json.dumps(safe_request, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            started = time.monotonic()
            try:
                response = requests.post(
                    endpoint,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=limits.timeout_seconds,
                )
            except requests.RequestException as exc:
                archive = _failure_archive(
                    output_dir=output_dir,
                    chunk_index=chunk_index,
                    pages=pages,
                    status_code=None,
                    reason=type(exc).__name__,
                )
                raise CommandError(
                    f"AvalAI OCR transport failed; no retry was attempted. "
                    f"Failure bundle={archive}"
                ) from exc

            latency_ms = round((time.monotonic() - started) * 1000, 2)
            total_latency_ms += latency_ms
            raw_name = f"response.chunk-{chunk_index:02d}.raw.json"
            headers_name = f"response.chunk-{chunk_index:02d}.headers.safe.json"
            (output_dir / raw_name).write_bytes(response.content)
            (output_dir / headers_name).write_text(
                json.dumps(_safe_headers(response.headers), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            if not response.ok:
                archive = _failure_archive(
                    output_dir=output_dir,
                    chunk_index=chunk_index,
                    pages=pages,
                    status_code=response.status_code,
                    reason="provider_http_error",
                )
                raise CommandError(
                    f"AvalAI OCR returned HTTP {response.status_code}; raw body and "
                    f"headers were saved. Failure bundle={archive}"
                )

            try:
                root = response.json()
            except ValueError as exc:
                archive = _failure_archive(
                    output_dir=output_dir,
                    chunk_index=chunk_index,
                    pages=pages,
                    status_code=response.status_code,
                    reason="provider_non_json",
                )
                raise CommandError(
                    f"AvalAI OCR returned non-JSON. Failure bundle={archive}"
                ) from exc
            if not isinstance(root, Mapping):
                archive = _failure_archive(
                    output_dir=output_dir,
                    chunk_index=chunk_index,
                    pages=pages,
                    status_code=response.status_code,
                    reason="provider_root_not_object",
                )
                raise CommandError(
                    f"AvalAI OCR returned an invalid root object. Failure bundle={archive}"
                )

            parsed = parse_ocr_response(
                response=OCRHTTPResponse(
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    body=response.content,
                ),
                expected_pages=tuple(range(len(pages))),
                limits=limits,
                latency_ms=latency_ms,
            )
            resolved_models.add(parsed.model)
            estimated = root.get("estimated_cost")
            estimated = estimated if isinstance(estimated, Mapping) else {}
            total_unit += _decimal(estimated.get("unit"))
            total_irt += _decimal(estimated.get("irt"))

            raw_pages = {
                int(page.get("index")): page
                for page in root.get("pages") or []
                if isinstance(page, Mapping) and isinstance(page.get("index"), int)
            }
            for local_index, original_page in enumerate(pages):
                raw_page = raw_pages.get(local_index)
                if raw_page is None:
                    continue
                merged = dict(raw_page)
                merged["index"] = original_page - 1
                merged_pages.append(merged)

            chunk_summaries.append(
                {
                    "chunkIndex": chunk_index,
                    "originalPages": list(pages),
                    "selectedPdfBytes": len(chunk_pdf),
                    "selectedPdfSha256": chunk_sha,
                    "latencyMs": latency_ms,
                    "requestId": parsed.request_id,
                    "resolvedModel": parsed.model,
                    "usagePagesProcessed": parsed.usage_pages_processed,
                    "usageDocumentBytes": parsed.usage_document_bytes,
                    "estimatedCost": estimated,
                    "rawResponseFile": raw_name,
                    "safeHeadersFile": headers_name,
                }
            )

        merged_pages.sort(key=lambda page: int(page.get("index") or 0))
        merged_root: dict[str, Any] = {
            "pages": merged_pages,
            "model": (
                next(iter(resolved_models))
                if len(resolved_models) == 1
                else ",".join(sorted(resolved_models))
            ),
            "document_annotation": None,
            "usage_info": {
                "pages_processed": len(merged_pages),
                "doc_size_bytes": sum(
                    int(chunk.get("selectedPdfBytes") or 0)
                    for chunk in chunk_summaries
                ),
            },
            "estimated_cost": {
                "unit": format(total_unit, "f"),
                "irt": format(total_irt, "f"),
            },
            "diagnostic_chunks": chunk_summaries,
        }
        (output_dir / "response.raw.json").write_text(
            json.dumps(merged_root, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        raw_by_global = {
            int(page.get("index")): page
            for page in merged_pages
            if isinstance(page.get("index"), int)
        }
        document = pdfium.PdfDocument(str(pdf_path))
        page_summaries: list[dict[str, Any]] = []
        try:
            scale = dpi / 72.0
            for original_page in range(1, page_count + 1):
                raw_page = raw_by_global.get(original_page - 1)
                if raw_page is None:
                    page_summaries.append(
                        {
                            "originalPageNumber": original_page,
                            "providerPageIndex": original_page - 1,
                            "missingProviderPage": True,
                        }
                    )
                    continue
                page = document[original_page - 1]
                try:
                    bitmap = page.render(scale=scale)
                    try:
                        image = bitmap.to_pil().convert("RGB")
                    finally:
                        bitmap.close()
                finally:
                    page.close()
                try:
                    page_summaries.append(
                        _write_page_bundle(
                            output_dir=output_dir,
                            original_page_number=original_page,
                            raw_page=raw_page,
                            image=image,
                        )
                    )
                finally:
                    image.close()
        finally:
            document.close()

        confidence_by_index = {
            item.get("providerPageIndex"): item
            for item in _confidence_aggregate(merged_root)
        }
        for page in page_summaries:
            page.update(confidence_by_index.get(page.get("providerPageIndex"), {}))

        total_blocks = sum(int(page.get("blockCount") or 0) for page in page_summaries)
        total_bboxes = sum(
            int(page.get("blockBBoxCount") or 0) for page in page_summaries
        )
        manifest = {
            "schemaVersion": 3,
            "privateDiagnosticBundle": True,
            "productionPipelineChanged": False,
            "providerRequestCount": len(chunks),
            "minimumRequestCountForCurrentLimits": True,
            "retryCount": 0,
            "confidenceGranularity": "word",
            "endpoint": endpoint,
            "requestedModel": model,
            "resolvedModels": sorted(resolved_models),
            "latencyMs": round(total_latency_ms, 2),
            "pageCount": page_count,
            "selectedOriginalPages": list(range(1, page_count + 1)),
            "chunkCount": len(chunks),
            "chunks": chunk_summaries,
            "estimatedCost": {
                "unit": format(total_unit, "f"),
                "irt": format(total_irt, "f"),
            },
            "pages": page_summaries,
            "totals": {
                "blocks": total_blocks,
                "blockBBoxes": total_bboxes,
                "bboxCoverage": (
                    round(total_bboxes / total_blocks, 6) if total_blocks else 0.0
                ),
                "words": sum(
                    int(page.get("wordScoreCount") or 0) for page in page_summaries
                ),
                "wordsBelow60": sum(
                    int(page.get("below60") or 0) for page in page_summaries
                ),
                "wordsBelow80": sum(
                    int(page.get("below80") or 0) for page in page_summaries
                ),
                "wordsBelow95": sum(
                    int(page.get("below95") or 0) for page in page_summaries
                ),
            },
            "acceptance": {
                "allPhysicalPagesReturned": len(merged_pages) == page_count,
                "noRetry": True,
                "blocksReturned": total_blocks > 0,
                "wordConfidenceReturned": any(
                    int(page.get("wordScoreCount") or 0) > 0
                    for page in page_summaries
                ),
                "chunkPageLimitRespected": all(
                    len(chunk.get("originalPages") or []) <= max_pages
                    for chunk in chunk_summaries
                ),
                "chunkByteLimitRespected": all(
                    int(chunk.get("selectedPdfBytes") or 0) <= max_chunk_bytes
                    for chunk in chunk_summaries
                ),
            },
        }
        manifest["acceptance"]["passed"] = all(manifest["acceptance"].values())
        (output_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (output_dir / "README.txt").write_text(
            "PRIVATE CHUNKED FULL-DOCUMENT OCR DIAGNOSTIC BUNDLE\n"
            "The PDF was physically split locally to respect the current 30-page "
            "AvalAI/Azure OCR4 input limit.\n"
            "No annotation or automatic retry was used.\n"
            "response.chunk-*.raw.json files are unmodified provider responses; "
            "response.raw.json is the merged page-index-normalized diagnostic view.\n"
            "Do not commit this bundle.\n",
            encoding="utf-8",
        )
        archive = shutil.make_archive(str(output_dir), "zip", root_dir=output_dir)
        self.stdout.write(
            self.style.SUCCESS(
                "Mistral OCR chunked full-document probe completed: "
                f"requests={len(chunks)}, pages={page_count}, blocks={total_blocks}, "
                f"bundle={archive}"
            )
        )
        if not manifest["acceptance"]["passed"]:
            raise CommandError(
                "Chunked full-document bundle was written, but acceptance failed."
            )
