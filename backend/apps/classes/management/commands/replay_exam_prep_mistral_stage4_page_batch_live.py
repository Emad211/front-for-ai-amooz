from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from typing import Any, Callable

from django.core.management.base import BaseCommand, CommandError
from pypdf import PdfReader

from apps.classes.management.commands.plan_exam_prep_mistral_stage4 import _number_set
from apps.classes.management.commands.replay_exam_prep_mistral_stage4_live import (
    _cached_transcriber,
)
from apps.classes.management.commands.replay_exam_prep_mistral_visual_stage3 import (
    _DiagnosticStore,
    _diagnostic_result,
    _load_bundle_root,
)
from apps.classes.services import exam_prep_mistral_stage2_core as stage2
from apps.classes.services import exam_prep_mistral_stage4_page_batch as stage4_page
from apps.classes.services import exam_prep_mistral_region_transcriber as region_transcriber
from apps.classes.services.exam_prep_mistral_page_batch_transcriber import (
    BatchItem,
    PageBatchResult,
    transcribe_page_batch,
)
from apps.classes.services.exam_prep_mistral_production import analyze_mistral_document_evidence
from apps.classes.services.exam_prep_mistral_risk_engine_v2 import score_region_risks
from apps.classes.services.exam_prep_mistral_stage4 import _render_crop
from apps.classes.services.exam_prep_mistral_stage4_runtime import verify_and_repair_risky_regions
from apps.classes.services.exam_prep_mistral_visual_reconcile import (
    VisualPipelineConfig,
    reconcile_mistral_source_visuals,
)
from apps.classes.services.exam_prep_page_records import assemble_page_extractions
from apps.classes.services.exam_prep_page_source import attach_source_regions
from apps.classes.services.exam_prep_question_verifier import rebuild_assembly_quality


PageBatchCall = Callable[..., PageBatchResult]


def _safe(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or ""))[:100] or "model"


def _batch_cache_path(root: Path, *, page_number: int, targets, model: str) -> Path:
    target_ids = [decision.target_id for decision, _payload in targets]
    digest = hashlib.sha256("|".join(target_ids).encode("utf-8")).hexdigest()[:12]
    return root / f"p{page_number:03d}-{_safe(model)}-{digest}.private.json"


def _serialize_batch(value: PageBatchResult) -> dict[str, Any]:
    return {
        "status": "success",
        "pageNumber": value.page_number,
        "model": value.model,
        "requestId": value.request_id,
        "usage": value.usage,
        "estimatedCost": value.estimated_cost,
        "items": [item.model_dump() for item in value.items],
    }


def _deserialize_batch(value: dict[str, Any]) -> PageBatchResult:
    return PageBatchResult(
        page_number=int(value.get("pageNumber") or 0),
        model=str(value.get("model") or ""),
        items=tuple(BatchItem.model_validate(item) for item in (value.get("items") or [])),
        request_id=str(value.get("requestId") or ""),
        usage={str(k): int(v or 0) for k, v in dict(value.get("usage") or {}).items()},
        estimated_cost={str(k): float(v or 0) for k, v in dict(value.get("estimatedCost") or {}).items()},
    )


