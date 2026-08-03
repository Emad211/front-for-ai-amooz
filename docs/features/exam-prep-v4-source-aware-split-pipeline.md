# Exam Prep V4 — Source-Aware Split Pipeline

> Canonical architecture and roadmap. The detailed, turn-by-turn evidence ledger lives in `exam-prep-v4-status.md` and must be updated before implementation work in every V4 turn.

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
15. Provider-specific OCR or vision services may propose evidence, but current Source Map, SourceBlock, typed-record, revision, provenance, and matcher contracts remain server-authoritative.
16. No provider-specific production route replaces the verified path without measured private evidence and an explicit roadmap decision.

## 3. Target pipeline

```text
independent private PDF
→ bounded validation and rendering
→ low-resolution page thumbnails
→ fast page-role classification
→ complete physical page map
→ deterministic virtual page order and segments
→ teacher source-map confirmation
→ layout/block detection or evidence proposal
→ specialized question extraction
→ specialized answer-plus-solution extraction
→ deterministic project-scoped matching
→ exception-only teacher review
→ backward-compatible projection
→ publication
```

A possible OCR-assisted implementation remains a candidate, not the active production route:

```text
confirmed Source Map
→ OCR Markdown / OCR4 blocks
→ deterministic SourceBlock proposals
→ existing typed validators and persistence
→ vision fallback for unresolved evidence
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

Private PDF bytes, page renders, thumbnails, extracted text, native text samples, object keys, hashes, OCR Markdown, annotation payloads, raw model payloads, model reasons, and private error details must not be exposed through public serializers or generic `/media/` routes.

Private source previews must use explicit authenticated endpoints with owner/project/document/page ancestry checks, private no-store caching, and no storage URL or object-name disclosure.

Virtual ordering may expose only immutable page number, one-based display order, safe role/orientation data, and safe segment page sequences. It may not expose private segment metadata or storage identity.

Benchmark and smoke reports may contain aggregate metrics and opaque request IDs only. Local paths, filenames, source bytes, text, crops, annotations, questions, answers, solutions, credentials, and raw provider output are forbidden.

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
- Changed Source Maps or block sets supersede dependent semantic rows and matches transactionally.
- Batched provider output remains record-level validated and block-authoritative.
- Live private runs require explicit credentials, transmission permission, reproducible model IDs, and hard request ceilings.

## 8. Acceptance principles

- no question invented from answer-only content;
- no answer or solution attached across project boundaries;
- no ambiguous automatic match;
- no accepted source block silently omitted;
- no valid sibling record lost due to one malformed record;
- no private object leaked through response metadata;
- accepted warm reruns invoke no provider calls;
- physical page evidence is never renumbered by virtual reorder;
- provider output cannot override document/project/evidence authority;
- documentation or synthetic tests alone do not prove private accuracy;
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
- [-] Add accessibility and RTL tests. **Implementation, focused typecheck, and pure-state tests pass; browser-level keyboard/RTL/accessibility evidence remains open.**

**Exit gate:** A nontechnical teacher can correct each benchmark source map without opening an advanced editor.

**Phase state:** 4/7 credited.

### Phase 4 — Page layout and block detection

- [ ] Implement content-area and column detection.
- [ ] Implement RTL reading order.
- [ ] Implement numbered-heading detection.
- [x] Implement source crops and bounding-box persistence.
- [x] Implement continuation candidates.
- [ ] Add project-scoped page deduplication at the block-processing boundary.
- [x] Add block inspection endpoints.
- [ ] Test multi-column, formula, diagram, and continuation pages on private fixtures.

**Exit gate:** Stable blocks exist before semantic question/answer extraction.

**Phase state:** 3/8 credited. Typed bbox/fragment persistence, continuation evidence, and owner-scoped safe inspection are verified. Real detector quality remains open.

### Phase 5 — Question extraction

- [x] Define simple question record schema.
- [x] Implement per-block extraction.
- [x] Implement tolerant parser and per-record validation.
- [x] Persist raw payload, warnings, and evidence privately.
- [x] Implement visual ownership references.
- [x] Implement record-level retry and cache reuse.
- [ ] Add private-fixture precision/recall tests.

**Exit gate:** At least 99% question recall on private fixtures without fabricated questions.

**Phase state:** 6/7 credited.

### Phase 6 — Answer-solution extraction

- [x] Define unified answer-solution schema.
- [ ] Implement and validate real numbered answer-heading extraction.
- [x] Implement continuation merge.
- [x] Extract correct option, final answer, and full source solution together.
- [ ] Add and validate compact answer-key sub-pipeline accuracy.
- [ ] Add and validate inline question-answer sub-pipeline accuracy.
- [x] Add per-record tolerant validation and retry.

**Exit gate:** At least 99% in-scope answer-solution recall with correct boundaries.

**Phase state:** 4/7 credited.

### Phase 7 — Deterministic matcher and integrity gates

- [x] Implement project-scoped exact matching.
- [x] Implement unique-number matching.
- [x] Implement duplicate-number refusal.
- [x] Implement out-of-scope classification.
- [ ] Implement complete option and solution consistency checks.
- [x] Persist match provenance.
- [x] Add zero-cross-project-match tests.

**Exit gate:** 100% automatic match precision for answers and solutions on private fixtures.

**Phase state:** 6/7 credited.

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

- source-domain models and additive migrations `0040` through `0044`;
- project isolation, private storage lifecycle, constraints, and byte-stable idempotency;
- private PDF preparation, renders, thumbnails, and bounded native-text evidence;
- tolerant fast page-role classification and deterministic virtual segments;
- owner-scoped source-map/detail/mutation/confirmation/thumbnail APIs;
- complete-map revision and structural-fingerprint binding;
- RTL teacher Source Map UI with role, boundary, ignore, rotation, virtual reorder, Save, Discard, conflict, and confirmation flows;
- immutable `pageNumber` plus mutable `displayOrder` and auditable prior revisions;
- typed SourceBlock/Fragment persistence with bbox, crop provenance, continuation candidates, and safe inspection;
- typed QuestionRecord and unified AnswerSolutionRecord schemas;
- tolerant record-level parsers, private raw payload/warnings/evidence, exact reuse, and partial retry;
- deterministic project-scoped matching, duplicate refusal, out-of-scope decisions, and persisted provenance;
- transaction-safe downstream invalidation preserving history;
- bounded semantic question/answer batching with authoritative block IDs;
- three-project synthetic cold/warm full-pipeline benchmark and aggregate-only report;
- hard live-benchmark external-request ceiling;
- isolated AvalAI OCR4 bounded client, two-page aggregate smoke command, fake transport, parser/privacy bounds, and runbook;
- no OCR production routing change and no private OCR request executed.

### Current APIs and commands

Application APIs:

```text
POST /api/classes/exam-prep-v4/projects/
GET  /api/classes/exam-prep-v4/projects/
GET  /api/classes/exam-prep-v4/projects/<project_id>/
PUT  /api/classes/exam-prep-v4/projects/<project_id>/documents/<document_id>/source-map/
POST /api/classes/exam-prep-v4/projects/<project_id>/documents/<document_id>/source-map/confirm/
GET  /api/classes/exam-prep-v4/projects/<project_id>/documents/<document_id>/pages/<page_number>/thumbnail/
GET  /api/classes/exam-prep-v4/projects/<project_id>/documents/<document_id>/blocks/
```

Private management commands:

```text
benchmark_exam_prep_v4
benchmark_exam_prep_v4_full_pipeline
smoke_exam_prep_v4_avalai_ocr
```

### Latest focused evidence

- validated branch head: `b29055d900d2ec6727d39be181567a554e0b336a`;
- workflow run `30845511947`;
- backend job `91792716665`;
- frontend job `91792716703`;
- validated PR merge ref `744149f2029e95fad17229ea36740baa845f2096`.

```text
Python 3.12
PostgreSQL 16
Redis 7
System check identified no issues (0 silenced).
No changes detected in app 'classes'.
231 passed, 47 warnings in 25.38s
Focused TypeScript check: passed
Source-map state-model tests: passed
```

Warnings are limited to the CI checkout lacking generated `backend/staticfiles/`. Expected negative PostgreSQL constraint logs are successful failure-path tests.

### Progress

The canonical roadmap denominator remains 77 established deliverables:

- credited: 42;
- **overall completion: 42/77 = 54.5%**;
- Phase 4: 3/8;
- Phase 5: 6/7;
- Phase 6: 4/7;
- Phase 7: 6/7.

No OCR feasibility credit was added because no live private quality evidence exists.

### AvalAI OCR feasibility checkpoint

Official AvalAI documentation must be re-read before future AvalAI endpoint/model/pricing/data-handling decisions. The pinned candidate is:

```text
endpoint: POST https://api.avalai.ir/v1/ocr
model: mistral-ocr-4-0
input: bounded local bytes as base64 data URL
```

Four isolated smoke modes are implemented:

```text
markdown
blocks
document_annotation
bbox_annotation
```

`bbox_annotation` is treated as extracted-image/figure annotation. It is not assumed to replace text-block detection. OCR4 `blocks` support through the AvalAI gateway remains a live measurement target.

### Active gate

The next permitted operation is only a bounded two-page live OCR smoke:

```text
one representative question page
one representative answer-solution or continuation page
× four modes
= exactly 8 requests
```

Required before execution:

1. local/environment `AVALAI_API_KEY` availability;
2. explicit permission to transmit exactly those two private page images;
3. approval of pinned `mistral-ocr-4-0`;
4. approval of hard request ceiling `8`;
5. page selection by the product owner or permission for the implementation agent to select representative pages.

No full PDF, production routing change, Phase 8 work, publication, or rollout is authorized by this gate.

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

A missing V4 thumbnail may not fall back to default or legacy storage.

### D-011 — Benchmark execution is explicit and aggregate-only

Fake and live benchmark modes are explicit, projects remain independent, and private source content or raw provider payloads may not enter reports.

### D-012 — Real Phase 2 benchmark deferred by product owner

The original three-PDF classification gate remains open and uncredited under an explicit product-owner waiver.

### D-013 — Complete-map optimistic mutations and exact confirmation binding

Teacher corrections replace the complete structural page map under an expected revision. Confirmation is valid only for the exact current revision and fingerprint.

### D-014 — Source Map UI preserves privacy and complete-map authority

The teacher UI stores edits locally until explicit save, preserves local changes on stale conflicts, retrieves authenticated private thumbnails, and confirms only saved current state.

### D-015 — Virtual page order is not physical page identity

`pageNumber` permanently identifies source evidence. `displayOrder` controls virtual presentation and processing only.

### D-016 — Semantic output invalidates transactionally

Changed Source Maps, block sets, question sets, or answer sets supersede dependent accepted downstream rows and matches without deleting audit history.

### D-017 — Semantic provider calls may batch but remain block-authoritative

Bounded stage-specific batches reduce calls while every record remains tied to authoritative block identity and malformed siblings remain isolated.

### D-018 — Private live benchmarks require hard request ceilings

The full live benchmark reserves the worst-case external-request budget before each structured invocation and fails before entering a request path when the ceiling is insufficient.

### D-019 — AvalAI documentation is a mandatory decision input

Before AvalAI-dependent code or execution, update the roadmap and re-read relevant current official AvalAI documentation. Pin reproducible model IDs, separate documented facts from upstream context/inference/measurement, and never infer endpoint privacy guarantees.

### D-020 — OCR4 remains an isolated candidate until live evidence

The AvalAI OCR client and smoke command do not alter production routing. `mistral-ocr-4-0` may become OCR-first, transcription-only, diagram-only, or rejected for V4 only after the bounded two-page live smoke is reviewed and recorded.