# Reference — Stage: PDF ingest/export + LLM cost attribution

- **Status:** Verified · **Created:** 2026-07-02 · **Last-verified:** 2026-07-02 (commit `c5504c2`)
- **Owner (doc):** technical-writer · **Spec source:** `docs/reference/ROADMAP.md` step L10 [a/b]
- **Layer:** llm (PDF step-1 alternative + the cost-tracking substrate)

## Purpose
Two related things: (a) the LLM-only PDF→Markdown ingest (the non-media step-1 path) + WeasyPrint
export; (b) **every LLM call's cost is logged and attributed** per session/teacher/class/feature — the
substrate the org AI-cost dashboards (B9) read.

## Scope & paths
| File | Role |
|---|---|
| `apps/classes/services/pdf_extraction.py` | `extract_pdf_to_markdown` (vision OCR per page) |
| `apps/classes/services/pdf_export.py` · `pdf_metrics.py` · `markdown_assets.py` | WeasyPrint export + metrics + assets |
| `apps/commons/token_tracker.py` | `llm_tracking_context`, `track_llm_usage/error`, session/user thread-locals |
| `apps/commons/models.py` | `LLMUsageLog`, `ModelPrice`, `estimate_cost`, `get_pricing` |
| `apps/commons/exchange_rate.py` | USD→Toman rate |

**Out of scope:** prompt body → L3 (`pdf_extraction.default`); the admin cost VIEWS → B9; the
middleware that seeds the user thread-local → B0.

## Public surface
**PDF (a):**
- `extract_pdf_to_markdown(...)` (`pdf_extraction.py:190`) — per-page vision OCR (prompt
  `pdf_extraction.default`, `:165`); deterministic figure extraction (no tokens); blank-page skip;
  `tables_to_markdown` (`:108`). Vision model via `_select_vision_model` (`:62`); knobs `PDF_*` (B0).
- PDF export via WeasyPrint (`pdf_export.py`); page metrics (`pdf_metrics.py`).

**Cost (b):**
- `llm_tracking_context(*, user=None, session_id=None)` (`token_tracker.py:55`) — context manager that
  binds the current user + session so nested LLM calls attribute correctly.
- `get_current_session_id()` / `set_current_session_id()` (`:44-49`); `set_current_user` (`:34`).
- `track_llm_usage(...)` (`:135`) / `track_llm_error(...)` (`:209`) — write an `LLMUsageLog` row
  (resolves `session_id or get_current_session_id()`, `:161`).
- `estimate_cost(...)` (`models.py:325`) / `get_pricing(model, provider)` (`:306`).

## Key flows
1. **PDF ingest:** each non-blank page → PNG → vision LLM (`_vision_extract_page:158`) → markdown;
   embedded figures extracted deterministically + reinjected; tables rendered. This is step-1 when the
   source is a PDF (the media path is L5).
2. **Cost attribution:** every call in `llm_client` (L1) calls `track_llm_usage` → `LLMUsageLog` with
   `feature` (the `Feature` TextChoices, `models.py:13`), `provider`, token counts, `duration_ms`, and
   **`session_id`** (indexed, `:104`; composite index `[session_id, created_at]`, `:119`). The
   `session_id` is what lets B9/data-analyst break cost down per teacher/class/study-group/feature — no
   migration needed for a new breakdown.
3. **Monetary estimate:** `estimate_cost` uses `ModelPrice` (`models.py:173`) + `exchange_rate` (USD→Toman).

## Data & invariants
- **`session_id` is the attribution key** (thread-local via `llm_tracking_context` +
  `get_current_session_id`); every LLM call must flow through the tracking so no call is unattributed.
- `LLMUsageLog` is append-only usage; new cost breakdowns are read-queries over `session_id`, not schema
  changes.
- PDF ingest is LLM-only (vision per page) — favors accuracy; blank-page skip + figure-extraction keep
  tokens down; all `PDF_*` knobs env-tunable (B0).
- Cost discipline: estimate tokens, prefer fewer/smaller calls, batch sizes env-tunable, report cost
  deltas in handoffs; benchmark tests opt-in only.

## Gotchas
- The user thread-local is seeded by `LLMTrackingMiddleware` (B0) for request-path calls; Celery tasks
  set it explicitly (`_attribute_llm_usage_to_teacher`, L4) — a task that forgets leaves usage
  unattributed to a teacher.
- PDF vision model has its own `_select_vision_model` env chain — distinct from the chat/structure model.
- WeasyPrint (export) is separate from pdfplumber/pypdf (ingest) — don't conflate the two PDF stacks.

## Cross-links
[llm-provider-client.md](llm-provider-client.md) (L1, the calls being tracked) ·
[llm-prompts-contract.md](llm-prompts-contract.md) (L3, `pdf_extraction`) · [backend-core.md](backend-core.md)
(B0, `PDF_*` knobs + `LLMTrackingMiddleware`) · [backend-commons-admin.md] (B9, the cost VIEWS) ·
[llm-pipeline-orchestration.md](llm-pipeline-orchestration.md) (L4, `_attribute_llm_usage_to_teacher`) ·
memory: `pdf-llm-extraction` (benchmarks) · `.claude/agents/data-analyst.md`, `ai-engineer.md`.

## Verified-by
- `rg "^def |PROMPTS\[|_select_vision_model" pdf_extraction.py` → `extract_pdf_to_markdown:190`, prompt
  `pdf_extraction.default:165`, vision model selector, blank/table helpers.
- `rg "^def |llm_tracking_context|get_current_session_id|track_llm_usage" token_tracker.py` → the
  context manager + session/user thread-locals + `track_llm_usage:135` (session resolution at `:161`).
- `rg "LLMUsageLog|ModelPrice|session_id|estimate_cost|get_pricing" models.py` → `LLMUsageLog:10`
  (session_id indexed `:104`, composite index `:119`), `ModelPrice:173`, `estimate_cost:325`,
  `get_pricing:306`.
- NOT read whole: service/model bodies. Benchmarks in memory `pdf-llm-extraction`. NOT verified live:
  vision OCR quality (Avalai VPN-blocked; benchmark opt-in).
