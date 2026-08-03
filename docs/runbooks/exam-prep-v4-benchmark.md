# Runbook — Exam Prep V4 Private Full-Pipeline Benchmark

- **Status:** harness, OCR adapter, request budget and one-click workflow verified; live three-PDF run pending one manual dispatch
- **Branch:** `feat/exam-prep-v4-source-aware`
- **Updated:** 2026-08-04
- **Roadmap:** `docs/features/exam-prep-v4-source-aware-split-pipeline.md`
- **Ledger:** `docs/features/exam-prep-v4-status.md`

## Purpose

This runbook operates one independent cold/warm V4 extraction benchmark for each of the three private PDFs. It measures classification, segments, block proposals, typed question/answer extraction, matching, latency, usage, OCR retry/fallback and unchanged warm reuse without publishing user output.

## Fixture contract

### Fixture A

```text
file: دفترچه اول (زیست).pdf
pages: 16
cover: 1
questions: 2–8
answer_solutions: 9–16
question numbers: 1–50
out of scope: 51–54
```

### Fixture B

```text
file: دفترچه دوم .pdf
pages: 27
answer_solutions: 1–11
cover: 12
questions: 13–27
question numbers: 51–115
out of scope: 49, 50, 116, 117
```

### Fixture C

```text
file: دفترچه سوم.pdf
pages: 15
cover: 1
questions: 2–8
answer_solutions: 9–15
question numbers: 116–145
out of scope: 114, 115, 146, 147
```

Each fixture remains a separate project. Equal hashes, page similarity and overlapping numbers never merge projects.

## Command

```bash
python backend/manage.py benchmark_exam_prep_v4_full_pipeline \
  --manifest /private/manifest.json \
  --mode live_provider \
  --classifier-model gemini-2.5-flash \
  --block-model gemini-2.5-flash \
  --question-model gemini-2.5-flash \
  --answer-model gemini-2.5-flash \
  --ocr-evidence \
  --ocr-model mistral-ocr-4-0 \
  --ocr-max-attempts 2 \
  --ocr-bbox-for-diagrams \
  --max-provider-calls 484 \
  --report /private/aggregate-report.json
```

To calculate the ceiling without creating projects or calling providers:

```bash
python backend/manage.py benchmark_exam_prep_v4_full_pipeline \
  --manifest /private/manifest.json \
  --mode live_provider \
  --model gemini-2.5-flash \
  --ocr-evidence \
  --ocr-model mistral-ocr-4-0 \
  --ocr-max-attempts 2 \
  --ocr-bbox-for-diagrams \
  --show-required-ceiling \
  --report /tmp/not-written.json
```

## Hard request ceiling

Recorded manifest calculation:

```text
classification invocations: 3
possible structured block fallbacks: 6
semantic batch invocations: 79
structured invocations: 88
structured external upper bound: 264
OCR-eligible pages: 55
OCR external upper bound: 220
required minimum: 484
```

The bound is deliberately conservative:

- every structured invocation reserves JSON mode, one response-format fallback and one repair;
- every eligible page reserves two primary OCR attempts and two possible bbox attempts;
- structured detector fallback is reserved for every non-cover segment;
- the runtime guard still stops before the next call if provider output creates more work than the manifest predicted.

A ceiling below 484 fails before project creation or provider access.

## Aggregate report

Allowed:

- anonymous fixture IDs and structural ranges;
- page, block, question, answer and match counts;
- issue counts and acceptance booleans;
- cold/warm latency;
- provider calls, tokens, duration and estimated cost;
- request-ceiling plan and consumption;
- OCR calls, retries, primary successes, bbox calls, fallback counts/reasons and resolved model IDs;
- opaque request IDs when needed for transaction-cost lookup.

Forbidden:

- filenames and paths in report output;
- PDF/render bytes or data URLs;
- OCR Markdown/block content/annotations;
- questions, answers or solutions;
- prompts and raw provider responses;
- object keys, database IDs and credentials.

The workflow stores either the aggregate report or a content-free failure summary for one day.

## Acceptance gates

### Phase 2

- exactly three independent projects;
- page counts exact;
- page-role and segment boundaries exact;
- unchanged warm classification calls: zero.

### Phase 4

- stable bounded blocks before semantic extraction;
- numbered headings retained;
- multi-column/RTL/diagram/continuation evidence reviewable;
- fallback/retry behavior recorded.

### Phase 5

- question recall at least 99%;
- no question fabricated from answer-only evidence.

### Phase 6

- in-scope answer-solution recall at least 99%;
- answer and complete source solution boundaries correct;
- out-of-scope answers do not create questions.

### Phase 7

- automatic match precision 100%;
- zero cross-project matches;
- duplicate/ambiguous numbers remain unresolved;
- warm extraction/OCR calls: zero.

A failed gate is recorded as failed; it is not silently waived or converted into roadmap credit.

## Cleanup

Benchmark projects and their private artifacts are deleted by default after aggregate metrics are built. The GitHub runner also deletes the sparse private fixture checkout and temporary files in an `always()` step.

Do not use `--keep-projects` in the GitHub workflow.

## Verification before live execution

Benchmark guard and workflow contract:

```text
feature checkpoint: 5db6e4b7eab2d4ae3150b79d342b8cfc93b107c9
workflow: 30857010156
backend job: 91830257210
frontend job: 91830257126
validated merge ref: 54e401d067c596444b20e1c4497d77fd7ad58615
System check: passed
Migration drift: none
Backend: 252 passed, 47 warnings in 25.62s
Frontend focused TypeScript/state tests: passed
```

## GitHub Actions execution

```text
workflow: .github/workflows/exam-prep-v4-full-live-benchmark.yml
main commit: 5903d08fc3f58d8625f4ddf80fdccd92949b1ac6
secret: AVALAI_API_KEY
```

The workflow is `workflow_dispatch` only, has no input field, never retries automatically, uses PostgreSQL/Redis, verifies the 484 ceiling before provider access, and uploads only `exam-prep-v4-full-live-aggregate` with one-day retention.

Run exactly once:

```text
GitHub → Actions → exam-prep-v4-full-live-benchmark → Run workflow
```

After terminal evidence is recovered, remove this workflow from `main`, update the roadmap/runbooks, and decide which private gates are closed.