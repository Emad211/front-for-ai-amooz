# Exam Prep V4 — Implementation Status Ledger

> Updated every V4 implementation turn. Full roadmap: `exam-prep-v4-source-aware-split-pipeline.md`.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **PR:** #4 (Draft)
- **Current phase:** Phase 3 — teacher source-map confirmation and virtual tools
- **Completed slice:** simple RTL teacher Source Map UI over the revision-safe backend
- **Next locked slice:** virtual page-order metadata and reorder flow; no physical PDF rewriting
- **Phase 2 status:** 8/9; real three-PDF live-provider benchmark explicitly deferred by product owner on 2026-08-03
- **Validated code checkpoint:** `49e485e5b71694b85c9051e1c7b33ea17ee4eea8`
- **Focused workflow:** run `30802787492`
- **Backend job:** `91651046345`
- **Frontend job:** `91651046449`
- **Last updated:** 2026-08-03

## Product-owner benchmark waiver

The live Phase 2 benchmark remains deferred by explicit product-owner instruction. It is not counted as passed and receives no progress credit. Real classifier accuracy, latency, and cost on the three private PDFs remain unknown and must be reconsidered before rollout, production-default activation, or real-document extraction tuning.

## Progress calculation

Progress is based on the 77 explicit canonical-roadmap deliverables.

| Phase | Credited | Total | State |
|---|---:|---:|---|
| Phase 0 | 5 | 6 | Automated PR ledger enforcement remains open. |
| Phase 1 | 6 | 7 | Read-only Django admin inspection remains deferred. |
| Phase 2 | 8 | 9 | Live private-fixture benchmark deferred. |
| Phase 3 | 3 | 7 | Simple UI, role/boundary correction, and revision/invalidation are complete. |
| Phases 4–10 | 0 | 48 | Not started. |

- **Entire V4 roadmap:** **22/77 = 28.6%**
- **Phase 2:** **8/9 = 88.9%**, with one deferred item
- **Phase 3:** **3/7 = 42.9%**

New credit in this slice:

1. `Build simple source-map UI` is complete.
2. `Support boundary changes and role changes` is complete: changing complete per-page roles rebuilds deterministic contiguous segment boundaries through the verified backend contract.

`Support ignore, rotate, and reorder metadata` remains in progress. Ignore and rotation are implemented end to end, but virtual reorder metadata is not yet implemented, so this deliverable receives no credit. `Accessibility and RTL tests` also remains open because this slice has focused type and state-model tests, not browser-level interaction/accessibility coverage.

## Verified teacher routes

```text
/teacher/exam-prep-v4
/teacher/exam-prep-v4/<projectId>
```

The V4 entry is available in both freelancer-teacher and organization-teacher navigation menus.

## Verified frontend architecture

### Centralized service layer

`frontend/src/services/exam-prep-v4-service.ts` owns all V4 frontend network traffic:

- paginated project list;
- owner-scoped project detail;
- complete-map mutation;
- exact revision/fingerprint confirmation;
- authenticated private thumbnail retrieval;
- access-token refresh;
- stable conflict-code extraction.

No V4 component performs an ad-hoc `fetch`.

### Source-map state model

`frontend/src/features/exam-prep-v4/source-map-model.ts` provides pure functions for:

- complete one-based map construction;
- page-order normalization;
- role updates;
- 90-degree orientation cycling;
- dirty-state comparison;
- unknown-page counting;
- complete mutation payload generation;
- confirmation eligibility.

Every save payload contains every page exactly once in source-page order.

### Revision-safe hook

`use-exam-prep-v4-source-map.ts` manages:

- project/document loading;
- selected document;
- initial and local draft maps;
- explicit role/rotation changes;
- unsaved-change tracking;
- browser refresh/close warning;
- full-map save;
- stale revision and fingerprint conflicts without discarding local edits;
- explicit server-map reload;
- exact revision/fingerprint confirmation;
- confirmation blocking for dirty, unknown, missing-fingerprint, busy, or already-confirmed states;
- screen-reader announcements.

### Private thumbnails

`use-exam-prep-v4-thumbnail.ts` retrieves the owner-scoped private JPEG as an authenticated Blob, creates a temporary object URL, aborts stale requests, and revokes the URL during cleanup. Storage URLs and object keys never enter component props or rendered markup.

## Verified UI behavior

### Project list

