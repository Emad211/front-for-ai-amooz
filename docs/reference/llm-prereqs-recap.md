# Reference — Stages: prerequisites, prereq-teaching, recap (steps 3-5)

- **Status:** Verified · **Created:** 2026-07-02 · **Last-verified:** 2026-07-14
- **Owner (doc):** technical-writer · **Spec source:** `docs/reference/ROADMAP.md` step L7
- **Layer:** llm (pipeline stages — steps 3, 4, 5)

## Purpose
The three mid-pipeline enrichment stages that turn structured content into a complete learning package:
step 3 extracts prerequisites, step 4 generates teaching material for them, step 5 builds the recap /
notes / formula sheet. Grouped because they share shape (structure in → enrichment JSON out) and status
progression.

## Scope & paths
| File | Role |
|---|---|
| `apps/classes/services/prerequisites.py` | `extract_prerequisites` (step 3) + `generate_prerequisite_teaching` (step 4) |
| `apps/classes/services/recap.py` | `generate_recap_from_structure` (step 5) + `recap_json_to_markdown` |

**Out of scope:** prompt bodies → L3; the models these write → B4; orchestration/statuses → L4.

## Public surface
- **`extract_prerequisites(*, transcript_markdown) -> (dict, str, str)`** (`prerequisites.py:104`) —
  prompt `prerequisites_prompt.default`; output key `prerequisites`. Model via env
  `PREREQUISITES_MODEL` → `STRUCTURE_MODEL` → `REWRITE_MODEL` (`_select_model:112`).
- **`generate_prerequisite_teaching(*, prerequisite_name, source_markdown)`** (`prerequisites.py`) —
  prompt `prerequisite_teaching.default`. A bounded 600-character beginning/middle/end sample of the original source
  is passed as `SOURCE_LANGUAGE_CONTEXT`; it is the authoritative language signal, so an English
  technical prerequisite name inside a Persian course does not switch the teaching output to English.
- **`generate_recap_from_structure(*, structure_json) -> (dict, str, str)`** (`recap.py:76`) — prompt
  `recap_and_notes.default`; output tree `recap`/`overview_markdown`/`key_notes_markdown`/`by_unit`
  (with `unit_recap_markdown`, `unit_key_points_markdown`, `common_mistakes_markdown`,
  `quick_self_check_markdown`, `formula_sheet_markdown` — the full L3 OUTPUT_KEYS).
- **`recap_json_to_markdown(recap_obj)`** (`recap.py:111`) — renders the recap dict to display markdown.

## Key flows
1. **Step 3 (prereqs):** transcript → `PROMPTS["prerequisites_prompt"]["default"]` → `_call_llm` →
   `_safe_json_from_llm` → `{prerequisites: [...]}`; status PREREQ_EXTRACTING → PREREQ_EXTRACTED.
2. **Step 4 (teaching):** the extracted prerequisites + bounded source-language context →
   `prerequisite_teaching.default` → teaching material per prerequisite in the source language; status
   PREREQ_TEACHING → PREREQ_TAUGHT. (The task takes an optional
   `prerequisite_name` to teach a single one — L4 `process_class_step4_prereq_teaching`.)
3. **Step 5 (recap):** the structure JSON → `recap_and_notes.default` → the recap tree; status
   RECAPPING → RECAPPED (pipeline terminal). `recap_json_to_markdown` turns it into rendered markdown.

## Data & invariants
- All three shared blocks apply where required: `SAFETY_PREAMBLE` + `AUDIENCE_ADAPTIVE` +
  `MATH_FORMAT_INSTRUCTIONS` (L3) — recap/prereqs consume untrusted content, so the safety block is
  contract-tested present.
- Output-JSON keys are the L3 contract (byte-for-byte with parsers/UI).
- **These three stages still use the older `generate_json`/manual-parse path**, NOT `generate_structured`
  — their migration onto `generate_structured` is the documented, still-pending follow-up (deferred:
  live pipeline VPN-untestable). See L2.
- Model names strictly env-driven (`_select_model` fallback chains) — never hardcoded.

## Gotchas
- Step 4 can teach a single named prerequisite (`prerequisite_name` arg) or all — don't assume it's
  always the full set.
- The 600-character language sample is intentionally repeated for each prerequisite generation. At
  the standard 10 prerequisites this adds at most 6,000 source characters across the step, trading a
  small bounded token increase for reliable language selection.
- `_safe_json_from_llm` here is the local safe-parse; the project convention (L2 `generate_structured`)
  is stricter — when this stage is migrated, the silent-fallback behavior changes to raise.
- Recap is the pipeline's terminal stage (RECAPPED) — nothing runs after it in the class pipeline.

## Cross-links
[llm-prompts-contract.md](llm-prompts-contract.md) (L3, the three prompt keys + output trees) ·
[llm-structured-output.md](llm-structured-output.md) (L2, the pending migration) ·
[llm-structure-stage.md](llm-structure-stage.md) (L6, the structure these consume) ·
[llm-pipeline-orchestration.md](llm-pipeline-orchestration.md) (L4, the status transitions) ·
[backend-classes-models.md](backend-classes-models.md) (B4) · `.claude/agents/ai-engineer.md`.

## Verified-by
- `rg "^def |PROMPTS\[|generate_json|_select_model" prerequisites.py recap.py` → the function inventory,
  the three prompt keys (`prerequisites_prompt`/`prerequisite_teaching`/`recap_and_notes`), env model
  resolution, and the `generate_json`/`_safe_json_from_llm` path (confirming NOT yet on
  `generate_structured`).
- Read (2026-07-02): `prerequisites.py:104-133` (`extract_prerequisites` — env model chain + prompt key).
- Output trees cross-checked against L3 `OUTPUT_KEYS` (`test_prompts_contract.py:135-146`).
- NOT read whole: both service bodies. NOT verified live: LLM enrichment (Avalai VPN-blocked).
