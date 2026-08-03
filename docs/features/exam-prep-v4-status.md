# Exam Prep V4 — Implementation Status Ledger

> Updated every V4 implementation turn. Full roadmap: `exam-prep-v4-source-aware-split-pipeline.md`.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **PR:** #4 (Draft)
- **Current phase:** Phase 3 — teacher source-map confirmation and virtual tools
- **Completed slice:** simple RTL teacher Source Map UI over the revision-safe backend
- **Active slice:** virtual page-order metadata and accessible reorder flow
- **Phase 2 status:** 8/9; real three-PDF live-provider benchmark explicitly deferred by product owner on 2026-08-03
- **Latest fully validated checkpoint before this slice:** `1c18efb8472a7730e301f38be716fd84841897f7`
- **Latest focused workflow before this slice:** run `30803198166`
- **Last updated:** 2026-08-03

## Progress before this slice

Progress is based on the 77 explicit canonical-roadmap deliverables.

| Phase | Credited | Total | State |
|---|---:|---:|---|
| Phase 0 | 5 | 6 | Automated PR ledger enforcement remains open. |
| Phase 1 | 6 | 7 | Read-only Django admin inspection remains deferred. |
| Phase 2 | 8 | 9 | Live private-fixture benchmark deferred. |
| Phase 3 | 3 | 7 | Simple UI, role/boundary correction, and revision/invalidation are complete. |
| Phases 4–10 | 0 | 48 | Not started. |

- **Entire V4 roadmap:** **22/77 = 28.6%**
- **Phase 3:** **3/7 = 42.9%**

No new credit is recorded until virtual reorder is persisted end to end and both backend and frontend gates pass.

## Product-owner benchmark waiver

The live Phase 2 benchmark remains deferred by explicit product-owner instruction. It is not counted as passed and receives no progress credit. Real classifier accuracy, latency, and cost on the three private PDFs remain unknown and must be reconsidered before rollout, production-default activation, or real-document extraction tuning.

## Locked architectural decision for this slice

`pageNumber` remains the immutable physical/evidence identity of the page inside the original PDF.

A separate one-based `displayOrder` becomes the mutable virtual processing order.

```text
physical identity: pageNumber
virtual processing/display order: displayOrder
```

Reordering must never:

- rewrite the PDF;
- renumber source-page evidence;
- change thumbnail/source object identity;
- change duplicate-page ancestry;
- move a page across documents or projects;
- delete prior order history.

## Allowed work for this turn

1. add `display_order` to `ExamSourcePage` through an additive migration;
2. backfill existing rows with `display_order = page_number` before enforcing non-null and uniqueness;
3. enforce one unique positive display order per document;
4. expose safe `displayOrder` through the current source-map detail serializer;
5. require every complete-map mutation row to include `displayOrder`;
6. reject missing, duplicate, non-contiguous, out-of-range, or cross-page order values before writes;
7. include display order in the structural Source Map fingerprint;
8. order structural snapshots and current-page maps by display order while retaining physical page numbers;
9. rebuild deterministic segments in virtual order;
10. retain prior-revision segments and pre-edit virtual-order history;
11. invalidate previous confirmation and stale fingerprints after a reorder;
12. make exact no-op and immediate retry idempotent;
13. add accessible Move Earlier and Move Later controls in the existing page cards;
14. render cards in virtual order while continuing to label them by immutable source page number;
15. disable impossible first/last moves;
16. keep all page changes local until explicit complete-map Save;
17. preserve stale-conflict behavior and local drafts;
18. add PostgreSQL constraints/migration tests, mutation/API tests, pure state tests, and focused TypeScript checks;
19. update this ledger and canonical roadmap with exact evidence.

## Explicitly out of scope

- physical PDF rewriting or regenerated PDFs;
- drag-and-drop reorder;
- split-into-separate-exams;
- grouping documents;
- cross-document page movement;
- block detection;
- question extraction;
- answer/solution extraction;
- matching, projection, publication, or rollout;
- claiming browser-level accessibility completion unless browser interaction tests are actually added and run.

## Acceptance criteria

### Database and migration

- existing pages receive `display_order = page_number`;
- the field is positive and non-null after migration;
- `(document, display_order)` is unique;
- fresh PostgreSQL migration and drift checks pass;
- physical `page_number` uniqueness and semantics remain unchanged.

### Mutation and fingerprinting

- every source page appears exactly once by immutable `pageNumber`;
- every display position from 1 through page count appears exactly once;
- page number and display order may differ;
- fingerprint changes on reorder even if roles and rotations do not;
- no-op complete maps do not create revisions;
- accepted reorder increments document/project revision exactly once;
- immediate retry reuses the accepted revision;
- prior confirmation is cleared;
- prior segment revision remains available as superseded audit history;
- rollback restores all page order, revision, confirmation, segment, and fingerprint state.

### Segments

- pages are grouped by adjacent effective roles in virtual order;
- segment `startPage` and `endPage` continue to identify immutable source page numbers at the virtual segment boundaries;
- segment `order` follows virtual sequence;
- non-contiguous physical page numbers are valid inside a virtual segment;
- no segment may cross document/project boundaries.

### Frontend

- cards render by `displayOrder` but visibly retain `pageNumber`;
- Move Earlier/Move Later are keyboard-accessible buttons with page-specific labels;
- first page cannot move earlier and last page cannot move later;
- reorder is local and dirty until Save;
- role, rotation, and reorder can be saved in one complete-map request;
- Discard restores server order;
- stale conflict preserves local order;
- screen-reader announcements mention source page and new virtual position;
- no drag-only interaction is required;
- private source metadata remains absent from rendered output.

## User action required

No user input or product decision is required for this slice. The implementation will use explicit non-drag controls first because they are deterministic, keyboard-accessible, easier to audit, and do not force a new interaction dependency.

## Next verified step

Implement only virtual page-order metadata and accessible reorder controls under the existing complete-map revision/fingerprint contract. Do not begin split/group actions or Phase 4 block detection.