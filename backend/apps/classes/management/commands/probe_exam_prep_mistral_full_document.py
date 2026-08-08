from __future__ import annotations

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


class Command(BaseCommand):
    help = (
        "Send exactly one full-document AvalAI Mistral OCR 4 request with blocks and "
        "word confidence, then write a private page bundle for local architecture analysis."
    )

    def add_arguments(self, parser):
        parser.add_argument("--pdf", required=True)
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--model", default=AVALAI_OCR_PINNED_MODEL)
        parser.add_argument("--dpi", type=int, default=200)
        parser.add_argument("--timeout-seconds", type=float, default=600.0)
        parser.add_argument("--max-pages", type=int, default=120)
        parser.add_argument("--max-input-bytes", type=int, default=80 * 1024 * 1024)
        parser.add_argument("--max-response-bytes", type=int, default=200 * 1024 * 1024)
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
        data = pdf_path.read_bytes()
        if not data.startswith(b"%PDF"):
            raise CommandError("The supplied file is not a PDF.")
        if len(data) > int(options["max_input_bytes"]):
            raise CommandError("Full PDF exceeds --max-input-bytes.")
        try:
            reader = PdfReader(str(pdf_path))
            page_count = len(reader.pages)
        except Exception as exc:
            raise CommandError("The supplied PDF cannot be opened.") from exc
        max_pages = max(1, int(options["max_pages"]))
        if page_count < 1 or page_count > max_pages:
            raise CommandError(
                f"PDF has {page_count} pages; full-document diagnostic cap is {max_pages}."
            )
        dpi = int(options["dpi"])
        if not 96 <= dpi <= 300:
            raise CommandError("--dpi must be between 96 and 300.")

        output_dir = Path(options["output_dir"]).expanduser().resolve()
        if output_dir.exists() and any(output_dir.iterdir()):
            raise CommandError("Output directory must be absent or empty.")
        output_dir.mkdir(parents=True, exist_ok=True)

        limits = AvalAIOCRLimits(
            max_input_bytes=int(options["max_input_bytes"]),
            max_response_bytes=int(options["max_response_bytes"]),
            max_pages=page_count,
            timeout_seconds=float(options["timeout_seconds"]),
        )
        model = str(options["model"] or "").strip()
        payload = build_ocr_payload(
            data=data,
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
        source_sha = hashlib.sha256(data).hexdigest()
        safe_request = {
            **payload,
            "document": {
                "type": "document_url",
                "document_url": "<redacted full PDF data URL>",
                "pdfBytes": len(data),
                "pdfSha256": source_sha,
            },
            "source": {
                "fullDocument": True,
                "originalPdfPageCount": page_count,
                "selectedOriginalPages": list(range(1, page_count + 1)),
            },
        }
        (output_dir / "request.safe.json").write_text(
            json.dumps(safe_request, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        endpoint = (os.getenv("AVALAI_OCR_ENDPOINT") or AVALAI_OCR_ENDPOINT).strip()
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
            raise CommandError("AvalAI OCR request failed; no retry was attempted.") from exc
        latency_ms = round((time.monotonic() - started) * 1000, 2)
        (output_dir / "response.raw.json").write_bytes(response.content)
        (output_dir / "response.headers.safe.json").write_text(
            json.dumps(
                {
                    key: value
                    for key, value in response.headers.items()
                    if key.lower() not in {"set-cookie", "authorization"}
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        if not response.ok:
            raise CommandError(
                f"AvalAI OCR returned HTTP {response.status_code}; raw body was saved."
            )
        try:
            root = response.json()
        except ValueError as exc:
            raise CommandError("AvalAI OCR returned non-JSON; raw body was saved.") from exc
        if not isinstance(root, Mapping):
            raise CommandError("AvalAI OCR root response is not an object.")

        parsed = parse_ocr_response(
            response=OCRHTTPResponse(
                status_code=response.status_code,
                headers=dict(response.headers),
                body=response.content,
            ),
            expected_pages=tuple(range(page_count)),
            limits=limits,
            latency_ms=latency_ms,
        )
        raw_by_index = {
            page.get("index"): page
            for page in root.get("pages") or []
            if isinstance(page, Mapping) and isinstance(page.get("index"), int)
        }

        document = pdfium.PdfDocument(str(pdf_path))
        page_summaries: list[dict[str, Any]] = []
        try:
            scale = dpi / 72.0
            for provider_index in range(page_count):
                raw_page = raw_by_index.get(provider_index)
                if raw_page is None:
                    page_summaries.append(
                        {
                            "originalPageNumber": provider_index + 1,
                            "providerPageIndex": provider_index,
                            "missingProviderPage": True,
                        }
                    )
                    continue
                page = document[provider_index]
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
                            original_page_number=provider_index + 1,
                            raw_page=raw_page,
                            image=image,
                        )
                    )
                finally:
                    image.close()
        finally:
            document.close()

        confidence_pages = _confidence_aggregate(root)
        confidence_by_index = {
            item.get("providerPageIndex"): item for item in confidence_pages
        }
        for page in page_summaries:
            page.update(confidence_by_index.get(page.get("providerPageIndex"), {}))

        total_blocks = sum(int(page.get("blockCount") or 0) for page in page_summaries)
        total_bboxes = sum(int(page.get("blockBBoxCount") or 0) for page in page_summaries)
        manifest = {
            "schemaVersion": 2,
            "privateDiagnosticBundle": True,
            "productionPipelineChanged": False,
            "fullDocumentSingleRequest": True,
            "providerRequestCount": 1,
            "retryCount": 0,
            "confidenceGranularity": "word",
            "endpoint": endpoint,
            "requestedModel": model,
            "resolvedModel": parsed.model,
            "requestId": parsed.request_id,
            "latencyMs": latency_ms,
            "pageCount": page_count,
            "pdfBytes": len(data),
            "pdfSha256": source_sha,
            "responseBytes": len(response.content),
            "usagePagesProcessed": parsed.usage_pages_processed,
            "usageDocumentBytes": parsed.usage_document_bytes,
            "estimatedCost": root.get("estimated_cost"),
            "issues": [
                {"code": issue.code, "pageIndex": issue.page_index}
                for issue in parsed.issues
            ],
            "pages": page_summaries,
            "totals": {
                "blocks": total_blocks,
                "blockBBoxes": total_bboxes,
                "bboxCoverage": round(total_bboxes / total_blocks, 6) if total_blocks else 0.0,
                "words": sum(int(page.get("wordScoreCount") or 0) for page in page_summaries),
                "wordsBelow60": sum(int(page.get("below60") or 0) for page in page_summaries),
                "wordsBelow80": sum(int(page.get("below80") or 0) for page in page_summaries),
                "wordsBelow95": sum(int(page.get("below95") or 0) for page in page_summaries),
            },
            "acceptance": {
                "oneRequestOnly": True,
                "allPagesReturned": len(parsed.pages) == page_count,
                "allPagesUsageReported": parsed.usage_pages_processed in {None, page_count},
                "blocksReturned": total_blocks > 0,
                "wordConfidenceReturned": any(
                    int(page.get("wordScoreCount") or 0) > 0 for page in page_summaries
                ),
            },
        }
        manifest["acceptance"]["passed"] = all(manifest["acceptance"].values())
        (output_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (output_dir / "README.txt").write_text(
            "PRIVATE FULL-DOCUMENT OCR DIAGNOSTIC BUNDLE\n"
            "Exactly one OCR request was used. No annotation or retry was used.\n"
            "The ZIP contains source page images and OCR text; do not commit it.\n",
            encoding="utf-8",
        )
        archive = shutil.make_archive(str(output_dir), "zip", root_dir=output_dir)
        self.stdout.write(
            self.style.SUCCESS(
                "Mistral OCR full-document probe completed: "
                f"request=1, pages={page_count}, blocks={total_blocks}, bundle={archive}"
            )
        )
        if not manifest["acceptance"]["passed"]:
            raise CommandError(
                "Full-document probe bundle was written but acceptance failed."
            )
