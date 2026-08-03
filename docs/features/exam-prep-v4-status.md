# Exam Prep V4 — Implementation Status Ledger

> Living execution ledger. Update this file before every V4 implementation step. Canonical roadmap: `exam-prep-v4-source-aware-split-pipeline.md`.

- **Branch:** `feat/exam-prep-v4-source-aware`
- **PR:** #4 — Draft
- **Execution mode:** Critical Path Acceleration
- **Current roadmap span:** Phase 4 → Phase 7 vertical extraction path
- **Last completed slice:** guarded manual GitHub Actions orchestration for the two-page AvalAI OCR live smoke
- **Active gate:** extract two representative pages from the three private fixtures now present on `main`, then execute the bounded live OCR smoke
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

Official pages re-read for this gate:

```text
https://docs.avalai.ir/fa/api-reference/ocr
https://docs.avalai.ir/fa/examples/processing_documents_with_mistral_ocr
https://docs.avalai.ir/fa/models/mistral-ocr-2512
```

## Product-owner authorization and credential state

The product owner has now explicitly authorized live requests and confirmed that repository Actions secret `AVALAI_API_KEY` is configured.

The user placed these three private benchmark PDFs at the repository root on `main`:

```text
دفترچه اول (زیست).pdf
دفترچه دوم .pdf
دفترچه سوم.pdf
```

The PDFs may be read inside the GitHub runner for the authorized feasibility smoke. This does **not** authorize sending complete PDFs to AvalAI. Only two extracted page images may leave the runner, with a hard ceiling of eight OCR requests.

## Selected two-page smoke fixture

Use `دفترچه اول (زیست).pdf` because it is the strongest candidate for RTL text plus biological diagrams/formulas.

Selected physical pages:

```text
question page: 5
answer-solution/continuation page: 12
```

These are interior pages of the previously recorded ranges:

```text
cover: 1
questions: 2–8
answer_solutions: 9–16
```

Selecting interior pages avoids cover/boundary bias while preserving representative question and solution evidence.

## Active implementation contract

Modify only the guarded manual OCR workflow so it:

1. checks out the V4 branch code;
2. fetches the named PDF from `origin/main` into a private runner-temp directory without adding it to the feature branch;
3. validates PDF signature and expected page count;
4. renders physical pages 5 and 12 to bounded PNG images locally;
5. sends only those two PNGs through the four existing smoke modes;
6. executes at most eight requests with pinned `mistral-ocr-4-0`;
7. uploads only `aggregate-report.json` for one day;
8. deletes the temporary PDF, PNGs, path files, and local report in an `always()` cleanup step;
9. never prints or artifacts source bytes, OCR text, annotations, data URLs, credentials, or raw provider output.

## Current verification before this implementation

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

No live OCR request has yet been executed by this branch.

## User action required

No additional credential or file-upload action is required. The next implementation step is fully defined.

## Exact continuation point

Update the guarded manual workflow from URL-secret input to direct private extraction of physical pages 5 and 12 from `دفترچه اول (زیست).pdf` on `origin/main`. Add static workflow tests, run focused CI, then manually dispatch the live smoke if the workflow gate is green. Do not change production routing or the 42/77 score before measured evidence is reviewed.