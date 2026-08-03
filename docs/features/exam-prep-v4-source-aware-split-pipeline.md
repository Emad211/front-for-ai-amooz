# Exam Prep V4 — Source-Aware Split Pipeline

> Canonical architecture and roadmap. The detailed, turn-by-turn evidence ledger lives in `exam-prep-v4-status.md` and must be updated in every implementation turn.

## 1. Problem statement

V3 retains important reliability, privacy, revision, audit, and publication safeguards, but its transcript-first mixed extraction architecture is not reliable enough for documents where question pages, answer pages, answer keys, inline answers, covers, multi-column layouts, and continuation pages appear in different orders.

V4 replaces that extraction path with a source-aware pipeline while reusing durable V3 infrastructure where appropriate.

## 2. Core product decisions

1. One uploaded PDF creates one independent exam project by default.
2. Several PDFs in one upload request create several independent projects.
3. Equal file hashes do not imply shared exam identity.
4. A PDF is classified by contiguous page ranges, not by one file-level role.
5. Questions are extracted only from question-bearing ranges.
6. Correct answer and detailed solution are extracted together from one answer-solution block.
7. Blocks are detected before semantic extraction.
8. Automatic matching is deterministic and project-scoped.
9. Out-of-scope answers never create questions.
10. One malformed model record must not erase valid sibling records.
11. Private source content never crosses a generic media route.
12. Teacher corrections and confirmation are revision-bound.
13. Physical page identity and virtual processing order are separate: `pageNumber` is immutable evidence identity and `displayOrder` is mutable one-based virtual order.
14. Virtual reorder never rewrites source PDFs or moves pages across source documents.

## 3. Target pipeline

```text
independent private PDF
→ bounded validation and rendering
→ low-resolution page thumbnails
→ fast page-role classification
→ complete physical page map
→ deterministic virtual page order and segments
→ teacher source-map confirmation
→ layout/block detection
→ specialized question extraction
→ specialized answer-plus-solution extraction
→ deterministic project-scoped matching
→ exception-only teacher review
→ backward-compatible projection
→ publication
```

## 4. Source roles

- `cover`
- `questions`
- `answer_solutions`
- `answer_key`
- `inline_question_answer`
- `ignored`
- `unknown`

## 5. Matching policy

Automatic matching is limited to:

1. exact normalized section plus printed question number;
2. a question number that is unique inside the same exam project.

Ambiguous, duplicate, unnumbered, or conflicting evidence remains unresolved for review. Fuzzy similarity may assist review but may not create an automatic match.

## 6. Privacy boundary

Private PDF bytes, page renders, thumbnails, extracted text, native text samples, object keys, hashes, raw model payloads, model reasons, and error details must not be exposed through public serializers or generic `/media/` routes.

Private source previews must use explicit authenticated endpoints with owner/project/document/page ancestry checks, private no-store caching, and no storage URL or object-name disclosure.

Virtual ordering may expose only immutable page number, one-based display order, safe role/orientation data, and safe segment page sequences. It may not expose private segment metadata or storage identity.

## 7. Reliability boundary

- Feature-gated V4 activation.
- One project per PDF by default.
- Idempotent request and document identifiers.
- Project-scoped duplicate handling.
- Revision and fingerprint checks.
- Independent task dispatch per source document.
- Warm reuse for accepted unchanged results.
- Controlled conflicts must not corrupt accepted state.
- Storage lifecycle must fail closed.
- Complete-map mutations contain every physical page and every virtual position exactly once.
- Reorder-only changes invalidate stale confirmation and downstream bindings.
- Prior virtual order and segment revisions remain auditable.

## 8. Acceptance principles

- no question invented from answer-only content;
- no answer or solution attached across project boundaries;
- no ambiguous automatic match;
- no accepted source block silently omitted;
- no valid sibling record lost due to one malformed record;
- no private object leaked through response metadata;
- accepted warm reruns invoke no provider calls;
- physical page evidence is never renumbered by virtual reorder;
- rollout is blocked until private benchmark metrics are recorded or explicitly waived with risk retained.

---

## 9. Implementation roadmap

Legend:

- `[ ]` not started
- `[-]` in progress
- `[x]` complete with evidence

### Phase 0 — Canonical design and benchmark contract

