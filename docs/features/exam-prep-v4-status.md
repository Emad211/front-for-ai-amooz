# Exam Prep V4 — Implementation Status Ledger

> Operational companion to `exam-prep-v4-source-aware-split-pipeline.md`.
> This file is updated in every implementation turn before moving to another roadmap slice.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **Draft PR:** #4
- **Current phase:** Phase 2 — upload and fast source classification
- **Completed slice:** Owner-scoped read-only source-map APIs
- **Next slice:** Owner-scoped private page-thumbnail delivery
- **State:** Intake, independent dispatch, source preparation, classification contracts, virtual split, and safe source-map reads are verified
- **Last updated:** 2026-08-03
- **Verified checkpoint:** `b22661d235824a28c014554cce577775915600ca`

## Roadmap guardrail

Work remains in Phase 2. The next implementation turn may add only the private page-thumbnail read path required to inspect a source map.

Allowed next work:

1. one owner-scoped thumbnail-content endpoint beneath a V4 project/document/page path;
2. feature-flag, teacher ownership, document ancestry, and page ancestry checks;
3. private storage streaming without exposing an object key or generated storage URL;
4. private cache headers, content type, content length when available, and download-safe disposition;
5. negative tests for another teacher, wrong project/document/page combinations, disabled V4, missing blob, and generic `/media/` denial;
6. bounded-query and no-content-leak tests;
7. update this ledger with exact CI evidence.

Explicitly out of scope for the next slice:

- full-resolution page delivery unless a later roadmap decision requires it;
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

This deferred item is not a prerequisite for the teacher source-map flow and remains explicitly tracked.

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

### Independent task dispatch — verified

- Every document receives a separate Celery signature.
- Tasks run on the `pipeline` queue.
- A per-document cache lock suppresses duplicate concurrent execution.
- Private source bytes are copied to a bounded temporary file.
- Missing source objects are persisted as observable failures.
- Controlled source/revision/fingerprint conflicts do not corrupt accepted workflow state.
- Transient provider failures use bounded Celery retry behavior.

### Read-only source-map APIs — verified

Endpoints:

```text
GET /api/classes/exam-prep-v4/projects/
GET /api/classes/exam-prep-v4/projects/<project_id>/
```

Verified list behavior:

- only projects owned by the authenticated teacher are returned;
- pagination uses the repository-wide page-number pagination contract;
- ordering is newest updated project first;
- each summary exposes only safe project metadata and document count;
- list execution is bounded to two database queries in the tested shape;
- organization IDs, study-group IDs, client request IDs, raw workflow state, and error details are absent.

Verified detail behavior:

- another teacher receives 404 rather than project-existence leakage;
- disabled V4 returns 404;
- current document status, classification revision, issue codes, complete page-role map, and proposed segments are returned;
- segment output is restricted to each document's current classification revision;
- page order and segment order are deterministic;
- teacher role override and effective role remain distinguishable;
- duplicate-page state is exposed only as a boolean;
- detail execution is bounded to four database queries in the tested populated shape;
- a project without documents returns an empty source map safely.

Privacy exclusions verified by adversarial response tests:

- original filenames;
- MIME/source object metadata;
- source, page, thumbnail, or render storage keys;
- source or page SHA-256 values;
- perceptual hashes;
- byte sizes;
- native-text samples and lengths;
- classifier reasons and printed-number raw metadata;
- raw classifier payloads;
- model names;
- classification and segment fingerprints;
- segment metadata and section keys;
- issue details and raw record indexes;
- project, document, or segment error details;
- organization and study-group identities.

Only review-safe structural fields cross the API boundary.

## Focused CI evidence

Latest focused workflow:

- **Run:** `30776737653`
- **Job:** `91573545689`
- **Head:** `b22661d235824a28c014554cce577775915600ca`
- **Environment:** Python 3.12, PostgreSQL 16, Redis 7
- **Result:** success

```text
System check identified no issues (0 silenced).
No changes detected in app 'classes'.
104 passed, 23 warnings in 9.40s
```

All warnings are the existing CI-only warning that `backend/staticfiles/` has not been generated when API/private-media tests initialize Django handlers. No V4 test failed.

Previous intake checkpoint:

- run `30776463102`;
- job `91572774281`;
- `94 passed, 13 warnings in 10.88s`.

The source-map slice added ten passing tests covering authentication, role permission, feature flag, owner isolation, privacy exclusions, current-revision filtering, deterministic ordering, empty maps, 404 behavior, and exact query bounds.

## Full repository status

Focused V4 CI is authoritative for this slice and is green.
The full repository workflow is not claimed as fully green because unrelated baseline frontend failures have existed outside V4. No V4 frontend code is present.

## Not yet verified or implemented

- no live provider classification has run;
- the three private benchmark PDFs have not run through V4;
- real classifier latency, cost, and accuracy are unknown;
- no owner-scoped thumbnail-content endpoint exists yet;
- no teacher source-map mutation or confirmation API exists;
- no V4 frontend exists;
- no block detector, extractor, matcher, exception review, projection, or publication path exists;
- Phase 2 exit gate on private fixtures has not been met.

## Next slice acceptance criteria

The private thumbnail slice is complete only when all of these are proven:

- the project, document, and page must all form one owner-scoped ancestry chain;
- another teacher receives 404;
- wrong project/document/page combinations receive 404;
- disabled V4 receives 404;
- missing private blobs fail without revealing storage details;
- the response streams bytes from private storage and never returns a storage URL or key;
- content type is `image/jpeg` for stored thumbnails;
- cache headers are private and do not authorize shared caches;
- generic `/media/exam-prep-v4/...` remains denied;
- query count is bounded;
- focused PostgreSQL tests, system check, and migration drift check pass;
- this ledger is updated with exact evidence.

## Next verified step

Implement only:

```text
GET /api/classes/exam-prep-v4/projects/<project_id>/documents/<document_id>/pages/<page_number>/thumbnail/
```

The endpoint must stream the existing private thumbnail after strict teacher/project/document/page ancestry validation. Do not add mutation, source confirmation, full-resolution delivery, Phase 3 UI, or Phase 4 block detection in the same slice.