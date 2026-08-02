# Exam Prep V4 — Source-Aware Split Pipeline

> Canonical living design, delivery roadmap, and implementation ledger for Exam Prep V4.

- **Status:** Phase 0 complete; Phase 1 is next
- **Branch:** `feat/exam-prep-v4-source-aware`
- **Base:** `main` at branch creation on 2026-08-03
- **Owner:** Classes / Exam Prep
- **Created:** 2026-08-03
- **Last updated:** 2026-08-03
- **Benchmark contract:** `docs/runbooks/exam-prep-v4-benchmark.md`
- **Target rollout:** Experimental feature flag first; no in-place upgrade of existing V1/V2/V3 artifacts

---

## 1. Document contract

This file is the source of truth for the V4 design and delivery state. Every V4 implementation change must update this document in the same branch and normally in the same pull request.

Every meaningful change must update at least the applicable sections below:

1. **Current status** — what is implemented and what is not.
2. **Implementation roadmap** — checkbox and phase state.
3. **Progress ledger** — date, commit, files, tests, result, next step.
4. **Decision log** — architecture or product decisions that changed or were clarified.
5. **Test evidence** — commands and exact results actually run.
6. **Known risks and open questions** — unresolved issues only.
7. **Next verified step** — one concrete next action.

Rules:

- Do not mark a phase complete based only on a plan or code review.
- A phase is complete only when its acceptance criteria and tests pass.
- Do not claim live-model benchmark success unless the private fixtures were actually run.
- Do not commit the private benchmark PDFs, filenames, page images, OCR output, or answer content.
- If this document conflicts with the current code, migrations, or tests, inspect the repository and update this file immediately. Code and database state are evidence; stale prose is not.
- Existing V3 release and runbook documents remain historical references and must not be rewritten to describe V4.

---

## 2. Executive decision

V4 will be a **new source-aware extraction engine built on the durable infrastructure of V3**.

It is not:

- a rewrite of the whole exam-prep product;
- an in-place mutation of existing V3 artifacts;
- a single larger prompt over a full PDF transcript;
- a PDF editor presented as the primary user experience.

It is:

- one independent exam project per uploaded PDF by default;
- page-range classification and virtual splitting before expensive extraction;
- block-first layout analysis instead of transcript-first inference;
- specialized pipelines for questions, answer-plus-solution records, short answer keys, and inline question-answer layouts;
- tolerant record-level validation;
- deterministic, exam-scoped matching;
- exception-only teacher review;
- V3-grade provenance, revision control, privacy, retry, caching, and publication safety.

Working name:

> **Exam Prep V4 — Source-Aware Split Pipeline**

---

## 3. Corrected input model

### 3.1 Core rule

**Each uploaded PDF is an independent exam by default.**

Multiple files belong to one exam only when the teacher explicitly groups them before processing. Uploading several PDFs in one browser action must not silently merge them.

This rule prevents a page, question number, answer, or solution in one uploaded PDF from influencing another exam.

### 3.2 Evidence from the three private benchmark inputs

The three reviewed PDFs are three different exams. They demonstrate that a single exam PDF can contain several internally different page ranges and that their order is not stable.

Anonymized structural observations:

| Fixture | Total pages | Internal order | Question range | Important boundary behavior |
|---|---:|---|---|---|
| A | 16 | cover → questions → answer-solutions | 1–50 | answer-solutions extend beyond the question inventory |
| B | 27 | answer-solutions → cover → questions | 51–115 | cover is in the middle; answer-solutions overlap below and above the question range |
| C | 15 | cover → questions → answer-solutions | 116–145 | answer-solutions begin below and end above the question range |

Additional implications:

- A whole PDF cannot safely receive one role.
- A cover page cannot be assumed to be page 1.
- The question range cannot be inferred from the answer range.
- An answer section may contain records for questions not present in that PDF.
- Answer records outside the question inventory must never create new questions.
- The correct option and detailed solution usually belong to one numbered answer block and should not be separated and rematched later.
- A detailed solution can continue onto the next page before the next numbered answer heading.
- Similar or identical pages can appear in different independent PDFs. Deduplication must therefore be scoped to one `ExamProject`, never global across uploads.

---

## 4. Problem statement

V3 has valuable reliability infrastructure but its extraction core is mismatched to these inputs.

The current path is broadly:

```text
PDF page OCR
→ one page-preserving transcript
→ page/chunk inventory prompts
→ independent question and answer records
→ matching
```

Observed product failures include:

