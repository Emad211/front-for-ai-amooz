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

## 3. Target pipeline

```text
independent private PDF
→ bounded validation and rendering
→ low-resolution page thumbnails
→ fast page-role classification
→ complete page map
→ deterministic virtual segments
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

## 8. Acceptance principles

- no question invented from answer-only content;
- no answer or solution attached across project boundaries;
- no ambiguous automatic match;
- no accepted source block silently omitted;
- no valid sibling record lost due to one malformed record;
- no private object leaked through response metadata;
- accepted warm reruns invoke no provider calls;
- rollout is blocked until private benchmark metrics are recorded.

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
- [-] Run and record private-fixture structural, latency, usage, and warm-rerun benchmark evidence.

**Exit gate:** The three private fixtures produce the correct independent segment maps without full-quality OCR, aggregate latency/usage is recorded, and an unchanged accepted warm rerun makes zero provider calls.

**Phase state:** 8/9 credited. The private benchmark harness and recorded real run are the only remaining Phase 2 deliverable.

### Phase 3 — Teacher source-map confirmation and virtual tools

- [ ] Build simple source-map UI.
- [ ] Support boundary changes and role changes.
- [ ] Support ignore, rotate, and reorder metadata.
- [ ] Add explicit split-into-separate-exams action.
- [ ] Add explicit group-documents action later behind a separate control.
- [ ] Persist revisions and invalidate stale classification.
- [ ] Add accessibility and RTL tests.

**Exit gate:** A nontechnical teacher can correct each benchmark source map without opening an advanced editor.

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

- source-domain models and migration;
- project isolation and constraints;
- private PDF preparation, renders, and thumbnails;
- tolerant fast page-role classification contract;
- deterministic current-revision virtual segments;
- multi-PDF intake with one project/task per PDF;
- owner-scoped project list and source-map detail;
- owner-scoped private thumbnail streaming with no storage fallback;
- private media denial and lifecycle tests.

### Latest focused evidence

- branch head before this documentation sync: `8f38978266f55955a76ed2b4185b19ad74ac78e0`;
- workflow run `30777631820`;
- job `91576032877`;
- PostgreSQL 16 and Redis 7;
- system check clean;
- migration drift clean;
- `114 passed, 33 warnings in 9.02s`.

Warnings are limited to the CI checkout lacking generated `backend/staticfiles/` while API tests initialize Django handlers.

### Progress

The canonical roadmap contains 77 checklist deliverables:

- credited: 19;
- total: 77;
- **overall completion: 24.7%**;
- **Phase 2 completion: 88.9% (8/9)**.

The thumbnail slice does not add a second credit to the already completed source-map API deliverable.

### Next verified step

Implement only a privacy-safe Phase 2 benchmark harness with fake-provider CI coverage and aggregate-only reporting. Do not begin Phase 3 teacher mutations or Phase 4 block detection until the Phase 2 private-fixture exit gate is measured and recorded.

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
