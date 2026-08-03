# Exam Prep V4 — Implementation Status Ledger

> Updated every V4 implementation turn. Full roadmap: `exam-prep-v4-source-aware-split-pipeline.md`.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **PR:** #4 (Draft)
- **Current phase:** Phase 3 — teacher source-map confirmation and virtual tools
- **Completed slice:** virtual page-order metadata and accessible reorder flow
- **Next locked slice:** focused browser-level RTL, keyboard, and accessibility interaction tests for the existing Source Map UI
- **Phase 2 status:** 8/9; real three-PDF live-provider benchmark explicitly deferred by product owner on 2026-08-03
- **Validated code checkpoint:** `eb071778d3c2fba460a1e2da14e4e8587a675646`
- **Focused workflow:** run `30809570611`
- **Backend job:** `91672836979`
- **Frontend job:** `91672836921`
- **Last updated:** 2026-08-03

## Progress calculation

Progress is based on the 77 explicit canonical-roadmap deliverables.

| Phase | Credited | Total | State |
|---|---:|---:|---|
| Phase 0 | 5 | 6 | Automated PR ledger enforcement remains open. |
| Phase 1 | 6 | 7 | Read-only Django admin inspection remains deferred. |
| Phase 2 | 8 | 9 | Live private-fixture benchmark deferred under an explicit product-owner waiver. |
| Phase 3 | 4 | 7 | Simple UI, role/boundary correction, ignore/rotation/reorder, and revision invalidation are complete. |
| Phases 4–10 | 0 | 48 | Not started. |

- **Entire V4 roadmap:** **23/77 = 29.9%**
- **Phase 2:** **8/9 = 88.9%**, with one deferred item
- **Phase 3:** **4/7 = 57.1%**

New credit in this slice:

- `Support ignore, rotate, and reorder metadata` is now complete end to end.

The accessibility/RTL roadmap item remains in progress. The implementation uses semantic controls, page-specific labels, visible focus, RTL layout, screen-reader announcements, and non-drag keyboard-accessible reorder buttons; however, no browser-level keyboard, RTL, contrast, or accessibility interaction run has yet been recorded.

## Product-owner benchmark waiver

The live Phase 2 benchmark remains deferred by explicit product-owner instruction. It is not counted as passed and receives no progress credit. Real classifier accuracy, latency, and cost on the three private PDFs remain unknown and must be reconsidered before rollout, production-default activation, or real-document extraction tuning.

## Locked page-identity contract

Virtual reordering never changes physical source evidence:

```text
immutable physical identity: pageNumber
mutable virtual position:    displayOrder
```

Verified guarantees:

- the original PDF is never rewritten;
- page numbers, page rows, thumbnails, hashes, and duplicate ancestry retain their physical identity;
- each document has exactly one positive, unique display position per page;
- every accepted map contains all physical page numbers and every virtual position from 1 through page count exactly once;
- virtual order cannot cross document or project boundaries;
- fingerprint schema version 2 includes `displayOrder`, role, orientation, page count, and immutable page number;
- reorder-only changes create a new revision and fingerprint;
- exact no-op maps do not create revisions;
- immediate network retries reuse the accepted revision;
- prior confirmation, review binding, and stale classification fingerprints are invalidated after reorder;
- prior segment revisions and pre-edit page-order maps remain available as bounded audit history.

## Additive database migration

Migration:

```text
classes.0042_exam_prep_v4_virtual_page_order
```

It performs the following sequence:

1. adds nullable `ExamSourcePage.display_order`;
2. backfills existing rows with `display_order = page_number`;
3. recalculates schema-v2 structural fingerprints;
4. transfers valid current confirmation to the recalculated fingerprint;
5. enriches current segment metadata with safe physical page sequence and virtual order bounds;
6. makes the field non-null;
7. enforces uniqueness on `(document, display_order)`;
8. enforces `display_order >= 1`;
9. adds the document/order index;
10. removes the obsolete physical ascending-boundary constraint from virtual segments.

Physical `page_number` uniqueness and meaning remain unchanged.

## Revision-safe mutation behavior

The existing complete-map endpoint now requires this for every page:

```json
{
  "pageNumber": 3,
  "displayOrder": 2,
  "role": "questions",
  "orientation": 0
}
```

The mutation service:

- validates complete and unique physical and virtual sequences before writes;
- uses a transaction-safe temporary order range before writing swapped final orders, avoiding unique-constraint collisions;
- changes only `display_order`, teacher role, and orientation on existing page rows;
- preserves classifier predictions and immutable page IDs;
- rebuilds segments from pages adjacent in virtual order;
- permits segment boundary pages such as `startPage=3`, `endPage=2` when the virtual segment sequence is `[3,2]`;
- records `pageNumbers`, `displayOrderStart`, `displayOrderEnd`, and `physicalContiguous` in private segment metadata;
- retains old segments as `superseded` rather than deleting them;
- rolls back page order, roles, orientation, revisions, segment state, confirmation state, and fingerprints together on failure.

## Safe read contract

Owner-scoped Source Map detail now exposes:

- `pageNumber` — immutable physical source identity;
- `displayOrder` — current virtual position;
- current pages ordered by display order;
- safe segment `displayOrderStart` and `displayOrderEnd`;
- safe segment `pageNumbers` sequence.

