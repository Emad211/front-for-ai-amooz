# Exam Prep Mistral OCR4 — Production Freeze

Branch of record: `experiment/mistral-ocr-layout-probe`

Safety snapshot created before productionization changes:
`snapshot/mistral-ocr-layout-probe-research-freeze-20260809`

## Stage 1 decision

The researched Mistral OCR4 branch is the only source of truth for the new
productionization work. Changes made later on `main`, including Exam Prep V4
source-map/page-confirmation architecture, are not merged into this branch.

The normal product contract is preserved:

`ClassCreationSession -> background task -> ExamPrepPipelineResult -> exam_prep_json`

No new product model, V4 source map, or page-by-page confirmation workflow is
introduced by this productionization effort.

## Stable production entrypoint

All future production wiring must enter through:

`apps.classes.services.exam_prep_mistral_production.run_exam_prep_mistral_pipeline`

The signature intentionally matches the existing simple PDF pipeline runner and
returns the existing `ExamPrepPipelineResult` type. Stage 1 leaves it fail-closed
and unwired; Stage 2 implements live OCR transport/runtime coordination behind
that signature.

## Production-safe research primitives

The Stage 1 production boundary may depend on these deterministic/service modules:

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

A dedicated architecture regression test enforces this boundary.

## Stage 1 non-goals

Stage 1 does **not**:

- change the current Celery task runtime;
- call AvalAI;
- run a benchmark;
- change frontend/UI behavior;
- merge or cherry-pick V4/main changes;
- alter existing research services.

Those changes begin only after this freeze boundary is established.

## Next stage

Stage 2 implements the bounded OCR4 document transport/runtime coordinator behind
the stable entrypoint, including page/chunk coverage, retry/checkpoint policy and
conversion toward the existing `ExamPrepPipelineResult` contract. The Celery task
is wired only after that runner is complete and its network-free contract tests
pass.