- [x] Create dedicated V4 branch.
- [x] Establish this canonical architecture and roadmap.
- [x] Establish the private benchmark contract.
- [x] Record that the three supplied PDFs are independent exams.
- [x] Record segment structures and out-of-scope boundary behavior without source content.
- [ ] Add PR-level enforcement requiring the living status ledger to change with meaningful V4 implementation changes.

**Phase state:** 5/6 credited.

### Phase 1 — Domain model and feature isolation

- [x] Finalize model names and relationships.
- [x] Add additive migrations.
- [ ] Add Django admin/read-only inspection support.
- [x] Add engine-version and feature-flag resolution without enabling V4 by default.
- [x] Add model constraints and indexes.
- [x] Add migration and project-isolation tests.
- [x] Update the living status ledger with actual schema names and evidence.

**Exit gate:** Fresh PostgreSQL migration, project isolation, constraints, and unchanged V1/V2/V3 behavior are verified.

**Phase state:** 6/7 credited; admin inspection remains deferred.

### Phase 2 — Upload and fast source classification

- [x] Create one independent project per uploaded PDF by default.
- [x] Stream and persist uploads safely.
- [x] Render low-resolution thumbnails.
- [x] Extract bounded native-text evidence.
- [x] Implement fast role classification contract.
- [x] Aggregate page roles into deterministic segment proposals.
- [x] Add owner-scoped source-map and private thumbnail read APIs.
- [x] Add classification usage/fingerprint/warm-reuse tracking.
- [-] Run and record private-fixture structural, latency, usage, and warm-rerun benchmark evidence. **Deferred by product owner on 2026-08-03; not credited.**

**Exit gate:** The three private fixtures produce the correct independent segment maps without full-quality OCR, aggregate latency/usage is recorded, and an unchanged accepted warm rerun makes zero provider calls.

**Phase state:** 8/9 credited. Harness and synthetic coverage are complete; the real run remains open under an explicit product-owner waiver.

### Phase 3 — Teacher source-map confirmation and virtual tools

- [x] Build simple source-map UI.
- [x] Support boundary changes and role changes.
- [x] Support ignore, rotate, and reorder metadata.
- [ ] Add explicit split-into-separate-exams action.
- [ ] Add explicit group-documents action later behind a separate control.
- [x] Persist revisions and invalidate stale classification.
- [-] Add accessibility and RTL tests. **RTL/accessibility implementation, focused typecheck, and pure state tests pass; browser-level keyboard/RTL/accessibility interaction tests remain open.**

**Exit gate:** A nontechnical teacher can correct each benchmark source map without opening an advanced editor.

**Phase state:** 4/7 credited. Source Map UI, role/boundary correction, ignore/rotation/reorder, and revision safety are verified. Split/group actions and browser-level accessibility evidence remain open.

### Phase 4 — Page layout and block detection

- [ ] Implement content-area and column detection.
- [ ] Implement RTL reading order.
- [ ] Implement numbered-heading detection.
- [ ] Implement source crops and bounding-box persistence.
- [ ] Implement continuation candidates.
- [ ] Add project-scoped page deduplication at the block-processing boundary.
- [ ] Add block inspection endpoints.
- [ ] Test multi-column, formula, diagram, and continuation pages.

**Exit gate:** Stable blocks exist before semantic question/answer extraction.

### Phase 5 — Question extraction

- [ ] Define simple question record schema.
- [ ] Implement per-block extraction.
- [ ] Implement tolerant parser and per-record validation.
- [ ] Persist raw payload, warnings, and evidence privately.
- [ ] Implement visual ownership references.
- [ ] Implement record-level retry and cache reuse.
- [ ] Add precision/recall tests.

**Exit gate:** At least 99% question recall on private fixtures without fabricated questions.

### Phase 6 — Answer-solution extraction

- [ ] Define unified answer-solution schema.
- [ ] Implement numbered answer heading extraction.
- [ ] Implement continuation merge.
- [ ] Extract correct option, final answer, and full source solution together.
- [ ] Add compact answer-key sub-pipeline.
- [ ] Add inline question-answer sub-pipeline.
- [ ] Add per-record tolerant validation and retry.

**Exit gate:** At least 99% in-scope answer-solution recall with correct boundaries.

### Phase 7 — Deterministic matcher and integrity gates

- [ ] Implement project-scoped exact matching.
- [ ] Implement unique-number matching.
- [ ] Implement duplicate-number refusal.
- [ ] Implement out-of-scope classification.
- [ ] Implement option and solution consistency checks.
- [ ] Persist match provenance.
- [ ] Add zero-cross-project-match tests.

