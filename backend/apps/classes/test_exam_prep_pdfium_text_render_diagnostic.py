import pytest
from django.core.management.base import CommandError

from apps.classes.management.commands.probe_exam_prep_pdfium_text_render_diagnostic import (
    _parse_dpis,
    _text_stats,
)


def test_parse_dpis_deduplicates_and_bounds_values():
    assert _parse_dpis("200,300,200,450") == (200, 300, 450)
    with pytest.raises(CommandError):
        _parse_dpis("99")
    with pytest.raises(CommandError):
        _parse_dpis("abc")


def test_text_stats_detects_pdf_encoding_warning_characters():
    stats = _text_stats("abc\ufffd□\ue001\n")
    assert stats["charCount"] == 7
    assert stats["replacementCharacterCount"] == 1
    assert stats["visibleBoxCharacterCount"] == 1
    assert stats["privateUseCharacterCount"] == 1
    assert stats["unexpectedControlCharacterCount"] == 0
