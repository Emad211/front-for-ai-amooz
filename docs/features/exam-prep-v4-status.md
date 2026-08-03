# Exam Prep V4 — Implementation Status Ledger

> Updated every V4 implementation turn. Canonical roadmap: `exam-prep-v4-source-aware-split-pipeline.md`.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **PR:** #4 (Draft)
- **Phase:** 2
- **Completed slice:** privacy-safe benchmark harness
- **Blocking gate:** real three-PDF live-provider benchmark
- **Validated code:** `b9426c0dffafa04aa61cc850b814f4df3feba1b7`
- **CI:** run `30778629588`, job `91578823573`, 128 tests passed

## Progress

- **Overall:** **19/77 = 24.7%**
- **Phase 2:** **8/9 = 88.9%**

The final Phase 2 item is credited only after the real private PDFs pass the live gate.

## Verified harness

- explicit fake/live modes;
- strict three-fixture anonymous manifest;
- independent project/document per PDF;
- aggregate-only output;
- no private path, filename, hash, key, image, text, payload, database ID, credential, or raw provider error disclosure;
- cleanup by default;
- live preflight before writes;
- failed acceptance returns nonzero;
- unchanged warm reuse creates zero provider calls/tokens/cost.

```text
System check identified no issues (0 silenced).
No changes detected in app 'classes'.
128 passed, 33 warnings in 12.36s
```

## Guardrail

Do not start Phase 3, Phase 4, extraction, matching, projection, or publication before recording the live Phase 2 result.

## User action required

Choose where to run it:

1. local development machine; or
2. staging/backend server.

That environment needs the three private PDFs, a private manifest copy with real paths, V4/model configuration, `AVALAI_API_KEY` as a secret, and a private output path. Never send the credential in chat or Git.

## Next step

Run only the live Phase 2 benchmark and record aggregate pass/fail evidence.