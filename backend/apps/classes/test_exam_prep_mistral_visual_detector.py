from __future__ import annotations

from io import BytesIO

from PIL import Image

from apps.classes.services import exam_prep_mistral_visual_runtime as runtime


def test_bounded_detector_downsamples_mask_but_preserves_normalized_ocr_geometry(monkeypatch):
    monkeypatch.setenv("EXAM_PREP_VISUAL_DETECTOR_MAX_DIMENSION", "800")
    image = Image.new("RGB", (2000, 1000), "white")
    raw_page = {
        "dimensions": {"width": 2000, "height": 1000},
        "blocks": [
            {
                "type": "image",
                "content": "",
                "bbox": {
                    "x0": 400,
                    "y0": 200,
                    "x1": 1200,
                    "y1": 700,
                },
            }
        ],
    }
    try:
        payload, detector_page = runtime._bounded_detector_page(image, raw_page)
    finally:
        image.close()

    with Image.open(BytesIO(payload)) as rendered:
        assert rendered.size == (800, 400)

    assert detector_page["dimensions"] == {"width": 800, "height": 400}
    assert detector_page["blocks"] == [
        {"x0": 0.2, "y0": 0.2, "x1": 0.6, "y1": 0.7}
    ]


def test_detector_dimension_is_bounded_even_for_bad_environment_values(monkeypatch):
    monkeypatch.setenv("EXAM_PREP_VISUAL_DETECTOR_MAX_DIMENSION", "50")
    assert runtime._detector_max_dimension() == 600
    monkeypatch.setenv("EXAM_PREP_VISUAL_DETECTOR_MAX_DIMENSION", "99999")
    assert runtime._detector_max_dimension() == 1400


def test_detector_keeps_small_source_at_native_local_resolution(monkeypatch):
    monkeypatch.setenv("EXAM_PREP_VISUAL_DETECTOR_MAX_DIMENSION", "1000")
    image = Image.new("RGB", (640, 480), "white")
    raw_page = {
        "dimensions": {"width": 640, "height": 480},
        "blocks": [],
    }
    try:
        payload, detector_page = runtime._bounded_detector_page(image, raw_page)
    finally:
        image.close()
    with Image.open(BytesIO(payload)) as rendered:
        assert rendered.size == (640, 480)
    assert detector_page["dimensions"] == {"width": 640, "height": 480}
