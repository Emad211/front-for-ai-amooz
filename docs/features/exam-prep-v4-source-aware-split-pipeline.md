# Exam Prep V4 — Source-Aware Split Pipeline

> Canonical architecture and roadmap. The execution ledger in `exam-prep-v4-status.md` must be updated before every implementation step. Real-provider validation is performed by the owner in the deployed environment; CI remains fake-provider/contract-only.

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
11. production models are selected from environment only;
12. Source Map confirmation queues the exact current revision for production extraction;
13. every extraction run has stable correlation IDs and content-free structured logs;
14. teacher exception decisions are immutable and fingerprint-bound;
15. reviewed V4 records project into the existing student Exam Prep domain rather than duplicating student/scoring infrastructure;
16. real accuracy, latency and provider-cost measurements belong to owner-run deployment validation, not CI.

Target flow:

```text
independent private PDF
→ bounded validation/rendering
→ fast page-role classification
→ complete revision-bound Source Map
→ deterministic virtual segments
→ teacher confirmation
→ idempotent production extraction dispatch
→ layout/block evidence proposals
→ typed question extraction
→ typed answer-plus-solution extraction
→ deterministic project-scoped matching
→ exception-only review
→ fingerprint-bound backward-compatible projection
→ publication through the existing student Exam Prep flow
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

- source PDFs, renders, thumbnails, text, OCR Markdown, annotations, raw payloads, object keys, credentials and private errors never enter public serializers or operational logs;
- authenticated private previews enforce owner/project/document/page ancestry and `no-store` caching;
- status/operational APIs expose identifiers, stages, safe counters and reason codes only;
- accepted unchanged results make zero provider calls;
- changed Source Maps, blocks, questions or answers supersede dependent rows transactionally while preserving history;
- provider output cannot override project/document/page/revision ownership;
- source-map confirmation, retries, reviews and publication remain bound to exact current fingerprints;
- cooperative cancellation is checked around provider stages/batches;
- stale active runs fail closed and retain correlation evidence;
- rollout remains feature-flagged until the owner records production behavior.

## 3. Implementation roadmap

Legend: `[ ]` open, `[-]` in progress, `[x]` complete with contract evidence. Real-quality items remain `[-]` until owner-run deployment evidence exists.

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
- [-] Run and record production structural, latency, usage and warm-rerun evidence.

**State:** 8/9. The owner measures this after deployment.

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
- [-] Test multi-column, formula, diagram and continuation pages in production.

**State:** 4/8. Provider evidence remains proposal-only; production quality evidence remains owner-run.

### Phase 5 — Question extraction

- [x] Define simple question record schema.
- [x] Implement per-block extraction.
- [x] Implement tolerant parser and per-record validation.
- [x] Persist raw payload, warnings and evidence privately.
- [x] Implement visual ownership references.
- [x] Implement record-level retry and cache reuse.
- [-] Record production precision/recall.

**State:** 6/7.

### Phase 6 — Answer-solution extraction

- [x] Define unified answer-solution schema.
- [-] Validate real numbered answer-heading extraction.
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
- [ ] Implement complete option and solution semantic consistency checks.
- [x] Persist match provenance.
- [x] Add zero-cross-project-match tests.

**State:** 6/7.

### Phase 8 — Exception review and final projection

- [-] Create a dedicated persisted issue model and APIs. The current exception queue API and immutable decision model are production-callable; a separately persisted issue row remains open.
- [x] Build exception-only review UI.
- [x] Support teacher match/ignore/out-of-scope decisions.
- [x] Build backward-compatible student projection.
- [x] Remove V4 provenance/raw payloads and rely on the existing authorized student response contract.
- [x] Bind review finalization and publication to current record/projection fingerprints.

**State:** 5/6.

### Phase 9 — Reliability, cleanup and security hardening

- [x] Add stale-task recovery.
- [ ] Add retention and orphan sweeps.
- [ ] Add fail-closed project deletion across all V4/projection artifacts.
- [ ] Add private-media denial tests across all new artifact classes.
- [ ] Add load, concurrency and worker-memory tests.
- [x] Add audit-safe observability.

Additional production reliability implemented without changing the denominator:

- idempotent extraction dispatch after exact Source Map confirmation;
- owner-scoped status/retry/cancel APIs and frontend controls;
- stable `runId`/`taskId` correlation;
- cooperative cancellation around provider stages/batches;
- bounded transient retry and explicit Celery terminal failure;
- stale-run management command/task and operator runbook.

**State:** 2/6.

### Phase 10 — Shadow benchmark and rollout

- [ ] Implement production shadow-benchmark management.
- [ ] Run cold and warm end-to-end production validations.
- [ ] Run V3/V4 shadow comparison without mutating user output.
- [ ] Record aggregate results in the rollout runbook.
- [ ] Enable for a limited cohort.
- [ ] Monitor corrections, latency, cost and failures.
- [ ] Verify rollback.
- [ ] Make V4 default only after all gates pass.

**State:** 0/8. All real-provider execution is owner-run in deployment.

## 4. Current checkpoint — 2026-08-04

Verified implementation includes:

- additive source, block, typed-record, review-decision and legacy-projection schemas;
- private storage lifecycle and project isolation;
- complete Source Map APIs and RTL teacher UI;
- immutable physical identity plus auditable virtual order;
- typed SourceBlocks/Fragments, crops, bboxes and continuation candidates;
- typed QuestionRecord and unified AnswerSolutionRecord paths;
- tolerant parsing, partial retry, exact reuse and private evidence;
- deterministic matching, duplicate refusal, out-of-scope handling and zero cross-project matches;
- transaction-safe downstream invalidation;
- bounded question/answer batching;
- optional AvalAI OCR evidence adapter, disabled unless selected by environment;
- automatic production extraction dispatch after Source Map confirmation;
- stage/batch/provider observability with safe counters and correlation IDs;
- status, retry and cooperative cancellation APIs/UI;
- exception-only review queue, immutable decisions and finalization;
- backward-compatible projection into `ClassCreationSession.exam_prep_json`;
- idempotent publication into the existing student/invitation/scoring/result flow;
- stale-run recovery and production operations runbook.

Latest contract evidence:

```text
feature head: d7b53393d77c50a53b81f0cba5e7d45367b6c6d8
validated merge ref: fd137cf8779eff5318cea23ca68fb7dc29f4cdb3
workflow: 30862683847
backend job: 91847863122
frontend job: 91847863181
System check: passed
Migration drift: none
Backend: 261 passed, 49 warnings in 26.03s
Frontend focused TypeScript/state tests: passed
Live provider calls: 0
```

Established denominator remains 77 deliverables:

- credited: 50;
- **overall: 50/77 = 64.9%**;
- Phase 8: 5/6;
- Phase 9: 2/6;
- Phase 10: 0/8.

## 5. Production validation contract

The application is now callable end to end in deployment. CI does not validate real provider accuracy.

Deployment must include:

```text
migrations: 0045, 0046
feature flag: EXAM_PREP_V4_ENABLED=True
worker queues: default,pipeline,interactive
models: EXAM_PREP_V4_BLOCK_MODEL / QUESTION_MODEL / ANSWER_MODEL
optional OCR flag: EXAM_PREP_V4_OCR_EVIDENCE_ENABLED
logger: apps.classes.exam_prep_v4
```

The owner validates:

```text
upload → Source Map confirm → correlated extraction → review → projection → publish → student flow
```

Use `docs/runbooks/exam-prep-v4-production-validation.md` for environment, worker command, APIs, log events, counters, cancellation, stale recovery and production test reporting.

## 6. Exact continuation point

Deploy the branch and migrations with a worker consuming `pipeline`. The owner runs real PDFs in production and reports concrete failures by `runId`, `taskId`, page/question and expected/observed behavior. Code continues from those failures while the remaining Phase 9 items—persisted issues, cleanup/deletion/media denial, load sizing and rollout controls—are completed independently. Do not require or run a CI live-provider benchmark.

## 7. Decision log

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
- **D-011:** Operational reports/logs are aggregate/content-free.
- **D-012:** Unmeasured real-quality gates receive no credit.
- **D-013:** Source Map mutations use complete-map optimistic concurrency.
- **D-014:** Source Map UI preserves local edits and privacy.
- **D-015:** Virtual order never changes physical evidence identity.
- **D-016:** Downstream invalidation is transactional and auditable.
- **D-017:** Provider batching remains block-authoritative.
- **D-018:** Production execution is bounded and explicitly correlated.
- **D-019:** Current official AvalAI documentation remains a decision input for provider-dependent changes.
- **D-020:** OCR4 is an optional evidence adapter; existing detector/persistence remain authoritative and default-disabled.
- **D-021:** Real-provider validation is performed manually by the owner in deployment, not CI.
- **D-022:** Exact Source Map confirmation dispatches the current semantic extraction revision.
- **D-023:** Every production extraction run exposes stable `runId` and `taskId` and content-free stage logs.
- **D-024:** Teacher exception decisions are immutable and bound to question/answer/match fingerprints.
- **D-025:** V4 projects into the existing Exam Prep student domain rather than creating a parallel student runtime.
- **D-026:** Publication is idempotent and bound to the reviewed V4 revision and projection fingerprint.
- **D-027:** Cancellation is cooperative and stale runs fail closed while preserving correlation evidence.
