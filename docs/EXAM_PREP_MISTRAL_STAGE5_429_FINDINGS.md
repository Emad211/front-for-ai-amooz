# Exam-Prep Mistral — Stage-5 429 celery-log analysis (does it hurt accuracy?)

**Status:** analyzed · **Engine:** `mistral_ocr4_document_visuals_stage5` (default production PDF path)
**Branch:** `work/mistral-stage5-live-readiness`

The owner ran the production Mistral OCR PDF pipeline on the 58-page / 145-question Konkur booklet, watched
the celery worker log, and asked three questions:

> «باید لاگ سلری هم دقیق بررسی بکنی و ببینی چرا این همه ارور تو منی ریکوست می‌خوریم و آیا اینکه این دقت
> کار مارو کم نمی‌کنه و مشکل اساسی نداریم اینجا؟»

1. **Why so many `429` errors across so many requests?**
2. **Does that reduce our accuracy?**
3. **Is there a fundamental problem here?**

Short answers: **(1)** by design Stage-5 fans out one small request *per numbered question + solution
region*, so a 145-question booklet fires ~150–290 requests in a concurrency-4 burst — AvalAI's rate
limiter answers some with `429`; **(2) no** — a `429`-blocked region falls back to the full deterministic
Stage-2 content and Stage-5 only *appends* an advisory (non-gating) marker, so the published question is
identical to what it would have been; **(3) no fundamental problem** — bounded SDK backoff absorbs the
burst and the sliding-window executor already self-paces, so the load-bearing fix is **backoff, not a
lower concurrency cap and not artificial pacing.** Details below.

Companion notes: publish/review gate in `EXAM_PREP_MISTRAL_PUBLISH_REVIEW_OVERHAUL.md` (§5 has the
one-line 429 fix); causal chain in memory `exam-prep-publish-gate-chain`.

---

## 1. Why the celery log is full of `429`s — it's the Stage-5 fan-out shape, not a bug

Stage-5 is a **per-region source re-read**: for every numbered question (and every solution region) it
sends **one small, single-crop, source-only** request to the Avalai gateway. That is the whole design —
one cheap verification request per region, never a batch.

- Concurrency is `EXAM_PREP_STAGE5_MAX_CONCURRENCY`, **default 4**, clamped 1..8
  (`exam_prep_mistral_stage5.py:143`).
- A 145-question booklet therefore submits **~150–290 requests** (questions + solution regions) through a
  4-wide window in a short window of wall-clock.

AvalAI enforces a per-key request-rate limit. A sustained 4-in-flight burst of ~200+ requests inevitably
touches that ceiling, and the gateway answers the overflow with HTTP `429 Too Many Requests`. So a log
full of `429` lines on a large booklet is the **expected shape of a healthy high-throughput run**, not an
error condition — the same way a busy HTTP client sees `429`s and retries. It is *not*:

- a wrong endpoint or auth failure (those are `401`/`404`, and the run would produce zero questions);
- a payload-too-large / model error (those are `400`/`413`);
- a symptom of retries hammering — see §3, the executor holds the worker slot during backoff so a
  backing-off request does **not** free a slot for a new one.

**What changed the `429`s from fatal to harmless (commit `a929670`).** The region transcriber used to call
`.with_options(max_retries=0)` — so the *first* `429` on a region became an immediate `blocked_main_failed`
and stamped that region the (then-critical) code `stage5_finalization_blocked`, which cascaded into an
unpublishable session. It now calls `.with_options(max_retries=_max_retries())`
(`exam_prep_mistral_region_transcriber.py:306,318`), where `_max_retries()` reads
`EXAM_PREP_STAGE4_MAX_RETRIES` (**default 3**, clamped 0..6, `:121-137`). The OpenAI client does
exponential backoff **+ jitter** on `429`/5xx internally, so each `429` becomes a short backed-off retry
that almost always succeeds on attempt 2–4. `provider_attempts` in the usage context reports
`max_retries + 1` (`:314`) so the log is honest about how many tries a region took.

You will still *see* `429` lines in the log even after the fix — that is the SDK reporting a retry it then
recovered from, not a failure. The meaningful signal is whether regions end `blocked_*`, not whether
`429` appears.

---

## 2. Accuracy is **not** reduced — a blocked region falls back to full Stage-2 content

This is the key question, and the answer is structural, not a matter of luck or budget.

Stage-5 is **additive verification layered on top of a complete deterministic extraction**, never the
source of a question's content. The finalize step proves it in one line
(`exam_prep_mistral_stage5.py:1219`):

```python
question = dict(questions.get(number, raw))
```

- `raw` is the **full Stage-2 deterministic question** (stem + options + solution + visuals), already
  assembled by the frozen `exam_prep_mistral_stage2_core` before Stage-5 ran.
- `questions.get(number, ...)` is the Stage-5 *re-read* result for that region — used **only if it exists**.
- When a region is `429`-blocked past its retry budget, there is no Stage-5 entry for `number`, so `.get`
  returns `raw` — **the question keeps its complete Stage-2 content unchanged.**

The only thing a block adds is an advisory marker (`:1221-1223`):

```python
if number in blocked_questions:
    if _STAGE5_BLOCKER not in issues:
        issues.append(_STAGE5_BLOCKER)      # "stage5_finalization_blocked"
```