- loading, empty, error, ready, and paginated states;
- status and progress display;
- one card per independent V4 project;
- direct route to Source Map review;
- no upload, extraction, matching, or publication action added.

### Source Map editor

- global RTL layout with logically increasing page numbers;
- responsive grid: one column on mobile, two on small screens, three on extra-large screens, and four on very large screens;
- dark-mode-compatible semantic tokens;
- private thumbnail cards;
- separate predicted role/confidence, teacher override, and local effective role display;
- all seven source roles;
- 90-degree rotation control;
- duplicate-page indicator;
- unresolved-unknown warning;
- explicit dirty state;
- explicit Save, Discard, and Confirm actions;
- no server mutation before Save;
- stale-conflict warning that preserves local edits;
- optional reload of the current server map;
- confirmation dialog bound to the currently loaded revision/fingerprint;
- document-switch warning when local edits exist;
- `beforeunload` warning for refresh/close with local edits;
- no Phase 4 processing triggered after confirmation.

### Accessibility-oriented implementation

- semantic headings and grouped page cards;
- visible `focus-within` treatment;
- explicit labels and descriptions for role selectors;
- page-specific rotate-button labels including current orientation;
- `aria-live` state announcements;
- loading `aria-busy` state;
- minimum 44px-style action/control heights through `h-11`;
- keyboard-reachable native/Radix controls;
- reduced-motion variants for transitions and spinners;
- screen-reader-only confirmation help.

These implementation properties are present and typechecked, but browser-level keyboard, screen-reader, contrast, and RTL interaction tests are still required before the roadmap accessibility-test item can be credited.

## Focused test evidence

### Backend

- **Job:** `91651046345`
- **Environment:** Python 3.12, PostgreSQL 16, Redis 7

```text
System check identified no issues (0 silenced).
No changes detected in app 'classes'.
150 passed, 42 warnings in 13.28s
```

Warnings are limited to the known CI-only missing generated `backend/staticfiles/` directory warning.

### Frontend

- **Job:** `91651046449`
- **Environment:** Node.js 22
- focused TypeScript check: passed;
- six native source-map state-model tests: passed;
- failed tests: 0.

The six tests cover complete/sorted maps, incomplete or duplicate maps, immutable dirty/revert behavior, the full rotation cycle, ordered complete save payloads, and confirmation gating.

The native Node runner emits a non-failing module-type warning because the existing frontend package does not declare `type: module`. Changing the package module mode was intentionally avoided because it would affect the whole application rather than this isolated slice.

`npm ci` also reports existing repository dependency-audit findings. They were not introduced or modified by this V4 slice and are not treated as a passing security audit.

## What is not claimed

- no browser/E2E execution of the new page has been recorded;
- no visual-regression run has been recorded;
- no automated screen-reader, keyboard-flow, contrast, or RTL browser test has been recorded;
- no virtual page reorder exists;
- no physical PDF rewriting exists;
- no split/group action exists;
- no block detection, extraction, matching, projection, or publication work has started;
- the full repository is not claimed all-green because unrelated baseline frontend failures remain outside V4;
- the deferred real benchmark remains unmeasured.

## Roadmap guardrail for the next slice

The next permitted slice is only virtual page-order metadata and its revision-safe teacher flow.

It may include:

1. preserve immutable source `pageNumber` as evidence identity;
2. add a separate one-based virtual `displayOrder` contract;
3. bind structural fingerprinting and deterministic segment order to the virtual order without changing private PDF bytes;
4. validate a complete unique virtual order for every page;
5. retain old-order audit history and invalidate confirmation on reorder;
6. expose revision-safe reorder through the existing complete-map mutation endpoint;
7. add accessible non-drag controls such as Move Earlier/Move Later before considering optional drag-and-drop;
8. retain local edits and stale-conflict handling;
9. add PostgreSQL, pure-state, focused typecheck, RTL, and keyboard-order tests;
10. update this ledger and canonical roadmap with exact evidence.

Still out of scope:

- rewriting or generating a reordered PDF;
- split-into-separate-exams;
- grouping documents;
- block detection;
- question/answer extraction;
- matching, projection, publication, or rollout.

## User action required

No user decision or input is required for the next virtual reorder slice. The deferred live benchmark remains an explicit product risk.

## Next verified step

Implement only virtual page-order metadata and accessible reorder controls while preserving immutable source-page identity and all revision/fingerprint guarantees. Do not begin split/group actions or Phase 4 block detection.