# Runbook — Exam Prep V4 AvalAI Mistral OCR Smoke

- **Status:** first live evidence run completed eight requests but failed aggregate acceptance; retry instrumentation is ready
- **Branch:** `feat/exam-prep-v4-source-aware`
- **Owner:** Classes / Exam Prep V4
- **Reviewed:** 2026-08-04
- **Production routing:** unchanged
- **Endpoint:** `POST https://api.avalai.ir/v1/ocr`
- **Roadmap ledger:** `docs/features/exam-prep-v4-status.md`

## Official documentation reviewed

AvalAI pages are re-read before every endpoint/model/retry decision:

```text
https://docs.avalai.ir/fa/
https://docs.avalai.ir/fa/api-reference/ocr
https://docs.avalai.ir/fa/examples/processing_documents_with_mistral_ocr
https://docs.avalai.ir/fa/models/mistral-ocr-2512
```

Supplementary upstream Mistral documentation is capability context only and must be measured through AvalAI:

```text
https://docs.mistral.ai/studio-api/document-processing/basic_ocr
https://docs.mistral.ai/studio-api/document-processing/annotations
https://docs.mistral.ai/api/endpoint/ocr
```

## Model and capability interpretation

- `mistral-ocr-2512` is OCR 3.
- `mistral-ocr-4-0` is the reproducible OCR 4 identifier in upstream documentation.
- `mistral-ocr-latest` is used only in the bounded discovery retry because AvalAI currently exposes the alias more consistently; the resolved model returned by each successful response is recorded in aggregate evidence.
- `blocks` is treated as an OCR4 capability that must be measured through AvalAI, not assumed.
- `bbox_annotation` annotates extracted figures/images and is not assumed to replace textual block detection.

No production route may depend on the mutable alias. A production decision must pin a model proven by measured evidence.

## Authorized private fixture

```text
source PDF: دفترچه اول (زیست).pdf on main
question page: physical page 5
answer-solution page: physical page 12
```

The complete PDF is never transmitted. The GitHub runner renders only these two pages locally and sends the two bounded PNG images.

Four isolated modes are evaluated:

```text
markdown
blocks
document_annotation
bbox_annotation
```

Two images × four modes = exactly eight external requests per run.

## Privacy and bounds

```text
max input bytes per rendered page: 12 MiB
max response bytes per request:    24 MiB
max Markdown chars per page:       500,000
max annotation chars:              500,000
request timeout:                   180 seconds
include_image_base64:              false
```

Forbidden from logs, artifacts, serializers, and roadmap evidence:

- source PDF/image bytes or data URLs;
- paths and filenames;
- OCR Markdown and block text;
- annotation payloads;
- questions, answers, and solutions;
- API credentials;
- raw provider response/error bodies.

The aggregate artifact may contain fixture/mode identifiers, model, content-free error class, counts, issue codes, confidence, usage, latency, and opaque request IDs. The workflow log prints a stricter sanitized subset without request IDs or input byte counts.

## First live run — terminal evidence

```text
run: 30852221763
job: 91814702919
requested model: mistral-ocr-4-0
executed requests: 8
command acceptance: false
```

Successful stages:

- API secret validation;
- V4 code checkout;
- sparse checkout of the selected PDF;
- exact 16-page validation;
- local rendering of pages 5 and 12;
- all eight planned OCR request attempts;
- private-file cleanup.

Terminal command output:

```text
Exam Prep V4 AvalAI OCR smoke completed; requests=8; passed=False
CommandError: AvalAI OCR smoke acceptance failed.
```

Interpretation:

- at least one of the eight requests raised a bounded transport, response-parse, or privacy exception;
- merely returning no blocks, no bbox annotations, or no document annotation would not by itself mark a request failed;
- the exact failed mode/error class is unavailable because the old workflow skipped artifact upload after the command returned nonzero;
- the later PR-comment step independently failed with GitHub `403 Forbidden`;
- cleanup then deleted the local report, so the first failed aggregate cannot be reconstructed.

No quality conclusion can be drawn from the first run.

## Failure-evidence patch

Feature branch:

```text
workflow commit: 32913cff94bc58493f09c9abe9f7204985fbabb0
static-test commit: 137518464ec3d2ee60a6051b07432cf6b8832f57
```

Operational workflow on `main`:

```text
commit: 5947a090c927243a1a7402b38cb59539af6a3972
```

The patched workflow now:

1. lets the command complete and write its report even when acceptance is false;
2. prints a content-free per-mode summary;
3. uploads `aggregate-report.json` on pass or fail;
4. retains the artifact for one day;
5. removes the GitHub PR-comment request that returned 403;
6. enforces pass/fail only after evidence upload;
7. always deletes the PDF checkout, rendered pages, and local report.

Focused verification:

```text
workflow: 30853630677
backend job: 91819412114
frontend job: 91819412054
System check identified no issues (0 silenced).
No changes detected in app 'classes'.
236 passed, 47 warnings in 24.09s
Focused TypeScript check: passed
Source-map state tests: passed
```

## Retry contract

The retry is another bounded evidence run, not a production rollout:

```text
model requested: mistral-ocr-latest
inputs: the same two rendered pages
modes: the same four modes
external-request ceiling: 8
artifact retention: 1 day
```

The retry must produce an aggregate artifact even if every request fails. The evidence review must determine:

- status and content-free error class for each mode/page;
- resolved model returned by successful requests;
- Markdown/RTL/formula/table signal counts;
- block/bbox/annotation availability;
- issue codes and latency;
- request IDs for authoritative transaction/cost lookup.

## Decision after the retry

Only measured evidence may select one of these outcomes:

1. **OCR-first candidate:** Markdown/blocks propose SourceBlocks, with vision fallback.
2. **Transcription-only:** Markdown supplies text; current vision detector retains layout ownership.
3. **Diagram-only utility:** bbox/image annotations are useful but text blocks are not.
4. **Rejected for V4:** current vision route remains authoritative.

No roadmap credit or production routing change is granted merely because the requests executed.