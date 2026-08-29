"""Provider-free regression guard for the exam-prep progress-bar bands.

Root cause this locks down: OCR (the fast ~2-min phase) used to map page
completion onto ``20 + (completed/total)*70`` so finishing every page read as
~90% while the ~6-min Stage-5 tail had not started. The bar must instead track
wall-clock share — OCR fills only the low band, Stage-5 carries it up.

These tests exercise only the pure ``_band_progress`` mapping and the module
band constants; no pipeline, no LLM, no live provider call.
"""
from __future__ import annotations

import pytest

from apps.classes import tasks_exam_prep as t


pytestmark = pytest.mark.unit


def test_ocr_completion_lands_at_band_ceiling_not_near_done():
    # 58/58 pages read (the screenshot case) must sit at the OCR ceiling, not 90%.
    assert (
        t._band_progress(58, 58, floor=t.OCR_PROGRESS_FLOOR, ceiling=t.OCR_PROGRESS_CEILING)
        == t.OCR_PROGRESS_CEILING
    )
    assert t.OCR_PROGRESS_CEILING < 90


def test_ocr_start_sits_at_floor():
    assert (
        t._band_progress(0, 58, floor=t.OCR_PROGRESS_FLOOR, ceiling=t.OCR_PROGRESS_CEILING)
        == t.OCR_PROGRESS_FLOOR
    )


def test_stage5_completion_lands_at_band_ceiling():
    assert (
        t._band_progress(145, 145, floor=t.STAGE5_PROGRESS_FLOOR, ceiling=t.STAGE5_PROGRESS_CEILING)
        == t.STAGE5_PROGRESS_CEILING
    )


def test_stage5_carries_the_bar_above_ocr():
    # The long tail must be able to advance past where OCR left the bar.
    assert t.STAGE5_PROGRESS_FLOOR >= t.OCR_PROGRESS_CEILING
    midway = t._band_progress(
        72, 145, floor=t.STAGE5_PROGRESS_FLOOR, ceiling=t.STAGE5_PROGRESS_CEILING
    )
    assert t.STAGE5_PROGRESS_FLOOR < midway < t.STAGE5_PROGRESS_CEILING


def test_midpoint_lands_inside_band():
    mid = t._band_progress(29, 58, floor=t.OCR_PROGRESS_FLOOR, ceiling=t.OCR_PROGRESS_CEILING)
    assert t.OCR_PROGRESS_FLOOR < mid < t.OCR_PROGRESS_CEILING


def test_fraction_is_clamped_and_never_overflows_band():
    # A caller reporting completed > total (bad accounting) can never push the
    # bar past the ceiling.
    assert (
        t._band_progress(200, 58, floor=t.OCR_PROGRESS_FLOOR, ceiling=t.OCR_PROGRESS_CEILING)
        == t.OCR_PROGRESS_CEILING
    )
    # Negative completion is floored, not sent below the band.
    assert (
        t._band_progress(-5, 58, floor=t.OCR_PROGRESS_FLOOR, ceiling=t.OCR_PROGRESS_CEILING)
        == t.OCR_PROGRESS_FLOOR
    )


def test_zero_total_does_not_divide_by_zero():
    assert (
        t._band_progress(0, 0, floor=t.STAGE5_PROGRESS_FLOOR, ceiling=t.STAGE5_PROGRESS_CEILING)
        == t.STAGE5_PROGRESS_FLOOR
    )


def test_bands_are_ordered_and_leave_headroom_for_terminal_100():
    assert (
        t.OCR_PROGRESS_FLOOR
        < t.OCR_PROGRESS_CEILING
        <= t.STAGE5_PROGRESS_FLOOR
        < t.STAGE5_PROGRESS_CEILING
        < 100
    )
