# Exam Prep page-first simplification plan (superseded)

> **Superseded on 2026-08-11:** This file is retained as the historical
> page-first/V4 cleanup plan only. It is not the production architecture or a
> deployment runbook. The standard Exam Prep intake now runs
> `Mistral OCR4 -> deterministic Stage 2 -> source-precise Stage 3 -> free
> deterministic Stage 4 -> all-region Stage 5`. Stage 5 uses
> `gpt-5.4-mini` as primary and `gemini-3.6-flash` as the bounded main
> escalation model. There is no public page-first or V4/Source-Map route and no
> runtime rollback flag. See `docs/EXAM_PREP_MISTRAL_PRODUCTION_FREEZE.md` for
> the active contract. All sections below are historical.

## Current checkpoint

- Phase 1 — pure page-record contract: **completed** in PR #8  
  Merge commit: `b354c6609e33f22dd8f7df5c3fecf4e13bda9c54`
- Phase 2 — isolated one-page extractor: **completed** in PR #9  
  Merge commit: `e9dd7610c22b15b65a1cf7b51e8b6919ab0a9d80`
- Phase 3 — production intake cutover: **implemented and validated** in PR #10
- Phase 4 — drain and freeze legacy drafts: **not started**
- Phase 5 — remove legacy executable code: **not started**
- Phase 6 — remove obsolete database structures: **not started**

Phase 3 focused evidence on PostgreSQL:

```text
Django system check: passed
classes migration drift: none
focused backend tests: 294 passed
focused frontend TypeScript/state tests: passed
live provider/OCR calls: 0
```

## Product decision

Target PDFs use the same visible question number in the question section and the
answer/solution section. The extraction engine therefore does not need page-role
classification, Source Maps, block graphs, fragment graphs, or fuzzy matching as
the primary path.

The only target pipeline is:

```text
PDF
  -> validate PDF
  -> render one physical page at a time
  -> one structured LLM extraction for that page
  -> PageExtraction records
  -> group by (scope_key, question_number)
  -> deterministic validation/review
  -> existing ClassCreationSession.exam_prep_json
  -> existing teacher publication and student exam flows
```

There is no V5. The final runtime name is simply `exam_prep`.

## Non-negotiable preservation boundary

The cleanup must not change or delete these product contracts:

- `ClassCreationSession` as the published exam container;
- `pipeline_type=exam_prep` scoping;
- `exam_prep_json` and its canonical question fields;
- teacher list/detail/publish/cancel/invitation/announcement behavior;
- `StudentExamPrepAttempt` and submitted answers;
- student list/detail/submit/check-answer/result/reset endpoints;
- exam-prep chat and chat history;
- published exams, scores, attempts, invitations, announcements, and roster data;
- shared authentication, organization, object-storage, Celery, idempotency,
  cancellation, logging, and retention infrastructure.

The stable question fields are:

```text
question_id
question_text_markdown
options
correct_option_label
correct_option_text_markdown
teacher_solution_markdown
final_answer_markdown
confidence
issues
```

The new assembler also records safe provenance:

```text
scope_key
source_question_number
source_pages
```

## Runtime after Phase 3

The existing public teacher endpoint remains:

```text
POST /api/classes/exam-prep-sessions/step-1/
```

New PDF intake now:

1. validates a real PDF upload;
2. creates a normal `ClassCreationSession` directly;
3. stores a Celery task ID before dispatch;
4. runs `process_exam_prep_pdf_session` on the `pipeline` queue;
5. renders and extracts one page at a time;
6. writes the assembled result directly to `exam_prep_json`;
7. finishes in the existing `exam_structured` / ready-for-review state.

New intake does **not** create:

- `ExamProject`;
- V4 bridge rows;
- Source Maps;
- blocks or fragments;
- question/answer record tables;
- legacy extraction artifacts or units;
- projection rows.

The temporary deployment rollback switch described by this historical plan has
been removed. Current deployments must not define or rely on
`EXAM_PREP_SIMPLE_PIPELINE_ENABLED`; the standard endpoint is fixed to the
Mistral Stage 1–5 runner and does not restore a public V4 intake.

## Legacy runtime still present

Cutover intentionally does not delete old code yet. The repository still
contains V1/V2/V3 and V4 executable code and tables so existing drafts and queued
jobs are not destroyed mid-run.

