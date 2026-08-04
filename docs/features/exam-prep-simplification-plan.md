# Exam Prep simplification and legacy removal plan

Status: Phase 1 in progress  
Baseline: `main@4de0d248c8efdcf925f4f8ed0abc7af69d85a4fc`

## Product decision

Target PDFs use the same visible question number in the question section and the
answer/solution section. The extraction engine therefore does not need page-role
classification, Source Maps, block graphs, fragment graphs, or fuzzy matching as
the primary path.

The replacement pipeline is deliberately small:

```text
PDF
  -> render pages
  -> one structured LLM extraction per page
  -> PageExtraction records
  -> group by (scope_key, question_number)
  -> deterministic validation/review
  -> existing ClassCreationSession.exam_prep_json
  -> existing teacher publication and student exam flows
```

There will be no V5. The final runtime name is simply `exam_prep`.

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

The canonical question fields that remain stable are:

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

The simple assembler may add safe provenance fields such as `scope_key`,
`source_question_number`, and `source_pages`; existing Pydantic/read contracts
already allow additional fields.

## Current runtime inventory

### Active production intake

`backend/core/urls.py` currently overrides
`/api/classes/exam-prep-sessions/step-1/` with
`ExamPrepSourceAwareStep1View` from `views_v4_compat.py`. New PDF intake therefore
enters the V4 project/bridge path before the legacy `apps.classes.urls` route can
handle it.

### Legacy V1/V2/V3 runtime still present

The original two-step pipeline remains in `apps/classes`:

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

These are removal candidates only after cutover. They are not changed in Phase 1.

### V4 runtime still present

V4 currently includes separate model modules, migrations, services, serializers,
views, tasks, frontend components, API routes, runbooks, benchmarks, and CI. The
runtime families include:

- `models_v4*.py` and migrations `0038` through `0047` associated with V4;
- `tasks_v4.py` and `tasks_v4_recovery.py`;
- `views_v4*.py`, `serializers_v4*.py`, and `urls_v4.py`;
- `exam_prep_v4_*` services for PDF source preparation, classification, Source
  Maps, blocks, records, matching, review, projection, bridge, OCR evidence,
  invalidation, observability, benchmark, and publication;
- frontend `exam-prep-v4` services, hooks, components, and the embedded
  source-aware workspace;
- V4 environment variables, workflows, benchmarks, and runbooks.

These are removal candidates only after the simple engine owns new traffic and
all active V4 drafts are resolved.

## Six safe phases

### Phase 1 — inventory, safety boundary, and pure contract

Deliverables:

- this canonical inventory and deletion plan;
- a pure page-level schema;
- deterministic assembly by `(scope_key, question_number)`;
- tests for normal matching, repeated numbers across scopes, continuation,
  conflicts, incomplete records, and duplicate pages;
- no route, task, model, migration, database, frontend, or production behavior
  change.

Exit criteria:

- the page contract is explicit and tested;
- preservation and removal boundaries are recorded;
- branch diff contains no runtime cutover.

### Phase 2 — page extractor behind no production route

Implement one provider call per rendered page using the Phase 1 schema.

Rules:

- no page-role classifier;
- no Source Map;
- no block/fragment/segment model;
- no fuzzy question matcher;
- one configured multimodal model from environment;
- bounded concurrency, retries, timeout, cancellation, and content-free logs;
- golden fixture tests only unless the owner explicitly requests live calls.

Exit criteria:

- page images produce `PageExtraction` objects;
- full fixture PDFs assemble into the existing `exam_prep_json` shape;
- no production route points to the new engine yet.

### Phase 3 — cut over the existing teacher route

Keep the current user-facing route and UI. Replace only its internal PDF
implementation.

Deliverables:

- `/api/classes/exam-prep-sessions/step-1/` creates the existing
  `ClassCreationSession` directly;
- the simple page pipeline writes directly to `exam_prep_json`;
- existing polling, cancellation, invitations, review, publish, and student
  behavior remain unchanged;
- new traffic no longer creates V4 projects or legacy extraction artifacts.

Exit criteria:

- one production path for new exam-prep PDFs;
- rollback is one feature switch, not a version selector;
- published exam and student regression tests pass.

### Phase 4 — drain and freeze legacy drafts

Deliverables:

- stop dispatch of V1/V2/V3/V4 extraction tasks;
- identify active queued/running jobs and drain or revoke them safely;
- retain completed `exam_prep_json` projections;
- mark incomplete legacy drafts for re-upload instead of building a complex
  migration into the new intermediate format;
- keep published exams and student attempts untouched.

Exit criteria:

- zero active legacy extraction jobs;
- zero new writes to legacy intermediate tables;
- explicit counts for retained, cancelled, and re-upload-required drafts.

### Phase 5 — remove legacy executable code

Delete runtime code no longer referenced after Phase 4:

- V1/V2/V3 extraction services, task branches, review/unit/visual APIs, flags,
  tests, and dead frontend behavior;
- V4 models/services/tasks/views/serializers/routes/frontend/benchmarks/runbooks;
- bridge and projection code;
- old imports in `apps.py`, `signals.py`, `tasks.py`, `core/urls.py`, and frontend
  navigation/services.

Keep historical migrations until the database removal migration is deployed.

Exit criteria:

- runtime source search has no versioned extraction path;
- only `exam_prep` naming remains in executable code;
- all preserved teacher/student contracts pass.

### Phase 6 — database removal and migration squash later

Deliverables:

- new migrations remove obsolete intermediate tables, columns, indexes, and
  signals;
- private obsolete artifacts are deleted according to retention rules;
- deploy and verify the removal migration;
- migration squashing is a separate later maintenance operation.

Historical applied migration files must not be deleted before a safe squash.

Exit criteria:

- obsolete tables are gone;
- no orphan private artifacts remain;
- fresh install and upgraded production database both migrate successfully.

## Phase 1 implementation in this branch

New isolated files:

- `backend/apps/classes/services/exam_prep_page_records.py`
- `backend/apps/classes/test_exam_prep_page_records.py`

The module is pure and has no side effects. It does not import Django models,
Celery, storage, provider clients, V2/V3/V4 code, or version flags.

Load-bearing key:

```python
(scope_key, question_number)
```

The assembler never performs fuzzy matching. Conflicts are retained
predictably and exposed through `issues` for later teacher review.

## Exact continuation point

After Phase 1 is reviewed and merged, continue only with Phase 2:

1. define the single page-extraction prompt;
2. call the configured multimodal provider once per page;
3. validate each response as `PageExtraction`;
4. assemble fixture pages with `assemble_page_extractions`;
5. do not change production routing yet.
