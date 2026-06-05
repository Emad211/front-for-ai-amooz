"""Deterministic, numeric tests for the LLM-only PDF extraction engine.

No network: every page goes through the (mocked) vision model, and embedded
figure images are extracted deterministically from the committed fixtures.
Produces hard, measurable assertions (page ordering, table-cell accuracy,
image-extraction counts, marker mapping, blank-skip, graceful fallback).
"""

from __future__ import annotations

import base64
import json
import os
import shutil
from types import SimpleNamespace

import pytest
from django.conf import settings as dj_settings
from django.core.files.storage import default_storage

from apps.classes.services import pdf_extraction as pe
from apps.classes.services.pdf_extraction import (
    extract_pdf_to_markdown,
    classify_text_quality,
    tables_to_markdown,
    PdfExtractionError,
)
from apps.classes.services.pdf_metrics import table_cell_accuracy, parse_markdown_table
from apps.commons.models import LLMUsageLog

FIXTURES = os.path.join(os.path.dirname(__file__), 'tests', 'fixtures', 'pdf')


def _fx(name: str) -> bytes:
    with open(os.path.join(FIXTURES, name), 'rb') as fh:
        return fh.read()


def _manifest() -> dict:
    with open(os.path.join(FIXTURES, 'manifest.json'), encoding='utf-8') as fh:
        return json.load(fh)


def _media_name(url: str) -> str:
    mu = dj_settings.MEDIA_URL or '/media/'
    return url.split(mu, 1)[1] if mu in url else url.lstrip('/')


@pytest.fixture(autouse=True)
def _cleanup_assets():
    """Remove any figure images written to storage during a test."""
    yield
    for prefix in ('class_creation/extracted', 'test_assets'):
        try:
            shutil.rmtree(default_storage.path(prefix), ignore_errors=True)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════
# Pure helpers (retained utilities)
# ═══════════════════════════════════════════════════════════════════════════


class TestQualityGate:
    def test_clean_long_text(self):
        txt = 'این یک متن فارسی سالم و طولانی با کلمات معمولی و فاصله گذاری درست است'
        assert classify_text_quality(txt, min_chars=20) is True

    def test_short_text(self):
        assert classify_text_quality('ab', min_chars=80) is False

    def test_cid_glyphs(self):
        assert classify_text_quality('(cid:32)(cid:11) text here', min_chars=2) is False

    def test_replacement_chars(self):
        assert classify_text_quality('ab����cd', min_chars=2) is False

    def test_glued_text(self):
        glued = 'اینیکمتنبسیارطولانیبدونهیچفاصلهکهچسبیدهاستوبایدباچشمخواندهشود'
        assert classify_text_quality(glued, min_chars=5) is False

    def test_force_vision_overrides(self):
        assert classify_text_quality('clean long sentence here ok', min_chars=2, force_vision=True) is False


class TestTablesToMarkdown:
    def test_basic_gfm(self):
        md = tables_to_markdown([[['A', 'B'], ['1', '2']]])
        assert md.splitlines()[0] == '| A | B |'
        assert md.splitlines()[1] == '| --- | --- |'
        assert md.splitlines()[2] == '| 1 | 2 |'

    def test_escapes_pipes_and_none(self):
        md = tables_to_markdown([[['a|b', None]]])
        assert 'a\\|b' in md


class TestParseMarkdownTable:
    def test_roundtrip_cells(self):
        table = [['Name', 'Score'], ['Ali', '20']]
        md = tables_to_markdown([table])
        parsed = parse_markdown_table(md)
        assert table_cell_accuracy(table, parsed) == 1.0


# ═══════════════════════════════════════════════════════════════════════════
# LLM-only extraction (mocked vision model — no network)
# ═══════════════════════════════════════════════════════════════════════════


def _mock_vision(monkeypatch, render):
    """Patch generate_text; ``render(detail) -> str`` builds each page's output."""
    calls = []

    def fake_generate_text(*, model, messages, timeout, feature, detail=None, **kw):
        calls.append({'model': model, 'feature': feature, 'detail': detail, 'messages': messages})
        return SimpleNamespace(text=render(detail), provider='gapgpt', model=model)

    monkeypatch.setattr(pe, 'generate_text', fake_generate_text)
    return calls


