# Exam Prep V4 — Implementation Status Ledger

> Updated every V4 implementation turn. Full roadmap: `exam-prep-v4-source-aware-split-pipeline.md`.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **PR:** #4 (Draft)
- **Current phase:** Phase 3 — teacher source-map confirmation and virtual tools
- **Completed slice:** revision-safe source-map mutation and explicit confirmation backend
- **Next locked slice:** simple teacher-facing source-map UI using the verified backend contract
- **Phase 2 status:** 8/9; real three-PDF live-provider benchmark explicitly deferred by product owner on 2026-08-03
- **Validated Phase 3 code checkpoint:** `3e65e7391feec798b9e893dae5071d7ec7c2e988`
- **Focused evidence:** run `30780894549`, job `91585164044`, 150 tests passed

## Product-owner benchmark waiver

The product owner instructed development to continue without running the live Phase 2 benchmark now.

This remains an explicit waiver, not a successful gate:

- the privacy-safe benchmark harness remains available;
- real classifier accuracy, latency, and cost on the three private PDFs remain unmeasured;
- the deferred item receives no progress credit;
- Phase 3 proceeds against synthetic and contract-level evidence;
- the live benchmark must be reconsidered before rollout, production-default activation, or real-document extraction tuning.

## Progress calculation

Progress is based on the 77 explicit canonical-roadmap deliverables.

| Phase | Credited | Total | State |
|---|---:|---:|---|
| Phase 0 | 5 | 6 | Automated PR ledger enforcement remains open. |
| Phase 1 | 6 | 7 | Read-only Django admin inspection remains deferred. |
| Phase 2 | 8 | 9 | Live private-fixture benchmark deferred by product owner. |
| Phase 3 | 1 | 7 | Revision persistence and stale-state invalidation are complete; UI/tools remain. |
| Phases 4–10 | 0 | 48 | Not started. |

- **Entire V4 roadmap:** **20/77 = 26.0%**
- **Phase 2:** **8/9 = 88.9%**, with one deferred item
- **Phase 3:** **1/7 = 14.3%**

Only `Persist revisions and invalidate stale classification` receives Phase 3 credit. Backend support for role/boundary edits and ignore/rotation exists, but those deliverables remain in progress because the teacher UI and reorder behavior are not implemented.

## Verified Phase 3 backend

### Structural source-map fingerprint

A stable content-free SHA-256 contract now binds:

- schema version;
- page count;
- every one-based page number;
- effective role;
- orientation.

The fingerprint excludes PDF bytes, file hashes, filenames, text, images, object keys, classifier reasons, and model payloads.

### Complete-map mutation

```text
PUT /api/classes/exam-prep-v4/projects/<project_id>/documents/<document_id>/source-map/
```

Properties:

- owner-only with indistinguishable 404 for other teachers;
- requires `expectedRevision`;
- requires every document page exactly once;
- validates supported roles and orientations;
- rejects missing, duplicate, out-of-range, and stale maps without partial writes;
- preserves classifier prediction separately from teacher override;
- supports role changes, ignored role, and 0/90/180/270 orientation metadata;
- deterministically rebuilds contiguous segments;
- increments document and project revisions atomically;
- clears stale classifier fingerprint;
- invalidates prior confirmation and downstream review fingerprints;
- retains prior-revision segments as `superseded` audit history;
- retains a bounded pre-edit structural map history;
- treats exact no-op and immediate network retry as idempotent.

### Explicit confirmation

```text
POST /api/classes/exam-prep-v4/projects/<project_id>/documents/<document_id>/source-map/confirm/
```

Properties:

- binds confirmation to the exact current revision and source-map fingerprint;
- rejects stale revision and mismatched fingerprint with stable 409 codes;
- rejects unknown roles, missing segments, gaps, ordering errors, or incomplete coverage;
- confirms only current-revision segments;
- stores confirmer, confirmation time, revision, and fingerprint;
- is idempotent for an identical accepted confirmation;
- any later source-map edit invalidates confirmation;
- advances only to the `source_map_confirmed`/`segmenting` workflow boundary; no Phase 4 processing is started.

### Safe read contract

The existing project detail response now exposes only safe binding fields:

- `sourceMapFingerprint`;
- `hasSourceMap`;
- `isTeacherConfirmed`;
- `teacherConfirmedRevision`.

It still excludes filenames, storage keys, source hashes, native text, raw model metadata, classifier reasons, segment metadata, and error detail.

### Additive migration

Migration `classes.0041_exam_prep_v4_source_map_confirmation` adds:

- `source_map_fingerprint`;
- `teacher_confirmed_revision`;
- `teacher_confirmed_fingerprint`;
- database constraint for valid confirmed revisions.

## Test coverage added

Service and API tests verify:

- owner isolation and student denial;
- complete one-based maps;
- duplicate/missing page rejection;
- no-op idempotency;
- immediate retry idempotency;
- stale revision rejection;
- preservation of model predictions;
- role and orientation changes;
- deterministic segment reconstruction;
- old-segment supersession without deletion;
- correct pre-edit audit snapshot;
- full transaction rollback on persistence failure;
- exact revision/fingerprint confirmation;
- idempotent confirmation;
- unknown-role confirmation refusal;
- stale fingerprint/revision refusal;
- confirmation invalidation after edits;
- no private information in API responses.

## Latest focused CI evidence

- **Run:** `30780894549`
- **Job:** `91585164044`
- **Head:** `3e65e7391feec798b9e893dae5071d7ec7c2e988`
- **Environment:** Python 3.12, PostgreSQL 16, Redis 7

```text
System check identified no issues (0 silenced).
No changes detected in app 'classes'.
150 passed, 42 warnings in 12.74s
```

Warnings are limited to the known CI-only missing generated `backend/staticfiles/` warning. Focused V4 CI is green. The full repository is not claimed all-green because unrelated baseline frontend failures remain outside V4.

## Roadmap guardrail for the next slice

The next permitted slice is only the simple source-map UI that consumes the verified APIs.

It may include:

- RTL page thumbnail grid;
- effective/predicted role display;
- role selection;
- 90-degree rotation control;
- unsaved-change state;
- full-map save with revision conflict handling;
- explicit confirmation button bound to current fingerprint;
- accessible keyboard and screen-reader behavior.

Still out of scope:

- physical PDF rewriting;
- page reorder persistence;
- split/group actions;
- block detection;
- question or answer extraction;
- matching, projection, or publication.

## User action required

No user decision or input is required for the next UI slice. The deferred live benchmark remains a known product risk and can be resumed later.

## Next verified step

Implement only the simple RTL/accessibility-conscious teacher source-map UI over the verified revision-safe APIs. Do not start Phase 4 block detection until the Phase 3 UI and correction flow pass their own acceptance tests and this ledger is updated again.