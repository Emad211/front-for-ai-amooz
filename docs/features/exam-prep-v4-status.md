# Exam Prep V4 — Implementation Status Ledger

> Living roadmap execution ledger. Updated in every V4 implementation turn. Canonical roadmap: `exam-prep-v4-source-aware-split-pipeline.md`.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **PR:** #4 — Draft
- **Execution mode:** Critical Path Acceleration
- **Current roadmap span:** Phase 4 → Phase 7 vertical extraction path
- **Last completed slice:** transaction-safe invalidation, bounded semantic batching, and hard live-benchmark provider-call ceiling
- **Active slice:** AvalAI Mistral OCR 4 feasibility smoke test for Phase 4/5 acceleration
- **Last fully validated code checkpoint:** `df105aa9f62302b6914c430de5be9ee654acfdd9`
- **Latest focused workflow:** `30842575840`
- **Backend job:** `91782991966`
- **Frontend job:** `91782991994`
- **Latest focused result:** 222 V4 backend tests passed; frontend focused validation passed
- **Last updated:** 2026-08-03

## Progress

Progress is counted only from the 77 canonical roadmap deliverables. A model, service, prompt, synthetic fixture, or passing smoke test does not by itself credit private-fixture accuracy.

| Phase | Credited | Total | State |
|---|---:|---:|---|
| Phase 0 | 5 | 6 | PR-level ledger enforcement remains open. |
| Phase 1 | 6 | 7 | Read-only admin inspection remains deferred. |
| Phase 2 | 8 | 9 | Real private live-provider benchmark remains open and uncredited. |
| Phase 3 | 4 | 7 | Core Source Map works; split/group and browser validation remain open. |
| Phase 4 | 3 | 8 | Bounding-box persistence, continuation candidates, and safe block inspection are verified. Real detector accuracy remains open. |
| Phase 5 | 6 | 7 | Typed question path, tolerant validation, private evidence, revisioning, partial retry, and warm reuse are verified. Private precision/recall remains open. |
| Phase 6 | 4 | 7 | Unified answer-solution records, continuation evidence, complete solution contract, and tolerant retry are verified. Real numbered-heading, answer-key, and inline accuracy remain open. |
| Phase 7 | 6 | 7 | Exact/unique matching, duplicate refusal, out-of-scope handling, provenance, and project isolation are verified. Full option/solution consistency remains open. |
| Phases 8–10 | 0 | 20 | Review, projection, hardening, shadow benchmark, and rollout have not started. |

- **Entire V4 roadmap:** **42/77 = 54.5%**
- **Phase 4:** **3/8 = 37.5%**
- **Phase 5:** **6/7 = 85.7%**
- **Phase 6:** **4/7 = 57.1%**
- **Phase 7:** **6/7 = 85.7%**

No progress credit is added for this OCR feasibility slice until measured evidence closes a canonical deliverable.

## Roadmap invariants

1. every uploaded PDF remains an independent `ExamProject` by default;
2. physical page identity, project scope, and evidence provenance remain authoritative;
3. questions originate only from accepted question-bearing evidence;
4. answer-only content never creates questions;
5. answer and complete source solution remain one record;
6. matching remains deterministic and project-scoped;
7. ambiguous evidence remains unresolved rather than guessed;
8. malformed provider siblings remain isolated;
9. accepted unchanged units are excluded from provider calls;
10. private source content, paths, crops, extracted text, and raw provider output remain outside public serializers and aggregate reports;
11. historical revisions remain auditable;
12. Phase 8 and rollout remain blocked until private evidence is recorded or explicitly waived.

## Closed prerequisites

### Synthetic full pipeline

Three independent synthetic PDFs pass through preparation, classification, Source Map confirmation, block persistence, typed question extraction, unified answer-solution extraction, deterministic matching, cold/warm reuse, aggregate-only reporting, and cleanup.

### Transaction-safe downstream invalidation

Changing a confirmed Source Map or accepted block set supersedes dependent accepted QuestionRecords, AnswerSolutionRecords, and MatchDecisions without deleting history. Unrelated projects remain untouched and failed replacement rolls back invalidation.

### Bounded semantic batching

Question and answer-solution extraction use bounded stage-specific batches with authoritative block IDs, tolerant sibling handling, partial retry, accepted-unit exclusion, and warm zero-call reuse.

### Hard live-provider call ceiling

