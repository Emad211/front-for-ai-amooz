# Exam Prep V4 — Source-Aware Split Pipeline

> Canonical architecture and roadmap. The execution ledger in `exam-prep-v4-status.md` must be updated before every implementation step.

## 1. Product contract

V4 replaces the transcript-first mixed extraction path with a source-aware pipeline while retaining V3 privacy, revision, audit, task and publication safeguards.

Core decisions:

1. one uploaded PDF creates one independent exam project by default;
2. page ranges, not whole files, receive source roles;
3. questions originate only from question-bearing evidence;
4. correct answer and detailed solution remain one record;
5. blocks and evidence ownership are established before semantic extraction;
6. automatic matching is deterministic and project-scoped;
7. malformed siblings are isolated;
8. private source content never crosses generic media/public-report boundaries;
9. physical `pageNumber` remains immutable while virtual `displayOrder` may change;
10. OCR/vision providers propose evidence only; Source Map, SourceBlock, typed-record, revision, provenance and matcher contracts remain server-authoritative;
11. production routing does not change without measured private evidence and an explicit roadmap decision.

Target flow:

```text
independent private PDF
→ bounded validation/rendering
→ fast page-role classification
→ complete revision-bound Source Map
→ deterministic virtual segments
→ teacher confirmation
→ layout/block evidence proposals
→ typed question extraction
→ typed answer-plus-solution extraction
→ deterministic project-scoped matching
→ exception-only review
→ backward-compatible projection
→ publication
```

Optional OCR evidence path:

```text
confirmed Source Map
→ OCR4 document annotation + blocks
→ deterministic bounded SourceBlock proposals
→ existing validators/persistence
→ current structured detector fallback
→ existing typed extraction and matcher
```

## 2. Privacy and reliability boundaries

- source PDFs, renders, thumbnails, text, OCR Markdown, annotations, raw payloads, object keys, credentials and private errors never enter public serializers or aggregate reports;
- authenticated private previews enforce owner/project/document/page ancestry and `no-store` caching;
- benchmark reports contain only aggregate metrics, reason codes and opaque request IDs;
- accepted unchanged results make zero provider calls;
- changed Source Maps, blocks, questions or answers supersede dependent rows transactionally while preserving history;
- provider output cannot override project/document/page/revision ownership;
- live runs require explicit secrets, reproducible model IDs and fail-closed request ceilings;
- rollout remains blocked until private metrics are recorded or explicitly waived with retained risk.

## 3. Implementation roadmap

Legend: `[ ]` open, `[-]` in progress, `[x]` complete with evidence.

### Phase 0 — Canonical design and benchmark contract

- [x] Create dedicated V4 branch.
- [x] Establish this canonical architecture and roadmap.
- [x] Establish the private benchmark contract.
- [x] Record that the three supplied PDFs are independent exams.
- [x] Record segment structures and out-of-scope boundary behavior without source content.
- [ ] Add PR-level enforcement requiring the living status ledger to change with meaningful V4 implementation changes.

**State:** 5/6.

### Phase 1 — Domain model and feature isolation

- [x] Finalize model names and relationships.
- [x] Add additive migrations.
- [ ] Add Django admin/read-only inspection support.
- [x] Add engine-version and feature-flag resolution without enabling V4 by default.
- [x] Add model constraints and indexes.
- [x] Add migration and project-isolation tests.
- [x] Update the living status ledger with actual schema names and evidence.

**State:** 6/7.

### Phase 2 — Upload and fast source classification

- [x] Create one independent project per uploaded PDF by default.
- [x] Stream and persist uploads safely.
- [x] Render low-resolution thumbnails.
- [x] Extract bounded native-text evidence.
- [x] Implement fast role classification contract.
- [x] Aggregate page roles into deterministic segment proposals.
- [x] Add owner-scoped source-map and private-thumbnail APIs.
- [x] Add classification usage/fingerprint/warm-reuse tracking.
- [-] Run and record private-fixture structural, latency, usage and warm-rerun evidence.

