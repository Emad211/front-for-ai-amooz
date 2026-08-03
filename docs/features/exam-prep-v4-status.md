# Exam Prep V4 — Implementation Status Ledger

> Living roadmap execution ledger. Updated in every V4 implementation turn. Canonical roadmap: `exam-prep-v4-source-aware-split-pipeline.md`.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **PR:** #4 — Draft
- **Execution mode:** Critical Path Acceleration
- **Current roadmap span:** Phase 4 → Phase 7 vertical extraction path
- **Last completed slice:** isolated bounded AvalAI Mistral OCR 4 fake-response smoke gate
- **Active gate:** product-owner authorization for the two-page private live OCR smoke
- **Validated branch head:** `b29055d900d2ec6727d39be181567a554e0b336a`
- **Focused workflow:** `30845511947`
- **Backend job:** `91792716665`
- **Frontend job:** `91792716703`
- **Validated PR merge ref:** `744149f2029e95fad17229ea36740baa845f2096`
- **Last updated:** 2026-08-03

## Progress

Progress is counted only from the 77 canonical roadmap deliverables. Documentation, adapters, synthetic responses, and passing smoke tests do not credit private-fixture quality by themselves.

| Phase | Credited | Total | State |
|---|---:|---:|---|
| Phase 0 | 5 | 6 | PR-level ledger enforcement remains open. |
| Phase 1 | 6 | 7 | Read-only admin inspection remains deferred. |
| Phase 2 | 8 | 9 | Real private live-provider benchmark remains open and uncredited. |
| Phase 3 | 4 | 7 | Core Source Map works; split/group and browser validation remain open. |
| Phase 4 | 3 | 8 | Bounding-box persistence, continuation candidates, and safe block inspection are verified. Real OCR/layout accuracy remains open. |
| Phase 5 | 6 | 7 | Typed question path, tolerant validation, private evidence, revisioning, partial retry, and warm reuse are verified. Private precision/recall remains open. |
| Phase 6 | 4 | 7 | Unified answer-solution records, continuation evidence, complete solution contract, and tolerant retry are verified. Real numbered-heading, answer-key, and inline accuracy remain open. |
| Phase 7 | 6 | 7 | Exact/unique matching, duplicate refusal, out-of-scope handling, provenance, and project isolation are verified. Full option/solution consistency remains open. |
| Phases 8–10 | 0 | 20 | Review, projection, hardening, shadow benchmark, and rollout have not started. |

- **Entire V4 roadmap:** **42/77 = 54.5%**
- **Phase 4:** **3/8 = 37.5%**
- **Phase 5:** **6/7 = 85.7%**
- **Phase 6:** **4/7 = 57.1%**
- **Phase 7:** **6/7 = 85.7%**

No credit was added for the OCR feasibility implementation. A live two-page result may guide architecture, but roadmap credit changes only when measured evidence closes a listed deliverable.

## Roadmap invariants

1. every uploaded PDF remains an independent `ExamProject` by default;
2. physical page identity, project scope, and evidence provenance remain authoritative;
3. questions originate only from accepted question-bearing evidence;
4. answer-only content never creates questions;
5. answer and complete source solution remain one record;
6. automatic matching remains deterministic and project-scoped;
7. ambiguous evidence remains unresolved rather than guessed;
8. malformed provider siblings remain isolated;
9. accepted unchanged units are excluded from provider calls;
10. private source content, paths, crops, extracted text, annotations, and raw provider output remain outside public serializers and aggregate reports;
11. historical revisions remain auditable;
12. production routing is not changed by a feasibility smoke;
13. Phase 8 and rollout remain blocked until private evidence is recorded or explicitly waived.

## AvalAI documentation rule

For every AvalAI-dependent implementation turn:

1. update this ledger before code changes;
2. re-read the relevant current official AvalAI pages;
3. pin reproducible model identifiers instead of mutable aliases where available;
4. distinguish documented behavior, upstream capability context, engineering inference, and measured behavior;
5. never infer retention, training, residency, or privacy guarantees absent from the specific endpoint documentation;
6. record the reviewed URLs and date in this ledger or the related runbook.

Reviewed for this slice:

```text
https://docs.avalai.ir/fa/
https://docs.avalai.ir/fa/api-reference/ocr
https://docs.avalai.ir/fa/examples/processing_documents_with_mistral_ocr
https://docs.avalai.ir/fa/models/mistral-ocr-2512
```

Supplementary upstream Mistral pages were used only to understand OCR 4 block capabilities that must still be verified through the AvalAI gateway.

## Documentation findings recorded

- AvalAI OCR uses `POST https://api.avalai.ir/v1/ocr`.
- The reproducible OCR 4 identifier is pinned as `mistral-ocr-4-0`.
- `mistral-ocr-latest` is not used because it is a mutable alias.
- `mistral-ocr-2512` documents OCR 3, not OCR 4.
- private local PDF/image bytes can be transmitted as base64 data URLs without public URLs.
- PDF `pages` indexes are zero-based.
- Markdown, table formatting, document annotation, bbox/image annotation, and image extraction controls are documented.
- current upstream Mistral docs describe OCR 4 paragraph-level `blocks`; AvalAI gateway support remains a live-smoke question rather than an assumed guarantee.
- bbox annotation is treated as image/figure annotation, not as a replacement for text-block detection.
- AvalAI's OCR reference states OCR and annotation page prices, but exact combined billing behavior is measured rather than inferred.
- base64 transport does not establish a no-retention/no-training guarantee.

