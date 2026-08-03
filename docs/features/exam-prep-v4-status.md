# Exam Prep V4 — Implementation Status Ledger

> Operational companion to `exam-prep-v4-source-aware-split-pipeline.md`.
> This file is updated in every implementation turn before moving to another roadmap slice.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **Draft PR:** #4
- **Current phase:** Phase 2 — upload and fast source classification
- **Completed implementation slice:** Privacy-safe private benchmark harness
- **Current gate:** Real private-fixture live-provider benchmark
- **State:** Harness and synthetic CI are verified; progression to Phase 3 is blocked until the real benchmark is run and recorded
- **Last updated:** 2026-08-03
- **Latest fully validated code checkpoint:** `b9426c0dffafa04aa61cc850b814f4df3feba1b7`
- **Latest focused evidence:** run `30778629588`, job `91578823573`, 128 tests passed

## Progress

- **Entire V4 roadmap:** **19 / 77 = 24.7%**.
- **Current Phase 2:** **8 / 9 = 88.9%**.

The final Phase 2 credit requires a recorded real-provider run on all three private PDFs. Synthetic/fake-provider success is not model-accuracy evidence.

## Guardrail

No Phase 3 source-map mutation/UI, Phase 4 block detection, extraction, matching, projection, or publication may begin until the real Phase 2 benchmark is recorded.

## Verified harness

```text
python backend/manage.py benchmark_exam_prep_v4
```

- explicit fake/live provider mode;
- strict three-fixture manifest;
- anonymous fixture IDs;
- independent projects/documents;
- aggregate-only output;
- no private paths, filenames, hashes, keys, images, text, payloads, IDs, credentials, or raw provider errors;
- default cleanup;
- preflight before live writes;
- failed acceptance returns nonzero;
- unchanged accepted warm reuse makes zero new provider calls/tokens/cost.

## Evidence

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

All three private fixtures require exact page/segment maps, 100% page-role accuracy, aggregate `passed`, zero warm provider calls, and no private-data leakage. Any failure leaves Phase 2 open.

## User action required now

Identify the execution environment:

- local development machine; or
- staging/backend server.

On it, make available:

1. the three private PDFs;
2. a private manifest copy with their local paths;
3. V4 enabled;
4. model configuration;
5. `AVALAI_API_KEY` through local/deployment secrets;
6. a private output path.

Do not paste credentials into chat or commit them.

## Next step

After the environment and inputs are available, run only the live Phase 2 benchmark and record aggregate pass/fail evidence. Do not begin Phase 3 unless the entire gate passes.