- incorrect question boundaries;
- answer records attached to the wrong printed number;
- detailed solutions attached to the wrong question;
- valid content rejected because one structured response fails strict validation;
- suspicious but usable OCR being removed from the downstream path;
- full-page OCR losing two-column layout and region ownership;
- answer continuation across pages being treated as a new or unrelated record;
- unnecessary inference where the teacher or page structure could provide a deterministic role.

The root issue is not only prompt quality. The pipeline asks a general model to recover structure after layout, document role, and record boundaries have already been flattened.

---

## 5. Product goals

### 5.1 Primary goals

1. Make source preparation simple for any teacher.
2. Classify and propose page ranges quickly before full OCR.
3. Extract every genuine question with its printed number and evidence.
4. extract the correct option and full detailed solution as one logical record.
5. Match records only inside the same exam project.
6. Prefer unresolved review issues over incorrect automatic matches.
7. Preserve every source page, block, crop, model response, and decision needed for review and retry.
8. Reuse accepted work on retry and warm reruns.
9. Keep existing V1/V2/V3 sessions behaviorally frozen.
10. Allow V4 rollout and rollback through configuration.

### 5.2 User experience goal

The normal flow must remain:

```text
Upload PDF
→ review a simple suggested split
→ start processing
→ resolve only exceptional cases
→ publish the draft
```

The teacher must not need to understand manifests, source blocks, model schemas, fingerprints, or pipeline stages.

### 5.3 Quality priority

For matching:

> **Precision is more important than recall.**

A missing automatic match can be fixed in review. A wrong match silently teaches the wrong answer and is unacceptable.

---

## 6. Non-goals

V4 will not initially:

- merge separate uploaded PDFs into one exam automatically;
- infer that two files belong together because their pages look similar;
- provide a full desktop-grade PDF editor;
- rewrite or improve source questions or solutions;
- solve missing answers;
- generate detailed solutions not present in the source;
- replace original diagrams by generated images by default;
- migrate existing V3 artifacts to V4;
- enable V4 in production before private benchmark gates pass.

---

## 7. V3 capabilities retained

V4 should reuse or extend the following proven V3 capabilities:

- private object storage for source pages and visual crops;
- source SHA-256 fingerprints;
- artifact revisions;
- immutable or revision-scoped extraction units;
- worker leases and heartbeats;
- stale-result rejection;
- accepted-unit reuse;
- per-unit retry;
- LLM usage attribution and tracking context;
- provider concurrency control;
- cancellation checkpoints;
- source preview restricted to the owning teacher;
- teacher confirmation bound to current content;
- fail-closed deletion;
- retention cleanup;
- bounded orphan-object sweeps;
- publication gates;
- source provenance in teacher-facing review data.

V4 must not copy V3 code blindly when its abstractions assume one source file, one transcript, or one shared inventory pass.

---

## 8. V3 behaviors replaced

V4 replaces these extraction behaviors:

- one role for an entire PDF;
- full-page OCR as the only structural representation;
- one large transcript as the primary downstream input;
- general question/answer chunk extraction over mixed content;
- strict whole-response success or failure;
- answer and detailed solution treated as independently recoverable fields after flattening;
- page proximity or loose numbering used as an automatic match fallback;
- quarantining usable content solely because of soft length or formatting anomalies.

---

## 9. Domain model

Names are provisional until migrations are reviewed. The concepts are mandatory even if implementation names change.

### 9.1 `ExamProject`

One independent exam draft.

Key fields:

- owner teacher;
- organization or personal scope;
- title and description;
- V4 status;
- revision;
- workflow state;
- publication fields;
- cancellation fields;
- teacher-confirmation fingerprint;
- created and updated timestamps.

Default behavior:

- one uploaded PDF creates one `ExamProject`;
- multiple selected PDFs create multiple projects;
- explicit grouping may add multiple documents to one project later.

### 9.2 `ExamSourceDocument`

One uploaded source file belonging to one `ExamProject`.

Key fields:

- project;
- original filename and MIME type;
- private source object;
- SHA-256;
- page count;
- classification state;
- extraction version;
- teacher-confirmed flag;
- retention deadline;
- source metadata and error fields.

### 9.3 `ExamSourcePage`

Durable metadata for one rendered page.

Key fields:

- document and one-based page number;
- private rendered image;
- image SHA-256 and perceptual hash;
- dimensions, byte size, content type;
- native text sample and length;
- thumbnail object or generated thumbnail metadata;
- page-role prediction;
- classification confidence;
- teacher override;
- orientation;
- duplicate-of reference scoped to the same project only.

### 9.4 `ExamSourceSegment`

A contiguous logical page range in one source document.

Allowed roles:

```text
cover
questions
answer_solutions
answer_key
inline_question_answer
ignored
unknown
```

Key fields:

- document;
- start and end page;
- role;
- order;
- predicted role and confidence;
- teacher-confirmed role;
- expected printed-number range when known;
- section or booklet key;
- revision and fingerprint;
- status and errors.

Segments are virtual. Initial split operations update metadata rather than rewriting PDFs.

### 9.5 `ExamExtractionBlock`

A region-level unit extracted from one or more consecutive pages.

Allowed block kinds:

```text
question
answer_solution
answer_key
continuation
decorative
unknown
```

Key fields:

- project, document, and segment;
- page range;
- normalized bounding boxes per page;
- reading order and column index;
- source crop references;
- detection fingerprint;
- block kind and confidence;
- continuation relation;
- revision and processing state.

### 9.6 `ExamQuestionRecord`

One genuine source question.

Required evidence fields:

- printed number as seen;
- normalized printed number;
- question text;
- source block;
- source pages and bounding boxes.

Optional fields:

- section key;
- options;
- question type;
- visual references;
- confidence;
- extraction warnings;
- raw model payload.

### 9.7 `ExamAnswerSolutionRecord`

One numbered answer together with the complete source-provided solution.

Fields:

- printed number;
- normalized printed number;
- section key;
- correct option label when present;
- short final answer when present;
- full detailed solution;
- starting block;
- continuation blocks;
- source pages and bounding boxes;
- confidence and warnings;
- raw model payload.

The correct option and detailed solution are kept together because the reviewed inputs present them under the same numbered heading.

### 9.8 `ExamAnswerKeyRecord`

Used only for compact answer-key tables or lists that do not contain detailed solutions.

Fields:

- printed number;
- normalized printed number;
- correct option or final answer;
- source page and bbox;
- confidence and warnings.

### 9.9 `ExamMatchDecision`

A durable record of how an answer or solution was connected to a question.

Fields:

- project and revision;
- question record;
- answer-solution or answer-key record;
- match status;
- deterministic match rule;
- supporting identifiers;
- confidence is informational, not authorization to guess;
- teacher override fields;
- created and invalidated timestamps.

Statuses:

```text
automatic_exact
automatic_unique_number
teacher_confirmed
unresolved
out_of_scope
conflict
invalidated
```

### 9.10 `ExamReviewIssue`

One teacher-facing exception.

Examples:

- question without an answer;
- answer without a question;
- duplicate printed number;
- conflicting answers;
- uncertain continuation;
- incomplete OCR;
- invalid option label;
- answer option not present in the question;
- missing or ambiguous visual;
- segment role not confirmed.

---

## 10. Target state machine

Provisional project stages:

```text
draft
uploading
classifying
awaiting_source_confirmation
segmenting
extracting_questions
extracting_answers
matching
awaiting_review
ready_to_publish
published
cancelled
failed
```

Rules:

- classification and extraction are distinct stages;
- the user can correct page roles before expensive full extraction;
- accepted segment or block work is revision-scoped and reusable;
- a teacher edit advances the relevant revision and invalidates stale confirmation;
- publish is impossible while required review issues remain unresolved.

---

## 11. Fast classification pipeline

### 11.1 Objective

Return a useful page-range proposal quickly enough that the teacher does not feel blocked.

### 11.2 Inputs

Use the cheapest reliable evidence first:

1. PDF metadata and page count;
2. native text layer, when usable;
3. low-resolution page thumbnails;
4. a contact sheet or bounded sample of pages;
5. targeted additional thumbnails only when boundaries remain uncertain.

Do not run production-quality OCR on every page during classification.

### 11.3 Outputs

The classifier produces:

- per-page role probabilities;
- contiguous segment proposals;
- cover candidates;
- likely question-number ranges;
- likely two-column or special layout flags;
- confidence and reasons suitable for logs, not UI clutter.

### 11.4 Latency target

Initial product target for a medium text-based PDF:

- first structural proposal: approximately 10 seconds or less;
- upload progress shown separately from classification;
- classification continues asynchronously when the HTTP request returns.

This is a target, not a claimed benchmark result.

### 11.5 Teacher confirmation UX

Normal UI:

```text
Pages 1: Cover
Pages 2–8: Questions
Pages 9–16: Answers and solutions
```

Actions:

- confirm and process;
- adjust section boundaries;
- change a section role;
- open advanced page tools.

No model or pipeline terminology is shown.

---

## 12. Virtual PDF preparation tools

The primary interaction is not a full PDF editor. Advanced tools appear only when the teacher chooses to correct the proposal.

Supported metadata-first operations:

- move a segment boundary;
- assign a role to a page range;
- ignore pages;
- rotate a page;
- reorder pages;
- duplicate a page into another segment;
- combine explicitly grouped source documents;
- split one document into several independent exam projects.

