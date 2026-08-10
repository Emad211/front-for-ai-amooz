from __future__ import annotations

from apps.classes.services.exam_prep_mistral_full_width_layout_policy import (
    _bind_full_width_option_row,
)


def _image(x0, y0, x1, y1):
    return {
        "type": "image",
        "bbox": [x0, y0, x1, y1],
        "role": "question",
    }


def test_bottom_row_of_four_full_width_images_binds_rtl_labels():
    source = _image(0.10, 0.10, 0.30, 0.28)
    left_to_right = [
        _image(0.10, 0.55, 0.22, 0.70),
        _image(0.30, 0.55, 0.42, 0.70),
        _image(0.52, 0.55, 0.64, 0.70),
        _image(0.76, 0.55, 0.88, 0.70),
    ]
    region = {
        "kind": "question",
        "bbox": [0.0, 0.05, 1.0, 0.80],
        "visuals": [source, *left_to_right],
    }

    assert _bind_full_width_option_row(region) is True
    assert source["role"] == "question"
    assert "optionLabel" not in source
    assert [item["optionLabel"] for item in left_to_right] == ["4", "3", "2", "1"]
    assert region["visualOptionMode"] == "separate_candidates"
    assert region["fullWidthVisualOptionBinding"] == "rtl_bottom_row_exact4"


def test_arbitrary_four_image_question_is_never_force_bound():
    region = {
        "kind": "question",
        "bbox": [0.0, 0.05, 1.0, 0.80],
        "visuals": [
            _image(0.10, 0.40, 0.20, 0.55),
            _image(0.30, 0.40, 0.40, 0.55),
            _image(0.52, 0.40, 0.62, 0.55),
            _image(0.76, 0.40, 0.86, 0.55),
        ],
    }
    assert _bind_full_width_option_row(region) is False
    assert all("optionLabel" not in item for item in region["visuals"])
