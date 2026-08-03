# Exam Prep V4 — Implementation Status Ledger

> Living execution ledger. Update this file before every V4 implementation step. Canonical roadmap: `exam-prep-v4-source-aware-split-pipeline.md`.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **PR:** #4 — Draft
- **Execution mode:** Critical Path Acceleration
- **Current roadmap span:** Phase 4 → Phase 7 vertical extraction path
- **Last completed slice:** fixed and validated the manual live OCR workflow syntax on `main`
- **Active gate:** product-owner manual dispatch of the bounded two-page live OCR workflow, followed by aggregate evidence recording and workflow removal
- **Validated feature implementation checkpoint before syntax fix:** `3bc8814726cf2218d3b8534ce6b0d74120e2c4f1`
- **Focused workflow:** `30850414707`
- **Backend job:** `91808774481`
- **Frontend job:** `91808774469`
- **Focused result:** 235 backend tests passed; frontend focused validation passed
- **Valid manual live workflow commit on main:** `867817effb4df7669c4d1ec04f2775e25d615201`
- **Feature workflow syntax/test commits:** `19836ec62d18db99e25bc318baeb4d575fcb19f6`, `f16f57619982ae5418546a1db0773d436d31afa0`
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

## Current manual workflow

```text
.github/workflows/exam-prep-v4-avalai-ocr-one-shot.yml
main commit: 867817effb4df7669c4d1ec04f2775e25d615201
```

The workflow is `workflow_dispatch`-only and requires:

```text
I_APPROVE_8_PRIVATE_OCR_REQUESTS
```

It checks out V4 code, sparse-checks out only the first PDF, renders pages 5 and 12, executes the bounded smoke, uploads only aggregate evidence, posts a sanitized PR comment, and cleans private temporary files.

## User action required now

In GitHub:

```text
Actions
→ exam-prep-v4-avalai-ocr-one-shot
→ Run workflow
→ Branch: main
→ confirmation: I_APPROVE_8_PRIVATE_OCR_REQUESTS
→ Run workflow
```

Run it once only. After starting it, report only `شروع شد`.

## Exact continuation point

After the single manual workflow run starts:

1. inspect the sanitized PR comment and workflow result;
2. determine exact executed request count and terminal status;
3. record measured evidence in this ledger and the OCR runbook;
4. remove the manual workflow from `main`;
5. decide OCR-first, transcription-only, diagram-only, or rejected;
6. do not change production routing or the 42/77 score before evidence review.