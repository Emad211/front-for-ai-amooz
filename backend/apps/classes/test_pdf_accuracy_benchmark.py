"""Opt-in real-model accuracy benchmark for the hybrid PDF vision path.

Runs the REAL extraction pipeline (renders pages + calls the configured
multimodal model) over a small curated, image-only corpus with known ground
truth, then reports measurable CER/WER per document and asserts regression
thresholds.

Skipped by default. Enable with real LLM credentials configured:

    RUN_PDF_BENCHMARK=1 pytest apps/classes/test_pdf_accuracy_benchmark.py -q -s

Drop additional real PDFs into ``tests/fixtures/pdf/pdf_corpus/`` with a
matching ``<name>`` entry in ``corpus_manifest.json`` (``lang`` + ``text``).
"""

from __future__ import annotations

import json
import os

import pytest

RUN = os.environ.get('RUN_PDF_BENCHMARK') == '1'

pytestmark = pytest.mark.skipif(
    not RUN,
    reason='set RUN_PDF_BENCHMARK=1 (with real LLM keys) to run the vision accuracy benchmark',
)

CORPUS = os.path.join(os.path.dirname(__file__), 'tests', 'fixtures', 'pdf', 'pdf_corpus')

# Regression thresholds (mean error rate per language) for the vision path.
CER_THRESHOLDS = {'english': 0.08, 'persian': 0.20}
WER_THRESHOLDS = {'english': 0.15, 'persian': 0.35}


@pytest.mark.benchmark
def test_vision_accuracy_corpus():
    from apps.classes.services.pdf_extraction import extract_pdf_to_markdown
    from apps.classes.services.pdf_metrics import cer, wer

    manifest_path = os.path.join(CORPUS, 'corpus_manifest.json')
    with open(manifest_path, encoding='utf-8') as fh:
        manifest = json.load(fh)

    by_lang: dict[str, list[tuple[float, float]]] = {}
    rows = []
    for name, meta in sorted(manifest.items()):
        with open(os.path.join(CORPUS, name), 'rb') as fh:
            data = fh.read()
        md, provider, model, pages = extract_pdf_to_markdown(data=data)
        c = cer(meta['text'], md)
        w = wer(meta['text'], md)
        by_lang.setdefault(meta['lang'], []).append((c, w))
        rows.append((name, meta['lang'], provider, model, c, w))

    # Report
    print('\n=== PDF vision accuracy benchmark ===')
    print(f"{'document':<24} {'lang':<8} {'provider':<10} {'CER':>8} {'WER':>8}")
    for name, lang, provider, model, c, w in rows:
        print(f'{name:<24} {lang:<8} {provider:<10} {c:>8.4f} {w:>8.4f}')

    # Assert per-language mean thresholds
    for lang, pairs in by_lang.items():
        mean_cer = sum(p[0] for p in pairs) / len(pairs)
        mean_wer = sum(p[1] for p in pairs) / len(pairs)
        print(f'mean[{lang}] CER={mean_cer:.4f} WER={mean_wer:.4f}')
        assert mean_cer <= CER_THRESHOLDS.get(lang, 0.25), f'{lang} CER {mean_cer:.4f} too high'
        assert mean_wer <= WER_THRESHOLDS.get(lang, 0.45), f'{lang} WER {mean_wer:.4f} too high'
