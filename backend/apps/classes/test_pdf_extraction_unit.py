"""Deterministic, numeric tests for the hybrid PDF extraction engine.

No network: the TEXT path is fully deterministic (committed digital fixtures
with known ground truth) and the VISION path is exercised with a mocked model.
Produces hard, measurable accuracy numbers (CER / WER / table-cell accuracy).
"""

from __future__ import annotations

import base64
import json
import os
from types import SimpleNamespace

import pytest

from apps.classes.services import pdf_extraction as pe
from apps.classes.services.pdf_extraction import (
    extract_pdf_to_markdown,
    classify_text_quality,
    tables_to_markdown,
    PdfExtractionError,
)
from apps.classes.services.pdf_metrics import cer, wer, table_cell_accuracy, normalize_persian
from apps.commons.models import LLMUsageLog

FIXTURES = os.path.join(os.path.dirname(__file__), 'tests', 'fixtures', 'pdf')


def _fx(name: str) -> bytes:
    with open(os.path.join(FIXTURES, name), 'rb') as fh:
        return fh.read()


def _manifest() -> dict:
    with open(os.path.join(FIXTURES, 'manifest.json'), encoding='utf-8') as fh:
        return json.load(fh)


def _strip_page_headings(md: str) -> str:
    return '\n'.join(l for l in md.splitlines() if not l.strip().startswith('## صفحه'))


def _parse_md_table(md: str) -> list[list[str]]:
    rows = []
    for line in md.splitlines():
        s = line.strip()
        if not s.startswith('|'):
            continue
        cells = [c.strip() for c in s.strip('|').split('|')]
        if all(set(c) <= set('-') for c in cells):  # separator row
            continue
        rows.append(cells)
    return rows


# ═══════════════════════════════════════════════════════════════════════════
# TEXT path — deterministic accuracy on digital fixtures
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def low_text_gate(settings):
    """Short fixture pages still take the text path (real docs have more text)."""
    settings.PDF_TEXT_LAYER_MIN_CHARS = 5
    return settings


class TestTextPathAccuracy:
    def test_english_exact(self, low_text_gate):
        md, provider, model, pages = extract_pdf_to_markdown(data=_fx('english.pdf'))
        gt = _manifest()['english.pdf']['text']
        assert provider == 'local'  # proves NO vision/network happened
        assert pages == 1
        assert cer(gt, md) <= 0.02
        assert wer(gt, md) <= 0.02

    def test_persian_exact(self, low_text_gate):
        md, provider, model, pages = extract_pdf_to_markdown(data=_fx('persian.pdf'))
        gt = _manifest()['persian.pdf']['text']
        assert provider == 'local'
        assert pages == 1
        # Persian digital text layer recovered in logical order.
        assert cer(gt, md) <= 0.02
        assert normalize_persian(gt) in normalize_persian(md)

    def test_twopage_order_and_count(self, low_text_gate):
        md, provider, model, pages = extract_pdf_to_markdown(data=_fx('twopage.pdf'))
        meta = _manifest()['twopage.pdf']
        assert pages == 2
        body = _strip_page_headings(md)
        assert cer(meta['text'], body) <= 0.05
        # reading order preserved (page 1 appears before page 2)
        p1, p2 = meta['page_texts']
        assert md.index(p1) < md.index(p2)

    def test_table_cells_exact(self, low_text_gate):
        md, provider, model, pages = extract_pdf_to_markdown(data=_fx('table.pdf'))
        gt_table = _manifest()['table.pdf']['table']
        parsed = _parse_md_table(md)
        # Keep only the data grid (drop any stray header text rows).
        parsed = [r for r in parsed if len(r) == len(gt_table[0])]
        assert table_cell_accuracy(gt_table, parsed) == 1.0


# ═══════════════════════════════════════════════════════════════════════════
# Quality gate routing (pure)
# ═══════════════════════════════════════════════════════════════════════════


class TestQualityGate:
    def test_clean_long_text_uses_text_path(self):
        txt = 'این یک متن فارسی سالم و طولانی با کلمات معمولی و فاصله گذاری درست است'
        assert classify_text_quality(txt, min_chars=20) is True

    def test_short_text_routes_to_vision(self):
        assert classify_text_quality('ab', min_chars=80) is False

    def test_cid_glyphs_route_to_vision(self):
        assert classify_text_quality('(cid:32)(cid:11) text here', min_chars=2) is False

    def test_replacement_chars_route_to_vision(self):
        assert classify_text_quality('ab����cd', min_chars=2) is False

    def test_glued_text_routes_to_vision(self):
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


# ═══════════════════════════════════════════════════════════════════════════
# VISION path — engine behavior with a mocked model (no network)
# ═══════════════════════════════════════════════════════════════════════════


class TestVisionPath:
    def test_scanned_routes_to_vision_with_correct_payload(self, monkeypatch):
        calls = []

        def fake_generate_text(*, model, messages, timeout, feature, **kw):
            calls.append({'model': model, 'messages': messages, 'feature': feature})
            return SimpleNamespace(text='# متن استخراج‌شده با مدل', provider='gapgpt', model=model)

        monkeypatch.setattr(pe, 'generate_text', fake_generate_text)

        md, provider, model, pages = extract_pdf_to_markdown(data=_fx('scanned.pdf'))

        assert pages == 1
        assert provider == 'gapgpt'  # came from the (mocked) vision model
        assert 'متن استخراج‌شده' in md
        assert len(calls) == 1
        # feature tag drives per-task cost tracking
        assert calls[0]['feature'] == LLMUsageLog.Feature.PDF_EXTRACTION
        # correct multimodal attachment format (PNG, base64-decodable)
        att = calls[0]['messages'][0]['attachments'][0]
        assert att['type'] == 'input_media'
        assert att['mime_type'] == 'image/png'
        assert base64.b64decode(att['data_base64'])[:8] == b'\x89PNG\r\n\x1a\n'

    def test_vision_failure_falls_back_and_never_drops_page(self, monkeypatch):
        def boom(**kw):
            raise RuntimeError('model down')

        monkeypatch.setattr(pe, 'generate_text', boom)
        # Should NOT raise — graceful degradation with a warning marker.
        md, provider, model, pages = extract_pdf_to_markdown(data=_fx('scanned.pdf'))
        assert pages == 1
        assert 'هشدار' in md


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
