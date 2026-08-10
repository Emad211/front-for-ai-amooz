from __future__ import annotations


def test_shared_facade_installs_provenance_safe_stage4_transport():
    # Importing the shared facade is the production/acceptance bootstrap seam.
    from apps.classes.services import exam_prep_mistral_visual_reconcile  # noqa: F401
    from apps.classes.services import exam_prep_mistral_stage4_page_batch as page_batch
    from apps.classes.services.exam_prep_mistral_page_batch_transcriber_v3 import (
        transcribe_page_batch,
    )

    assert page_batch.transcribe_page_batch is transcribe_page_batch