Physical PDF export or rewritten files can be added later. V4 processing should operate from page manifests and private rendered pages.

---

## 13. Layout and block detection

### 13.1 Why block-first

The sample pages contain two-column RTL layouts, multiple numbered answers on one page, equations, diagrams, and continuations. Flattening a page before record boundaries are known loses ownership information.

### 13.2 Detection stages

1. Detect page orientation and content area.
2. Detect columns and RTL reading order.
3. Detect numbered headings and separators.
4. Detect question or answer-solution block boundaries.
5. Detect figures and associate them with the nearest owning block using layout constraints.
6. Detect incomplete blocks that continue on the next page.
7. Persist crops and bounding boxes before semantic extraction.

### 13.3 Continuation rule

A block at the top of page N may continue the previous answer-solution record when:

- it lacks a new numbered heading;
- the previous block had no terminal boundary;
- layout order supports continuation;
- no intervening segment boundary exists;
- the content classifier does not identify a new record.

Ambiguous continuations create a review issue rather than an automatic merge.

---

## 14. Specialized extraction pipelines

### 14.1 Question pipeline

Input: one `question` block and its source crop(s).

Output record:

```json
{
  "printedNumber": "۷۸",
  "normalizedNumber": "78",
  "sectionKey": "",
  "questionTextMarkdown": "...",
  "options": [
    {"label": "1", "textMarkdown": "..."}
  ],
  "visualHints": [],
  "warnings": []
}
```

The model must not answer or solve the question.

### 14.2 Answer-solution pipeline

Input: one numbered answer-solution block plus confirmed continuation blocks.

Output record:

```json
{
  "printedNumber": "۷۸",
  "normalizedNumber": "78",
  "sectionKey": "",
  "correctOptionLabel": "1",
  "finalAnswerMarkdown": "...",
  "fullSolutionMarkdown": "...",
  "warnings": []
}
```

The model must not create a question or invent missing reasoning.

### 14.3 Compact answer-key pipeline

Input: one answer-key table or list block.

Output: a list of small number-to-answer records. Each row is validated and stored independently.

### 14.4 Inline question-answer pipeline

For a source where each question is immediately followed by its answer and solution, extract one `QuestionBundle` from one bounded region. No separate matching step is required unless the record is later split manually.

---

## 15. Tolerant structured-output contract

### 15.1 Principle

Strictness must protect factual linkage and provenance, not reject usable records because one sibling record or optional field is malformed.

### 15.2 Parsing layers

1. request JSON mode where supported;
2. extract the first valid JSON object or array from wrapper text;
3. apply bounded local repairs for common syntax defects;
4. validate records individually;
5. preserve valid records;
6. retry only invalid records or blocks;
7. keep raw model output for debugging and review;
8. never silently replace invalid output with an empty object.

### 15.3 Hard failures

A record is hard-failed when:

- the provider returns no usable content;
- the source block or evidence is missing;
- a question record has no genuine question text;
- a numbered record has neither a recoverable number nor a confirmed continuation relation;
- an answer or solution is not grounded in the supplied crop;
- a stale worker attempts to commit to a newer revision.

### 15.4 Soft warnings

Examples:

- missing optional section key;
- missing confidence;
- incomplete option list;
- unreadable formula fragment;
- output length anomaly without contradictory evidence;
- optional field type coercion;
- visual hint without a detected crop.

Soft warnings do not erase source-grounded text. They create review metadata.

---

## 16. Deterministic matching

### 16.1 Scope

Matching is always scoped to one `ExamProject` and one current revision.

### 16.2 Canonical key

Primary key:

```text
project_id + normalized_section_key + normalized_printed_number
```

### 16.3 Automatic rules

Apply in order:

1. exact section key and normalized printed number;
2. normalized printed number when it is unique in the project;
3. no other automatic fallback.

### 16.4 Forbidden automatic rules

These may generate UI suggestions but may not create an automatic match:

- fuzzy text similarity;
- page proximity alone;
- visual similarity;
- same raw number across different sections when duplicated;
- model confidence alone;
- cross-document similarity outside an explicitly grouped project;
- cross-project matching under any circumstance.

### 16.5 Out-of-scope records

An answer-solution record whose normalized number is absent from the question inventory is `out_of_scope` unless a teacher deliberately maps it.

It must not:

- create a new question;
- expand the expected range;
- attach to the nearest number;
- leak into another exam project.

---

## 17. Consistency gates

Before an automatic match becomes publishable:

