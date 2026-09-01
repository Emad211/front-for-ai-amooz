from django.test import override_settings

from apps.classes.services import exam_prep_v4_nul_safety as nul_safety
from apps.classes.services import exam_prep_v4_pdf_source as pdf_source


class _Page:
    def __init__(self, text):
        self.text = text

    def extract_text(self):
        if isinstance(self.text, Exception):
            raise self.text
        return self.text


class _Reader:
    def __init__(self, text):
        self.pages = [_Page(text)]


def test_sanitize_postgres_text_removes_only_nul():
    value = 'الف\x00ب\nج\tد'
    assert nul_safety.sanitize_postgres_text(value) == 'الفب\nج\tد'


@override_settings(EXAM_PREP_V4_NATIVE_TEXT_STORED_CHARS=100)
def test_safe_native_text_removes_nul_before_database_persistence():
    sample, length = nul_safety.safe_native_text(_Reader('  A\x00B\x00C  '), 0)
    assert sample == 'ABC'
    assert length == 3
    assert '\x00' not in sample


@override_settings(EXAM_PREP_V4_NATIVE_TEXT_STORED_CHARS=4)
def test_safe_native_text_keeps_existing_bound_and_handles_extraction_failure():
    sample, length = nul_safety.safe_native_text(_Reader('abcdef'), 0)
    assert sample == 'abcd'
    assert length == 6

    failed_sample, failed_length = nul_safety.safe_native_text(
        _Reader(RuntimeError('broken text layer')),
        0,
    )
    assert failed_sample == ''
    assert failed_length == 0


def test_installer_replaces_pdf_source_native_text_seam():
    nul_safety.install()
    assert pdf_source._native_text is nul_safety.safe_native_text
