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

## 2026-08-05 — Completion actions and persistent publication UX

Problem found after the first merged live run:

- A completed but publication-blocked Exam Prep draft was persisted with
  `status=exam_transcribed` even though `workflow_state.stage=ready_for_review` and
  `readyForReview=true` correctly showed that processing had finished.
- The create flow treated only `exam_structured` as terminal, so its primary processing
  button remained visible instead of switching to the two completion actions.
- The exam detail page rendered the publish button only when publication was already
  allowed, so the action disappeared completely while processing, blocked, failed, or
  already published.

Final decision and implementation:

1. Backend publication safety remains fail-closed and its status contract is unchanged.
2. A publishable completed draft uses `status=exam_structured`.
3. A completed draft with unresolved critical issues can remain `status=exam_transcribed`,
   while `workflowStage=ready_for_review`, `readyForReview=true`, and
   `publicationBlocked=true` identify it as finished but not publishable.
4. The create UI determines Exam Prep completion from workflow readiness, not from the
   status field alone, and polling stops as soon as the draft is ready for review.
5. The terminal create-flow actions are exactly:
   - `ساخت آمادگی آزمون جدید`
   - `رفتن به آزمون‌های من`
6. The exam detail page always renders the publication action in both the header and the
   publication card.
7. When publishing is not allowed, the button remains visible but disabled and a precise
   reason is shown; no frontend state bypasses the backend publication gate.
8. Existing `exam_transcribed + readyForReview` drafts are handled correctly without a
   database migration or status rewrite.
9. Published exams keep a disabled `منتشر شده` action as a stable visible state.

Focused verification targets:

- A publishable completed draft is terminal and publish-enabled.
- A review-blocked completed draft is terminal but publish-disabled.
- A bare intermediate `exam_transcribed` state without workflow readiness is not treated
  as publishable.
- Processing, failed, empty, review-required, and published states all retain a visible
  publication button with the correct disabled reason or final label.
