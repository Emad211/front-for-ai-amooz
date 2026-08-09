from __future__ import annotations

from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import shutil
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from pypdf import PdfReader

from apps.classes.management.commands.replay_exam_prep_mistral_visual_stage3 import (
    _DiagnosticStore,
    _diagnostic_result,
    _load_bundle_root,
)
from apps.classes.services.exam_prep_mistral_disjoint_ranges import (
    aligned_solutions_for_intervals,
    build_page_extractions_disjoint,
    declared_question_intervals,
    scope_key_for_question,
)
from apps.classes.services.exam_prep_mistral_production import (
    _question_numbers,
    analyze_mistral_document_evidence,
)
from apps.classes.services.exam_prep_mistral_risk_engine_v2 import score_region_risks
from apps.classes.services.exam_prep_mistral_stage4 import _render_crop
from apps.classes.services.exam_prep_mistral_visual_reconcile import (
    VisualPipelineConfig,
    reconcile_mistral_source_visuals,
)
from apps.classes.services.exam_prep_page_records import assemble_page_extractions
from apps.classes.services.exam_prep_page_source import attach_source_regions
from apps.classes.services.exam_prep_question_verifier import rebuild_assembly_quality


_DEFAULT_TOTAL_BUDGET = Decimal("0.30")


def _number_set(value: str) -> set[int]:
    output: set[int] = set()
    for item in str(value or "").replace(";", ",").split(","):
        text = item.strip()
        if not text:
            continue
        try:
            number = int(text)
        except ValueError as exc:
            raise CommandError(f"Invalid question number: {text}") from exc
        if number < 1:
            raise CommandError("Question numbers must be positive.")
        output.add(number)
    return output


def _decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    try:
        return Decimal(str(value or "0"))
    except (InvalidOperation, ValueError):
        return default


