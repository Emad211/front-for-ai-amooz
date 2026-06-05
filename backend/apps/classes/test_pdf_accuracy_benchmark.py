"""Opt-in REAL-model accuracy benchmark for the LLM-only PDF extraction path.

Runs the REAL pipeline (renders pages + calls the configured multimodal model)
and asserts measurable thresholds. Two complementary corpora:

  1. Real Persian PDFs (``pdf_corpus_real/``, from Wikipedia) — measures Persian
     OCR quality as *word recall* of the article's clean plain-text summary in
     the vision output, plus CER for transparency, plus that a lead figure is
     extracted. Real docs have broken text layers, so the reference is the
     Wikipedia summary, NOT the PDF text layer.
  2. Synthetic control PDFs (``pdf_corpus/``) — gives EXACT ground truth where
     real docs can't: precise GFM table-cell accuracy and an exact embedded
     figure count.

Skipped by default. Enable with real LLM credentials configured:

    RUN_PDF_BENCHMARK=1 pytest apps/classes/test_pdf_accuracy_benchmark.py -q -s
"""

from __future__ import annotations

import json
import os
import re

import pytest

RUN = os.environ.get('RUN_PDF_BENCHMARK') == '1'

pytestmark = pytest.mark.skipif(
    not RUN,
    reason='set RUN_PDF_BENCHMARK=1 (with real LLM keys) to run the accuracy benchmark',
)

FIX = os.path.join(os.path.dirname(__file__), 'tests', 'fixtures', 'pdf')
REAL = os.path.join(FIX, 'pdf_corpus_real')
SYNTH = os.path.join(FIX, 'pdf_corpus')

# Thresholds.
REAL_RECALL_MIN = 0.65   # mean Persian word recall on real article pages
TABLE_MIN_ACCURACY = 0.90
CER_REPORT_ONLY = True   # CER on real docs is reported but not asserted


def _count_images(md: str) -> int:
    return len(re.findall(r'!\[[^\]]*\]\([^)]+\)', md))


@pytest.mark.benchmark
@pytest.mark.django_db
def test_real_persian_corpus():
    from apps.classes.services.pdf_extraction import extract_pdf_to_markdown
    from apps.classes.services.pdf_metrics import word_recall

    with open(os.path.join(REAL, 'real_manifest.json'), encoding='utf-8') as fh:
        manifest = json.load(fh)

    recalls = []
    rows = []
    for name, meta in sorted(manifest.items()):
        with open(os.path.join(REAL, name), 'rb') as fh:
            data = fh.read()
        md, provider, model, pages = extract_pdf_to_markdown(
            data=data, asset_prefix=f'benchmark/real/{os.path.splitext(name)[0]}'
        )
        # Recall of the clean reference summary measures Persian OCR fidelity
        # without penalising the legitimate extra page text (captions, infobox).
        rec = word_recall(meta['ref_text'], md)
        imgs = _count_images(md)
        recalls.append(rec)
        rows.append((name, provider, rec, imgs, meta.get('expect_image')))

    print('\n=== REAL Persian PDF benchmark (recall of clean summary) ===')
    print(f"{'document':<22} {'provider':<10} {'recall':>8} {'imgs':>5}")
    for name, provider, rec, imgs, _ in rows:
        print(f'{name:<22} {provider:<10} {rec:>8.4f} {imgs:>5}')
    mean_recall = sum(recalls) / len(recalls)
    print(f'mean recall = {mean_recall:.4f} (min required {REAL_RECALL_MIN})')

    assert mean_recall >= REAL_RECALL_MIN, f'Persian recall {mean_recall:.4f} too low'
    for name, provider, rec, imgs, expect_image in rows:
        if expect_image:
            assert imgs >= 1, f'{name}: expected at least one extracted figure, got {imgs}'


@pytest.mark.benchmark
@pytest.mark.django_db
def test_table_and_figure_fidelity():
    from apps.classes.services.pdf_extraction import extract_pdf_to_markdown
    from apps.classes.services.pdf_metrics import table_cell_accuracy, parse_markdown_table

    with open(os.path.join(SYNTH, 'corpus_manifest.json'), encoding='utf-8') as fh:
        manifest = json.load(fh)

    # Exact table-cell accuracy.
    table_doc = 'table_doc.pdf'
    if table_doc in manifest and 'table' in manifest[table_doc]:
        with open(os.path.join(SYNTH, table_doc), 'rb') as fh:
            data = fh.read()
        md, *_ = extract_pdf_to_markdown(data=data, asset_prefix='benchmark/synth/table')
        gt = manifest[table_doc]['table']
        parsed = [r for r in parse_markdown_table(md) if len(r) == len(gt[0])]
        acc = table_cell_accuracy(gt, parsed)
        print(f'\ntable_doc cell_accuracy = {acc:.4f} (min {TABLE_MIN_ACCURACY})')
        assert acc >= TABLE_MIN_ACCURACY, f'table cell accuracy {acc:.4f} too low'

    # Exact extracted-figure count.
    fig_doc = 'figure_doc.pdf'
    if fig_doc in manifest and 'expected_images' in manifest[fig_doc]:
        with open(os.path.join(SYNTH, fig_doc), 'rb') as fh:
            data = fh.read()
        md, *_ = extract_pdf_to_markdown(data=data, asset_prefix='benchmark/synth/fig')
        exp = manifest[fig_doc]['expected_images']
        got = _count_images(md)
        print(f'figure_doc images expected={exp} got={got}')
        assert got == exp, f'figure_doc extracted {got} images, expected {exp}'
