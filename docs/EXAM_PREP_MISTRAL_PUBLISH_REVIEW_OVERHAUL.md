# Exam-Prep Mistral — Publish/Review overhaul, visuals-everywhere, 429 fix

**Status:** shipped · **Engine:** `mistral_ocr4_document_visuals_stage5` (default production PDF path)
**Branch:** `work/mistral-stage5-live-readiness`

This records why a fully-extracted Mistral OCR exam session used to be unpublishable, the two
owner-locked policy decisions that reshaped the review/publish gate, and exactly what changed.
Companion causal-chain note lives in memory `exam-prep-publish-gate-chain`.

---

## 1. The failure that triggered this (session-198)

Owner ran the production Mistral OCR PDF pipeline on a 58-page Konkur booklet (145 questions).
Extraction quality was good, yet **every question was blocked from publishing**.

Root cause — a **Stage-5 429 flood**:

- The region transcriber (`services/exam_prep_mistral_region_transcriber.py`) called
  `.with_options(max_retries=0)`.
- Stage-5 fans out **one small source-only request per numbered question + solution region** at
  `EXAM_PREP_STAGE5_MAX_CONCURRENCY` (default 4). Across a 145-question burst, AvalAI rate-limited.
- With `max_retries=0`, each 429 became an immediate `blocked_main_failed` and stamped the region
  the **critical** code `stage5_finalization_blocked`.
- Any code in `CRITICAL_ISSUE_CODES` made `is_critical_page_issue` True → Stage-5 set
  `publication_ready = False` → `tasks_exam_prep.py` landed the session in `EXAM_TRANSCRIBED`
  (not `EXAM_STRUCTURED`) with `workflow_state.publication_blocked = True` → the publish view
  refused.

`native_pdf_answer_label_authority` on all 145 questions was a **red herring** — a healthy native
answer-key lock, never in the critical set.

---

## 2. Two locked policy decisions (owner, via AskUserQuestion)

These are product decisions, verbatim, and govern the whole subsystem:

1. **"واقعاً خراب" (→ forced review) = ONLY** a question with **no options** OR **no
   question-stem text** — *"سوال بدون گزینه و یا سوال بدون صورت سوال"*. The empty-exam case
   (`no_questions`) is included. **Everything else** — Stage-5 rate-limit blocks, image-based
   options, visual-evidence hints, answer-label authority, LaTeX doubts, missing/duplicate question
   numbers — is an **advisory warning**: surfaced to the teacher, never forcing review.

2. **Publish policy = "همیشه مجاز"** (always allowed). Publishing is gated **only** by teacher
   ownership + proof the pipeline actually ran (anti-forgery). Never by issue counts, critical
   counts, or a review-confirmation step.

---

## 3. The two-tier issue model (the core lever)

`services/exam_prep_page_output.py` now carries **two** sets:

| Set | Role | Members |
|-----|------|---------|
| `CRITICAL_ISSUE_CODES` (unchanged) | **Advisory** — drives `criticalIssueCount` + per-issue display. Does **not** gate anything. | broad (Stage-5 blockers, visual-critical, etc.) |
| `REVIEW_BLOCKING_ISSUE_CODES` (**new**) | **The only gate** for status / review lane / publish. | `no_questions`, `missing_question_text`, `missing_options` |

Helpers added next to `is_critical_page_issue`:

- `is_review_blocking_issue(code) -> bool`
- `review_blocking_question_keys(issues) -> set[(scopeKey, questionNumber)]`
- `count_review_blocking_issues(issues) -> int`

**Every audit-status computation** now derives `status`/`questionsNeedingReview`/
`usableQuestionCount` from `review_blocking_question_keys(issues)` **plus** any unrecoverable
physical page (`failedPageNumbers`), while keeping `criticalIssueCount` as the broad advisory metric:

- `build_strict_page_first_audit` (`exam_prep_page_output.py`)
- `_promote_own_critical` (`exam_prep_mistral_production.py`)
- `promote_integrity_audit` (`exam_prep_projection_integrity.py`)
- `audit_page_first_projection` (`exam_prep_page_review.py`)
- `_downgrade_intentional_number_gaps` / `_refresh_exam_review_state` (`views_exam_prep_review.py`)
- `revalidate_exam_prep_teacher_edit` (`signals.py`)
- Stage-5 `finalize_stage5_regions` `publication_ready` (`exam_prep_mistral_stage5.py`) — switched
  `is_critical_page_issue` → `is_review_blocking_issue`.

Net effect: a question carrying only advisory issues (`stage5_finalization_blocked`,
`visual_evidence_required`, `missing_option_text`, `placeholder_option_text`, …) is **publishable**,
so a normal run now lands in `EXAM_STRUCTURED` automatically. Genuinely-broken questions (no
stem / no options) and unrecoverable pages still force `needs_review`.

---

## 4. Publish gate (`views.py` `ExamPrepSessionPublishView`)

Final gate order (owner-ownership scoped throughout — `teacher=request.user`, 404 otherwise):

- **Gate A** — accept both `EXAM_TRANSCRIBED` **and** `EXAM_STRUCTURED` (both are valid
  post-pipeline review states; a degraded run legitimately lands `EXAM_TRANSCRIBED`). Still reject
  `failed` / processing / `cancelled`.
- **Gate B** — for the Mistral engine only, `production_review_artifact_is_valid(workflow)` **without
  `require_publishable=True`**. This is pure anti-forgery: it proves all five stages ran (Stage-1 OCR
  pages/models, Stage-2 numbering schemaVersion==2, Stage-3 visual pipeline schemaVersion==2 +
  sha256, Stage-4/5 risk-engine policy) — it does **not** demand zero blocked/critical.
- **Artifact block (v2/v3 inventory pipeline only, `pipeline_version >= 2`)** — Gate C
  (`extraction_review_required`), Gate D (generated-visual approval), Gate E
  (`teacher_extraction_confirmation_required`, `pipeline_version >= 3`) are **left intact**.

### Why the artifact block is safe to keep — and why it was wrong to drop globally

The original plan said "drop Gate C/E". Implementation review proved that over-reaches into a
**separate** pipeline's security contract. The default **Mistral production engine creates NO
`ExamPrepExtractionArtifact`** (`tasks_exam_prep.py` stores state only in `workflow_state` /
`exam_prep_json`). So for any Mistral session `artifact is None` and the entire block is inert —
"همیشه مجاز" for Mistral is delivered fully by **Gate A + engine-scoped Gate B alone**.

The v2/v3 inventory pipeline (`exam_prep_v3`, `views_v4_*`) is a different code path that *does*
persist an artifact and relies on Gate C/E for its own anti-forgery (review-binding via
`reviewed_revision` / `reviewed_projection_fingerprint`). The owner never asked to touch it, so it
stays. **Correct scoping = restore v3's gates, keep only the Mistral-facing relaxations.**

`exam_prep_mistral_readiness.py` is untouched; its `require_publishable=True` branch is simply no
longer reached from the publish view.

---

## 5. 429 fix (req #6) — bounded backoff, not a lower cap

`services/exam_prep_mistral_region_transcriber.py`:

- New `_max_retries()` env helper (`EXAM_PREP_STAGE4_MAX_RETRIES`, default **3**, clamped 0..6),
  alongside `_timeout()` / `_max_tokens()`.
- `.with_options(max_retries=0)` → `.with_options(max_retries=_max_retries())`.

The OpenAI client already does exponential backoff + jitter on 429/5xx, so a small retry budget
absorbs the burst. **No repair pass** — each attempt is the same single source-only request. Stage-5
concurrency stays env-tunable (`EXAM_PREP_STAGE5_MAX_CONCURRENCY`, default 4); backoff — not a lower
cap — is the load-bearing fix. `provider_attempts` in the usage context now reports
`max_retries + 1`.