**Exit gate:** 100% automatic match precision for answers and solutions on private fixtures.

### Phase 8 — Exception review and final projection

- [ ] Create issue model and APIs.
- [ ] Build exception-only review UI.
- [ ] Support teacher match/ignore/out-of-scope decisions.
- [ ] Build backward-compatible student projection.
- [ ] Remove provenance and solutions from unauthorized student responses.
- [ ] Bind final confirmation to current revision and projection fingerprint.

**Exit gate:** Teacher can resolve all ambiguous benchmark cases and publish safely.

### Phase 9 — Reliability, cleanup, and security hardening

- [ ] Add stale-task recovery.
- [ ] Add retention and orphan sweeps.
- [ ] Add fail-closed project deletion.
- [ ] Add private media denial tests across all new artifact classes.
- [ ] Add load, concurrency, and worker-memory tests.
- [ ] Add audit-safe observability.

**Exit gate:** Security/lifecycle suite passes and no private object is leaked or orphaned.

### Phase 10 — Shadow benchmark and rollout

- [ ] Implement production shadow-benchmark management.
- [ ] Run cold and warm end-to-end private benchmarks.
- [ ] Run V3/V4 shadow comparison without mutating user output.
- [ ] Record aggregate results in the rollout runbook.
- [ ] Enable for a limited cohort.
- [ ] Monitor corrections, latency, cost, and failures.
- [ ] Verify rollback.
- [ ] Make V4 default only after all gates pass.

**Exit gate:** Product owner approves metrics and controlled rollout.

---

## 10. Current checkpoint — 2026-08-03

### Verified implementation

- source-domain models and migrations `0040`, `0041`, and `0042`;
- project isolation and constraints;
- private PDF preparation, renders, and thumbnails;
- tolerant fast page-role classification contract;
- deterministic current-revision virtual segments;
- multi-PDF intake with one project/task per PDF;
- owner-scoped project list and source-map detail;
- owner-scoped private thumbnail streaming with no storage fallback;
- privacy-safe benchmark harness with fake/live modes and aggregate-only output;
- product-owner waiver retaining the unmeasured real benchmark risk;
- canonical structural Source Map fingerprint;
- complete-map teacher mutation with optimistic revision checks;
- preservation of classifier predictions and separate teacher overrides;
- role/ignored/orientation metadata edits;
- deterministic segment reconstruction;
- prior revision segment supersession and bounded structural history;
- stale classification and confirmation invalidation;
- exact revision/fingerprint confirmation;
- owner-scoped mutation and confirmation endpoints;
- teacher V4 project-list and Source Map routes;
- centralized V4 frontend service and revision-safe hooks;
- responsive RTL page-card grid;
- explicit role, ignore, rotation, save, discard, reload, and confirm controls;
- virtual `displayOrder` separate from immutable `pageNumber`;
- migration backfill and schema-v2 fingerprint upgrade;
- database uniqueness/positivity constraints for virtual order;
- virtual-order-aware classifier and segment builder;
- transaction-safe reorder swaps without uniqueness collisions;
- safe read serialization of virtual order and physical page sequence;
- accessible Move Earlier/Move Later controls without drag dependency;
- virtual DOM ordering while thumbnail/evidence identity remains physical;
- dirty-state, rollback, stale-conflict, retry, and confirmation behavior after reorder;
- PostgreSQL migration/constraint/mutation coverage and focused frontend state tests.

### Current endpoints

```text
POST /api/classes/exam-prep-v4/projects/
GET  /api/classes/exam-prep-v4/projects/
GET  /api/classes/exam-prep-v4/projects/<project_id>/
PUT  /api/classes/exam-prep-v4/projects/<project_id>/documents/<document_id>/source-map/
POST /api/classes/exam-prep-v4/projects/<project_id>/documents/<document_id>/source-map/confirm/
GET  /api/classes/exam-prep-v4/projects/<project_id>/documents/<document_id>/pages/<page_number>/thumbnail/
```

### Current teacher routes

```text
/teacher/exam-prep-v4
/teacher/exam-prep-v4/<projectId>
```

### Latest focused evidence

- validated branch head: `eb071778d3c2fba460a1e2da14e4e8587a675646`;
- workflow run `30809570611`;
- backend job `91672836979`;
- frontend job `91672836921`.

Backend:

