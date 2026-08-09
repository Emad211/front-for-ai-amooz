"""Final production-shaped Stage-4 acceptance replay.

This command is intentionally thin. It does not implement another extraction
pipeline. It enriches a reusable OCR bundle with the strict native-PDF answer
heading contract, invokes the existing live page-batch replay with fresh caches,
and then audits the final projection against the same native source labels.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import zipfile
from typing import Any, Mapping

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from pypdf import PdfReader

from apps.classes.management.commands.replay_exam_prep_mistral_visual_stage3 import (
    _diagnostic_result,
    _load_bundle_root,
)
from apps.classes.services.exam_prep_mistral_native_answer_headings import (
    authoritative_answer_labels,
    extract_native_answer_evidence,
    overlay_native_solution_heading_blocks,
)
from apps.classes.services.exam_prep_mistral_production import (
    _question_numbers,
    analyze_mistral_document_evidence,
)


def _number(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _final_label_audit(
    projection: Mapping[str, Any],
    *,
    authoritative: Mapping[int, str],
) -> dict[str, Any]:
    exam = projection.get("exam_prep")
    questions = exam.get("questions") if isinstance(exam, Mapping) else []
    observed: dict[int, str] = {}
    for raw in questions or []:
        if not isinstance(raw, Mapping):
            continue
        number = _number(raw.get("source_question_number"))
        if number > 0:
            observed[number] = str(raw.get("correct_option_label") or "").strip()

    mismatches = sorted(
        number
        for number, expected in authoritative.items()
        if observed.get(number) and observed.get(number) != str(expected)
    )
    missing = sorted(
        number for number in authoritative if observed.get(number) not in {"1", "2", "3", "4"}
    )
    extra = sorted(set(observed) - set(authoritative)) if authoritative else []
    return {
        "expectedLabelCount": len(authoritative),
        "observedQuestionCount": len(observed),
        "mismatchCount": len(mismatches),
        "mismatchQuestions": mismatches,
        "missingLabelCount": len(missing),
        "missingLabelQuestions": missing,
        "extraQuestionNumbers": extra,
        "passed": bool(authoritative) and not mismatches and not missing and not extra,
    }


def _write_overlay_bundle(
    target: Path,
    *,
    root: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "response.raw.json",
            json.dumps(dict(root), ensure_ascii=False, separators=(",", ":")),
        )
        archive.writestr(
            "manifest.json",
            json.dumps(dict(manifest), ensure_ascii=False, separators=(",", ":"), default=str),
        )


class Command(BaseCommand):
    help = (
        "Run the final Stage-4 acceptance replay using a reusable OCR bundle plus "
        "strict native-PDF answer-heading authority and a final label integrity audit."
    )

    def add_arguments(self, parser):
        parser.add_argument("--pdf", required=True)
        parser.add_argument("--bundle", required=True)
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--title", default="Stage 4 final acceptance replay")
        parser.add_argument("--max-page-batches", type=int, default=40)
        parser.add_argument("--max-secondary-calls", type=int, default=12)
        parser.add_argument("--total-budget-usd", type=float, default=5.00)
        parser.add_argument("--prior-provider-cost-usd", type=float, default=None)
        parser.add_argument("--allow-private-transmission", action="store_true")

    def handle(self, *args, **options):
        if not options.get("allow_private_transmission"):
            raise CommandError("Pass --allow-private-transmission for the final live replay.")

        pdf_path = Path(options["pdf"]).expanduser().resolve()
        bundle_path = Path(options["bundle"]).expanduser().resolve()
        output_dir = Path(options["output_dir"]).expanduser().resolve()
        if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
            raise CommandError("--pdf must point to an existing PDF file.")
        if not bundle_path.is_file() or bundle_path.suffix.lower() != ".zip":
            raise CommandError("--bundle must point to an existing reusable OCR ZIP.")
        if output_dir.exists() and any(output_dir.iterdir()):
            raise CommandError("--output-dir must be absent or empty for final acceptance.")
        output_dir.mkdir(parents=True, exist_ok=True)

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

        diagnostic = _diagnostic_result(
            pdf_data=pdf_data,
            root=root,
            page_count=page_count,
        )
        initial_root = dict(root)
        initial_root["pages"] = [dict(page) for page in diagnostic.pages]
        initial_evidence = analyze_mistral_document_evidence(
            initial_root,
            original_page_numbers=list(range(1, page_count + 1)),
        )
        expected_numbers = _question_numbers(initial_evidence)
        if not expected_numbers:
            raise CommandError("No numbered questions were found in the OCR bundle.")

        native = extract_native_answer_evidence(pdf_data)
        native_trusted = native.trusted_for(expected_numbers)
        authoritative = authoritative_answer_labels(
            native,
            expected_question_numbers=expected_numbers,
        )
        overlaid_root = overlay_native_solution_heading_blocks(
            initial_root,
            pdf_data=pdf_data,
            evidence=native,
            trusted=native_trusted,
        )

        with tempfile.TemporaryDirectory(prefix="ai-amooz-stage4-final-") as tmp:
            overlay_bundle = Path(tmp) / "ocr-overlay.zip"
            _write_overlay_bundle(
                overlay_bundle,
                root=overlaid_root,
                manifest=bundle_manifest,
            )
            kwargs: dict[str, Any] = {
                "pdf": str(pdf_path),
                "bundle": str(overlay_bundle),
                "output_dir": str(output_dir),
                "title": str(options.get("title") or "Stage 4 final acceptance replay"),
                "max_page_batches": max(1, min(40, int(options.get("max_page_batches") or 40))),
                "max_secondary_calls": max(0, min(20, int(options.get("max_secondary_calls") or 12))),
                "total_budget_usd": float(options.get("total_budget_usd") or 5.00),
                "allow_private_transmission": True,
            }
            prior = options.get("prior_provider_cost_usd")
            if prior is not None:
                kwargs["prior_provider_cost_usd"] = float(prior)
            call_command(
                "replay_exam_prep_mistral_stage4_page_batch_live",
                **kwargs,
            )

        manifest_path = output_dir / "manifest.json"
        projection_path = output_dir / "projection.stage4.private.json"
        if not manifest_path.is_file() or not projection_path.is_file():
            raise CommandError("Underlying Stage-4 replay did not produce final artifacts.")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        projection = json.loads(projection_path.read_text(encoding="utf-8"))
        label_audit = _final_label_audit(projection, authoritative=authoritative)
        manifest["nativeAnswerEvidence"] = native.safe_dict(trusted=native_trusted)
        manifest["nativeAnswerLabelAuthorityCount"] = len(authoritative)
        manifest["nativeAnswerLabelIntegrity"] = label_audit
        manifest["finalAcceptanceNativeLabelsPassed"] = bool(
            (not native_trusted) or label_audit.get("passed")
        )
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

        archive = shutil.make_archive(str(output_dir), "zip", root_dir=output_dir)
        self.stdout.write(
            self.style.SUCCESS(
                "Stage 4 FINAL acceptance completed: "
                f"questions={len(expected_numbers)}, nativeTrusted={native_trusted}, "
                f"nativeLabels={len(authoritative)}, "
                f"labelMismatches={label_audit['mismatchCount']}, "
                f"missingLabels={label_audit['missingLabelCount']}, "
                f"stage4Repaired={int(manifest.get('repaired') or 0)}, "
                f"stage4Unresolved={int(manifest.get('unresolved') or 0)}, "
                f"totalEstimatedCostUsd={manifest.get('totalEstimatedCostUsd')}, "
                f"bundle={archive}"
            )
        )