class TestLlmOnlyExtraction:
    def test_every_page_via_vision_in_order(self, monkeypatch):
        calls = _mock_vision(monkeypatch, lambda detail: f'محتوای {detail}')
        md, provider, model, pages = extract_pdf_to_markdown(data=_fx('twopage.pdf'))
        assert pages == 2
        assert provider == 'gapgpt'  # proves the vision path ran
        assert len(calls) == 2
        # feature tag drives per-task cost tracking
        assert calls[0]['feature'] == LLMUsageLog.Feature.PDF_EXTRACTION
        # page order preserved
        assert md.index('pdf page 1') < md.index('pdf page 2')

    def test_correct_multimodal_payload(self, monkeypatch):
        calls = _mock_vision(monkeypatch, lambda detail: '# متن')
        extract_pdf_to_markdown(data=_fx('english.pdf'))
        # Standard OpenAI multimodal shape: a content list with text + image_url.
        content = calls[0]['messages'][0]['content']
        assert isinstance(content, list)
        text_parts = [p for p in content if p.get('type') == 'text']
        img_parts = [p for p in content if p.get('type') == 'image_url']
        assert text_parts and img_parts
        url = img_parts[0]['image_url']['url']
        assert url.startswith('data:image/png;base64,')
        assert base64.b64decode(url.split(',', 1)[1])[:8] == b'\x89PNG\r\n\x1a\n'

    def test_table_fidelity_passthrough(self, monkeypatch):
        gt = _manifest()['table.pdf']['table']
        gfm = tables_to_markdown([gt])
        _mock_vision(monkeypatch, lambda detail: gfm)
        md, *_ = extract_pdf_to_markdown(data=_fx('table.pdf'))
        parsed = parse_markdown_table(md)
        parsed = [r for r in parsed if len(r) == len(gt[0])]
        assert table_cell_accuracy(gt, parsed) == 1.0

    def test_images_extracted_saved_and_referenced(self, monkeypatch):
        _mock_vision(
            monkeypatch,
            lambda detail: 'مقدمه\n\n[[IMAGE_1: شکل الف]]\n\n[[IMAGE_2: شکل ب]]',
        )
        md, *_ = extract_pdf_to_markdown(data=_fx('images.pdf'), asset_prefix='test_assets/imgs')
        # exactly two figures referenced (the tiny decorative icon is filtered out)
        assert md.count('![') == 2
        assert 'شکل الف' in md and 'شکل ب' in md
        # markers fully resolved
        assert '[[IMAGE' not in md
        # the real bitmaps were saved to storage under the asset prefix
        names = [_media_name(u) for u in _img_urls(md)]
        assert len(names) == 2
        for n in names:
            assert n.startswith('test_assets/imgs/')
            assert default_storage.exists(n)

    def test_marker_fewer_than_images_appends_leftovers(self, monkeypatch):
        _mock_vision(monkeypatch, lambda detail: 'متن\n\n[[IMAGE_1: تنها]]')
        md, *_ = extract_pdf_to_markdown(data=_fx('images.pdf'), asset_prefix='test_assets/few')
        assert md.count('![') == 2  # second image appended so nothing is lost
        assert '[[IMAGE' not in md

    def test_marker_more_than_images_drops_dangling(self, monkeypatch):
        _mock_vision(
            monkeypatch,
            lambda detail: '[[IMAGE_1: a]]\n[[IMAGE_2: b]]\n[[IMAGE_3: c]]',
        )
        md, *_ = extract_pdf_to_markdown(data=_fx('images.pdf'), asset_prefix='test_assets/many')
        assert md.count('![') == 2  # only two real images exist
        assert '[[IMAGE' not in md  # extra marker dropped, none left dangling

    def test_blank_page_skipped_no_llm_call(self, monkeypatch):
        calls = _mock_vision(monkeypatch, lambda detail: 'should not be called')
        # A single fully-blank page yields no content → guarded error, and the
        # model is never invoked (the page was skipped).
        with pytest.raises(PdfExtractionError):
            extract_pdf_to_markdown(data=_fx('blank.pdf'))
        assert len(calls) == 0

    def test_vision_failure_falls_back_and_never_drops_page(self, monkeypatch):
        def boom(**kw):
            raise RuntimeError('model down')

        monkeypatch.setattr(pe, 'generate_text', boom)
        md, provider, model, pages = extract_pdf_to_markdown(data=_fx('scanned.pdf'))
        assert pages == 1
        assert 'هشدار' in md  # graceful degradation marker


def _img_urls(md: str):
    import re
    return [m.group(1) for m in re.finditer(r'!\[[^\]]*\]\(([^)]+)\)', md)]


# ═══════════════════════════════════════════════════════════════════════════
# Robustness
# ═══════════════════════════════════════════════════════════════════════════


class TestRobustness:
    def test_non_pdf_rejected(self):
        with pytest.raises(PdfExtractionError):
            extract_pdf_to_markdown(data=b'this is definitely not a pdf')

    def test_encrypted_pdf_rejected(self):
        with pytest.raises(PdfExtractionError):
            extract_pdf_to_markdown(data=_fx('encrypted.pdf'))

    def test_page_cap_enforced(self, settings):
        settings.PDF_MAX_PAGES = 1
        with pytest.raises(PdfExtractionError):
            extract_pdf_to_markdown(data=_fx('twopage.pdf'))

    def test_empty_bytes_rejected(self):
        with pytest.raises(PdfExtractionError):
            extract_pdf_to_markdown(data=b'')