```text
System check identified no issues (0 silenced).
No changes detected in app 'classes'.
165 passed, 44 warnings in 14.07s
```

Frontend:

```text
Focused TypeScript check: passed
Source-map state-model tests: 8 passed, 0 failed
```

Backend warnings are limited to the CI checkout lacking generated `backend/staticfiles/`. The native Node runner emits a non-failing package-module warning. Existing dependency-audit findings are not claimed resolved or caused by this slice.

### Progress

The canonical roadmap contains 77 checklist deliverables:

- credited: 23;
- total: 77;
- **overall completion: 29.9%**;
- **Phase 2: 88.9% (8/9), one item deferred**;
- **Phase 3: 57.1% (4/7)**.

The virtual-order slice closes the combined ignore/rotate/reorder roadmap item. Accessibility/RTL browser validation, split, and group remain open.

### Known limitations

- no source PDF rewriting or reordered-PDF generation exists;
- no cross-document page movement exists;
- no drag-and-drop interaction exists or is required;
- no browser/E2E, visual-regression, contrast, screen-reader, or full keyboard-flow run is recorded yet;
- no split/group action exists;
- no Phase 4 block detection or later extraction work has started;
- the real private benchmark remains deferred and unmeasured;
- unrelated baseline frontend failures mean the full repository is not claimed all-green.

### Next verified step

Inspect existing browser-test infrastructure and add only focused RTL, keyboard, dialog-focus, stale-conflict, confirmation, and accessibility interaction tests for the existing Source Map UI. Do not begin split/group actions or Phase 4 block detection.

---

## 11. Decision log

### D-001 — New engine on durable V3 infrastructure

Build V4 as a new extraction engine while reusing proven reliability, privacy, revision, audit, and task primitives.

### D-002 — One PDF equals one independent exam by default

Similar pages, equal hashes, and overlapping numbers never merge independent projects automatically.

### D-003 — Page-range roles, not file-level roles

Classify contiguous ranges because cover, question, and answer sections may appear in any order.

### D-004 — Unified answer and solution record

Extract the correct answer and detailed solution together from the same numbered source block.

### D-005 — Block-first extraction

Preserve layout, column ownership, bounding boxes, and continuations before semantic extraction.

### D-006 — Tolerant record-level validation

A malformed record is isolated; valid siblings remain usable.

### D-007 — Deterministic matching only

Incorrect automatic matches are worse than unresolved records. Fuzzy evidence is review assistance only.

### D-008 — Out-of-scope answers never create questions

Question inventory originates only from question-bearing segments.

### D-009 — Deduplication is project-scoped

No global page or block identity is inferred across independent exams.

### D-010 — Private V4 thumbnail storage never falls back

A missing V4 thumbnail may not fall back to default or legacy storage. The owner-scoped endpoint opens only the storage bound to the private field and otherwise returns an indistinguishable 404.

### D-011 — Benchmark execution is explicit and aggregate-only

Benchmark mode has no implicit default. Fake-provider and live-provider modes must be chosen explicitly, every fixture remains an independent project, report-visible fixture IDs are anonymous, and no private source data or raw model payload may enter command output or the aggregate report.

### D-012 — Real benchmark deferred by product owner

The product owner explicitly chose to continue development without running the local live Phase 2 benchmark. The gate remains open, receives no credit, and its accuracy/latency/cost risk remains visible until resumed.

### D-013 — Complete-map optimistic mutations and exact confirmation binding

Teacher corrections replace the complete structural page map under an expected revision. Accepted edits create a new revision, preserve prior audit history, and invalidate stale state. Confirmation is valid only for the exact current revision and structural Source Map fingerprint.

### D-014 — Source Map UI preserves complete-map and privacy boundaries

The teacher UI keeps all network access in a centralized service, stores edits locally until explicit save, preserves local changes on stale conflicts, retrieves private thumbnails only as authenticated Blobs, and confirms only the currently saved revision/fingerprint.

### D-015 — Virtual page order is not physical page identity

`pageNumber` permanently identifies the original PDF page and evidence. `displayOrder` alone controls virtual presentation and future processing order. Reordering swaps adjacent virtual positions inside one document, participates in the structural fingerprint and revision history, and never rewrites the PDF, renumbers evidence, changes page-row identity, or crosses document/project boundaries. Accessible explicit move buttons are the required baseline interaction; drag-and-drop is optional and not necessary for correctness.