# Exam Prep V4 — Implementation Status Ledger

> Living execution ledger. Update this file before every V4 implementation step. Canonical roadmap: `exam-prep-v4-source-aware-split-pipeline.md`.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **PR:** #4 — Draft
- **Execution mode:** Critical Path Acceleration
- **Current roadmap span:** Phase 4 → Phase 7 vertical extraction path
- **Last completed slice:** isolated bounded AvalAI Mistral OCR 4 fake-response smoke gate
- **Active gate:** choose the secure execution/input path for the authorized two-page private live OCR smoke
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
10. private source content, paths, crops, OCR text, annotations, and raw provider output remain outside public serializers and aggregate reports;
11. historical revisions remain auditable;
12. production routing is not changed by a feasibility smoke;
13. Phase 8 and rollout remain blocked until private evidence is recorded or explicitly waived.

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

The service remains isolated from production extraction routing.

Supported modes:

```text
markdown
blocks
document_annotation
bbox_annotation
```

The client uses bounded local PDF/image bytes as in-memory base64 data URLs, sets `include_image_base64=false`, enforces bounded input/response/page/annotation limits, and emits aggregate-only metrics.

## Product-owner authorization recorded

The product owner approved on 2026-08-03:

1. exactly two selected private page images may be transmitted to AvalAI/Mistral;
2. pinned model `mistral-ocr-4-0`;
3. a hard ceiling of exactly eight OCR requests;
4. implementation-agent selection of one representative question page and one representative answer-solution/continuation page;
5. use of an environment/secret credential without committing or pasting the key.

This does not authorize complete PDFs, more than two page images, more than eight requests, production routing changes, Phase 8, publication, or rollout.

## Credential deployment decision

A GitHub Actions secret named `AVALAI_API_KEY` is an acceptable credential source. The key must be added through repository or, preferably, dedicated environment Actions secrets. It must never be committed to source, workflow YAML, `.env`, an issue, a PR comment, or chat.

The assistant and workflow logs do not need to reveal the value. The workflow references it only as:

```text
${{ secrets.AVALAI_API_KEY }}
```

A dedicated environment such as `v4-live-ocr-smoke` is preferred because it can isolate the secret from ordinary CI jobs and may support deployment protection rules depending on repository/plan settings.

## Important remaining blocker

The GitHub secret solves only credential delivery. A GitHub-hosted runner cannot access the user's local filesystem or the two local private page images.

Do **not** commit those images or PDFs to Git history, even temporarily. Git history and workflow artifacts introduce additional retention/access surfaces.

Permitted execution paths:

### Path A — local execution (preferred and simplest)

- keep `AVALAI_API_KEY` in the local environment;
- keep both images local;
- run the existing command locally;
- return only the aggregate JSON report.

### Path B — GitHub Actions execution

Requires all of:

- `AVALAI_API_KEY` as an Actions secret;
- a manually triggered, dedicated workflow rather than ordinary PR CI;
- a secure runner-accessible source for exactly two page images, preferably short-lived signed object-storage URLs passed as environment secrets;
- no page/PDF commit;
- no raw OCR output artifact;
- only the aggregate report as an artifact, with minimum practical retention;
- hard request ceiling `8` and explicit private-transmission flag.

The two page images must not be placed directly into Actions secrets unless their encoded size fits GitHub's secret limit and image quality remains adequate; this is not the recommended path.

## Current verification

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

No live OCR request has been executed and no private image has been transmitted by this branch.

## User decision required now

Choose one execution path:

```text
A) local execution — recommended
B) GitHub Actions — requires a secure source for the two images in addition to the Actions secret
```

## Exact continuation point

- If Path A is selected, provide exact local commands and process only the aggregate report.
- If Path B is selected, add `AVALAI_API_KEY` as an Actions secret, define the secure two-image transport, then implement a manual workflow that produces only the aggregate report.
- Do not change production OCR routing or the 42/77 score before measured evidence is recorded.