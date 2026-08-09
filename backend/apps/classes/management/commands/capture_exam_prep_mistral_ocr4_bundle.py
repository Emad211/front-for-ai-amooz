from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import shutil
import tempfile

from django.core.management.base import BaseCommand, CommandError
from pypdf import PdfReader

from apps.classes.services.exam_prep_mistral_ocr_transport import (
    MistralOCR4Config,
    MistralOCR4Error,
    OCR4Chunk,
    document_root,
    fetch_ocr4_document,
)


class _LocalOCRCheckpointStore:
    """Resumable diagnostic checkpoints with no Django/storage dependency."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(
        self,
        *,
        source_sha256: str,
        contract_fingerprint: str,
        chunk: OCR4Chunk,
    ) -> Path:
        return (
            self.root
            / source_sha256
            / contract_fingerprint
            / f"chunk-{chunk.index:03d}-{chunk.sha256[:16]}.json"
        )

    def load(self, *, source_sha256: str, contract_fingerprint: str, chunk: OCR4Chunk) -> bytes | None:
        path = self._path(
            source_sha256=source_sha256,
            contract_fingerprint=contract_fingerprint,
            chunk=chunk,
        )
        try:
            return path.read_bytes() if path.is_file() else None
        except OSError:
            return None

    def save(
        self,
        *,
        source_sha256: str,
        contract_fingerprint: str,
        chunk: OCR4Chunk,
        payload: bytes,
    ) -> None:
        path = self._path(
            source_sha256=source_sha256,
            contract_fingerprint=contract_fingerprint,
            chunk=chunk,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(payload)
        temporary.replace(path)

    def delete(self, *, source_sha256: str, contract_fingerprint: str, chunk: OCR4Chunk) -> None:
        path = self._path(
            source_sha256=source_sha256,
            contract_fingerprint=contract_fingerprint,
            chunk=chunk,
        )
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


class Command(BaseCommand):
    help = (
        "Run only Mistral OCR4 for one PDF and save a reusable diagnostic ZIP. "
        "No Stage-3/Stage-4 LLM calls are made and automatic paid OCR retry is disabled. "
        "Validated OCR chunks are checkpointed beside the requested ZIP so a later rerun "
        "does not re-buy completed chunks."
    )

    def add_arguments(self, parser):
        parser.add_argument("--pdf", required=True)
        parser.add_argument("--output", required=True)

    def handle(self, *args, **options):
        pdf_path = Path(options["pdf"]).expanduser().resolve()
        output = Path(options["output"]).expanduser().resolve()
        if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
            raise CommandError("--pdf must point to an existing PDF file.")
        if output.suffix.lower() != ".zip":
            raise CommandError("--output must end with .zip")
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            raise CommandError("--output already exists; remove it or choose another path.")

        try:
            data = pdf_path.read_bytes()
            local_page_count = len(PdfReader(str(pdf_path)).pages)
        except Exception as exc:
            raise CommandError("The supplied PDF cannot be opened.") from exc

        # The diagnostic command must never touch Django/S3 checkpoint storage.
        # It owns a local sibling checkpoint directory instead. max_attempts=1
        # prevents an implicit second paid provider request for one chunk.
        checkpoint_root = output.with_suffix(output.suffix + ".checkpoints")
        checkpoint_store = _LocalOCRCheckpointStore(checkpoint_root)
        config = replace(
            MistralOCR4Config.from_env(),
            max_attempts=1,
            checkpoint_enabled=True,
        )
        try:
            result = fetch_ocr4_document(
                data,
                config=config,
                checkpoint_store=checkpoint_store,
            )
        except MistralOCR4Error as exc:
            raise CommandError(str(exc)) from exc
        if result.page_count != local_page_count:
            raise CommandError(
                f"OCR page count mismatch ({result.page_count} != {local_page_count})."
            )

        root = document_root(result)
        manifest = {
            "schemaVersion": 3,
            "bundleType": "exam_prep_mistral_ocr4_reusable",
            "sourcePdfSha256": result.source_sha256,
            "originalPdfPageCount": result.page_count,
            "pageCount": result.page_count,
            "providerCalls": result.provider_call_count,
            "retryCount": result.retry_count,
            "automaticPaidRetryAllowed": False,
            "checkpointBackend": "local_diagnostic",
            "checkpointReusedChunks": result.checkpoint_reuse_count,
            "requestIds": list(result.request_ids),
            "resolvedModels": list(result.resolved_models),
            "estimatedCostUnit": format(result.estimated_cost_unit, "f"),
            "estimatedCostIrt": format(result.estimated_cost_irt, "f"),
            "latencyMs": round(float(result.latency_ms or 0), 3),
            "chunkCount": len(result.chunks),
            "stage3ProviderCalls": 0,
            "stage4ProviderCalls": 0,
        }

        with tempfile.TemporaryDirectory(prefix="ai-amooz-ocr4-bundle-") as tmp:
            root_dir = Path(tmp)
            (root_dir / "response.raw.json").write_text(
                json.dumps(root, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            (root_dir / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            archive_base = str(output.with_suffix(""))
            generated = Path(shutil.make_archive(archive_base, "zip", root_dir=root_dir))
            if generated != output:
                generated.replace(output)

        # Once the reusable ZIP exists, the per-chunk local checkpoints are no
        # longer needed. On any earlier failure they deliberately remain so the
        # next invocation can resume without paying for completed chunks again.
        shutil.rmtree(checkpoint_root, ignore_errors=True)

        self.stdout.write(
            self.style.SUCCESS(
                "OCR4 bundle captured: "
                f"pages={result.page_count}, providerCalls={result.provider_call_count}, "
                f"checkpointReused={result.checkpoint_reuse_count}, "
                f"retries={result.retry_count}, estimatedCostUsd={manifest['estimatedCostUnit']}, "
                f"bundle={output}"
            )
        )
