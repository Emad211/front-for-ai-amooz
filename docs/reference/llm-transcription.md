# Reference — Stage: transcription (chunked + multimodal)

- **Status:** Verified · **Created:** 2026-07-02 · **Last-verified:** 2026-07-02 (commit `6e058cb`)
- **Owner (doc):** technical-writer · **Spec source:** `docs/reference/ROADMAP.md` step L5
- **Layer:** llm (pipeline stage — step 1)

## Purpose
Pipeline step 1 for media: turn lecture audio/video into a transcript. The design that lets 500 MB /
multi-hour lectures survive the gateway — split into time-window chunks, one small LLM request per chunk
carrying that window's audio + frames + the prior transcript tail. Durable contract restated here; the
fix history lives in memory `chunked-transcription-500mb` + `avalai-multimodal-format`.

## Scope & paths
| File | Role |
|---|---|
| `apps/classes/services/transcription.py` | orchestrates single-shot + chunked transcription |
| `apps/classes/services/transcription_media.py` | ffmpeg audio-extract + frame-sample (the multimodal parts) |
| `apps/classes/services/media_compressor.py` | ffmpeg compression |
| `apps/commons/text_sanitize.py` | `sanitize_llm_markdown` (applied to every chunk) |

**Out of scope:** the prompt bodies → L3 (`transcribe_media.default`/`.chunked`); orchestration/heartbeat
wiring → L4; PDF step-1 alternative → L10.

## Public surface
- **`transcribe_media_file(*, path, progress_cb=None, …)`** (`transcription.py:244`) — the pipeline entry;
  ffmpeg reads from a path (never the whole video in RAM — the OOM fix). Long media
  (> ~1.5× `TRANSCRIPTION_CHUNK_SECONDS`) routes to `_transcribe_media_file_chunked` (`:368`).
- **`transcribe_media_bytes(*, data, mime_type)`** (`transcription.py:201`) — **stays single-shot** (the
  chat audio path); don't route it through chunking.
- `extract_audio_mp3_chunks_from_path` (`transcription_media.py:99`) — ONE ffmpeg `-f segment` pass →
  sequential 16 kHz mono-mp3 segments. `extract_frames_jpeg_from_path` (`:175`) — sampled JPEG frames.
- `TranscriptionAborted` (`transcription.py:49`) — raised between chunks when `progress_cb` returns False.

**Env knobs:** `TRANSCRIPTION_CHUNK_SECONDS` (600, clamped 120–1800) · `TRANSCRIPTION_FRAMES_PER_CHUNK`
(8, max 16) · `TRANSCRIPTION_MAX_DURATION_SECONDS` (4 h) · `FRAME_MAX_WIDTH` (960) · `FRAME_HARD_CAP`
(16) · `FRAME_MAX_FRAMES_FOR_MODEL` (40) · `MAX_TOTAL_FRAME_BYTES_MB` (3, **per-request** budget) ·
`FRAME_EXTRACTION_FPS` (0.25, fallback pass) · `TRANSCRIPTION_MODEL` (L1).

## Key flows
1. **Multimodal shapes** (the gateway has NO video type — `transcription_media.py:4-6`): video →
   **audio track → mono mp3 → `input_audio`** + **sampled frames → JPEG → `image_url`**. The standard
   OpenAI shapes; the legacy `attachments/input_file` shape is silently ignored (the empty/hallucinated
   transcript bug).
2. **Chunked flow** (`_transcribe_media_file_chunked:368`): one ffmpeg `-f segment` pass splits audio into
   `TRANSCRIPTION_CHUNK_SECONDS` mono-mp3 segments → for each: build ONE small request with that window's
   frames + the tail of the transcript so far (prompt `transcribe_media.chunked`) → `_notify_progress`
   heartbeat after every chunk (bumps `updated_at`; returns False → `TranscriptionAborted`, never
   retried) → `sanitize_llm_markdown` each chunk (HTML garbage self-amplifies chunk-to-chunk).
3. **Retry guard** (`_run_transcription:174`): retries transient errors but NOT `SoftTimeLimitExceeded`
   or `TranscriptionAborted` (`:187`).

## Data & invariants
- **Never collapse chunking back into one request** — a single request hit body limits + silent
  output-token truncation (and `SSL: UNEXPECTED_EOF` on flaky links).
- Standard multimodal shapes only (`input_audio` / `image_url`); build via `part_from_bytes` (L1).
- `transcribe_media_bytes` (chat audio) stays single-shot.
- Every chunk passes `sanitize_llm_markdown`.
- ffmpeg reads from a path (path-based ingest) — never load the whole video into memory.
- `progress_cb` heartbeat + `TranscriptionAborted`-never-retried is the mid-step-cancel + anti-reap
  contract (L4).

## Gotchas
- `MAX_TOTAL_FRAME_BYTES_MB` is a PER-REQUEST budget now (each chunk carries its own frames), not a
  whole-media budget.
- Duration over `TRANSCRIPTION_MAX_DURATION_SECONDS` (4 h) is rejected.
- Exam-prep step 1 shares this infra (windowing) — see L9.

## Cross-links
[llm-prompts-contract.md](llm-prompts-contract.md) (L3, `transcribe_media` keys) ·
[llm-pipeline-orchestration.md](llm-pipeline-orchestration.md) (L4, heartbeat/cancel) ·
[llm-provider-client.md](llm-provider-client.md) (L1, `part_from_bytes` + `TRANSCRIPTION_MODEL`) ·
[llm-exam-prep.md] (L9, shared windowing) · root `AvalAI-Developer-Documentation.md` · memory:
`chunked-transcription-500mb`, `avalai-multimodal-format` · `.claude/agents/ai-engineer.md`.

## Verified-by
- `rg "^def |TranscriptionAborted|progress_cb|TRANSCRIPTION_*|transcribe_media_bytes" transcription.py`
  → the function inventory, chunk/duration/frames env clamps (`:74-98`), single-shot vs chunked split.
- `rg "input_audio|image_url|-f segment|FRAME_" transcription_media.py` → the standard multimodal shapes
  + the module docstring (`:4-6`) confirming video→audio+frames, the `-f segment` pass (`:99`), frame
  env budgets.
- NOT read whole: both files' bodies (grep gives the contract; the fix narrative is in the two memory
  files). NOT verified live: actual transcription (Avalai VPN-blocked; guarded by
  `test_chunked_transcription*`).
