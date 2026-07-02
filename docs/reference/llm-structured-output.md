# Reference — LLM structured output (`generate_structured` / `validate_keep_dict`)

- **Status:** Verified · **Created:** 2026-07-02 · **Last-verified:** 2026-07-02 (commit `ef6ffca`)
- **Owner (doc):** technical-writer · **Spec source:** `docs/reference/ROADMAP.md` step L2
- **Layer:** llm (cross-cutting)

## Purpose
Turns raw LLM text into a **validated** Python object — the convention that replaced the old "scrape
free text with `extract_json_object`, silently return `{}` on failure" pattern. JSON mode → robust parse
→ Pydantic validate → one repair round-trip → **raise** (never return corrupt/empty data downstream).

## Scope & paths
| File | Role |
|---|---|
| `apps/commons/structured_llm.py` (195) | `generate_structured`, `validate_keep_dict`, `parse_structured`, `validate_obj`, `StructuredOutputError` |
| `apps/commons/json_utils.py` (249) | `extract_json_object` — the canonical robust extractor (single source of truth) |
| `apps/classes/services/json_utils.py` (18) | Thin re-export of `extract_json_object` (back-compat only) |
| `apps/classes/services/schemas.py` | Pydantic schemas, e.g. `StructureOutput`/`StructureRootObject`/`StructureSection`/`StructureUnit` |

**Out of scope:** the client + JSON mode + `generate_json` legacy path → [llm-provider-client.md](llm-provider-client.md)
(L1); prompt bodies → [llm-prompts-contract.md](llm-prompts-contract.md) (L3).

## Public surface
- **`generate_structured(*, schema, messages|contents, model=None, feature=None, timeout=None,
  max_repair=1, json_object_mode=None) -> schema_instance`** (`structured_llm.py:128`) — THE entry point
  for new pipeline JSON. Returns a validated Pydantic instance; **raises `StructuredOutputError`** on
  total failure. Use for anything new.
- **`validate_keep_dict(text, schema) -> Any`** (`:114`) — validates against `schema` as a gate but
  returns the ORIGINAL parsed dict unmutated (no Pydantic normalization). Used by the structure step,
  whose exact dict is stored verbatim and consumed elsewhere.
- **`parse_structured(text, schema) -> T`** (`:102`) — extract + validate an already-obtained text.
- **`validate_obj(obj, schema) -> T`** (`:92`) — validate an already-parsed object.
- **`extract_json_object(text) -> Any`** (`json_utils.py:220`) — robust noisy-LLM→JSON extractor
  (details below). The re-export at `classes/services/json_utils.py` exists ONLY for legacy imports.

## Key flows
1. **`generate_structured` tier ladder** (`:160-194`): call `generate_text` with
   `response_format={"type":"json_object"}` (unless disabled) → if the provider rejects
   `response_format` (`_looks_like_response_format_unsupported`, `:54`) transparently retry plain →
   loop `max_repair+1` times: `extract_json_object` → `validate_obj`; on parse/validation failure send a
   `_repair_instruction` (`:80`, lists the schema's required top-level keys) and retry → exhausted ⇒
   **raise `StructuredOutputError`**.
2. **`extract_json_object` 3-tier extraction** (`json_utils.py:220-248`): (1) direct `json.loads` of
   fence-stripped, quote-normalized text → (2) **string-aware balanced-block** scan on normalized text
   (survives ` ``` ` fences *inside* JSON string values) → (3) safety net: balanced scan on RAW text.
   Along the way it repairs invalid LaTeX backslash escapes (`\cdot`→`\\cdot`), escapes raw control
   chars, drops over-escaped quotes, removes trailing commas, rejoins broken floats.

## Data & invariants
- **Never** reintroduce raw `extract_json_object` + silent `{}` for new code — use `generate_structured`
  (raises) or `validate_keep_dict`.
- `_FENCE_RE` is **greedy on purpose** (`json_utils.py:29`) — a non-greedy version truncated JSON whose
  string values contained ` ```python … ``` ` fences ("no JSON object/array found"; the
  `pdf-structure-json-bug-fixed` incident). Don't change it.
- `generate_structured` imports `generate_text` lazily inside the function (`:146`) to avoid an import
  cycle — keep it lazy.
- `validate_keep_dict` MUST return the raw dict (structure.py stores it verbatim) — don't "upgrade" it
  to return the Pydantic model.
- Schemas live in `apps/classes/services/schemas.py`; `StructureOutput` is the L6 structure-stage shape.

## Gotchas
- gemini-via-avalai doesn't reliably honour *strict* `json_schema`, so the design uses looser
  `json_object` mode + self-validation — don't switch to strict schema mode expecting it to hold.
- The migration of recap/prereqs/quizzes/exam_prep_structure onto `generate_structured` is **still
  pending** (deferred — the live pipeline is VPN-untestable); those stages currently use the older
  `generate_json`/manual path (noted in L7/L8/L9).

## Cross-links
[llm-provider-client.md](llm-provider-client.md) (L1, the underlying `generate_text`) ·
[llm-prompts-contract.md](llm-prompts-contract.md) (L3) · [llm-structure-stage.md] (L6, `validate_keep_dict`
consumer) · guard tests: `apps/commons/test_structured_llm.py`, `test_json_utils.py` ·
`.claude/agents/ai-engineer.md`.

## Verified-by
- Full read (2026-07-02): `structured_llm.py` (195), `json_utils.py` (249).
- `rg "^class |^def " classes/services/json_utils.py` → confirms it's a pure re-export (`__all__ =
  ["extract_json_object"]`).
- `rg "^class " classes/services/schemas.py` → `StructureUnit/Section/RootObject/Output` present.
- Confirmed in code: tier ladder + repair loop (`structured_llm.py:160-194`); raise-not-return
  contract (`StructuredOutputError`, `:46`); greedy `_FENCE_RE` (`json_utils.py:29`); 3-tier extractor
  (`:220-248`).
- NOT verified live: repair round-trip against a real provider (mocked in tests; Avalai VPN-blocked).
