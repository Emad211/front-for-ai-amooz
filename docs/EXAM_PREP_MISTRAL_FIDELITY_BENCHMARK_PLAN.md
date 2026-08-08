# Exam Prep Mistral OCR Fidelity Benchmark Plan

Status: diagnostic experiment only. Production pipeline remains unchanged.

## Objective

Measure whether Mistral OCR transcription is trustworthy enough for Persian exam questions and worked solutions when geometry/boundaries are already known. The benchmark is deliberately separate from boundary recovery.

## Cost/accuracy policy

The goal is minimum practical cost without giving up strong multimodal checking.

- Mistral OCR remains the primary document/layout pass.
- Verifiers are not used on every question in production.
- Production target: one economical verifier only for locally high-risk regions; a second verifier is reserved for unresolved disagreement.
- Benchmark calibration uses two independent economical-but-capable vision models so the verifier itself can be evaluated.
- Default benchmark pair for the next experiment: `gpt-5.4-mini` and `gemini-3-flash-preview`.
- Do not use `gpt-5.5` + `gemini-3.1-pro-preview` by default; they are unnecessarily expensive for this well-scoped OCR-audit task.

## Two-stage benchmark

### Stage A: six-item pilot

Run only:

- `question:65` — grouped circuit-option visual
- `question:94` — chemistry structures / missing visual coverage case
- `question:120` — math/visual-heavy question
- `solution:50` — physics worked solution
- `solution:57` — known OCR-number/formula fragility
- `solution:133` — formula-heavy math solution

This uses two models and batch size 3: four verifier calls total in the normal path.

Acceptance for expanding the benchmark:

- both models complete all six items;
- source images are interpreted consistently enough to make disagreement informative;
- no systematic schema/mapping failures;
- costs/latency are acceptable;
- critical findings are visually plausible when manually spot-checked.

### Stage B: eighteen-item hard set

Only if the pilot is useful, expand to:

Question side:

- 18
- 52
- 65
- 79
- 81
- 89
- 94
- 111
- 120
- 129
- 150

Solution side:

- 45
- 50
- 57
- 73
- 93
- 133
- 150

These cover Persian scientific text, numbers, equations, diagrams, tables, circuits, chemistry structures, graph/image options, and formula-heavy worked solutions.

## Safety/merge rules

- The source image is authoritative for the verifier benchmark.
- Verifier output never auto-repairs candidate OCR in this experiment.
- A second verifier is evidence, not truth.
- Disagreement is itself a review/risk signal.
- Word confidence is never a correctness gate; earlier tests showed highly confident wrong option digits and formula tokens.
- Targeted crop OCR is used for missing boundary anchors only and must not overwrite healthy non-target records.

## Crop persistence

Diagnostic benchmark crops are temporary artifacts in the selected output directory/ZIP.

Production persistence should use existing `ExamPrepVisualAsset` private storage only for crops that are actual question/option/solution visual assets. Temporary OCR/recheck crops should normally be regenerated from the source PDF and deleted after use.

## Final validation

After architecture choices are frozen, run a fresh full-PDF end-to-end validation on the complete document. That final validation must exercise:

- bounded document OCR chunks;
- local RTL/layout normalization;
- booklet ranges;
- 155 question anchors;
- 155 solution boundaries after targeted repair;
- visual coverage reconciliation;
- Smart Union Crop;
- transcription-risk routing;
- economical targeted verification;
- final integrity audit.
