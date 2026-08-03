# Exam Prep V4 — Implementation Status Ledger

> Living execution ledger. Update this file before every V4 implementation step. Canonical roadmap: `exam-prep-v4-source-aware-split-pipeline.md`.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **PR:** #4 — Draft
- **Execution mode:** Critical Path Acceleration
- **Current roadmap span:** Phase 4 → Phase 7 vertical extraction path
- **Last completed slice:** isolated bounded AvalAI Mistral OCR 4 fake-response smoke gate
- **Active gate:** authorized two-page private live OCR smoke
- **Last fully validated implementation checkpoint:** `b29055d900d2ec6727d39be181567a554e0b336a`
- **Last fully validated focused workflow:** `30846013026`
- **Last updated:** 2026-08-03

## Progress

Progress is counted only from the 77 canonical roadmap deliverables.

| Phase | Credited | Total | State |
|---|---:|---:|---|
| Phase 0 | 5 | 6 | PR ledger enforcement remains open. |
| Phase 1 | 6 | 7 | Read-only admin inspection remains deferred. |
| Phase 2 | 8 | 9 | Real private classification benchmark remains open and uncredited. |
| Phase 3 | 4 | 7 | Core Source Map works; split/group and browser validation remain open. |
| Phase 4 | 3 | 8 | Block persistence/continuation/inspection are verified; real OCR/layout quality remains open. |
| Phase 5 | 6 | 7 | Typed question path is verified; private precision/recall remains open. |
| Phase 6 | 4 | 7 | Unified answer-solution path is verified; real heading/answer-key/inline quality remains open. |
| Phase 7 | 6 | 7 | Deterministic matching is verified; complete consistency gate remains open. |
| Phases 8–10 | 0 | 20 | Not started. |

- **Entire V4 roadmap:** **42/77 = 54.5%**
- **Phase 4:** **3/8 = 37.5%**
- **Phase 5:** **6/7 = 85.7%**
- **Phase 6:** **4/7 = 57.1%**
- **Phase 7:** **6/7 = 85.7%**

No progress credit is added before measured private evidence closes a canonical deliverable.

## AvalAI documentation rule

For every AvalAI-dependent turn:

1. update this ledger before code or live execution;
2. re-read the relevant current official AvalAI documentation;
3. pin reproducible model identifiers instead of mutable aliases;
4. separate documented behavior, inference, and measured behavior;
5. never infer endpoint retention/training/residency guarantees;
6. record reviewed documentation in the related runbook.

Required official pages for this gate:

```text
https://docs.avalai.ir/fa/api-reference/ocr
https://docs.avalai.ir/fa/examples/processing_documents_with_mistral_ocr
https://docs.avalai.ir/fa/models/mistral-ocr-2512
```

## Existing OCR feasibility implementation

```text
backend/apps/classes/services/exam_prep_v4_avalai_ocr.py
backend/apps/classes/management/commands/smoke_exam_prep_v4_avalai_ocr.py
backend/apps/classes/test_exam_prep_v4_avalai_ocr.py
docs/runbooks/exam-prep-v4-avalai-ocr-smoke.md
```

The OCR service remains isolated from production extraction routing.

Four modes are supported:

```text
markdown
blocks
document_annotation
bbox_annotation
```

The client uses local private PDF/image bytes as in-memory base64 data URLs, sets `include_image_base64=false`, enforces bounded input/response/page/annotation limits, and emits aggregate-only metrics.

## Product-owner authorization recorded

The product owner explicitly approved all required items on 2026-08-03:

1. `AVALAI_API_KEY` is available in the local secret/environment;
2. exactly two selected private page images may be transmitted to AvalAI/Mistral;
3. pinned model `mistral-ocr-4-0` is approved;
4. hard request ceiling `8` is approved;
5. the implementation agent may choose one representative question page and one representative answer-solution/continuation page.

This authorization does **not** permit:

- sending complete PDFs;
- sending more than two selected page images;
- exceeding eight OCR requests;
- changing production routing;
- starting Phase 8, publication, or rollout.

## Active gate — bounded live OCR smoke

Exact plan:

```text
1 representative question page
1 representative answer-solution or continuation page
× markdown, blocks, document_annotation, bbox_annotation
= exactly 8 maximum requests
```

Pinned configuration:

```text
endpoint: https://api.avalai.ir/v1/ocr
model: mistral-ocr-4-0
hard request ceiling: 8
include_image_base64: false
input transport: local base64 data URL
```

Measured outputs must remain aggregate-only:

- request count and request IDs;
- processed-page count;
- latency;
- Markdown/RTL/formula/table signal counts;
- OCR4 block count/type/bbox/confidence availability;
- document annotation presence;
- image/bbox annotation count;
- content-free issue codes;
- authoritative cost lookup when available.

Raw OCR results may remain only in the operator's local private directory for human inspection. They must not be committed or pasted into chat.

## Current blocker

The assistant does not have access to the user's local filesystem, local `AVALAI_API_KEY`, or local private page images. The live command must therefore be executed by the user/operator on the authorized local machine. Only the aggregate JSON report should be returned.

## Exact continuation point

1. re-read the three official AvalAI pages;
2. identify two representative source pages from the private fixtures;
3. export those pages locally as PNG/JPEG without committing them;
4. execute `smoke_exam_prep_v4_avalai_ocr` with model `mistral-ocr-4-0`, request ceiling `8`, and explicit private-transmission permission;
5. return only the aggregate report;
6. record measured evidence in this ledger and the OCR runbook before deciding whether OCR should be OCR-first, transcription-only, diagram-only, or rejected for V4.
