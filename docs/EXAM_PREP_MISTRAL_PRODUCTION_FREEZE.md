# Exam Prep Mistral OCR4 — Production Freeze

Branch of record: `experiment/mistral-ocr-layout-probe`

Safety snapshot created before productionization:
`snapshot/mistral-ocr-layout-probe-research-freeze-20260809`

## Branch decision

This branch remains the source of truth for the researched OCR4 production
engine. Exam Prep V4/source-map architecture is not merged into this runtime.
Useful production fixes from `main` must later be reconciled selectively rather
than by wholesale merge.

The normal product contract remains:

`ClassCreationSession -> background task -> ExamPrepPipelineResult -> exam_prep_json`

No new product model or page-confirmation workflow is introduced.

## Stable production entrypoint

All new OCR4 production wiring enters through:

`apps.classes.services.exam_prep_mistral_production.run_exam_prep_mistral_pipeline`

The signature and return type remain compatible with the existing simple Exam
Prep runner.

## Stage 1 — research freeze / production boundary: complete

Research probes, benchmark builders, calibration tools, run-comparison helpers
and findings remain in the repository for reproducibility but are not production
runtime dependencies.

The production boundary forbids:

- `management.commands`;
- `exam_prep_v4*`;
- benchmark/gold/run-comparison helpers;
- probe commands.

## Stage 2 — OCR4 document core: complete and frozen

Stage 2 is preserved byte-for-byte in:

`apps.classes.services.exam_prep_mistral_stage2_core`

Its contract is:

`PDF -> bounded chunks -> Mistral OCR4 blocks -> physical page remap -> booklet ranges -> RTL layout -> question regions -> solution-heading state machine -> targeted gap/invalid recovery -> deterministic assembly`

The paid OCR boundary remains:

`apps.classes.services.exam_prep_mistral_ocr_transport`

### OCR transport invariants

- all chunks planned before first paid call;
- maximum 30 physical pages per provider chunk;
- default 28 MiB mini-PDF cap;
- default 120 MiB response cap;
- exact local page coverage required before acceptance;
- physical page indexes remapped before document analysis;
- missing/duplicate page coverage fails closed;
- word-confidence retained as evidence, never treated as correctness truth.

### Retry invariants

Only transport failures and:

`408, 429, 500, 502, 503, 504`

are retryable.

Request/configuration failures such as 400/401/403/404/409/422 are not retried.
Malformed 2xx evidence is not paid-retried.

### Checkpoint invariants

A successful chunk is checkpointed only after exact coverage validation in
private `answer_sources` storage. Checkpoints are bound to source SHA, OCR
contract fingerprint, chunk index/pages and mini-PDF SHA. A later run can reuse
validated chunks and pay only for unfinished work.

### Structure invariants

- question anchors only from pages classified as question pages;
- printed question number is the deterministic identity;
- question and solution match only by printed number;
- duplicate/recovered-unverified anchors are production-critical;
- booklet declared ranges must match observed question numbers when available;
- missing/invalid solution headings alone may trigger targeted OCR;
- targeted OCR is target-only merge;
- conflicting target labels fail closed;
- no general LLM call in Stage 2.

## Stage 3 — precise source visual pipeline: complete

Full design and safety contract:

`docs/EXAM_PREP_MISTRAL_VISUAL_STAGE3.md`

The production path now extends Stage 2 with:

`OCR image/table candidates + rendered-page uncovered graphics -> semantic region reconciliation -> Smart Union -> bounded source crop -> local sanity gates -> private visual asset -> audit`

### Stage 3 implementation boundary

- `exam_prep_mistral_visual_primitives`
  - frozen local geometry/crop primitives;
- `exam_prep_mistral_visual_runtime`
  - fail-closed production orchestration;
- `exam_prep_mistral_visuals`
  - stable public facade and stricter production policy;
- `exam_prep_mistral_visual_review`
  - recomputes visual blockers during teacher review;
- `views_exam_prep_inline_visual`
  - streams authenticated Stage-3 private crops while preserving legacy visual
    behavior.

### Visual authority

The rendered source PDF remains authoritative. OCR image/table blocks are
candidates. Local uncovered-rendered graphics supplement OCR when vector or
mixed graphics were not represented as image blocks.

Smart Union may include the visual, axis/unit labels, legends, captions,
equations, option labels, arrows/lines/local graphics and complete table borders,
but remains bounded by the semantic question/solution region plus small padding.

### Visual modes

- precise question visual;
- grouped question visual;
- grouped visual options;
- four independent option visuals only when explicit source option labels bind
  deterministically;
- precise solution visuals, semantically independent from question visuals.

Geometry-only option ordering is not publish-safe. Axis/tick numbers cannot be
used as option labels. If binding is uncertain, the system groups the source
evidence and marks it review-only rather than guessing.

### Decorative suppression

Repeated body graphics are never discarded merely because they repeat. Only a
small, repeated, same-position margin/header/footer template candidate is
suppressed.

### Persistence

Crops are stored privately under:

`exam-prep/source/visuals/v1/<source-sha>/...`

`exam_prep_json` keeps asset id, role, option binding, physical source page,
normalized bbox, private storage reference, hash/size, visual mode, component
provenance and sanity metadata.

Asset identity includes physical page + question + semantic role + option where
applicable + occurrence + payload digest. Question and solution visual evidence
is never semantically deduplicated.

### Visual fail-closed gates

Critical Stage-3 codes include:

- `visual_precise_crop_unresolved`
- `visual_crop_clipped`
- `visual_bbox_too_small`
- `visual_bbox_too_large`
- `visual_caption_mismatch`
- `visual_missing_option_asset`
- `visual_option_binding_unresolved`
- `visual_table_border_risk`
- `visual_residual_graphics`
- `visual_crop_oversized`
- `visual_storage_failed`

A whole-page crop is allowed only as `whole_page_review_fallback`; it is always
`reviewOnly` and cannot open publication.

Teacher review re-derives Stage-3 blockers from asset metadata itself. Removing a
saved issue string or acknowledging a visual-critical code cannot turn a clipped
or unresolved asset into a publishable one.

### No general LLM in Stage 3

Stage 3 is local/deterministic. `generalLlmCalls` remains zero. The later risk
engine may selectively pass suspicious source crops to a model, but it cannot
downgrade deterministic visual evidence.

## Research code retained

The repository intentionally keeps research-only:

- `management/commands/probe_exam_prep_*`;
- fidelity/gold/calibration helpers;
- OCR comparison/analyzer commands;
- research findings and benchmark documents.

They are evidence, not production dependencies.

## Current product wiring state

The new OCR4 Stage 1–3 runner is still intentionally **not** the live Celery
runner. `tasks_exam_prep.py` continues to call the existing simple page-first
pipeline until later stages are complete.

This prevents a half-finished OCR4 rollout while the risk/verifier, final
integrity/dashboard/UI, branch reconciliation and release gate are unfinished.

## Next stage

Stage 4 is the targeted risk engine and independent source transcriber/verifier:

- deterministic local risk scoring;
- clean regions: zero LLM calls;
- suspicious region: one exact Stage-3 source crop, one model call;
- primary candidate: Gemini 3 Flash with minimal thinking based on prior
  calibration;
- hard residual formula/math disagreement may use GPT-5.4-mini as a second
  opinion;
- no multi-image batching;
- unresolved/high-risk output fails closed to teacher review;
- verifier may escalate local visual evidence but may not remove it.

Celery cutover remains later, after risk/verifier, final integrity/UI, selective
`main` reconciliation, and full 55-page end-to-end acceptance.
