# Exam Prep Mistral OCR4 — Stage 3 Precise Visual Pipeline

Branch of record: `experiment/mistral-ocr-layout-probe`

Stage 3 production entrypoint remains:

`apps.classes.services.exam_prep_mistral_production.run_exam_prep_mistral_pipeline`

The product contract remains unchanged:

`ClassCreationSession -> ExamPrepPipelineResult -> exam_prep_json`

No Exam Prep V4 model/source-map/block graph is introduced. No general LLM call
is made by Stage 3.

## Status

Stage 3 is part of the complete Mistral Stage 1–5 production entrypoint used by
the standard Exam Prep Celery task. The public intake has no page-first or
V4/Source-Map alternative route. Stage-3 output remains review-gated and does
not bypass final integrity/publication checks.

## Authority model

The rendered source PDF is authoritative.

Mistral OCR4 image/table blocks are candidate geometry, not truth. The pipeline
also renders every relevant physical source page locally and searches for
meaningful ink not covered by OCR blocks. OCR candidates and local uncovered
graphics are reconciled before any final crop is accepted.

A verifier in a later stage may escalate a visual risk, but it may not delete or
invalidate visual evidence that the deterministic source pipeline has already
established.

## Runtime layers

The implementation is intentionally separated into three files:

- `exam_prep_mistral_visual_primitives.py`
  - frozen deterministic geometry/crop primitives;
  - OCR/local seed representation;
  - clustering, Smart Union, crop encoding, storage metadata.
- `exam_prep_mistral_visual_runtime.py`
  - fail-closed production policy;
  - conservative option binding;
  - raster edge/clipping checks;
  - whole-page review fallback when precise encoding fails.
- `exam_prep_mistral_visuals.py`
  - stable production facade;
  - stricter option-marker rules;
  - stricter decorative suppression;
  - auxiliary completeness checks;
  - page-aware immutable asset identities;
  - unresolved audit reconciliation.

Stage 2 is separately frozen byte-for-byte in:

`exam_prep_mistral_stage2_core.py`

so Stage 3 does not silently alter the already-tested OCR4 transport, numbering,
solution-heading, or target-only recovery logic.

## Visual discovery

For pages classified as `question`, `solution`, or `mixed`:

1. render the physical PDF page locally;
2. retain OCR4 `image` and `table` blocks that belong to a question/solution
   geometric region;
3. erase all OCR block coverage from the rendered page mask;
4. detect significant remaining connected graphic components locally;
5. associate uncovered graphics to the smallest containing question/solution
   region;
6. combine both sources as visual seeds.

No provider call is made during this pass.

## Decorative/template suppression

Repeated content is not automatically decorative.

A visual is suppressed only when the same rendered fingerprint occurs on at
least three physical pages at essentially the same geometry and is in a
header/footer/page-margin-like position with bounded area.

Repeated graphics in the body are never discarded only because they repeat.
This prevents legitimate repeated axes, diagrams, or option templates from being
mistaken for logos.

## Smart Union Crop

Each visual seed starts from OCR image/table geometry or a local uncovered
component. Nearby educational annotations can expand the crop when they belong
to the visual:

- caption;
- axis label / short unit label;
- equation adjacent to the diagram;
- option label;
- short legend/annotation;
- local uncovered arrows, lines, axes, or graphic components;
- full OCR table geometry, including its border.

Expansion is iterative but bounded by the semantic question/solution region plus
small configurable guard/padding. The question heading itself is explicitly
excluded from visual annotation candidates.

A second completeness pass looks slightly beyond the normal union radius. If a
nearby caption/legend/axis/equation-like block should belong to the visual but is
outside every final crop, `visual_residual_graphics` is raised and the region is
not publish-safe.

## Visual modes

### 1. Question visual

A single diagram/chart/table becomes a `role=question` source visual.

Multiple compact pieces that form one educational visual may become one
`grouped_question` crop. If they are not compact, they remain separate question
visuals.

### 2. Grouped visual options

If OCR returns one image block containing the complete option set (for example,
four circuits in one visual), it remains one source crop with:

- `role=question`;
- `visualMode=grouped_options`;
- `groupedOptionLabels=[1,2,3,4]`.

The UI may present the crop above four selectable option labels without trying to
split source geometry that the provider/source does not support safely.

### 3. Independent option visuals

Four separate option assets are accepted only when the source provides four
explicit, tiny, standalone option markers `1..4` adjacent to OCR image/table
blocks and a one-to-one geometric assignment is deterministic.

Important safety rules:

- the question heading for questions 1..4 can never be used as an option marker;
- graph axis/tick numbers inside image bboxes can never be used as option
  markers;
- geometry-only reading-order inference is not publish-safe.

If separate option binding is not explicit, the runtime collapses the candidates
into a grouped source visual. That grouped result is publish-safe only if all
four explicit source labels are observed and included; otherwise it is
`reviewOnly` with `visual_option_binding_unresolved`.

### 4. Solution visuals

Solution diagrams/tables are stored with `role=solution` independently from the
question visual. A visually identical question/solution graphic is not
semantically deduplicated.

Multiple compact solution pieces may be unioned as `grouped_solution`; otherwise
multiple solution crops are retained.

## Asset identity and persistence

Precise source crops are persisted in the existing private `answer_sources`
storage, under:

`exam-prep/source/visuals/v1/session-<id>/<source-sha>/...`

