from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
from typing import Any, Callable

from django.core.management.base import BaseCommand, CommandError
from pypdf import PdfReader

from apps.classes.management.commands.plan_exam_prep_mistral_stage4 import _number_set
from apps.classes.management.commands.replay_exam_prep_mistral_visual_stage3 import (
    _DiagnosticStore,
    _diagnostic_result,
    _load_bundle_root,
)
from apps.classes.services import exam_prep_mistral_stage2_core as stage2
from apps.classes.services import exam_prep_mistral_stage4 as stage4_impl
from apps.classes.services import exam_prep_mistral_region_transcriber as transcriber
from apps.classes.services.exam_prep_mistral_production import analyze_mistral_document_evidence
from apps.classes.services.exam_prep_mistral_risk_engine_v2 import score_region_risks
from apps.classes.services.exam_prep_mistral_stage4 import _render_crop
from apps.classes.services.exam_prep_mistral_stage4_runtime import (
    verify_and_repair_risky_regions,
)
from apps.classes.services.exam_prep_mistral_visual_reconcile import (
    VisualPipelineConfig,
    reconcile_mistral_source_visuals,
)
from apps.classes.services.exam_prep_page_records import assemble_page_extractions
from apps.classes.services.exam_prep_page_source import attach_source_regions
from apps.classes.services.exam_prep_question_verifier import rebuild_assembly_quality


Transcriber = Callable[..., transcriber.RegionTranscriptionResult]


def _safe_model_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or ""))[:100] or "model"


def _cache_path(
    root: Path,
    *,
    kind: str,
    question_number: int,
    page_number: int,
    model: str,
    thinking_minimal: bool,
) -> Path:
    mode = "minimal" if thinking_minimal else "standard"
    return root / (
        f"{kind[0]}-{question_number:03d}-p{page_number:03d}-"
        f"{_safe_model_name(model)}-{mode}.private.json"
    )


def _serialize_result(value: transcriber.RegionTranscriptionResult) -> dict[str, Any]:
    return {
        "status": "success",
        "kind": value.kind,
        "questionNumber": value.question_number,
        "pageNumber": value.page_number,
        "model": value.model,
        "transcript": value.transcript,
        "responseId": value.response_id,
        "inputTokens": value.input_tokens,
        "outputTokens": value.output_tokens,
        "totalTokens": value.total_tokens,
        "reasoningTokens": value.reasoning_tokens,
    }


def _deserialize_result(value: dict[str, Any]) -> transcriber.RegionTranscriptionResult:
    return transcriber.RegionTranscriptionResult(
        kind=str(value.get("kind") or "question"),
        question_number=int(value.get("questionNumber") or 0),
        page_number=int(value.get("pageNumber") or 0),
        model=str(value.get("model") or ""),
        transcript=dict(value.get("transcript") or {}),
        response_id=str(value.get("responseId") or ""),
        input_tokens=int(value.get("inputTokens") or 0),
        output_tokens=int(value.get("outputTokens") or 0),
        total_tokens=int(value.get("totalTokens") or 0),
        reasoning_tokens=int(value.get("reasoningTokens") or 0),
    )


