from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import re
import shutil
from typing import Any, Mapping
from zipfile import BadZipFile, ZipFile

from django.core.management.base import BaseCommand, CommandError
from PIL import Image
import pypdfium2 as pdfium

from apps.classes.services.exam_prep_mistral_fidelity_benchmark import (
    find_target_regions,
    padded_pixel_box,
    parse_fidelity_targets,
)
from apps.classes.services.exam_prep_mistral_layout_analysis import analyze_ocr_document


_DEFAULT_TARGET = "solution:57"
_DEFAULT_DPIS = (200, 300, 450)


def _parse_dpis(raw: str) -> tuple[int, ...]:
    values: list[int] = []
    for part in str(raw or "").split(","):
        token = part.strip()
        if not token:
            continue
        try:
            dpi = int(token)
        except ValueError as exc:
            raise CommandError("--dpis must be comma-separated integers.") from exc
        if not 100 <= dpi <= 600:
            raise CommandError("Each diagnostic DPI must be between 100 and 600.")
        if dpi not in values:
            values.append(dpi)
    if not values:
        raise CommandError("At least one diagnostic DPI is required.")
    if len(values) > 4:
        raise CommandError("Diagnostic is capped at four DPI renders.")
    return tuple(values)


def _text_stats(value: str) -> dict[str, Any]:
    text = str(value or "")
    private_use = sum(0xE000 <= ord(ch) <= 0xF8FF for ch in text)
    controls = sum(ord(ch) < 32 and ch not in "\r\n\t" for ch in text)
    return {
        "charCount": len(text),
        "replacementCharacterCount": text.count("\ufffd"),
        "visibleBoxCharacterCount": text.count("□"),
        "privateUseCharacterCount": private_use,
        "unexpectedControlCharacterCount": controls,
    }


def _load_success_bundle(path: Path) -> tuple[Mapping[str, Any], Mapping[str, Any], ZipFile]:
    try:
        archive = ZipFile(path)
    except (OSError, BadZipFile) as exc:
        raise CommandError("--bundle must be a readable successful full-document ZIP.") from exc
    names = set(archive.namelist())
    if "failure.json" in names:
        archive.close()
        raise CommandError("--bundle is a failure bundle.")
    try:
        manifest = json.loads(archive.read("manifest.json"))
        root = json.loads(archive.read("response.raw.json"))
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        archive.close()
        raise CommandError("Bundle is missing valid manifest/response JSON.") from exc
    if not isinstance(manifest, Mapping) or not isinstance(root, Mapping):
        archive.close()
        raise CommandError("Bundle manifest/response roots must be objects.")
    return manifest, root, archive


def _selected_pages(manifest: Mapping[str, Any]) -> list[int]:
    values = manifest.get("selectedOriginalPages")
    if isinstance(values, list):
        try:
            return [int(value) for value in values]
        except (TypeError, ValueError):
            return []
    try:
        count = int(manifest.get("pageCount") or 0)
    except (TypeError, ValueError):
        count = 0
    return list(range(1, count + 1)) if count > 0 else []


