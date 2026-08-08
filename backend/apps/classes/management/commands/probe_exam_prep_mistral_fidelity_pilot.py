from __future__ import annotations

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


_PILOT_MODELS = (
    "gpt-5.4-mini",
    "gemini-3-flash-preview",
)

_PILOT_TARGETS = (
    "question:65",
    "question:94",
    "question:120",
    "solution:50",
    "solution:57",
    "solution:133",
)


class Command(BaseCommand):
    help = (
        "Run the low-cost six-region OCR fidelity calibration using two strong "
        "economical multimodal models. Diagnostic only; no production writes."
    )

    def add_arguments(self, parser):
        parser.add_argument("--bundle", required=True)
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--batch-size", type=int, default=3)
        parser.add_argument("--timeout-seconds", type=float, default=600.0)
        parser.add_argument("--allow-private-transmission", action="store_true")

    def handle(self, *args, **options):
        if not options.get("allow_private_transmission"):
            raise CommandError("Live verifier pilot requires --allow-private-transmission.")
        batch_size = int(options.get("batch_size") or 0)
        if not 1 <= batch_size <= 3:
            raise CommandError("Pilot --batch-size must be between 1 and 3.")

        self.stdout.write(
            "Economical fidelity pilot: "
            f"models={','.join(_PILOT_MODELS)}, "
            f"targets={len(_PILOT_TARGETS)}, batch_size={batch_size}"
        )
        call_command(
            "probe_exam_prep_mistral_fidelity_benchmark",
            bundle=options["bundle"],
            output_dir=options["output_dir"],
            targets=",".join(_PILOT_TARGETS),
            models=",".join(_PILOT_MODELS),
            batch_size=batch_size,
            timeout_seconds=float(options.get("timeout_seconds") or 600.0),
            allow_private_transmission=True,
        )