def _cached_page_batch(
    *,
    cache_dir: Path,
    base_call: PageBatchCall,
    counters: dict[str, float],
) -> PageBatchCall:
    cache_dir.mkdir(parents=True, exist_ok=True)

    def call(**kwargs):
        selected_model = str(kwargs.get("model") or os.getenv("EXAM_PREP_STAGE4_PRIMARY_MODEL") or "gemini-3-flash-preview")
        path = _batch_cache_path(
            cache_dir,
            page_number=int(kwargs.get("page_number") or 0),
            targets=kwargs.get("targets") or [],
            model=selected_model,
        )
        if path.is_file():
            cached = json.loads(path.read_text(encoding="utf-8"))
            counters["pageCacheHits"] = counters.get("pageCacheHits", 0) + 1
            if cached.get("status") == "success":
                result = _deserialize_batch(cached)
                counters["logicalEstimatedCostUnit"] = counters.get("logicalEstimatedCostUnit", 0.0) + float(result.estimated_cost.get("unit") or 0)
                counters["logicalEstimatedCostIrt"] = counters.get("logicalEstimatedCostIrt", 0.0) + float(result.estimated_cost.get("irt") or 0)
                return result
            raise RuntimeError(f"cached_page_batch_failure:{cached.get('errorType') or 'unknown'}")

        counters["networkPageRequests"] = counters.get("networkPageRequests", 0) + 1
        try:
            result = base_call(**kwargs)
        except Exception as exc:
            path.write_text(
                json.dumps(
                    {
                        "status": "failure",
                        "pageNumber": kwargs.get("page_number"),
                        "model": selected_model,
                        "targetIds": [d.target_id for d, _p in (kwargs.get("targets") or [])],
                        "errorType": type(exc).__name__,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            raise
        path.write_text(json.dumps(_serialize_batch(result), ensure_ascii=False, indent=2), encoding="utf-8")
        unit = float(result.estimated_cost.get("unit") or 0)
        irt = float(result.estimated_cost.get("irt") or 0)
        counters["networkEstimatedCostUnit"] = counters.get("networkEstimatedCostUnit", 0.0) + unit
        counters["networkEstimatedCostIrt"] = counters.get("networkEstimatedCostIrt", 0.0) + irt
        counters["logicalEstimatedCostUnit"] = counters.get("logicalEstimatedCostUnit", 0.0) + unit
        counters["logicalEstimatedCostIrt"] = counters.get("logicalEstimatedCostIrt", 0.0) + irt
        return result

    return call


class Command(BaseCommand):
    help = (
        "Replay calibrated Stage 4 with all suspicious crops from one physical page "
        "batched into one native Gemini structured-output request. OCR calls are zero."
    )

    def add_arguments(self, parser):
        parser.add_argument("--pdf", required=True)
        parser.add_argument("--bundle", required=True)
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--title", default="Stage 4 page-batch live replay")
        parser.add_argument("--recovered-solution-targets", default="")
        parser.add_argument("--unresolved-solution-targets", default="")
        parser.add_argument("--max-page-batches", type=int, default=24)
        parser.add_argument("--max-secondary-calls", type=int, default=6)
        parser.add_argument("--resume", action="store_true")
        parser.add_argument("--allow-private-transmission", action="store_true")

    def handle(self, *args, **options):
        if not options.get("allow_private_transmission"):
            raise CommandError("Pass --allow-private-transmission to send private source crops.")

        pdf_path = Path(options["pdf"]).expanduser().resolve()
        bundle_path = Path(options["bundle"]).expanduser().resolve()
        output_dir = Path(options["output_dir"]).expanduser().resolve()
        resume = bool(options.get("resume"))
        if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
            raise CommandError("--pdf must point to an existing PDF file.")
        if not bundle_path.is_file() or bundle_path.suffix.lower() != ".zip":
            raise CommandError("--bundle must point to an existing OCR ZIP bundle.")
        if output_dir.exists() and any(output_dir.iterdir()) and not resume:
            raise CommandError("--output-dir is non-empty; use --resume or a new directory.")
        output_dir.mkdir(parents=True, exist_ok=True)

        maximum_pages = max(1, min(40, int(options.get("max_page_batches") or 24)))
        maximum_secondary = max(0, min(12, int(options.get("max_secondary_calls") or 6)))
        recovered = _number_set(options.get("recovered_solution_targets") or "")
        unresolved = _number_set(options.get("unresolved_solution_targets") or "")
        if recovered & unresolved:
            raise CommandError("A target cannot be both recovered and unresolved.")

        try:
            pdf_data = pdf_path.read_bytes()
            page_count = len(PdfReader(str(pdf_path)).pages)
        except Exception as exc:
            raise CommandError("The supplied PDF cannot be opened.") from exc
        root, manifest = _load_bundle_root(bundle_path)
        bundle_page_count = int(
            manifest.get("originalPdfPageCount")
            or manifest.get("pageCount")
            or len(root.get("pages") or [])
            or 0
        )
        if bundle_page_count and bundle_page_count != page_count:
            raise CommandError(f"PDF/bundle page count mismatch ({page_count} != {bundle_page_count}).")

        result = _diagnostic_result(pdf_data=pdf_data, root=root, page_count=page_count)
        replay_root = dict(root)
        replay_root["pages"] = [dict(page) for page in result.pages]
        evidence = analyze_mistral_document_evidence(
            replay_root,
            original_page_numbers=list(range(1, page_count + 1)),
        )
        page_extractions = stage2._build_page_extractions(
            result=result,
            evidence=evidence,
            recovered_targets={},
        )
        assembled = assemble_page_extractions(
            page_extractions,
            title=str(options.get("title") or "Stage 4 page-batch live replay"),
        )
        assembled = attach_source_regions(assembled, pages=page_extractions)
        assembled = rebuild_assembly_quality(assembled)

        visual_store = _DiagnosticStore(output_dir / "stage3-visuals")
        assembled, visual_stats, visual_audit = reconcile_mistral_source_visuals(
            assembled,
            pdf_data=pdf_data,
            ocr_pages=result.pages,
            layout=evidence.layout,
            source_sha256=result.source_sha256,
            store=visual_store,
            config=VisualPipelineConfig(),
        )

        decisions = score_region_risks(
            projection=assembled.projection,
            layout=evidence.layout,
            recovered_solution_targets=recovered,
            unresolved_solution_targets=unresolved,
        )
        suspicious = [item for item in decisions if item.suspicious]
        suspicious_pages = sorted({item.page_number for item in suspicious})
        if len(suspicious_pages) > maximum_pages:
            raise CommandError(
                f"pageBatchCount={len(suspicious_pages)} exceeds max-page-batches={maximum_pages}."
            )

        crop_dir = output_dir / "source-crops"
        crop_dir.mkdir(parents=True, exist_ok=True)
        risk_rows: list[dict[str, Any]] = []
        for decision in decisions:
            row = decision.safe_dict()
            if decision.suspicious:
                crop_name = f"{decision.target_id}.png"
                (crop_dir / crop_name).write_bytes(_render_crop(pdf_data, decision))
                row["cropFile"] = f"source-crops/{crop_name}"
            risk_rows.append(row)
        (output_dir / "risk-plan.safe.json").write_text(
            json.dumps(risk_rows, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        old_page_cap = os.environ.get("EXAM_PREP_STAGE4_MAX_PAGE_BATCH_CALLS")
        old_secondary_cap = os.environ.get("EXAM_PREP_STAGE4_MAX_SECONDARY_CALLS")
        old_usage_logging = os.environ.get("EXAM_PREP_STAGE4_USAGE_DB_LOGGING")
        old_page_call = stage4_page.transcribe_page_batch
        old_secondary_call = stage4_page.transcribe_source_region
        counters: dict[str, float] = {
            "networkPageRequests": 0,
            "pageCacheHits": 0,
            "networkSecondaryRequests": 0,
            "secondaryCacheHits": 0,
            "networkEstimatedCostUnit": 0.0,
            "networkEstimatedCostIrt": 0.0,
            "logicalEstimatedCostUnit": 0.0,
            "logicalEstimatedCostIrt": 0.0,
        }
        os.environ["EXAM_PREP_STAGE4_MAX_PAGE_BATCH_CALLS"] = str(maximum_pages)
        os.environ["EXAM_PREP_STAGE4_MAX_SECONDARY_CALLS"] = str(maximum_secondary)
        os.environ["EXAM_PREP_STAGE4_USAGE_DB_LOGGING"] = "0"
        stage4_page.transcribe_page_batch = _cached_page_batch(
            cache_dir=output_dir / "page-provider-cache",
            base_call=transcribe_page_batch,
            counters=counters,
        )
        secondary_counter: dict[str, int] = {
            "networkRequests": 0,
            "networkPrimaryRequests": 0,
            "networkSecondaryRequests": 0,
            "cacheHits": 0,
        }
        stage4_page.transcribe_source_region = _cached_transcriber(
            cache_dir=output_dir / "secondary-provider-cache",
            base_call=region_transcriber.transcribe_source_region,
            counters=secondary_counter,
        )
        try:
            updated, stage4_audit = verify_and_repair_risky_regions(
                assembled,
                pdf_data=pdf_data,
                layout=evidence.layout,
                recovered_solution_targets=recovered,
                unresolved_solution_targets=unresolved,
            )
        finally:
            stage4_page.transcribe_page_batch = old_page_call
            stage4_page.transcribe_source_region = old_secondary_call
            for name, old in (
                ("EXAM_PREP_STAGE4_MAX_PAGE_BATCH_CALLS", old_page_cap),
                ("EXAM_PREP_STAGE4_MAX_SECONDARY_CALLS", old_secondary_cap),
                ("EXAM_PREP_STAGE4_USAGE_DB_LOGGING", old_usage_logging),
            ):
                if old is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = old

        counters["networkSecondaryRequests"] = int(secondary_counter.get("networkRequests") or 0)
        counters["secondaryCacheHits"] = int(secondary_counter.get("cacheHits") or 0)
        stats = dict(stage4_audit.get("stats") or {})
        provider_requests_this_run = int(counters.get("networkPageRequests") or 0) + int(counters.get("networkSecondaryRequests") or 0)

        (output_dir / "stage4.audit.safe.json").write_text(
            json.dumps(stage4_audit, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (output_dir / "projection.stage4.private.json").write_text(
            json.dumps(updated.projection, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        manifest_out = {
            "schemaVersion": 3,
            "privateDiagnosticBundle": True,
            "ocrProviderRequests": 0,
            "providerRequestsThisRun": provider_requests_this_run,
            "networkPageBatchRequestsThisRun": int(counters.get("networkPageRequests") or 0),
            "networkSecondaryRequestsThisRun": int(counters.get("networkSecondaryRequests") or 0),
            "pageBatchCacheHits": int(counters.get("pageCacheHits") or 0),
            "secondaryCacheHits": int(counters.get("secondaryCacheHits") or 0),
            "estimatedPrimaryCostUnitThisRun": round(float(counters.get("networkEstimatedCostUnit") or 0), 8),
            "estimatedPrimaryCostIrtThisRun": round(float(counters.get("networkEstimatedCostIrt") or 0), 2),
            "sourcePdfSha256": result.source_sha256,
            "pageCount": page_count,
            "riskRegionCount": len(decisions),
            "suspiciousRegionCount": len(suspicious),
            "suspiciousPageCount": len(suspicious_pages),
            "pageBatches": int(stats.get("pageBatches") or 0),
            "primaryTargets": int(stats.get("primaryTargets") or 0),
            "secondaryCalls": int(stats.get("secondaryCalls") or 0),
            "verified": int(stats.get("verified") or 0),
            "repaired": int(stats.get("repaired") or 0),
            "unresolved": int(stats.get("unresolved") or 0),
            "deferred": int(stats.get("deferred") or 0),
            "stage3Stats": visual_stats,
            "stage3CriticalIssueCodes": list(visual_audit.get("criticalIssueCodes") or []),
        }
        (output_dir / "manifest.json").write_text(
            json.dumps(manifest_out, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        archive = shutil.make_archive(str(output_dir), "zip", root_dir=output_dir)
        self.stdout.write(
            self.style.SUCCESS(
                "Stage 4 page-batch replay completed: ocrProviderRequests=0, "
                f"targets={len(suspicious)}, pages={len(suspicious_pages)}, "
                f"newPageRequests={int(counters.get('networkPageRequests') or 0)}, "
                f"newSecondaryRequests={int(counters.get('networkSecondaryRequests') or 0)}, "
                f"repaired={int(stats.get('repaired') or 0)}, "
                f"unresolved={int(stats.get('unresolved') or 0)}, bundle={archive}"
            )
        )
