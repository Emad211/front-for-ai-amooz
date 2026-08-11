from __future__ import annotations

from collections import Counter
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from threading import Lock
from types import SimpleNamespace
from typing import Any, Mapping
from zipfile import BadZipFile, ZipFile

from django.core.management.base import BaseCommand, CommandError
from pypdf import PdfReader

from apps.classes.management.commands.replay_exam_prep_mistral_visual_stage3 import (
    _DiagnosticStore,
    _diagnostic_result,
    _load_bundle_root,
)
from apps.classes.services import exam_prep_mistral_production as production
from apps.classes.services import exam_prep_mistral_stage5 as stage5
from apps.classes.services.exam_prep_mistral_targeted_recovery import (
    collect_crop_headings,
    resolve_target_questions,
)
from apps.classes.services.exam_prep_question_verifier import rebuild_assembly_quality


RegionTarget = tuple[int, str]
_TARGET_KINDS = frozenset({"question", "solution"})
_USAGE_LOG_ENV = "EXAM_PREP_STAGE4_USAGE_DB_LOGGING"


def _parse_targets(value: Any) -> frozenset[RegionTarget]:
    """Parse ``question:65,solution:57`` into exact Stage-5 region keys."""

    if isinstance(value, (list, tuple)):
        raw = ",".join(str(item) for item in value)
    else:
        raw = str(value or "")
    tokens = [item for item in re.split(r"[,;\s]+", raw.strip()) if item]
    targets: set[RegionTarget] = set()
    for token in tokens:
        kind, separator, number_text = token.partition(":")
        kind = kind.strip().lower()
        try:
            number = int(number_text.strip()) if separator else 0
        except ValueError:
            number = 0
        if kind not in _TARGET_KINDS or number < 1:
            raise CommandError(
                f"Invalid target {token!r}; use question:N or solution:N with N >= 1."
            )
        targets.add((number, kind))
    if not targets:
        raise CommandError("At least one valid target is required.")
    return frozenset(targets)


def _load_cached_input(*, pdf_path: Path, bundle_path: Path):
    """Load an exact PDF/OCR pair and reject ambiguous or stale bundles."""

    if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
        raise CommandError("--pdf must point to an existing PDF file.")
    if not bundle_path.is_file() or bundle_path.suffix.lower() != ".zip":
        raise CommandError("--bundle must point to an existing OCR ZIP bundle.")
    try:
        pdf_data = pdf_path.read_bytes()
        page_count = len(PdfReader(str(pdf_path)).pages)
    except Exception as exc:
        raise CommandError("The supplied PDF cannot be opened.") from exc

    root, manifest = _load_bundle_root(bundle_path)
    manifest_sha = str(manifest.get("sourcePdfSha256") or "").strip().lower()
    actual_sha = sha256(pdf_data).hexdigest()
    if manifest_sha != actual_sha:
        raise CommandError("PDF/bundle SHA-256 mismatch.")

    raw_page_count = manifest.get("originalPdfPageCount") or manifest.get("pageCount")
    try:
        bundle_page_count = int(raw_page_count)
    except (TypeError, ValueError) as exc:
        raise CommandError("OCR bundle manifest has no valid page count.") from exc
    if bundle_page_count != page_count:
        raise CommandError(
            f"OCR bundle page count mismatch ({page_count} != {bundle_page_count})."
        )

    result = _diagnostic_result(
        pdf_data=pdf_data,
        root=root,
        page_count=page_count,
    )
    return pdf_data, result, manifest


def _solution_target_numbers(
    targets: frozenset[RegionTarget] | None,
) -> list[int]:
    if targets is None:
        return []
    return sorted({number for number, kind in targets if kind == "solution"})


