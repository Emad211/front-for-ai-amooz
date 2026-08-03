# Exam Prep V4 — Implementation Status Ledger

> Living execution ledger. This file is updated in every V4 implementation turn. Canonical roadmap: `exam-prep-v4-source-aware-split-pipeline.md`.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **PR:** #4 — Draft
- **Execution mode:** Critical Path Acceleration
- **Current phase:** Phase 4 — page layout and block detection
- **Last completed slice:** virtual page-order metadata and accessible reorder flow
- **Active slice:** first real vertical extraction path: source pages → deterministic blocks → typed question / answer-solution records → exact matcher
- **Last fully validated branch head before this slice:** `a95c3efa2bbc1d369a16b87ac4b139b532c27be4`
- **Latest focused validation:** workflow `30810029507`, backend job `91674334189`, frontend job `91674334216`
- **Last updated:** 2026-08-03

## Progress

Progress is counted only from the 77 canonical roadmap deliverables.

| Phase | Credited | Total | State |
|---|---:|---:|---|
| Phase 0 | 5 | 6 | PR-level ledger enforcement open. |
| Phase 1 | 6 | 7 | Read-only admin inspection deferred. |
| Phase 2 | 8 | 9 | Real live-provider benchmark deferred by product owner; uncredited. |
| Phase 3 | 4 | 7 | Core Source Map correction path works; split/group and browser-level validation remain open. |
| Phases 4–10 | 0 | 48 | Phase 4 starts in this slice. |

- **Entire V4 roadmap:** **23/77 = 29.9%**
- **Phase 3:** **4/7 = 57.1%**

No Phase 4 credit is recorded until code, migration, and focused tests pass.

## Product-owner acceleration directive — 2026-08-03

The product owner explicitly requested faster progress toward a real end-to-end pipeline test while remaining inside the canonical plan.

The roadmap order is preserved, but execution is changed as follows:

1. work in larger vertical slices rather than one micro-capability per turn;
2. keep every deferred item visible and uncredited;
3. do not block the extraction critical path on nonfunctional infrastructure that is not needed for the first real fixture run;
4. preserve all privacy, provenance, revision, deterministic matching, and no-fabrication gates;
5. run focused PostgreSQL/backend/frontend gates after each vertical slice;
6. return to deferred Phase 0–3 items before rollout or production-default activation.

## Browser-test infrastructure decision

Repository inspection found no installed Playwright, Cypress, or equivalent browser-test framework in `frontend/package.json` or code search.

Therefore:

- no broad browser dependency is added in this slice;
- browser-level RTL/keyboard/accessibility testing remains open and uncredited;
- existing semantic controls, RTL structure, pure state tests, and focused TypeScript checks remain the current evidence;
- browser interaction tests must be completed before Phase 3 is declared fully complete and before rollout;
- this deferral does not permit weakening accessibility implementation.

## Phase 3 retained open items

- explicit split-into-separate-exams action;
- explicit group-documents action;
- browser-level RTL, keyboard, focus, dialog, screen-reader, contrast, and visual-regression evidence.

These items are not required to process the current one-PDF-per-project private fixtures and therefore do not block the first extraction vertical slice.

## Locked architecture for the accelerated vertical slice

```text
confirmed Source Map
→ virtual-order source pages
→ layout observations
→ deterministic source blocks
→ typed QuestionRecord
→ typed AnswerSolutionRecord
→ exact project-scoped match
→ aggregate-only fixture report
```

Hard invariants:

- `pageNumber` remains immutable physical evidence identity;
- `displayOrder` controls virtual processing order;
- blocks always retain document, page, bounding box, and fingerprint provenance;
- question inventory originates only from question-bearing segments;
- answer and full solution remain one unified source record;
- out-of-scope answers never create questions;
- automatic matching uses exact normalized scope and printed number only;
- malformed records are isolated per block and never erase valid siblings;
- private crops, text, provider payloads, and model reasons never enter public serializers or aggregate reports;
- no provider-dependent claim is made until a live fixture run is actually recorded.

## Active Phase 4 slice

The first accelerated slice is limited to the minimum stable block layer needed by both question and answer-solution extraction:

1. add additive `SourceBlock` and evidence-boundary persistence;
2. define block kinds for question, answer-solution, continuation, answer-key, inline question-answer, ignored, and unknown;
3. consume only confirmed current-revision segments;
4. preserve virtual page order and physical page identity;
5. implement deterministic anchor/boundary contract independent from provider integration;
6. allow blocks to continue across page boundaries without losing source-page fragments;
7. persist normalized bounding boxes and ordered fragment provenance;
8. implement block fingerprints and exact warm reuse;
9. expose only owner-scoped safe block summaries for inspection;
10. add PostgreSQL constraints, isolation, idempotency, continuation, rollback, and privacy tests.

## Explicitly out of scope for this slice

- pretending that native text alone solves formulas, diagrams, or two-column RTL pages;
- full semantic question extraction before stable blocks exist;
- answer/solution matching before typed records exist;
- fuzzy automatic matching;
- cross-project or cross-document block merging;
- physical PDF rewriting;
- publication or student projection;
- completing deferred browser tests by assertion without running them.

## Latest verified evidence before Phase 4

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

## User action required

No user action is required for the Phase 4 block-layer implementation.

A user decision will be requested only when one of these becomes necessary:

- choosing a paid/live model or API for the real fixture run;
- uploading a missing booklet needed to resolve out-of-scope records such as printed questions 146–147;
- accepting a new broad dependency that materially affects deployment or maintenance;
- changing the deterministic matching policy.

## Next verified step

Implement and validate the Phase 4 evidence-bound block layer. When it passes, continue immediately into the smallest typed question and unified answer-solution extraction vertical slice instead of stopping for another planning-only turn.