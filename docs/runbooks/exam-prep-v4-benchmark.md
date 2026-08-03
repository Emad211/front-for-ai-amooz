# Runbook — Exam Prep V4 Source-Aware Benchmark

- **Status:** Operational harness implemented; real private-fixture run pending
- **Branch:** `feat/exam-prep-v4-source-aware`
- **Owner:** Classes / Exam Prep
- **Created:** 2026-08-03
- **Last updated:** 2026-08-03
- **Related design:** `docs/features/exam-prep-v4-source-aware-split-pipeline.md`
- **Example manifest:** `docs/runbooks/exam-prep-v4-benchmark-manifest.example.json`

## Purpose

This runbook defines and operates the Phase 2 classify-and-segment benchmark for Exam Prep V4. Each private PDF remains an independent exam project. The benchmark measures page-role classification, segment boundaries, latency, provider usage, cost, and unchanged warm-rerun reuse before any question or answer extraction begins.

The harness does **not** yet evaluate question recall, answer-solution recall, matching precision, or publication. Those metrics belong to later roadmap phases.

## Implemented command

```bash
python backend/manage.py benchmark_exam_prep_v4 \
  --manifest "$EXAM_PREP_V4_BENCHMARK_MANIFEST" \
  --stage classify-and-segment \
  --fake-provider
```

The command requires an explicit execution mode:

- `--fake-provider`: deterministic, no network, for CI and contract verification;
- `--live-provider`: calls the configured provider and records aggregate usage.

No default mode exists. This prevents accidental provider calls and cost.

## Data-handling rules

1. Never commit source PDFs, rendered pages, filenames, paths, extracted text, answer keys, screenshots, or provider payloads.
2. Keep the manifest and PDFs outside Git or under an ignored private directory.
3. Use only anonymous fixture IDs matching `[a-z0-9][a-z0-9_-]{0,63}`.
4. Every fixture remains a separate `ExamProject` and `ExamSourceDocument`, even when bytes or hashes are equal.
5. The report may contain only anonymous fixture IDs, structural ranges, counts, latency, usage, cost, and boolean acceptance results.
6. The command does not print manifest paths, PDF paths, PDF filenames, storage keys, native text, image bytes, or model payloads.
7. Benchmark projects and private objects are deleted by default after the report is built.
8. `--keep-projects` is allowed only with an explicit existing `--teacher-id`.
9. A failed fixture makes the aggregate status `failed`; partial success is never reported as a pass.

## Manifest schema

The manifest must contain exactly three fixtures:

```json
{
  "manifestVersion": 1,
  "fixtures": [
    {
      "fixtureId": "fixture-a",
      "pattern": "cover_questions_solutions",
      "pdfPath": "/private/path/fixture-a.pdf",
      "expectedPageCount": 16,
      "expectedSegments": [
        {"startPage": 1, "endPage": 1, "role": "cover"},
        {"startPage": 2, "endPage": 8, "role": "questions"},
        {"startPage": 9, "endPage": 16, "role": "answer_solutions"}
      ],
      "expectedQuestionNumbers": {"from": 1, "to": 50},
      "expectedOutOfScopeNumbers": [51, 52, 53, 54]
    }
  ]
}
```

The full example contains fixtures A/B/C. Relative `pdfPath` values are resolved relative to the manifest file. Paths are used internally and are never copied into the report.

### Supported structural patterns

- `cover_questions_solutions`
- `solutions_cover_questions`
- `cover_questions_solutions_overlap`

Segments must:

- start at page 1;
- be contiguous with no gaps or overlap;
- end exactly at `expectedPageCount`;
- match the role order declared by `pattern`.

Unknown manifest keys, duplicate fixture IDs, invalid page ranges, unsupported roles, unavailable PDFs, and non-PDF files fail before any benchmark project is created.

## Fixture matrix

The real benchmark contains three independent exams.

### Fixture A — questions first, solutions second

- pages: 16;
- segment map: `cover 1`, `questions 2–8`, `answer_solutions 9–16`;
- printed question range: 1–50.

### Fixture B — solutions first, cover in the middle, questions last

- pages: 27;
- segment map: `answer_solutions 1–11`, `cover 12`, `questions 13–27`;
- printed question range: 51–115.

### Fixture C — questions first with overlapping solution-number boundaries

- pages: 15;
- segment map: `cover 1`, `questions 2–8`, `answer_solutions 9–15`;
- printed question range: 116–145.

The overlap and out-of-scope number expectations are retained in the local manifest for later extraction phases. The current Phase 2 benchmark scores only page roles and segment boundaries.

## Fake-provider execution

Use fake mode to validate the harness, manifest, storage lifecycle, structural patterns, reporting contract, and warm reuse without network access:

```bash
EXAM_PREP_V4_ENABLED=1 \
python backend/manage.py benchmark_exam_prep_v4 \
  --manifest "$EXAM_PREP_V4_BENCHMARK_MANIFEST" \
  --stage classify-and-segment \
  --fake-provider \
  --output /safe/path/v4-benchmark-fake.json
```

Fake mode uses the expected content-free page roles from the local manifest. It is not evidence of real model accuracy and cannot close the Phase 2 exit gate.

## Live-provider execution

Required environment:

```text
EXAM_PREP_V4_ENABLED=1
EXAM_PREP_V4_CLASSIFICATION_MODEL=<configured model>
AVALAI_API_KEY=<private provider key>
```

Run:

```bash
python backend/manage.py benchmark_exam_prep_v4 \
  --manifest "$EXAM_PREP_V4_BENCHMARK_MANIFEST" \
  --stage classify-and-segment \
  --live-provider \
  --output /safe/path/v4-benchmark-live.json
```

An explicit model may be supplied with `--model`. Missing model configuration or credentials fails before creating benchmark projects.

## Output contract

The report contains:

- `schemaVersion`;
- `mode`;
- aggregate `status`;
- anonymous fixture ID and declared pattern;
- actual and expected page counts;
- page-role accuracy and role counts;
- expected and actual segment maps;
- exact-boundary result;
- issue count;
- preparation, cold-classification, and warm-reuse latency;
- provider calls, tokens, provider duration, and estimated USD cost;
- warm reuse boolean;
- independent project count;
- explicit privacy flags, all of which must remain false.

The report excludes:

- source or manifest path;
- source filename;
- source hash or object key;
- page images;
- native or OCR text;
- model prompt or response payload;
- classifier reasons;
- database project/document IDs;
- credential or provider error details.

## Warm-rerun acceptance

For each unchanged accepted classification:

- the same source, page catalog, contact sheets, model, prompt version, and revision produce the same fingerprint;
- the persisted result is reused;
- new provider calls equal **0**;
- new provider tokens and cost equal **0**.

Any nonzero warm provider call fails that fixture.

## Phase 2 acceptance

A real live run closes Phase 2 only when all three private fixtures satisfy:

- independent project count: 3;
- expected page count exact;
- page-role accuracy: 100%;
- segment map exact: true;
- warm rerun provider calls: 0;
- no private data in stdout or report;
- report status: `passed`.

If the real model misses a boundary or role, Phase 2 remains open and the aggregate report is recorded as failed without moving to Phase 3.

## Cleanup and retention

Default execution deletes benchmark projects, source documents, rendered pages, thumbnails, and private blobs after metrics are collected.

To inspect persisted benchmark records deliberately:

```bash
python backend/manage.py benchmark_exam_prep_v4 \
  --manifest "$EXAM_PREP_V4_BENCHMARK_MANIFEST" \
  --live-provider \
  --teacher-id <existing-teacher-id> \
  --keep-projects
```

Do not use `--keep-projects` in CI or routine benchmark runs.

## Verified synthetic evidence

Focused PostgreSQL CI validates:

- all three documented structural patterns using synthetic blank PDFs;
- three independent projects for equal PDF bytes;
- aggregate-only reporting;
- path and filename non-disclosure;
- default project/blob cleanup;
- exact segment maps;
- zero warm provider calls;
- fail-closed missing configuration;
- invalid manifest rejection;
- failed aggregate nonzero command result.

Latest harness implementation evidence before the final privacy-ID hardening:

```text
System check identified no issues (0 silenced).
No changes detected in app 'classes'.
127 passed, 33 warnings in 12.23s
```

This is synthetic/fake-provider evidence only.

## Benchmark result log

| Date | Commit | Mode | Fixtures | Result | Key notes |
|---|---|---|---|---|---|
| 2026-08-03 | Initial V4 branch | Contract only | A/B/C | Not run | Design contract created. |
| 2026-08-03 | Harness implementation | Fake provider / synthetic | Three structural patterns | Passed | Contract, privacy, cleanup, independence and warm reuse verified; not a live accuracy result. |
| Pending | Pending live checkpoint | Live provider / private | A/B/C | Not run | Requires local private paths, configured model and provider credential. |

## User action required for the real exit gate

After the harness is merged into the working branch, the operator must provide on the execution machine:

1. the local path of each of the three private PDFs;
2. a local manifest based on the example file;
3. `EXAM_PREP_V4_CLASSIFICATION_MODEL`;
4. `AVALAI_API_KEY`.

Do not send credentials in chat or commit them. Configure them as local environment variables or deployment secrets.

## Current completion state

The harness is implemented and fake-provider CI coverage exists. Phase 2 remains **8/9** until the real private fixture run is executed and aggregate evidence is recorded.