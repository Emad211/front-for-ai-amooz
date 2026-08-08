# Exam Prep — Mistral OCR layout probe

Branch: `experiment/mistral-ocr-layout-probe`

This branch is diagnostic only. It does not change the production Exam Prep pipeline.

## Goal

Determine how to use AvalAI Mistral OCR 4 as the document-reading/layout layer for the
simple Exam Prep pipeline while keeping page roles, Persian reading order, question and
solution regions, visual attachment, crop construction, integrity checks, and review
routing deterministic and local whenever possible.

The representative exam has 55 physical PDF pages. The original layout sample used:

`4,10,13,17,20,31,39,40`

## Provider contract used by this branch

- pinned model: `mistral-ocr-4-0`;
- `include_blocks=true`;
- `confidence_scores_granularity=word` for confidence diagnostics;
- extracted headers and footers;
- HTML table output;
- no image base64 unless explicitly requested for diagnostics;
- no document annotation;
- no bbox annotation;
- no automatic provider retry;
- no production write.

Annotations remain excluded from the base architecture. OCR geometry, rendered source
pages, deterministic reconciliation, and later targeted verification are the evidence
layers.

## Provider transport limit discovered during full-document testing

A single 55-page AvalAI OCR request returned HTTP 400. The current Microsoft Foundry
catalog documents the Azure `mistral-ocr-4-0` route as accepting at most 30 PDF pages
and 30 MB per input. AvalAI publishes its Mistral OCR provider route as Azure.

Therefore `one request for every physical page` is not a valid provider-independent
architecture requirement. The replacement contract is:

```text
physically split the PDF locally only for transport
-> <= 30 pages per current AvalAI/Azure request
-> also enforce a conservative decoded-PDF byte cap
-> use the minimum number of requests
-> normalize returned pages back to immutable physical page numbers
```

For this 55-page PDF the minimum plan is 30 + 25 pages = two OCR requests, unless the
byte cap requires a smaller split. Chunk boundaries are not semantic boundaries;
question/solution continuation state is rebuilt across physical pages after OCR.

The experimental command implementing this contract is:

```powershell
python manage.py probe_exam_prep_mistral_chunked_document `
  --pdf "C:\absolute\path\exam.pdf" `
  --output-dir "$env:TEMP\ai-amooz-mistral-chunked-document" `
  --allow-private-transmission
```

If any chunk fails, the command now creates a failure ZIP containing the exact raw
provider body and safe response headers before raising the error.

## Original layout probe

```powershell
python manage.py probe_exam_prep_mistral_layout `
  --pdf "C:\absolute\path\exam.pdf" `
  --pages "4,10,13,17,20,31,39,40" `
  --output-dir "$env:TEMP\ai-amooz-mistral-layout-probe" `
  --allow-private-transmission
```

This established that OCR 4 returns useful paragraph-level geometry, but also revealed:

- Persian two-column provider order can be left-column-first rather than logical RTL;
- separate option images may be separate image blocks or one grouped image block;
- visual cells may live only inside a table block;
- meaningful line art can be absent from OCR visual blocks;
- compact solution numbers can lose a leading digit;
- block labels can vary between runs even when content and geometry remain stable.

## Local bundle analyzer — zero provider calls

```powershell
python manage.py analyze_exam_prep_mistral_layout_bundle `
  --bundle "C:\absolute\path\probe.zip"
```

It performs:

1. OCR block/bbox normalization;
2. local page-role classification;
3. Persian RTL two-column geometry detection and right-column-first ordering;
4. question/solution heading parsing;
5. conservative sequential recovery for compact truncated headings;
6. geometric question/solution region construction;
7. image/table/caption visual classification;
8. table visual-cell completeness checks;
9. rendered-page residual-graphics detection after masking OCR blocks;
10. association of uncovered graphics with its containing question/solution region.

## Word-confidence exact-repeat result

Two requests over physical pages 20, 39, and 40 used exactly the same model, payload,
and selected mini-PDF SHA. Provider-reported cost was `0.0030000000` unit per run.

Content-free comparison:

```text
page 20 markdown similarity = 1.000000
page 39 markdown similarity = 0.993647
page 40 markdown similarity = 0.930687
high-confidence changed words = 65
formula-instability pages = 1
```

On page 40, 97 changed words were inside formula regions; 59 of them had confidence
>= 0.95. Therefore confidence is a useful feature but cannot be interpreted as truth.

At the same time bbox geometry was extremely stable:

```text
page 20 block mean IoU = 0.997306 ; image mean IoU = 1.000000
page 39 block mean IoU = 0.999907 ; image mean IoU = 0.997416
page 40 block mean IoU = 1.000000 ; image mean IoU = 1.000000
```

This supports a key architectural distinction:

```text
OCR geometry/layout evidence: strong source signal
OCR exact text/formula transcription: fallible source candidate
OCR confidence: risk feature, not acceptance gate
OCR block type: feature, not semantic truth
```

The comparator now measures markdown, formula, high-confidence text, block-label, block
bbox, and image bbox stability separately:

```powershell
python manage.py compare_exam_prep_mistral_ocr_runs `
  --first "C:\path\run-a.zip" `
  --second "C:\path\run-b.zip" `
  --output "C:\path\comparison.json"
```

## Evidence-backed architecture

```text
1.  Render PDF locally once

2.  Build provider transport chunks locally
    - current AvalAI/Azure cap: <=30 physical pages/request
    - bounded decoded mini-PDF bytes
    - minimum number of requests

3.  OCR each chunk with Mistral OCR 4
    - include_blocks
    - word confidence
    - no annotations
    - normalize every page to original physical page number

4.  Normalize OCR blocks
    + correct Persian RTL/multi-column reading order locally

5.  Classify page/block roles locally
    - block type is only one feature

6.  Parse booklet ranges and question/solution headings
    + monotonic numbering constraints
    + conservative heading recovery

7.  Build column-aware geometric question/solution regions
    - continuation state crosses OCR chunk boundaries

8.  Reconcile OCR coverage against rendered-page graphics locally

9.  Classify visual evidence
    question / option / solution / table / decorative

10. Smart Union Crop locally
    OCR geometry + captions + table bounds + uncovered graphics

11. Local ambiguity/risk scoring
    - word-confidence distribution
    - numbering/sequence anomalies
    - formula density and syntax anomalies
    - OCR run disagreement when available
    - uncovered graphics
    - table/visual completeness

12. Targeted visual verifier only for unresolved regions

13. Integrity audit

14. Teacher review and publication
```

## Benchmark before production integration

Run the complete 55-page document twice through the bounded chunked diagnostic. This is
an experiment, not a permanent dual-OCR production decision.

For each run:

1. expect two provider requests if the byte cap permits 30 + 25 pages;
2. run the local layout analyzer;
3. confirm physical page mapping across the chunk boundary;
4. inspect residual graphics, tables, heading recovery, and RTL order.

Then compare both complete runs to quantify:

- stable vs unstable OCR text by physical page;
- formula-instability pages;
- block-label instability;
- block/image geometry stability;
- disagreement localized to question/solution regions;
- the number of regions that would actually need a paid verifier.

Only after this benchmark should we decide between:

- one OCR pass + targeted verifier;
- one OCR pass + selective OCR repeat for high-risk pages + targeted verifier;
- or another bounded consensus strategy.

Do not make a second full OCR pass a permanent production requirement without evidence
that it materially reduces verifier load or catches otherwise invisible defects.