---

## 6. Per-session token/cost (req #4)

`serializers.py` `ExamPrepSessionDetailSerializer` gains `usageSummary` (SerializerMethodField),
aggregating `LLMUsageLog` rows filtered by `session_id` (== `ClassCreationSession.id`, stamped via
`set_current_session_id(session.id)` in `tasks_exam_prep.py`):

```
totalTokens, inputTokens, outputTokens (ints), costUsd, costToman (floats), calls (int)
```

Mirrors the org-costs rollup; all-zero when a run logged nothing. Surfaced in the frontend مرحله ۱
report so the teacher reads a run's cost directly.

---

## 7. Frontend

- **`exam-review-utils.ts`** — new `REVIEW_BLOCKING_EXAM_CODES` mirrors the backend set byte-for-byte.
  `buildExamReviewSummary.needsReview` now = "issue set intersects the blocking set" (was
  "any issue"). `describeExamReviewIssue` downgrades displayed severity so **only** a missing
  stem / missing options render `critical`; every other code (incl. backend `severity:'critical'`
  advisories) renders as an advisory `warning`. `CRITICAL_EXAM_REVIEW_CODES` / `ISSUE_COPY` kept for
  copy/rendering.
- **`my-exams/[examId]/page.tsx`** — publish button `canPublish` dropped `extractionPassed` +
  `extractionReviewConfirmed`; now `!is_published && questions.length > 0 && !isProcessing &&
  status !== 'failed'`. Pipeline-panel مرحله ۲ renders `q.visuals` by role
  (question / option / solution) via `ProtectedExamVisual`; مرحله ۱ shows the token/cost line.
- **`classes-service.ts`** — `usageSummary?` added to `ExamPrepSessionDetail`.

### Student visuals (req #5) — already worked

`StudentExamPrepDetailView` emits per-question `visuals[]`; `QuestionContent` renders them via
`ProtectedExamVisual`. No code change needed — guarded by a payload test. If a specific exam lacks
images, the cause is upstream `exam_prep_json`, not the render path.

---

## 8. Tests

- `test_exam_prep_page_output.py` — `is_review_blocking_issue` True only for the 3 codes.
- `test_exam_prep_page_review.py` / `test_exam_prep_teacher_review_decisions.py` — advisory issues
  (`missing_option_text`, `source_verification_failed`, Stage-5 advisories) → `status == passed`;
  `missing_options` / `missing_question_text` → `needs_review` and **not** teacher-overridable.
- `test_exam_prep_mistral_visual_review.py` — visual-critical codes still **detected** from immutable
  source metadata and surfaced as critical advisories, but `status == passed`.
- `test_exam_prep_mistral_region_transcriber.py` — retries come from `_max_retries()` (env, default
  3), not hardcoded 0 (signature/mocked — **no live provider call**).
- `test_serializer_annotations.py` — `usageSummary` sums `LLMUsageLog` by `session_id`.
- `test_exam_prep_pipeline.py` — degraded `EXAM_TRANSCRIBED` session publishes (200); `failed` → 400.
- `test_exam_prep_inventory_api.py` / `test_exam_prep_v3.py` — v2/v3 Gate C/E **still block** (proves
  the inventory pipeline's anti-forgery survived).

Verified: 151 passed across the touched suites; `cd frontend && npx tsc --noEmit` clean.

---

## 9. Owner verification (live LLM forbidden in dev/CI)

1. Re-run the 58-page Konkur PDF: no 429 flood (backoff), lands `EXAM_STRUCTURED`, publish enabled.
2. Pipeline panel مرحله ۲ shows question/option/solution images; مرحله ۱ shows token count + cost.
3. Edit/review lane lists only genuinely-broken questions (empty for a clean run); all visuals shown.
4. Student opens the published exam → images render.

## 10. Out of scope

Garbled/doubled LaTeX from `mistral-ocr-4-0` on dense math is a model-quality issue, not a gate.
Not fixed here.
