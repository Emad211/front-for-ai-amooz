from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence
from zipfile import BadZipFile, ZipFile

from django.core.management.base import BaseCommand, CommandError

from apps.classes.services.exam_prep_mistral_solution_headings import (
    AlignedSolutionHeading,
    align_solution_headings,
    solution_heading_candidates,
)
from apps.classes.services.exam_prep_mistral_targeted_recovery import (
    collect_crop_headings,
    resolve_target_questions,
)


def _load_bundle(path: Path) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    if not path.is_file() or path.suffix.lower() != ".zip":
        raise CommandError("Bundle must point to an existing ZIP file.")
    try:
        with ZipFile(path) as archive:
            names = set(archive.namelist())
            if "failure.json" in names and "response.raw.json" not in names:
                failure = json.loads(archive.read("failure.json").decode("utf-8"))
                raise CommandError(
                    "Cannot audit a failed OCR bundle: "
                    f"code={failure.get('providerErrorCode') or 'unknown'}; "
                    f"retryable={failure.get('retryable')}"
                )
            metadata_name = (
                "request.safe.json"
                if "request.safe.json" in names
                else "manifest.json"
                if "manifest.json" in names
                else ""
            )
            if not metadata_name:
                raise CommandError(
                    "Bundle is missing request.safe.json or manifest.json metadata."
                )
            return (
                json.loads(archive.read("response.raw.json").decode("utf-8")),
                json.loads(archive.read(metadata_name).decode("utf-8")),
            )
    except CommandError:
        raise
    except (OSError, BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CommandError("Bundle ZIP is invalid or incomplete.") from exc


def _selected_pages(request: Mapping[str, Any]) -> list[int] | None:
    values = request.get("selectedOriginalPages")
    if not isinstance(values, list):
        source = request.get("source")
        source = source if isinstance(source, Mapping) else {}
        values = source.get("selectedOriginalPages")
    if not isinstance(values, list):
        return None
    try:
        return [int(value) for value in values]
    except (TypeError, ValueError):
        return None


def _crop_specs(request: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    source = request.get("source")
    source = source if isinstance(source, Mapping) else {}
    values = source.get("cropSpecs")
    if not isinstance(values, list):
        raise CommandError("Targeted bundle request is missing source.cropSpecs.")
    output = [item for item in values if isinstance(item, Mapping)]
    if len(output) != len(values):
        raise CommandError("Targeted bundle cropSpecs are malformed.")
    return output


def _base_alignment(
    root: Mapping[str, Any],
    *,
    original_pages: Sequence[int] | None,
    first_question: int,
    last_question: int,
) -> dict[str, Any]:
    raw_pages = [
        page for page in (root.get("pages") or []) if isinstance(page, Mapping)
    ]
    raw_pages.sort(key=lambda page: int(page.get("index") or 0))
    mapping = list(original_pages or [])
    candidates = []
    for position, page in enumerate(raw_pages):
        provider_index = int(page.get("index") or 0)
        physical_page = (
            int(mapping[position]) if position < len(mapping) else provider_index + 1
        )
        candidates.extend(
            solution_heading_candidates(
                page,
                physical_page_number=physical_page,
            )
        )
    return align_solution_headings(
        candidates,
        first_expected_question=first_question,
        last_expected_question=last_question,
    )


def _parse_target_override(value: str | None) -> list[int] | None:
    if not value:
        return None
    output: list[int] = []
    for token in value.split(","):
        try:
            number = int(token.strip())
        except ValueError as exc:
            raise CommandError("--target-questions must be comma-separated integers.") from exc
        if number < 1:
            raise CommandError("--target-questions values must be positive.")
        if number not in output:
            output.append(number)
    return output


class Command(BaseCommand):
    help = (
        "Audit a successful targeted solution-gap OCR bundle against the full-document "
        "base run. The report is content-free and never lets non-target crop OCR "
        "overwrite already accepted base headings."
    )

    def add_arguments(self, parser):
        parser.add_argument("--base", required=True)
        parser.add_argument("--targeted", required=True)
        parser.add_argument("--output", required=True)
        parser.add_argument("--first-question", type=int, default=1)
        parser.add_argument("--last-question", type=int, default=155)
        parser.add_argument("--target-questions")

    def handle(self, *args, **options):
        base_root, base_request = _load_bundle(
            Path(options["base"]).expanduser().resolve()
        )
        targeted_root, targeted_request = _load_bundle(
            Path(options["targeted"]).expanduser().resolve()
        )
        first_question = max(1, int(options["first_question"]))
        last_question = int(options["last_question"])
        if last_question < first_question:
            raise CommandError("--last-question must not be smaller than --first-question.")

        aligned = _base_alignment(
            base_root,
            original_pages=_selected_pages(base_request),
            first_question=first_question,
            last_question=last_question,
        )
        accepted_all: list[AlignedSolutionHeading] = list(aligned["accepted"])
        accepted = [
            item
            for item in accepted_all
            if first_question <= item.question_number <= last_question
        ]
        out_of_range_accepted = sorted(
            {
                item.question_number
                for item in accepted_all
                if not first_question <= item.question_number <= last_question
            }
        )
        base_options = {
            item.question_number: item.option_label
            for item in accepted
            if item.option_label_valid and isinstance(item.option_label, int)
        }
        base_missing = list(aligned["missingQuestionNumbers"])
        base_invalid = sorted(
            {
                item.question_number
                for item in accepted
                if not item.option_label_valid
            }
        )

        target_override = _parse_target_override(options.get("target_questions"))
        target_questions = (
            target_override
            if target_override is not None
            else sorted(set(base_missing) | set(base_invalid))
        )
        crop_specs = _crop_specs(targeted_request)
        headings = collect_crop_headings(targeted_root, crop_specs)
        resolution = resolve_target_questions(headings, target_questions)
        recovered_map = {
            int(item["questionNumber"]): int(item["optionLabel"])
            for item in resolution["recovered"]
        }

        non_target_grouped: dict[int, list[Mapping[str, Any]]] = {}
        target_set = set(target_questions)
        for item in headings:
            question = int(item.get("rawQuestionNumber") or 0)
            if question < 1 or question in target_set:
                continue
            non_target_grouped.setdefault(question, []).append(item)

        disagreements: list[dict[str, Any]] = []
        non_target_invalid: list[dict[str, Any]] = []
        for question, values in sorted(non_target_grouped.items()):
            crop_valid = sorted(
                {
                    int(item["optionLabel"])
                    for item in values
                    if item.get("optionLabelValid") is True
                    and isinstance(item.get("optionLabel"), int)
                }
            )
            invalid_raw = sorted(
                {
                    int(item["rawOptionLabel"])
                    for item in values
                    if item.get("optionLabelValid") is not True
                    and isinstance(item.get("rawOptionLabel"), int)
                }
            )
            if invalid_raw:
                non_target_invalid.append(
                    {
                        "questionNumber": question,
                        "rawOptionLabels": invalid_raw,
                    }
                )
            base_option = base_options.get(question)
            if base_option is not None and len(crop_valid) == 1 and crop_valid[0] != base_option:
                disagreements.append(
                    {
                        "questionNumber": question,
                        "baseOptionLabel": base_option,
                        "targetedOptionLabel": crop_valid[0],
                    }
                )

        recovered_missing = sorted(set(base_missing) & set(recovered_map))
        recovered_invalid = sorted(set(base_invalid) & set(recovered_map))
        remaining_missing = sorted(set(base_missing) - set(recovered_map))
        remaining_invalid = sorted(set(base_invalid) - set(recovered_map))
        base_unique = len({item.question_number for item in accepted})
        projected_unique = base_unique + len(recovered_missing)
        expected_total = last_question - first_question + 1
        ready = (
            resolution["complete"]
            and not remaining_missing
            and not remaining_invalid
            and projected_unique == expected_total
        )

        report = {
            "schemaVersion": 2,
            "contentFree": True,
            "safeMergePolicy": "target_questions_only",
            "base": {
                "acceptedHeadingCount": len(accepted),
                "uniqueAcceptedQuestionCount": base_unique,
                "outOfRangeAcceptedQuestionNumbers": out_of_range_accepted,
                "missingQuestionNumbers": base_missing,
                "invalidOptionQuestionNumbers": base_invalid,
            },
            "targeted": {
                "cropCount": len(crop_specs),
                "detectedHeadingCount": len(headings),
                "targetQuestionNumbers": target_questions,
                "recoveredTargets": resolution["recovered"],
                "unresolvedTargetQuestions": resolution["unresolvedQuestionNumbers"],
                "targetConflicts": resolution["conflicts"],
                "nonTargetValidDisagreements": disagreements,
                "nonTargetInvalidHeadings": non_target_invalid,
            },
            "projected": {
                "recoveredMissingQuestionNumbers": recovered_missing,
                "recoveredInvalidOptionQuestionNumbers": recovered_invalid,
                "remainingMissingQuestionNumbers": remaining_missing,
                "remainingInvalidOptionQuestionNumbers": remaining_invalid,
                "uniqueSolutionQuestionCount": projected_unique,
                "expectedSolutionQuestionCount": expected_total,
                "readyForBoundaryMerge": ready,
            },
        }

        output = Path(options["output"]).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Mistral targeted recovery audit completed: "
                f"detected={len(headings)}, targets={len(target_questions)}, "
                f"recovered={len(resolution['recovered'])}, "
                f"projectedSolutions={projected_unique}/{expected_total}, "
                f"ready={ready}, output={output}"
            )
        )
