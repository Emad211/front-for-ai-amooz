# Exam Prep V4 — Implementation Status Ledger

> Updated every V4 implementation turn. Full roadmap: `exam-prep-v4-source-aware-split-pipeline.md`.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **PR:** #4 (Draft)
- **Phase:** 2
- **Completed:** privacy-safe benchmark harness
- **Blocking gate:** real three-PDF live-provider benchmark
- **Selected execution environment:** local Windows development machine
- **Validated code:** `b9426c0dffafa04aa61cc850b814f4df3feba1b7`
- **CI:** run `30778629588`, job `91578823573`, 128 passed

## Progress

- **Overall:** **24.7% (19/77)**
- **Phase 2:** **88.9% (8/9)**

The final Phase 2 item is credited only after the real private PDFs pass the local live-provider gate and aggregate evidence is recorded.

## Verified

Explicit fake/live modes, strict anonymous three-fixture manifest, independent projects, aggregate-only reports, no private-data leakage, default cleanup, live preflight, failure exit, and zero-call warm reuse.

```text
System check identified no issues (0 silenced).
No changes detected in app 'classes'.
128 passed, 33 warnings in 12.36s
```

## Guardrail

No Phase 3/4, extraction, matching, projection, or publication before the local live benchmark result is recorded.

## User action now

On the local Windows machine:

1. check out and update `feat/exam-prep-v4-source-aware`;
2. prepare Python, PostgreSQL, and Redis;
3. place the three private PDFs in a private directory outside Git;
4. create a local manifest from `docs/runbooks/exam-prep-v4-benchmark-manifest.example.json`;
5. configure `EXAM_PREP_V4_ENABLED`, database/Redis settings, the classification model, and `AVALAI_API_KEY` locally;
6. run the fake-provider smoke test;
7. run the live-provider benchmark;
8. return only the aggregate JSON report or its non-sensitive metrics for roadmap recording.

Never paste the provider credential into chat or commit it.

## Next

Run only the local fake smoke test and then the local live Phase 2 benchmark. Record aggregate pass/fail evidence before any Phase 3 work.