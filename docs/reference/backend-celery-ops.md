# Reference — Celery wiring + SMS + media (cross-cutting ops)

- **Status:** Verified · **Created:** 2026-07-02 · **Last-verified:** 2026-07-08
- **Owner (doc):** technical-writer · **Spec source:** `docs/reference/ROADMAP.md` step B8
- **Layer:** backend-app (operational/cross-cutting)

## Purpose
The operational plumbing around the pipeline: the Celery task→queue map + beat schedule, the SMS
delivery (Mediana) that publish/invite dispatch, and the ffmpeg media compressor. Complements L4 (which
owns the pipeline task *bodies*) — this doc owns the *inventory + config + supporting services*.

## Scope & paths
| File | Role |
|---|---|
| `backend/core/celery.py` | Celery app + task lifecycle logging (B0) |
| `backend/core/settings.py:486-529` | `CELERY_TASK_ROUTES`, defaults, visibility timeout, beat (B0) |
| `apps/classes/tasks.py` | task inventory (SMS + cleanup here; pipeline bodies → L4) |
| `apps/classes/services/mediana_sms.py` | Mediana SMS client |
| `apps/classes/services/media_compressor.py` | ffmpeg compress/split |
| `apps/classes/services/pdf_metrics.py` | PDF page metrics |

**Out of scope:** pipeline task bodies + cancellation → L4; queue-config rationale → B0; SMS *content* is
Persian copy (product).

## Public surface
**SMS tasks (queue `default`, `max_retries=5`):** `send_publish_sms_task`,
`send_new_invites_sms_task`, `send_teacher_message_sms_task` (`tasks.py`). Beat task
`cleanup_stale_sessions` (`max_retries=0`, every 30 min) runs from a separate `celery beat`
process in production compose and Kubernetes.

**Exercise async tasks (queue `pipeline`, `acks_late=True`):** `extract_exercise_content` and
`grade_exercise_submission` retry only provider/network-transient LLM failures. Permanent errors
(bad request shape, missing model/key, 401/403/413/422, parser/application errors) fail fast and mark
the exercise/submission failed. Retryable errors are restricted to timeouts/transport errors, 408,
409, 429, and 5xx. The task id is persisted before work starts; a redelivered/retried task with the
same id may resume from `EXTRACTING`/`GRADING` instead of skipping itself.

**Mediana SMS:** `send_peer_to_peer_sms(*, api_key, requests, message_type='Informational')`
(`mediana_sms.py:64`) → `_post_json` with `X-API-KEY` header. Higher-level:
`send_publish_sms_for_session`, `send_teacher_message_sms`, `send_invite_sms_for_ids`. All no-op (logged)
if `MEDIANA_API_KEY` unset.

**Media:** `prepare_media_parts_for_api` (`media_compressor.py:106`), `_try_compress_video`,
`_split_and_compress_video_into_parts`, `_run_ffmpeg` (`:44`, 1800s timeout). ffmpeg path via
`FFMPEG_PATH` (default `ffmpeg`).

## Key flows
1. **Queue routing** (`settings.py`, B0): pipeline/transcription/exam-prep/exercise/pregeneration tasks
   → `pipeline`; SMS tasks + `cleanup_stale_sessions` → `default`. `CELERY_TASK_DEFAULT_QUEUE='default'`
   is load-bearing
   (unrouted tasks would go to the unconsumed `celery` queue).
2. **Publish → SMS:** `ClassCreationSessionPublish` (B5) dispatches `send_publish_sms_task` →
   `send_publish_sms_for_session` → `_send_sms_for_invites` chunks recipients →
   `send_peer_to_peer_sms`. Best-effort; missing key = skip + log.
3. **Stale-session reaper** (`cleanup_stale_sessions:1076`): every 30 min, sessions in an in-progress
   `*ING` status with `updated_at` older than 2 h → marked FAILED. The step-1 heartbeat (L4) is what
   keeps a genuinely-live long run from being reaped.
4. **Media compression:** ffmpeg fast-split / compress before/within transcription (L5) to fit gateway limits.

## Data & invariants
- Queue discipline: slow LLM/media work ONLY on `pipeline` (hard 2h/soft 100min, prefetch=1, B0); quick
  tasks (SMS, cleanup) on `default`. Don't cross them.
- Redis broker visibility timeout must exceed the global hard task limit. Default:
  `CELERY_VISIBILITY_TIMEOUT=21600` seconds, mirrored to broker and result backend transport options.
- Redis broker/cache in production compose uses `noeviction`. Evicting broker keys can drop or duplicate
  work under memory pressure; if cache pressure grows, split broker/result/cache into separate Redis
  instances instead of using an LRU policy on the broker.
- Production workers must consume `-Q default,pipeline`; beat is a separate singleton process. The
  repository locks this with `TestCelerySettings.test_deploy_manifests_consume_routed_queues_and_run_beat`.
- SMS is best-effort and idempotent-ish (`max_retries=5`); no key ⇒ no send, never an error.
- `cleanup_stale_sessions` 2 h cutoff must stay longer than the longest legit step gap — the heartbeat is
  the real protection, not the cutoff.
- Mediana uses `X-API-KEY` header + chunked recipient lists; `MEDIANA_API_KEY` env only (never committed).
- ffmpeg/ffprobe path env-tunable (`FFMPEG_PATH`); `_run_ffmpeg` has a generous timeout for large media.

## Gotchas
- The cleanup reaper and the heartbeat are a pair — changing one without the other risks either reaping
  live runs (too-short cutoff / broken heartbeat) or leaving zombies (too-long cutoff).
- SMS content is Persian and product-owned — this doc covers delivery, not copy.
- `_get_duration` derives ffprobe from the ffmpeg path by string-replace (`media_compressor.py:430`) —
  a custom `FFMPEG_PATH` must have a sibling ffprobe.

## Cross-links
[llm-pipeline-orchestration.md](llm-pipeline-orchestration.md) (L4, task bodies + heartbeat/cancel) ·
[backend-core.md](backend-core.md) (B0, queue routing + limits + celery.py) ·
[llm-transcription.md](llm-transcription.md) (L5, uses the compressor) · [backend-classes-teacher-views.md](backend-classes-teacher-views.md)
(B5, publish dispatch) · `MEDIANA DOCUMENT.json` (SMS API) · `.claude/agents/devops-engineer.md`,
`performance-engineer.md`.

## Verified-by
- `rg "^def |send_peer_to_peer|MEDIANA_API_KEY" mediana_sms.py` → `send_peer_to_peer_sms:64` + `X-API-KEY`
  + the no-key skip in the higher-level senders.
- `rg "^def |ffmpeg|_run" media_compressor.py` → `_run_ffmpeg:44` (1800s), `prepare_media_parts_for_api:106`,
  split/compress helpers, `FFMPEG_PATH`.
- Read (2026-07-02): `tasks.py:1076-1101` (`cleanup_stale_sessions` — 2 h cutoff, `*ING`→FAILED).
- Queue map cross-checked against `settings.py` + the task inventory in L4.
- 2026-07-08 sqlite fast lane: `test_llm_client_timeout.py`, `test_exercise_extraction_task.py`,
  `test_exercise_grading.py`, `test_settings.py` → 63 passed.
- NOT verified live: Mediana SMS delivery, ffmpeg on the real media (VPN/hardware-dependent).
