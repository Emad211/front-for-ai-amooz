# Exam Prep — Mistral OCR layout probe

Branch: `experiment/mistral-ocr-layout-probe`

This branch is diagnostic only. It does not change the production Exam Prep pipeline.

## Goal

Use bounded AvalAI Mistral OCR 4 requests to determine whether OCR 4 can become the
single document-reading pass for the simple Exam Prep pipeline while all page roles,
question/solution regions, visual attachment, crop construction, completeness checks,
and publication integrity stay deterministic and local whenever possible.

The original layout sample uses physical PDF pages:

`4,10,13,17,20,31,39,40`

Page numbers are one-based and refer to the original PDF.

## Provider contract used by this branch

- pinned model: `mistral-ocr-4-0`;
- `include_blocks=true`;
- extracted headers and footers;
- HTML table output;
- no image base64 unless explicitly requested for diagnostics;
- no document annotation;
- no bbox annotation;
- no automatic provider retry;
- no production write.

Annotations are deliberately excluded from the base architecture. The OCR blocks,
rendered PDF pages, and deterministic local checks are the source evidence. A later
question-level verifier is reserved only for unresolved ambiguity.

## Original layout probe

From `backend/`:

```powershell
python manage.py probe_exam_prep_mistral_layout `
  --pdf "C:\absolute\path\exam.pdf" `
  --pages "4,10,13,17,20,31,39,40" `
  --output-dir "$env:TEMP\ai-amooz-mistral-layout-probe" `
  --allow-private-transmission
```

Required environment variable:

```powershell
$env:AVALAI_API_KEY = "..."
```

Do not print or commit the key.

## Local bundle analyzer — zero provider calls

The new analyzer consumes the private ZIP produced above and does not contact AvalAI:

```powershell
python manage.py analyze_exam_prep_mistral_layout_bundle `
  --bundle "C:\absolute\path\ai-amooz-mistral-layout-probe.zip"
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
9. local rendered-page residual-graphics detection after masking all OCR blocks;
10. association of uncovered graphics with the containing question/solution region.

The generated `*.analysis.json` is private because it can contain OCR source text. It
must not be committed.

## Word-confidence probe

Page-level average confidence can hide individual OCR errors. The next live diagnostic
uses one request for representative chemistry and worked-solution pages and requests
word-level confidence:

```powershell
python manage.py probe_exam_prep_mistral_word_confidence `
  --pdf "C:\absolute\path\exam.pdf" `
  --pages "20,39,40" `
  --output-dir "$env:TEMP\ai-amooz-mistral-word-confidence" `
  --allow-private-transmission
```

This diagnostic still makes exactly one provider request, performs no annotation, and
has no retry. Send the generated ZIP back before any full-document rollout decision.

## Evidence-backed architecture refinement

The original architecture remains valid, with three explicit local guards added:

```text
1.  Render PDF locally
2.  One Mistral OCR 4 block request for the document
3.  Normalize OCR blocks + correct RTL multi-column reading order locally
4.  Classify page/block roles locally
5.  Parse booklet ranges and question/solution headings
6.  Build column-aware geometric question/solution regions
7.  Reconcile OCR coverage against rendered-page graphics locally
8.  Classify visual evidence: question / option / solution / table / decorative
9.  Smart Union Crop locally from OCR visuals + captions + uncovered graphics
10. Completeness + OCR confidence/anomaly checks locally
11. One targeted verifier only for unresolved ambiguous regions
12. Integrity audit
13. Teacher review and publication
```

### Why the extra guards exist

The diagnostic showed several distinct provider behaviors that one image-only rule
cannot safely represent:

- multiple visual options can be returned as separate image blocks;
- several visual options can also be grouped into one image block;
- a table can contain important visual cells without separate image records;
- a meaningful piece of line art can be absent from OCR visual blocks entirely;
- provider block order can disagree with Persian right-to-left two-column reading order;
- compact numeric solution headings can lose a leading digit while nearby geometry and
  sequence remain sufficient for conservative local recovery;
- a high page-average confidence does not prove every formula or token is trustworthy.

For those reasons OCR block geometry is strong evidence, but OCR visual coverage,
reading order, and transcribed text are not treated as unquestionable ground truth.

## Bundle contents

The original probe writes:

- `manifest.json`: request count, page mapping, block/bbox counts, acceptance result;
- `response.raw.json`: unmodified private provider response;
- `request.safe.json`: request metadata with document data redacted;
- `page-XXX.original.png`: local page render;
- `page-XXX.overlay.png`: OCR block and image bounding boxes over the page;
- `page-XXX.records.json`: normalized and raw block/image records;
- `page-XXX.md`: page Markdown returned by OCR;
- sibling ZIP archive: the private artifact for architecture review.

## Acceptance before production integration

Do not replace the production extractor merely because blocks exist. Before production
integration we require all of the following:

1. RTL multi-column ordering is deterministic on the representative solution pages;
2. local coverage reconciliation catches OCR-missed line art without noisy false positives;
3. grouped and separate visual-option layouts are distinguishable;
4. table regions preserve visual cells in the source crop;
5. word confidence is measured against real observed OCR mistakes;
6. one full representative document can be processed within the intended single-request
   budget and response-size limits;
7. only residual ambiguous regions reach a paid verifier.

A failed diagnostic still produces private evidence. Do not rerun automatically; inspect
the exact failure first.
