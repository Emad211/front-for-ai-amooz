# Exam Prep V4 — Implementation Status Ledger

> Living execution ledger. Update this file before every V4 implementation step. Canonical roadmap: `exam-prep-v4-source-aware-split-pipeline.md`.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **PR:** #4 — Draft
- **Execution mode:** Critical Path Acceleration
- **Current roadmap span:** Phase 4 → Phase 7 vertical extraction path
- **Last completed slice:** measured two-page AvalAI OCR feasibility run and selected a bounded OCR evidence-proposal role
- **Active gate:** implement and verify the optional OCR evidence adapter with transient retry, authoritative validation, exact reuse, and deterministic fallback to the existing detector
- **Second live run/job:** `30854537419` / `91822320489`
- **Artifact:** `8871965000` — aggregate-only, one-day retention
- **Second-run external requests:** 8 attempted
- **Second-run result:** 6 passed, 2 transport failures
- **One-shot workflow removal from main:** `2f457da65029c6c617dc4f1ab70c542096c4a563`
- **Focused verification before adapter slice:** `30853630677`; 236 backend tests passed; frontend focused validation passed
- **Last updated:** 2026-08-04

## Progress

Progress remains based on the 77 canonical roadmap deliverables.

| Phase | Credited | Total | State |
|---|---:|---:|---|
| Phase 0 | 5 | 6 | PR ledger enforcement remains open. |
| Phase 1 | 6 | 7 | Read-only admin inspection remains deferred. |
| Phase 2 | 8 | 9 | Real private classification benchmark remains open and uncredited. |
| Phase 3 | 4 | 7 | Core Source Map works; split/group and browser validation remain open. |
| Phase 4 | 3 | 8 | Real OCR block/bbox evidence exists; optional adapter/retry/fallback and private quality gates remain open. |
| Phase 5 | 6 | 7 | Typed question path is verified; private precision/recall remains open. |
| Phase 6 | 4 | 7 | Unified answer-solution path is verified; real heading/answer-key/inline accuracy remains open. |
| Phase 7 | 6 | 7 | Deterministic matching is verified; complete consistency gate remains open. |
| Phases 8–10 | 0 | 20 | Not started. |

- **Entire V4 roadmap:** **42/77 = 54.5%**
- **Phase 4:** **3/8 = 37.5%**
- **Phase 5:** **6/7 = 85.7%**
- **Phase 6:** **4/7 = 57.1%**
- **Phase 7:** **6/7 = 85.7%**

No adapter credit is added until focused PostgreSQL and fallback/reuse evidence passes.

## AvalAI documentation rule

Before every AvalAI-dependent change or evidence interpretation:

1. update this ledger;
2. re-read the current official AvalAI OCR documentation;
3. separate documented, inferred, and measured behavior;
4. never infer retention, training, or residency guarantees;
5. update `docs/runbooks/exam-prep-v4-avalai-ocr-smoke.md`.

Official/current evidence re-read before this slice:

```text
https://docs.avalai.ir/fa/api-reference/ocr
https://docs.avalai.ir/fa/examples/processing_documents_with_mistral_ocr
https://docs.avalai.ir/fa/models/mistral-ocr-2512
https://docs.avalai.org/en/providers/mistralai
```

Current official provider documentation states that `mistral-ocr-latest` resolves to `mistral-ocr-4-0`, supports OCR4 blocks/annotations, and that the explicit versioned identifier is preferred for reproducible workflows. The adapter must therefore default to the versioned ID while retaining measured fallback behavior.

## Measured second-run evidence

Fixture:

```text
source PDF: دفترچه اول (زیست).pdf
question page: physical page 5
answer-solution page: physical page 12
requested model: mistral-ocr-latest
modes: markdown, blocks, document_annotation, bbox_annotation
```

Aggregate totals:

```text
requests attempted: 8
passed: 6
failed: 2
returned pages: 6
blocks: 134
bboxes: 138
RTL characters: 16,750
formula signals: 0
table signals: 0
total wall time: 96,360.34 ms
successful-request latency average: 5,739.00 ms
```

Question page:

- all four modes passed;
- each successful response returned one page, 21 blocks, and 22 bboxes;
- blocks mode returned page confidence `0.981177`;
- document annotation was present;
- one extracted image received bbox annotation.

Answer page:

- `document_annotation` and `bbox_annotation` passed;
- both successful responses returned one page, 25 blocks, and 25 bboxes;
- standalone `markdown` and `blocks` calls failed with `AvalAIOCRTransportError`;
- later annotation calls on the same image succeeded, so transient provider/gateway failure is plausible but not proven.

## Adapter contract for this slice

The adapter is proposal-only and must not become the production authority.

Required behavior:

1. use one `document_annotation` request as the primary page call because it returned Markdown, blocks, bboxes, and document annotation together on both measured pages;
2. request `bbox_annotation` only when diagram/figure evidence is explicitly needed;
3. retry only transient transport failures with a small bounded attempt count and deterministic backoff supplied/injected for tests;
4. never retry schema/privacy/configuration failures;
5. validate project/document/page/revision ownership before persistence;
6. convert OCR blocks only into bounded SourceBlock proposals; existing SourceBlock persistence remains authoritative;
7. reject empty, malformed, duplicate, out-of-range, or low-confidence proposals and fall back to the existing detector;
8. preserve history and downstream invalidation semantics;
9. cache accepted unchanged page evidence so a warm rerun makes zero provider calls;
10. record aggregate provider calls, attempts, fallback reasons, latency, model and request IDs privately/audit-safely;
11. never expose OCR Markdown, block content, annotations, source bytes, local paths, or raw responses through public APIs/logs;
12. keep feature-disabled/default behavior identical to the current detector.

## Required focused tests

- primary document-annotation success creates bounded deterministic proposals;
- transient transport failure retries and then succeeds;
- exhausted transient retries fall back exactly once to the existing detector;
- response/schema/privacy/configuration errors do not retry and fall back safely;
- low-confidence or empty OCR evidence falls back;
- optional bbox call occurs only for explicitly diagram-relevant pages;
- unchanged accepted evidence warm-rerun performs zero provider calls;
- changed page/revision invalidates reuse;
- project/document/page isolation is enforced;
- no private OCR content enters aggregate/public output;
- existing non-OCR detector path remains byte-stable when OCR is disabled.

## Current locked sequence

1. inspect the existing detector, block persistence, page/revision fingerprints, provider abstractions and full-pipeline benchmark;
2. implement the smallest optional adapter at the proposal boundary;
3. add focused fake-transport retry/fallback/reuse/privacy tests;
4. run full V4 PostgreSQL/frontend CI;
5. update this ledger and canonical roadmap with exact evidence;
6. only then define the bounded request ceiling for the three-private-PDF live full-pipeline benchmark.

## User action required

None for this adapter slice. Do not begin Phase 8, publication, rollout, or a live three-PDF run before the adapter gate is green.

## Exact continuation point

Read the current detector/persistence/benchmark code and implement only the optional OCR evidence adapter described above. Keep progress at 42/77 until focused evidence proves a canonical deliverable.