from __future__ import annotations

import json
from pathlib import Path
import zipfile
from typing import Any, Mapping

from django.core.management.base import BaseCommand, CommandError

from apps.classes.services.exam_prep_mistral_solution_headings import (
    audit_solution_headings,
)


def _load_json_member(archive: zipfile.ZipFile, name: str) -> Mapping[str, Any]:
    try:
        value = json.loads(archive.read(name).decode("utf-8"))
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CommandError(f"Bundle is missing valid {name}.") from exc
    if not isinstance(value, Mapping):
        raise CommandError(f"{name} must contain one JSON object.")
    return value


class Command(BaseCommand):
    help = (
        "Audit solution-heading coverage/alignment in a successful private Mistral OCR "
        "bundle. The emitted JSON is content-free and makes no provider request."
    )

    def add_arguments(self, parser):
        parser.add_argument("--bundle", required=True)
        parser.add_argument("--output", required=True)
        parser.add_argument("--first-question", type=int, default=1)
        parser.add_argument("--last-question", type=int, default=155)

    def handle(self, *args, **options):
        bundle = Path(options["bundle"]).expanduser().resolve()
        if not bundle.is_file() or bundle.suffix.lower() != ".zip":
            raise CommandError("--bundle must point to an existing ZIP file.")
        try:
            archive = zipfile.ZipFile(bundle)
        except (OSError, zipfile.BadZipFile) as exc:
            raise CommandError("The supplied bundle is not a readable ZIP.") from exc
        with archive:
            names = set(archive.namelist())
            if "failure.json" in names and "response.raw.json" not in names:
                failure = _load_json_member(archive, "failure.json")
                raise CommandError(
                    "Cannot audit a failed OCR bundle: "
                    f"chunk={failure.get('failedChunkIndex')}, "
                    f"httpStatus={failure.get('httpStatus')}, "
                    f"reason={failure.get('reason')}."
                )
            root = _load_json_member(archive, "response.raw.json")
            manifest = _load_json_member(archive, "manifest.json")

        selected = manifest.get("selectedOriginalPages")
        original_pages = (
            [int(value) for value in selected]
            if isinstance(selected, list)
            else None
        )
        report = audit_solution_headings(
            root,
            original_page_numbers=original_pages,
            first_expected_question=max(1, int(options["first_question"])),
            last_expected_question=max(1, int(options["last_question"])),
        )
        output = Path(options["output"]).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Mistral OCR solution-heading audit completed: "
                f"candidates={report['rawCandidateCount']}, "
                f"accepted={report['acceptedHeadingCount']}, "
                f"missing={len(report['missingSolutionHeadingNumbers'])}, "
                f"recovered={report['recoveryCount']}, "
                f"invalidOptions={len(report['invalidOptionLabels'])}, "
                f"output={output}"
            )
        )
