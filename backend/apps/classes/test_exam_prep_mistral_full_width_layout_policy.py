from __future__ import annotations

from apps.classes.services.exam_prep_mistral_full_width_layout_policy import (
    has_full_width_visual_question_bands,
    production_is_rtl_double_column,
)
from apps.classes.services.exam_prep_mistral_layout_analysis import LayoutBlock


def _block(index, kind, text, box, column):
    return LayoutBlock(
        provider_index=index,
        block_type=kind,
        content=text,
        bbox=box,
        column=column,
        raw={},
    )


def test_visual_option_band_crossing_both_halves_is_full_width_question_layout():
    blocks = [
        _block(0, "text", "۲۸۶- سؤال تصویری", (0.60, 0.08, 0.95, 0.10), "right"),
        _block(1, "image", "a", (0.08, 0.12, 0.28, 0.25), "left"),
        _block(2, "image", "b", (0.12, 0.29, 0.28, 0.39), "left"),
        _block(3, "image", "c", (0.55, 0.29, 0.68, 0.39), "right"),
        _block(4, "image", "d", (0.72, 0.29, 0.85, 0.39), "right"),
        _block(5, "text", "۲۸۷-", (0.90, 0.46, 0.95, 0.48), "right"),
        _block(6, "image", "e", (0.18, 0.50, 0.29, 0.59), "left"),
        _block(7, "image", "f", (0.33, 0.50, 0.43, 0.59), "left"),
        _block(8, "image", "g", (0.58, 0.50, 0.68, 0.59), "right"),
        _block(9, "image", "h", (0.75, 0.50, 0.86, 0.59), "right"),
    ]
    assert has_full_width_visual_question_bands(blocks) is True
    assert production_is_rtl_double_column(blocks) is False


def test_true_two_column_question_page_remains_double_column():
    blocks = [
        _block(0, "text", "۱- سؤال", (0.60, 0.10, 0.90, 0.12), "right"),
        _block(1, "text", "۲- سؤال", (0.60, 0.30, 0.90, 0.32), "right"),
        _block(2, "text", "۳- سؤال", (0.10, 0.10, 0.40, 0.12), "left"),
        _block(3, "text", "۴- سؤال", (0.10, 0.30, 0.40, 0.32), "left"),
        _block(4, "text", "متن", (0.60, 0.14, 0.90, 0.18), "right"),
        _block(5, "text", "متن", (0.60, 0.34, 0.90, 0.38), "right"),
        _block(6, "text", "متن", (0.10, 0.14, 0.40, 0.18), "left"),
        _block(7, "text", "متن", (0.10, 0.34, 0.40, 0.38), "left"),
    ]
    assert has_full_width_visual_question_bands(blocks) is False
    assert production_is_rtl_double_column(blocks) is True


def test_spanning_question_heading_is_direct_full_width_evidence():
    blocks = [
        _block(0, "text", "۲۹۰- سؤال", (0.05, 0.40, 0.92, 0.44), "span"),
        _block(1, "image", "a", (0.37, 0.50, 0.60, 0.68), "left"),
    ]
    assert has_full_width_visual_question_bands(blocks) is True
