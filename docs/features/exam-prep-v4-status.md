# Exam Prep V4 — Implementation Status Ledger

> Living execution ledger. Update this file before every V4 implementation step. Canonical roadmap: `exam-prep-v4-source-aware-split-pipeline.md`.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **PR:** #4 — Draft
- **Execution mode:** Critical Path Acceleration
- **Current roadmap span:** Phase 4 → Phase 7 vertical extraction path
- **Last completed slice:** fixed and validated the manual live OCR workflow syntax on `main`
- **Active gate:** inspect failed live OCR run `30852221763`, establish exact failure step and provider-request count, then patch only that failure
- **Validated feature checkpoint before live run:** `3bc8814726cf2218d3b8534ce6b0d74120e2c4f1`
- **Focused verification workflow:** `30850414707`
- **Focused backend job:** `91808774481`
- **Focused frontend job:** `91808774469`
- **Focused result:** 235 backend tests passed; frontend focused validation passed
- **Manual live workflow on main:** `867817effb4df7669c4d1ec04f2775e25d615201`
- **Failed live run:** `30852221763`
- **Failed live job:** `91814702919`
- **Exact external request count:** pending log inspection; rerun prohibited until recovered
- **Last updated:** 2026-08-04

## Progress

Progress is counted only from the 77 canonical roadmap deliverables.

| Phase | Credited | Total | State |
|---|---:|---:|---|
| Phase 0 | 5 | 6 | PR ledger enforcement remains open. |
| Phase 1 | 6 | 7 | Read-only admin inspection remains deferred. |
| Phase 2 | 8 | 9 | Real private classification benchmark remains open and uncredited. |
| Phase 3 | 4 | 7 | Core Source Map works; split/group and browser validation remain open. |
| Phase 4 | 3 | 8 | Block persistence/continuation/inspection are verified; real OCR/layout quality remains open. |
| Phase 5 | 6 | 7 | Typed question path is verified; private precision/recall remains open. |
| Phase 6 | 4 | 7 | Unified answer-solution path is verified; real heading/answer-key/inline quality remains open. |
| Phase 7 | 6 | 7 | Deterministic matching is verified; complete consistency gate remains open. |
| Phases 8–10 | 0 | 20 | Not started. |

- **Entire V4 roadmap:** **42/77 = 54.5%**
- **Phase 4:** **3/8 = 37.5%**
- **Phase 5:** **6/7 = 85.7%**
- **Phase 6:** **4/7 = 57.1%**
- **Phase 7:** **6/7 = 85.7%**

No progress credit is added before measured private evidence closes a canonical deliverable.

## Roadmap and privacy invariants

1. every uploaded PDF remains an independent project by default;
2. physical page identity, project scope, and evidence provenance remain authoritative;
3. questions originate only from accepted question-bearing evidence;
4. answer-only content never creates questions;
5. answer and complete source solution remain one record;
6. automatic matching remains deterministic and project-scoped;
7. ambiguous evidence remains unresolved rather than guessed;
8. malformed provider siblings remain isolated;
9. accepted unchanged units are excluded from provider calls;
10. private source content, paths, crops, OCR text, annotations, credentials, request IDs, and raw provider output remain outside public serializers, logs, and recorded roadmap evidence;
11. historical revisions remain auditable;
12. production routing is not changed by a feasibility smoke;
13. Phase 8 and rollout remain blocked until private evidence is recorded or explicitly waived;
14. one live OCR workflow run at a time; no rerun until prior request count is known.

## AvalAI documentation rule

Before any AvalAI-dependent implementation or retry:

1. update this ledger;
2. re-read the current official AvalAI documentation;
3. pin reproducible model identifiers;
4. separate documented, inferred, and measured behavior;
5. never infer retention, training, or residency guarantees;
6. update the OCR runbook with evidence.

Official pages for this gate:

```text
https://docs.avalai.ir/fa/api-reference/ocr
https://docs.avalai.ir/fa/examples/processing_documents_with_mistral_ocr
https://docs.avalai.ir/fa/models/mistral-ocr-2512
```

## Authorized live fixture

```text
source PDF: دفترچه اول (زیست).pdf on main
question page: physical page 5
answer-solution page: physical page 12
model: mistral-ocr-4-0
modes: markdown, blocks, document_annotation, bbox_annotation
hard external-request ceiling: 8
credential: repository Actions secret AVALAI_API_KEY
```

The complete PDF must never be sent to AvalAI. Only the two locally rendered bounded PNG images are authorized.

## Current failed live run

```text
run: https://github.com/Emad211/front-for-ai-amooz/actions/runs/30852221763
job: https://github.com/Emad211/front-for-ai-amooz/actions/runs/30852221763/job/91814702919
```

Until logs are inspected:

- no rerun;
- no production routing change;
- no roadmap-credit increase;
- no assumption of zero, partial, or eight provider requests.

## Exact continuation point

1. fetch job steps and complete logs for job `91814702919`;
2. identify the first failing step;
3. determine whether `smoke_exam_prep_v4_avalai_ocr` started;
4. determine exact completed provider-request count;
5. patch only the demonstrated failure;
6. run focused/static verification;
7. update this ledger and the OCR runbook before any retry.