- the question and answer belong to the same project and revision;
- printed numbers are compatible;
- section keys are compatible or the number is unique;
- the correct option exists in the question option set when options exist;
- short final answer and detailed solution do not conflict;
- no second accepted answer claims the same question without a conflict issue;
- all source evidence remains privately retrievable by the owning teacher;
- the record has not been superseded by a newer extraction or teacher edit.

A consistency failure creates an issue; it does not silently select a winner.

---

## 18. Exception-only review

The teacher should not have to recheck every correctly processed question.

Review queue categories:

- missing answer;
- unmatched answer or solution;
- duplicate question number;
- conflicting answer records;
- uncertain continuation;
- page or block OCR problem;
- invalid or missing visual;
- option mismatch;
- unconfirmed source segment.

Each review card should show:

- source crop for the question;
- source crop for the answer-solution;
- printed numbers and section;
- why the engine did not auto-match;
- a short list of valid destinations;
- `none of these` and `out of scope` actions.

---

## 19. Proposed API surface

Paths and payloads are provisional.

### Project and upload

```text
POST   /api/classes/exam-prep-v4/projects/
POST   /api/classes/exam-prep-v4/projects/{id}/documents/
GET    /api/classes/exam-prep-v4/projects/{id}/
DELETE /api/classes/exam-prep-v4/projects/{id}/
```

### Classification and segmentation

```text
POST  /api/classes/exam-prep-v4/projects/{id}/classify/
GET   /api/classes/exam-prep-v4/projects/{id}/source-map/
PATCH /api/classes/exam-prep-v4/projects/{id}/source-map/
POST  /api/classes/exam-prep-v4/projects/{id}/source-map/confirm/
```

### Extraction and review

```text
POST /api/classes/exam-prep-v4/projects/{id}/extract/
GET  /api/classes/exam-prep-v4/projects/{id}/records/
GET  /api/classes/exam-prep-v4/projects/{id}/issues/
POST /api/classes/exam-prep-v4/projects/{id}/issues/{issue_id}/resolve/
POST /api/classes/exam-prep-v4/projects/{id}/units/{unit_id}/retry/
```

### Private source content

```text
GET /api/classes/exam-prep-v4/projects/{id}/pages/{page_id}/content/
GET /api/classes/exam-prep-v4/projects/{id}/blocks/{block_id}/content/
```

### Finalization

```text
POST /api/classes/exam-prep-v4/projects/{id}/review/confirm/
POST /api/classes/exam-prep-v4/projects/{id}/publish/
```

All endpoints are teacher-authenticated and owner/tenant scoped. Frontend guards are not security boundaries.

---

## 20. Async orchestration

Recommended task groups:

```text
classify_document
render_document_pages
build_source_segments
detect_segment_blocks
extract_question_block
extract_answer_solution_block
extract_answer_key_block
rebuild_project_matches
finalize_project_draft
```

Rules:

- expensive work runs on `pipeline`;
- interactive single-block retry may use a dedicated interactive queue later if latency requires it;
- task inputs carry project revision and unit identity;
- stale results cannot commit;
- accepted block records are reusable;
- one block failure does not fail valid sibling blocks;
- coordinator tasks aggregate statuses rather than holding all page images in memory.

---

## 21. Fingerprints, cache, and revision behavior

### 21.1 Fingerprints

Include the minimum inputs required to invalidate stale work:

- source page or crop bytes;
- page orientation and bbox;
- document and segment revision;
- model name;
- prompt version;
- schema version;
- parser/repair version;
- quality-contract version;
- block kind.

### 21.2 Revision triggers

Advance revision when:

- source pages are reordered, ignored, rotated, or reassigned;
- segment boundaries or roles change;
- a source document is added or removed from an explicitly grouped project;
- the teacher edits question, answer, or solution content;
- a unit is manually retried under a changed contract;
- selected visual evidence changes.

### 21.3 Reuse

Unaffected accepted units should be cloned or referenced into the new revision without provider calls, following V3's immutable snapshot principle.

---

## 22. Privacy and storage

V4 source PDFs, rendered pages, block crops, and generated candidates are private educational records.

Requirements:

- store under private storage aliases;
- block generic `/media/` access;
- serve only through owner-scoped authenticated endpoints;
- use `private, no-store` for review previews;
- retain sources long enough for review, retry, and controlled post-publication cleanup;
- delete fail-closed;
- keep orphan sweeps bounded and cursor-based;
- do not expose answer-solution crops to students;
- do not place private fixture data in logs or GitHub Actions artifacts.

---

## 23. Observability

Track by project, document, segment, block, unit, revision, and attempt:

- stage latency;
- provider and model;
- token and estimated cost;
- output parser result;
- retry reason;
- block and page counts;
- classification confidence;
- accepted, warning, unresolved, out-of-scope, and failed counts;
- automatic match rule;
- wrong-match corrections made by teachers;
- cache reuse;
- worker RSS and restart count;
- cleanup outcomes.

No raw source text should be required in production metrics.

---

## 24. Feature flags and rollout

Proposed configuration:

```env
EXAM_PREP_V4_ENABLED=False
EXAM_PREP_DEFAULT_ENGINE=v3
EXAM_PREP_V4_FAST_CLASSIFIER_MODEL=<env-only>
EXAM_PREP_V4_LAYOUT_MODEL=<env-only>
EXAM_PREP_V4_QUESTION_MODEL=<env-only>
EXAM_PREP_V4_ANSWER_SOLUTION_MODEL=<env-only>
EXAM_PREP_V4_REQUIRE_TEACHER_SOURCE_CONFIRMATION=True
EXAM_PREP_V4_REQUIRE_FINAL_REVIEW=True
```

Rules:

- V4 must not become selectable until core migrations and API guards are present.
- Existing sessions remain on their stored engine version.
- Rollback changes the default for new projects only.
- Shadow mode must not mutate the user's V3 result.
- Live enablement follows the benchmark gate in the runbook.

---

## 25. Test strategy

### 25.1 Pure unit tests

- Persian, Arabic, and Latin digit normalization;
- section-key normalization;
- page-role aggregation into contiguous segments;
- cover-in-the-middle segmentation;
- two-column RTL reading order;
- numbered heading detection;
- continuation detection;
- record-level tolerant JSON parsing;
- bounded JSON repair;
- option normalization;
- exact and unique-number matching;
- duplicate-number refusal;
- out-of-scope classification;
- cross-project match prevention;
- project-scoped deduplication.

### 25.2 Database integration tests

- one upload creates one project by default;
- three uploads create three projects;
- explicit grouping is required for multi-document projects;
- revision isolation;
- accepted-unit reuse;
- stale lease rejection;
- single-block retry;
- teacher edit invalidates confirmation;
- owner and tenant scoping;
- private source content;
- fail-closed deletion and retention cleanup.

### 25.3 Pipeline tests

- questions first;
- answers first;
- cover in the middle;
- answer ranges extending outside question ranges;
- answer continuation across pages;
- one malformed record beside valid sibling records;
- compact answer key;
- inline question-answer source;
- formulas, diagrams, tables, and multi-column pages.

### 25.4 End-to-end tests

- upload three independent PDFs together and obtain three drafts;
- accept automatic source maps;
- edit a source boundary;
- run extraction;
- resolve an unmatched answer;
- retry one block;
- confirm review and publish;
- cancel and delete safely.

### 25.5 Private benchmark

Use `docs/runbooks/exam-prep-v4-benchmark.md`. Private source files are local-only.

---

## 26. Acceptance criteria

V4 is not production-ready until all of the following are demonstrated:

- cross-exam automatic matches: 0;
- automatic answer-to-question precision: 100%;
- automatic solution-to-question precision: 100%;
- question recall on the current private fixtures: at least 99%;
- in-scope answer-solution recall: at least 99%;
- answer records converted into fabricated questions: 0;
- valid sibling records lost because one JSON record is malformed: 0;
- accepted warm reruns invoke no provider calls;
- source previews remain private and owner-scoped;
- all required backend and frontend tests pass;
- private benchmark metrics are recorded without source content;
- rollback for new projects is verified.

---

## 27. Implementation roadmap

Legend:

- `[ ]` not started
- `[-]` in progress
- `[x]` complete with evidence

### Phase 0 — Canonical design and benchmark contract

- [x] Create dedicated V4 branch.
- [x] Establish this living architecture and progress document.
- [x] Establish the private benchmark contract.
- [x] Record that the three supplied PDFs are independent exams.
- [x] Record segment structures and out-of-scope boundary behavior without source content.
- [ ] Add a PR-level enforcement check requiring this document to change with V4 implementation changes.

**Phase state:** Complete for implementation start. The enforcement check is deferred until the branch contains code paths that can be detected reliably.

### Phase 1 — Domain model and feature isolation

- [ ] Finalize model names and relationships.
- [ ] Add additive migrations.
- [ ] Add admin/read-only inspection support.
- [ ] Add engine-version and feature-flag resolution without enabling V4.
- [ ] Add model constraints and indexes.
- [ ] Add migration and project-isolation tests.
- [ ] Update this document with actual schema names.

**Exit gate:** Fresh PostgreSQL migration passes, project scoping tests pass, V1/V2/V3 behavior remains unchanged.

### Phase 2 — Upload and fast source classification

