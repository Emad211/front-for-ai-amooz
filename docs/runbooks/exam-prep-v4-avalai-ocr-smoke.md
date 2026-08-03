# Runbook — Exam Prep V4 AvalAI OCR Evidence

- **Status:** two-page feasibility measured; optional adapter implemented and verified; three-PDF benchmark ready
- **Branch:** `feat/exam-prep-v4-source-aware`
- **Reviewed:** 2026-08-04
- **Production routing:** unchanged/default-disabled
- **Endpoint:** `POST https://api.avalai.ir/v1/ocr`
- **Reproducible model:** `mistral-ocr-4-0`
- **Ledger:** `docs/features/exam-prep-v4-status.md`

## Official documentation rule

Before every AvalAI-dependent decision, re-read:

```text
https://docs.avalai.ir/fa/api-reference/ocr
https://docs.avalai.ir/fa/examples/processing_documents_with_mistral_ocr
https://docs.avalai.ir/fa/models/mistral-ocr-2512
```

The documentation supports image/document data URLs, selective pages, OCR Markdown, blocks, document annotation and bbox annotation. It does not establish endpoint-specific retention, training or residency guarantees; none are inferred.

## Measured feasibility smoke

Fixture:

```text
دفترچه اول (زیست).pdf
question page: physical page 5
answer-solution page: physical page 12
```

Only two locally rendered PNG images were transmitted. The PDF was not sent.

### First run

```text
run: 30852221763
job: 91814702919
requests: 8
result: acceptance failed
```

The initial workflow lost the aggregate failure report. Evidence preservation was subsequently fixed and verified.

### Second run

```text
run: 30854537419
job: 91822320489
artifact: 8871965000
requested model: mistral-ocr-latest
attempted: 8
passed: 6
failed: 2
```

Aggregate evidence:

```text
returned pages: 6
blocks: 134
bboxes: 138
RTL characters: 16,750
formula signals: 0
table signals: 0
wall time: 96,360.34 ms
successful latency average: 5,739.00 ms
```

Question page: all four modes passed, 21 blocks, 22 bboxes, page confidence `0.981177`, document annotation present and one image annotation present.

Answer page: `document_annotation` and `bbox_annotation` passed with 25 blocks/25 bboxes; standalone Markdown and blocks calls failed with `AvalAIOCRTransportError`. Later calls on the same image succeeded, so transient transport failure is plausible but not proven.

The smoke supports OCR as an evidence source. It does not prove transcription accuracy, RTL order, formula/table preservation, continuation ownership or private-fixture recall.

## Implemented adapter

```text
backend/apps/classes/services/exam_prep_v4_ocr_evidence.py
backend/apps/classes/test_exam_prep_v4_ocr_evidence.py
```

Contract:

1. `document_annotation` is the primary page request because it can return Markdown, blocks, bboxes and page annotation together;
2. `bbox_annotation` is requested only when page annotation marks diagram evidence;
3. only transport failures receive bounded retry;
4. schema, response, privacy and configuration errors do not retry;
5. exhausted retry, low confidence, missing headings, unsupported roles or malformed evidence fall back once for the complete segment;
6. Persian, Arabic and Latin printed numbers are normalized deterministically;
7. OCR output creates proposals only; existing SourceBlock parser/persistence remain authoritative;
8. answer continuation is allowed only after a prior accepted answer block;
9. accepted unchanged evidence performs zero OCR and zero detector calls;
10. stats expose only counts, reason codes and model IDs.

Adapter verification:

```text
checkpoint: 62815466d9af92348705d4c68acb1e2b7400f86e
workflow: 30856089814
backend: 244 passed, 47 warnings in 24.41s
frontend focused validation: passed
```

## Full benchmark integration

The adapter is available only through the explicit private benchmark option:

```text
--ocr-evidence
--ocr-model mistral-ocr-4-0
--ocr-max-attempts 2
--ocr-bbox-for-diagrams
```

Every direct OCR HTTP request reserves one slot from the shared live-call budget before transport. The aggregate report records:

- OCR calls;
- primary successes;
- bbox calls;
- retries;
- fallback count and reason codes;
- resolved model IDs;
- shared request-ceiling consumption.

It never records OCR text, annotations, data URLs, paths, bytes, credentials or raw responses.

## Current three-PDF live configuration

```text
structured model: gemini-2.5-flash
OCR model: mistral-ocr-4-0
OCR attempts: 2
bbox escalation: diagram pages only
OCR-eligible pages: 55
OCR worst-case external slots: 220
shared hard ceiling: 484
```

The OCR bound assumes two attempts for both primary and possible bbox calls on every eligible page. Actual OCR calls should be lower when first attempts pass and pages have no diagrams.

## Acceptance and decision after full benchmark

The aggregate run must provide:

- OCR call/retry/fallback totals;
- structural classification and Source Map accuracy;
- block, question and answer counts;
- question and answer recall against the private manifest;
- automatic match precision and cross-project isolation;
- cold latency and warm zero-call reuse;
- provider usage and exact transaction-cost evidence where available.

After private evidence review, OCR may be accepted as:

1. OCR-first proposal source with structured fallback;
2. transcription-only evidence;
3. diagram-only utility; or
4. rejected for the production path.

No production routing or rollout decision is implied by adapter implementation.

## Current workflow

```text
.github/workflows/exam-prep-v4-full-live-benchmark.yml
main commit: 5903d08fc3f58d8625f4ddf80fdccd92949b1ac6
```

It is manual-only, non-recurring, bounded to 484 external calls, retains only aggregate evidence for one day and must be removed after terminal evidence is recovered.