`session-<id>` is an isolation and cleanup boundary, not only a naming detail.
Successful pipelines retain these final crops. Cancellation, terminal failure,
session deletion, and cascade deletion remove the exact session prefix (with a
second verification pass), without listing or deleting another session's
namespace.

The canonical question JSON stores a reference and provenance instead of an
inline base64 blob. Each Stage-3 visual records:

- stable `id` (`inline-mistral-v1-*`);
- semantic `role`;
- optional `optionLabel`;
- `sourcePage`;
- normalized `sourceBBox`;
- private `storagePath`;
- `contentType`;
- `byteSize`;
- payload SHA-256;
- `visualMode`;
- grouped option labels, when applicable;
- source kinds and union component IDs;
- `reviewOnly`;
- local `sanity.status` and `sanity.issues`.

Asset identity includes the physical source page, question number, semantic role,
option label where present, occurrence order, and payload digest. Two identical
images on two pages therefore do not produce duplicate client IDs. Question and
solution roles are always separate.

The authenticated existing visual-content URL remains the product URL. It now
supports Stage-3 private storage references while preserving numeric legacy
assets and old inline data URLs.

Students never receive solution-role visuals from that endpoint.

## Crop bounds

Default policy is bounded and environment-configurable:

- local discovery render: 150 DPI;
- final crop render: 260 DPI;
- small normalized padding;
- bounded region guard;
- final crop maximum page-area ratio;
- maximum rendered dimension;
- maximum persisted crop bytes.

Precise crops prefer PNG. Oversized images are downscaled within configured
bounds.

## Sanity gates

The following are production-critical and block publication:

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

### Clipping

Clipping is checked twice:

1. geometry: a seed touching the semantic region/crop boundary after bounded
   padding is suspicious;
2. raster: material dark ink touching the final crop perimeter despite expected
   padding makes the crop `reviewOnly` with `visual_crop_clipped`.

### Tables

A table seed is preserved as the complete table bbox. If the table reaches the
final crop/region edge such that its border may be cut, the result is
`visual_table_border_risk` and cannot publish automatically.

### Residual graphics / missing labels

Every source seed must be covered by at least one final crop. Nearby visual
annotations that are identified as part of the visual must also be covered.
Leaving behind an axis label, legend, equation, caption, or local graphic
component produces a critical residual/caption issue.

## Whole-page fallback

A whole physical page is never a final product visual.

It is allowed only as a source-evidence fallback for teacher review when precise
visual planning or bounded crop encoding cannot safely produce the requested
asset.

Such an asset always has:

- `visualMode=whole_page_review_fallback`;
- `reviewOnly=true`;
- a critical unresolved visual issue.

Therefore whole-page fallback cannot make a question publication-ready.

## Teacher review / publication persistence

Initial extraction audit promotes every Stage-3 critical visual issue to
`critical`.

More importantly, teacher review re-derives Stage-3 blockers from visual metadata
itself instead of trusting only `question.issues`.

For every Stage-3 asset the review audit rechecks:

- recognized semantic role;
- physical page;
- normalized bbox;
- private Stage-3 storage namespace;
- sanity metadata;
- `reviewOnly`;
- whole-page fallback mode;
- option labels / complete option set.

Removing a saved issue string therefore cannot accidentally make a clipped or
review-only visual publishable. Stage-3 visual critical codes are not teacher
"acknowledgement" overrides; the underlying visual/source evidence must be
corrected.

## Output/audit counters

`extraction_audit.visualPipeline` records local visual evidence including:

- pages scanned;
- OCR visual candidates;
- local uncovered-graphic candidates;
- decorative candidates suppressed;
- assets attached;
- question/option/solution asset counts;
- grouped visual count;
- table visual count;
- whole-page fallback count;
- review-only asset count;
- sanity failure count;
- unresolved region count;
- storage failure count.

`generalLlmCalls` remains zero in Stage 3.

## Known source examples this design targets

The design specifically covers failure modes proven during research on the
55-page sample:

- Q65: four circuits returned as one grouped OCR image;
- Q81/Q89: educational image content inside table geometry;
- Q94: a missing third chemical structure found through rendered-page graphics;
- Q150: multiple independent option visuals;
- solution pages: diagrams that must remain solution-role evidence and must not
  be deduplicated against question visuals.

## Focused zero-provider test surface

Stage-3 tests cover:

- Smart Union annotation inclusion/exclusion;
- repeated header/template suppression without body suppression;
- grouped option behavior;
- explicit option binding and axis-tick rejection;
- geometry-only option binding fail-closed behavior;
- table-border risk;
- missing axis/annotation residual detection;
- raster edge clipping;
- page/role-aware asset identity;
- empty option text with complete option visuals;
- precise crop persistence through private storage;
- whole-page review fallback;
- authenticated private visual streaming;
- storage path traversal/size guards;
- session-isolated cancel/failure/delete cleanup;
- visual metadata re-audit during teacher review;
- inability to acknowledge away visual-critical issues;
- architecture boundary: no V4 / benchmark / general LLM dependency.

All of these tests are local/provider-free.

## Stage boundary

Stage 3 does not decide scientific text/formula truth. It establishes source
visual completeness and immutable visual provenance.

Stage 4 consumes Stage-3 region evidence only for free deterministic risk
scoring. Stage 5 then reads every numbered question and solution region with one
source crop per request: `gpt-5.4-mini` is primary and
`gemini-3.6-flash` is the bounded main escalation model. Neither stage may
downgrade Stage-3 fail-closed visual authority or replace immutable source
provenance.
