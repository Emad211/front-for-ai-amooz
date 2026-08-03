# Exam Prep V4 — Implementation Status Ledger

> Update this file before every V4 implementation step. Canonical roadmap: `exam-prep-v4-source-aware-split-pipeline.md`.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **PR:** #4 — Draft
- **Current span:** Phase 2 + Phase 4 → Phase 7 private full-pipeline evidence
- **Last completed slice:** optional OCR adapter, OCR-aware benchmark guard and one-click three-PDF workflow
- **Active gate:** execute the manual full live benchmark exactly once and inspect aggregate evidence
- **Feature/workflow contract checkpoint:** `5db6e4b7eab2d4ae3150b79d342b8cfc93b107c9`
- **Manual workflow on main:** `5903d08fc3f58d8625f4ddf80fdccd92949b1ac6`
- **Focused CI:** `30857010156`
- **Backend job:** `91830257210`
- **Frontend job:** `91830257126`
- **Validated merge ref:** `54e401d067c596444b20e1c4497d77fd7ad58615`
- **Result:** 252 backend tests passed; migration drift zero; frontend focused validation passed
- **Hard live ceiling:** 484 external requests
- **Structured model:** `gemini-2.5-flash`
- **OCR model:** `mistral-ocr-4-0`
- **Last updated:** 2026-08-04

## Progress

| Phase | Credited | Total | State |
|---|---:|---:|---|
| Phase 0 | 5 | 6 | PR ledger enforcement remains open. |
| Phase 1 | 6 | 7 | Read-only admin inspection remains deferred. |
| Phase 2 | 8 | 9 | Real three-fixture classification evidence is active. |
| Phase 3 | 4 | 7 | Split/group and browser accessibility evidence remain open. |
| Phase 4 | 4 | 8 | Numbered headings complete; private layout/RTL/diagram/continuation evidence active. |
| Phase 5 | 6 | 7 | Private question precision/recall active. |
| Phase 6 | 4 | 7 | Private answer-heading/key/inline evidence open. |
| Phase 7 | 6 | 7 | Private automatic-match precision/consistency active. |
| Phases 8–10 | 0 | 20 | Not started. |

- **Overall:** **43/77 = 55.8%**
- **Phase 4:** **4/8 = 50.0%**
- **Phase 5:** **6/7 = 85.7%**
- **Phase 6:** **4/7 = 57.1%**
- **Phase 7:** **6/7 = 85.7%**

No private-accuracy credit is added before the live report and human review.

## AvalAI documentation rule

For every AvalAI-dependent step:

1. update this ledger first;
2. re-read the relevant official AvalAI pages;
3. pin reproducible model IDs;
4. separate documentation, inference and measurement;
5. never infer retention/training/residency guarantees;
6. update the OCR and benchmark runbooks.

Reviewed for this gate:

```text
https://docs.avalai.ir/fa/api-reference/ocr
https://docs.avalai.ir/fa/examples/processing_documents_with_mistral_ocr
https://docs.avalai.ir/fa/models/mistral-ocr-2512
```

## Closed implementation gates

### OCR evidence adapter

```text
backend/apps/classes/services/exam_prep_v4_ocr_evidence.py
backend/apps/classes/test_exam_prep_v4_ocr_evidence.py
```

Verified:

- primary `document_annotation` request;
- deterministic Persian/Arabic/Latin numbered headings;
- diagram-only bbox escalation;
- retry only for transport failures;
- whole-segment fallback for exhausted/invalid/low-confidence evidence;
- existing SourceBlock parser/persistence remains authoritative;
- accepted unchanged evidence makes zero OCR/detector calls;
- private content excluded from stats/public output.

### OCR-aware full benchmark

```text
backend/apps/classes/services/exam_prep_v4_benchmark_guard.py
backend/apps/classes/management/commands/benchmark_exam_prep_v4_full_pipeline.py
backend/apps/classes/test_exam_prep_v4_benchmark_guard.py
```

Verified:

- OCR enabled only by explicit benchmark flag;
- structured calls reserve three external slots;
- direct OCR calls reserve one slot before transport;
- below-plan ceilings fail before project/provider access;
- report contains aggregate call/retry/fallback/ceiling data only;
- fake and non-OCR modes remain unchanged;
- warm extraction reuse remains zero-call.

### Workflow contract

```text
.github/workflows/exam-prep-v4-full-live-benchmark.yml
backend/apps/classes/test_exam_prep_v4_full_live_workflow.py
```

Verified:

- manual `workflow_dispatch` only;
- no confirmation input;
- no automatic retry;
- exact three private PDFs only;
- PostgreSQL 16 and Redis 7;
- preflight asserts required ceiling 484 before provider calls;
- one cold/warm run;
- aggregate report or content-free failure summary retained one day;
- no PR comment/raw output;
- private fixture checkout/temp files deleted in `always()`.

Focused evidence:

```text
System check identified no issues (0 silenced).
No changes detected in app 'classes'.
252 passed, 47 warnings in 25.62s
Focused frontend TypeScript check: passed
Source-map state-model tests: passed
```

## Hard request ceiling

```text
classification invocations: 3
possible structured block fallbacks: 6
semantic batch invocations: 79
structured invocations: 88
structured external upper bound: 264
OCR-eligible pages: 55
OCR external upper bound: 220
required minimum: 484
```

This is a worst-case fail-closed upper bound, not expected usage. Actual calls should be lower when OCR succeeds first attempt, pages lack diagrams, structured output needs no fallback/repair and OCR avoids detector fallback.

Planning envelope remains **$10 maximum for this single run**. Exact cost is recorded from AvalAI transaction/request evidence after execution.

## Active workflow

```text
name: exam-prep-v4-full-live-benchmark
branch: main
workflow commit: 5903d08fc3f58d8625f4ddf80fdccd92949b1ac6
secret: AVALAI_API_KEY
artifact: exam-prep-v4-full-live-aggregate
retention: 1 day
```

## User action required now

Run exactly once:

```text
GitHub
→ Actions
→ exam-prep-v4-full-live-benchmark
→ Run workflow
→ Run workflow
```

There is no input field. Do not start it twice.

## Exact continuation point

After the run starts:

1. recover run/job IDs;
2. inspect terminal step and aggregate artifact;
3. determine actual calls, retries, fallbacks, latency, structural accuracy, question/answer recall, match precision and warm reuse;
4. update this ledger, canonical roadmap and runbooks;
5. remove the temporary workflow from `main`;
6. credit only canonical deliverables actually proven;
7. continue the roadmap from the first failed private gate—never jump to Phase 8.