### V1/V2/V3 candidates

- `process_exam_prep_step1_transcription`;
- `process_exam_prep_step2_structure`;
- `process_exam_prep_full_pipeline`;
- `retry_exam_prep_extraction_unit`;
- `exam_prep_structure.py`;
- `exam_prep_inventory_pipeline.py`;
- `exam_prep_v3.py`;
- `exam_prep_visuals.py`;
- `ExamPrepExtractionArtifact`;
- `ExamPrepExtractionUnit`;
- `ExamPrepVisualAsset`;
- extraction-review, unit-retry, unit-source, and visual-asset endpoints;
- version flags such as `EXAM_PREP_EXTRACTION_V2` and
  `EXAM_PREP_EXTRACTION_VERSION`.

### V4 candidates

- `models_v4*.py` and associated migrations;
- `tasks_v4.py` and `tasks_v4_recovery.py`;
- `views_v4*.py`, `serializers_v4*.py`, and `urls_v4.py`;
- `exam_prep_v4_*` source, classification, Source Map, block, matching, review,
  projection, bridge, OCR, benchmark, and observability services;
- frontend V4 services, hooks, components, and source-aware workspace;
- V4 environment variables, workflows, benchmarks, and runbooks.

None of these are removed before Phase 4 proves that no active work depends on
them.

## Six safe phases

### Phase 1 — inventory, safety boundary, and pure contract

Completed deliverables:

- canonical preservation/removal map;
- pure `PageExtraction` schema;
- deterministic assembly by `(scope_key, question_number)`;
- conflict and continuation handling;
- no runtime side effects.

### Phase 2 — isolated page extractor

Completed deliverables:

- one registered page-extraction prompt;
- one configured multimodal request per rendered page;
- strict page attribution and input validation;
- fake-provider tests;
- no production route.

### Phase 3 — cut over the existing teacher route

Completed implementation:

- the existing endpoint creates `ClassCreationSession` directly;
- page images are rendered lazily, one page at a time;
- output is written directly to `exam_prep_json`;
- idempotency, queue failure, cancellation, retry, progress, and content-free
  logging are covered;
- V4 legacy tests call the retained V4 view directly instead of claiming the
  production endpoint;
- no model or migration change.

Exit gate:

- merge PR #10 after focused CI remains green.

### Phase 4 — drain and freeze legacy drafts

Required work:

- inventory active V1/V2/V3/V4 sessions and queued/running task IDs;
- stop all new legacy dispatch;
- safely drain or revoke active legacy jobs;
- retain completed sessions that already have valid `exam_prep_json`;
- mark incomplete legacy drafts as requiring re-upload;
- produce explicit counts for retained, cancelled, and re-upload-required data;
- remove the temporary rollback switch only after zero active legacy work is
  proven.

No complex migration from old intermediate formats into the new intermediate
format is allowed.

### Phase 5 — remove legacy executable code

Only after Phase 4 reaches zero active legacy work:

- remove V1/V2/V3 task branches, services, APIs, flags, tests, and dead frontend;
- remove V4 models/services/tasks/views/serializers/routes/frontend tooling;
- remove bridge/projection code;
- remove old imports from `apps.py`, `signals.py`, `tasks.py`, URLs, and frontend;
- retain historical applied migration files until database removal is deployed.

Exit criteria:

- no versioned extraction runtime remains;
- only `exam_prep` naming remains in executable code;
- all preserved teacher/student contracts pass.

### Phase 6 — database removal and later migration squash

Required work:

- add migrations that remove obsolete intermediate tables, columns, indexes,
  and signals;
- delete obsolete private artifacts according to retention rules;
- verify both an upgraded production database and a fresh install;
- squash historical migrations only in a later maintenance operation.

Historical applied migration files must not be deleted before a safe squash.

## Exact continuation point

After PR #10 is merged, continue only with Phase 4:

1. obtain database counts for every legacy active/terminal status;
2. identify queued/running legacy Celery task IDs;
3. add a dry-run management command that reports the drain plan without writes;
4. verify completed `exam_prep_json` sessions remain publishable;
5. only then implement the explicit drain/freeze operation.

Do not delete legacy code or tables in Phase 4.