**State:** 8/9. The real three-PDF run is the active gate.

### Phase 3 — Teacher source-map confirmation and virtual tools

- [x] Build simple source-map UI.
- [x] Support boundary and role changes.
- [x] Support ignore, rotate and reorder metadata.
- [ ] Add explicit split-into-separate-exams action.
- [ ] Add explicit group-documents action behind a separate control.
- [x] Persist revisions and invalidate stale classification.
- [-] Add accessibility and RTL tests; browser-level evidence remains open.

**State:** 4/7.

### Phase 4 — Page layout and block detection

- [ ] Implement content-area and column detection.
- [ ] Implement RTL reading order.
- [x] Implement numbered-heading detection.
- [x] Implement source crops and bounding-box persistence.
- [x] Implement continuation candidates.
- [ ] Add project-scoped page deduplication at the block-processing boundary.
- [x] Add block inspection endpoints.
- [-] Test multi-column, formula, diagram and continuation pages on private fixtures.

**State:** 4/8. Persian/Arabic/Latin numbered headings are deterministic and provider evidence remains proposal-only; private quality evidence is still open.

### Phase 5 — Question extraction

- [x] Define simple question record schema.
- [x] Implement per-block extraction.
- [x] Implement tolerant parser and per-record validation.
- [x] Persist raw payload, warnings and evidence privately.
- [x] Implement visual ownership references.
- [x] Implement record-level retry and cache reuse.
- [-] Add private-fixture precision/recall tests.

**State:** 6/7.

### Phase 6 — Answer-solution extraction

- [x] Define unified answer-solution schema.
- [-] Implement and validate real numbered answer-heading extraction.
- [x] Implement continuation merge.
- [x] Extract correct option, final answer and full source solution together.
- [ ] Add and validate compact answer-key accuracy.
- [ ] Add and validate inline question-answer accuracy.
- [x] Add per-record tolerant validation and retry.

**State:** 4/7.

### Phase 7 — Deterministic matcher and integrity gates

- [x] Implement project-scoped exact matching.
- [x] Implement unique-number matching.
- [x] Implement duplicate-number refusal.
- [x] Implement out-of-scope classification.
- [ ] Implement complete option and solution consistency checks.
- [x] Persist match provenance.
- [x] Add zero-cross-project-match tests.

**State:** 6/7.

### Phase 8 — Exception review and final projection

- [ ] Create issue model and APIs.
- [ ] Build exception-only review UI.
- [ ] Support teacher match/ignore/out-of-scope decisions.
- [ ] Build backward-compatible student projection.
- [ ] Remove provenance and solutions from unauthorized student responses.
- [ ] Bind final confirmation to current revision and projection fingerprint.

### Phase 9 — Reliability, cleanup and security hardening

- [ ] Add stale-task recovery.
- [ ] Add retention and orphan sweeps.
- [ ] Add fail-closed project deletion.
- [ ] Add private-media denial tests across all new artifact classes.
- [ ] Add load, concurrency and worker-memory tests.
- [ ] Add audit-safe observability.

### Phase 10 — Shadow benchmark and rollout

- [ ] Implement production shadow-benchmark management.
- [ ] Run cold and warm end-to-end private benchmarks.
- [ ] Run V3/V4 shadow comparison without mutating user output.
- [ ] Record aggregate results in the rollout runbook.
- [ ] Enable for a limited cohort.
- [ ] Monitor corrections, latency, cost and failures.
- [ ] Verify rollback.
- [ ] Make V4 default only after all gates pass.

## 4. Current checkpoint — 2026-08-04

Verified implementation now includes:

