# Exam Prep V4 — Implementation Status Ledger

> Living roadmap execution ledger. Updated in every V4 implementation turn. Canonical roadmap: `exam-prep-v4-source-aware-split-pipeline.md`.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **PR:** #4 — Draft
- **Execution mode:** Critical Path Acceleration
- **Current roadmap span:** Phase 4 → Phase 7 vertical extraction path
- **Last completed slice:** transaction-safe downstream invalidation and bounded semantic provider batching
- **Active gate:** private live-provider benchmark authorization and aggregate-only preflight
- **Validated code checkpoint:** `b72dfc34a9995616052a0991dbc186a4f6c05a11`
- **Focused workflow:** `30841604840`
- **Backend job:** `91779735773`
- **Frontend job:** `91779735590`
- **Last updated:** 2026-08-03

## Progress

Progress is counted only from the 77 canonical roadmap deliverables. A model, service, prompt, commit, synthetic fixture, or passing test does not by itself credit a private-fixture accuracy requirement.

| Phase | Credited | Total | State |
|---|---:|---:|---|
| Phase 0 | 5 | 6 | PR-level ledger enforcement remains open. |
| Phase 1 | 6 | 7 | Read-only admin inspection remains deferred. |
| Phase 2 | 8 | 9 | Real private live-provider benchmark remains open and uncredited. |
| Phase 3 | 4 | 7 | Core Source Map works; split/group and browser validation remain open. |
| Phase 4 | 3 | 8 | Bounding-box persistence, continuation candidates, and safe block inspection are verified. Real detector accuracy remains open. |
| Phase 5 | 6 | 7 | Typed question path, tolerant validation, private evidence, revisioning, partial retry, and warm reuse are verified. Private precision/recall remains open. |
| Phase 6 | 4 | 7 | Unified answer-solution records, continuation evidence, complete solution contract, and tolerant retry are verified. Real numbered-heading, answer-key, and inline accuracy remain open. |
| Phase 7 | 6 | 7 | Exact/unique matching, duplicate refusal, out-of-scope handling, provenance, and project isolation are verified. Full option/solution consistency gate remains open. |
| Phases 8–10 | 0 | 20 | Review, projection, hardening, shadow benchmark, and rollout have not started. |

- **Entire V4 roadmap:** **42/77 = 54.5%**
- **Phase 4:** **3/8 = 37.5%**
- **Phase 5:** **6/7 = 85.7%**
- **Phase 6:** **4/7 = 57.1%**
- **Phase 7:** **6/7 = 85.7%**

No progress credit was added for the invalidation and batching prerequisites. They make a private live run trustworthy and affordable, but they do not prove private layout, OCR, formula, recall, precision, latency, or cost targets.

## Roadmap invariants still enforced

1. every uploaded PDF remains an independent `ExamProject` by default;
2. equal hashes, duplicate pages, overlapping numbers, or shared headings never merge projects automatically;
3. questions originate only from accepted question-bearing blocks;
4. answer-only records never create questions;
5. answer and full source solution remain one evidence-bound record;
6. automatic matching remains deterministic and project-scoped;
7. ambiguous or duplicate evidence remains unresolved rather than guessed;
8. one malformed provider record may not erase healthy siblings;
9. accepted unchanged units are excluded from provider calls;
10. private source content, crops, paths, object names, extracted text, and raw provider output remain outside reports and public serializers;
11. historical revisions remain auditable while only current accepted rows drive projection;
12. rollout remains blocked until private benchmark metrics are recorded or explicitly waived with risk retained.

## Closed gate — three-project synthetic full pipeline

The synthetic benchmark routes three independent projects through the same persistence and matching path used by live mode:

```text
private PDF preparation
→ page rendering and thumbnails
→ source-role classification
→ canonical Source Map fingerprint
→ teacher-style confirmation
→ source block persistence
→ QuestionRecord extraction
→ unified AnswerSolutionRecord extraction
→ deterministic matching
→ aggregate-only report
→ cold/warm comparison
→ private artifact cleanup
```

