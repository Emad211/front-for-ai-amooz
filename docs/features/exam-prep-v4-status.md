# Exam Prep V4 — Implementation Status Ledger

> Living execution ledger. Update this file before every V4 implementation step. Canonical roadmap: `exam-prep-v4-source-aware-split-pipeline.md`.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **PR:** #4 — Draft
- **Execution mode:** Critical Path Acceleration
- **Current roadmap span:** Phase 4 → Phase 7 vertical extraction path
- **Last completed slice:** fixed and validated the manual live OCR workflow syntax on `main`
- **Active gate:** inspect the failed manual live OCR run, establish the exact failing step and executed request count, then patch only that failure
- **Validated feature implementation checkpoint before live run:** `3bc8814726cf2218d3b8534ce6b0d74120e2c4f1`
- **Focused workflow:** `30850414707`
- **Backend job:** `91808774481`
- **Frontend job:** `91808774469`
- **Focused result:** 235 backend tests passed; frontend focused validation passed
- **Current manual live workflow on main:** `867817effb4df7669c4d1ec04f2775e25d615201`
- **Latest manual run state reported by product owner:** failed
- **Exact workflow run/job ID:** pending recovery
- **Exact external request count:** unknown; rerun prohibited until recovered
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
14. one live OCR workflow run at a time; no rerun until the prior request count is known.

## AvalAI documentation rule

For every AvalAI-dependent turn:

1. update this ledger before code or live execution;
2. re-read the relevant current official AvalAI documentation;
3. pin reproducible model identifiers instead of mutable aliases;
4. separate documented behavior, inference, and measured behavior;
5. never infer endpoint retention, training, or residency guarantees;
6. record reviewed documentation in the related runbook.

Official pages re-read for this gate:

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

The complete PDF is never sent to AvalAI. GitHub Actions reads the PDF, renders only pages 5 and 12 locally, and sends only those two bounded PNG images.

## Verified implementation and safety gate

The feature-branch workflow and static tests verify:

- `%PDF-` signature and exact 16-page count;
- only physical pages 5 and 12 are rendered;
- image size bounds and byte-distinctness;
- four explicit modes and hard ceiling 8;
- aggregate-only artifact with one-day retention;
- cleanup of temporary PDF, PNGs, path files, and local report;
- no additional image URL secrets;
- no automatic live trigger.

```text
System check identified no issues (0 silenced).
No changes detected in app 'classes'.
235 passed, 47 warnings in 21.06s
Focused frontend TypeScript check: passed
Source-map state-model tests: passed
```

## Workflow syntax failure and correction

The first manual workflow revision failed validation because `runner.temp` was referenced inside job-level `env`, where that context was not recognized.

Correction:

```text
PRIVATE_DIR: /tmp/exam-prep-v4-ocr-smoke
REPORT_PATH: /tmp/exam-prep-v4-ocr-smoke/aggregate-report.json
artifact path: ${{ env.REPORT_PATH }}
```

The same correction was applied to the feature-branch workflow and enforced by a static test that rejects `${{ runner.temp }}` in the workflow.

The obsolete push marker was removed. No live OCR request was issued by the invalid workflow or the connector-generated push attempt.

## Current failed manual run

The product owner manually started the corrected workflow and reported a failure. No sanitized aggregate comment has appeared on PR #4, so the terminal stage and request count are not yet proven.

Until the exact run/job is inspected:

- do not rerun;
- do not modify production routing;
- do not increase roadmap credit;
- do not assume zero or eight provider requests;
- do not infer the error from the absence of a PR comment.

## Active investigation contract

Only this sequence is allowed:

1. recover the manual workflow run URL/ID;
2. fetch job steps and complete logs;
3. identify the exact first failing step;
4. determine whether the live command started and, if so, how many requests completed;
5. patch only the demonstrated failure;
6. run static/focused CI before any bounded retry;
7. update this ledger and the OCR runbook with evidence.

## User action required only if connector discovery is insufficient

Provide only the GitHub Actions run URL from the browser address bar. Do not paste logs, the API key, PDF content, OCR output, or screenshots containing secrets.

## Exact continuation point

Recover and inspect the failed run. Then fix only the proven cause, update this ledger before retry, and keep the 42/77 score unchanged until measured OCR evidence is reviewed.