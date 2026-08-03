# Exam Prep V4 — Implementation Status Ledger

> Operational companion to `exam-prep-v4-source-aware-split-pipeline.md`.
> Update this file with every meaningful V4 implementation change.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **Draft PR:** #4
- **Current phase:** Phase 2 — source preparation, fast classification, and virtual split
- **State:** Internal backend pipeline verified; upload API and live benchmark not implemented
- **Last updated:** 2026-08-03
- **Branch relation:** 31 commits ahead and 1 unrelated landing commit behind `main` at the latest check; do not rebase while validations are in flight.

## Verified baseline

- Phase 0 architecture and benchmark contracts are committed.
- The three private benchmark PDFs are three independent exams.
- No private PDF, page image, OCR text, filename, answer, or solution content is committed.
- Existing V1/V2/V3 endpoints, tasks, artifacts, and publication behavior remain unchanged.
- V4 remains disabled unless `EXAM_PREP_V4_ENABLED` is explicitly enabled.

## Phase 1 — complete

### Source-domain schema

The additive `classes.0040` migration creates:

- `ExamProject`
- `ExamSourceDocument`
- `ExamSourcePage`
- `ExamSourceSegment`
- shared `ExamSourceRole`

The schema stores ownership, organization scope, project revision, private source-object references, page metadata, classifier roles, teacher overrides, virtual page ranges, fingerprints, retention metadata, and processing status.

### Project isolation

- One PDF creates one independent project by default.
- Several PDFs in one request create several projects.
- Equal SHA-256 values never merge projects.
- Idempotent retries reuse a project only when request and document identifiers match.
- Conflicting retry metadata is rejected.
- Teacher querysets are owner-scoped.
- Duplicate-page references cannot cross exam-project boundaries.
- Page confidence and segment-range constraints are enforced by PostgreSQL.

## Phase 2 — implemented internally

### Tolerant page-classification contract

- Classifier records are validated independently.
- One malformed record does not discard valid sibling pages.
- Missing or invalid pages become explicit `unknown` pages.
- Duplicate predictions keep the higher-confidence record and produce an issue.
- Persian, Arabic, and Latin printed digits are normalized.
- Teacher page-role overrides remain authoritative without erasing the model prediction.
- Every PDF receives a complete one-based page map.

### Deterministic virtual split

Adjacent pages with the same effective role are grouped without reordering into:

- `cover`
- `questions`
- `answer_solutions`
- `answer_key`
- `inline_question_answer`
- `ignored`
- `unknown`

The segment builder is verified against anonymized structures representing:

- cover → questions → answer-solutions;
- answer-solutions → cover → questions;
- cover → questions → answer-solutions with overlapping answer-number bounds.

### Fast multimodal classifier

- Builds bounded, numbered JPEG contact sheets from low-resolution page thumbnails.
- Uses bounded native-text samples as supplemental evidence.
- Makes one structured multimodal classification call rather than full OCR calls per page.
- Uses the central OpenAI-compatible gateway and centralized V4 prompt registry.
- Selects the model only from `EXAM_PREP_V4_CLASSIFICATION_MODEL` or `PDF_VISION_MODEL`.
- Uses temperature 0, one bounded JSON repair, one provider attempt, and sensitive usage tracking.
- Fingerprints source, revision, page catalog, contact sheets, model, and prompt version.
- An unchanged warm rerun returns the persisted classification before any new provider call.

### Private PDF preparation

- Validates size, PDF signature, encryption, and page-count limits.
- Stores the original PDF in private object storage.
- Renders pages serially with bounded memory.
- Stores private PNG page renders and compact JPEG thumbnails.
- Captures bounded native-text samples without treating them as authoritative OCR.
- Reuses a complete unchanged source without creating new blobs.
- Detects duplicate rendered pages only inside the same exam project.
- Denies all `exam-prep-v4/` objects through the generic `/media/` route.
- Deletes source PDF, rendered pages, and thumbnails after database deletion commits.

### Internal source coordinator

The internal coordinator currently performs:

```text
private path-based PDF input
→ validation and private persistence
→ serial page rendering and thumbnails
→ contact sheets
→ fast multimodal page classification
→ tolerant page map
→ persisted virtual segment proposals
```

It records project/document workflow states and fail-closed errors. No public API or Celery task exposes this pipeline yet.

## Focused CI evidence

The focused workflow uses PostgreSQL 16 and Redis and runs:

1. production backend dependency installation;
2. `python backend/manage.py check`;
3. `python backend/manage.py makemigrations classes --check --dry-run`;
4. all `backend/apps/classes/test_exam_prep_v4_*.py` tests with real migrations and `--create-db`.

Latest fully inspected successful run:

- **Workflow run:** `30774398746`
- **Job:** `91567007925`
- **Result:** success

```text
System check identified no issues (0 silenced).
No changes detected in app 'classes'.
54 passed, 1 warning in 9.05s
```

The warning only reports that the CI checkout has no generated `backend/staticfiles/` directory during a negative private-media-route test. Later commits only update documentation until a newer focused run is explicitly inspected and recorded here.

Repository-wide frontend CI remains red on pre-existing files unrelated to V4:

- `frontend/src/app/(admin)/admin/tickets/page.tsx`
- `frontend/src/constants/mock/messages-data.ts`

Focused V4 CI is green; the full repository is not claimed as all-green.

## What is not yet verified

- No live LLM classification call has been made.
- The three private PDFs have not yet been run through the V4 classifier.
- Classification latency, cost, and real page-role accuracy are unknown.
- No V4 upload/list/detail/confirmation API exists.
- No V4 Celery task or queue routing exists.
- No teacher-facing source preparation UI exists.
- Question blocks, answer-solution blocks, matching, review, and publication are not implemented.

## Current correctness issue being closed

A conflicting attempt to replace an already prepared source with different PDF bytes must return a conflict without changing the valid existing document to `failed`. This behavior is the next targeted fix before public API work.

## Next verified step

1. Fix and test conflict-state preservation for prepared source documents.
2. Add an owner-scoped, feature-gated multi-PDF upload API that creates one project per PDF.
3. Dispatch each source document to a dedicated V4 pipeline task without merging files.
4. Add list/detail and segment-confirmation APIs only after upload isolation tests pass.
