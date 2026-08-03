# Exam Prep V4 — Implementation Status Ledger

> Operational companion to `exam-prep-v4-source-aware-split-pipeline.md`.
> Update this file in every implementation turn before moving to another roadmap slice.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **Draft PR:** #4
- **Current phase:** Phase 2 — upload and fast source classification
- **Completed implementation slice:** Privacy-safe private benchmark harness
- **Blocking exit gate:** Real three-fixture live-provider benchmark
- **State:** Harness and synthetic CI are verified; Phase 3 and Phase 4 remain blocked
- **Last updated:** 2026-08-03
- **Latest fully validated code checkpoint:** `b9426c0dffafa04aa61cc850b814f4df3feba1b7`
- **Latest focused evidence:** run `30778629588`, job `91578823573`, 128 tests passed

## Progress calculation

Progress is calculated from 77 explicit canonical-roadmap deliverables.

| Phase | Credited | Total | State |
|---|---:|---:|---|
| Phase 0 | 5 | 6 | Architecture and benchmark contract exist; automated PR ledger enforcement remains open. |
| Phase 1 | 6 | 7 | Models, migration, constraints, and isolation are verified; read-only Django admin remains deferred. |
| Phase 2 | 8 | 9 | Harness exists; the recorded real private-fixture run remains open. |
| Phases 3–10 | 0 | 55 | Not started by design. |

- **Entire V4 roadmap:** **19/77 = 24.7%**
- **Current Phase 2:** **8/9 = 88.9%**

Harness implementation alone does not receive the ninth Phase 2 credit. That credit requires a real-provider run on all three private PDFs and recorded aggregate evidence.

## Roadmap guardrail

Until the live Phase 2 gate is recorded, do not begin source-map mutations/UI, block detection, extraction, matching, projection, or publication.

## Verified benchmark harness

```text
python backend/manage.py benchmark_exam_prep_v4
```

- explicit fake/live provider modes;
- strict exactly-three-fixture manifest;
- anonymous fixture IDs;
- one independent project/document per fixture;
- aggregate-only reports;
- no private paths, filenames, hashes, keys, images, text, payloads, database IDs, credentials, or raw provider errors;
- cleanup by default;
- live preflight before writes;
- nonzero failure result;
- unchanged accepted warm reuse with zero calls/tokens/cost.

## Latest CI evidence

- run `30778629588`;
- job `91578823573`;
- code head `b9426c0dffafa04aa61cc850b814f4df3feba1b7`;
- Python 3.12, PostgreSQL 16, Redis 7.

```text
System check identified no issues (0 silenced).
No changes detected in app 'classes'.
128 passed, 33 warnings in 12.36s
```

## Real acceptance gate

All three live fixtures require exact page counts, 100% page-role accuracy, exact segment maps, aggregate `passed`, zero warm calls, and no private-data leakage. Any failure leaves Phase 2 open.

## User action required now

Choose the execution environment:

1. local development machine; or
2. staging/backend server.

Make available there:

- the three private PDFs;
- a private manifest copy with real paths;
- V4 and model configuration;
- `AVALAI_API_KEY` through secrets, never chat/Git;
- a private aggregate output path.

## Next verified step

Run only the live Phase 2 benchmark after the environment and inputs are available. Record aggregate pass/fail evidence and do not begin Phase 3 unless the whole gate passes.