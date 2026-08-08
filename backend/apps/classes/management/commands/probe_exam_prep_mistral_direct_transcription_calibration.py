from __future__ import annotations

from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import time
from typing import Any, Mapping

from django.core.management.base import BaseCommand, CommandError
from PIL import Image
import requests

from apps.chatbot.services.llm_client import part_from_bytes
from apps.classes.management.commands.probe_exam_prep_mistral_fidelity_single_item_calibration import (
    _base_url,
    _cost_meta,
    _load_success_bundle,
    _preflight,
    _provider_content,
    _safe_filename,
    _selected_pages,
)
from apps.classes.services.exam_prep_mistral_direct_transcription import (
    DirectTranscription,
    normalize_direct_transcription,
    numeric_signature,
    summarize_direct_transcriptions,
    text_similarity,
)
from apps.classes.services.exam_prep_mistral_fidelity_benchmark import (
    find_target_regions,
    padded_pixel_box,
    parse_fidelity_targets,
)
from apps.classes.services.exam_prep_mistral_layout_analysis import analyze_ocr_document
from apps.commons.json_utils import extract_json_object


_MODELS = (
    "gpt-5.4-mini",
    "gemini-3-flash-preview",
)

_TARGETS = (
    "question:65",
    "question:94",
    "solution:57",
    "solution:133",
)


def _system_prompt() -> str:
    return (
        "You are a source-faithful transcription engine for Persian high-school exam material. "
        "There is exactly ONE target and exactly ONE source image. The IMAGE is the only source "
        "of truth. Transcribe; do not solve, explain, normalize, or correct from subject knowledge. "
        "Preserve all visible Persian text, digits, signs, option labels, units, Latin letters, and "
        "equations. Use Markdown and LaTeX for linear text/formulas. If a diagram, graph, circuit, "
        "chemical structure, table, or spatial construction carries information that should remain "
        "an image, do NOT invent a textual reconstruction of that visual; set source_visual_required "
        "to true and choose the closest visual_type. Still transcribe visible labels/captions and "
        "surrounding prose. A thin strip of a neighboring question may be present because of crop "
        "padding; ignore content belonging to another printed question number. If any visible source "
        "fragment cannot be read confidently, preserve the best literal reading, set "
        "transcription_uncertain=true, and list only short uncertain fragments. Return ONLY one valid "
        "JSON object, with no Markdown fence and no surrounding prose."
    )


def _json_contract(item: Mapping[str, Any]) -> str:
    return (
        "Return JSON with exactly these top-level keys: "
        '{"transcription_markdown":"full faithful target transcription",'
        '"source_visual_required":true,'
        '"visual_type":"none|diagram|graph|chemical_structure|table|spatial_layout|other",'
        '"transcription_uncertain":false,'
        '"uncertain_fragments":[]}. '
        "JSON string escaping must be valid, including LaTeX backslashes. "
        f"TARGET kind={item['kind']} question_number={item['questionNumber']} "
        f"physical_page={item['physicalPageNumber']}."
    )


def _messages(item: Mapping[str, Any], crop_bytes: bytes) -> list[dict[str, Any]]:
    return [
        {"role": "system", "content": _system_prompt()},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": _json_contract(item)},
                part_from_bytes(data=crop_bytes, mime_type="image/png"),
            ],
        },
    ]


def _parse_transcription(content: str) -> dict[str, Any]:
    obj = extract_json_object(content)
    parsed = DirectTranscription.model_validate(obj)
    return normalize_direct_transcription(parsed)


def _config(bundle: Path) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "sourceBundleName": bundle.name,
        "sourceBundleBytes": bundle.stat().st_size,
        "models": list(_MODELS),
        "targets": list(_TARGETS),
        "oneSourceImagePerProviderCall": True,
        "candidateOcrShownToTranscriber": False,
        "automaticRetry": False,
        "automaticPaidRepair": False,
    }


