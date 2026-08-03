# Exam Prep V4 — Implementation Status Ledger

> Living execution ledger. Update this file before every V4 implementation step. Canonical roadmap: `exam-prep-v4-source-aware-split-pipeline.md`.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **PR:** #4 — Draft
- **Execution mode:** Critical Path Acceleration
- **Current roadmap span:** Phase 4 → Phase 7 vertical extraction path
- **Last completed slice:** optional OCR evidence adapter with deterministic numbered-heading proposals, transient retry, fail-closed fallback, diagram-only bbox escalation, privacy-safe stats, and warm zero-call reuse
- **Active gate:** wire the optional adapter into the aggregate full-pipeline benchmark, expose adapter metrics, and calculate the hard request ceiling for the three private PDFs
- **Adapter checkpoint:** `62815466d9af92348705d4c68acb1e2b7400f86e`
- **Focused workflow:** `30856089814`
- **Backend job:** `91827311913`
- **Frontend job:** `91827311993`
- **Validated PR merge ref:** `cfc5229087afb714cd050f9a426c90497edbcaad`
- **Focused result:** 244 backend tests passed; migration drift zero; frontend focused validation passed
- **Measured OCR smoke:** run `30854537419`, job `91822320489`, artifact `8871965000`; 6/8 calls passed
- **Last updated:** 2026-08-04

## Progress

Progress remains based on the 77 canonical roadmap deliverables.

| Phase | Credited | Total | State |
|---|---:|---:|---|
| Phase 0 | 5 | 6 | PR ledger enforcement remains open. |
| Phase 1 | 6 | 7 | Read-only admin inspection remains deferred. |
| Phase 2 | 8 | 9 | Real private classification benchmark remains open and uncredited. |
| Phase 3 | 4 | 7 | Core Source Map works; split/group and browser validation remain open. |
| Phase 4 | 4 | 8 | Numbered-heading detection is now implemented and focused-tested; content-area/columns, RTL reading order, page deduplication, and private layout/formula/diagram/continuation acceptance remain open. |
| Phase 5 | 6 | 7 | Typed question path is verified; private precision/recall remains open. |
| Phase 6 | 4 | 7 | Unified answer-solution path is verified; real heading/answer-key/inline accuracy remains open. |
| Phase 7 | 6 | 7 | Deterministic matching is verified; complete consistency gate remains open. |
| Phases 8–10 | 0 | 20 | Not started. |

- **Entire V4 roadmap:** **43/77 = 55.8%**
- **Phase 4:** **4/8 = 50.0%**
- **Phase 5:** **6/7 = 85.7%**
- **Phase 6:** **4/7 = 57.1%**
- **Phase 7:** **6/7 = 85.7%**

The single new credit is the canonical Phase 4 deliverable **Implement numbered-heading detection**. It is supported by deterministic Persian/Arabic/Latin number parsing, proposal generation, fail-closed validation, full-pipeline persistence, exact matching, retry/fallback tests, and the complete PostgreSQL suite. No private-accuracy credit is inferred.

## AvalAI documentation rule

Before every AvalAI-dependent change or evidence interpretation:

1. update this ledger;
2. re-read the current official AvalAI OCR documentation;
3. separate documented, inferred, and measured behavior;
4. never infer retention, training, or residency guarantees;
5. update `docs/runbooks/exam-prep-v4-avalai-ocr-smoke.md`.

Official/current evidence re-read for the adapter and benchmark-wiring decision:

```text
https://docs.avalai.ir/fa/api-reference/ocr
https://docs.avalai.ir/fa/examples/processing_documents_with_mistral_ocr
https://docs.avalai.ir/fa/models/mistral-ocr-2512
https://docs.avalai.org/en/providers/mistralai
```

The adapter defaults to the reproducible `mistral-ocr-4-0` identifier. The mutable `mistral-ocr-latest` alias is retained only as measured historical evidence from the smoke.

## Closed adapter gate

Implemented:

```text
backend/apps/classes/services/exam_prep_v4_ocr_evidence.py
backend/apps/classes/test_exam_prep_v4_ocr_evidence.py
```

Verified behavior:

1. `document_annotation` is the primary per-page OCR call;
2. deterministic heading detection accepts Persian, Arabic, and Latin digits;
3. OCR blocks become bounded proposals only, then pass through existing SourceBlock parsing and persistence;
4. only `AvalAIOCRTransportError` receives bounded retry;
5. response/schema/privacy/configuration errors do not retry;
6. exhausted retries, malformed/empty evidence, low confidence, unsupported roles, and page/image mismatches fall back once for the whole segment;
7. bbox annotation is requested only when the document annotation reports a diagram;
8. answer pages without a new numbered heading may become continuation proposals only after an accepted primary answer block;
9. accepted unchanged blocks short-circuit before OCR or fallback calls;
10. disabled mode preserves the existing detector output;
11. adapter stats contain only counts, reason codes, and model identifiers—not OCR text, annotations, image bytes, local paths, credentials, or raw responses.

Focused evidence:

```text
System check identified no issues (0 silenced).
No changes detected in app 'classes'.
244 passed, 47 warnings in 24.41s
Focused frontend TypeScript check: passed
Source-map state-model tests: passed
```

## Active benchmark-wiring contract

The next change is limited to the private full-pipeline benchmark path. It must not enable OCR by default in production.

Required behavior:

1. construct the existing live structured provider exactly as before;
2. wrap it with `AvalAIOCREvidenceAdapter` only when an explicit benchmark option/flag is enabled;
3. keep classification, question extraction, answer-solution extraction, persistence, matching, cleanup, and warm reuse unchanged;
4. include aggregate OCR metrics in the benchmark report: OCR calls, retries, primary successes, bbox calls, fallback count/reasons, resolved model IDs, and wrapped-provider calls;
5. keep all private OCR content and request credentials out of the report;
6. calculate the worst-case external-request ceiling from fixture pages, configured OCR attempts/bbox escalation, classification calls, fallback block calls, and semantic batch calls;
7. fail before any provider call if the supplied hard ceiling is below the calculated maximum;
8. prove fake-mode output and existing live mode without OCR remain unchanged;
9. prove warm rerun performs zero extraction/OCR calls;
10. run the complete V4 PostgreSQL/frontend gate before requesting live execution authorization.

## Locked sequence

1. inspect and patch only `benchmark_exam_prep_v4_full_pipeline` and its benchmark service/provider construction;
2. add aggregate/report/privacy/ceiling tests;
3. run complete focused CI;
4. update this ledger, canonical roadmap, OCR runbook, and benchmark runbook;
5. present the exact calculated request ceiling and estimated cost for approval;
6. only after approval, run all three private PDFs once cold and once warm;
7. do not begin Phase 8, publication, or rollout.

## User action required

None during benchmark wiring. A single decision will be requested only after the exact hard request ceiling and cost envelope are calculated.

## Exact continuation point

Read the full-pipeline benchmark command and provider construction, then add optional OCR wrapping and deterministic ceiling calculation without changing production defaults. Keep progress at 43/77 until another canonical deliverable is proven.