def _decimal(value: Any) -> Decimal:
    try:
        return max(Decimal("0"), Decimal(str(value or "0")))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _load_cached_targeted_recovery(
    *,
    bundle_path: Path,
    targets: frozenset[RegionTarget] | None,
):
    """Load a previously paid targeted OCR result without making a provider call."""

    target_questions = _solution_target_numbers(targets)
    if not target_questions:
        raise CommandError("--targeted-bundle requires at least one solution:N target.")
    if not bundle_path.is_file() or bundle_path.suffix.lower() != ".zip":
        raise CommandError("--targeted-bundle must point to an existing ZIP file.")

    try:
        with ZipFile(bundle_path) as archive:
            names = set(archive.namelist())
            required = {"response.raw.json", "request.safe.json", "manifest.json"}
            if not required.issubset(names):
                raise CommandError(
                    "Targeted bundle must contain response.raw.json, request.safe.json, and manifest.json."
                )
            root = json.loads(archive.read("response.raw.json").decode("utf-8"))
            request = json.loads(archive.read("request.safe.json").decode("utf-8"))
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
    except CommandError:
        raise
    except (OSError, BadZipFile, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CommandError("Targeted recovery bundle is invalid or incomplete.") from exc

    if not isinstance(root, Mapping) or not isinstance(request, Mapping) or not isinstance(manifest, Mapping):
        raise CommandError("Targeted recovery bundle JSON roots must be objects.")
    source = request.get("source")
    source = source if isinstance(source, Mapping) else {}
    crop_specs = source.get("cropSpecs")
    if not isinstance(crop_specs, list) or not all(isinstance(item, Mapping) for item in crop_specs):
        raise CommandError("Targeted recovery bundle has no valid source.cropSpecs.")

    headings = collect_crop_headings(root, crop_specs)
    resolution = resolve_target_questions(headings, target_questions)
    if not resolution.get("complete"):
        unresolved = resolution.get("unresolvedQuestionNumbers") or []
        conflicts = resolution.get("conflicts") or []
        raise CommandError(
            "Targeted recovery bundle does not resolve every requested solution target "
            f"(unresolved={unresolved}, conflicts={conflicts})."
        )

    recovered: dict[int, tuple[str, int, str]] = {}
    for item in resolution.get("recovered") or []:
        question = int(item.get("questionNumber") or 0)
        option = int(item.get("optionLabel") or 0)
        evidence = [
            heading
            for heading in headings
            if int(heading.get("rawQuestionNumber") or 0) == question
            and heading.get("optionLabelValid") is True
            and int(heading.get("optionLabel") or 0) == option
        ]
        pages = {
            int(heading.get("physicalPageNumber") or 0)
            for heading in evidence
            if int(heading.get("physicalPageNumber") or 0) > 0
        }
        columns = {
            str(heading.get("column") or "").strip().lower()
            for heading in evidence
            if str(heading.get("column") or "").strip().lower() in {"left", "right"}
        }
        if len(pages) != 1 or len(columns) != 1:
            raise CommandError(
                f"Targeted recovery evidence for solution {question} is spatially ambiguous."
            )
        recovered[question] = (str(option), next(iter(pages)), next(iter(columns)))

    estimated = manifest.get("estimatedCost")
    estimated = estimated if isinstance(estimated, Mapping) else {}
    cached_result = SimpleNamespace(
        estimated_cost_unit=_decimal(estimated.get("unit")),
        provider_call_count=max(0, int(manifest.get("providerRequestCount") or 0)),
        retry_count=max(0, int(manifest.get("retryCount") or 0)),
    )
    return recovered, cached_result


def _question_number(question: Mapping[str, Any]) -> int:
    try:
        return int(question.get("source_question_number") or 0)
    except (TypeError, ValueError):
        return 0


def _subset_questions(result, *, numbers: frozenset[int]):
    projection = dict(result.projection)
    exam = dict(projection.get("exam_prep") or {})
    exam["questions"] = [
        dict(question)
        for question in (exam.get("questions") or [])
        if isinstance(question, Mapping) and _question_number(question) in numbers
    ]
    projection["exam_prep"] = exam
    subset = result.model_copy(
        update={
            "projection": projection,
            "issues": [
                issue
                for issue in result.issues
                if int(issue.question_number) in numbers
            ],
            "orphan_answers": [
                item
                for item in result.orphan_answers
                if int(item.question_number) in numbers
            ],
            "question_number_gaps": {},
        }
    )
    return rebuild_assembly_quality(subset)


def _run_cached_pipeline(
    *,
    pdf_data: bytes,
    cached_result,
    title: str,
    targets: frozenset[RegionTarget] | None,
    visual_store: _DiagnosticStore,
    evidence_sink: list[dict[str, Any]] | None = None,
    cached_targeted_recovery: tuple[dict[int, tuple[str, int, str]], Any | None] | None = None,
):
    """Run the production facade with narrowly scoped, fully restored replay seams."""

    original_fetch = production.fetch_ocr4_document
    original_targeted_recovery = production._targeted_recovery
    original_reconcile = production.reconcile_mistral_source_visuals
    original_score = production.score_region_risks
    original_finalize = production.finalize_stage5_regions
    original_transcribe = stage5._transcribe
    original_usage_logging = os.environ.get(_USAGE_LOG_ENV)
    evidence_lock = Lock()
    target_numbers = (
        frozenset(number for number, _kind in targets)
        if targets is not None
        else None
    )
    cached_recovered, cached_targeted_result = cached_targeted_recovery or ({}, None)

    def cached_fetch(*args, **kwargs):
        return cached_result

    def cached_targeted_ocr(*args, **kwargs):
        requested = sorted(
            set(int(value) for value in (kwargs.get("missing") or []))
            | set(int(value) for value in (kwargs.get("invalid") or []))
        )
        if not requested:
            return {}, None
        if cached_targeted_result is None:
            return {}, None
        missing_from_bundle = sorted(set(requested) - set(cached_recovered))
        if missing_from_bundle:
            raise RuntimeError(
                "Cached targeted recovery does not cover production-requested solution targets: "
                f"{missing_from_bundle}"
            )
        return (
            {number: cached_recovered[number] for number in requested},
            cached_targeted_result,
        )

    def local_reconcile(result, *args, **kwargs):
        if target_numbers is not None:
            result = _subset_questions(result, numbers=target_numbers)
        kwargs.pop("storage_namespace", None)
        kwargs.pop("should_cancel", None)
        kwargs["store"] = visual_store
        return original_reconcile(result, *args, **kwargs)

    def exact_target_score(*args, **kwargs):
        decisions = original_score(*args, **kwargs)
        if targets is None:
            return decisions
        return [
            decision
            for decision in decisions
            if (decision.question_number, decision.kind) in targets
        ]

    def exact_target_finalize(*args, **kwargs):
        if targets is not None:
            kwargs["required_targets"] = targets
        return original_finalize(*args, **kwargs)

    def capture_transcribe(*args, **kwargs):
        decision = kwargs.get("decision")
        model = str(kwargs.get("model") or "")
        base = {
            "questionNumber": _safe_int(getattr(decision, "question_number", 0)),
            "kind": str(getattr(decision, "kind", "") or ""),
            "pageNumber": _safe_int(getattr(decision, "page_number", 0)),
            "model": model,
        }
        try:
            value = original_transcribe(*args, **kwargs)
        except Exception as exc:
            if evidence_sink is not None:
                with evidence_lock:
                    evidence_sink.append(
                        {**base, "status": "failed", "failureType": type(exc).__name__}
                    )
            raise
        if evidence_sink is not None:
            with evidence_lock:
                evidence_sink.append(
                    {
                        **base,
                        "status": "succeeded",
                        "responseId": str(value.response_id or ""),
                        "inputTokens": _safe_int(value.input_tokens),
                        "outputTokens": _safe_int(value.output_tokens),
                        "totalTokens": _safe_int(value.total_tokens),
                        "reasoningTokens": _safe_int(value.reasoning_tokens),
                        "transcript": dict(value.transcript),
                    }
                )
        return value

    production.fetch_ocr4_document = cached_fetch
    production._targeted_recovery = cached_targeted_ocr
    production.reconcile_mistral_source_visuals = local_reconcile
    production.score_region_risks = exact_target_score
    production.finalize_stage5_regions = exact_target_finalize
    stage5._transcribe = capture_transcribe
    # Replay already persists token counts and provider evidence locally. Do not
    # make diagnostic live calls depend on the application's PostgreSQL logger.
    os.environ[_USAGE_LOG_ENV] = "0"
    try:
        return production.run_exam_prep_mistral_pipeline(
            data=pdf_data,
            title=title,
        )
    finally:
        production.fetch_ocr4_document = original_fetch
        production._targeted_recovery = original_targeted_recovery
        production.reconcile_mistral_source_visuals = original_reconcile
        production.score_region_risks = original_score
        production.finalize_stage5_regions = original_finalize
        stage5._transcribe = original_transcribe
        if original_usage_logging is None:
            os.environ.pop(_USAGE_LOG_ENV, None)
        else:
            os.environ[_USAGE_LOG_ENV] = original_usage_logging


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _build_manifest(
    *,
    result,
    cached_result,
    bundle_name: str,
    targets: frozenset[RegionTarget] | None,
    targeted_bundle_name: str | None = None,
) -> dict[str, Any]:
    audit = result.extraction_audit if isinstance(result.extraction_audit, Mapping) else {}
    risk = audit.get("riskEngine") if isinstance(audit.get("riskEngine"), Mapping) else {}
    stats = risk.get("stats") if isinstance(risk.get("stats"), Mapping) else {}
    regions = [item for item in (risk.get("regions") or []) if isinstance(item, Mapping)]
    statuses = Counter(str(item.get("status") or "unknown") for item in regions)
    primary_calls = _safe_int(stats.get("primaryCalls"))
    main_calls = _safe_int(stats.get("mainCalls"))
    requested = (
        [
            {"questionNumber": number, "kind": kind}
            for number, kind in sorted(targets)
        ]
        if targets is not None
        else []
    )
    return {
        "schemaVersion": 4,
        "privateDiagnosticBundle": True,
        "privateTransmissionExplicitlyAllowed": True,
        "productionPipelineChanged": False,
        "productionEntrypoint": production.PRODUCTION_ENTRYPOINT,
        "cachedOcrOnly": True,
        "inputBundle": bundle_name,
        "cachedTargetedRecoveryBundle": targeted_bundle_name,
        "sourcePdfSha256": cached_result.source_sha256,
        "pageCount": cached_result.page_count,
        "targetStats": {
            "mode": "targets" if targets is not None else "all_regions",
            "requestedCount": len(requested) if targets is not None else None,
            "requestedTargets": requested,
            "processedRegionCount": len(regions),
        },
        "callStats": {
            "ocrProviderCallsThisReplay": 0,
            "targetedOcrProviderCallsThisReplay": 0,
            "primaryCalls": primary_calls,
            "mainCalls": main_calls,
            "stage5Calls": primary_calls + main_calls,
            "totalProviderCallsThisReplay": primary_calls + main_calls,
            "projectedProductionTotalProviderCalls": _safe_int(
                audit.get("totalProviderCalls")
            ),
        },
        "blockStats": {
            "blockedRegions": _safe_int(stats.get("blocked")),
            "verifiedRegions": _safe_int(stats.get("verified")),
            "repairedRegions": _safe_int(stats.get("repaired")),
            "statusCounts": dict(sorted(statuses.items())),
        },
        "costStats": {
            "replayChargedCostUsd": str(audit.get("stage5ChargedCostUsd") or "0"),
            "replaySuccessfulUsageCostUsd": str(
                audit.get("stage5SuccessfulCallEstimatedCostUsd") or "0"
            ),
            "replayCostEstimateComplete": bool(
                audit.get("stage5CostEstimateComplete")
            ),
            "projectedProductionTotalEstimatedCostUsd": str(
                audit.get("totalEstimatedCostUsd") or "0"
            ),
            "totalPdfBudgetUsd": str(audit.get("totalPdfBudgetUsd") or "0"),
            "projectedProductionBudgetWithinLimit": bool(
                audit.get("budgetWithinLimit")
            ),
        },
        "files": {
            "projection": "projection.private.json",
            "audit": "audit.private.json",
            "providerEvidence": "provider-evidence.private.json",
            "storedMapping": "stored-files.private.json",
        },
    }


class Command(BaseCommand):
    help = (
        "Replay the exact production Mistral Stage-5 path with cached OCR and "
        "explicitly approved private source-region transmission."
    )

    def add_arguments(self, parser):
        parser.add_argument("--pdf", required=True)
        parser.add_argument("--bundle", required=True)
        parser.add_argument("--targeted-bundle")
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--title", default="Stage 5 production replay")
        selection = parser.add_mutually_exclusive_group(required=True)
        selection.add_argument("--targets")
        selection.add_argument("--all-regions", action="store_true")
        parser.add_argument("--allow-private-transmission", action="store_true")

    def handle(self, *args, **options):
        if not options.get("allow_private_transmission"):
            raise CommandError("--allow-private-transmission is mandatory for Stage-5 replay.")

        targets = (
            None
            if options.get("all_regions")
            else _parse_targets(options.get("targets"))
        )
        pdf_path = Path(options["pdf"]).expanduser().resolve()
        bundle_path = Path(options["bundle"]).expanduser().resolve()
        targeted_bundle_path = (
            Path(options["targeted_bundle"]).expanduser().resolve()
            if options.get("targeted_bundle")
            else None
        )
        if targeted_bundle_path is not None and targets is None:
            raise CommandError("--targeted-bundle is supported only with --targets.")
        output_dir = Path(options["output_dir"]).expanduser().resolve()
        if output_dir.exists():
            if not output_dir.is_dir() or any(output_dir.iterdir()):
                raise CommandError("--output-dir must be absent or empty.")

        pdf_data, cached_result, _bundle_manifest = _load_cached_input(
            pdf_path=pdf_path,
            bundle_path=bundle_path,
        )
        cached_targeted_recovery = (
            _load_cached_targeted_recovery(
                bundle_path=targeted_bundle_path,
                targets=targets,
            )
            if targeted_bundle_path is not None
            else None
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        visual_store = _DiagnosticStore(output_dir / "stage3-visuals")
        provider_evidence: list[dict[str, Any]] = []
        result = _run_cached_pipeline(
            pdf_data=pdf_data,
            cached_result=cached_result,
            title=str(options.get("title") or "Stage 5 production replay"),
            targets=targets,
            visual_store=visual_store,
            evidence_sink=provider_evidence,
            cached_targeted_recovery=cached_targeted_recovery,
        )

        manifest = _build_manifest(
            result=result,
            cached_result=cached_result,
            bundle_name=bundle_path.name,
            targets=targets,
            targeted_bundle_name=(
                targeted_bundle_path.name if targeted_bundle_path is not None else None
            ),
        )
        (output_dir / "projection.private.json").write_text(
            json.dumps(result.projection, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (output_dir / "audit.private.json").write_text(
            json.dumps(result.extraction_audit, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        provider_evidence.sort(
            key=lambda item: (
                _safe_int(item.get("questionNumber")),
                str(item.get("kind") or ""),
                str(item.get("model") or ""),
            )
        )
        (output_dir / "provider-evidence.private.json").write_text(
            json.dumps(provider_evidence, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (output_dir / "stored-files.private.json").write_text(
            json.dumps(visual_store.files, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (output_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        call_stats = manifest["callStats"]
        block_stats = manifest["blockStats"]
        cost_stats = manifest["costStats"]
        self.stdout.write(
            self.style.SUCCESS(
                "Stage 5 replay completed: "
                f"regions={manifest['targetStats']['processedRegionCount']}, "
                f"calls={call_stats['stage5Calls']}, "
                f"blocked={block_stats['blockedRegions']}, "
                f"chargedCostUsd={cost_stats['replayChargedCostUsd']}, "
                f"costEstimateComplete={cost_stats['replayCostEstimateComplete']}"
            )
        )


__all__ = [
    "Command",
    "_DiagnosticStore",
    "_build_manifest",
    "_load_cached_input",
    "_load_cached_targeted_recovery",
    "_parse_targets",
    "_run_cached_pipeline",
]