- [ ] Create one project per uploaded PDF by default.
- [ ] Stream uploads safely.
- [ ] Render low-resolution thumbnails.
- [ ] Extract bounded native-text evidence.
- [ ] Implement fast role classification.
- [ ] Aggregate page roles into segment proposals.
- [ ] Add source-map APIs.
- [ ] Add classification latency and usage tracking.
- [ ] Add unit and integration tests for all three structural patterns.

**Exit gate:** Correct segment map for the private fixtures with no full-quality OCR.

### Phase 3 — Teacher source-map confirmation and virtual tools

- [ ] Build simple source-map UI.
- [ ] Support boundary changes and role changes.
- [ ] Support ignore, rotate, and reorder metadata.
- [ ] Add explicit split-into-separate-exams action.
- [ ] Add explicit group-documents action later behind a separate control.
- [ ] Persist revisions and invalidate stale classification.
- [ ] Add accessibility and RTL tests.

**Exit gate:** A nontechnical teacher can correct each benchmark source map without opening an advanced editor.

### Phase 4 — Page layout and block detection

- [ ] Implement content-area and column detection.
- [ ] Implement RTL reading order.
- [ ] Implement numbered-heading detection.
- [ ] Implement source crops and bbox persistence.
- [ ] Implement continuation candidates.
- [ ] Add project-scoped page deduplication.
- [ ] Add block inspection endpoints.
- [ ] Test multi-column, formula, diagram, and continuation pages.

**Exit gate:** Stable blocks exist before semantic question/answer extraction.

### Phase 5 — Question extraction

- [ ] Define simple question record schema.
- [ ] Implement per-block extraction.
- [ ] Implement tolerant parser and per-record validation.
- [ ] Persist raw payload, warnings, and evidence.
- [ ] Implement visual ownership references.
- [ ] Implement record-level retry and cache reuse.
- [ ] Add precision/recall tests.

**Exit gate:** At least 99% question recall on private fixtures without fabricated questions.

### Phase 6 — Answer-solution extraction

- [ ] Define unified answer-solution schema.
- [ ] Implement numbered answer heading extraction.
- [ ] Implement continuation merge.
- [ ] Extract correct option, final answer, and full source solution together.
- [ ] Add compact answer-key sub-pipeline.
- [ ] Add inline question-answer sub-pipeline.
- [ ] Add per-record tolerant validation and retry.

**Exit gate:** At least 99% in-scope answer-solution recall with correct boundaries.

### Phase 7 — Deterministic matcher and integrity gates

- [ ] Implement project-scoped exact matching.
- [ ] Implement unique-number matching.
- [ ] Implement duplicate-number refusal.
- [ ] Implement out-of-scope classification.
- [ ] Implement option and solution consistency checks.
- [ ] Persist match provenance.
- [ ] Add zero-cross-project-match tests.

**Exit gate:** 100% automatic match precision for answers and solutions on private fixtures.

### Phase 8 — Exception review and final projection

- [ ] Create issue model and APIs.
- [ ] Build exception-only review UI.
- [ ] Support teacher match/ignore/out-of-scope decisions.
- [ ] Build backward-compatible student projection.
- [ ] Remove provenance and solutions from unauthorized student responses.
- [ ] Bind final confirmation to current revision and projection fingerprint.

**Exit gate:** Teacher can resolve all ambiguous benchmark cases and publish safely.

### Phase 9 — Reliability, cleanup, and security hardening

- [ ] Add stale-task recovery.
- [ ] Add retention and orphan sweeps.
- [ ] Add fail-closed project deletion.
- [ ] Add private media denial tests.
- [ ] Add load, concurrency, and worker-memory tests.
- [ ] Add audit-safe observability.

**Exit gate:** Security/lifecycle suite passes and no private object is leaked or orphaned.

### Phase 10 — Shadow benchmark and rollout

- [ ] Implement benchmark management command.
- [ ] Run cold and warm private benchmarks.
- [ ] Run V3/V4 shadow comparison without mutating user output.
- [ ] Record aggregate results in the runbook.
- [ ] Enable for a limited cohort.
- [ ] Monitor corrections, latency, cost, and failures.
- [ ] Verify rollback.
- [ ] Make V4 default only after gates pass.

**Exit gate:** Product owner approves metrics and controlled rollout.

---

## 28. Current status

### Completed

- Dedicated branch created: `feat/exam-prep-v4-source-aware`.
- Final architecture direction recorded.
- Corrected assumption recorded: the three supplied PDFs are independent exams.
- Private benchmark structural contract created.
- Matching priority and safety rule recorded.
- V3 capabilities to retain and behaviors to replace identified.

