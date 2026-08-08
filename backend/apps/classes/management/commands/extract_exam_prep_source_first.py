"""Run the bounded source-first OCR4 ingestion on a private PDF.

This command is intentionally separate from the teacher-facing pipeline until
the two supplied held-out PDFs have been inspected. It is the inexpensive,
resumable production-candidate path: one Mistral OCR4 request per <=30-page
chunk, deterministic geometry analysis, and source page/item crops. It never
uses a second LLM and never publishes OCR text into application records.
"""
from __future__ import annotations

from decimal import Decimal
import json
import os
from pathlib import Path
from typing import Any, Mapping

from django.core.management.base import BaseCommand, CommandError

from apps.classes.services.exam_prep_source_first import (
    OCR4_DEFAULT_CHUNK_BYTES,
    OCR4_DEFAULT_RESPONSE_BYTES,
    OCR4_PAGE_PRICE_UNIT,
    OCR4Chunk,
    OCR4ChunkResult,
    OCR4DocumentResult,
    SourceFirstConfigurationError,
    SourceFirstOCRConfig,
    _atomic_json,
    _physical_pages_from_chunk,
    _read_pdf,
    _request_chunk,
    _sha256,
    analyze_source_result,
    merge_chunk_results,
    plan_pdf_chunks,
    write_source_first_bundle,
)
from apps.classes.services.exam_prep_v4_avalai_ocr import (
    AvalAIOCRLimits,
    OCRHTTPResponse,
    parse_ocr_response,
)


def _nonempty(path: Path) -> bool:
    return path.exists() and any(path.iterdir())


def _checkpoint_payload(
    *,
    pdf_path: Path,
    source_sha256: str,
    config: SourceFirstOCRConfig,
    chunks: tuple[OCR4Chunk, ...],
    completed: Mapping[int, Mapping[str, Any]],
    status: str,
    error: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "pipeline": "exam_prep_source_first",
        "status": status,
        "sourceFilename": pdf_path.name,
        "sourceSha256": source_sha256,
        "contractFingerprint": config.contract_fingerprint,
        "requestedModel": config.model,
        "plannedChunks": [
            {
                "chunkIndex": chunk.index,
                "physicalPages": list(chunk.physical_pages),
                "pdfBytes": len(chunk.data),
                "pdfSha256": chunk.sha256,
            }
            for chunk in chunks
        ],
        "completedChunks": [
            dict(completed[index]) for index in sorted(completed)
        ],
        "error": dict(error or {}),
    }


def _load_completed_chunk(
    *,
    chunk: OCR4Chunk,
    output_dir: Path,
    config: SourceFirstOCRConfig,
) -> OCR4ChunkResult | None:
    raw_path = output_dir / "chunks" / f"chunk-{chunk.index:02d}.raw.json"
    if not raw_path.is_file():
        return None
    try:
        body = raw_path.read_bytes()
        root = json.loads(body)
        if not isinstance(root, Mapping):
            return None
        limits = AvalAIOCRLimits(
            max_input_bytes=config.max_chunk_bytes,
            max_response_bytes=config.max_response_bytes,
            max_pages=len(chunk.physical_pages),
            timeout_seconds=config.timeout_seconds,
        )
        parsed = parse_ocr_response(
            response=OCRHTTPResponse(
                status_code=200,
                headers={
                    "x-request-id": str(root.get("request_id") or "")
                },
                body=body,
            ),
            expected_pages=tuple(range(len(chunk.physical_pages))),
            limits=limits,
            latency_ms=0,
        )
        # Validate the local page set before allowing a resume to skip a call.
        probe = OCR4ChunkResult(chunk=chunk, root=root, parsed=parsed)
        _physical_pages_from_chunk(probe)
        checkpoint = output_dir / "checkpoint.json"
        retry_count = 0
        if checkpoint.is_file():
            try:
                state = json.loads(checkpoint.read_text(encoding="utf-8"))
                for item in state.get("completedChunks") or []:
                    if isinstance(item, Mapping) and int(item.get("chunkIndex") or 0) == chunk.index:
                        retry_count = int(item.get("retryCount") or 0)
                        break
            except (OSError, TypeError, ValueError):
                retry_count = 0
        estimated = root.get("estimated_cost")
        estimated = estimated if isinstance(estimated, Mapping) else {}
        estimated_unit = Decimal(str(estimated.get("unit") or "0"))
        if estimated_unit <= 0:
            estimated_unit = chunk.expected_cost_unit
        return OCR4ChunkResult(
            chunk=chunk,
            root=root,
            parsed=parsed,
            retry_count=retry_count,
            estimated_cost_unit=estimated_unit,
            estimated_cost_irt=Decimal(str(estimated.get("irt") or "0")),
        )
    except Exception:
        # A partial/corrupt response is not trusted as a checkpoint. Keep it on
        # disk for diagnosis, but fetch this chunk again on --resume.
        return None