def _cached_transcriber(
    *,
    cache_dir: Path,
    base_call: Transcriber,
    counters: dict[str, int],
) -> Transcriber:
    cache_dir.mkdir(parents=True, exist_ok=True)

    def call(**kwargs):
        path = _cache_path(cache_dir, **kwargs)
        if path.is_file():
            try:
                cached = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                raise RuntimeError("invalid_stage4_provider_cache") from exc
            counters["cacheHits"] = counters.get("cacheHits", 0) + 1
            if cached.get("status") == "success":
                return _deserialize_result(cached)
            error_type = str(cached.get("errorType") or "cached_provider_failure")
            raise RuntimeError(f"cached_stage4_provider_failure:{error_type}")

        counters["networkRequests"] = counters.get("networkRequests", 0) + 1
        if bool(kwargs.get("thinking_minimal")):
            counters["networkPrimaryRequests"] = counters.get("networkPrimaryRequests", 0) + 1
        else:
            counters["networkSecondaryRequests"] = counters.get("networkSecondaryRequests", 0) + 1
        try:
            result = base_call(**kwargs)
        except Exception as exc:
            path.write_text(
                json.dumps(
                    {
                        "status": "failure",
                        "kind": kwargs.get("kind"),
                        "questionNumber": kwargs.get("question_number"),
                        "pageNumber": kwargs.get("page_number"),
                        "model": kwargs.get("model"),
                        "thinkingMinimal": bool(kwargs.get("thinking_minimal")),
                        "errorType": type(exc).__name__,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            raise
        path.write_text(
            json.dumps(_serialize_result(result), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return result

    return call


class Command(BaseCommand):
    help = (
        "Replay Stage 4 against an existing successful OCR4 bundle. OCR provider "
        "requests are zero; only bounded suspicious-region Gemini/GPT calls are made. "
        "Provider results are checkpointed so --resume never re-buys completed calls."
    )

    def add_arguments(self, parser):
        parser.add_argument("--pdf", required=True)
        parser.add_argument("--bundle", required=True)
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--title", default="Stage 4 live replay")
        parser.add_argument("--recovered-solution-targets", default="")
        parser.add_argument("--unresolved-solution-targets", default="")
        parser.add_argument("--max-primary-calls", type=int, default=50)
        parser.add_argument("--max-secondary-calls", type=int, default=6)
        parser.add_argument("--resume", action="store_true")
        parser.add_argument("--allow-private-transmission", action="store_true")

    def handle(self, *args, **options):
        if not options.get("allow_private_transmission"):
            raise CommandError(
                "Live Stage 4 sends private source crops to the configured provider; "
                "pass --allow-private-transmission explicitly."
            )

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

        maximum_primary = max(1, min(56, int(options.get("max_primary_calls") or 50)))
        maximum_secondary = max(0, min(6, int(options.get("max_secondary_calls") or 6)))
        recovered = _number_set(options.get("recovered_solution_targets") or "")
        unresolved = _number_set(options.get("unresolved_solution_targets") or "")
        if recovered & unresolved:
            raise CommandError("A target cannot be both recovered and unresolved.")

        output_dir.mkdir(parents=True, exist_ok=True)
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
            raise CommandError(
                f"PDF/bundle page count mismatch ({page_count} != {bundle_page_count})."
            )

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
            title=str(options.get("title") or "Stage 4 live replay"),
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
        if len(suspicious) > maximum_primary:
            raise CommandError(
                "Stage-4 live preflight refused provider transmission: "
                f"suspicious={len(suspicious)} exceeds max-primary-calls={maximum_primary}."
            )

        crop_dir = output_dir / "source-crops"
        crop_dir.mkdir(parents=True, exist_ok=True)
        risk_rows: list[dict[str, Any]] = []
        for decision in decisions:
            row = decision.safe_dict()
            if decision.suspicious:
                crop_name = f"{decision.target_id}.png"
                try:
                    (crop_dir / crop_name).write_bytes(_render_crop(pdf_data, decision))
                    row["cropFile"] = f"source-crops/{crop_name}"
                except Exception as exc:
                    row["cropError"] = type(exc).__name__
            risk_rows.append(row)
        (output_dir / "risk-plan.safe.json").write_text(
            json.dumps(risk_rows, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        old_primary = os.environ.get("EXAM_PREP_STAGE4_MAX_PRIMARY_CALLS")
        old_secondary = os.environ.get("EXAM_PREP_STAGE4_MAX_SECONDARY_CALLS")
        old_usage_logging = os.environ.get("EXAM_PREP_STAGE4_USAGE_DB_LOGGING")
        old_transcriber = stage4_impl.transcribe_source_region
        counters: dict[str, int] = {
            "networkRequests": 0,
            "networkPrimaryRequests": 0,
            "networkSecondaryRequests": 0,
            "cacheHits": 0,
        }
        os.environ["EXAM_PREP_STAGE4_MAX_PRIMARY_CALLS"] = str(maximum_primary)
        os.environ["EXAM_PREP_STAGE4_MAX_SECONDARY_CALLS"] = str(maximum_secondary)
        # Diagnostic replay has no requirement for Django DB-backed usage rows;
        # response token counts are persisted in stage4.audit.safe.json/cache.
        os.environ["EXAM_PREP_STAGE4_USAGE_DB_LOGGING"] = "0"
        stage4_impl.transcribe_source_region = _cached_transcriber(
            cache_dir=output_dir / "provider-cache",
            base_call=transcriber.transcribe_source_region,
            counters=counters,
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
            stage4_impl.transcribe_source_region = old_transcriber
            if old_primary is None:
                os.environ.pop("EXAM_PREP_STAGE4_MAX_PRIMARY_CALLS", None)
            else:
                os.environ["EXAM_PREP_STAGE4_MAX_PRIMARY_CALLS"] = old_primary
            if old_secondary is None:
                os.environ.pop("EXAM_PREP_STAGE4_MAX_SECONDARY_CALLS", None)
            else:
                os.environ["EXAM_PREP_STAGE4_MAX_SECONDARY_CALLS"] = old_secondary
            if old_usage_logging is None:
                os.environ.pop("EXAM_PREP_STAGE4_USAGE_DB_LOGGING", None)
            else:
                os.environ["EXAM_PREP_STAGE4_USAGE_DB_LOGGING"] = old_usage_logging

        stats = dict(stage4_audit.get("stats") or {})
        logical_primary_calls = int(stats.get("primaryCalls") or 0)
        logical_secondary_calls = int(stats.get("secondaryCalls") or 0)
        network_requests = int(counters.get("networkRequests") or 0)

        (output_dir / "stage4.audit.safe.json").write_text(
            json.dumps(stage4_audit, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (output_dir / "projection.stage4.private.json").write_text(
            json.dumps(updated.projection, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        manifest_out = {
            "schemaVersion": 2,
            "privateDiagnosticBundle": True,
            "ocrProviderRequests": 0,
            "providerRequestsThisRun": network_requests,
            "networkPrimaryRequestsThisRun": int(counters.get("networkPrimaryRequests") or 0),
            "networkSecondaryRequestsThisRun": int(counters.get("networkSecondaryRequests") or 0),
            "providerCacheHits": int(counters.get("cacheHits") or 0),
            "logicalPrimaryCalls": logical_primary_calls,
            "logicalSecondaryCalls": logical_secondary_calls,
            "maxPrimaryCalls": maximum_primary,
            "maxSecondaryCalls": maximum_secondary,
            "sourcePdfSha256": result.source_sha256,
            "pageCount": page_count,
            "riskRegionCount": len(decisions),
            "suspiciousRegionCount": len(suspicious),
            "verified": int(stats.get("verified") or 0),
            "repaired": int(stats.get("repaired") or 0),
            "unresolved": int(stats.get("unresolved") or 0),
            "deferred": int(stats.get("deferred") or 0),
            "recoveredSolutionTargets": sorted(recovered),
            "unresolvedSolutionTargets": sorted(unresolved),
            "stage3Stats": visual_stats,
            "stage3CriticalIssueCodes": list(visual_audit.get("criticalIssueCodes") or []),
            "files": {
                "riskPlan": "risk-plan.safe.json",
                "stage4Audit": "stage4.audit.safe.json",
                "projection": "projection.stage4.private.json",
                "providerCache": "provider-cache/",
            },
        }
        (output_dir / "manifest.json").write_text(
            json.dumps(manifest_out, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        archive = shutil.make_archive(str(output_dir), "zip", root_dir=output_dir)
        self.stdout.write(
            self.style.SUCCESS(
                "Stage 4 live replay completed: "
                "ocrProviderRequests=0, "
                f"suspicious={len(suspicious)}, newProviderRequests={network_requests}, "
                f"cacheHits={int(counters.get('cacheHits') or 0)}, "
                f"logicalPrimary={logical_primary_calls}, logicalSecondary={logical_secondary_calls}, "
                f"repaired={int(stats.get('repaired') or 0)}, "
                f"unresolved={int(stats.get('unresolved') or 0)}, bundle={archive}"
            )
        )
