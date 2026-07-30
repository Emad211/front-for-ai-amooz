# Exam-prep inventory extraction

- **Status:** V2 implemented; V3 quality gate implemented behind version selection
- **Created:** 2026-07-23
- **Last verified:** 2026-07-30
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

## Version 3 quality gate

Version 3 keeps the inventory-first architecture and adds durable extraction units. Each OCR page and
each structured extraction chunk is identified by stage, unit key, revision, fingerprint, and a
database-owned lease. Accepted units are reused; failed or suspicious units are retried once and then
quarantined.

An OCR result is not accepted merely because the provider returned HTTP 200. The quality contract
rejects empty or incomplete responses and absolute length violations. It also inspects robust length
outliers, OCR/native-text ratio, repeated lines, and numeric stability between reads. Quarantined
content never enters the transcript or either inventory.

Question and answer records carry source block IDs. V3 validates those IDs against the exact blocks
sent to the model and computes ordering on the server. Each phase must explicitly acknowledge every
block it inspected, so answer-phase evidence cannot hide a question-phase omission. Matching uses
same-block adjacency; page-only proximity is not sufficient.

Teacher detail exposes unit issues and protected source previews. Retrying one unit creates a new
artifact revision and reuses unaffected accepted units. Any retry, content edit, or visual decision
invalidates the previous review confirmation. Publication requires:

1. audit status `passed`
2. zero critical issues
3. teacher-reviewed revision equals the current revision
4. reviewed projection fingerprint equals the current projection

### V3 configuration

```env
EXAM_PREP_EXTRACTION_VERSION=3
EXAM_PREP_REQUIRE_TEACHER_REVIEW=True
EXAM_PREP_SOURCE_RETENTION_DAYS=7
PDF_OCR_MAX_OUTPUT_CHARS_PER_PAGE=24000
PDF_OCR_MAX_OUTPUT_TOKENS=16000
PDF_OCR_NATIVE_RATIO_LIMIT=3
PDF_OCR_ROBUST_Z_LIMIT=8
PDF_OCR_DUPLICATE_LINE_RATIO_LIMIT=0.35
PDF_OCR_MAX_ATTEMPTS=2
PDF_EXTRACTION_CONCURRENCY=2
LLM_PROVIDER_MAX_CONCURRENCY=8
```

`EXAM_PREP_EXTRACTION_VERSION` is read only when a session is created. Changing it never changes an
existing session. V3 uses the existing `pipeline` queue and current private storage.

### Security resolution — 2026-07-30

- Source preview, retry, review confirmation, and publication are teacher-only and owner-scoped.
- Publication locks the session and extraction artifact in one transaction and revalidates the
  current revision, audit, review confirmation, and projection fingerprint before publishing.
- A structured unit that omits an input source block becomes retryable and cannot be published.
- Manual deletion removes retained private page sources for V2 and V3 before deleting the database
  row. A storage failure returns a retryable error and preserves the session.
- Generic `/media/` delivery explicitly denies retained exam source pages and both original and
  generated visual assets. Teachers can inspect a quarantined page only through the authenticated,
  owner-scoped source-preview endpoint.
- Visual replacement and session deletion remove every original/generated private blob before
  deleting its database inventory. A partial storage failure preserves the inventory for retry.
- Scheduled retention cleanup removes metadata only for objects whose deletion succeeded; failed
  objects keep their inventory and a retry deadline. A bounded orphan-prefix sweep persists a cursor,
  advances across runs, and wraps after a full pass so later prefixes cannot starve behind live
  sessions. The same bounded sweep covers orphaned original and generated visual files while
  preserving every file referenced by a current visual asset. A one-hour age grace prevents a file
  being collected between its object-store write and database reference commit, while the cursor
  still advances across recently written objects. It provides defense in depth for a worker/storage
  failure during concurrent deletion.
- V3 visual-detection calls use the same durable unit lease, retry budget, fingerprint, and revision
  rules as manifest/question/answer calls. Optional Gemini image generation remains disabled and
  outside this rollout.
- Student APIs never expose extraction artifacts, source blocks, provider errors, or source previews.

## Rollout

1. Apply migrations `commons.0008_llmusagelog_context` and
   `classes.0039_exam_prep_extraction_v3`.
2. Deploy the shared backend image to web and the existing `pipeline` worker.
3. Deploy the frontend.
4. Run controlled benchmark sessions while `EXAM_PREP_EXTRACTION_VERSION` remains below `3`.
5. Validate question counts, phase coverage, quarantined pages, unmatched answers, and review gates.
6. Set `EXAM_PREP_EXTRACTION_VERSION=3` for new sessions.
7. Keep image generation disabled; it is outside the V3 quality-gate rollout.

For rollback, set `EXAM_PREP_EXTRACTION_VERSION=2` for new sessions. Existing V3 sessions remain V3
and must finish or be cancelled under their frozen contract; there is no mid-session fallback.