Verified guarantees:

- fake and live modes share source preparation, provenance, revision, persistence, and matching paths;
- provider fakes replace only provider responses;
- no cross-project match is accepted;
- out-of-scope answers remain out of scope;
- duplicate or ambiguous numbers are not auto-matched;
- unchanged accepted warm reruns make zero provider calls;
- report and command output remain aggregate-only;
- benchmark-created database rows and private files are cleaned.

This closes synthetic infrastructure only. It does not prove private-fixture extraction quality.

## Closed gate — transaction-safe downstream invalidation

A changed confirmed Source Map or accepted block-set replacement now makes dependent accepted semantic output non-current without deleting audit history.

Verified behavior:

- accepted `ExamQuestionRecord` rows for the changed document are superseded;
- accepted `ExamAnswerSolutionRecord` rows for the changed document are superseded;
- accepted `ExamMatchDecision` rows referencing either record side are superseded;
- unrelated documents and independent projects remain untouched;
- invalidation participates in the same database transaction as the replacing source/block operation;
- a failed replacement rolls back invalidation and restores the prior accepted records and matches;
- historical rows and evidence remain available for audit;
- PostgreSQL row locking targets `ExamMatchDecision` directly through FK-id subqueries and no longer applies `FOR UPDATE` to the nullable side of an outer join.

The final PostgreSQL-specific correction is commit:

```text
8df84961b08268a6590877b10b4728dc090c2a7a
fix(exam-prep-v4): lock invalidated matches without nullable join
```

## Closed gate — bounded semantic provider batching

Question extraction and answer-solution extraction now support bounded, stage-specific batches while retaining record-level authority and failure isolation.

### Payload bounds

The live runner enforces three independent batch limits:

```text
EXAM_PREP_V4_EXTRACTION_BATCH_MAX_BLOCKS   default 4
EXAM_PREP_V4_EXTRACTION_BATCH_MAX_IMAGES   default 12
EXAM_PREP_V4_EXTRACTION_BATCH_MAX_BYTES    default 12 MiB
```

The existing per-image byte ceiling remains active. An individual block that cannot fit inside the configured image/byte limits fails closed rather than bypassing the boundary.

### Authoritative identity and prompts

- question and answer-solution batches use separate schemas and prompts;
- prompt versions are `exam-prep-v4-question-extraction-v2-batched` and `exam-prep-v4-answer-solution-extraction-v2-batched`;
- each request contains an authoritative block catalog;
- every crop group is delimited by its authoritative block ID;
- provider output may not introduce an unknown block ID or merge block identities;
- question batches select only question-bearing blocks;
- answer batches cannot create a question record;
- continuation crops remain ordered within their primary answer-solution block.

### Tolerant batch handling

- every returned record is validated independently;
- a malformed sibling does not reject healthy records;
- duplicate block IDs are surfaced as issues and the existing higher-confidence retention rule applies;
- unexpected block IDs are surfaced and rejected;
- omitted expected block IDs become block-specific retryable issues;
- accepted healthy block records are reconstructed into the next set and excluded from retry calls;
- a partial rerun sends only missing blocks;
- after recovery, an unchanged warm rerun sends zero provider calls.

### Usage attribution

Live structured calls retain usage attribution for:

- project;
- source document;
- extraction stage;
- model;
- batch index and size;
- authoritative block IDs and fingerprints;
- prompt version.

The live provider retains a single-block compatibility path so later stronger-model escalation can remain block-specific. Model-selection and escalation policy are not yet credited as implemented product behavior.

Batching commits:

```text
c2508e9a4350e078b2381cba90e1acfb1bf40733
feat(exam-prep-v4): add bounded semantic extraction batches

38ffc6059844f2ad6c6bcaac8f553edf51fb71a5
feat(exam-prep-v4): version prompts for bounded block batches

b72dfc34a9995616052a0991dbc186a4f6c05a11
test(exam-prep-v4): prove bounded batching and partial recovery
```