### Not implemented

- No V4 migration exists.
- No V4 model exists.
- No V4 API exists.
- No V4 frontend exists.
- No classifier, segmenter, block detector, extractor, matcher, or benchmark runner exists.
- No live-model V4 benchmark has run.
- Production remains unchanged.

### Next verified step

> Design and implement Phase 1 additive domain models and feature isolation, beginning with a repository-grounded model/migration plan and tests that prove one uploaded PDF maps to one independent V4 project by default.

---

## 29. Progress ledger

| Date | Commit | Change | Tests actually run | Result | Next step |
|---|---|---|---|---|---|
| 2026-08-03 | Branch creation | Created `feat/exam-prep-v4-source-aware` from current `main`. | None | Branch created; production unchanged. | Add benchmark contract and living design. |
| 2026-08-03 | `17636b851dab70530f1a3eee839d51919add932b` | Added private benchmark contract and acceptance metrics. | None; documentation-only | Benchmark runner explicitly marked not implemented. | Add canonical living design and roadmap. |
| 2026-08-03 | This document commit | Added architecture, phases, status, decisions, and update protocol. | None; documentation-only | Phase 0 ready for implementation start. | Start Phase 1 schema design. |

---

## 30. Decision log

### D-001 — New engine on V3 infrastructure

- **Date:** 2026-08-03
- **Decision:** Build V4 as a new extraction engine while reusing durable V3 infrastructure.
- **Reason:** V3 reliability features are valuable, but its transcript-first extraction architecture is the source of current matching and validation problems.

### D-002 — One PDF equals one exam by default

- **Date:** 2026-08-03
- **Decision:** Every uploaded PDF creates an independent exam project unless the user explicitly groups files.
- **Reason:** The three reviewed inputs are separate exams. Similar pages and overlapping question numbers must not imply shared identity.

### D-003 — Page-range roles, not file roles

- **Date:** 2026-08-03
- **Decision:** Classify contiguous page ranges inside each PDF.
- **Reason:** Cover, question, and answer-solution sections can appear in different orders, including a cover in the middle.

### D-004 — Unified answer and solution record

- **Date:** 2026-08-03
- **Decision:** Extract the correct option and detailed solution together from one numbered answer block.
- **Reason:** The source format presents them under one heading; separating them creates avoidable rematching errors.

### D-005 — Block-first extraction

- **Date:** 2026-08-03
- **Decision:** Detect layout and record blocks before semantic extraction.
- **Reason:** Full-page transcripts lose two-column ownership, block boundaries, and continuation relationships.

### D-006 — Tolerant record-level validation

- **Date:** 2026-08-03
- **Decision:** Validate and retry individual records rather than failing a full chunk.
- **Reason:** A minor JSON defect must not erase valid sibling questions or solutions.

### D-007 — Deterministic matching only

- **Date:** 2026-08-03
- **Decision:** Automatic matching is limited to exact section-plus-number or a project-unique number.
- **Reason:** Incorrect matches are more harmful than unresolved records. Fuzzy evidence is review assistance only.

### D-008 — Out-of-scope answers never create questions

- **Date:** 2026-08-03
- **Decision:** Build question inventory only from question segments.
- **Reason:** Answer ranges can exceed question ranges in both directions.

### D-009 — Deduplication is project-scoped

- **Date:** 2026-08-03
- **Decision:** Never globally deduplicate pages across independent projects.
- **Reason:** Similar or identical pages can appear in different exam PDFs without making them the same exam.

---

## 31. Known risks and open questions

These are unresolved and must be revisited with evidence:

1. Best fast classifier model and contact-sheet size for Persian two-column pages.
2. Whether deterministic computer-vision layout detection is sufficient before an LLM fallback.
3. Exact schema split between new V4 models and reusable V3 artifact/unit models.
4. How much native PDF text can be trusted for classification without contaminating extraction.
5. Reliable continuation detection when a new page begins with formulas and no prose.
6. Handling repeated printed numbers across subjects within one explicitly grouped project.
7. Whether source-map confirmation is mandatory for every project or only low-confidence maps.
8. Final latency and cost budgets after real provider benchmarking.
9. Whether a separate interactive worker is needed for block retry.
10. How to enforce living-document updates in CI without creating false positives.

---

## 32. Test evidence

No V4 code or tests exist yet. Phase 0 is documentation-only.

Actual evidence recorded so far:

- branch creation succeeded;
- benchmark contract committed;
- no repository tests were run because production code was not changed;
- no live-model benchmark was run;
- no claim of extraction improvement is made yet.

This section must be updated with exact commands and outcomes as soon as Phase 1 code is introduced.