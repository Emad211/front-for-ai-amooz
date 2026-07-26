# Exam-prep inventory extraction

- **Status:** Implemented behind feature flags; not yet deployed
- **Created:** 2026-07-23
- **Last verified:** 2026-07-26
- **Owner:** classes / exam-prep

## Scope

Version 2 extracts an exam source in three independent stages: source manifest, question inventory,
and answer inventory. Deterministic server code then deduplicates questions, matches answers, builds
the existing `exam_prep_json` projection, and creates a publish audit.

Supported source types:

- PDF: page-aware transcript plus one retained page image per source page.
- Image: one document block plus the retained original image.
- Video: chunked transcript plus sampled source frames carrying timestamps.
- Audio: chunked transcript; no visual asset is expected.

Large logical blocks are split at paragraph/line/word boundaries before model calls. No phase may
drop a single-block media source solely because the manifest classified it as only questions or only
answers.

## Durable data

`ExamPrepExtractionArtifact` owns source blocks, page manifest, raw question and answer records,
failed chunks, audit, fingerprint, provider/model, and prompt version.

`ExamPrepVisualAsset` owns an immutable-keyed original crop and an optional generated candidate.
Its stable `asset_key` includes source fingerprint, question key, role, option, order, and bounding
box so question and solution images with the same local order cannot overwrite each other.

`exam_prep_json` remains the compatibility projection consumed by existing APIs. `_source` fields are
teacher-only provenance and are removed by the existing student serializer.

## Matching rules

1. exact normalized `(sectionKey, sourceQuestionNumber)`
2. source number alone only when unique across the inventory
3. same-page/block adjacency
4. otherwise unmatched and reviewable

Out-of-scope answers never create questions. An answer key may set a correct option/final answer, but
an absent source solution remains empty.

## Visual policy

The original crop is always the default and fallback. When
`EXAM_PREP_IMAGE_GENERATION_ENABLED=True`, Avalai is called with
`EXAM_PREP_IMAGE_GENERATION_MODEL`. Production must set it to
`gemini-3.1-flash-lite-image`.

The detector first creates a structured visual specification containing exact labels, numbers,
formulae, components, and relationships. The candidate is compared against the crop; one repair is
allowed. A verified candidate still requires the teacher to select `استفاده از بازطراحی`. Generated
solution visuals are never exposed through the student content endpoint.

Official model reference:
[Gemini image generation](https://ai.google.dev/gemini-api/docs/image-generation).

## Review and retry

Teacher detail exposes:

- `extractionAudit`
- `extractionVersion`
- `visualAssets`
- `extractionReview`

A failed chunk leaves the current review output visible and exposes `بازپردازش بخش ناموفق`. The
owner-scoped step-2 endpoint can retry only an unpublished version-2 session whose audit is not
passed. The status transition is protected by a database row lock and duplicate requests while
structuring do not dispatch another task.

Publication is blocked until the audit passes. Teacher edits rebuild correctable audit items while
retaining hard pipeline failures.

## Configuration

```env
EXAM_PREP_EXTRACTION_V2=False
EXAM_PREP_STRUCTURE_MODEL=
EXAM_PREP_INVENTORY_CHUNK_CHARS=16000
EXAM_PREP_VISUAL_ANALYSIS_MODEL=
EXAM_PREP_IMAGE_GENERATION_ENABLED=False
EXAM_PREP_IMAGE_GENERATION_MODEL=gemini-3.1-flash-lite-image
```

Both flags default off. No new queue, worker, bucket, or service is required.

## Rollout

1. Apply migration `classes.0038_exam_prep_inventory_artifacts`.
2. Deploy the shared backend image to web and the existing `pipeline` worker.
3. Deploy the frontend.
4. Enable `EXAM_PREP_EXTRACTION_V2` for controlled benchmark sessions.
5. Validate question counts, failed chunks, unmatched answers, and visual decisions.
6. Enable image generation separately after the Avalai model catalog/request preflight succeeds.

Rollback is flag-first: disable both flags. Existing version-2 sessions retain their artifact and
continue to use the compatible `exam_prep_json` projection.
