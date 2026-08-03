# Exam Prep V4 — Implementation Status Ledger

> Living execution ledger. Update this file before every V4 implementation step. Canonical roadmap: `exam-prep-v4-source-aware-split-pipeline.md`.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **PR:** #4 — Draft
- **Execution mode:** Critical Path Acceleration
- **Current roadmap span:** Phase 4 → Phase 7 vertical extraction path
- **Last completed slice:** diagnosed the first live OCR run and implemented pass/fail aggregate-evidence preservation
- **Active gate:** inspect second live OCR run `30854537419`, recover the aggregate artifact, record measured evidence, and decide the bounded OCR role in V4
- **First live run/job:** `30852221763` / `91814702919`
- **First-run external requests:** 8 completed
- **Second live run/job:** `30854537419` / `91822320489`
- **Second-run terminal state:** pending inspection
- **Second-run external request count:** pending inspection
- **Evidence-preservation workflow commit:** `32913cff94bc58493f09c9abe9f7204985fbabb0`
- **Evidence-preservation static-test commit:** `137518464ec3d2ee60a6051b07432cf6b8832f57`
- **Operational workflow on main:** `5947a090c927243a1a7402b38cb59539af6a3972`
- **Focused verification workflow:** `30853630677`
- **Focused result:** 236 backend tests passed; frontend focused validation passed
- **Last updated:** 2026-08-04

## Progress

Progress is counted only from the 77 canonical roadmap deliverables.

| Phase | Credited | Total | State |
|---|---:|---:|---|
| Phase 0 | 5 | 6 | PR ledger enforcement remains open. |
| Phase 1 | 6 | 7 | Read-only admin inspection remains deferred. |
| Phase 2 | 8 | 9 | Real private classification benchmark remains open and uncredited. |
| Phase 3 | 4 | 7 | Core Source Map works; split/group and browser validation remain open. |
| Phase 4 | 3 | 8 | Block persistence/continuation/inspection are verified; real OCR/layout quality remains under measured review. |
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
10. private bytes, OCR text, annotations, credentials, and raw provider output remain outside logs and roadmap evidence;
11. historical revisions remain auditable;
12. production routing is unchanged by the smoke;
13. Phase 8 and rollout remain blocked;
14. no further live run may start until the second run artifact and exact request count are reviewed.

## AvalAI documentation rule

Before every AvalAI-dependent change, execution, or evidence interpretation:

1. update this ledger;
2. re-read the current official AvalAI documentation;
3. separate documented, inferred, and measured behavior;
4. never infer retention/training/residency guarantees;
5. update `docs/runbooks/exam-prep-v4-avalai-ocr-smoke.md`.

Official pages for this gate:

```text
https://docs.avalai.ir/fa/api-reference/ocr
https://docs.avalai.ir/fa/examples/processing_documents_with_mistral_ocr
https://docs.avalai.ir/fa/models/mistral-ocr-2512
```

## Authorized retry fixture

```text
source PDF: دفترچه اول (زیست).pdf
question page: 5
answer-solution page: 12
requested model: mistral-ocr-latest
modes: markdown, blocks, document_annotation, bbox_annotation
hard ceiling: 8 additional requests
```

The complete PDF is not transmitted. Only two locally rendered bounded PNG images are authorized.

## Active investigation contract

Only this sequence is allowed now:

1. inspect run `30854537419` and job `91822320489`;
2. determine exact terminal state and completed request count;
3. retrieve the aggregate-only artifact, including pass/fail per mode and content-free error classes;
4. record resolved model, latency, counts, issue codes, and evidence limitations;
5. update this ledger, the OCR runbook, and the canonical checkpoint;
6. remove the one-shot workflow from `main` after evidence is secured;
7. decide OCR-first, transcription-only, diagram-only, or rejected;
8. do not change production routing or roadmap credit before evidence review.

## User action required

No user action is required during this inspection.

## Exact continuation point

Fetch the second run job, logs, and artifacts. Analyze only aggregate evidence, then synchronize the roadmap documents and remove the one-shot operational workflow.