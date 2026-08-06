# Exam Prep — Mistral OCR layout probe

Branch: `experiment/mistral-ocr-layout-probe`

This branch is diagnostic only. It does not change the production Exam Prep pipeline.

## Goal

Use exactly one AvalAI Mistral OCR 4 request to inspect whether `include_blocks` returns useful reading-order blocks and bounding boxes for representative pages containing:

- embedded diagrams,
- vector charts,
- image-based answer options,
- chemistry structures,
- two-column worked solutions,
- mixed text/equation/figure regions.

The default physical PDF pages are:

`4,10,13,17,20,31,39,40`

Page numbers are one-based and refer to the original PDF.

## Privacy and cost contract

- The command first creates a selected-page mini-PDF locally.
- Only those selected pages are transmitted.
- Exactly one provider request is made.
- There is no retry, annotation request, Vision fallback, or production write.
- The API key and PDF path are never written to the output bundle.
- The output bundle is private and must not be committed.

## Command

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

## Bundle contents

- `manifest.json`: request count, page mapping, block/bbox counts, acceptance result.
- `response.raw.json`: unmodified private provider response.
- `request.safe.json`: request metadata with document data redacted.
- `page-XXX.original.png`: local page render.
- `page-XXX.overlay.png`: OCR block and image bounding boxes over the page.
- `page-XXX.records.json`: normalized and raw block/image records.
- `page-XXX.md`: page Markdown returned by OCR.
- sibling ZIP archive: the artifact to send back for architecture review.

## Acceptance

The probe is useful when:

1. one request returns all eight selected pages;
2. `blocks` are present;
3. at least some blocks have bounding boxes;
4. overlays align with the original page;
5. vector diagrams and option figures are represented either as visual blocks, image records, or coherent combinations of text/equation blocks.

A failed acceptance still produces the raw bundle. Do not rerun automatically; inspect the exact failure first.
