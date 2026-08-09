# Exam Prep Mistral OCR4 — Production Freeze

Branch of record: `experiment/mistral-ocr-layout-probe`

Safety snapshot created before productionization changes:
`snapshot/mistral-ocr-layout-probe-research-freeze-20260809`

## Branch decision

The researched Mistral OCR4 branch is the only source of truth for the new
productionization work. Changes made later on `main`, including Exam Prep V4
source-map/page-confirmation architecture, are not merged into this branch.

The normal product contract is preserved:

`ClassCreationSession -> background task -> ExamPrepPipelineResult -> exam_prep_json`

No new product model, V4 source map, or page-by-page confirmation workflow is
introduced by this productionization effort.

## Stable production entrypoint

All production wiring must enter through:

`apps.classes.services.exam_prep_mistral_production.run_exam_prep_mistral_pipeline`

The signature matches the existing simple PDF pipeline runner and returns the
existing `ExamPrepPipelineResult` type.

## Stage 2: OCR4 production core — complete

The stable runner now implements:

`PDF -> bounded chunks -> Mistral OCR4 blocks -> physical page remap -> booklet ranges -> RTL layout -> question regions -> solution-heading state machine -> targeted gap/invalid recovery -> deterministic assembly`

The paid OCR boundary lives in:

`apps.classes.services.exam_prep_mistral_ocr_transport`

### Bounded transport contract

- all chunks are planned before the first network request;
- a provider chunk contains at most 30 physical PDF pages;
- the default byte cap is 28 MiB per mini-PDF;
- the default response cap is 120 MiB;
- OCR uses blocks and keeps word-confidence evidence for later risk scoring;
- each successful response must contain exactly the local page indexes expected
  for that chunk;
- local provider page indexes are remapped to immutable one-based physical source
  pages before document analysis;
- missing or duplicate page coverage fails closed.

### Retry contract

Only transport errors and the narrow transient HTTP allow-list are retried:

`408, 429, 500, 502, 503, 504`

HTTP 400/401/403/404/409/422-style request/configuration failures are not retried.
A malformed successful response is not retried because repeating a paid request
would only buy the same invalid evidence again.

`Retry-After` is honored when numeric and is bounded to 60 seconds.

### Durable chunk checkpoints

A chunk is checkpointed only after exact page-coverage validation.

Checkpoint objects are written to the repository's private `answer_sources`
storage under the private `exam-prep/source/` namespace. The checkpoint contract
is bound to:

- exact source SHA-256;
- OCR contract fingerprint;
- chunk index;
- exact physical page list;
- exact mini-PDF SHA-256.

A later run validates the checkpoint again before reuse. A corrupt or mismatched
checkpoint is discarded and never trusted. Therefore, if chunk 1 succeeds and a
later chunk fails, a rerun can reuse chunk 1 and pay only for the unfinished
chunk.

### Deterministic numbering and matching

Question anchors are accepted only from pages classified by the research layout
analyzer as `question`; question-like noise on mixed/solution pages is not counted
as a second question anchor.

Question numbers recovered from sequence are retained as review evidence but are
marked production-critical rather than silently trusted. Duplicate question
anchors are also production-critical.

Question and answer/solution records are matched only by printed question number.
There is no fuzzy matching step in Stage 2.

When the booklet cover exposes valid structured ranges, the declared range set is
checked against observed question numbers. A mismatch blocks publication.

### Solution state machine and targeted recovery

The existing conservative solution-heading state machine remains authoritative.
Its supported deterministic recoveries remain local and explicit.

Only missing solution headings or invalid option labels can trigger a targeted
OCR recovery request. The recovery OCR scans selected solution-column crops.
Only explicitly requested question numbers may be merged back. Non-target
headings are ignored even if OCR returns them with apparently strong evidence.
Conflicting labels for a target fail closed.

Targeted crop PDFs use fixed PDF metadata so their bytes are deterministic across
reruns; this keeps checkpoint hashes stable.

### No general LLM work in Stage 2

The Stage 2 runner has no general per-page or per-question LLM call site.
`generalLlmCalls` is reported as zero in the extraction audit. Verifier escalation
is a later stage and remains risk-targeted only.

## Production-safe research primitives

The production boundary may depend on these deterministic/service modules:

- `exam_prep_mistral_ocr_transport`
- `exam_prep_mistral_layout_analysis`
- `exam_prep_mistral_booklet_ranges`
- `exam_prep_mistral_solution_headings`
- `exam_prep_mistral_targeted_recovery`
- `exam_prep_mistral_direct_transcription`
- `exam_prep_avalai_ocr_errors`
- existing non-versioned Exam Prep contracts such as `exam_prep_pipeline`

Adding another dependency to the production entrypoint requires an explicit code
review against the rules below.

## Research-only code kept for reproducibility

These files remain in the repository but are not production runtime dependencies:

- every `management/commands/probe_exam_prep_*` command;
- benchmark/gold/fidelity helpers;
- run-comparison tools;
- benchmark builders and calibration scripts;
- findings/benchmark documents and private diagnostic tooling.

They are intentionally not deleted because they contain the evidence and
reproducible experiments behind production decisions.

## Forbidden production dependencies

The production entrypoint must not import:

- `management.commands`;
- any `exam_prep_v4*` module;
- benchmark/gold/run-comparison modules;
- probe commands.

Dedicated architecture regression tests enforce this boundary.

## Current rollout state

Stage 2 deliberately does **not** replace the current Celery runner yet. The
stable OCR4 runner is implemented and contract-tested, but the branch stays
fail-safe at the product wiring layer until the precise visual pipeline, targeted
LLM verifier, final integrity gate, and UI review work are complete.

## Next stage

Stage 3 builds precise source visual reconciliation and Smart Union Crop behavior
for question visuals, option visuals, tables/graphs/diagrams and solution visuals.
Whole-page or whole-question crops are not accepted as final product visuals when
a precise source region can be established.
