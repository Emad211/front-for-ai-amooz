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
    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--max-network-page-requests",
            type=int,
            default=None,
            help=(
                "Acceptance/probe-only hard cap on real Stage-4 page-batch network requests. "
                "Unlike --max-page-batches, this does not reject a document with more suspicious pages."
            ),
        )

    def handle(self, *args, **options):
        previous_transport = live_replay.transcribe_page_batch
        previous_cache_factory = live_replay._cached_page_batch
        raw_cap = options.get("max_network_page_requests")
        network_cap = None if raw_cap is None else max(1, int(raw_cap))

        def capped_cache_factory(*, cache_dir, base_call, counters):
            inner = previous_cache_factory(
                cache_dir=cache_dir,
                base_call=base_call,
                counters=counters,
            )
            if network_cap is None:
                return inner

            def call(**kwargs):
                # Important: check before entering the original cache wrapper.
                # The original wrapper increments networkPageRequests immediately
                # before the provider call, so bypassing it here keeps the manifest
                # counter equal to the number of actual network attempts.
                if int(counters.get("networkPageRequests") or 0) >= network_cap:
                    raise RuntimeError("acceptance_probe_network_page_cap")
                return inner(**kwargs)

            return call

        live_replay.transcribe_page_batch = transcribe_page_batch_v2
        live_replay._cached_page_batch = capped_cache_factory
        try:
            return super().handle(*args, **options)
        finally:
            live_replay.transcribe_page_batch = previous_transport
            live_replay._cached_page_batch = previous_cache_factory