class Command(BaseCommand):
    help = (
        "Replay OCR4 + Stage 3 locally and emit the exact Stage-4 risk/crop plan. "
        "This command makes zero provider requests."
    )

    def add_arguments(self, parser):
        parser.add_argument("--pdf", required=True)
        parser.add_argument("--bundle", required=True)
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--title", default="Stage 4 risk plan")
        parser.add_argument("--recovered-solution-targets", default="")
        parser.add_argument("--unresolved-solution-targets", default="")
        parser.add_argument("--total-budget-usd", type=float, default=0.30)

    def handle(self, *args, **options):
        pdf_path = Path(options["pdf"]).expanduser().resolve()
        bundle_path = Path(options["bundle"]).expanduser().resolve()
        output_dir = Path(options["output_dir"]).expanduser().resolve()
        if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
            raise CommandError("--pdf must point to an existing PDF file.")
        if not bundle_path.is_file() or bundle_path.suffix.lower() != ".zip":
            raise CommandError("--bundle must point to an existing OCR ZIP bundle.")
        if output_dir.exists() and any(output_dir.iterdir()):
            raise CommandError("--output-dir must be absent or empty.")
        output_dir.mkdir(parents=True, exist_ok=True)

        recovered = _number_set(options.get("recovered_solution_targets") or "")
        manual_unresolved = _number_set(options.get("unresolved_solution_targets") or "")
        if recovered & manual_unresolved:
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

        result = _diagnostic_result(
            pdf_data=pdf_data,
            root=root,
            page_count=page_count,
        )
        replay_root = dict(root)
        replay_root["pages"] = [dict(page) for page in result.pages]
        evidence = analyze_mistral_document_evidence(
            replay_root,
            original_page_numbers=list(range(1, page_count + 1)),
        )
        question_numbers = _question_numbers(evidence)
        intervals = declared_question_intervals(evidence, question_numbers)
        _accepted, detected_missing, detected_invalid = aligned_solutions_for_intervals(
            result,
            intervals,
        )
        detected_unresolved = set(detected_missing) | set(detected_invalid)
        unresolved = (detected_unresolved | manual_unresolved) - recovered

        # A number-only --recovered-solution-targets list is sufficient for risk
        # calibration but cannot reconstruct the exact recovered answer label and
        # source side. Keep assembly source-pure and make that limitation explicit
        # in the diagnostic manifest instead of fabricating an answer record.
        page_extractions = build_page_extractions_disjoint(
            result=result,
            evidence=evidence,
            recovered_targets={},
            intervals=intervals,
        )
        assembled = assemble_page_extractions(
            page_extractions,
            title=str(options.get("title") or "Stage 4 risk plan"),
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
        crop_dir = output_dir / "suspicious-crops"
        crop_dir.mkdir(parents=True, exist_ok=True)
        rows: list[dict[str, Any]] = []
        for decision in decisions:
            row = decision.safe_dict()
            row["scopeKey"] = scope_key_for_question(intervals, decision.question_number)
            if decision.suspicious:
                crop_name = f"{decision.target_id}.png"
                try:
                    (crop_dir / crop_name).write_bytes(_render_crop(pdf_data, decision))
                    row["cropFile"] = f"suspicious-crops/{crop_name}"
                except Exception as exc:
                    row["cropError"] = type(exc).__name__
            rows.append(row)

        signal_counts: dict[str, int] = {}
        for item in suspicious:
            for signal in item.signals:
                signal_counts[signal] = signal_counts.get(signal, 0) + 1
        hard_math = sum(item.hard_math for item in suspicious)
        total_budget = _decimal(options.get("total_budget_usd"), _DEFAULT_TOTAL_BUDGET)
        if total_budget <= 0:
            total_budget = _DEFAULT_TOTAL_BUDGET
        ocr_cost = _decimal(bundle_manifest.get("estimatedCostUnit"))
        remaining_budget = max(Decimal("0"), total_budget - ocr_cost)

        manifest_out = {
            "schemaVersion": 3,
            "privateDiagnosticBundle": True,
            "providerRequests": 0,
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
            "intentionalNumberGapSuppressed": len(intervals) > 1,
            "regionCount": len(decisions),
            "cleanRegionCount": len(decisions) - len(suspicious),
            "suspiciousRegionCount": len(suspicious),
            "suspiciousPageCount": len(suspicious_pages),
            "hardMathSuspiciousCount": hard_math,
            "potentialPrimaryPageBatchCalls": len(suspicious_pages),
            "potentialSecondaryCallsUpperBound": min(hard_math, 6),
            "signalCounts": dict(sorted(signal_counts.items())),
            "detectedMissingSolutionTargets": sorted(detected_missing),
            "detectedInvalidSolutionTargets": sorted(detected_invalid),
            "recoveredSolutionTargetsRiskHintOnly": sorted(recovered),
            "unresolvedSolutionTargets": sorted(unresolved),
            "recoveredAssemblyWarning": (
                "number-only recovered targets are not reconstructed in this zero-provider plan"
                if recovered
                else ""
            ),
            "ocrEstimatedCostUsd": format(ocr_cost, "f"),
            "totalBudgetUsd": format(total_budget, "f"),
            "remainingBudgetBeforeStage4Usd": format(remaining_budget, "f"),
            "stage3Stats": visual_stats,
            "stage3CriticalIssueCodes": list(visual_audit.get("criticalIssueCodes") or []),
        }
        (output_dir / "manifest.json").write_text(
            json.dumps(manifest_out, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (output_dir / "risk-plan.safe.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        archive = shutil.make_archive(str(output_dir), "zip", root_dir=output_dir)
        self.stdout.write(
            self.style.SUCCESS(
                "Stage 4 risk plan completed: providerRequests=0, "
                f"questions={len(question_numbers)}, intervals={list(intervals)}, "
                f"regions={len(decisions)}, suspicious={len(suspicious)}, "
                f"pages={len(suspicious_pages)}, hardMath={hard_math}, "
                f"remainingBudgetUsd={format(remaining_budget, 'f')}, bundle={archive}"
            )
        )