class Command(BaseCommand):
    help = (
        "Zero-cost diagnostic for a difficult exam-prep region: compare PDFium renders at "
        "multiple DPIs and extract the PDFium text layer. No network/provider calls."
    )

    def add_arguments(self, parser):
        parser.add_argument("--pdf", required=True)
        parser.add_argument("--bundle", required=True)
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--target", default=_DEFAULT_TARGET)
        parser.add_argument("--dpis", default=",".join(str(value) for value in _DEFAULT_DPIS))

    def handle(self, *args, **options):
        pdf_path = Path(options["pdf"]).expanduser().resolve()
        bundle_path = Path(options["bundle"]).expanduser().resolve()
        output_dir = Path(options["output_dir"]).expanduser().resolve()
        if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
            raise CommandError("--pdf must point to an existing PDF.")
        if not bundle_path.is_file():
            raise CommandError("--bundle must point to an existing successful ZIP.")
        if output_dir.exists() and any(output_dir.iterdir()):
            raise CommandError("Output directory must be absent or empty.")
        output_dir.mkdir(parents=True, exist_ok=True)
        dpis = _parse_dpis(options.get("dpis"))
        try:
            targets = parse_fidelity_targets(str(options.get("target") or ""))
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        if len(targets) != 1:
            raise CommandError("--target must identify exactly one question:N or solution:N region.")

        manifest, root, archive = _load_success_bundle(bundle_path)
        try:
            analysis = analyze_ocr_document(root, original_page_numbers=_selected_pages(manifest))
            try:
                selected = find_target_regions(analysis, targets)
            except ValueError as exc:
                raise CommandError(str(exc)) from exc
            item = selected[0]
        finally:
            archive.close()

        page_number = int(item["physicalPageNumber"])
        try:
            document = pdfium.PdfDocument(str(pdf_path))
        except Exception as exc:
            raise CommandError("The source PDF could not be opened with PDFium.") from exc
        try:
            if page_number < 1 or page_number > len(document):
                raise CommandError(f"Resolved physical page {page_number} is outside the source PDF.")
            page = document[page_number - 1]
            try:
                try:
                    textpage = page.get_textpage()
                    try:
                        page_text = textpage.get_text_range()
                    finally:
                        textpage.close()
                except Exception as exc:
                    page_text = ""
                    text_error = type(exc).__name__
                else:
                    text_error = ""

                (output_dir / "page-text-layer.private.txt").write_text(
                    page_text,
                    encoding="utf-8",
                    errors="replace",
                )
                render_rows: list[dict[str, Any]] = []
                for dpi in dpis:
                    bitmap = page.render(scale=float(dpi) / 72.0)
                    try:
                        full = bitmap.to_pil().convert("RGB")
                    finally:
                        bitmap.close()
                    try:
                        box = padded_pixel_box(
                            item["bbox"],
                            width=full.width,
                            height=full.height,
                        )
                        crop = full.crop(box)
                        try:
                            name = f"target-{dpi}dpi.png"
                            crop.save(output_dir / name, format="PNG", optimize=True)
                            render_rows.append(
                                {
                                    "dpi": dpi,
                                    "fullWidth": full.width,
                                    "fullHeight": full.height,
                                    "cropWidth": crop.width,
                                    "cropHeight": crop.height,
                                    "cropFile": name,
                                    "cropBytes": (output_dir / name).stat().st_size,
                                }
                            )
                        finally:
                            crop.close()
                    finally:
                        full.close()
            finally:
                page.close()
        finally:
            document.close()

        report = {
            "schemaVersion": 1,
            "privateDiagnosticBundle": True,
            "productionPipelineChanged": False,
            "providerRequestCount": 0,
            "sourcePdfName": pdf_path.name,
            "sourcePdfBytes": pdf_path.stat().st_size,
            "sourceBundleName": bundle_path.name,
            "target": {
                "itemId": item["itemId"],
                "kind": item["kind"],
                "questionNumber": item["questionNumber"],
                "physicalPageNumber": page_number,
                "bbox": item["bbox"],
            },
            "dpis": list(dpis),
            "renders": render_rows,
            "textLayer": {
                **_text_stats(page_text),
                "extractionErrorType": text_error,
                "privateTextFile": "page-text-layer.private.txt",
            },
        }
        (output_dir / "manifest.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        archive_path = shutil.make_archive(str(output_dir), "zip", root_dir=output_dir)
        self.stdout.write(
            self.style.SUCCESS(
                "PDFium text/render diagnostic completed: "
                f"target={item['itemId']}, page={page_number}, renders={len(render_rows)}, "
                f"textChars={report['textLayer']['charCount']}, providerCalls=0, bundle={archive_path}"
            )
        )
