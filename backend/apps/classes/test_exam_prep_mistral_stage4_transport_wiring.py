from __future__ import annotations


def test_stage4_runtime_installs_provenance_safe_transport():
    # Stage-3 visual imports remain independent of Stage-4 transport. The
    # production Stage-4 facade installs the OpenAI-compatible AvalAI vision seam.
    from apps.classes.services import exam_prep_mistral_stage4_runtime  # noqa: F401
    from apps.classes.services import exam_prep_mistral_stage4_page_batch as page_batch
    from apps.classes.services.exam_prep_mistral_page_batch_transcriber_v4 import (
        transcribe_page_batch,
    )

    assert page_batch.transcribe_page_batch is transcribe_page_batch
