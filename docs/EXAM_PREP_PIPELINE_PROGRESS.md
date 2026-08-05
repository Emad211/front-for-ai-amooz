# Exam Prep PDF Pipeline — Progress Log

## 2026-08-05 — Layout, content integrity, and cancellation hardening

Baseline evidence from live session 191:

- 16 physical PDF pages.
- Page 1 was a cover but consumed four requests and became a failed chunk.
- Pages 9–16 used a full-page request plus two column requests.
- 40 AvalAI requests total.
- 50 questions assembled; one visible review question, but additional deterministic
  output defects existed (serialized options, missing gradable labels, copied solution).

Implemented in PR #19 on branch `fix/exam-prep-layout-content-integrity`:

1. Conservative local cover/non-content classifier with zero-call skip.
2. Sparse figure/continuation pages are never skipped merely for having little text.
3. Local single/double/uncertain layout router.
4. One multi-image request for uncertain layout.
5. Two-call double-column path with retry limited to the failed column.
6. Hidden response-format fallback calls are disabled in routed extraction.
7. Loose page envelope and independent record quarantine.
8. Deterministic serialized-option decoding and unresolved-payload gate.
9. Persian combining-hamza correct-option inference.
10. Missing gradable option-label gate and explicit counters.
11. Cross-question duplicate-solution detection.
12. Cancellation-aware targeted verifier.
13. Per-page and final provider-call accounting.
14. Focused regression tests for routing, integrity, sparse visuals, and cancellation.
15. Decision contract recorded in `docs/EXAM_PREP_PIPELINE_DECISIONS.md`.

Verification contract:

- PR #19 must pass the focused Exam Prep PostgreSQL/frontend gate before merge.
- The complete backend PostgreSQL suite is the final backend gate.
- The repository-wide frontend typecheck may continue to show unrelated legacy
  failures; focused Exam Prep frontend validation is the gate for this backend/docs-only PR.
- After deployment, the same 16-page PDF must be run again and its output and Celery
  logs compared against session 191. The live run, not unit tests, confirms the real
  provider request count and exposes any document-specific edge cases.

Exact continuation point after merge:

1. Deploy the merged main revision.
2. Re-run the original 16-page PDF.
3. Collect the complete Celery log and rendered transcript.
4. Verify page 1 is `skippedNonContent`, pages 9–16 use the expected routed budgets,
   no raw serialized options reach output, questions 21–23 have gradable labels, and
   question 8/44 are either source-corrected or explicitly review-blocked.
5. Record the real `totalProviderCalls` and address only evidence-backed remaining gaps.
