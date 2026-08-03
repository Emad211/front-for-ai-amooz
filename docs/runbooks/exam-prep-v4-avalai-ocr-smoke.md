# Runbook — Exam Prep V4 AvalAI Mistral OCR Smoke

- **Status:** bounded live feasibility evidence recorded
- **Branch:** `feat/exam-prep-v4-source-aware`
- **Owner:** Classes / Exam Prep V4
- **Reviewed:** 2026-08-04
- **Production routing:** unchanged
- **Endpoint:** `POST https://api.avalai.ir/v1/ocr`
- **Roadmap ledger:** `docs/features/exam-prep-v4-status.md`

## Official documentation reviewed

AvalAI documentation is re-read before every AvalAI-dependent decision:

```text
https://docs.avalai.ir/fa/api-reference/ocr
https://docs.avalai.ir/fa/examples/processing_documents_with_mistral_ocr
https://docs.avalai.ir/fa/models/mistral-ocr-2512
```

The documentation establishes the AvalAI endpoint, authentication, document/image data-URL input, page selection, Markdown/table output, document annotation, and bbox annotation. It does not establish endpoint-specific no-retention, no-training, or residency guarantees; none are inferred.

## Test contract

Private fixture:

```text
source: دفترچه اول (زیست).pdf
question page: physical page 5
answer-solution page: physical page 12
```

The runner rendered both pages locally and sent only the bounded PNG images. The complete PDF was not transmitted.

Modes:

```text
markdown
blocks
document_annotation
bbox_annotation
```

Two images × four modes = eight requests.

Bounds:

```text
max input bytes per page:       12 MiB
max response bytes per request: 24 MiB
max Markdown chars per page:    500,000
max annotation chars:           500,000
request timeout:                180 seconds
include_image_base64:           false
```

## First live run

```text
run: 30852221763
job: 91814702919
requested model: mistral-ocr-4-0
requests attempted: 8
acceptance: false
```

The old workflow lost the per-mode failed report because artifact upload was skipped after the command returned nonzero. A later PR-comment attempt also failed with GitHub 403. No quality conclusion was recorded from the first run.

## Evidence-preservation patch

```text
feature workflow commit: 32913cff94bc58493f09c9abe9f7204985fbabb0
static-test commit: 137518464ec3d2ee60a6051b07432cf6b8832f57
operational workflow commit: 5947a090c927243a1a7402b38cb59539af6a3972
focused CI: 30853630677
```

Verification:

```text
System check identified no issues (0 silenced).
No changes detected in app 'classes'.
236 passed, 47 warnings in 24.09s
Focused TypeScript check: passed
Source-map state tests: passed
```

The patched workflow preserved aggregate evidence on pass or fail, uploaded it for one day, then enforced acceptance.

## Second live run — measured evidence

```text
run: 30854537419
job: 91822320489
artifact: 8871965000
requested model: mistral-ocr-latest
requests attempted: 8
passed: 6
failed: 2
acceptance: false
```

Aggregate totals:

```text
returned pages: 6
blocks: 134
bboxes: 138
RTL characters: 16,750
formula signals: 0
table signals: 0
total wall time: 96,360.34 ms
successful-request latency average: 5,739.00 ms
```

### Question page

All four modes passed.

Each response returned:

```text
pages: 1
blocks: 21
bboxes: 22
RTL characters: 2,299
```

Observed block types:

```text
header: 3
text: 9
list: 7
image: 1
footer: 1
```

Additional evidence:

- blocks-mode page confidence: `0.981177`;
- document annotation was present;
- one image bbox annotation was present;
- no content-free parser issue codes were recorded.

### Answer page

Passed:

```text
document_annotation
bbox_annotation
```

Both successful responses returned:

```text
pages: 1
blocks: 25
bboxes: 25
RTL characters: 3,777
```

Observed block types:

```text
title: 7
header: 4
text: 13
footer: 1
```

Additional evidence:

- document annotation was present;
- no extracted images were returned;
- no content-free parser issue codes were recorded.

Failed:

```text
markdown → AvalAIOCRTransportError
blocks   → AvalAIOCRTransportError
```

The workflow did not retain the HTTP status or provider error body by design. Later annotation calls on the same answer image succeeded, so a transient gateway/provider failure is a plausible inference only.

## Interpretation

### Supported by measurement

- Persian/Arabic-script content is returned at substantial volume.
- OCR responses can provide typed block labels and bboxes.
- document annotation can coexist with Markdown and block evidence in one request.
- bbox annotation can classify an extracted figure on the question page.
- a successful page request completes in roughly 5.4–7.0 seconds in this sample.

### Not proven

- exact transcription accuracy;
- correct RTL reading order;
- printed-number recall;
- formula preservation;
- table preservation;
- multi-column ownership;
- continuation boundaries;
- immutable resolved model behind the alias;
- authoritative cost;
- reliable single-attempt transport.

Zero formula/table signals cannot distinguish “structure absent” from “signal detector missed it.”

## Architecture decision

OCR4 is **accepted as an optional evidence-proposal source**, not as the authoritative production extractor.

Recommended bounded path:

```text
confirmed Source Map
→ document_annotation OCR call
→ Markdown + blocks + bboxes + page-role proposal
→ deterministic SourceBlock proposal builder
→ existing validators, revision, provenance, and persistence
→ optional bbox_annotation only for figure-bearing pages
→ vision fallback for failed, low-confidence, formula-heavy, ambiguous, or layout-sensitive evidence
```

Rationale:

- `document_annotation` succeeded on both pages while also returning block/bbox evidence;
- a separate four-call-per-page strategy is unnecessary for the production candidate;
- two transport failures show that retry/fallback is mandatory;
- current server-authoritative contracts remain necessary.

## Required implementation before full private benchmark

1. add a provider adapter that maps OCR blocks to bounded SourceBlock proposals;
2. use `document_annotation` as the primary OCR request;
3. invoke `bbox_annotation` only when extracted-image evidence is needed;
4. classify HTTP 408/429/5xx and network failures as retryable without exposing provider bodies;
5. use bounded exponential backoff and a strict request ceiling;
6. cache accepted unchanged page evidence for zero-call warm reuse;
7. fall back to the current vision detector when OCR evidence is unavailable or insufficient;
8. preserve all current project/document/page authority and downstream invalidation guarantees;
9. run the full three-PDF benchmark with aggregate precision, recall, latency, call, and warm-reuse metrics.

## Operational cleanup

The one-shot workflow was removed from `main` after the aggregate artifact was secured:

```text
2f457da65029c6c617dc4f1ab70c542096c4a563
```

No recurring live smoke workflow remains on the default branch.

## Roadmap credit

No canonical item is credited by this two-page aggregate smoke. Phase 4 private-fixture acceptance remains open because text quality, formulas, tables, RTL order, multi-column ownership, and continuation were not fully measured.