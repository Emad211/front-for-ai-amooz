# Reference — LLM provider & client foundation

- **Status:** Verified · **Created:** 2026-07-02 · **Last-verified:** 2026-07-02 (commit `0ec8ed9`)
- **Owner (doc):** technical-writer · **Spec source:** `docs/reference/ROADMAP.md` step L1
- **Layer:** llm (cross-cutting foundation)

## Purpose
The single low-level door to the LLM: provider selection, the OpenAI-compatible client (Avalai / GAPGPT
gateway), base-URL normalization, model resolution from env, and the `generate_text` / `generate_json`
entry points every higher LLM feature calls. This is the god-node `chatbot/services/llm_client.py`.

## Scope & paths
| File | Role |
|---|---|
| `apps/chatbot/services/llm_client.py` (383) | The client: `generate_text`, `generate_json`, `part_from_bytes`, retry, tracking |
| `apps/commons/llm_provider.py` (25) | `preferred_provider()` — reads `LLM_PROVIDER` / legacy `MODE` |

**Out of scope:** structured-output validation → [llm-structured-output.md](llm-structured-output.md) (L2);
prompt bodies → [llm-prompts-contract.md](llm-prompts-contract.md) (L3); cost logging internals → L10;
gateway API details → root `AvalAI-Developer-Documentation.md`.

## Public surface
- **`generate_text(*, messages=None, contents=None, model=None, feature=None, timeout=None,
  response_format=None, **kwargs) -> LlmResult`** (`llm_client.py:232`) — unified caller; pass EITHER
  `messages` (full chat array) OR `contents` (wrapped as one user message). Returns
  `LlmResult(text, provider, model)` (frozen dataclass, `:102`).
- **`generate_json(*, feature, contents) -> dict`** (`llm_client.py:304`) — free-text→dict using
  provider JSON mode (`response_format={"type":"json_object"}`); transparently retries WITHOUT json mode
  if the provider rejects `response_format`; empty/unparseable → one LLM repair round-trip
  (`_repair_json_with_llm`, prompt key `json_repair`), else silent `{}`. ⚠️ New pipeline JSON should use
  L2's `generate_structured` (raises) instead of this silent-`{}` path.
- **`part_from_bytes(*, data, mime_type)`** (`llm_client.py:360`) — builds a STANDARD OpenAI multimodal
  part: `audio/*` → `{type:'input_audio', input_audio:{data,format}}`, else →
  `{type:'image_url', image_url:{url:'data:…;base64,…'}}`. The legacy `input_file` shape is silently
  ignored by the gateway — never build parts by hand.
- **`preferred_provider() -> 'auto'|'gemini'|'avalai'`** (`llm_provider.py:10`).
- **`set_llm_feature(feature)`** — thread-local feature tag for cost attribution.

**Env → model/provider matrix (all env-driven; nothing hardcoded):**
| Var | Effect | Default in code |
|---|---|---|
| `LLM_PROVIDER` / legacy `MODE` | provider selector (prod sets `MODE=avalai`) | `auto` |
| `AVALAI_API_KEY` | gateway key (required; raises if missing, `:85`) | — |
| `AVALAI_BASE_URL` | gateway base; `/v1` auto-appended | `https://api.gapgpt.app/v1` |
| `CHAT_MODEL` | default chat model (`_default_model`, `:94`) | `gemini-2.5-flash` |
| `LLM_TIMEOUT_SECONDS` | per-request timeout | `600` |
| `LLM_JSON_OBJECT_MODE` | enable json_object mode in `generate_json` | `1` (on) |

Other stages read their own model vars (`TRANSCRIPTION_MODEL`, `IMAGE_MODEL`, `EMBEDDING_MODEL_NAME`) —
documented at their stage docs (L5/L10).

## Key flows
1. **A text call:** caller → `generate_text` → resolve model (`model` arg or `_default_model()`) + feature
   → `_call_gapgpt_with_messages` (`:175`, `@retry` 3× exp-backoff, but NOT on a `response_format`
   rejection) → `_get_gapgpt_client()` builds `OpenAI(api_key, base_url=_normalize_base_url(...))` →
   `client.chat.completions.create(...)` → on success `track_llm_usage`, on error `track_llm_error`
   (both feed `LLMUsageLog`, L10) → `LlmResult`.
2. **Base-URL normalization** (`_normalize_base_url`, `:66`): appends `/v1` if the URL lacks a `/v{n}`
   suffix — a bare `https://api.avalai.ir` would otherwise POST to `/chat/completions` and 404. Idempotent.
3. **JSON mode with fallback** (`generate_json`): try json_object mode → on `response_format`-unsupported
   error retry plain → parse via `extract_json_object` → on failure, one LLM repair → else `{}`.
4. **Multimodal:** callers build parts ONLY via `part_from_bytes`; `_normalize_content`/`_normalize_messages`
   (`:112-140`) wrap raw strings in `{type:'text'}` so mixed text+media lists are valid OpenAI shapes.

## Data & invariants
- **`/v1` on the base URL is mandatory** — the auto-append is the guard; don't remove it.
- **Standard multimodal shapes only** (`image_url` / `input_audio`); the legacy `input_file`/
  `attachments` shape is silently dropped by Avalai (historical empty/hallucinated-vision bug).
- **No hardcoded model/key/URL** — every one comes from env; a hardcoded model name is a review finding.
- Retry never retries a permanent `response_format` rejection (`_should_retry_llm_call`, `:155`).
- Every call is tracked (success or error) for cost attribution — don't add a bypass path.

## Gotchas
- Despite `preferred_provider()` naming `gemini`, THIS client is the OpenAI-compatible (Avalai/GAPGPT)
  path only; the `google-genai` Gemini path lives in the calling stages, selected by provider/env.
- The in-code default base URL is `api.gapgpt.app`, but **prod runs Avalai** via `MODE=avalai` +
  `AVALAI_BASE_URL` — don't assume the code default is what production uses.
- Avalai is **not testable locally** (VPN blocks it); unit tests mock the client. See
  `avalai-multimodal-format` memory history.
- `generate_json`'s silent `{}` is legacy — prefer L2 `generate_structured` for anything new.

## Cross-links
[llm-structured-output.md](llm-structured-output.md) (L2) · [llm-prompts-contract.md](llm-prompts-contract.md)
(L3, the prompt bodies) · L10 (`token_tracker`/`LLMUsageLog`) · root `AvalAI-Developer-Documentation.md` ·
`.claude/agents/ai-engineer.md` · memory: `avalai-multimodal-format`.

## Verified-by
- Full read (2026-07-02): `llm_client.py` (383), `llm_provider.py` (25).
- Confirmed in code: `_normalize_base_url` `/v1` append (`:66-78`); default base
  `api.gapgpt.app/v1` (`:83`); `_default_model` = `CHAT_MODEL` or `gemini-2.5-flash` (`:94`);
  `part_from_bytes` standard shapes (`:360-382`); retry excludes `response_format` errors (`:155-163`);
  `generate_json` json-mode + repair fallback (`:304-334`).
- NOT verified live: actual gateway behavior (Avalai VPN-blocked locally); the Gemini `google-genai`
  path (lives in calling stages, out of this file's scope — flagged for L5/L10).
