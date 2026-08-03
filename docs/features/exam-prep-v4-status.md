# Exam Prep V4 — Implementation Status Ledger

> Operational companion to `exam-prep-v4-source-aware-split-pipeline.md`. Updated every implementation turn.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **Draft PR:** #4
- **Phase:** Phase 2
- **Completed slice:** Privacy-safe benchmark harness
- **Blocking gate:** Real three-fixture live-provider benchmark
- **Validated code checkpoint:** `b9426c0dffafa04aa61cc850b814f4df3feba1b7`
- **Evidence:** run `30778629588`, job `91578823573`, 128 tests passed

## Progress

- **Overall:** **19/77 = 24.7%**
- **Phase 2:** **8/9 = 88.9%**

No additional credit is recorded until the real private PDFs pass the live gate.

## Guardrail

Phase 3, Phase 4, extraction, matching, projection, and publication remain blocked.

## Harness verification

- explicit fake/live modes;
- exactly three independent fixtures;
- strict anonymous manifest IDs;
- aggregate-only reports;
- no source paths, filenames, hashes, keys, images, text, model payloads, database IDs, credentials, or raw provider errors;
- cleanup by default;
- live preflight before writes;
- failed acceptance is nonzero;
- warm reuse adds zero provider calls, tokens, and cost.

```text
System check identified no issues (0 silenced).
No changes detected in app 'classes'.
128 passed, 33 warnings in 12.36s
```

## User action required

Choose the real execution environment:

- local development machine; or
- staging/backend server.

Make available there:

1. all three private PDFs;
2. a private copy of the manifest template with real paths;
3. V4 and model configuration;
4. `AVALAI_API_KEY` through secrets, not chat/Git;
5. a private aggregate output path.

## Next step

Run only the real Phase 2 benchmark and record aggregate pass/fail evidence. Do not begin Phase 3 unless the entire gate passes.