- additive source-domain schema, private storage lifecycle and project isolation;
- complete revision-bound Source Map APIs and RTL teacher UI;
- immutable physical identity plus auditable virtual order;
- typed SourceBlocks/Fragments, crops, bboxes, continuation candidates and safe inspection;
- typed QuestionRecord and unified AnswerSolutionRecord paths;
- tolerant parsing, partial retry, exact reuse and private evidence;
- deterministic matching, duplicate refusal, out-of-scope handling and zero cross-project matches;
- transaction-safe downstream invalidation;
- bounded question/answer batching;
- synthetic three-project cold/warm full-pipeline benchmark;
- isolated AvalAI OCR4 client and measured two-page smoke;
- optional OCR evidence adapter using primary `document_annotation`, transient-only retry, diagram-only bbox escalation, whole-segment fallback and warm zero-call reuse;
- OCR-aware aggregate full benchmark with a manifest-derived fail-closed ceiling;
- manual one-click three-private-PDF workflow on `main`.

Latest focused evidence:

```text
feature head: 5db6e4b7eab2d4ae3150b79d342b8cfc93b107c9
workflow: 30857010156
backend job: 91830257210
frontend job: 91830257126
validated merge ref: 54e401d067c596444b20e1c4497d77fd7ad58615
System check: passed
Migration drift: none
Backend: 252 passed, 47 warnings in 25.62s
Frontend focused TypeScript/state tests: passed
```

Established denominator remains 77 deliverables:

- credited: 43;
- **overall: 43/77 = 55.8%**;
- Phase 4: 4/8;
- Phase 5: 6/7;
- Phase 6: 4/7;
- Phase 7: 6/7.

## 5. Active live gate

Workflow:

```text
.github/workflows/exam-prep-v4-full-live-benchmark.yml
main commit: 5903d08fc3f58d8625f4ddf80fdccd92949b1ac6
```

Configuration:

```text
three recorded private PDFs
structured model: gemini-2.5-flash
OCR model: mistral-ocr-4-0
OCR attempts: 2
bbox escalation: diagram pages only
hard external-call ceiling: 484
aggregate artifact retention: 1 day
```

Ceiling derivation:

```text
3 classification invocations
6 possible structured block fallbacks
79 semantic batches
88 structured invocations × 3 request slots = 264
55 OCR-eligible pages × 2 attempts × 2 possible modes = 220
required fail-closed ceiling = 484
```

This is a worst-case bound, not expected usage. The workflow never reruns automatically and stores only an aggregate report or content-free failure summary.

The next permitted operation is exactly one manual workflow run. Phase 8, publication and rollout remain blocked until its evidence is reviewed.

## 6. Decision log

- **D-001:** Build V4 as a new engine on durable V3 infrastructure.
- **D-002:** One PDF equals one independent project by default.
- **D-003:** Roles attach to contiguous page ranges.
- **D-004:** Correct answer and source solution remain unified.
- **D-005:** Block/evidence ownership precedes semantic extraction.
- **D-006:** Validation is tolerant per record, not permissive globally.
- **D-007:** Automatic matching is deterministic only.
- **D-008:** Out-of-scope answers never create questions.
- **D-009:** Deduplication is project-scoped.
- **D-010:** Private V4 thumbnail storage never falls back to public/default media.
- **D-011:** Benchmarks are explicit and aggregate-only.
- **D-012:** Unmeasured private gates receive no credit.
- **D-013:** Source Map mutations use complete-map optimistic concurrency.
- **D-014:** Source Map UI preserves local edits and privacy.
- **D-015:** Virtual order never changes physical evidence identity.
- **D-016:** Downstream invalidation is transactional and auditable.
- **D-017:** Provider batching remains block-authoritative.
- **D-018:** Live benchmarks require hard external-call ceilings.
- **D-019:** Current official AvalAI documentation is a mandatory decision input.
- **D-020:** OCR4 is an optional evidence adapter; existing detector/persistence remain authoritative and default-disabled.
- **D-021:** The three-private-PDF run uses a manifest-derived ceiling of 484 and one manual, non-recurring workflow execution.