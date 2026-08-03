# Exam Prep V4 — Benchmark Runbook

## Current policy

The production critical path does not require a live provider benchmark in CI or before implementation proceeds.

- Development and CI run fake-provider, unit and contract validation only.
- The owner validates real PDFs, latency, provider calls and accuracy manually in deployment.
- Existing live benchmark commands/workflows are optional diagnostic tools and must never run automatically.
- The production operator flow is documented in `exam-prep-v4-production-validation.md`.

## Preferred production validation

Use the deployed teacher flow:

```text
upload
→ Source Map confirmation
→ correlated extraction run
→ exception review
→ projection
→ publish
→ student validation
```

Record:

```text
runId
taskId
stage timings
provider/OCR counters
question/answer/match counts
corrections by page/question
```

Do not paste or publish source text, raw provider payloads, images, storage keys or credentials.

## Offline fake-provider benchmark

The management command remains available for deterministic contract checks without external calls:

```bash
python backend/manage.py benchmark_exam_prep_v4_full_pipeline \
  --manifest /private/path/manifest.json \
  --mode fake_provider \
  --report /private/path/aggregate-report.json
```

Fake mode exercises preparation, Source Map confirmation, block persistence, typed records, matching and warm reuse through the real server-authoritative persistence path. It does not measure provider accuracy.

## Optional owner-triggered live diagnostic

A live run may be performed only when the owner intentionally chooses it in a controlled deployment or private runner. It must have:

- explicit model IDs;
- explicit secrets;
- a hard external-call ceiling;
- no automatic retry or rerun;
- aggregate-only evidence;
- private temporary-file cleanup;
- no raw provider output in comments, logs or artifacts.

Example command shape:

```bash
python backend/manage.py benchmark_exam_prep_v4_full_pipeline \
  --manifest /private/path/manifest.json \
  --mode live_provider \
  --classifier-model "$EXAM_PREP_V4_CLASSIFIER_MODEL" \
  --block-model "$EXAM_PREP_V4_BLOCK_MODEL" \
  --question-model "$EXAM_PREP_V4_QUESTION_MODEL" \
  --answer-model "$EXAM_PREP_V4_ANSWER_MODEL" \
  --max-provider-calls <explicit-ceiling> \
  --report /private/path/aggregate-report.json
```

Enable optional OCR evidence only intentionally:

```text
--ocr-evidence
--ocr-model mistral-ocr-4-0
--ocr-max-attempts 2
--ocr-bbox-for-diagrams
```

To calculate a manifest/config ceiling without project creation or provider access:

```bash
python backend/manage.py benchmark_exam_prep_v4_full_pipeline \
  --manifest /private/path/manifest.json \
  --mode live_provider \
  --model "$EXAM_PREP_V4_BLOCK_MODEL" \
  --show-required-ceiling \
  --report /tmp/not-written.json
```

## Aggregate-only evidence contract

Allowed:

- opaque fixture identifiers and structural ranges;
- page, block, question, answer and match counts;
- issue codes and acceptance booleans;
- cold/warm latency;
- provider calls, tokens, duration and estimated cost;
- request-ceiling plan and consumption;
- OCR call/retry/fallback counts and resolved model IDs;
- opaque request IDs when needed for cost investigation.

Forbidden:

- source filenames or paths;
- PDF/render bytes or data URLs;
- OCR Markdown, block content or annotations;
- question, answer or solution text;
- prompts or raw provider responses;
- object keys, credentials or private errors.

## Acceptance interpretation

A command or workflow being technically successful is not proof of real extraction quality. Production acceptance must be based on owner-inspected output, including:

- Source Map correctness;
- question inventory recall;
- answer-solution completeness;
- correct-option accuracy;
- continuation, diagram and formula ownership;
- deterministic match correctness;
- exception-review burden;
- warm reuse;
- observed latency and cost.

No real-quality roadmap item receives credit solely from a green command or CI workflow.

## Continuation rule

Do not block coding or deployment preparation on an automatic live benchmark. Continue from concrete production failures reported with:

```text
runId
taskId
page or printed question number
expected behavior
observed behavior
safe stage/counter/error information
```

The default operational reference is `docs/runbooks/exam-prep-v4-production-validation.md`.