from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import shutil
from typing import Any, Mapping
from zipfile import BadZipFile, ZipFile

from django.core.management.base import BaseCommand, CommandError
from PIL import Image
import pypdfium2 as pdfium

from apps.classes.services.exam_prep_mistral_fidelity_benchmark import padded_pixel_box
from apps.classes.services.exam_prep_mistral_gold_benchmark import (
    GoldTarget,
    gold_targets,
    resolve_gold_target_regions,
)
from apps.classes.services.exam_prep_mistral_layout_analysis import analyze_ocr_document


# These frozen regions exposed square/tofu glyphs or other source-render uncertainty
# while blind-annotating the first gold source pack. They cover question math plus
# several solution pages, so one local run can tell whether the problem is PDFium-
# specific or inherent to the PDF/font data.
_DEFAULT_ITEM_IDS = (
    "q-122",
    "s-046",
    "s-055",
    "s-056",
    "s-057",
    "s-065",
    "s-073",
    "s-081",
    "s-115",
    "s-150",
)


def _parse_item_ids(raw: str | None) -> tuple[str, ...]:
    values: list[str] = []
    for part in str(raw or "").split(","):
        value = part.strip().lower()
        if value and value not in values:
            values.append(value)
    if not values:
        return _DEFAULT_ITEM_IDS
    valid = {target.item_id for target in gold_targets()}
    unknown = sorted(set(values) - valid)
    if unknown:
        raise CommandError(f"Unknown gold item ids: {unknown}")
    return tuple(values)


def _load_bundle(path: Path) -> tuple[Mapping[str, Any], Mapping[str, Any], ZipFile]:
    try:
        archive = ZipFile(path)
    except (OSError, BadZipFile) as exc:
        raise CommandError("--bundle must point to a readable successful full-document ZIP.") from exc
    names = set(archive.namelist())
    if "failure.json" in names:
        archive.close()
        raise CommandError("--bundle is a failure bundle.")
    try:
        manifest = json.loads(archive.read("manifest.json"))
        root = json.loads(archive.read("response.raw.json"))
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        archive.close()
        raise CommandError("Bundle is missing valid manifest.json/response.raw.json.") from exc
    if not isinstance(manifest, Mapping) or not isinstance(root, Mapping):
        archive.close()
        raise CommandError("Bundle manifest/response roots must be JSON objects.")
    return manifest, root, archive


def _original_pages(manifest: Mapping[str, Any]) -> list[int]:
    raw = manifest.get("selectedOriginalPages")
    if isinstance(raw, list):
        try:
            return [int(value) for value in raw]
        except (TypeError, ValueError):
            return []
    try:
        count = int(manifest.get("pageCount") or 0)
    except (TypeError, ValueError):
        count = 0
    return list(range(1, count + 1)) if count > 0 else []


def _target_rows(item_ids: tuple[str, ...]) -> tuple[GoldTarget, ...]:
    indexed = {target.item_id: target for target in gold_targets()}
    return tuple(indexed[item_id] for item_id in item_ids)


def _render_pdfium_page(document: pdfium.PdfDocument, page_number: int, dpi: int) -> Image.Image:
    page = document[page_number - 1]
    try:
        bitmap = page.render(scale=dpi / 72.0)
        try:
            return bitmap.to_pil().convert("RGB")
        finally:
            bitmap.close()
    finally:
        page.close()


def _crop_and_save(
    *,
    image: Image.Image,
    bbox: list[float],
    path: Path,
) -> None:
    box = padded_pixel_box(bbox, width=image.width, height=image.height, padding_ratio=0.012)
    crop = image.crop(box)
    try:
        crop.save(path, format="PNG", optimize=True)
    finally:
        crop.close()


