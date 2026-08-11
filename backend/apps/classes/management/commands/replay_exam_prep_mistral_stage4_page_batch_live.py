from __future__ import annotations

from dataclasses import replace
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import time
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
from apps.classes.services.exam_prep_mistral_disjoint_ranges import (
    aligned_solutions_for_intervals,
    build_page_extractions_disjoint,
    declared_question_intervals,
    scope_key_for_question,
)
from apps.classes.services.exam_prep_mistral_ocr_transport import MistralOCR4Config
from apps.classes.services.exam_prep_mistral_page_batch_transcriber import (
    BatchItem,
    PageBatchEnvelopeError,
    PageBatchResult,
)
# Use the same AvalAI /v1/chat/completions transport that production installs via
# exam_prep_mistral_stage4_runtime.install_stage4_transport_policy(). The base
# (v1) transcriber above calls the native, unreliable v1beta:generateContent
# bridge; importing it directly here (as this file previously did) silently
# bypassed the production transport fix and made every page batch fail closed
# with a fabricated 'invalid_items_envelope'/timeout at zero real cost.
from apps.classes.services.exam_prep_mistral_page_batch_transcriber_v4 import (
    transcribe_page_batch,
)
from apps.classes.services.exam_prep_mistral_production import (
    _question_numbers,
    _targeted_recovery_budget_plan,
    analyze_mistral_document_evidence,
)
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


def _decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    try:
        return Decimal(str(value or "0"))
    except (InvalidOperation, ValueError):
        return default


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
        "requestedTargetIds": list(value.requested_target_ids),
        "missingTargetIds": list(value.missing_target_ids),
        "invalidTargetIds": list(value.invalid_target_ids),
        "items": [item.model_dump() for item in value.items],
    }


def _deserialize_batch(value: dict[str, Any]) -> PageBatchResult:
    return PageBatchResult(
        page_number=int(value.get("pageNumber") or 0),
        model=str(value.get("model") or ""),
        items=tuple(BatchItem.model_validate(item) for item in (value.get("items") or [])),
        request_id=str(value.get("requestId") or ""),
        usage={str(k): int(v or 0) for k, v in dict(value.get("usage") or {}).items()},
        estimated_cost={
            str(k): float(v or 0) for k, v in dict(value.get("estimatedCost") or {}).items()
        },
        requested_target_ids=tuple(str(v) for v in (value.get("requestedTargetIds") or [])),
        missing_target_ids=tuple(str(v) for v in (value.get("missingTargetIds") or [])),
        invalid_target_ids=tuple(str(v) for v in (value.get("invalidTargetIds") or [])),
    )


def _failure_cost(value: dict[str, Any]) -> tuple[float, float]:
    estimated = dict(value.get("estimatedCost") or {})
    try:
        unit = float(estimated.get("unit") or 0)
    except (TypeError, ValueError):
        unit = 0.0
    try:
        irt = float(estimated.get("irt") or 0)
    except (TypeError, ValueError):
        irt = 0.0
    return unit, irt


