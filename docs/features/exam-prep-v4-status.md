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

Progress is calculated from the 77 explicit checklist deliverables in the canonical roadmap, not from commit count, changed files, test count, or lines of code.

| Phase | Credited | Total | State |
|---|---:|---:|---|
| Phase 0 | 5 | 6 | Architecture and benchmark contract exist; PR-level ledger enforcement remains open. |
| Phase 1 | 6 | 7 | Models, migration and isolation are verified; read-only Django admin inspection remains deferred. |
| Phase 2 | 8 | 9 | The harness exists; the real three-fixture live benchmark is the only open Phase 2 deliverable. |
| Phases 3–10 | 0 | 55 | Not started by design. |

- **Entire V4 roadmap:** **19 / 77 = 24.7%**.
- **Current Phase 2 checklist:** **8 / 9 = 88.9%**.

The percentage does not increase for harness implementation alone. The ninth Phase 2 deliverable is credited only after all three private PDFs are executed with the real configured provider and the aggregate results are recorded. Synthetic/fake-provider success is not model-accuracy evidence.

## Roadmap guardrail

No Phase 3 source-map mutation, Phase 3 UI, Phase 4 block detection, question extraction, answer/solution extraction, matching, projection or publication work may begin until the real Phase 2 benchmark result is recorded.

The only permitted next operation is:

1. place or identify the three private PDFs on the selected execution machine;
2. create a local, non-committed manifest from `docs/runbooks/exam-prep-v4-benchmark-manifest.example.json`;
3. configure the real classification model and provider credential as local/deployment secrets;
4. run `benchmark_exam_prep_v4 --live-provider`;
5. inspect only the aggregate report;
6. record pass/fail evidence in the runbook and this ledger;
7. recalculate progress only if the full Phase 2 exit gate passes.

## Verified benchmark harness

### Management command

```text
python backend/manage.py benchmark_exam_prep_v4
```

- requires exactly one explicit mode: `--fake-provider` or `--live-provider`;
- accepts a local non-committed manifest through `--manifest`;
- supports aggregate JSON output through `--output`;
- supports optional `--model` override;
- creates one independent project/document per fixture;
- deletes temporary projects and private blobs by default;
- permits `--keep-projects` only with an explicit existing teacher ID;
- returns nonzero when any fixture fails;
- fails before writes when live model configuration or credentials are missing.

### Manifest and privacy contract

- exactly three fixtures and manifest version 1;
- anonymous unique IDs matching `[a-z0-9][a-z0-9_-]{0,63}`;
- strict unknown-key, page-range, role, pattern, file-existence, and PDF validation;
- no paths, filenames, hashes, keys, image bytes, text, payloads, database IDs, credentials, or raw provider errors in reports;
- structures A/B/C retained independently;
- warm reuse requires zero new provider calls, tokens, and cost.

## Latest focused CI evidence

- **Run:** `30778629588`
- **Job:** `91578823573`
- **Head:** `b9426c0dffafa04aa61cc850b814f4df3feba1b7`
- **Environment:** Python 3.12, PostgreSQL 16, Redis 7
- **Result:** success

```text
System check identified no issues (0 silenced).
No changes detected in app 'classes'.
128 passed, 33 warnings in 12.36s
```

Warnings are limited to the existing CI-only missing generated `backend/staticfiles/` warning.

## Real benchmark acceptance gate

Phase 2 closes only if all three private fixtures in live-provider mode satisfy:

- fixture count and independent project count: 3;
- exact page count per fixture;
- 100% page-role accuracy;
- exact segment map;
- aggregate status `passed`;
- zero warm provider calls;
- no private source data in stdout/report.

Any failure keeps Phase 2 open and must be recorded honestly before classifier correction.

## User action required now

State which environment will run the real benchmark:

- local development machine; or
- staging/backend server.

On that environment, make available:

1. the three private PDFs;
2. a private local copy of the manifest template with real paths;
3. `EXAM_PREP_V4_ENABLED=1`;
4. model configuration;
5. `AVALAI_API_KEY` through local/deployment secrets;
6. a private aggregate output path.

Do not paste credentials into chat or commit them.

## Exact live command

```bash
EXAM_PREP_V4_ENABLED=1 \
EXAM_PREP_V4_CLASSIFICATION_MODEL=<configured-model> \
AVALAI_API_KEY=<configured-secret> \
python backend/manage.py benchmark_exam_prep_v4 \
  --manifest "$EXAM_PREP_V4_BENCHMARK_MANIFEST" \
  --stage classify-and-segment \
  --live-provider \
  --output /safe/private/path/v4-benchmark-live.json
```

## Next verified step

Wait for the user to identify the execution environment and make the private PDFs plus provider configuration available there. Then run only the live Phase 2 benchmark, record aggregate pass/fail evidence, and do not begin Phase 3 unless the entire exit gate passes.