class Command(BaseCommand):
    help = (
        "Render the same frozen gold regions with PDFium and PyMuPDF to diagnose "
        "Persian/font tofu artifacts. Zero provider calls; diagnostic only."
    )

    def add_arguments(self, parser):
        parser.add_argument("--pdf", required=True)
        parser.add_argument("--bundle", required=True)
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--dpi", type=int, default=240)
        parser.add_argument(
            "--items",
            default=",".join(_DEFAULT_ITEM_IDS),
            help="Comma-separated frozen gold item ids.",
        )

    def handle(self, *args, **options):
        try:
            import fitz  # PyMuPDF; optional diagnostic dependency.
        except ImportError as exc:
            raise CommandError(
                "PyMuPDF is required only for this renderer diagnostic. Install it in the "
                "active virtualenv with: python -m pip install PyMuPDF"
            ) from exc

        pdf_path = Path(options["pdf"]).expanduser().resolve()
        bundle_path = Path(options["bundle"]).expanduser().resolve()
        output_dir = Path(options["output_dir"]).expanduser().resolve()
        if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
            raise CommandError("--pdf must point to the original PDF.")
        if not bundle_path.is_file():
            raise CommandError("--bundle must point to the successful full-document ZIP.")
        if output_dir.exists() and any(output_dir.iterdir()):
            raise CommandError("Output directory must be absent or empty.")
        output_dir.mkdir(parents=True, exist_ok=True)
        dpi = int(options.get("dpi") or 0)
        if not 144 <= dpi <= 450:
            raise CommandError("--dpi must be between 144 and 450.")
        item_ids = _parse_item_ids(options.get("items"))
        targets = _target_rows(item_ids)

        manifest, root, archive = _load_bundle(bundle_path)
        archive.close()  # Source page PNGs are deliberately not used in this diagnostic.
        analysis = analyze_ocr_document(root, original_page_numbers=_original_pages(manifest))
        try:
            selected = resolve_gold_target_regions(analysis, targets=targets)
        except ValueError as exc:
            raise CommandError(f"Renderer diagnostic target resolution failed: {exc}") from exc
        indexed = {str(row["itemId"]): row for row in selected}

        try:
            pdfium_doc = pdfium.PdfDocument(str(pdf_path))
        except Exception as exc:
            raise CommandError("PDFium could not open the source PDF.") from exc
        try:
            try:
                mupdf_doc = fitz.open(str(pdf_path))
            except Exception as exc:
                raise CommandError("PyMuPDF could not open the source PDF.") from exc
            try:
                page_numbers = sorted({int(row["physicalPageNumber"]) for row in selected})
                if max(page_numbers, default=0) > len(pdfium_doc) or max(page_numbers, default=0) > mupdf_doc.page_count:
                    raise CommandError("Resolved page number exceeds source PDF page count.")

                public_rows: list[dict[str, Any]] = []
                for page_number in page_numbers:
                    pdfium_image = _render_pdfium_page(pdfium_doc, page_number, dpi)
                    try:
                        mupdf_page = mupdf_doc.load_page(page_number - 1)
                        matrix = fitz.Matrix(dpi / 72.0, dpi / 72.0)
                        pixmap = mupdf_page.get_pixmap(matrix=matrix, alpha=False)
                        mupdf_image = Image.open(BytesIO(pixmap.tobytes("png"))).convert("RGB")
                        try:
                            for item_id in item_ids:
                                row = indexed[item_id]
                                if int(row["physicalPageNumber"]) != page_number:
                                    continue
                                pdfium_file = f"{item_id}.pdfium.png"
                                mupdf_file = f"{item_id}.pymupdf.png"
                                _crop_and_save(
                                    image=pdfium_image,
                                    bbox=list(row["bbox"]),
                                    path=output_dir / pdfium_file,
                                )
                                _crop_and_save(
                                    image=mupdf_image,
                                    bbox=list(row["bbox"]),
                                    path=output_dir / mupdf_file,
                                )
                                public_rows.append(
                                    {
                                        "itemId": item_id,
                                        "physicalPageNumber": page_number,
                                        "bbox": list(row["bbox"]),
                                        "pdfiumFile": pdfium_file,
                                        "pymupdfFile": mupdf_file,
                                    }
                                )
                        finally:
                            mupdf_image.close()
                    finally:
                        pdfium_image.close()
            finally:
                mupdf_doc.close()
        finally:
            pdfium_doc.close()

        public_rows.sort(key=lambda row: item_ids.index(str(row["itemId"])))
        (output_dir / "items.safe.json").write_text(
            json.dumps(public_rows, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        manifest_out = {
            "schemaVersion": 1,
            "contentFree": True,
            "privateDiagnosticBundle": True,
            "productionPipelineChanged": False,
            "providerRequestCount": 0,
            "dpi": dpi,
            "itemCount": len(public_rows),
            "itemIds": list(item_ids),
            "renderers": {
                "pdfium": "pypdfium2",
                "pymupdf": str(getattr(fitz, "VersionBind", "unknown")),
            },
            "purpose": "decide whether blind-gold source crops need an alternate renderer",
        }
        (output_dir / "manifest.safe.json").write_text(
            json.dumps(manifest_out, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (output_dir / "README.txt").write_text(
            "AI-AMOOZ ZERO-COST RENDERER A/B\n"
            "providerRequestCount=0\n"
            "Compare *.pdfium.png with *.pymupdf.png for square/tofu Persian glyphs.\n"
            "Do not use OCR/model output to decide which source rendering is correct.\n",
            encoding="utf-8",
        )
        archive_path = shutil.make_archive(str(output_dir), "zip", root_dir=output_dir)
        self.stdout.write(
            self.style.SUCCESS(
                "Renderer A/B completed: providerRequests=0, "
                f"items={len(public_rows)}, bundle={archive_path}"
            )
        )
