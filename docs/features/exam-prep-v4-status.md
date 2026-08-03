# Exam Prep V4 — Implementation Status Ledger

> Living execution ledger. Update this file before every V4 implementation step. Canonical roadmap: `exam-prep-v4-source-aware-split-pipeline.md`.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **PR:** #4 — Draft
- **Execution mode:** Critical Path Acceleration
- **Current roadmap span:** Phase 2 + Phase 4 → Phase 7 private full-pipeline evidence
- **Last completed slice:** optional OCR evidence adapter wired into the bounded aggregate full-pipeline benchmark with deterministic preflight ceiling calculation
- **Active gate:** install a simple manual GitHub Actions workflow for one cold/warm run of the three private PDFs, then execute and inspect aggregate evidence
- **Benchmark-wiring checkpoint:** `ac806c6a6ad409a3c209b41f78cba15674466835`
- **Focused workflow:** `30856605364`
- **Backend job:** `91828966959`
- **Frontend job:** `91828967132`
- **Validated PR merge ref:** `935800b8802528bd0e652264f35a718dcb5729b7`
- **Focused result:** 248 backend tests passed; migration drift zero; frontend focused validation passed
- **Calculated three-private-PDF ceiling:** 484 external requests
- **Selected structured model for first live benchmark:** `gemini-2.5-flash`
- **Selected OCR model:** `mistral-ocr-4-0`
- **Last updated:** 2026-08-04

## Progress

Progress remains based on the 77 canonical roadmap deliverables.

| Phase | Credited | Total | State |
|---|---:|---:|---|
| Phase 0 | 5 | 6 | PR ledger enforcement remains open. |
| Phase 1 | 6 | 7 | Read-only admin inspection remains deferred. |
| Phase 2 | 8 | 9 | Real three-fixture classification evidence is the active live gate. |
| Phase 3 | 4 | 7 | Core Source Map works; split/group and browser validation remain open. |
| Phase 4 | 4 | 8 | Numbered-heading detection is complete; private layout/formula/diagram/continuation evidence is active. |
| Phase 5 | 6 | 7 | Private question precision/recall is active. |
| Phase 6 | 4 | 7 | Private answer-heading/answer-key/inline evidence remains open. |
| Phase 7 | 6 | 7 | Private automatic-match precision and consistency evidence is active. |
| Phases 8–10 | 0 | 20 | Not started. |

- **Entire V4 roadmap:** **43/77 = 55.8%**
- **Phase 4:** **4/8 = 50.0%**
- **Phase 5:** **6/7 = 85.7%**
- **Phase 6:** **4/7 = 57.1%**
- **Phase 7:** **6/7 = 85.7%**

No live-accuracy credit is added before aggregate and private human-review evidence is available.

## AvalAI documentation rule

Before every AvalAI-dependent change or evidence interpretation:

1. update this ledger;
2. re-read the current official AvalAI documentation;
3. separate documented, inferred, and measured behavior;
4. never infer retention, training, or residency guarantees;
5. update the OCR and benchmark runbooks.

Current official documentation confirms:

- `mistral-ocr-4-0` is the reproducible OCR4 identifier;
- AvalAI exposes model capability/pricing metadata through its model endpoints;
- Gemini supports multimodal input through AvalAI;
- exact authoritative cost can be recovered from transaction/request identifiers after execution;
- rate limits are model/tier dependent, so transient failures remain retry/fallback evidence rather than correctness evidence.

## Closed benchmark-wiring gate

Implemented:

```text
backend/apps/classes/services/exam_prep_v4_benchmark_guard.py
backend/apps/classes/management/commands/benchmark_exam_prep_v4_full_pipeline.py
backend/apps/classes/test_exam_prep_v4_benchmark_guard.py
```

New command options:

```text
--ocr-evidence
--ocr-model mistral-ocr-4-0
--ocr-max-attempts 2
--ocr-bbox-for-diagrams
--max-provider-calls <hard ceiling>
--show-required-ceiling
```

Verified behavior:

1. production/default provider routing remains unchanged;
2. OCR wrapping occurs only in explicit `live_provider --ocr-evidence` benchmark mode;
3. every structured invocation reserves three external-call slots for JSON-mode/fallback/repair;
4. every direct OCR request reserves one external-call slot before HTTP transport;
5. a supplied ceiling below the manifest/config plan fails before project creation or provider access;
6. aggregate reports include ceiling plan, consumed upper bound, OCR calls/retries/successes/bbox calls/fallback counts/reasons and resolved model IDs;
7. private OCR text, annotations, source bytes, paths, credentials and raw responses remain excluded;
8. fake mode is unchanged and rejects live OCR evidence configuration;
9. warm extraction reuse remains zero-call;
10. runtime still fails before the next request if provider output creates more work than the manifest plan.

Focused evidence:

```text
System check identified no issues (0 silenced).
No changes detected in app 'classes'.
248 passed, 47 warnings in 26.02s
Focused frontend TypeScript check: passed
Source-map state-model tests: passed
```

## Deterministic ceiling for the recorded private fixtures

Manifest inventory:

```text
fixtures: 3
classification invocations: 3
non-cover segment fallback invocations: 6
semantic batch invocations: 79
structured invocations: 88
structured external upper bound: 264
OCR-eligible pages: 55
OCR primary + optional bbox attempts: 220
hard required minimum: 484
```

The 484 value is a fail-closed upper bound, not an expected usage count. It assumes:

- two OCR attempts for every eligible page;
- separate bbox annotation on every eligible page;
- structured fallback block detection for every non-cover segment;
- three possible external requests for every structured invocation;
- all semantic batches implied by the recorded expected question/out-of-scope inventory.

Actual usage should be materially lower when first-attempt OCR succeeds, pages lack diagrams, structured output does not require fallback/repair, and OCR avoids block-detector calls.

## Model and cost envelope

First live benchmark configuration:

```text
classifier/block/question/answer model: gemini-2.5-flash
OCR model: mistral-ocr-4-0
OCR attempts: 2
bbox escalation: enabled only when page annotation reports a diagram
hard external-call ceiling: 484
```

Planning envelope:

- OCR worst-case annotation component: up to approximately `$1.10` for 220 annotated-page requests at the documented `$0.005` rate;
- structured-model cost is token-dependent and cannot be derived from request count alone;
- a conservative total benchmark spend envelope of **$10** is adopted for this single run;
- exact cost must be recovered from AvalAI transaction data after execution.

The workflow must stop at the 484-call ceiling. It must not automatically rerun.

## Live workflow contract

Create one `workflow_dispatch`-only workflow on `main` with no confirmation phrase or extra input. It must:

1. use repository secret `AVALAI_API_KEY`;
2. check out V4 code and only the three named PDF fixtures;
3. run PostgreSQL and Redis locally;
4. build the recorded manifest in runner temp storage;
5. execute one cold/warm full benchmark with the configuration above;
6. retain only an aggregate report or content-free failure summary for one day;
7. clean the private fixture checkout and temporary files in `always()`;
8. never post raw or private output to PR comments;
9. never rerun automatically;
10. be removed from `main` after terminal evidence is recovered.

## User action required

None while the workflow is being installed and statically verified. After installation, one manual click in GitHub Actions will be required because the connected GitHub tool cannot dispatch `workflow_dispatch` runs.

## Exact continuation point

Create and validate the simple one-click full live benchmark workflow on `main`. Then update this ledger with its commit and give the user only the minimal Run workflow instruction. Do not start Phase 8 or change the 43/77 score before the live report is reviewed.