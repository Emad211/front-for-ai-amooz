# Exam Prep V4 — Implementation Status Ledger

> Updated every V4 implementation turn. Full roadmap: `exam-prep-v4-source-aware-split-pipeline.md`.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **PR:** #4 (Draft)
- **Current phase:** Phase 3 — teacher source-map confirmation and virtual tools
- **Completed slice:** revision-safe source-map mutation and explicit confirmation backend
- **Active slice:** simple RTL and accessibility-conscious teacher source-map UI
- **Phase 2 status:** 8/9; real three-PDF live-provider benchmark explicitly deferred by product owner on 2026-08-03
- **Validated backend checkpoint:** `3e65e7391feec798b9e893dae5071d7ec7c2e988`
- **Latest focused backend evidence:** run `30780894549`, job `91585164044`, 150 tests passed
- **Current branch head before UI implementation:** `e2640243067a32b806200a3a91fc85716d4cd531`
- **Last updated:** 2026-08-03

## Product-owner benchmark waiver

The live Phase 2 benchmark remains deferred by explicit product-owner instruction. It is not counted as passed and receives no progress credit. Real classifier accuracy, latency, and cost on the three private PDFs remain unknown and must be reconsidered before rollout, production-default activation, or real-document extraction tuning.

## Progress before this UI slice

Progress is based on the 77 explicit canonical-roadmap deliverables.

| Phase | Credited | Total | State |
|---|---:|---:|---|
| Phase 0 | 5 | 6 | Automated PR ledger enforcement remains open. |
| Phase 1 | 6 | 7 | Read-only Django admin inspection remains deferred. |
| Phase 2 | 8 | 9 | Live private-fixture benchmark deferred. |
| Phase 3 | 1 | 7 | Revision persistence and stale-state invalidation are complete. |
| Phases 4–10 | 0 | 48 | Not started. |

- **Entire V4 roadmap:** **20/77 = 26.0%**
- **Phase 3:** **1/7 = 14.3%**

No UI credit is recorded until the teacher flow is implemented and its frontend acceptance gates pass.

## Verified backend contract consumed by this slice

### Read APIs

```text
GET /api/classes/exam-prep-v4/projects/
GET /api/classes/exam-prep-v4/projects/<project_id>/
GET /api/classes/exam-prep-v4/projects/<project_id>/documents/<document_id>/pages/<page_number>/thumbnail/
```

### Mutation and confirmation APIs

```text
PUT  /api/classes/exam-prep-v4/projects/<project_id>/documents/<document_id>/source-map/
POST /api/classes/exam-prep-v4/projects/<project_id>/documents/<document_id>/source-map/confirm/
```

Mutation requires a complete page map and `expectedRevision`. Confirmation requires the exact current revision and structural `sourceMapFingerprint`. Stale requests are rejected without partial writes.

## Roadmap scope for this turn

Only the simple teacher-facing Source Map UI is allowed:

1. add a teacher route reachable from the existing teacher workflow;
2. fetch one owned V4 project and its current document/page map;
3. render an RTL thumbnail grid with responsive breakpoint-specific layouts rather than a scaled desktop layout;
4. show predicted role, effective role, teacher override, orientation, issue state, and confirmation state without exposing private source identifiers;
5. support role selection for all defined source roles;
6. support 90-degree rotation steps through the existing orientation metadata contract;
7. retain a complete local page map and track unsaved changes;
8. save the complete map through the revision-safe PUT endpoint;
9. handle `stale_source_map` and fingerprint conflicts by preserving local edits, warning the teacher, and offering a reload of the current server map;
10. confirm only the current saved revision/fingerprint through the explicit confirmation endpoint;
11. disable confirmation when unsaved changes or unresolved `unknown` roles exist;
12. preserve keyboard navigation, visible focus, meaningful labels, screen-reader status announcements, touch targets, reduced-motion behavior, RTL alignment, dark mode, and semantic design tokens;
13. use shared components and the existing API/auth infrastructure;
14. add focused unit/component tests and include the new frontend files in the V4 CI path gate;
15. update this ledger and the canonical roadmap with exact frontend and backend evidence.

Explicitly out of scope:

- physical PDF rewriting;
- page reorder persistence;
- drag-and-drop reorder;
- split-into-separate-exams action;
- group-documents action;
- full-resolution PDF/page delivery;
- block detection;
- question extraction;
- answer/solution extraction;
- matching, projection, or publication.

## UI acceptance criteria

- another teacher cannot reach or infer another project through the UI or API;
- loading, empty, failed, ready, dirty, saving, stale, confirming, and confirmed states are distinct;
- all pages remain represented exactly once in the save payload;
- prediction and teacher override are visually distinct;
- role changes and rotations never mutate the server before explicit save;
- leaving or refreshing with unsaved changes produces a warning;
- stale save responses never silently overwrite server changes;
- confirmation cannot run with dirty state, missing fingerprint, unresolved unknown pages, or a non-current revision;
- successful save updates revision/fingerprint from the returned safe source map;
- successful confirmation updates the UI without starting Phase 4 work;
- keyboard-only users can reach every page control and action;
- screen readers receive page number, role, rotation, save state, errors, and confirmation results;
- RTL ordering is correct while page numbers remain logically increasing;
- mobile, tablet, and desktop layouts are breakpoint-specific;
- dark mode and reduced motion remain usable;
- no filename, storage key, source hash, native text, model payload, classifier reason, or private error detail is rendered or logged;
- existing frontend baseline failures are separated from V4-caused failures.

## User action required

No user input or product decision is required for this UI slice. Existing preferences are treated as binding: shared components, semantic tokens, RTL, dark mode, breakpoint-specific responsive layouts, interactive state changes, keyboard accessibility, adequate touch targets, and reduced-motion support.

## Next verified step

Inspect the existing teacher frontend architecture and implement only the Source Map UI over the verified backend APIs. Do not begin reorder, split/group actions, Phase 4 block detection, or extraction.