def _cached_page_batch(
    *,
    cache_dir: Path,
    base_call: PageBatchCall,
    counters: dict[str, float],
) -> PageBatchCall:
    """Checkpoint every logical page call, including structured envelope failures."""

    cache_dir.mkdir(parents=True, exist_ok=True)

    def call(**kwargs):
        page_number = int(kwargs.get("page_number") or 0)
        target_ids = [d.target_id for d, _p in (kwargs.get("targets") or [])]
        selected_model = str(
            kwargs.get("model")
            or os.getenv("EXAM_PREP_STAGE4_PRIMARY_MODEL")
            or "gemini-3-flash-preview"
        )
        path = _batch_cache_path(
            cache_dir,
            page_number=page_number,
            targets=kwargs.get("targets") or [],
            model=selected_model,
        )
        if path.is_file():
            cached = json.loads(path.read_text(encoding="utf-8"))
            counters["pageCacheHits"] = counters.get("pageCacheHits", 0) + 1
            print(
                f"[stage4] page {page_number:>3} targets={target_ids} "
                f"CACHE-HIT status={cached.get('status')}",
                flush=True,
            )
            if cached.get("status") == "success":
                result = _deserialize_batch(cached)
                unit = float(result.estimated_cost.get("unit") or 0)
                irt = float(result.estimated_cost.get("irt") or 0)
                counters["logicalEstimatedCostUnit"] = counters.get("logicalEstimatedCostUnit", 0.0) + unit
                counters["logicalEstimatedCostIrt"] = counters.get("logicalEstimatedCostIrt", 0.0) + irt
                return result
            unit, irt = _failure_cost(cached)
            counters["logicalEstimatedCostUnit"] = counters.get("logicalEstimatedCostUnit", 0.0) + unit
            counters["logicalEstimatedCostIrt"] = counters.get("logicalEstimatedCostIrt", 0.0) + irt
            if cached.get("errorType") == "PageBatchEnvelopeError":
                raise PageBatchEnvelopeError(
                    str(cached.get("reasonCode") or "cached_envelope_failure"),
                    usage={str(k): int(v or 0) for k, v in dict(cached.get("usage") or {}).items()},
                    estimated_cost={
                        str(k): float(v or 0)
                        for k, v in dict(cached.get("estimatedCost") or {}).items()
                    },
                    request_id=str(cached.get("requestId") or ""),
                )
            raise RuntimeError(
                f"cached_page_batch_failure:{cached.get('errorType') or 'unknown'}"
            )

        counters["networkPageRequests"] = counters.get("networkPageRequests", 0) + 1
        started = time.monotonic()
        print(
            f"[stage4] page {page_number:>3} targets={target_ids} REQUEST model={selected_model} ...",
            flush=True,
        )
        try:
            result = base_call(**kwargs)
        except Exception as exc:
            elapsed = time.monotonic() - started
            print(
                f"[stage4] page {page_number:>3} targets={target_ids} FAILED "
                f"({type(exc).__name__}: {exc}) elapsed={elapsed:.1f}s",
                flush=True,
            )
            payload: dict[str, Any] = {
                "status": "failure",
                "pageNumber": kwargs.get("page_number"),
                "model": selected_model,
                "targetIds": [d.target_id for d, _p in (kwargs.get("targets") or [])],
                "errorType": type(exc).__name__,
            }
            if isinstance(exc, PageBatchEnvelopeError):
                payload.update(
                    {
                        "reasonCode": exc.reason_code,
                        "requestId": exc.request_id,
                        "usage": exc.usage,
                        "estimatedCost": exc.estimated_cost,
                    }
                )
                unit = float(exc.estimated_cost.get("unit") or 0)
                irt = float(exc.estimated_cost.get("irt") or 0)
                counters["networkEstimatedCostUnit"] = counters.get("networkEstimatedCostUnit", 0.0) + unit
                counters["networkEstimatedCostIrt"] = counters.get("networkEstimatedCostIrt", 0.0) + irt
                counters["logicalEstimatedCostUnit"] = counters.get("logicalEstimatedCostUnit", 0.0) + unit
                counters["logicalEstimatedCostIrt"] = counters.get("logicalEstimatedCostIrt", 0.0) + irt
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            raise

        path.write_text(
            json.dumps(_serialize_batch(result), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        unit = float(result.estimated_cost.get("unit") or 0)
        irt = float(result.estimated_cost.get("irt") or 0)
        elapsed = time.monotonic() - started
        print(
            f"[stage4] page {page_number:>3} targets={target_ids} OK "
            f"items={len(result.items)} costUsd={unit:.5f} elapsed={elapsed:.1f}s",
            flush=True,
        )
        counters["networkEstimatedCostUnit"] = counters.get("networkEstimatedCostUnit", 0.0) + unit
        counters["networkEstimatedCostIrt"] = counters.get("networkEstimatedCostIrt", 0.0) + irt
        counters["logicalEstimatedCostUnit"] = counters.get("logicalEstimatedCostUnit", 0.0) + unit
        counters["logicalEstimatedCostIrt"] = counters.get("logicalEstimatedCostIrt", 0.0) + irt
        return result

    return call


class Command(BaseCommand):
    help = (
        "Replay production-shaped targeted heading recovery plus page-batched Stage 4. "
        "The full OCR document is reused from a bundle; any targeted OCR/Gemini/GPT "
        "requests made now are charged against the same total PDF budget."
    )

    def add_arguments(self, parser):
        parser.add_argument("--pdf", required=True)
        parser.add_argument("--bundle", required=True)
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--title", default="Stage 4 page-batch live replay")
        parser.add_argument("--recovered-solution-targets", default="")
        parser.add_argument("--unresolved-solution-targets", default="")
        parser.add_argument("--max-page-batches", type=int, default=30)
        parser.add_argument("--max-secondary-calls", type=int, default=6)
        parser.add_argument("--total-budget-usd", type=float, default=0.30)
        parser.add_argument("--prior-provider-cost-usd", type=float, default=None)
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

        maximum_pages = max(1, min(40, int(options.get("max_page_batches") or 30)))
        maximum_secondary = max(0, min(12, int(options.get("max_secondary_calls") or 6)))
        manual_recovered = _number_set(options.get("recovered_solution_targets") or "")
        manual_unresolved = _number_set(options.get("unresolved_solution_targets") or "")
        if manual_recovered & manual_unresolved:
            raise CommandError("A target cannot be both recovered and unresolved.")

        try:
            pdf_data = pdf_path.read_bytes()
            page_count = len(PdfReader(str(pdf_path)).pages)
        except Exception as exc:
            raise CommandError("The supplied PDF cannot be opened.") from exc
        root, bundle_manifest = _load_bundle_root(bundle_path)
        bundle_page_count = int(
            bundle_manifest.get("originalPdfPageCount")
            or bundle_manifest.get("pageCount")
            or len(root.get("pages") or [])
            or 0
        )
        if bundle_page_count and bundle_page_count != page_count:
            raise CommandError(
                f"PDF/bundle page count mismatch ({page_count} != {bundle_page_count})."
            )

        total_budget = _decimal(options.get("total_budget_usd"), Decimal("0.30"))
        if total_budget <= 0:
            raise CommandError("--total-budget-usd must be positive.")
        explicit_prior = options.get("prior_provider_cost_usd")
        prior_cost = (
            _decimal(explicit_prior)
            if explicit_prior is not None
            else _decimal(bundle_manifest.get("estimatedCostUnit"))
        )
        if prior_cost >= total_budget:
            raise CommandError(
                f"No live-repair budget remains: prior={prior_cost}, total={total_budget}."
            )

        result = _diagnostic_result(pdf_data=pdf_data, root=root, page_count=page_count)
        replay_root = dict(root)
        replay_root["pages"] = [dict(page) for page in result.pages]
        evidence = analyze_mistral_document_evidence(
            replay_root,
            original_page_numbers=list(range(1, page_count + 1)),
        )
        question_numbers = _question_numbers(evidence)
        intervals = declared_question_intervals(evidence, question_numbers)
        accepted, detected_missing, detected_invalid = aligned_solutions_for_intervals(
            result,
            intervals,
        )

        targeted_plan = _targeted_recovery_budget_plan(
            accepted=accepted,
            missing=detected_missing,
            invalid=detected_invalid,
            ocr_cost_usd=prior_cost,
            total_budget_usd=total_budget,
        )
        auto_recovered: dict[int, tuple[str, int, str]] = {}
        targeted_result = None
        if targeted_plan.get("allowed"):
            # One bounded retry: this request only carries small cropped
            # question/solution regions, so retrying a transient provider
            # failure (e.g. HTTP 504) is cheap, unlike the main OCR chunks.
            targeted_config = replace(
                MistralOCR4Config.from_env(),
                max_attempts=2,
                word_confidence=False,
                checkpoint_enabled=False,
            )
            print("[stage4] targeted solution-heading recovery: requesting ...", flush=True)
            try:
                auto_recovered, targeted_result = stage2._targeted_recovery(
                    pdf_data,
                    accepted=accepted,
                    missing=detected_missing,
                    invalid=detected_invalid,
                    config=targeted_config,
                    should_cancel=None,
                )
                print(
                    f"[stage4] targeted recovery OK: recovered={sorted(auto_recovered)}",
                    flush=True,
                )
            except Exception as exc:
                print(
                    f"[stage4] targeted recovery FAILED ({type(exc).__name__}: {exc}); "
                    "continuing with all targets unresolved.",
                    flush=True,
                )

        targeted_cost = (
            targeted_result.estimated_cost_unit if targeted_result is not None else Decimal("0")
        )
        targeted_calls = targeted_result.provider_call_count if targeted_result is not None else 0
        spent_before_stage4 = prior_cost + targeted_cost
        remaining_stage4_budget = max(Decimal("0"), total_budget - spent_before_stage4)
        if remaining_stage4_budget <= 0:
            raise CommandError(
                f"No Stage-4 budget remains after targeted recovery: "
                f"spent={spent_before_stage4}, total={total_budget}."
            )

        recovered_numbers = set(manual_recovered) | set(auto_recovered)
        detected_unresolved = set(detected_missing) | set(detected_invalid)
        unresolved = (detected_unresolved | manual_unresolved) - recovered_numbers

        page_extractions = build_page_extractions_disjoint(
            result=result,
            evidence=evidence,
            recovered_targets=auto_recovered,
            intervals=intervals,
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
            recovered_solution_targets=recovered_numbers,
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
            row["scopeKey"] = scope_key_for_question(intervals, decision.question_number)
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
                recovered_solution_targets=recovered_numbers,
                unresolved_solution_targets=unresolved,
                max_cost_usd=float(remaining_stage4_budget),
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
        provider_requests_this_run = targeted_calls + int(counters.get("networkPageRequests") or 0) + int(
            counters.get("networkSecondaryRequests") or 0
        )
        stage4_cost = _decimal(stats.get("totalLlmCostUsd"))
        total_estimated_cost = spent_before_stage4 + stage4_cost

        (output_dir / "stage4.audit.safe.json").write_text(
            json.dumps(stage4_audit, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (output_dir / "projection.stage4.private.json").write_text(
            json.dumps(updated.projection, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        manifest_out = {
            "schemaVersion": 5,
            "privateDiagnosticBundle": True,
            "ocrProviderRequests": 0,
            "targetedOcrProviderRequestsThisRun": targeted_calls,
            "providerRequestsThisRun": provider_requests_this_run,
            "networkPageBatchRequestsThisRun": int(counters.get("networkPageRequests") or 0),
            "networkSecondaryRequestsThisRun": int(counters.get("networkSecondaryRequests") or 0),
            "pageBatchCacheHits": int(counters.get("pageCacheHits") or 0),
            "secondaryCacheHits": int(counters.get("secondaryCacheHits") or 0),
            "estimatedPrimaryCostUnitThisRun": round(
                float(counters.get("networkEstimatedCostUnit") or 0), 8
            ),
            "estimatedPrimaryCostIrtThisRun": round(
                float(counters.get("networkEstimatedCostIrt") or 0), 2
            ),
            "targetedOcrCostUsdThisRun": format(targeted_cost, "f"),
            "sourcePdfSha256": result.source_sha256,
            "pageCount": page_count,
            "questionCount": len(question_numbers),
            "questionIntervals": [
                {
                    "start": start,
                    "end": end,
                    "scopeKey": scope_key_for_question(intervals, start),
                }
                for start, end in intervals
            ],
            "riskRegionCount": len(decisions),
            "suspiciousRegionCount": len(suspicious),
            "suspiciousPageCount": len(suspicious_pages),
            "pageBatches": int(stats.get("pageBatches") or 0),
            "primaryCalls": int(stats.get("primaryCalls") or 0),
            "splitCalls": int(stats.get("splitCalls") or 0),
            "primaryTargets": int(stats.get("primaryTargets") or 0),
            "secondaryCalls": int(stats.get("secondaryCalls") or 0),
            "verified": int(stats.get("verified") or 0),
            "repaired": int(stats.get("repaired") or 0),
            "partialRepairs": int(stats.get("partialRepairs") or 0),
            "unresolved": int(stats.get("unresolved") or 0),
            "deferred": int(stats.get("deferred") or 0),
            "detectedMissingSolutionTargets": sorted(detected_missing),
            "detectedInvalidSolutionTargets": sorted(detected_invalid),
            "targetedRecoveryBudgetPlan": targeted_plan,
            "targetedSolutionHeadingRecovered": sorted(auto_recovered),
            "unresolvedSolutionTargets": sorted(unresolved),
            "manualRecoveredSolutionTargetsRiskHintOnly": sorted(manual_recovered),
            "priorProviderCostUsd": format(prior_cost, "f"),
            "spentBeforeStage4Usd": format(spent_before_stage4, "f"),
            "totalBudgetUsd": format(total_budget, "f"),
            "stage4BudgetUsd": format(remaining_stage4_budget, "f"),
            "stage4EstimatedCostUsd": format(stage4_cost, "f"),
            "totalEstimatedCostUsd": format(total_estimated_cost, "f"),
            "budgetWithinLimit": total_estimated_cost <= total_budget,
            "stage3Stats": visual_stats,
            "stage3CriticalIssueCodes": list(visual_audit.get("criticalIssueCodes") or []),
        }
        (output_dir / "manifest.json").write_text(
            json.dumps(manifest_out, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        archive = shutil.make_archive(str(output_dir), "zip", root_dir=output_dir)
        self.stdout.write(
            self.style.SUCCESS(
                "Stage 4 page-batch replay completed: fullOcrProviderRequests=0, "
                f"targetedOcrRequests={targeted_calls}, targets={len(suspicious)}, "
                f"pages={len(suspicious_pages)}, "
                f"newPageRequests={int(counters.get('networkPageRequests') or 0)}, "
                f"newSecondaryRequests={int(counters.get('networkSecondaryRequests') or 0)}, "
                f"repaired={int(stats.get('repaired') or 0)}, "
                f"unresolved={int(stats.get('unresolved') or 0)}, "
                f"totalEstimatedCostUsd={format(total_estimated_cost, 'f')}, bundle={archive}"
            )
        )
