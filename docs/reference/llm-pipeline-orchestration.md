# Reference — LLM pipeline orchestration (HUB)

- **Status:** Verified · **Created:** 2026-07-02 · **Last-verified:** 2026-07-02 (commit `2948d86`)
- **Owner (doc):** technical-writer · **Spec source:** `docs/reference/ROADMAP.md` step L4
- **Layer:** llm (cross-cutting HUB — every stage doc L5-L10 hangs off this spine)

## Purpose
The Celery orchestration spine: how the class 5-step and exam-prep 2-step pipelines are driven as
resumable, cancellable, heartbeat-monitored state machines on the `pipeline` queue. Stage *bodies* (what
each step asks the LLM) are L5-L10; this doc owns the flow, statuses, cancellation, and retries.

## Scope & paths
| File | Role |
|---|---|
| `apps/classes/tasks.py` (1101) | All pipeline tasks + orchestration helpers (grep by `@shared_task`/`^def`) |
| `apps/classes/models.py:12` | `ClassCreationSession.Status` (the state machine — B4) |
| `backend/core/settings.py:502-525` | `CELERY_TASK_ROUTES` + beat (B0) |

**Out of scope:** step LLM bodies → L5 (transcription), L6 (structure), L7 (prereqs/recap), L8 (quizzes),
L9 (exam-prep), L10 (pdf/cost); view→dispatch → B5/B7.

## Public surface — the tasks (`tasks.py`)
| Task | Queue | `max_retries` | Role |
|---|---|---|---|
| `process_class_step1_transcription` … `step5_recap` | pipeline | **3**, `acks_late` | the 5 class steps |
| `process_class_full_pipeline` | pipeline | **0**, `acks_late` | chains steps 1-5 inline |
| `process_exam_prep_step1_transcription` / `step2_structure` | pipeline | 3, `acks_late` | exam-prep steps |
| `process_exam_prep_full_pipeline` | pipeline | 0, `acks_late` | chains exam-prep |
| `pregenerate_student_assessments` | pipeline | 2 | pre-build a student's quizzes+exam |
| `send_publish_sms_task` / `send_new_invites_sms_task` / `send_teacher_message_sms_task` | default | 5 | SMS |
| `cleanup_stale_sessions` | default | 0 | beat (every 30 min) |

Helpers: `_run_pipeline_step` (`:265`), `_pipeline_cancelled` (`:232`), `_make_step1_heartbeat`
(`:333`), `_ingest_source_to_markdown` (`:369`), `_attribute_llm_usage_to_teacher` (`:61`),
`_safe_mark_failed`/`_safe_mark_cancelled`/`_safe_refresh`/`_safe_save`.

## Key flows
1. **Full-pipeline as a status-guarded state machine** (`process_class_full_pipeline:639`): each step runs
   ONLY if `session.status` is the step's expected precondition (`TRANSCRIBING`→step1,
   `TRANSCRIBED`→step2, …), so a re-dispatched pipeline **resumes** where it stopped rather than redoing
   work. Steps are called **inline** (not sub-tasks) to guarantee ordering; `max_retries=0` on the
   chainer (the inline `_run_pipeline_step` owns retries).
2. **Cooperative cancellation:** between EVERY step the chainer calls `_safe_refresh` +
   `_pipeline_cancelled` → on `cancel_requested` returns `{status:'cancelled', stopped_at:'stepN'}` and
   the session lands CANCELLED. The owner cancel endpoint also HARD-revokes the persisted
   `celery_task_id`. **Preserve these checkpoints when reordering steps.**
3. **Per-step retry** (`_run_pipeline_step:265`): up to 4 inline attempts, exp-backoff (15s→120s cap);
   `SoftTimeLimitExceeded` fails FAST (the signal fires once; retrying would hit the hard-limit SIGKILL)
   → `_safe_mark_failed`; genuine failure marks the session FAILED.
4. **Heartbeat** (`_make_step1_heartbeat:333`): long chunked transcription calls a `progress_cb` between
   chunks that bumps `updated_at` (so `cleanup_stale_sessions` never reaps a live run) and aborts on
   `cancel_requested` (→ `TranscriptionAborted`, never retried — L5).
5. **Ingestion dispatch** (`_ingest_source_to_markdown:369`): step-1 routes media→transcription (L5) OR
   PDF→extraction (L10) based on the source; reads the file to a temp path (never the whole video in RAM
   — the OOM fix).
6. **Cost attribution** (`_attribute_llm_usage_to_teacher:61`): decorator binding the session's LLM usage
   to the owning teacher (L10).

## Data & invariants
- **Queue split** (settings): all 9 pipeline tasks + pregeneration → `pipeline`; SMS + cleanup →
  `default`. Slow LLM/media work only on `pipeline` (hard 2h/soft 100min, prefetch=1). Don't put quick
  tasks on `pipeline`.
- The status state machine is the resume mechanism — a step's precondition guard must match the prior
  step's terminal status (B4 Status list).
- Cancellation checkpoints between steps + heartbeat + `TranscriptionAborted`-never-retried are the
  cancel contract — refactors must keep them.
- `cleanup_stale_sessions` (beat, 30 min) reaps only sessions with a stale `updated_at` in an in-progress
  status (`_get_in_progress_statuses:1034`) — the heartbeat is what protects live runs.

## Gotchas
- The chainer's `max_retries=0` is intentional (inline retries live in `_run_pipeline_step`); the
  individual step tasks keep `max_retries=3` for when they're dispatched standalone.
- `acks_late=True` means a task re-runs if the worker dies mid-execution — steps must be idempotent via
  the status guard.
- `SoftTimeLimitExceeded` must fail fast, not retry (documented in `_run_pipeline_step`).

## Cross-links
[backend-classes-models.md](backend-classes-models.md) (B4, the Status enum) · [backend-core.md](backend-core.md)
(B0, queue routing + limits) · L5-L10 (step bodies) · [backend-classes-teacher-views.md] (B5, dispatch) ·
memory: `pipeline-cancellation`, `chunked-transcription-500mb` · `.claude/agents/ai-engineer.md`.

## Verified-by
- `rg "^def |@shared_task|acks_late|max_retries" tasks.py` → the full task inventory + retry/acks config
  cited above.
- Read (2026-07-02): `tasks.py:265-334` (`_run_pipeline_step` + heartbeat), `:639-693`
  (`process_class_full_pipeline` status-guarded steps + cancel checkpoints).
- Queue routing cross-checked against `core/settings.py:502-525` (B0).
- NOT read whole: `tasks.py` (1101 lines — step bodies belong to L5-L10). NOT verified live: actual
  Celery execution / cancellation timing (Avalai VPN-blocked; guarded by `pipeline-cancellation` tests).
