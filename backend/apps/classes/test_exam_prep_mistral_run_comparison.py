from apps.classes.services.exam_prep_mistral_run_comparison import (
    compare_ocr_runs,
    compare_page_runs,
)


def _page(markdown, words, *, blocks=None, index=0):
    return {
        "index": index,
        "markdown": markdown,
        "blocks": blocks or [],
        "confidence_scores": {
            "word_confidence_scores": words,
        },
    }


def test_high_confidence_formula_change_is_not_hidden_by_confidence():
    first = _page(
        "$$x^2$$ stable",
        [],
        blocks=[{"type": "equation"}, {"type": "text"}],
    )
    second = _page(
        "$$x^t$$ stable",
        [
            {"text": "$$x^t$$", "confidence": 0.99, "start_index": 0},
            {"text": " stable", "confidence": 0.99, "start_index": 7},
        ],
        blocks=[{"type": "equation"}, {"type": "text"}],
    )

    report = compare_page_runs(first, second)

    assert "formula_instability" in report["riskCodes"]
    assert "high_confidence_instability" in report["riskCodes"]
    assert report["changedFormulaWordConfidence"]["atLeast95"] == 1


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
    assert [page["originalPageNumber"] for page in report["pages"]] == [20, 40]
    assert "alpha" not in str(report)
    assert "better" not in str(report)