class Command(BaseCommand):
    help = "Extract a private PDF with resumable, source-first AvalAI Mistral OCR4."

    def add_arguments(self, parser):
        parser.add_argument("--pdf", required=True)
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--model", default=os.getenv("EXAM_PREP_SOURCE_FIRST_MODEL") or "mistral-ocr-4-0")
        parser.add_argument("--max-pages-per-request", type=int, default=30)
        parser.add_argument("--max-chunk-bytes", type=int, default=OCR4_DEFAULT_CHUNK_BYTES)
        parser.add_argument("--max-response-bytes", type=int, default=OCR4_DEFAULT_RESPONSE_BYTES)
        parser.add_argument("--timeout-seconds", type=float, default=600.0)
        parser.add_argument(
            "--max-attempts",
            type=int,
            default=1,
            help="Transport/transient attempts per chunk; 1 avoids duplicate paid calls.",
        )
        parser.add_argument(
            "--max-planned-cost-unit",
            type=Decimal,
            default=Decimal("0.50"),
            help="Fail before network if base OCR cost times max attempts exceeds this unit cap.",
        )
        parser.add_argument("--render-dpi", type=int, default=200)
        parser.add_argument("--no-page-images", action="store_true")
        parser.add_argument("--resume", action="store_true")
        parser.add_argument("--archive", action="store_true")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--allow-private-transmission", action="store_true")

    def handle(self, *args, **options):
        if not options.get("dry_run") and not options.get("allow_private_transmission"):
            raise CommandError(
                "Live OCR transmits the private PDF to AvalAI; pass "
                "--allow-private-transmission explicitly."
            )
        pdf_path = Path(options["pdf"]).expanduser().resolve()
        output_dir = Path(options["output_dir"]).expanduser().resolve()
        if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
            raise CommandError("--pdf must point to an existing PDF file.")
        if _nonempty(output_dir) and not options.get("resume"):
            raise CommandError("--output-dir must be absent or empty (or use --resume).")
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            raw_word_confidence = (
                os.getenv("EXAM_PREP_SOURCE_FIRST_WORD_CONFIDENCE", "1") or "1"
            )
            config = SourceFirstOCRConfig(
                model=str(options["model"] or "").strip(),
                endpoint=(os.getenv("AVALAI_OCR_ENDPOINT") or "https://api.avalai.ir/v1/ocr").strip(),
                max_pages_per_request=int(options["max_pages_per_request"]),
                max_chunk_bytes=int(options["max_chunk_bytes"]),
                max_response_bytes=int(options["max_response_bytes"]),
                timeout_seconds=float(options["timeout_seconds"]),
                max_attempts=int(options["max_attempts"]),
                word_confidence=raw_word_confidence.strip().lower()
                in {"1", "true", "yes", "on"},
            )
            config.validate()
            chunks = plan_pdf_chunks(
                pdf_path,
                max_pages_per_request=config.max_pages_per_request,
                max_chunk_bytes=config.max_chunk_bytes,
            )
            source_sha = _sha256(pdf_path.read_bytes())
            planned_cost = sum(
                (chunk.expected_cost_unit for chunk in chunks),
                Decimal("0"),
            ) * int(config.max_attempts)
            if planned_cost > Decimal(str(options["max_planned_cost_unit"])):
                raise SourceFirstConfigurationError(
                    f"Planned OCR cost {planned_cost} exceeds the configured cap "
                    f"{options['max_planned_cost_unit']}; no request was sent."
                )
        except SourceFirstConfigurationError as exc:
            raise CommandError(str(exc)) from exc

        plan = {
            "pageCount": sum(len(chunk.physical_pages) for chunk in chunks),
            "chunkCount": len(chunks),
            "chunkPageCounts": [len(chunk.physical_pages) for chunk in chunks],
            "plannedCostUnitUpperBound": format(planned_cost, "f"),
            "sourceSha256": source_sha,
            "model": config.model,
            "wordConfidence": config.word_confidence,
            "contractFingerprint": config.contract_fingerprint,
        }
        _atomic_json(output_dir / "plan.safe.json", plan)
        checkpoint_path = output_dir / "checkpoint.json"
        if options.get("dry_run"):
            self.stdout.write(json.dumps(plan, ensure_ascii=False, indent=2))
            return

        if options.get("resume"):
            if not checkpoint_path.is_file():
                raise CommandError(
                    "--resume requires a checkpoint.json created by this command; "
                    "use a new output directory for an unrelated bundle."
                )
            try:
                checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise CommandError("checkpoint.json is unreadable; use a new output directory.") from exc
            if not isinstance(checkpoint, Mapping):
                raise CommandError("checkpoint.json has an invalid root object.")
            if (
                str(checkpoint.get("sourceSha256") or "") != source_sha
                or str(checkpoint.get("contractFingerprint") or "")
                != config.contract_fingerprint
            ):
                raise CommandError(
                    "The resume directory belongs to a different PDF or OCR contract."
                )

        api_key = (os.getenv("AVALAI_API_KEY") or "").strip()
        if not api_key:
            raise CommandError("AVALAI_API_KEY is required.")
        (output_dir / "chunks").mkdir(exist_ok=True)
        completed: dict[int, dict[str, Any]] = {}
        results: list[OCR4ChunkResult] = []
        for chunk in chunks:
            loaded = (
                _load_completed_chunk(
                    chunk=chunk,
                    output_dir=output_dir,
                    config=config,
                )
                if options.get("resume")
                else None
            )
            if loaded is not None:
                results.append(loaded)
                completed[chunk.index] = {
                    "chunkIndex": chunk.index,
                    "physicalPages": list(chunk.physical_pages),
                    "retryCount": loaded.retry_count,
                    "reused": True,
                }
                continue
            try:
                fetched = _request_chunk(
                    chunk,
                    config=config,
                    api_key=api_key,
                )
            except Exception as exc:
                error = {
                    "type": type(exc).__name__,
                    "statusCode": getattr(exc, "status_code", None),
                    "retryable": bool(getattr(exc, "retryable", False)),
                    "attempts": int(getattr(exc, "attempts", 1)),
                    "chunkIndex": chunk.index,
                    "physicalPages": list(chunk.physical_pages),
                }
                _atomic_json(
                    checkpoint_path,
                    _checkpoint_payload(
                        pdf_path=pdf_path,
                        source_sha256=source_sha,
                        config=config,
                        chunks=chunks,
                        completed=completed,
                        status="failed",
                        error=error,
                    ),
                )
                raise CommandError(
                    f"OCR4 chunk {chunk.index} failed; successful chunks are checkpointed "
                    f"in {output_dir}. Re-run with --resume after checking the error."
                ) from exc
            raw_path = output_dir / "chunks" / f"chunk-{chunk.index:02d}.raw.json"
            _atomic_json(raw_path, dict(fetched.root))
            _atomic_json(
                output_dir / "chunks" / f"chunk-{chunk.index:02d}.headers.safe.json",
                {
                    "requestId": fetched.parsed.request_id,
                    "resolvedModel": fetched.parsed.model,
                    "statusCode": 200,
                },
            )
            results.append(fetched)
            completed[chunk.index] = {
                "chunkIndex": chunk.index,
                "physicalPages": list(chunk.physical_pages),
                "retryCount": fetched.retry_count,
                "reused": False,
            }
            _atomic_json(
                checkpoint_path,
                _checkpoint_payload(
                    pdf_path=pdf_path,
                    source_sha256=source_sha,
                    config=config,
                    chunks=chunks,
                    completed=completed,
                    status="running",
                ),
            )
            self.stdout.write(
                f"chunk={chunk.index}/{len(chunks)} pages={len(chunk.physical_pages)} "
                f"retry={fetched.retry_count}"
            )

        document = merge_chunk_results(
            source_sha256=source_sha,
            page_count=len(_read_pdf(pdf_path)[0].pages),
            chunk_results=results,
        )
        analysis = analyze_source_result(document)
        manifest = write_source_first_bundle(
            pdf_path=pdf_path,
            result=document,
            analysis=analysis,
            output_dir=output_dir,
            render_dpi=int(options["render_dpi"]),
            write_page_images=not options.get("no_page_images"),
            max_pages_per_chunk=config.max_pages_per_request,
            max_chunk_bytes=config.max_chunk_bytes,
        )
        _atomic_json(
            checkpoint_path,
            _checkpoint_payload(
                pdf_path=pdf_path,
                source_sha256=source_sha,
                config=config,
                chunks=chunks,
                completed=completed,
                status="completed",
            ),
        )
        archive = None
        if options.get("archive"):
            import shutil

            archive = shutil.make_archive(str(output_dir), "zip", root_dir=output_dir)
        self.stdout.write(
            self.style.SUCCESS(
                "Source-first OCR4 completed: "
                f"pages={document.page_count}, chunks={len(document.chunks)}, "
                f"questions={manifest['metrics']['questionRegions']}, "
                f"solutions={manifest['metrics']['solutionRegions']}, "
                f"estimated_unit={manifest['metrics']['estimatedCostUnit']}, "
                f"output={output_dir}"
                + (f", archive={archive}" if archive else "")
            )
        )