## Focused verification evidence

The focused V4 workflow tested the pull-request merge result against current `main`, not only an isolated branch checkout.

Backend environment:

```text
Python 3.12
PostgreSQL 16
Redis 7
```

Backend result:

```text
System check identified no issues (0 silenced).
No changes detected in app 'classes'.
211 passed, 47 warnings in 25.25s
```

Frontend result:

```text
Focused TypeScript check: passed
Source-map state-model tests: passed
```

The warnings remain limited to the CI checkout lacking generated `backend/staticfiles/`. PostgreSQL constraint-error lines in the service-container log are expected negative tests and did not fail the suite.

The focused V4 workflow is green. The repository-wide generic frontend workflow has inherited baseline typecheck failures outside this V4 slice and is not claimed resolved by this work.

## Acceptance evidence for the completed slice

- [x] changing one document never invalidates another project;
- [x] replacing one accepted block set supersedes dependent semantic records and matches;
- [x] failed replacement restores prior current records and matches;
- [x] unchanged complete warm rerun performs zero provider calls;
- [x] batched output with one malformed record preserves healthy siblings;
- [x] missing block IDs are surfaced as retryable issues;
- [x] duplicate block IDs are surfaced;
- [x] unexpected block IDs are rejected;
- [x] accepted healthy units are excluded from partial retry calls;
- [x] no answer-only batch creates a question;
- [x] no batched match crosses a project boundary;
- [x] migration drift is clean;
- [x] all focused V4 PostgreSQL tests are green;
- [x] focused frontend regression is green.

## Still open and explicitly uncredited

- real content-area, column, RTL reading-order, and numbered-heading detector accuracy;
- project-scoped visual/page deduplication at the block-processing boundary;
- private multi-column, formula, diagram, table, and continuation validation;
- private question precision and recall;
- private in-scope answer-solution precision and recall;
- automatic answer/solution match precision on private fixtures;
- complete option and solution consistency checks;
- explicit stronger-model selection and escalation policy;
- browser-level RTL, keyboard, focus, screen-reader, contrast, and visual-regression evidence;
- split and group actions;
- exception-review model and UI;
- student projection and publication;
- stale-task recovery, orphan sweeps, load/concurrency tests, and rollout controls;
- real cold/warm latency, usage, and cost measurements;
- the real three-PDF live-provider benchmark.

## Active gate — private live-provider authorization and preflight

The fake-provider prerequisites are closed. The next roadmap-preserving action is the first private live-provider benchmark. No private PDF has been sent to a provider in this branch.

Execution sequence after explicit authorization:

```text
1. validate provider credential and selected model names without persisting them;
2. validate the aggregate-only manifest and source availability;
3. apply an explicit maximum-cost/call boundary;
4. run three independent cold projects through the production provider path;
5. run unchanged warm reruns and require zero provider calls;
6. emit only aggregate structural, recall, precision, matching, latency, usage, and cost metrics;
7. clean benchmark-created rows and private artifacts;
8. record evidence in this ledger before crediting any private-fixture deliverable.
```

No Phase 8 exception-review implementation, publication work, Phase 9 hardening, or rollout work begins before this gate is resolved or explicitly waived with the retained risk documented.

## Product-owner authorization required

Before the first private live call, the product owner must approve all four items:

1. **provider and exact model names** for classification, block detection, question extraction, and answer-solution extraction;
2. **credential source**, configured through repository/environment secrets and never committed or pasted into this ledger;
3. **maximum permitted benchmark spend or provider-call budget**;
4. **permission to transmit the three private PDFs to the selected provider under that provider's data-handling terms**.

The missing booklet containing questions 146–147 is requested only when those answers must be treated as in-scope rather than intentionally out-of-scope.

## Exact continuation point

Obtain the four product-owner approvals above. Then implement only the bounded live-benchmark preflight/cost guard that is missing, rerun focused CI, execute the authorized aggregate-only private benchmark, and update this ledger with measured evidence before changing the 42/77 score.
