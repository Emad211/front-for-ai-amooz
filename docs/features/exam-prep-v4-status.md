# Exam Prep V4 — Implementation Status Ledger

> Living execution ledger. Update this file before every V4 implementation step. Canonical roadmap: `exam-prep-v4-source-aware-split-pipeline.md`.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **PR:** #4 — Draft
- **Execution mode:** Critical Path Acceleration
- **Current roadmap span:** Phase 4 → Phase 7 vertical extraction path
- **Last completed slice:** diagnosed the first live OCR run and implemented pass/fail aggregate-evidence preservation
- **Active gate:** run one bounded evidence-preserving OCR retry, inspect the aggregate artifact, and decide the OCR role in V4
- **First live run:** `30852221763`
- **First live job:** `91814702919`
- **First-run external requests:** **8 completed**
- **First-run result:** aggregate acceptance false; original failed report lost by old workflow
- **Evidence-preservation workflow commit:** `32913cff94bc58493f09c9abe9f7204985fbabb0`
- **Evidence-preservation static-test commit:** `137518464ec3d2ee60a6051b07432cf6b8832f57`
- **Operational workflow on main:** `5947a090c927243a1a7402b38cb59539af6a3972`
- **Focused verification workflow:** `30853630677`
- **Backend job:** `91819412114`
- **Frontend job:** `91819412054`
- **Focused result:** **236 backend tests passed; frontend focused validation passed**
- **Last updated:** 2026-08-04

## Progress

Progress is counted only from the 77 canonical roadmap deliverables.

| Phase | Credited | Total | State |
|---|---:|---:|---|
| Phase 0 | 5 | 6 | PR ledger enforcement remains open. |
| Phase 1 | 6 | 7 | Read-only admin inspection remains deferred. |
| Phase 2 | 8 | 9 | Real private classification benchmark remains open and uncredited. |
| Phase 3 | 4 | 7 | Core Source Map works; split/group and browser validation remain open. |
| Phase 4 | 3 | 8 | Block persistence/continuation/inspection are verified; real OCR/layout quality remains open. |
| Phase 5 | 6 | 7 | Typed question path is verified; private precision/recall remains open. |
| Phase 6 | 4 | 7 | Unified answer-solution path is verified; real heading/answer-key/inline quality remains open. |
| Phase 7 | 6 | 7 | Deterministic matching is verified; complete consistency gate remains open. |
| Phases 8–10 | 0 | 20 | Not started. |

- **Entire V4 roadmap:** **42/77 = 54.5%**
- **Phase 4:** **3/8 = 37.5%**
- **Phase 5:** **6/7 = 85.7%**
- **Phase 6:** **4/7 = 57.1%**
- **Phase 7:** **6/7 = 85.7%**

No progress credit is added before measured private evidence closes a canonical deliverable.

## Roadmap and privacy invariants

1. every uploaded PDF remains an independent project by default;
2. physical page identity, project scope, and evidence provenance remain authoritative;
3. questions originate only from accepted question-bearing evidence;
4. answer-only content never creates questions;
5. answer and complete source solution remain one record;
6. automatic matching remains deterministic and project-scoped;
7. ambiguous evidence remains unresolved rather than guessed;
8. malformed provider siblings remain isolated;
9. accepted unchanged units are excluded from provider calls;
10. private bytes, OCR text, annotations, credentials, and raw provider output remain outside logs and roadmap evidence;
11. historical revisions remain auditable;
12. production routing is unchanged by the smoke;
13. Phase 8 and rollout remain blocked;
14. the retry must preserve aggregate evidence before reporting success or failure.

## AvalAI documentation rule

Before every AvalAI-dependent change or execution:

1. update this ledger;
2. re-read the current official AvalAI documentation;
3. separate documented, inferred, and measured behavior;
4. never infer retention/training/residency guarantees;
5. update `docs/runbooks/exam-prep-v4-avalai-ocr-smoke.md`.

## First live run — proven facts

```text
run: 30852221763
job: 91814702919
requested model: mistral-ocr-4-0
executed requests: 8
command output: requests=8; passed=False
```

- PDF checkout and local page rendering succeeded.
- The complete PDF was not sent; only pages 5 and 12 were rendered and transmitted.
- At least one request raised a bounded transport/response/privacy exception.
- Empty blocks or absent annotations alone would not cause request failure.
- The old workflow skipped artifact upload after the command returned nonzero.
- The old PR-comment step separately failed with GitHub `403 Forbidden`.
- Cleanup deleted the local failed report, so per-mode failure details cannot be recovered.

## Closed gate — failed-evidence preservation

The patched workflow now:

- runs the command with `continue-on-error`;
- requires the aggregate report to exist with eight result rows;
- prints only a sanitized per-mode summary;
- uploads the aggregate artifact on pass or fail;
- retains it for one day;
- removes the failing PR-comment request;
- enforces terminal pass/fail only after upload;
- always deletes private temporary files.

The bounded discovery retry requests `mistral-ocr-latest`; each successful result records the model actually returned. This alias is not approved for production routing.

Verification:

```text
System check identified no issues (0 silenced).
No changes detected in app 'classes'.
236 passed, 47 warnings in 24.09s
Focused TypeScript check: passed
Source-map state tests: passed
```

## Authorized retry fixture

```text
source PDF: دفترچه اول (زیست).pdf
question page: 5
answer-solution page: 12
requested model: mistral-ocr-latest
modes: markdown, blocks, document_annotation, bbox_annotation
hard ceiling: 8 additional requests
```

The user previously granted broad permission for live testing and explicitly requested fast progress with real tests. The retry remains bounded to the same two images and eight requests.

## User action required now

Run the updated workflow once:

```text
Actions
→ exam-prep-v4-avalai-ocr-one-shot
→ Run workflow
→ Branch: main
→ Run workflow
```

There is no confirmation textbox in the updated workflow. Do not run it more than once.

## Exact continuation point

After the retry starts, inspect its job and aggregate artifact. Record per-mode status/error classes, resolved model, counts, latency, and request IDs/cost lookup. Then remove the one-shot workflow from `main` and decide OCR-first, transcription-only, diagram-only, or rejected. Do not change the 42/77 score or production routing before reviewing that evidence.