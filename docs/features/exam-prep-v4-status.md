# Exam Prep V4 — Implementation Status Ledger

> Living roadmap execution ledger. Updated in every V4 implementation turn. Canonical roadmap: `exam-prep-v4-source-aware-split-pipeline.md`.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **PR:** #4 — Draft
- **Execution mode:** Critical Path Acceleration
- **Current roadmap span:** Phase 4 → Phase 7 vertical extraction path
- **Last completed slice:** three-project synthetic cold/warm full-pipeline gate and byte-stable retry validation
- **Active slice:** downstream invalidation and provider-call batching before the first private live-provider run
- **Validated code checkpoint:** `bb31ce85671ab5080fcd09c229afa6ba0f9131d6`
- **Focused workflow:** `30825335511`
- **Backend job:** `91725403092`
- **Frontend job:** `91725403209`
- **Last updated:** 2026-08-03

## Progress

Progress is counted only from the 77 canonical roadmap deliverables. A model, service, prompt, commit, or passing synthetic test does not by itself credit a private-fixture accuracy requirement.

| Phase | Credited | Total | State |
|---|---:|---:|---|
| Phase 0 | 5 | 6 | PR-level ledger enforcement remains open. |
| Phase 1 | 6 | 7 | Read-only admin inspection remains deferred. |
| Phase 2 | 8 | 9 | Real private live-provider benchmark remains deferred and uncredited. |
| Phase 3 | 4 | 7 | Core Source Map works; split/group and browser validation remain open. |
| Phase 4 | 3 | 8 | Bounding-box persistence, continuation candidates, and safe block inspection are verified. Real detector accuracy remains open. |
| Phase 5 | 6 | 7 | Typed question path, tolerant validation, private evidence, revisioning, and warm reuse are verified. Private precision/recall remains open. |
| Phase 6 | 4 | 7 | Unified answer-solution records, continuation evidence, complete solution contract, and tolerant retry are verified. Real numbered-heading, answer-key, and inline accuracy remain open. |
| Phase 7 | 6 | 7 | Exact/unique matching, duplicate refusal, out-of-scope handling, provenance, and project isolation are verified. Full option/solution consistency gate remains open. |
| Phases 8–10 | 0 | 20 | Review, projection, hardening, shadow benchmark, and rollout have not started. |

- **Entire V4 roadmap:** **42/77 = 54.5%**
- **Phase 4:** **3/8 = 37.5%**
- **Phase 5:** **6/7 = 85.7%**
- **Phase 6:** **4/7 = 57.1%**
- **Phase 7:** **6/7 = 85.7%**

The increase from 26 to 42 credited deliverables is recorded only after the complete synthetic PDF runner, PostgreSQL suite, migration-drift check, frontend regression gate, cold/warm reuse test, project-isolation tests, and aggregate benchmark command all passed together.

## Product-owner acceleration directive — 2026-08-03

The product owner explicitly requested faster progress toward a real end-to-end pipeline test while preserving the canonical plan.

Execution rules:

1. roadmap order and all safety invariants remain unchanged;
2. work proceeds in larger vertical slices rather than isolated micro-capabilities;
3. deferred work remains visible and receives no credit;
4. the first real fixture path is not blocked on unrelated admin or browser-test infrastructure;
5. privacy, provenance, revision binding, tolerant record validation, deterministic matching, and no-fabrication gates may not be skipped;
6. each vertical slice must pass focused PostgreSQL/backend/frontend gates before the next one is credited;
7. no live-model credential or cost decision is requested until the fake-provider gate is completely green;
8. the roadmap ledger is updated in every implementation turn.

## Closed gate — three-project synthetic full pipeline

The synthetic benchmark now runs three independent PDF projects through the same persistence and matching path used by live mode:

```text
private PDF preparation
→ page rendering and thumbnails
→ source-role classification
→ canonical Source Map fingerprint
→ teacher-style confirmation
→ source block persistence
→ QuestionRecord extraction
→ unified AnswerSolutionRecord extraction
→ deterministic matching
→ aggregate-only report
→ cold/warm comparison
→ private artifact cleanup
```

Verified guarantees:

- each PDF remains an independent `ExamProject`;
- fake and live modes share the same database, provenance, revision, persistence, and matcher path;
- fake mode replaces only provider responses and does not bypass production persistence;
- answer-only records do not create questions;
- out-of-scope answers remain out of scope;
- duplicate or ambiguous numbers are not automatically matched;
- no match can cross an `ExamProject` boundary;
- malformed sibling records remain isolated;
- accepted unchanged warm reruns invoke zero extraction-provider calls;
- command output and report remain aggregate-only;
- source paths, filenames, PDF bytes, images, question text, answer text, solution text, crop data, and raw provider payloads are not emitted;
- benchmark-created database rows and private files are cleaned after the command.

This closes the synthetic infrastructure gate only. It does **not** prove private-fixture OCR, layout detection, formula handling, question recall, answer-solution recall, automatic-match precision, latency, or cost.

## Retry/idempotency correction in this turn

The last failing test was not a production idempotency defect. The production contract intentionally requires:

```text
same client request id
+ same client document id
+ same filename and MIME type
+ same exact PDF SHA-256
```

The affected API tests generated a fresh PDF on each retry. PDF encoder metadata can change the bytes even when the rendered page looks identical, so a valid `409 idempotency_conflict` was produced.

Correction:

- production comparison rules were not weakened;
- retry tests now generate one PDF byte buffer and wrap the same bytes in a new upload object for each request;
- successful dispatch retry, already-ready retry, and ordinary same-byte retry all use exact byte-stable fixtures;
- intentionally different PDF bytes still produce `409` and preserve the accepted private source.

## Verified typed question path

Credited Phase 5 capabilities:

- [x] simple typed `ExamQuestionRecord` schema;
- [x] per-block question extraction path;
- [x] tolerant parser and per-record validation;
- [x] private raw payload, warnings, and ordered block evidence persistence;
- [x] visual ownership through evidence-bound source blocks and block fragments;
- [x] record-set revision, exact fingerprint reuse, and unchanged warm retry;
- [ ] private-fixture precision/recall measurement.

No question may originate from answer-only content. Question inventory is created only from accepted question-bearing blocks.

## Verified unified answer-solution path

Credited Phase 6 capabilities:

- [x] unified `ExamAnswerSolutionRecord` schema;
- [ ] real numbered answer-heading extraction accuracy;
- [x] ordered continuation-block evidence merge;
- [x] correct option or final answer plus complete source solution in one record;
- [ ] compact answer-key sub-pipeline accuracy;
- [ ] inline question-answer sub-pipeline accuracy;
- [x] tolerant per-record validation, revisioning, and exact reuse.

An answer-solution block is rejected when it lacks a complete source solution or lacks both a correct option and final answer. Valid siblings remain usable.

## Verified deterministic matcher

Credited Phase 7 capabilities:

- [x] project-scoped exact normalized section and printed-number matching;
- [x] project-unique printed-number matching;
- [x] duplicate-number refusal;
- [x] out-of-scope classification without question fabrication;
- [ ] complete option-and-solution consistency gate;
- [x] persisted method, reason, fingerprints, and match provenance;
- [x] zero-cross-project-match tests.

Fuzzy similarity is not an automatic matching method.

## Focused verification evidence

Backend environment:

```text
Python 3.12
PostgreSQL 16
Redis 7
```

Backend result:

```text
System check identified no issues (0 silenced).
No changes detected in app 'classes'.
202 passed, 47 warnings in 19.94s
```

Frontend result:

```text
Focused TypeScript check: passed
Source-map state-model tests: passed
```

The warnings remain limited to the CI checkout lacking generated `backend/staticfiles/`. PostgreSQL constraint-error lines in the service-container log are expected negative tests that passed; they are not suite failures.

## Still open and explicitly uncredited

- real content-area, column, RTL reading-order, and numbered-heading detector accuracy;
- project-scoped visual/page deduplication at the block-processing boundary;
- private multi-column, formula, diagram, table, and continuation validation;
- private question and answer-solution precision/recall;
- full option/solution consistency checks;
- browser-level RTL, keyboard, focus, screen-reader, contrast, and visual-regression evidence;
- split and group actions;
- exception-review model and UI;
- student projection and publication;
- stale-task recovery, orphan sweeps, load/concurrency tests, and rollout controls;
- the real three-PDF live-provider benchmark.

## Active slice — downstream invalidation and provider batching

The next roadmap-preserving slice is locked to two prerequisites for a trustworthy and affordable live run.

### A. Downstream invalidation

A changed confirmed Source Map or accepted block-set revision must make prior semantic output non-current before any new extraction result can be accepted.

Required behavior:

1. supersede current QuestionRecords whose evidence belongs to the changed document/block set;
2. supersede current AnswerSolutionRecords whose evidence belongs to the changed document/block set;
3. supersede MatchDecisions that reference either superseded set;
4. retain all historical rows and private evidence for audit;
5. perform invalidation transactionally with the source/block revision change;
6. leave unrelated documents and independent projects untouched;
7. rollback all invalidation when the replacing block/source operation fails.

### B. Provider-call batching

Question and answer-solution extraction may batch compatible blocks to reduce latency and cost, while preserving record-level isolation.

Required behavior:

1. bounded batch size and image payload size;
2. separate question and answer-solution schemas/prompts;
3. each returned record remains bound to an authoritative block id;
4. one malformed record does not reject valid siblings;
5. missing returned block ids become retryable issues, not silent omissions;
6. stronger-model escalation remains block-specific;
7. unchanged accepted units remain excluded from provider calls;
8. aggregate usage remains attributable to project, document, stage, model, and batch.

### Acceptance tests for the active slice

- changing one document never invalidates another project;
- changing one accepted block set supersedes dependent semantic records and matches;
- failed replacement restores prior current records and matches;
- unchanged warm rerun performs zero provider calls;
- batched output with one malformed record preserves healthy siblings;
- missing and duplicate block ids are surfaced as issues;
- no answer-only batch can create a question;
- no batched match crosses a project boundary;
- migration drift, all V4 PostgreSQL tests, and focused frontend regression remain green.

## User action required

**No user action is required now.**

A user decision will be requested only after downstream invalidation and batching pass their gates. At that point the product owner must choose or approve:

1. the live provider/model names;
2. the API credential source;
3. the acceptable maximum test cost;
4. whether the three supplied private PDFs may be sent to that selected provider under its data-handling terms.

The missing booklet containing questions 146–147 will be requested only if those answers must be treated as in-scope rather than intentionally out-of-scope.

## Next verified step

Implement transaction-safe downstream semantic invalidation first. Do not begin batching until invalidation tests pass. Then add bounded provider batching, rerun the complete synthetic cold/warm gate, update this ledger, and request the live-model decision from the product owner.