def _call_once(
    *,
    model: str,
    item: Mapping[str, Any],
    crop_bytes: bytes,
    api_key: str,
    timeout: float,
    output_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    item_id = str(item["itemId"])
    prefix = f"transcriber.{_safe_filename(model)}.{item_id}"
    payload = {
        "model": model,
        "messages": _messages(item, crop_bytes),
        "response_format": {"type": "json_object"},
    }
    (output_dir / f"{prefix}.request.safe.json").write_text(
        json.dumps(
            {
                "privateDiagnosticBundle": True,
                "model": model,
                "itemId": item_id,
                "imageCount": 1,
                "candidateOcrIncluded": False,
                "responseFormat": "json_object",
                "automaticRetry": False,
                "automaticPaidRepair": False,
                "endpoint": f"{_base_url()}/chat/completions",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    started = time.monotonic()
    try:
        response = requests.post(
            f"{_base_url()}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"provider_transport:{type(exc).__name__}") from exc
    latency_ms = round((time.monotonic() - started) * 1000, 2)
    (output_dir / f"{prefix}.provider.private.json").write_bytes(response.content)

    root: Mapping[str, Any] = {}
    try:
        decoded = response.json()
        if isinstance(decoded, Mapping):
            root = decoded
    except ValueError:
        root = {}
    meta = {
        "model": model,
        "itemId": item_id,
        **_cost_meta(root, status_code=response.status_code, latency_ms=latency_ms),
    }
    (output_dir / f"{prefix}.response.safe.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if not response.ok:
        raise RuntimeError(f"provider_http_{response.status_code}")
    if not root:
        raise RuntimeError("provider_non_json_root")
    try:
        transcript = _parse_transcription(_provider_content(root))
    except Exception as exc:
        raise RuntimeError(f"provider_transcription_invalid:{type(exc).__name__}") from exc
    row = {"itemId": item_id, **transcript}
    (output_dir / f"{prefix}.transcript.private.json").write_text(
        json.dumps(row, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return row, meta


class Command(BaseCommand):
    help = (
        "Directly transcribe four difficult OCR regions from one source crop per call with two "
        "economical multimodal models. Candidate OCR is hidden from the transcribers."
    )

    def add_arguments(self, parser):
        parser.add_argument("--bundle", required=True)
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--timeout-seconds", type=float, default=600.0)
        parser.add_argument("--resume", action="store_true")
        parser.add_argument("--allow-private-transmission", action="store_true")

    def handle(self, *args, **options):
        if not options.get("allow_private_transmission"):
            raise CommandError("Live direct-transcription calibration requires --allow-private-transmission.")
        api_key = (os.getenv("AVALAI_API_KEY") or "").strip()
        if not api_key:
            raise CommandError("AVALAI_API_KEY is required in this PowerShell session.")
        timeout = max(30.0, float(options.get("timeout_seconds") or 600.0))
        bundle = Path(options["bundle"]).expanduser().resolve()
        if not bundle.is_file():
            raise CommandError("--bundle must point to an existing successful ZIP.")
        output_dir = Path(options["output_dir"]).expanduser().resolve()
        resume = bool(options.get("resume"))
        expected_config = _config(bundle)

        if output_dir.exists() and any(output_dir.iterdir()):
            if not resume:
                raise CommandError("Output directory is non-empty; use --resume only for this exact calibration run.")
            try:
                prior = json.loads((output_dir / "direct-transcription-config.safe.json").read_text(encoding="utf-8"))
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                raise CommandError("Resume directory has no valid direct-transcription config.") from exc
            if prior != expected_config:
                raise CommandError("Resume directory config does not match this calibration run.")
        else:
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "direct-transcription-config.safe.json").write_text(
                json.dumps(expected_config, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        preflight = _preflight(models=_MODELS, api_key=api_key, timeout=timeout)
        (output_dir / "model-preflight.safe.json").write_text(
            json.dumps(preflight, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if any(not row.get("accessible") for row in preflight):
            archive_path = shutil.make_archive(str(output_dir), "zip", root_dir=output_dir)
            raise CommandError(
                "One or more transcription models are inaccessible; no source crop was sent. "
                f"bundle={archive_path}"
            )

        manifest, root, archive = _load_success_bundle(bundle)
        try:
            analysis = analyze_ocr_document(root, original_page_numbers=_selected_pages(manifest))
            targets = parse_fidelity_targets(",".join(_TARGETS))
            try:
                selected = find_target_regions(analysis, targets)
            except ValueError as exc:
                raise CommandError(str(exc)) from exc

            private_items: list[dict[str, Any]] = []
            public_items: list[dict[str, Any]] = []
            for item in selected:
                page_number = int(item["physicalPageNumber"])
                page_name = f"page-{page_number:03d}.original.png"
                try:
                    page_bytes = archive.read(page_name)
                except KeyError as exc:
                    raise CommandError(f"Bundle is missing {page_name}.") from exc
                with Image.open(BytesIO(page_bytes)) as source:
                    image = source.convert("RGB")
                try:
                    box = padded_pixel_box(item["bbox"], width=image.width, height=image.height)
                    crop = image.crop(box)
                    try:
                        crop_path = output_dir / f"{item['itemId']}.png"
                        crop.save(crop_path, format="PNG", optimize=True)
                        crop_bytes = crop_path.read_bytes()
                    finally:
                        crop.close()
                finally:
                    image.close()
                if len(crop_bytes) > 10 * 1024 * 1024:
                    raise CommandError(f"Crop {item['itemId']} exceeds 10 MiB.")
                private_items.append({**item, "cropBytes": crop_bytes})
                public_items.append(
                    {
                        "itemId": item["itemId"],
                        "kind": item["kind"],
                        "questionNumber": item["questionNumber"],
                        "physicalPageNumber": page_number,
                        "regionIssues": item["regionIssues"],
                        "cropFile": f"{item['itemId']}.png",
                    }
                )
        finally:
            archive.close()

        (output_dir / "baseline-mistral.private.json").write_text(
            json.dumps(
                [
                    {key: value for key, value in item.items() if key != "cropBytes"}
                    for item in private_items
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (output_dir / "targets.json").write_text(
            json.dumps(public_items, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        transcripts_by_model: dict[str, list[dict[str, Any]]] = {model: [] for model in _MODELS}
        call_meta: list[dict[str, Any]] = []
        completed = 0
        current_model = ""
        current_item_id = ""
        try:
            for model in _MODELS:
                for item in private_items:
                    current_model = model
                    current_item_id = str(item["itemId"])
                    prefix = f"transcriber.{_safe_filename(model)}.{current_item_id}"
                    transcript_path = output_dir / f"{prefix}.transcript.private.json"
                    response_meta_path = output_dir / f"{prefix}.response.safe.json"
                    if resume and transcript_path.exists() and response_meta_path.exists():
                        transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
                        meta = json.loads(response_meta_path.read_text(encoding="utf-8"))
                    else:
                        transcript, meta = _call_once(
                            model=model,
                            item=item,
                            crop_bytes=item["cropBytes"],
                            api_key=api_key,
                            timeout=timeout,
                            output_dir=output_dir,
                        )
                    transcripts_by_model[model].append(transcript)
                    call_meta.append(meta)
                    completed += 1
        except Exception as exc:
            (output_dir / "failure.json").write_text(
                json.dumps(
                    {
                        "privateDiagnosticBundle": True,
                        "productionPipelineChanged": False,
                        "stage": "direct_transcription",
                        "errorType": type(exc).__name__,
                        "error": str(exc)[:800],
                        "failedModel": current_model,
                        "failedItemId": current_item_id,
                        "completedOrResumedItems": completed,
                        "automaticRetry": False,
                        "automaticPaidRepair": False,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            archive_path = shutil.make_archive(str(output_dir), "zip", root_dir=output_dir)
            raise CommandError(f"Direct-transcription calibration failed; partial bundle={archive_path}") from exc

        summary = summarize_direct_transcriptions(
            targets=public_items,
            transcripts_by_model=transcripts_by_model,
        )
        baseline_by_id = {str(item["itemId"]): item for item in private_items}
        comparison_rows: list[dict[str, Any]] = []
        for model, rows in transcripts_by_model.items():
            for row in rows:
                item_id = str(row["itemId"])
                baseline = str(baseline_by_id[item_id].get("candidateText") or "")
                transcript = str(row.get("transcriptionMarkdown") or "")
                comparison_rows.append(
                    {
                        "model": model,
                        "itemId": item_id,
                        "textSimilarityToMistral": text_similarity(baseline, transcript),
                        "numericSignatureMatchesMistral": numeric_signature(baseline) == numeric_signature(transcript),
                    }
                )
        summary["baselineComparison"] = comparison_rows
        (output_dir / "comparison.safe.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (output_dir / "provider-calls.safe.json").write_text(
            json.dumps(call_meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        for model, rows in transcripts_by_model.items():
            (output_dir / f"transcriber.{_safe_filename(model)}.private.json").write_text(
                json.dumps(rows, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        manifest_out = {
            "schemaVersion": 1,
            "privateDiagnosticBundle": True,
            "productionPipelineChanged": False,
            "models": list(_MODELS),
            "itemCount": len(private_items),
            "acceptedTranscriptCount": sum(len(rows) for rows in transcripts_by_model.values()),
            "expectedProviderCalls": len(_MODELS) * len(private_items),
            "oneSourceImagePerProviderCall": True,
            "candidateOcrShownToTranscriber": False,
            "providerRetryPerCall": 0,
            "paidRepairBudgetPerCall": 0,
            "estimatedTotalUnit": round(sum(float(row.get("estimatedUnit") or 0) for row in call_meta), 8),
            "estimatedTotalIrt": round(sum(float(row.get("estimatedIrt") or 0) for row in call_meta), 2),
            "acceptance": {
                "allTargetsResolvedLocally": len(private_items) == len(_TARGETS),
                "allTranscriptsAccepted": sum(len(rows) for rows in transcripts_by_model.values()) == len(_MODELS) * len(private_items),
                "exactExpectedProviderResponses": len(call_meta) == len(_MODELS) * len(private_items),
            },
        }
        manifest_out["acceptance"]["passed"] = all(manifest_out["acceptance"].values())
        (output_dir / "manifest.json").write_text(
            json.dumps(manifest_out, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        archive_path = shutil.make_archive(str(output_dir), "zip", root_dir=output_dir)
        self.stdout.write(
            self.style.SUCCESS(
                "Direct-transcription calibration completed: "
                f"items={len(private_items)}, calls={len(call_meta)}, "
                f"numericDisagreements={summary['numericSignatureDisagreementCount']}, "
                f"visualDisagreements={summary['visualRequirementDisagreementCount']}, "
                f"bundle={archive_path}"
            )
        )
