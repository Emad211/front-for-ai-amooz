# Exam Prep V4 — Implementation Status Ledger

> Living execution ledger. Update this file before every V4 implementation step. Canonical roadmap: `exam-prep-v4-source-aware-split-pipeline.md`.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **PR:** #4 — Draft
- **Execution mode:** Critical Path Acceleration
- **Current roadmap span:** Phase 4 → Phase 7 vertical extraction path
- **Last completed slice:** guarded manual GitHub Actions orchestration for the two-page AvalAI OCR live smoke
- **Active gate:** provide two short-lived signed page-image URLs as GitHub Actions secrets, then manually dispatch the bounded live smoke
- **Validated implementation checkpoint:** `86d0ccbc312dd7adc725add4ef3ee671c574390a`
- **Focused workflow:** `30849183611`
- **Backend job:** `91804786818`
- **Frontend job:** `91804786856`
- **Validated PR merge ref:** `92d30fd1f4d96f3efc175cf15e3520118dd2c0f2`
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

## Roadmap and privacy invariants

1. every uploaded PDF remains an independent project by default;
2. physical page identity, project scope, and evidence provenance remain authoritative;
3. questions originate only from accepted question-bearing evidence;
4. answer-only content never creates questions;
5. answer and complete source solution remain one record;
6. automatic matching remains deterministic and project-scoped;
7. ambiguous evidence remains unresolved rather than guessed;
8. malformed provider siblings remain isolated;
9. accepted unchanged units are excluded from provider calls;
10. private source content, paths, crops, OCR text, annotations, and raw provider output remain outside public serializers, logs, and aggregate reports;
11. historical revisions remain auditable;
12. production routing is not changed by a feasibility smoke;
13. Phase 8 and rollout remain blocked until private evidence is recorded or explicitly waived.

## AvalAI documentation rule

For every AvalAI-dependent turn:

1. update this ledger before code or live execution;
2. re-read the relevant current official AvalAI documentation;
3. pin reproducible model identifiers instead of mutable aliases;
4. separate documented behavior, inference, and measured behavior;
5. never infer endpoint retention, training, or residency guarantees;
6. record reviewed documentation in the related runbook.

Required official pages for this gate:

```text
https://docs.avalai.ir/fa/api-reference/ocr
https://docs.avalai.ir/fa/examples/processing_documents_with_mistral_ocr
https://docs.avalai.ir/fa/models/mistral-ocr-2512
```

## Product-owner authorization and credential state

The product owner approved:

- transmission of exactly two selected private page images;
- pinned model `mistral-ocr-4-0`;
- hard ceiling of exactly eight OCR requests;
- implementation-agent selection of one question page and one answer-solution/continuation page;
- secret-based credential delivery.

The user confirmed through the GitHub settings UI that repository Actions secret `AVALAI_API_KEY` is configured. The secret value is neither visible nor required by the implementation agent.

This authorization does not permit complete PDFs, more than two images, more than eight requests, production routing changes, Phase 8, publication, or rollout.

## Closed gate — guarded GitHub Actions workflow

Implemented workflow:

```text
.github/workflows/exam-prep-v4-avalai-ocr-live-smoke.yml
```

Safety contract:

- `workflow_dispatch` only; no push, pull-request, schedule, or automatic trigger;
- read-only repository contents permission;
- explicit confirmation string `I_APPROVE_8_PRIVATE_OCR_REQUESTS`;
- branch locked to `feat/exam-prep-v4-source-aware`;
- pinned endpoint/model path through the existing command;
- exactly two secret-backed HTTPS page-image URLs;
- accepts only PNG or JPEG signatures;
- each input is bounded to 12 MiB;
- the two images must be byte-distinct;
- exactly four smoke modes and a hard eight-request ceiling;
- only `aggregate-report.json` is uploaded;
- aggregate artifact retention is one day;
- raw page images and local report are shredded/removed in an `always()` cleanup step;
- no private image, OCR text, annotation, raw provider response, URL, or credential is uploaded as an artifact.

Required secrets:

```text
AVALAI_API_KEY
OCR_QUESTION_PAGE_URL
OCR_ANSWER_PAGE_URL
```

The URL secrets must point to short-lived signed HTTPS URLs for exactly two private page images. They must not point to full PDFs or public permanent files.

## Workflow safety tests

```text
backend/apps/classes/test_exam_prep_v4_avalai_ocr_workflow.py
```

The tests enforce:

- manual-only and read-only workflow behavior;
- exact secret names;
- pinned `mistral-ocr-4-0` model;
- exact request ceiling `8`;
- aggregate-only artifact path;
- one-day artifact retention;
- private input cleanup;
- image signature and byte-size checks;
- exact aggregate acceptance contract.

## Focused verification

```text
Python 3.12
PostgreSQL 16
Redis 7
System check identified no issues (0 silenced).
No changes detected in app 'classes'.
235 passed, 47 warnings in 26.63s
Focused frontend TypeScript check: passed
Source-map state-model tests: passed
```

Warnings remain limited to the CI checkout lacking generated `backend/staticfiles/`. Expected negative PostgreSQL constraint logs are not suite failures.

No live OCR request has been executed and no private image has been transmitted by this branch.

## User action required now

Add these two repository Actions secrets:

```text
OCR_QUESTION_PAGE_URL
OCR_ANSWER_PAGE_URL
```

Each value must be a short-lived signed HTTPS URL to one PNG/JPEG page image, maximum 12 MiB. Do not paste the URLs into chat, a PR, an issue, or the repository.

## Exact continuation point

After both URL secrets are confirmed:

1. re-read the official AvalAI OCR pages;
2. manually dispatch `exam-prep-v4-avalai-ocr-live-smoke` on branch `feat/exam-prep-v4-source-aware`;
3. enter confirmation `I_APPROVE_8_PRIVATE_OCR_REQUESTS`;
4. inspect the aggregate-only artifact and request IDs;
5. record measured RTL, formula, table, blocks/bbox, annotation, latency, and cost evidence in this ledger and runbook;
6. decide whether OCR should be OCR-first, transcription-only, diagram-only, or rejected;
7. do not change production routing or the 42/77 score before that evidence is reviewed.