# Exam Prep V4 — Implementation Status Ledger

> Operational companion to `exam-prep-v4-source-aware-split-pipeline.md`.
> This file is updated in every implementation turn before moving to another roadmap slice.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **Draft PR:** #4
- **Current phase:** Phase 2 — upload and fast source classification
- **Current slice:** Owner-scoped read-only source-map APIs
- **State:** Multi-PDF intake and independent task dispatch verified; source-map reads not yet implemented
- **Last updated:** 2026-08-03
- **Verified checkpoint:** `640b63e0031adaaa46c2731be1dfb8f1819b3e67`

## Roadmap guardrail

Work must remain inside the current Phase 2 slice until its tests and evidence pass.

Allowed next work:

1. owner-scoped V4 project list API;
2. owner-scoped V4 project detail/source-map API;
3. safe serialization of document, page-role, issue, and segment metadata;
4. negative authorization, privacy, and feature-flag tests.

Explicitly out of scope for this slice:

- changing page roles or segment boundaries;
- teacher confirmation mutations;
- source-map UI;
- block detection;
- question extraction;
- answer/solution extraction;
- matching;
- publication;
- live private-fixture benchmarking.

Those remain in later roadmap phases.

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

This deferred item is not required for the current Phase 2 API slice and must not be confused with teacher-facing source-map APIs.

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

### Multi-PDF intake API — complete for this slice

Endpoint:

```text
POST /api/classes/exam-prep-v4/projects/
```

Verified behavior:

- teacher authentication is required;
- disabled V4 returns 404;
- accepts several multipart PDF files with one metadata record per file;
- prevalidates the whole batch before database or blob writes;
- creates one independent `ExamProject` and one `ExamSourceDocument` per PDF;
- identical SHA-256 values still create independent projects;
- validates organization membership and study-group teacher assignment;
- retries with the same identifiers and bytes reuse the project, document, and valid blob;
- retries restore a missing private blob;
- same identifiers with different bytes return an idempotency conflict;
- a ready classification is not regressed to uploading or dispatched again;
- broker dispatch failure preserves the private source for retry;
- retry after broker failure clears retryable failure state;
- validation errors use the repository-standard error envelope.

### Independent task dispatch — complete for this slice

- Every document receives a separate Celery signature.
- Tasks run on the `pipeline` queue.
- A per-document cache lock suppresses duplicate concurrent execution.
- Private source bytes are copied to a bounded temporary file.
- Missing source objects are persisted as observable failures.
- controlled source/revision/fingerprint conflicts do not corrupt accepted workflow state.
- transient provider failures use bounded Celery retry behavior.

## Focused CI evidence

Focused workflow:

- **Run:** `30776463102`
- **Job:** `91572774281`
- **Head:** `640b63e0031adaaa46c2731be1dfb8f1819b3e67`
- **Environment:** Python 3.12, PostgreSQL 16, Redis 7
- **Result:** success

```text
System check identified no issues (0 silenced).
No changes detected in app 'classes'.
94 passed, 13 warnings in 10.88s
```

The warnings only report that the CI checkout has no generated `backend/staticfiles/` directory while API/private-media negative tests construct Django handlers.

The immediately preceding focused run `30775372159` exposed two real integration defects:

1. the API test did not follow the repository-standard validation envelope;
2. a database filename whose private blob had been deleted was incorrectly treated as reusable.

Both were fixed before run `30776463102` passed.

## Full repository status

Focused V4 CI is authoritative for this slice and is green.
The full repository workflow is not claimed as fully green because unrelated baseline frontend failures have existed outside V4. No V4 frontend code is part of this slice.

## Not yet verified or implemented

- no live provider classification has run;
- the three private benchmark PDFs have not run through V4;
- real classifier latency, cost, and accuracy are unknown;
- no read-only V4 project list API exists yet;
- no read-only project detail/source-map API exists yet;
- no owner-scoped page thumbnail/content endpoint exists yet;
- no teacher source-map mutation or confirmation API exists;
- no V4 frontend exists;
- no block detector, extractor, matcher, exception review, projection, or publication path exists.

## Current slice acceptance criteria

The read-only source-map API slice is complete only when all of these are proven:

- a teacher can list only their own V4 projects;
- project detail returns the current document status, complete page-role map, issues, and segment proposals;
- another teacher receives 404 rather than existence leakage;
- inaccessible organization/study-group data is never returned;
- disabled V4 returns 404;
- source file names, storage keys, SHA-256 values, native text, model reasons, raw payloads, and private bytes are not exposed;
- page entries contain only review-safe structural metadata;
- segment entries are limited to the current classification revision;
- query count remains bounded for list and detail;
- focused PostgreSQL tests, system check, and migration drift check pass;
- this ledger is updated with exact evidence.

## Next verified step

Implement the smallest owner-scoped, read-only source-map API surface:

1. `GET /api/classes/exam-prep-v4/projects/` for the current teacher only;
2. `GET /api/classes/exam-prep-v4/projects/<project_id>/` for current revision metadata, pages, issues, and proposed segments;
3. strict privacy serialization with no private content or storage identifiers;
4. isolation, feature-flag, revision, response-shape, and query-count tests.

Do not implement Phase 3 mutations or Phase 4 block detection until this slice is green.