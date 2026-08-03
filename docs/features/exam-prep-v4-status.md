# Exam Prep V4 — Implementation Status Ledger

> Living execution ledger. Update this file before every V4 implementation step. Canonical roadmap: `exam-prep-v4-source-aware-split-pipeline.md`.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **PR:** #4 — Draft
- **Execution mode:** Critical Path Acceleration
- **Current roadmap span:** Phase 4 → Phase 7 vertical extraction path
- **Last completed slice:** validated direct extraction of two representative pages from the `main` fixture for the guarded OCR smoke
- **Active gate:** determine the result of the authorized one-shot live OCR workflow, record aggregate evidence, and disable the one-shot trigger
- **Validated feature implementation checkpoint:** `3bc8814726cf2218d3b8534ce6b0d74120e2c4f1`
- **Focused workflow:** `30850414707`
- **Backend job:** `91808774481`
- **Frontend job:** `91808774469`
- **Focused result:** 235 backend tests passed; frontend focused validation passed
- **One-shot workflow installed on main:** `6337a1dcd191e41c967f560aeb686f45835179f5`
- **Authorized trigger commit on main:** `fd39c172662bc91e8c5e0e2078630c418ef80aa4`
- **Last updated:** 2026-08-03

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
10. private source content, paths, crops, OCR text, annotations, request credentials, and raw provider output remain outside public serializers, logs, PR comments, and aggregate reports;
11. historical revisions remain auditable;
12. production routing is not changed by a feasibility smoke;
13. Phase 8 and rollout remain blocked until private evidence is recorded or explicitly waived;
14. no second live OCR run may be triggered until the first one-shot outcome is known and the trigger is disabled or explicitly re-authorized.

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

## Product-owner authorization and fixture selection

The product owner authorized live requests, confirmed repository Actions secret `AVALAI_API_KEY`, and permitted use of the private PDFs stored on `main`.

The live smoke is restricted to:

```text
source PDF: دفترچه اول (زیست).pdf
question page: physical page 5
answer-solution page: physical page 12
model: mistral-ocr-4-0
modes: markdown, blocks, document_annotation, bbox_annotation
hard external-request ceiling: 8
```

The complete PDF is never submitted to AvalAI. The runner renders pages 5 and 12 locally and only those two bounded PNG images may leave the runner.

## Verified pre-live workflow gate

The feature-branch workflow and static tests prove:

- source file is read from `origin/main` without adding it to the V4 branch;
- `%PDF-` signature and exact 16-page count are checked;
- only physical pages 5 and 12 are rendered;
- images are bounded and byte-distinct;
- exactly four modes and a maximum of eight requests are configured;
- only `aggregate-report.json` may be uploaded for one day;
- temporary PDF, PNGs, path files, and local report are deleted;
- no URL secrets or additional private transport are required.

Verification:

```text
System check identified no issues (0 silenced).
No changes detected in app 'classes'.
235 passed, 47 warnings in 21.06s
Focused frontend TypeScript check: passed
Source-map state-model tests: passed
```

## One-shot execution mechanism

A one-shot workflow was installed on `main` because GitHub manual dispatch requires the workflow file on the default branch and the available connector cannot dispatch arbitrary workflows directly.

Files/commits:

```text
.github/workflows/exam-prep-v4-avalai-ocr-one-shot.yml
workflow installation commit: 6337a1dcd191e41c967f560aeb686f45835179f5
trigger file: .github/v4-ocr-live-trigger
trigger commit: fd39c172662bc91e8c5e0e2078630c418ef80aa4
```

The workflow runs only when all of these match:

- push to `main`;
- changed path `.github/v4-ocr-live-trigger`;
- exact commit message `chore(exam-prep-v4): [run-v4-ocr-smoke] authorized one-shot`.

It checks out validated V4 code separately, sparse-checks out only the selected PDF, extracts two pages, runs the smoke, posts a sanitized aggregate-only result to PR #4, retains the aggregate artifact for one day, and deletes private checkout/render files.

## Current evidence state

- The trigger commit was created.
- No marked aggregate OCR comment has yet been observed on PR #4.
- Therefore the workflow outcome is currently **unknown**, not passed or failed.
- No live-result claims and no roadmap credit are permitted until the run/job or sanitized result is recovered.

## Active investigation contract

Only the following work is allowed now:

1. locate the push-triggered one-shot workflow run or check-run;
2. determine whether it is queued, running, skipped, failed, or successful;
3. if successful, retrieve only the aggregate artifact/comment and record measured evidence;
4. if failed before or during provider calls, establish the exact request count before any retry decision;
5. disable/remove the trigger after a terminal outcome;
6. do not issue a second live run without explicit evidence that the first made zero requests or a new product-owner authorization.

## User action required

No user action is required while the one-shot outcome is being recovered.

## Exact continuation point

Find the one-shot push workflow state for commit `fd39c172662bc91e8c5e0e2078630c418ef80aa4`. Then record aggregate evidence or the exact failure stage, disable the one-shot trigger, update this ledger and the OCR runbook, and only afterward decide whether a bounded retry is safe. Do not change production routing or the 42/77 score before measured evidence is reviewed.