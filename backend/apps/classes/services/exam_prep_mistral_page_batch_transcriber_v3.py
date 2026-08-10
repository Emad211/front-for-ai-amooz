"""Final Stage-4 Gemini transport policy.

Keeps the v2 transport/validation/provenance contract intact and installs only
the documented Gemini 3 media-resolution spelling before requests are made.
The patch is process-wide and idempotent, so there is no per-call mutation or
thread race.
"""
from __future__ import annotations

import base64
from typing import Any

from . import exam_prep_mistral_page_batch_transcriber_v2 as v2


BatchItem = v2.BatchItem
BatchOption = v2.BatchOption
BatchUncertainSpan = v2.BatchUncertainSpan
PageBatchEnvelopeError = v2.PageBatchEnvelopeError
PageBatchResult = v2.PageBatchResult


def _image_part_high(payload: bytes) -> dict[str, Any]:
    return {
        "inlineData": {
            "mimeType": "image/png",
            "data": base64.b64encode(payload).decode("ascii"),
        },
        "mediaResolution": {"level": "MEDIA_RESOLUTION_HIGH"},
    }


# Capture v2's proven responseSchema config before installing our one-time media
# policy. The helper then adds the documented global fallback.
_ORIGINAL_GENERATION_CONFIG = v2._generation_config


def _generation_config_high(maximum: int) -> dict[str, Any]:
    value = dict(_ORIGINAL_GENERATION_CONFIG(maximum))
    value["mediaResolution"] = "MEDIA_RESOLUTION_HIGH"
    return value


v2._image_part_high = _image_part_high
v2._generation_config = _generation_config_high

transcribe_page_batch = v2.transcribe_page_batch


__all__ = [
    "BatchItem",
    "BatchOption",
    "BatchUncertainSpan",
    "PageBatchEnvelopeError",
    "PageBatchResult",
    "transcribe_page_batch",
]