`stage5_finalization_blocked` is **not** in `REVIEW_BLOCKING_ISSUE_CODES`
(`{no_questions, missing_question_text, missing_options}`), so it does **not** force review and does **not**
block publishing (see the publish/review overhaul doc). It is a metadata hint that "the optional second
opinion didn't run for this region," nothing more.

So the accuracy contract is:

| Stage-5 outcome for a region | Question content that gets published |
|------------------------------|--------------------------------------|
| Re-read succeeded            | Stage-2 content, optionally refined by the source re-read |
| `429`-blocked (retries exhausted) | **Full Stage-2 content, unchanged** + advisory `stage5_finalization_blocked` |

A `429` therefore costs us *the optional extra verification pass on that one region*, not any question
text, option, answer, or visual. The floor is always the complete deterministic Stage-2 extraction. This
is why the owner sees good extraction quality even on runs whose logs are noisy with `429`s.

---

## 3. No fundamental problem — the executor self-throttles; backoff is the right lever

A natural worry is "if every `429` triggers a retry, don't the retries pile on and make the rate-limiting
*worse* — a retry storm?" They don't, because of how the Stage-5 fan-out is scheduled.

`_transcribe_many` runs a **sliding-window `ThreadPoolExecutor`** with
`max_workers = min(_max_concurrency(), len(items))` and a `fill_window()` that submits exactly **one new
region each time a worker finishes** (`exam_prep_mistral_stage5.py`, `_transcribe_many`). Crucially, a
worker slot is held for the *entire* lifetime of a region request **including its SDK backoff sleeps** — a
region that is mid-backoff on a `429` is still occupying its slot, so `fill_window()` **cannot** submit a
new request in its place. The consequence:

- In-flight requests are capped at the concurrency window (≤ 4 by default) **at all times**, retries
  included. A backing-off request does not free capacity for a fresh one.
- When the gateway is rate-limiting, the backoff sleeps naturally **stretch the effective submit rate** —
  the window drains slower, so the pipeline paces *itself* down to whatever rate AvalAI will accept, then
  speeds back up. The executor + SDK backoff form a closed feedback loop.

Because of that, we deliberately added **no artificial pacing / jitter / sleep between submissions.** It
would be redundant with the self-throttling the executor already provides, and it would only slow healthy
runs. Likewise, **lowering the concurrency cap is the wrong fix**: it would make every run slower while
still hitting `429`s on the tail of a large booklet, and it does nothing about the real failure mode we
fixed (a *single* `429` being fatal at `max_retries=0`). The load-bearing fix is the bounded retry budget,
which converts a transient `429` into a recovered request; concurrency stays env-tunable
(`EXAM_PREP_STAGE5_MAX_CONCURRENCY`) for the owner to raise or lower per deployment without touching code.

Additional guardrails that make a noisy-but-recovering run safe rather than runaway:

- **Bounded retries** — `EXAM_PREP_STAGE4_MAX_RETRIES` (default 3, hard-clamped 0..6) means a region that
  is *genuinely* unreachable gives up after a few attempts and falls back to Stage-2 (§2), rather than
  retrying forever.
- **Wall-clock ceiling** — `EXAM_PREP_STAGE5_MAX_WALL_SECONDS` (default 1800, clamp 300..2700,
  `:147-153`): the whole Stage-5 fan-out is time-boxed, so even a pathologically rate-limited run ends and
  publishes the Stage-2 floor instead of hanging.
- **Cost budget + cancel** — the finalize loop also blocks regions on `blocked_stage5_cost_budget` when the
  reservation is exhausted (`:1195-1200`) and honors cooperative cancel; both degrade to the Stage-2 floor,
  never to broken output.

### Verdict

- **Why so many `429`s:** the per-region fan-out (≈150–290 requests) at concurrency 4 legitimately reaches
  AvalAI's rate limit; the SDK now reports each as a recovered retry, so they're visible but harmless.
- **Accuracy impact:** none — a blocked region publishes the full deterministic Stage-2 content and only
  gains a non-gating advisory marker (`exam_prep_mistral_stage5.py:1219`).
- **Fundamental problem:** none — the sliding-window executor self-throttles under backoff, so bounded SDK
  backoff (not a lower cap, not artificial pacing) is the correct and sufficient fix. Concurrency, retries,
  wall-clock, and budget are all env-bounded.

---

## 4. What the owner should watch in the log

- `429` lines that are followed by a successful region result → **normal**, ignore.
- A region ending `blocked_main_failed` after `provider_attempts` tries → that region fell back to Stage-2
  and carries advisory `stage5_finalization_blocked`; the question still publishes. If *many* regions block,
  the key is being rate-limited harder than 3 retries can absorb → **raise `EXAM_PREP_STAGE4_MAX_RETRIES`
  (up to 6) and/or lower `EXAM_PREP_STAGE5_MAX_CONCURRENCY`** via env; no code change needed.
- `blocked_stage5_cost_budget` → the run hit its cost reservation, not a rate limit; raise the Stage-5
  budget env if the booklet is large.

## 5. Out of scope

Tuning AvalAI's account-level rate limit itself (a gateway/plan setting) is outside the codebase. The
pipeline is designed to run correctly *under* whatever limit the key has, degrading to the Stage-2 floor
rather than failing.
