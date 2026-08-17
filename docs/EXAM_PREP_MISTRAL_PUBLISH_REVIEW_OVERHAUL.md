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

  **The `require_publishable=False` path is now purely *structural*** (see §4.1) — every check is a
  type/schema-version/shape assertion on durable pipeline evidence. It carries **no numeric-consistency
  checks**, because those measure publish-*readiness*, not forgery, and a healthy degraded run fails
  them (see §4.1).
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

### 4.1 Gate B is structural-only — the second degraded-run block, and its fix

After the two-tier issue model + the 429 backoff landed (commit e92e6f6), the owner re-ran the same
58-page Konkur booklet and publishing was **still refused** (red toast *"خروجی معتبر و آماده بازبینی
مراحل ۱ تا ۵ برای انتشار موجود نیست."*). The 429 flood was gone and the session reached
review, but Gate B itself still returned `False`.

Root cause — Gate B's `require_publishable=False` path used to end with a **numeric-consistency**
check `not (0 <= primaryCalls <= regions)`. But:

- Stage-5 policy allows `maxPrimaryDegradedRechecksPerRegion: 1` (`exam_prep_mistral_stage5.py`), and
- `riskEngine.stats.primaryCalls` is a **sum across all regions**.

So a single legitimate degraded recheck pushes `primaryCalls > regions` — a **healthy** signal (the
pipeline retried a shaky region), not a forged one. Gating on it wrongly blocked real 100+ question
booklets. The sibling equalities on that path (`recordedPrimaryCalls == primaryCalls`,
`recordedUnresolved == blocked`, `riskRegionCount == regions`) compared a `stats`-derived value to
itself — always-true dead weight.

**Fix:** the `require_publishable=False` path now returns `True` as soon as the **structural**
anti-forgery block passes (engine/stage/readyForReview + the five schema-versioned stage
fingerprints). All numeric-consistency checks were removed from it. Those checks survive **only** in
the dead `require_publishable=True` branch (0 production callers — all four callers use the default;
confirmed by grep), kept as a latent publish-readiness helper and for its unit coverage. Structural
forgery detection is unchanged: a bare `{'engine': PRODUCTION_ENGINE, 'status': 'passed'}` workflow
still fails (missing OCR pages / question intervals / risk-engine schema) → `409
production_audit_required`.

Regression: `test_publish_endpoint_allows_degraded_run_with_recheck_call_inflation` (a blocked region
+ `primaryCalls=3 > regions=2`) publishes 200; `test_publish_endpoint_blocks_forged_production_workflow`
still 409. Both in `test_exam_prep_page_review.py`.

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

### 7.1 Second-round owner fixes (edit-form review UX + مرحله ۲ performance)

After the publish gate was unblocked, the owner ran the 58-page / 145-question booklet through the
teacher UI and reported four follow-ups. All are frontend-only; each is `tsc --noEmit` clean.

- **Hide advisory warnings, show only review-blocking (C)** — `exam-edit-form.tsx`. Because
  `describeExamReviewIssue` already sets `severity === 'critical'` **iff** the code is in
  `REVIEW_BLOCKING_EXAM_CODES` (§7), "show only critical" is exactly `filter(i => i.severity ===
  'critical')`. The global-issues card now guards/counts/maps over `blockingGlobalIssues =
  globalIssues.filter(i => i.severity === 'critical')`; per-question issue rows filter to
  `severity === 'critical'` and render a fixed `بحرانی` destructive badge (no more `هشدار` rows);
  the accordion-trigger badge reads `نیازمند بازبینی · {review.criticalCount}`. Advisory issues are
  no longer surfaced in the edit lane — matching the owner's *"هشدارها همه پاک بشن، فقط بحرانی‌ها"*.
- **Add/remove options when options are incomplete (D)** — `exam-edit-form.tsx`. Persian option
  labels (`PERSIAN_OPTION_LABELS = ['الف','ب','ج','د','ه','و','ز','ح','ط','ی']`) + `nextOptionLabel`
  pick the first unused label. `addOption(questionIndex)` appends `{label, text_markdown:''}`;
  `removeOption` drops one and falls the `correct_option_label` back to `options[0]?.label ?? null`
  when the removed option was the key. Each option row gained a ghost `Trash2` remove button and the
  grid an outline **«افزودن گزینه»** (`Plus`) button, so a question extracted with < 4 options can be
  completed in place. `addQuestion` seeds four labelled options + `correct_option_label` =
  `PERSIAN_OPTION_LABELS[0]`.
- **Rendered-LaTeX preview + math keyboard in the edit section (E)** — `exam-edit-form.tsx`. The stem
  (`متن اصلی سؤال`) and teacher-solution (`تحلیل و راه‌حل مدرس`) `<Textarea>`s were swapped for
  `LatexMarkdownEditor` (`@/components/exercises/latex-markdown-editor`) — the exact component used in
  **ساخت تمرین**, which carries an always-on live `MarkdownWithMath` preview and a toggleable
  «کیبورد ریاضی». Its `onChange` yields the new string, wired straight into `updateQuestion`; the
  solution editor stays inside the `space-y-2` block above the solution-visuals `.map`
  (`ProtectedExamVisual`, `role === 'solution'`), so images still render. No new dependency — the
  feature is reused verbatim from the exercise builder.
- **مرحله ۲ latency — lazy per-card mount (B)** — `my-exams/[examId]/page.tsx`. `MarkdownWithMath`
  runs one KaTeX `renderMathInElement` pass per instance (in a `requestAnimationFrame` effect) and
  `ProtectedExamVisual` fires one authenticated blob fetch on mount. Mounting all 145 question cards
  the instant the accordion opened meant ~870 typeset passes **plus** a fetch burst — the *"دیلی بسیار
  زیاد"* the owner hit. Fix: a local `LazyMount` wrapper reserves a fixed-height (`200px`) placeholder
  per card and only mounts the real `<Card>` once it scrolls near the panel's own scroll viewport
  (`IntersectionObserver` with the `max-h-[60vh] overflow-y-auto` container as `root`, `rootMargin:
  '800px'` for pre-render), then keeps it mounted. Initial work drops from all-cards to the ~10
  on/near screen; the rest render progressively as the teacher scrolls. Falls back to eager render
  where `IntersectionObserver` is unavailable. No virtualization dependency, no data-shape change.

### 7.2 Third-round owner fixes (inline-option recovery + option-visual placement + form cleanup)

After the second round, the owner ran the 58-page / 145-question booklet again and reported that **24 of
145 questions were forced into the review lane**, 23 of them with `missing_options` and one (Q19) with
`missing_question_text`. The demand: *"نمی‌خواهم حتی یک سؤال رو ببینم که برای بازبینی برگشت داده شده"* —
zero questions in the review lane — **without** dropping the gate (a genuinely broken question must still
block).

**Root cause (data-extraction, not a gate).** `mistral-ocr-4-0` sometimes emits the four numbered options
*inside* the question stem and leaves `options[]` empty. The frozen region parser
(`exam_prep_mistral_stage2_core.parse_question_region_text`) has an `all(item["text_markdown"] …)` guard
(`:201`): when the 4th option marker (`۴)`) has empty text — an image option or an OCR truncation — the
whole run is discarded, options stay inline in `question_text_markdown`, `options == []`, and
`canonical_question_issues` fires the **review-blocking** `missing_options`. 23 of 24 review items were
exactly this shape (the 24th, Q19, was a true empty stem → legitimately stays blocked).

**Fix — deterministic, provider-free, pre-quality recovery** (`exam_prep_mistral_production.py`):

- `_split_inline_stem_options(stem)` strips the leading question heading, then reuses the frozen core's
  own detectors (`_QUESTION_HEADING_RE`, `_marker_sequence`, `_OPTION_MARKER_RE` → `_PAREN_OPTION_RE`
  fallback, `_clean_option_text`) to split a clean `۱)…۲)…۳)…۴)` run off the tail. Returns the recovered
  stem + labelled options, or `None` when there is no real stem before the markers (so an option-marker-only
  string is **not** mistaken for a question).
- `_recover_inline_stem_options(result)` runs over the assembled projection, touching **only** questions
  with `< 2` options and a recoverable stem. It writes the trimmed stem + `options[]` (labels preserved
  even when a value is empty — an image option or truncation) and drops the now-stale region code
  `mistral_question_option_parse_failed`. Wired into `run_exam_prep_mistral_pipeline` **between**
  `attach_source_regions` and `rebuild_assembly_quality`, so the canonical recompute sees the recovered
  options and the review gate clears naturally.

This is a **data fix, not a gate drop**: a question with a real stem but genuinely no option markers, or a
true empty stem (Q19), still surfaces `missing_options` / `missing_question_text` and stays review-blocking
per the locked policy. Because `canonical_question_issues` only fires `missing_options` when
`len(options) < 2` (empty option *text* is advisory `missing_option_text`), recovering ≥ 2 labelled options
is sufficient to clear the lane while preserving image/empty options for the render layer.

The frozen `exam_prep_mistral_stage2_core.py` is **untouched** — the recovery lives entirely in the
production facade and reuses the core's detectors read-only.

**Frontend — option-visual placement + form cleanup** (`exam-edit-form.tsx`):

- **Image options render *as* options (D)** — *"گزینه‌هایی که خودشون تصویر هستن هم باید به‌عنوان گزینه
  نمایش داده بشن"*. The stem-adjacent visual grid used to lump **all** non-solution visuals
  (`role !== 'solution'`) above the stem, disconnected from their option. It now renders **only**
  `role === 'question'` visuals there; each `role === 'option'` visual renders **beside its matching option
  row**, matched by `visual.optionLabel === option.label`, inside the options map. An orphaned-option
  fallback block (an `option` visual whose `optionLabel` matches no current option — null label, or the
  teacher removed the row) renders under the options grid so a visual is **never silently dropped**. The
  pipeline-output panel (`my-exams/[examId]/page.tsx`) and the student view (`question-content.tsx`)
  already did this exact `optionLabel === label` matching (incl. the student-view orphan fallback) — only
  the edit form was inconsistent, now aligned across all three surfaces.
- **Remove the "خروجی نهایی (نتیجه)" field (C)** — *"«جوابِ نهایی چیه» رو هم پاک بکن"*. The
  `final_answer_markdown` `<Input>` and its two-column wrapper were removed from the per-question form;
  the "انتخاب گزینه صحیح" `<Select>` is now full-width. The backend data shape is **unchanged**
  (`final_answer_markdown` stays in the payload / factory default) — this is a display-only removal.

**Regression + hygiene:**

- `test_exam_prep_mistral_inline_option_recovery.py` (**new**, 6 tests, provider-free): splitter recovers
  the real broken shape and keeps the empty trailing option; recovery clears the `missing_options` gate;
  labels are emitted for a pure-image (all-empty) option row; a marker-less stem and an option-marker-only
  string stay unrecovered; questions with existing options are untouched.
- **Stale prompts-contract allow-list** — `test_prompts_contract.py::test_no_unexpected_top_level_keys` was
  **already red on `main`** (unrelated to this round): 7 genuinely-live prompt keys
  (`exam_prep_page_extraction`, `exam_prep_question_audit`, `exam_prep_question_repair`, and the four
  `exam_prep_v4_*`) existed in `PROMPTS` but were never added to `LIVE_KEYS`. Added them (each `["default"]`)
  so the guard is green. **No prompt wording changed** — this is a test-fixture correction only.

Both frontend surfaces are `cd frontend && npx tsc --noEmit` clean; the touched backend suites
(`test_exam_prep_mistral_production_core/boundary`, `_inline_option_recovery`, `_visual_only_options`,
`_question_verifier`, `test_exam_prep_page_output`, `test_prompts_contract`) pass.

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

---

## 11. Progress-bar honesty — OCR band vs Stage-5 tail

**Symptom (owner):** on a ~8-minute run the bar hit **90%** in the first ~2 minutes — while only OCR
had run — then froze there for the ~6 minutes of real extraction work.

**Root cause:** `tasks_exam_prep.on_page_complete` mapped OCR page completion onto `20 + (completed/
total)*70`, so 58/58 pages read = 90%, under a stage mislabelled `extracting_questions`. Stages 2–5 (the
majority of wall-clock, dominated by the per-question Stage-5 source re-read) emitted **no** progress
until the terminal `progress=100`.

**Fix — wall-clock bands, not page count** (`tasks_exam_prep.py`):

- Pure, unit-testable `_band_progress(completed, total, *, floor, ceiling)` clamps the fraction to
  `[0,1]` and maps it into a band. Two bands, ordered with headroom below terminal 100:
  - **OCR** → `reading_source`, `OCR_PROGRESS_FLOOR=15 → OCR_PROGRESS_CEILING=40`. Finishing every
    page now reads 40%, never 90%. The short deterministic Stages 2–4 sit in the seam at the ceiling.
  - **Stage 5** → `extracting_questions`, `STAGE5_PROGRESS_FLOOR=40 → STAGE5_PROGRESS_CEILING=95`. The
    long tail carries the bar up as each numbered question/solution region is re-read.
- New `on_region_complete(completed, total)` heartbeat plumbed **tasks → production facade →
  `exam_prep_mistral_stage5`**: `run_exam_prep_mistral_pipeline(..., on_region_complete=…)` forwards it
  to `finalize_stage5_regions(..., on_region_complete=…)`, which passes it as `on_progress` into the
  **primary** `_transcribe_many` pass only (one call per eligible region). Fired from the completion
  loop after each outcome is recorded; **best-effort (try/except)** so a DB/progress-sink hiccup can
  never abort the paid fan-out. Retry (non-transient) path now resets to `reading_source` /
  `OCR_PROGRESS_FLOOR` instead of the old `extracting_questions` / 20.
- Frontend `pipeline-tracker.tsx` stays a passive renderer (`effectiveProgress = progressPercent`
  verbatim); the OCR→`reading_source` / Stage-5→`extracting_questions` mapping matches its
  stage-chip order. **Backend-only fix.**

**Regression guard:** `test_exam_prep_progress_bands.py` (provider-free) — OCR 58/58 → 40 (not 90),
fraction clamp on over/under-count, Stage-5 completion → 95, band ordering leaves headroom for terminal
100. The facade signature-lock tests (`test_exam_prep_mistral_production_boundary.py`,
`test_exam_prep_mistral_stage5_runtime.py`) now include `on_region_complete` after `on_page_complete`.
