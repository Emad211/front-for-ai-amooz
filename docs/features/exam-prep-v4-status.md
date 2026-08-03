# Exam Prep V4 — Implementation Status Ledger

> Operational companion to `exam-prep-v4-source-aware-split-pipeline.md`.
> This file is updated in every implementation turn before moving to another roadmap slice.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **Draft PR:** #4
- **Current phase:** Phase 2 — upload and fast source classification
- **Active slice:** Privacy-safe private benchmark harness for the Phase 2 exit gate
- **State:** In progress; Phase 3 source-map mutation and Phase 4 block detection remain prohibited
- **Last updated:** 2026-08-03
- **Latest fully validated checkpoint before this slice:** `65baef2f0c9bc67ce99a978df730ba7fa24d1c84`
- **Latest focused evidence before this slice:** run `30777760405`, job `91576402385`, 114 tests passed

## Progress calculation

Progress is calculated from the 77 explicit checklist deliverables in the canonical roadmap, not from commit count, changed files, test count, or lines of code.

| Phase | Credited | Total | State |
|---|---:|---:|---|
| Phase 0 | 5 | 6 | Architecture and benchmark contract exist; PR-level ledger enforcement remains open. |
| Phase 1 | 6 | 7 | Models, migration and isolation are verified; read-only Django admin inspection remains deferred. |
| Phase 2 | 8 | 9 | Only the private-fixture benchmark exit gate remains open. |
| Phases 3–10 | 0 | 55 | Not started by design. |

- **Entire V4 roadmap:** **19 / 77 = 24.7%**.
- **Current Phase 2 checklist:** **8 / 9 = 88.9%**.

This slice does not receive the final Phase 2 credit until a real private-fixture run is executed and aggregate results are recorded. Building and testing the harness alone is necessary infrastructure, not completion of the live exit gate.

## Roadmap guardrail for this turn

Only the following work is allowed:

1. implement `benchmark_exam_prep_v4` or an equivalent isolated management command;
2. accept a local non-committed JSON manifest containing three independent fixture paths and content-free expected segment ranges;
3. keep every fixture in its own `ExamProject` and `ExamSourceDocument`;
4. support a deterministic fake-provider/dry-run mode for CI;
5. support a real-provider classify-and-segment mode without printing or committing source content;
6. measure aggregate cold latency, page-role counts, segment counts, issue counts, provider calls, tokens and estimated cost;
7. verify unchanged accepted warm reruns make zero provider calls;
8. fail closed for missing files, invalid manifests, absent model configuration or absent credentials;
9. write aggregate JSON only to an explicitly requested output path;
10. update the benchmark runbook and this ledger with exact CI evidence.

Explicitly out of scope:

- source-map role/boundary mutations or confirmation;
- frontend work;
- full-resolution source delivery;
- block detection;
- question extraction;
- answer or solution extraction;
- matching, projection or publication;
- any claim of real fixture accuracy before the private PDFs are actually run.

## Verified implementation before this slice

### Phase 1 foundation

- additive V4 models and migration `classes.0040`;
- `ExamProject`, `ExamSourceDocument`, `ExamSourcePage`, and `ExamSourceSegment`;
- project-scoped isolation, duplicate references, indexes and PostgreSQL constraints;
- one-PDF-one-project behavior even for equal hashes;
- idempotent request/document identifiers;
- V4 feature gating without changing V1/V2/V3 behavior.

### Phase 2 implementation

- private PDF validation and persistence;
- serial bounded-memory page rendering;
- private PNG renders and JPEG thumbnails;
- bounded native-text samples;
- missing-blob restoration and committed-deletion cleanup;
- generic `/media/exam-prep-v4/...` denial;
- tolerant fast page-role classification;
- deterministic current-revision virtual segments;
- input fingerprinting, usage tracking and accepted warm reuse;
- multi-PDF intake with one independent project/task per PDF;
- owner/organization/study-group scope enforcement;
- owner-scoped project list and source-map detail APIs;
- strict private thumbnail streaming with one-query ancestry validation and no storage fallback.

## Latest verified evidence before this slice

- **Run:** `30777760405`
- **Job:** `91576402385`
- **Environment:** Python 3.12, PostgreSQL 16, Redis 7

```text
System check identified no issues (0 silenced).
No changes detected in app 'classes'.
114 passed, 33 warnings in 7.37s
```

Warnings are limited to the CI checkout lacking generated `backend/staticfiles/` while API/private-media tests initialize Django handlers.

## Benchmark harness acceptance criteria

The implementation portion of this slice is complete only when tests prove:

- manifest schema rejects unknown keys, duplicate fixture IDs, missing paths, non-PDF files, invalid page ranges and unsupported roles;
- fixture filenames and absolute paths never appear in standard output or aggregate reports;
- fixture bytes, page images, native text and model payloads are never serialized to output;
- three inputs create three separate projects/documents even if their bytes are identical;
- fake-provider mode reproduces the three documented structures A/B/C without network access;
- aggregate reports contain only fixture IDs, counts, role metrics, boundary metrics, latency, usage totals and warm-reuse results;
- cold provider-call counts are measurable;
- warm reruns verify zero new provider calls after accepted unchanged classification;
- a failed fixture prevents a false aggregate `passed` result;
- temporary benchmark projects and private objects are removed unless an explicit keep flag is supplied;
- system check, migration drift and all focused PostgreSQL tests pass.

## User input or decision boundary

No decision is needed from the user to implement and test the harness with synthetic PDFs and a fake provider.

A real Phase 2 exit-gate run will require the user to provide or identify, on the machine where the command is executed:

1. the three private PDF paths;
2. the local manifest path mapping anonymized fixture IDs A/B/C to those files;
3. a configured classification model and provider credentials.

The harness must be completed first. When the code is ready, the exact command and required local inputs will be requested; no private file or credential will be committed to GitHub.

## Next verified step

Implement only the private benchmark harness, fake-provider CI coverage, aggregate-only report contract and runbook updates. Do not begin Phase 3 or Phase 4 until a real private-fixture benchmark is executed and recorded.