## Closed gate — isolated AvalAI OCR fake smoke

Implemented files:

```text
backend/apps/classes/services/exam_prep_v4_avalai_ocr.py
backend/apps/classes/management/commands/smoke_exam_prep_v4_avalai_ocr.py
backend/apps/classes/test_exam_prep_v4_avalai_ocr.py
docs/runbooks/exam-prep-v4-avalai-ocr-smoke.md
```

The service is isolated from the production extraction runner. No production SourceBlock, QuestionRecord, AnswerSolutionRecord, MatchDecision, task, or API routing was modified.

### Four independent smoke modes

```text
markdown
blocks
document_annotation
bbox_annotation
```

The modes measure different capabilities instead of treating all annotations as equivalent:

- Markdown for Persian/RTL transcription, formula signals, and HTML tables;
- OCR 4 blocks for paragraph-level type/bbox/confidence feasibility;
- document annotation for constrained page/document-level classification;
- bbox annotation for extracted figure/image classification.

### Input and privacy contract

- local PDF, PNG, and JPEG bytes only;
- base64 data URLs generated in memory;
- no public or presigned source URL;
- bounded input, response, page count, Markdown, annotation, and timeout;
- `include_image_base64=false` on every request;
- unexpected returned image base64 fails closed;
- duplicate/missing requested page indexes fail closed;
- malformed annotations become content-free issues while valid sibling OCR pages remain available;
- stdout and report exclude source paths, filenames, bytes, data URLs, Markdown, block text, annotations, questions, answers, solutions, credentials, and raw provider errors.

### Smoke command

```text
python backend/manage.py smoke_exam_prep_v4_avalai_ocr
```

Default plan:

```text
2 private page images × 4 modes = 8 requests
```

Live mode requires all of:

```text
--mode live_provider
--model mistral-ocr-4-0
--max-requests 8
--allow-private-transmission
AVALAI_API_KEY in local environment/secret
```

The command refuses to read/send inputs when permission, key, or request ceiling preflight is missing.

## Fake-smoke acceptance evidence

Verified with the same parser and report builder used by live mode:

- pinned model and endpoint;
- private base64 data URL payloads;
- zero-based bounded page selection;
- Markdown, Persian/RTL, formula, and HTML table signal metrics;
- OCR4 block type and bbox parsing;
- document annotation and bbox/image annotation parsing;
- malformed annotation isolation;
- duplicate and missing page refusal;
- input, response, Markdown, and annotation bounds;
- unexpected image-base64 privacy refusal;
- eight-request aggregate command flow;
- aggregate-only stdout/report;
- live permission/key/request-ceiling preflight.

## Focused verification evidence

The focused workflow validated the pull-request merge result against current `main`.

```text
Python 3.12
PostgreSQL 16
Redis 7
System check identified no issues (0 silenced).
No changes detected in app 'classes'.
231 passed, 47 warnings in 25.38s
Focused frontend TypeScript check: passed
Source-map state-model tests: passed
```

Warnings remain limited to the CI checkout lacking generated `backend/staticfiles/`. Expected negative PostgreSQL constraint logs are not suite failures.

## What is not claimed

- no OCR request reached AvalAI in this slice;
- no private page content was transmitted;
- no OCR 4 gateway response shape was observed live;
- no Persian RTL, formula, table, diagram, numbered-heading, continuation, block bbox, latency, or cost quality is claimed;
- no production extraction route uses OCR;
- no three-PDF benchmark was run;
- no canonical deliverable received new credit.

## Active gate — two-page private live OCR smoke

The next allowed operation is only a two-page live feasibility run:

```text
one representative question page
one representative answer-solution or continuation page
× markdown, blocks, document_annotation, bbox_annotation
= exactly 8 requests
```

Pinned configuration:

```text
endpoint: https://api.avalai.ir/v1/ocr
model: mistral-ocr-4-0
hard request ceiling: 8
include_image_base64: false
input transport: local base64 data URL
output: aggregate-only report plus private local human inspection
```

The live smoke will measure:

- Persian/RTL reading-order plausibility;
- printed-number preservation;
- formula and table preservation;
- OCR 4 block labels/bboxes/confidence returned through AvalAI;
- document role annotation;
- image/diagram bbox annotation usefulness;
- latency, request IDs, processed pages, and authoritative cost lookup;
- whether OCR should be OCR-first, transcription-only, diagram-only, or rejected for V4.

Production integration remains forbidden until this result is reviewed and explicitly recorded.

## User action required now

Before the first live OCR request, the product owner must explicitly confirm:

1. `AVALAI_API_KEY` is available in the local secret/environment and will not be pasted into chat or Git;
2. permission to transmit exactly two selected private page images to AvalAI/Mistral for this smoke;
3. approval of pinned model `mistral-ocr-4-0`;
4. approval of the hard request ceiling of exactly 8;
5. which representative question page and answer-solution/continuation page should be used, or permission for the implementation agent to select them from the supplied private PDFs.

The full three PDFs are not authorized by this gate.

## Exact continuation point

Obtain the five approvals above. Then execute only the bounded two-page OCR smoke, retain raw OCR results locally/private for human inspection, emit only aggregate metrics, record measured evidence in this ledger and runbook, and decide whether an OCR-assisted production path merits a separate roadmap slice.