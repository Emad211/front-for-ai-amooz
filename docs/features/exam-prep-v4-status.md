# Exam Prep V4 — Implementation Status Ledger

> Living execution ledger. Update this file before every V4 implementation step. Canonical roadmap: `exam-prep-v4-source-aware-split-pipeline.md`.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **PR:** #4 — Draft
- **Execution mode:** Critical Path Acceleration
- **Current roadmap span:** Phase 4 → Phase 7 vertical extraction path
- **Last completed slice:** measured two-page AvalAI OCR feasibility run and selected a bounded OCR evidence-proposal role
- **Active gate:** implement an optional OCR evidence adapter with transient retry and deterministic fallback, then run the three private PDFs through the full V4 pipeline
- **Second live run/job:** `30854537419` / `91822320489`
- **Artifact:** `8871965000` — aggregate-only, one-day retention
- **Second-run external requests:** 8 attempted
- **Second-run result:** 6 passed, 2 transport failures
- **One-shot workflow removal from main:** `2f457da65029c6c617dc4f1ab70c542096c4a563`
- **Focused verification before live run:** `30853630677`; 236 backend tests passed; frontend focused validation passed
- **Last updated:** 2026-08-04

## Progress

Progress remains based on the 77 canonical roadmap deliverables.

| Phase | Credited | Total | State |
|---|---:|---:|---|
| Phase 0 | 5 | 6 | PR ledger enforcement remains open. |
| Phase 1 | 6 | 7 | Read-only admin inspection remains deferred. |
| Phase 2 | 8 | 9 | Real private classification benchmark remains open and uncredited. |
| Phase 3 | 4 | 7 | Core Source Map works; split/group and browser validation remain open. |
| Phase 4 | 3 | 8 | Real OCR block/bbox evidence now exists, but private layout/formula/continuation acceptance remains incomplete. |
| Phase 5 | 6 | 7 | Typed question path is verified; private precision/recall remains open. |
| Phase 6 | 4 | 7 | Unified answer-solution path is verified; real heading/answer-key/inline accuracy remains open. |
| Phase 7 | 6 | 7 | Deterministic matching is verified; complete consistency gate remains open. |
| Phases 8–10 | 0 | 20 | Not started. |

- **Entire V4 roadmap:** **42/77 = 54.5%**
- **Phase 4:** **3/8 = 37.5%**
- **Phase 5:** **6/7 = 85.7%**
- **Phase 6:** **4/7 = 57.1%**
- **Phase 7:** **6/7 = 85.7%**

No new canonical deliverable is credited from this smoke alone.

## AvalAI documentation rule

Before every AvalAI-dependent change or evidence interpretation:

1. update this ledger;
2. re-read the current official AvalAI OCR documentation;
3. separate documented, inferred, and measured behavior;
4. never infer retention, training, or residency guarantees;
5. update `docs/runbooks/exam-prep-v4-avalai-ocr-smoke.md`.

Official pages re-read for this result:

```text
https://docs.avalai.ir/fa/api-reference/ocr
https://docs.avalai.ir/fa/examples/processing_documents_with_mistral_ocr
https://docs.avalai.ir/fa/models/mistral-ocr-2512
```

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
- block types were `header`, `text`, `list`, `image`, and `footer`;
- blocks mode returned page confidence `0.981177`;
- document annotation was present in `document_annotation` mode;
- one extracted image received a bbox annotation in `bbox_annotation` mode;
- Markdown contained 2,299 RTL characters.

Answer page:

- `document_annotation` and `bbox_annotation` passed;
- both successful responses returned one page, 25 blocks, and 25 bboxes;
- block types were `title`, `header`, `text`, and `footer`;
- document annotation was present in `document_annotation` mode;
- no extracted images were returned;
- Markdown contained 3,777 RTL characters;
- standalone `markdown` and `blocks` calls failed with `AvalAIOCRTransportError`.

The exact HTTP status for the two transport failures was not recorded. Because later annotation calls on the same answer image succeeded, a transient provider/gateway failure is a plausible inference, not a proven cause.

## Evidence limitations

- aggregate-only reporting does not prove transcription correctness or RTL reading order;
- zero formula/table signals may mean the selected pages lacked those structures or the current signal detector missed them;
- the response reported the alias `mistral-ocr-latest`, not a resolved immutable model identifier;
- exact authoritative cost was not retrieved;
- transport reliability was 6/8 in this small sample, so single-attempt OCR cannot be authoritative.

## Architecture decision

**OCR4 is accepted as an optional evidence-proposal candidate, not as the production authority.**

The next adapter should use:

1. `document_annotation` as the primary call because it succeeded on both pages and returned Markdown, blocks, bboxes, and document annotation together;
2. `bbox_annotation` only when figure/diagram evidence is needed;
3. bounded retry only for transient transport failures;
4. existing Source Map, SourceBlock, typed-record, revision, provenance, and matcher contracts as authoritative validators;
5. the current vision detector as fallback for failed, low-confidence, ambiguous, formula-heavy, or layout-sensitive evidence;
6. exact caching so accepted unchanged page evidence makes zero provider calls.

No production-default switch is authorized yet.

## Closed operational gate

The one-shot workflow was removed from `main` after the artifact was secured. No further manual OCR smoke workflow remains on the default branch.

## Next locked slice

Implement only the optional OCR evidence adapter and retry/fallback policy, then execute the existing full-pipeline benchmark on all three private PDFs. The benchmark must record aggregate question/answer inventory, match precision, block coverage, provider calls, latency, warm reuse, and failures. Do not begin Phase 8 or rollout.

## User action required

No user decision is required for the adapter slice. A later full three-PDF live benchmark may require a new explicit request ceiling before execution.