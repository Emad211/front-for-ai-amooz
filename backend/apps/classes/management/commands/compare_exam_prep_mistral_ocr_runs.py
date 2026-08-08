from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping
import zipfile

from django.core.management.base import BaseCommand, CommandError

from apps.classes.services.exam_prep_mistral_run_comparison import compare_ocr_runs


def _load_bundle(path: Path) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    if path.is_dir():
        raw_path = path / "response.raw.json"
        request_path = path / "request.safe.json"
        if not raw_path.is_file() or not request_path.is_file():
            raise CommandError(
                "Bundle directory is missing response.raw.json or request.safe.json."
            )
        return (
            json.loads(raw_path.read_text(encoding="utf-8")),
            json.loads(request_path.read_text(encoding="utf-8")),
        )
    if not path.is_file() or path.suffix.lower() != ".zip":
        raise CommandError("Bundle must be a ZIP file or extracted bundle directory.")
    try:
        with zipfile.ZipFile(path) as archive:
            return (
                json.loads(archive.read("response.raw.json").decode("utf-8")),
                json.loads(archive.read("request.safe.json").decode("utf-8")),
            )
    except (KeyError, ValueError, zipfile.BadZipFile) as exc:
        raise CommandError("Bundle ZIP is invalid or incomplete.") from exc


def _selected_pages(request: Mapping[str, Any]) -> list[int] | None:
    source = request.get("source")
    if not isinstance(source, Mapping):
        return None
    values = source.get("selectedOriginalPages")
    if not isinstance(values, list):
        return None
    try:
        return [int(value) for value in values]
    except (TypeError, ValueError):
        return None


class Command(BaseCommand):
    help = (
        "Compare two private Mistral OCR diagnostic runs without emitting source text. "
        "Use this to measure run-to-run markdown/formula instability."
    )

    def add_arguments(self, parser):
        parser.add_argument("--first", required=True)
        parser.add_argument("--second", required=True)
        parser.add_argument("--output", required=True)

    def handle(self, *args, **options):
        first_root, first_request = _load_bundle(
            Path(options["first"]).expanduser().resolve()
        )
        second_root, second_request = _load_bundle(
            Path(options["second"]).expanduser().resolve()
        )
        first_pages = _selected_pages(first_request)
        second_pages = _selected_pages(second_request)
        if first_pages != second_pages:
            raise CommandError("The two diagnostic runs used different original pages.")
        try:
            report = compare_ocr_runs(
                first_root,
                second_root,
                original_pages=first_pages,
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        output = Path(options["output"]).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Mistral OCR run comparison completed: "
                f"pages={report['pageCount']}, "
                f"formulaInstabilityPages={report['pagesWithFormulaInstability']}, "
                f"highConfidenceChangedWords={report['highConfidenceChangedWordCount']}, "
                f"report={output}"
            )
        )
