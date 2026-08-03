# Exam Prep V4 — Implementation Status Ledger

> Living execution ledger. Updated in every V4 implementation turn. Canonical roadmap: `exam-prep-v4-source-aware-split-pipeline.md`.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **PR:** #4 — Draft
- **Execution mode:** Critical Path Acceleration
- **Current roadmap span:** Phase 4 → Phase 7 vertical extraction path
- **Last completed slice:** evidence-bound Source Block persistence
- **Active slice:** typed QuestionRecord + unified AnswerSolutionRecord + deterministic matcher
- **Validated code checkpoint:** `6e411e4483bfdb19b176731df24400c4ad60ed3f`
- **Focused workflow:** `30811932130`
- **Backend job:** `91680491219`
- **Frontend job:** `91680491251`
- **Last updated:** 2026-08-03

## Progress

Progress is counted only from the 77 canonical roadmap deliverables.

| Phase | Credited | Total | State |
|---|---:|---:|---|
| Phase 0 | 5 | 6 | PR-level ledger enforcement open. |
| Phase 1 | 6 | 7 | Read-only admin inspection deferred. |
| Phase 2 | 8 | 9 | Real live-provider benchmark deferred by product owner; uncredited. |
| Phase 3 | 4 | 7 | Core Source Map works; split/group and browser validation remain open. |
| Phase 4 | 3 | 8 | Bounding-box evidence, continuation candidates, and safe inspection API verified. |
| Phases 5–10 | 0 | 40 | Typed extraction slice starts now. |

- **Entire V4 roadmap:** **26/77 = 33.8%**
- **Phase 4:** **3/8 = 37.5%**

No Phase 5–7 credit is recorded until typed persistence and matcher tests pass.

## Product-owner acceleration directive — 2026-08-03

The product owner explicitly requested faster progress toward a real end-to-end pipeline test while preserving the canonical plan.

Execution rules:

1. roadmap order and all safety invariants remain unchanged;
2. work proceeds in larger vertical slices rather than isolated micro-capabilities;
3. deferred work remains visible and receives no credit;
4. the first real fixture path is not blocked on unrelated admin or browser-test infrastructure;
5. privacy, provenance, revision binding, tolerant record validation, deterministic matching, and no-fabrication gates may not be skipped;
6. each vertical slice must pass focused PostgreSQL/backend/frontend gates before the next one is credited.

## Browser-test infrastructure decision

Repository inspection found no installed Playwright, Cypress, or equivalent browser-test framework. No broad dependency was added. Browser-level RTL, keyboard, focus, screen-reader, contrast, and visual-regression evidence remains open and uncredited and must be completed before rollout.

## Verified Phase 4 Source Block layer

Migration:

```text
classes.0043_exam_prep_v4_source_blocks
```

Models:

```text
ExamSourceBlock
ExamSourceBlockFragment
```

Block kinds:

```text
question
answer_solution
answer_key
inline_question_answer
continuation
ignored
unknown
```

Verified guarantees:

- blocks can only be persisted against the exact current confirmed Source Map revision and fingerprint;
- every block belongs to one current confirmed segment;
- every fragment belongs to an immutable source page inside that segment;
- bounding boxes are normalized, positive, and database-constrained;
- fragments follow virtual page order while retaining physical `pageNumber` identity;
- a logical block may own several ordered page fragments;
- continuation candidates may link only to an earlier block in the same document and block revision;
- block and complete-set fingerprints support exact warm reuse;
- an unchanged retry creates no new revision or provider-visible work;
- changed sets supersede previous revisions without deleting history;
- failed replacement rolls back supersession, fragments, project state, and new revisions together;
- an individual source page with active evidence is protected from deletion while project deletion still cascades cleanly;
- owner-scoped block inspection exposes only kind, order, printed number, confidence, segment role/order, safe page numbers, display positions, bounding boxes, columns, and continuation flags;
- raw metadata, text, provider payloads, source fingerprints, storage identifiers, and private error details remain hidden.

Safe endpoint:

```text
GET /api/classes/exam-prep-v4/projects/<project_id>/documents/<document_id>/blocks/
```

## Phase 4 credit boundaries

Credited:

- [x] source crops and bounding-box persistence;
- [x] continuation candidates;
- [x] block inspection endpoints.

Still open and uncredited:

- [ ] content-area and column detection;
- [ ] RTL reading-order detector;
- [ ] numbered-heading detector;
- [ ] project-scoped page deduplication at block-processing boundary;
- [ ] real multi-column/formula/diagram fixture validation.

The block schema is ready, but provider/layout detection accuracy has not yet been claimed.

## Focused verification evidence

Backend:

```text
System check identified no issues (0 silenced).
No changes detected in app 'classes'.
178 passed, 46 warnings in 13.09s
```

Frontend regression gate:

```text
Focused TypeScript check: passed
Source-map state-model tests: 8 passed, 0 failed
```

The first block-layer run exposed one stale in-memory test expectation. Production rollback behavior was correct; the test was refreshed against persisted state and the next run passed without changing service semantics.

## Active typed-record and matcher slice

The next accelerated slice implements the smallest complete semantic path over accepted blocks:

```text
accepted question block
→ tolerant QuestionRecord candidate
→ persisted question inventory

accepted answer_solution block + continuation chain
→ tolerant unified AnswerSolutionRecord candidate
→ persisted answer and full solution together

question inventory + answer-solution records
→ exact project-scoped deterministic MatchDecision
```

Locked invariants:

- QuestionRecord can originate only from `question` or approved inline question-bearing blocks;
- AnswerSolutionRecord can originate only from answer-solution, answer-key, or approved inline blocks;
- full solution and correct answer remain in one record and one evidence chain;
- content fields are private and never emitted from the safe structural API;
- source block and block-set fingerprints bind every record to evidence;
- malformed model records are isolated per block and cannot erase valid siblings;
- exact normalized printed number and logical scope are the only automatic keys;
- duplicate question numbers refuse automatic matching;
- answers absent from question inventory become `out_of_scope` and never create questions;
- missing numbers remain unresolved;
- match decisions retain explicit provenance and may be recomputed idempotently;
- no cross-project or stale-block match is possible.

## Explicitly out of scope for the active slice

- live provider selection or tuning;
- claiming OCR/vision accuracy from synthetic payloads;
- fuzzy automatic matching;
- teacher exception-review UI;
- final student projection or publication;
- physical PDF rewriting;
- completing deferred browser tests by assertion.

## User action required

No user action is required for typed-record persistence and deterministic matching.

A user decision will be requested before the first live three-PDF run only when a concrete live model/API credential and expected cost must be selected. The missing booklet containing source questions 146–147 will be requested only if those records must be treated as in-scope rather than intentionally out-of-scope.

## Next verified step

Implement migration-backed typed records, tolerant per-block persistence, exact deterministic matching, safe aggregate inspection, and zero-cross-project tests. When green, add the provider adapter and fixture runner needed for the first real three-PDF pipeline execution.