It still excludes filenames, object keys, source hashes, native/OCR text, raw segment metadata, prompts, model payloads, classifier reasons, private error details, and internal fingerprints other than the explicit structural binding required for confirmation.

## Frontend reorder behavior

### State model

The pure Source Map model now:

- carries `displayOrder` with each editable page;
- validates complete physical and virtual one-based sequences;
- compares dirty state by immutable page number while including virtual order;
- sorts cards and mutation payloads by virtual order;
- swaps only two adjacent display positions for Move Earlier/Move Later;
- never changes `pageNumber`;
- rejects impossible first/last movement as a no-op;
- blocks confirmation while local order differs from the saved server map.

### Teacher UI

Each page card now displays both:

- `صفحهٔ منبع N` — immutable physical identity;
- `جایگاه مجازی X` — editable processing position.

Accessible controls:

- `زودتر` / Move Earlier;
- `دیرتر` / Move Later;
- first and last impossible moves are disabled;
- controls have page-specific labels containing source page and current virtual position;
- no drag-and-drop is required;
- screen-reader announcements report the physical page and its new virtual position;
- cards are rendered in virtual DOM order while thumbnail requests remain keyed by physical page number;
- role, rotation, and reorder are saved together through one complete-map request;
- Discard restores the server order;
- stale conflicts preserve the local order until the teacher explicitly reloads the server version;
- confirmation binds to the saved schema-v2 fingerprint including virtual order.

The UI explicitly states that no PDF is regenerated or rewritten.

## Focused verification evidence

### Backend

- **Job:** `91672836979`
- **Environment:** Python 3.12, PostgreSQL 16, Redis 7

```text
System check identified no issues (0 silenced).
No changes detected in app 'classes'.
165 passed, 44 warnings in 14.07s
```

Coverage added includes:

- migration backfill and confirmation fingerprint preservation;
- unique/positive order database constraints;
- descending physical segment boundaries for virtual segments;
- classifier preservation of existing virtual order;
- reorder-only fingerprint changes;
- immutable page row identity;
- virtual segment reconstruction;
- confirmation after reorder;
- idempotent immediate retry;
- stale revision refusal;
- invalid or duplicate display-order rejection;
- full transactional rollback;
- safe read ordering and safe segment page sequences.

Warnings are limited to the known CI-only missing generated `backend/staticfiles/` directory warning.

### Frontend

- **Job:** `91672836921`
- **Environment:** Node.js 22

```text
Focused TypeScript check: passed
Source-map state-model tests: 8 passed, 0 failed
```

The eight tests cover virtual sorting, physical/virtual completeness, dirty/revert behavior, rotation, adjacent reorder with immutable page identity, first/last movement boundaries, complete ordered mutation payloads, and confirmation gating after reorder.

The native Node runner emits the existing non-failing module-type warning. `npm ci` also reports existing repository dependency-audit findings; this slice does not claim a repository-wide dependency security audit.

## Failed gates encountered and resolved

The first backend run exposed six slice-local incompatibilities:

- a classification fixture with an incomplete pre-rendered page map;
- two tests still assuming physically ascending segment boundaries;
- one wrapped serializer-error assertion;
- one constraint test masked by model fallback;
- one historical-user migration fixture mismatch.

A second run isolated the historical migration fixture. All were corrected without weakening the virtual-order contract. No frontend reorder work began until migration, constraints, mutation, and confirmation passed on PostgreSQL.

## What is not claimed

- no physical PDF rewriting or reordered PDF generation exists;
- no cross-document page movement exists;
- no drag-and-drop interaction exists or is required;
- no browser/E2E, visual-regression, contrast, screen-reader, or full keyboard-flow run is recorded yet;
- no split or group action exists;
- no Phase 4 block detection or extraction work has started;
- the real private benchmark remains deferred and unmeasured;
- unrelated baseline frontend failures mean the full repository is not claimed all-green.

## Roadmap guardrail for the next slice

The next permitted slice is only focused browser-level validation of the existing Source Map UI:

1. inspect whether the repository already has a browser-testing framework before adding any dependency;
2. test keyboard-only access to role, rotation, reorder, Save, Discard, reload, and Confirm controls;
3. verify logical RTL card order and immutable physical labels after reorder;
4. verify first/last move controls are disabled;
5. verify dirty-state, stale-conflict, confirmation, and document-switch dialogs;
6. verify focus remains visible and returns predictably after dialogs;
7. verify `aria-live` announcements for reorder/save/conflict/confirmation;
8. verify reduced-motion and dark-mode behavior at the interaction level where supported;
9. run a focused accessibility scan if an existing supported tool is available;
10. update this ledger and canonical roadmap with exact evidence.

Still out of scope:

- split-into-separate-exams;
- grouping documents;
- physical PDF changes;
- Phase 4 block detection;
- question/answer extraction;
- matching, projection, publication, or rollout.

## User action required

No user input or product decision is required for the next focused browser-validation slice. A decision will be requested before introducing a new broad frontend testing dependency only if the repository has no suitable existing browser-test infrastructure and the dependency would materially affect the project.

## Next verified step

Implement only browser-level RTL, keyboard, and accessibility interaction tests for the already-built Source Map correction/reorder flow. Do not begin split/group actions or Phase 4 block detection.