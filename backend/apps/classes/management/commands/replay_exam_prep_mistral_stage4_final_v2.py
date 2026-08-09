"""Final acceptance command using the current Gemini structured transport."""
from __future__ import annotations

from apps.classes.management.commands import (
    replay_exam_prep_mistral_stage4_page_batch_live as live_replay,
)
from apps.classes.management.commands.replay_exam_prep_mistral_stage4_final import (
    Command as FinalAcceptanceCommand,
)
from apps.classes.services.exam_prep_mistral_page_batch_transcriber_v2 import (
    transcribe_page_batch as transcribe_page_batch_v2,
)


class Command(FinalAcceptanceCommand):
    def handle(self, *args, **options):
        previous = live_replay.transcribe_page_batch
        live_replay.transcribe_page_batch = transcribe_page_batch_v2
        try:
            return super().handle(*args, **options)
        finally:
            live_replay.transcribe_page_batch = previous