Live benchmark requires `--max-provider-calls`. Each structured invocation reserves three worst-case external requests for JSON mode, fallback, and one repair. Exhaustion fails before entering the next provider request path.

## Focused verification before this slice

```text
Python 3.12
PostgreSQL 16
Redis 7
System check identified no issues (0 silenced).
No changes detected in app 'classes'.
222 passed, 47 warnings in 25.47s
Focused frontend TypeScript check: passed
Source-map state-model tests: passed
```

Warnings remain limited to the CI checkout lacking generated `backend/staticfiles/`. Expected negative PostgreSQL constraint logs are not suite failures.

## Active slice — AvalAI Mistral OCR 4 feasibility smoke test

The product owner requested that AvalAI documentation remain an explicit source for model/provider decisions. Before any implementation or live request in this slice, read and ground decisions in the current official AvalAI documentation, including:

```text
https://docs.avalai.ir/fa/
https://docs.avalai.ir/fa/examples/processing_documents_with_mistral_ocr
https://docs.avalai.ir/fa/models/mistral-ocr-2512
```

### Purpose

Determine whether the specialized AvalAI OCR endpoint can replace or accelerate part of the existing Phase 4 block-detection and Phase 5/6 transcription path while preserving the current domain model, persistence, provenance, revision, matching, privacy, and warm-reuse contracts.

### Allowed work

1. verify the exact current OCR endpoint, pinned model identifier, request/response contract, page selection, base64/private-input support, structured annotation options, layout/bbox semantics, pricing, limits, and data-handling caveats from official documentation;
2. document which claims are explicit and which remain unverified;
3. implement a provider-neutral AvalAI OCR client isolated from the production pipeline;
4. support local private PDF/image bytes through base64 without public URLs;
5. validate response size, page indexes, dimensions, usage data, markdown bounds, and optional annotations fail-closed;
6. create an aggregate-only smoke command for one question page and one answer/continuation page;
7. add fake-response tests for Persian RTL text, formulas, tables, images/bboxes, malformed annotations, missing pages, oversized output, and privacy;
8. record request count, processed pages, latency, and provider-reported usage without printing source content;
9. keep all existing V4 block/record/matcher paths unchanged until a measured live smoke result justifies an integration decision;
10. update this ledger and canonical roadmap with exact evidence.

### Explicitly out of scope

- sending all three private PDFs;
- replacing the existing block detector before measured evidence;
- changing SourceBlock, QuestionRecord, AnswerSolutionRecord, or MatchDecision authority;
- persisting raw OCR output as public data;
- public or presigned source URLs;
- Phase 8 review UI, student projection, publication, or rollout;
- adding progress credit from documentation or synthetic OCR fixtures alone.

### Smoke acceptance criteria

- endpoint/model/request contract is pinned from current official AvalAI docs;
- no private input path, filename, source bytes, markdown, annotation payload, crop, question, answer, or solution appears in stdout or aggregate report;
- fake mode validates the same parser, bounds, privacy, and report path used by live mode;
- local base64 input is bounded and no public URL is required;
- requested page indexes and returned page indexes are exact and unique;
- malformed or unexpected page/annotation records fail closed or surface content-free issues;
- JSON/annotation parsing is tolerant per record but never invents missing evidence;
- provider usage and latency are aggregate-only;
- live mode requires explicit model, credential, page/request ceiling, and product-owner permission;
- all focused PostgreSQL/backend/frontend gates remain green.

## AvalAI documentation rule

For future AvalAI-dependent implementation turns:

1. re-read the relevant current official AvalAI pages before model, endpoint, pricing, parameter, or data-handling decisions;
2. pin reproducible model identifiers rather than mutable aliases when available;
3. distinguish documented behavior from inference and measured behavior;
4. never infer retention, training, residency, or privacy guarantees that are not stated for the specific endpoint;
5. record official-doc URLs and the date reviewed in this ledger or the related runbook;
6. update code only after the roadmap is updated for that turn.

## User action required

No credential, model approval, cost ceiling, or permission to transmit the three original PDFs is required for documentation review and fake-response implementation.

A user decision will be requested only before the first live OCR request, with the exact pinned model, page count, expected maximum cost, request ceiling, and data-transmission scope stated explicitly.

## Exact continuation point

Read the official AvalAI OCR processing example and pinned model page. Then implement only the isolated bounded OCR client, aggregate-only two-page smoke command, and fake-response acceptance tests. Do not modify production extraction routing or send private content before the smoke gate is reviewed and explicitly authorized.