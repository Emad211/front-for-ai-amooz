# Exam Prep V4 — Implementation Status Ledger

> Updated every V4 implementation turn. Full roadmap: `exam-prep-v4-source-aware-split-pipeline.md`.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **PR:** #4 (Draft)
- **Current phase:** Phase 3 — teacher source-map confirmation and virtual tools
- **Active slice:** revision-safe source-map mutation and explicit confirmation backend
- **Phase 2 status:** 8/9 complete; real three-PDF live-provider benchmark explicitly deferred by product owner on 2026-08-03
- **Validated Phase 2 code checkpoint:** `b9426c0dffafa04aa61cc850b814f4df3feba1b7`
- **Latest focused evidence before this slice:** run `30778629588`, job `91578823573`, 128 tests passed

## Product-owner decision — benchmark waiver

The product owner instructed the team to skip the local live benchmark for now and continue development.

This is recorded as a deliberate waiver, not as a successful Phase 2 exit gate:

- the private benchmark harness remains implemented and available;
- the live benchmark deliverable remains open;
- real classifier accuracy, latency, and cost on the three private PDFs remain unmeasured;
- no percentage credit is awarded for the deferred benchmark;
- Phase 3 proceeds conditionally with this known risk;
- the benchmark can be resumed before rollout, extraction tuning, or any production-default decision.

## Progress

Progress is calculated from the 77 explicit roadmap deliverables.

- **Overall:** **19/77 = 24.7%**
- **Phase 2:** **8/9 = 88.9%**, with the final item deferred
- **Phase 3:** **0/7 = 0%** at the start of this slice

## Roadmap scope for this turn

Only the first backend foundation of Phase 3 is allowed:

1. add a revision-safe source-map mutation service;
2. accept a complete page-role map rather than partial implicit edits;
3. validate one-based total page coverage, supported roles, orientation, and contiguous deterministic segments;
4. preserve classifier predictions separately from teacher overrides;
5. increment `classification_revision` atomically on accepted mutation;
6. supersede previous-revision segments without deleting audit history;
7. clear stale classification fingerprint and invalidate stale downstream state;
8. add explicit source-map confirmation bound to the current revision and current projection fingerprint;
9. reject stale revision/fingerprint requests;
10. expose owner-scoped mutation and confirmation endpoints;
11. add PostgreSQL tests for ownership, stale writes, rollback, idempotency, total coverage, and confirmation binding;
12. update this ledger and the canonical roadmap with exact CI evidence.

Explicitly out of scope for this slice:

- frontend/UI;
- page reorder implementation beyond storing validated order metadata;
- split-into-separate-exams action;
- group-documents action;
- block detection;
- question extraction;
- answer/solution extraction;
- matching, projection, or publication.

## Acceptance criteria for this slice

- another teacher receives indistinguishable 404 responses;
- every mutation supplies the expected current revision;
- every page in the source document appears exactly once;
- teacher overrides remain separate from model predictions;
- accepted edits create a new revision and deterministic segment set;
- old segments are retained as `superseded` audit history;
- stale writes and duplicate/reversed/missing pages fail without partial writes;
- confirmation is accepted only for the current revision and exact current source-map fingerprint;
- confirmation is idempotent for the same revision/fingerprint;
- any later edit invalidates prior confirmation;
- no private filename, text, hash, storage key, model payload, or error detail is exposed;
- focused PostgreSQL CI, system check, and migration drift checks pass.

## Current known risk

Because the Phase 2 live benchmark was deferred, Phase 3 is being developed against synthetic and contract-level evidence. Before production rollout or tuning extraction prompts against real documents, the deferred live benchmark must be reconsidered.

## Next verified step

Implement only the revision-safe source-map mutation and confirmation backend. Do not begin UI or Phase 4 block detection until this backend slice passes all focused tests and the roadmap is updated again.