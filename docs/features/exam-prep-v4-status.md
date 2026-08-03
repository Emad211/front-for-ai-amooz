# Exam Prep V4 — Implementation Status Ledger

> Operational companion to `exam-prep-v4-source-aware-split-pipeline.md`.
> This file is updated in every implementation turn before moving to another roadmap slice.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **Draft PR:** #4
- **Current phase:** Phase 2 — upload and fast source classification
- **Completed slice:** Owner-scoped private page-thumbnail delivery
- **Next slice:** Private benchmark harness for the Phase 2 exit gate
- **State:** Thumbnail delivery is verified; Phase 3 and Phase 4 have not started
- **Last updated:** 2026-08-03
- **Verified checkpoint:** `8f38978266f55955a76ed2b4185b19ad74ac78e0`

## Overall progress calculation

Progress is calculated from the 77 explicit checklist deliverables in the canonical roadmap, not from commit count, changed files, test count, or lines of code.

| Phase | Credited deliverables | Total deliverables | State |
|---|---:|---:|---|
| Phase 0 | 5 | 6 | Architecture and benchmark contract exist; PR-level living-document enforcement remains open. |
| Phase 1 | 6 | 7 | Models, migration, isolation and constraints are verified; read-only Django admin inspection remains deferred. |
| Phase 2 | 8 | 9 | Intake, preparation, classification contracts, virtual split and source-map delivery exist; the live private-fixture exit gate remains open. |
| Phases 3–10 | 0 | 55 | Not started by design. |

**Credited total: 19 / 77 = 24.7%.**

Therefore:

- **Entire V4 roadmap:** **24.7% complete**.
- **Current Phase 2 checklist:** **88.9% complete** (`8 / 9`).

Closing the thumbnail endpoint does not increase the canonical total because it is a security-critical sub-deliverable of the already credited Phase 2 source-map API item. Recording a higher overall percentage here would double-count the same roadmap deliverable.

The remaining work is still substantial: teacher correction, block detection, question extraction, answer-plus-solution extraction, deterministic matching, exception review, projection/publication, lifecycle hardening and controlled rollout are all later phases.

## Roadmap guardrail

The implementation must remain in Phase 2 until its private-fixture exit gate is measured and recorded.

The next slice may implement only a private benchmark harness that:

1. accepts each private PDF as an independent exam;
2. runs source preparation and fast page-role classification without committing source content;
3. records only aggregate page-role/segment metrics, latency, provider usage and warm-rerun reuse;
4. verifies the three documented structural patterns;
5. verifies that an unchanged accepted warm rerun performs zero provider calls;
6. supports a dry-run/fake-provider mode for CI;
7. fails closed when fixtures, model configuration or credentials are absent;
8. updates the benchmark runbook and this ledger with exact evidence.

Explicitly out of scope for the next slice:

- source-map mutations or confirmation;
- frontend UI;
- full-resolution page delivery;
- block detection;
- question extraction;
- answer/solution extraction;
- matching or publication;
- claims about private-fixture accuracy without a real recorded run.

## Verified baseline

- Phase 0 architecture and private benchmark contracts exist.
- The three supplied private PDFs are independent exams.
- No private PDF, page image, native text, OCR text, answer, or solution content is committed.
- Existing V1/V2/V3 API, task, artifact and publication behavior remains untouched.
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

## Phase 2 — verified implementation

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

### Multi-PDF intake and independent tasks

```text
POST /api/classes/exam-prep-v4/projects/
```

- accepts several PDFs while creating one independent project per PDF;
- prevalidates the whole batch before writes;
- preserves idempotency and restores missing private blobs;
- dispatches one independent task per source document;
- validates owner, organization, and study-group scope;
- preserves private sources across broker failures.

### Read-only source-map APIs

```text
GET /api/classes/exam-prep-v4/projects/
GET /api/classes/exam-prep-v4/projects/<project_id>/
```

- list and detail are owner-scoped;
- another teacher receives 404;
- current-revision pages and segments are returned in deterministic order;
- private filenames, object keys, hashes, native text, raw model metadata, fingerprints, error details, and organization identities are excluded;
- list and detail query counts are bounded.

### Private page-thumbnail delivery — verified

```text
GET /api/classes/exam-prep-v4/projects/<project_id>/documents/<document_id>/pages/<page_number>/thumbnail/
```

Verified behavior:

- authentication and teacher role are required;
- disabled V4 returns 404;
- project, document and page ancestry plus teacher ownership are resolved in one database query;
- another teacher receives 404 before private storage is touched;
- mixed project/document/page identifiers return 404;
- missing page metadata, missing filename, missing object and storage failure are all indistinguishable 404 responses;
- the endpoint opens only the storage bound to the private thumbnail field;
- legacy/default-storage fallback is explicitly forbidden;
- bytes are streamed as `image/jpeg`;
- `Content-Disposition` uses only the synthetic name `page-<number>.jpg`;
- private object names and storage keys do not enter body or headers;
- the response uses `private, no-store, max-age=0`, `Pragma: no-cache`, `Expires: 0`, and varies on authorization/cookie;
- `nosniff`, same-origin resource policy, and no-referrer headers are present;
- the generic `/media/exam-prep-v4/...` path remains denied.

## Focused CI evidence

Latest successful focused workflow:

- **Run:** `30777631820`
- **Job:** `91576032877`
- **Head:** `8f38978266f55955a76ed2b4185b19ad74ac78e0`
- **Environment:** Python 3.12, PostgreSQL 16, Redis 7
- **Result:** success

```text
System check identified no issues (0 silenced).
No changes detected in app 'classes'.
114 passed, 33 warnings in 9.02s
```

All warnings are the existing CI-only warning that `backend/staticfiles/` has not been generated while API/private-media tests initialize Django handlers.

The immediately preceding focused run `30777540171` failed with `113 passed, 1 failed`. The failure was in the test harness: creation of the outsider user occurred inside an exact one-query assertion and contributed three setup queries. The user fixture was moved outside the measured block. The endpoint itself already returned 404 without opening storage. The corrected head then passed all 114 tests.

## Full repository status

Focused V4 CI is authoritative for this slice and is green.
The full repository workflow is not claimed as all-green because unrelated baseline frontend failures exist outside V4. No V4 frontend code is present.

## Not yet verified or implemented

- no live provider classification benchmark has run;
- the three private benchmark PDFs have not been processed by V4 in a recorded benchmark;
- real classifier latency, cost and page-role accuracy remain unknown;
- no teacher source-map mutation or confirmation API exists;
- no V4 frontend exists;
- no block detector, extractor, matcher, exception review, projection or publication path exists;
- Phase 2 exit gate has not yet been met.

## Next slice acceptance criteria

The private benchmark-harness slice is complete only when:

- a management command or equivalent isolated runner accepts three independent private fixture paths;
- fixture bytes, filenames, page images, text and model payloads are never committed or printed;
- each fixture remains a separate project/document scope;
- dry-run CI tests cover expected structural patterns and aggregate output shape;
- cold-run latency, page counts, role counts, segment counts, issue counts and provider usage can be recorded;
- warm reruns verify zero provider calls for unchanged accepted classifications;
- missing configuration and missing fixtures fail clearly without partial benchmark claims;
- aggregate results are written to `docs/runbooks/exam-prep-v4-benchmark.md` only after a real run;
- focused PostgreSQL checks remain green;
- this ledger is updated with exact evidence and recalculated progress.

## Next verified step

Implement only the Phase 2 private benchmark harness and its fake-provider/CI tests. Do not begin Phase 3 teacher mutations or Phase 4 block detection until the Phase 2 exit gate is measured and recorded.
