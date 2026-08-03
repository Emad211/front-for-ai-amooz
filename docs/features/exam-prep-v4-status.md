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
- **Documentation synchronization:** canonical roadmap, runbook, status ledger, and local-path manifest template are aligned after the validated code checkpoint

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

Required command behavior:

- requires exactly one explicit mode: `--fake-provider` or `--live-provider`;
- accepts a local non-committed manifest through `--manifest`;
- supports an explicit aggregate JSON output path through `--output`;
- supports an optional model override through `--model`;
- creates one independent project/document per fixture;
- deletes temporary projects and private blobs by default;
- permits `--keep-projects` only with an explicit existing teacher ID;
- returns a nonzero command result when any fixture fails acceptance;
- fails before writes when live model configuration or credentials are missing.

### Manifest contract

- manifest version is fixed at 1;
- exactly three fixtures are required;
- fixture IDs must be unique anonymous lowercase identifiers matching `[a-z0-9][a-z0-9_-]{0,63}`;
- unknown manifest keys are rejected;
- missing/non-PDF files are rejected without echoing paths or filenames;
- page ranges must be contiguous, one-based, and cover the expected page count;
- declared segment roles must match the selected A/B/C structural pattern;
- relative PDF paths are resolved relative to the local manifest;
- the manifest and PDFs remain outside Git.

### Supported structures

- Fixture A: cover → questions → answer/solutions;
- Fixture B: answer/solutions → cover → questions;
- Fixture C: cover → questions → answer/solutions with overlapping answer-number boundaries retained for later phases.

### Aggregate-only report

The report may contain:

- anonymous fixture ID and structural pattern;
- actual/expected page counts;
- role counts and page-role accuracy;
- expected/actual segment ranges and exact-boundary result;
- issue count;
- preparation, cold-classification and warm-reuse latency;
- provider calls, tokens, provider duration and estimated cost;
- independent project count;
- boolean privacy assertions.

The report excludes:

- manifest or PDF paths;
- PDF filenames;
- source hashes and storage keys;
- rendered or thumbnail bytes;
- native/OCR text;
- prompts, model responses and classifier reasons;
- database project/document identifiers;
- credentials and raw provider errors.

### Warm-rerun gate

For an unchanged accepted source classification:

- fingerprint reuse must occur;
- `warmReused` must be true;
- new provider calls must equal 0;
- new tokens and estimated cost must equal 0.

A nonzero warm provider call fails the fixture.

## Synthetic/fake-provider verification

Tests use generated blank PDFs only; no private fixture content is committed or processed in CI.

Verified behaviors include:

- the three documented structural patterns;
- exactly three independent projects even when all PDFs have identical bytes;
- manifest schema and privacy validation;
- aggregate output shape;
- no path or filename disclosure in stdout/report/errors;
- anonymous report-visible fixture IDs;
- default project/blob cleanup;
- exact segment maps;
- zero warm provider calls;
- missing live configuration failure before database writes;
- failed aggregate status and nonzero command exit;
- management-command output and atomic report writing.

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

The warnings are limited to the existing CI-only warning that `backend/staticfiles/` has not been generated while API/private-media tests initialize Django handlers.

Focused V4 CI is green. The full repository is not claimed all-green because unrelated baseline frontend failures remain outside V4.

## Real benchmark acceptance gate

Phase 2 closes only if all three private fixtures in live-provider mode satisfy:

- fixture count: 3;
- independent project count: 3;
- expected page count exact for each fixture;
- page-role accuracy: 100% for each fixture;
- segment map exact for each fixture;
- aggregate report status: `passed`;
- warm provider calls: 0;
- no private source data in stdout or the report.

A boundary or role error leaves Phase 2 open. The failed aggregate must be recorded honestly and the classifier corrected before another live run.

## User action required now

The harness is ready. A real Phase 2 exit-gate run now requires an execution environment that can access both the repository backend and the three private PDFs.

The user must choose and identify the execution environment:

- local development machine; or
- staging/backend server.

On that machine, the following must be available:

1. the three private PDF files;
2. a local manifest based on `docs/runbooks/exam-prep-v4-benchmark-manifest.example.json`;
3. `EXAM_PREP_V4_ENABLED=1`;
4. `EXAM_PREP_V4_CLASSIFICATION_MODEL` or an explicit `--model`;
5. `AVALAI_API_KEY` configured as a local/deployment secret;
6. an aggregate output path outside Git.

Credentials must not be pasted into chat or committed. The user only needs to state which execution environment will be used and ensure the PDFs and secrets are present there.

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

Do not place the key directly in shell history where avoidable; use the local secret mechanism appropriate to the selected environment.

## Next verified step

Wait for the user to identify the execution environment and make the three private PDFs plus provider configuration available there. Then run only the live Phase 2 benchmark, record aggregate pass/fail evidence, and do not begin Phase 3 unless the entire exit gate passes.