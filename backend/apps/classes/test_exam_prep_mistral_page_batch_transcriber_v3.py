from __future__ import annotations

from apps.classes.services import exam_prep_mistral_page_batch_transcriber_v2 as v2
from apps.classes.services import exam_prep_mistral_page_batch_transcriber_v3 as v3


def test_final_transport_uses_documented_high_media_resolution():
    part = v3._image_part_high(b"png")
    assert part["mediaResolution"]["level"] == "MEDIA_RESOLUTION_HIGH"
    config = v2._generation_config(3200)
    assert config["mediaResolution"] == "MEDIA_RESOLUTION_HIGH"
    assert config["responseMimeType"] == "application/json"
    assert "responseSchema" in config
