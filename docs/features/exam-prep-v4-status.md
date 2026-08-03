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

Progress is calculated from 77 explicit canonical-roadmap deliverables, not commits, lines of code, changed files, or test count.

| Phase | Credited | Total | State |
|---|---:|---:|---|
| Phase 0 | 5 | 6 | Architecture and benchmark contract exist; automated PR ledger enforcement remains open. |
| Phase 1 | 6 | 7 | Models, migration, constraints, and isolation are verified; read-only Django admin remains deferred. |
| Phase 2 | 8 | 9 | Harness exists; the recorded real private-fixture run remains open. |
| Phases 3–10 | 0 | 55 | Not started by design. |

- **Entire V4 roadmap:** **19/77 = 24.7%**
- **Current Phase 2:** **8/9 = 88.9%**

The harness itself does not receive the ninth Phase 2 credit. That credit requires a real-provider run on the three private PDFs and recorded aggregate evidence. Fake-provider success is infrastructure evidence, not model-accuracy evidence.

## Roadmap guardrail

Until the live Phase 2 gate is recorded, do not begin:

- source-map mutations or confirmation;
- V4 frontend/UI;
- full-resolution delivery;
- block detection;
- question extraction;
- answer/solution extraction;
- deterministic matching;
- projection or publication.

## Verified benchmark implementation

### Management command

```text
python backend/manage.py benchmark_exam_prep_v4
```

Behavior:

- requires an explicit `--fake-provider` or `--live-provider` mode;
- accepts a local private manifest through `--manifest`;
- optionally writes aggregate JSON through `--output`;
- optionally accepts `--model`;
- creates one independent project/document per fixture;
- removes benchmark projects and private blobs by default;
- permits `--keep-projects` only with an explicit teacher ID;
- fails before database writes when live model/key configuration is absent;
- returns nonzero if any fixture or aggregate acceptance fails.

### Manifest contract

- `manifestVersion` must be 1;
- exactly three fixtures are required;
- fixture IDs must be unique anonymous lowercase IDs matching `[a-z0-9][a-z0-9_-]{0,63}`;
- unknown fields are rejected;
- unavailable/non-PDF files are rejected without echoing paths or filenames;
- ranges must be contiguous, one-based, and cover the declared page count exactly;
- roles must match one of the three declared structural patterns;
- relative paths resolve from the private manifest directory;
- manifest and PDFs remain outside Git.

### Structural patterns

- **A:** cover → questions → answer/solutions;
- **B:** answer/solutions → cover → questions;
- **C:** cover → questions → answer/solutions, with overlapping answer-number boundaries retained for later extraction phases.

### Aggregate report contract

Allowed:

- anonymous fixture ID and pattern;
- expected/actual page counts;
- page-role counts and accuracy;
- expected/actual segment ranges and exact-boundary result;
- issue count;
- preparation/cold/warm latency;
- provider call, token, provider-duration, and estimated-cost totals;
- warm-reuse and privacy booleans;
- independent project count.

Forbidden:

- source or manifest path;
- PDF filename;
- source hash or storage key;
- image or thumbnail bytes;
- native/OCR text;
- prompts, responses, classifier reasons, or raw model payloads;
- database project/document IDs;
- credentials or raw provider errors.

### Warm-rerun gate

Unchanged accepted classifications must produce:

- `warmReused = true`;
- zero new provider calls;
- zero new tokens;
- zero new estimated cost.

Any nonzero warm call fails the fixture.

## Synthetic/fake-provider verification

CI uses generated blank PDFs only. No private fixture content is committed or processed.

Verified:

- all three A/B/C structures;
- three independent projects even for identical PDF bytes;
- strict manifest validation;
- anonymous fixture IDs;
- no private path/filename leakage in output or errors;
- aggregate-only output shape;
- default project/blob cleanup;
- exact segment maps;
- zero warm calls;
- live preflight before writes;
- false aggregate pass prevention;
- atomic report writing;
- nonzero command exit on failed acceptance.

## Latest focused CI evidence

- **Run:** `30778629588`
- **Job:** `91578823573`
- **Head:** `b9426c0dffafa04aa61cc850b814f4df3feba1b7`
- **Environment:** Python 3.12, PostgreSQL 16, Redis 7

```text
System check identified no issues (0 silenced).
No changes detected in app 'classes'.
128 passed, 33 warnings in 12.36s
```

Warnings are limited to the known CI-only missing generated `backend/staticfiles/` warning. Focused V4 CI is green; unrelated baseline frontend failures mean the entire repository is not claimed all-green.

## Real Phase 2 acceptance gate

All three private fixtures in live mode must satisfy:

- exactly three independent projects;
- exact expected page counts;
- 100% page-role accuracy;
- exact expected segment maps;
- aggregate status `passed`;
- zero warm provider calls;
- no private data in stdout or report.

Any failure leaves Phase 2 open and must be recorded honestly before classifier correction and rerun.

## User action required now

Choose the environment where the real benchmark will run:

1. **local development machine**, or
2. **staging/backend server**.

On that environment make available:

- the three private PDFs;
- a private copy of `docs/runbooks/exam-prep-v4-benchmark-manifest.example.json` with real local paths;
- `EXAM_PREP_V4_ENABLED=1`;
- `EXAM_PREP_V4_CLASSIFICATION_MODEL` or an explicit `--model`;
- `AVALAI_API_KEY` through local/deployment secrets;
- a private aggregate output path outside Git.

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

After the user identifies the execution environment and makes the private PDFs plus provider configuration available there, run only the live Phase 2 benchmark and record aggregate pass/fail evidence. Do not begin Phase 3 unless the entire gate passes.