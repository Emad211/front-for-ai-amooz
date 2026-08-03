# Exam Prep V4 — Implementation Status Ledger

> Updated every V4 implementation turn. Full roadmap: `exam-prep-v4-source-aware-split-pipeline.md`.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **PR:** #4 (Draft)
- **Phase:** 2
- **Completed:** privacy-safe benchmark harness
- **Blocked on:** real three-PDF live-provider benchmark
- **Validated code:** `b9426c0dffafa04aa61cc850b814f4df3feba1b7`
- **CI:** run `30778629588`, job `91578823573`, 128 passed

## Progress

- **Overall:** **24.7% (19/77)**
- **Phase 2:** **88.9% (8/9)**

## Verified

Explicit fake/live modes, strict anonymous three-fixture manifest, independent projects, aggregate-only reports, no private-data leakage, default cleanup, live preflight, failure exit, and zero-call warm reuse.

```text
System check identified no issues (0 silenced).
No changes detected in app 'classes'.
128 passed, 33 warnings in 12.36s
```

## Guardrail

No Phase 3/4, extraction, matching, projection, or publication before the real benchmark is recorded.

## User action required

Choose: **local development machine** or **staging/backend server**. Make the three PDFs, private manifest, V4/model config, secret `AVALAI_API_KEY`, and private output path available there. Never send the credential in chat or Git.

## Next

Run only the real live Phase 2 benchmark and record aggregate pass/fail evidence.