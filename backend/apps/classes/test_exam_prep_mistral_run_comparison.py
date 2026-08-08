from apps.classes.services.exam_prep_mistral_run_comparison import (
    compare_ocr_runs,
    compare_page_runs,
)


def _page(markdown, words, *, blocks=None, images=None, index=0):
    return {
        "index": index,
        "markdown": markdown,
        "blocks": blocks or [],
        "images": images or [],
        "confidence_scores": {
            "word_confidence_scores": words,
        },
    }


def _box(kind, x0, y0, x1, y1):
    return {
        "type": kind,
        "top_left_x": x0,
        "top_left_y": y0,
        "bottom_right_x": x1,
        "bottom_right_y": y1,
    }


def test_high_confidence_formula_change_is_not_hidden_by_confidence():
    first = _page(
        "$$x^2$$ stable",
        [],
        blocks=[_box("equation", 0, 0, 100, 20), _box("text", 0, 30, 100, 50)],
    )
    second = _page(
        "$$x^t$$ stable",
        [
            {"text": "$$x^t$$", "confidence": 0.99, "start_index": 0},
            {"text": " stable", "confidence": 0.99, "start_index": 7},
        ],
        blocks=[_box("equation", 0, 0, 100, 20), _box("text", 0, 30, 100, 50)],
    )

    report = compare_page_runs(first, second)

    assert "formula_instability" in report["riskCodes"]
    assert "high_confidence_instability" in report["riskCodes"]
    assert "block_geometry_instability" not in report["riskCodes"]
    assert report["changedFormulaWordConfidence"]["atLeast95"] == 1
    assert report["blockGeometry"]["meanIoU"] == 1.0


def test_low_confidence_changed_words_are_separated_from_stable_words():
    first = _page("wrong stable", [])
    second = _page(
        "right stable",
        [
            {"text": "right", "confidence": 0.45, "start_index": 0},
            {"text": " stable", "confidence": 0.99, "start_index": 5},
        ],
    )

    report = compare_page_runs(first, second)

    assert report["changedWordConfidence"]["below60"] == 1
    assert report["stableWordConfidence"]["atLeast95"] == 1


def test_geometry_is_measured_separately_from_block_label_instability():
    first = _page(
        "same",
        [],
        blocks=[
            _box("list", 10, 10, 100, 40),
            _box("image", 10, 50, 100, 120),
        ],
        images=[_box("image", 10, 50, 100, 120)],
    )
    second = _page(
        "same",
        [{"text": "same", "confidence": 0.99, "start_index": 0}],
        blocks=[
            _box("text", 10, 10, 100, 40),
            _box("image", 10, 50, 100, 120),
        ],
        images=[_box("image", 10, 50, 100, 120)],
    )

    report = compare_page_runs(first, second)

    assert "block_structure_instability" in report["riskCodes"]
    assert "block_geometry_instability" not in report["riskCodes"]
    assert "image_geometry_instability" not in report["riskCodes"]
    assert report["blockGeometry"]["meanIoU"] == 1.0
    assert report["imageGeometry"]["meanIoU"] == 1.0


def test_large_bbox_shift_is_reported_as_geometry_instability():
    first = _page(
        "same",
        [],
        blocks=[_box("text", 0, 0, 100, 100)],
    )
    second = _page(
        "same",
        [{"text": "same", "confidence": 0.99, "start_index": 0}],
        blocks=[_box("text", 80, 80, 180, 180)],
    )

    report = compare_page_runs(first, second)

    assert "block_geometry_instability" in report["riskCodes"]
    assert report["blockGeometry"]["below90"] == 1


def test_run_comparison_is_content_free_and_preserves_page_mapping():
    first = {
        "pages": [
            _page("alpha", [], index=0),
            _page("beta", [], index=1),
        ]
    }
    second = {
        "pages": [
            _page(
                "alpha",
                [{"text": "alpha", "confidence": 0.99, "start_index": 0}],
                index=0,
            ),
            _page(
                "better",
                [{"text": "better", "confidence": 0.70, "start_index": 0}],
                index=1,
            ),
        ]
    }

    report = compare_ocr_runs(first, second, original_pages=[20, 40])

    assert report["contentFree"] is True
    assert report["schemaVersion"] == 2
    assert [page["originalPageNumber"] for page in report["pages"]] == [20, 40]
    assert "alpha" not in str(report)
    assert "better" not in str(report)
