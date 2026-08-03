# Exam Prep V4 — Implementation Status Ledger

> Operational companion to `exam-prep-v4-source-aware-split-pipeline.md`.
> This file is updated in every implementation turn before moving to another roadmap slice.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **Draft PR:** #4
- **Current phase:** Phase 2 — upload and fast source classification
- **Current slice:** Owner-scoped private page-thumbnail delivery
- **State:** Slice in progress; no Phase 3 mutation or Phase 4 extraction work is permitted
- **Last updated:** 2026-08-03
- **Verified checkpoint before this slice:** `e11e8f9d45b6eb5c420666ff0a60cf8e65d3c85f`
- **Focused evidence before this slice:** run `30776835064`, job `91573810334`, 104 tests passed

## Overall progress calculation

The overall percentage is calculated from the 77 explicit checklist deliverables in the canonical roadmap, not from commit count or lines of code.

Current credited work before closing this thumbnail slice:

| Phase | Credited deliverables | Total deliverables | Notes |
|---|---:|---:|---|
| Phase 0 | 5 | 6 | PR-level living-document enforcement remains open. |
| Phase 1 | 6 | 7 | Read-only Django admin inspection remains deferred. |
| Phase 2 | 8 | 9 | Core implementation is present; live private-fixture accuracy/latency evidence remains incomplete. |
| Phases 3–10 | 0 | 55 | Not started by design. |

**Credited total: 19 / 77 = 24.7%.**

The product-level V4 roadmap is therefore **24.7% complete before this slice**. This is intentionally conservative: infrastructure and APIs are real, but the heavier block detection, extraction, matching, review, publication, and rollout phases remain ahead.

The percentage will be recalculated only when a canonical roadmap deliverable or a formally recorded sub-deliverable is closed with tests and evidence.

## Roadmap guardrail

Work remains in Phase 2. This implementation turn may add only the private page-thumbnail read path required to inspect a source map.

Allowed work:

1. one owner-scoped thumbnail-content endpoint beneath a V4 project/document/page path;
2. feature-flag, teacher ownership, document ancestry, and page ancestry checks;
3. private storage streaming without exposing an object key or generated storage URL;
4. private cache headers, content type, content length when available, and inline-safe disposition;
5. negative tests for another teacher, wrong project/document/page combinations, disabled V4, missing blob, and generic `/media/` denial;
6. bounded-query and no-content-leak tests;
7. update this ledger with exact CI evidence.

Explicitly out of scope:

- full-resolution page delivery;
- page-role changes;
- boundary changes;
- rotate/reorder mutations;
- source-map confirmation;
- source-map UI;
- block detection;
- question or answer extraction;
- matching or publication;
- live private-fixture claims without an executed benchmark.

## Verified baseline

- Phase 0 architecture and private benchmark contracts exist.
- The three supplied private PDFs are independent exams.
- No private PDF, page image, native text, OCR text, answer, or solution content is committed.
- Existing V1/V2/V3 API, task, artifact, and publication behavior remains untouched.
- V4 is hidden when `EXAM_PREP_V4_ENABLED` is disabled.

## Phase 1 — complete except admin inspection

Implemented and verified:

- additive V4 models under the existing `classes` app;
- migration `classes.0040`;
- `ExamProject`, `ExamSourceDocument`, `ExamSourcePage`, and `ExamSourceSegment`;
- owner, organization, study-group, revision, status, fingerprint, and private-storage fields;
- project-scoped duplicate references;
- indexes and PostgreSQL constraints;
- one-PDF-one-project invariant;
- equal file hashes never merge projects;
- idempotent request/document identifiers;
- feature-gated service boundaries;
- migration drift and project-isolation tests.

Still deferred within Phase 1:

- Django admin/read-only inspection support.

## Phase 2 — completed portions

### Private source preparation

- Validates PDF header, size, encryption, and page-count limits.
- Stores the original PDF in private object storage.
- Renders pages serially with bounded memory.
- Stores private PNG page renders and JPEG thumbnails.
- Captures bounded native-text samples.
- Restores a named-but-missing private blob on an idempotent retry.
- Reuses unchanged valid blobs without duplicate writes.
- Deletes source, render, and thumbnail blobs after committed row deletion.
- Blocks all `exam-prep-v4/` objects from the generic `/media/` route.

### Fast page classification

- Builds bounded numbered contact sheets.
- Uses bounded native-text evidence only as supplemental classifier input.
- Uses the central OpenAI-compatible gateway and central V4 prompt registry.
- Selects the model only from environment configuration.
- Validates classifier records independently.
- Preserves valid sibling records when another record is malformed.
- Converts missing pages to explicit `unknown` records.
- Preserves teacher overrides without erasing model predictions.
- Fingerprints source, revision, sheets, model, catalog, and prompt version.
- Skips provider calls for accepted warm reruns.

### Deterministic virtual split

- Produces a complete one-based page map.
- Groups adjacent equal effective roles without reordering pages.
- Supports cover-first, answer-first, and cover-in-the-middle structures.
- Persists proposed segments against classification revision and fingerprint.
- Rejects stale revisions and conflicting accepted fingerprints.

### Multi-PDF intake API — verified

```text
POST /api/classes/exam-prep-v4/projects/
```

- accepts several PDFs while creating one independent project per PDF;
- prevalidates the whole batch before writes;
- preserves idempotency and restores missing private blobs;
- dispatches one independent task per source document;
- validates owner, organization, and study-group scope;
- preserves private sources across broker failures.

### Read-only source-map APIs — verified

```text
GET /api/classes/exam-prep-v4/projects/
GET /api/classes/exam-prep-v4/projects/<project_id>/
```

- list and detail are owner-scoped;
- another teacher receives 404;
- current-revision pages and segments are returned in deterministic order;
- private filenames, object keys, hashes, native text, raw model metadata, fingerprints, error details, and organization identities are excluded;
- list and detail query counts are bounded.

## Latest completed focused evidence

- **Run:** `30776835064`
- **Job:** `91573810334`
- **Head:** `e11e8f9d45b6eb5c420666ff0a60cf8e65d3c85f`
- **Environment:** Python 3.12, PostgreSQL 16, Redis 7
- **Result:** success

```text
System check identified no issues (0 silenced).
No changes detected in app 'classes'.
104 passed, 23 warnings in 8.90s
```

Warnings are limited to the CI checkout lacking generated `backend/staticfiles/` when API/private-media tests initialize Django handlers.

## Current slice acceptance criteria

The private thumbnail slice is complete only when all of these are proven:

- the project, document, and page form one owner-scoped ancestry chain;
- another teacher receives 404;
- wrong project/document/page combinations receive 404;
- disabled V4 receives 404;
- missing private blobs fail without revealing storage details;
- the response streams bytes from private storage and never returns a storage URL or key;
- content type is `image/jpeg` for stored thumbnails;
- cache headers are private and shared caches cannot retain the response;
- generic `/media/exam-prep-v4/...` remains denied;
- the response includes no private object name in headers or body;
- database query count is bounded;
- focused PostgreSQL tests, system check, and migration drift check pass;
- this ledger is updated with exact evidence and the new percentage.

## Next verified step

Implement only:

```text
GET /api/classes/exam-prep-v4/projects/<project_id>/documents/<document_id>/pages/<page_number>/thumbnail/
```

Do not add mutation, source confirmation, full-resolution delivery, Phase 3 UI, or Phase 4 block detection in this slice.
