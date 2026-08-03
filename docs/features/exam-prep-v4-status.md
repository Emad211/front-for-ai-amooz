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
- **Documentation state:** canonical roadmap, runbook, ledger, and local-path manifest template are synchronized after the validated code checkpoint

## Progress calculation

Progress is calculated from the 77 explicit checklist deliverables in the canonical roadmap.

- **Entire V4 roadmap:** **19 / 77 = 24.7%**.
- **Current Phase 2 checklist:** **8 / 9 = 88.9%**.

The final Phase 2 credit requires a recorded real-provider run on all three private PDFs. Synthetic/fake-provider success is not model-accuracy evidence.

## Roadmap guardrail

No Phase 3 source-map mutation/UI, Phase 4 block detection, question extraction, answer/solution extraction, matching, projection, or publication work may begin until the real Phase 2 benchmark result is recorded.

## Verified benchmark harness

```text
python backend/manage.py benchmark_exam_prep_v4
```

Verified properties:

- explicit fake or live provider mode;
- strict three-fixture manifest;
- anonymous report-visible fixture IDs;
- one independent project/document per fixture;
- aggregate-only output;
- no private paths, filenames, hashes, keys, images, text, payloads, database IDs, credentials, or raw provider errors;
- default project/private-blob cleanup;
- live configuration preflight before writes;
- nonzero result on failed acceptance;
- unchanged accepted warm reuse with zero new provider calls, tokens, and cost.

## Latest focused evidence

- run `30778629588`;
- job `91578823573`;
- code head `b9426c0dffafa04aa61cc850b814f4df3feba1b7`;
- Python 3.12, PostgreSQL 16, Redis 7.

```text
System check identified no issues (0 silenced).
No changes detected in app 'classes'.
128 passed, 33 warnings in 12.36s
```

## Real benchmark acceptance gate

All three private fixtures must have:

- exact independent project count and page counts;
- 100% page-role accuracy;
- exact segment maps;
- aggregate status `passed`;
- zero warm provider calls;
- no private source data in stdout/report.

Any failure leaves Phase 2 open.

## User action required now

Identify the execution environment:

- local development machine; or
- staging/backend server.

On that environment make available:

1. the three private PDFs;
2. a private copy of `docs/runbooks/exam-prep-v4-benchmark-manifest.example.json` with real local paths;
3. `EXAM_PREP_V4_ENABLED=1`;
4. model configuration;
5. `AVALAI_API_KEY` through a local/deployment secret;
6. a private output path.

Do not paste credentials into chat or commit them.

## Next verified step

After the user identifies the environment and makes the inputs available, run only the live Phase 2 benchmark and record aggregate pass/fail evidence. Do not begin Phase 3 unless the whole exit gate passes.