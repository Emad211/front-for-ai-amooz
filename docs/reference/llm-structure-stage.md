# Reference — Stage: structure extraction (step 2)

- **Status:** Verified · **Created:** 2026-07-02 · **Last-verified:** 2026-07-02 (commit `d8c7a95`)
- **Owner (doc):** technical-writer · **Spec source:** `docs/reference/ROADMAP.md` step L6
- **Layer:** llm (pipeline stage — step 2)

## Purpose
Pipeline step 2: turn the raw transcript/markdown into structured course content — a `root_object`
(title, audience level, learning goals) plus an `outline` of sections, each with units carrying
`source_markdown` + `content_markdown` + `image_ideas`. Then persist that structure into DB rows.

## Scope & paths
| File | Role |
|---|---|
| `apps/classes/services/structure.py` | `structure_transcript_markdown` — the LLM extraction |
| `apps/classes/services/sync_structure.py` | `sync_structure_from_session` — JSON → `ClassSection`/`ClassUnit` rows |
| `apps/classes/services/schemas.py:20-63` | `StructureOutput`/`StructureRootObject`/`StructureSection`/`StructureUnit` |

**Out of scope:** prompt body → L3 (`structure_content.default`); the `validate_keep_dict` mechanics →
L2; the models it writes → B4.

## Public surface
- **`structure_transcript_markdown(...)`** (`structure.py:86`) — transcript → structure dict. Uses
  `PROMPTS["structure_content"]["default"]` (`:98`), rendered via `_render_prompt` (`str.replace`).
- **`sync_structure_from_session(*, session)`** (`sync_structure.py:29`) — reads the stored structure
  and upserts `ClassSection` + `ClassUnit` rows (`update_or_create` by `external_id`), deleting orphans.
- Output JSON keys (L3 contract): `root_object`, `outline`, `what_you_will_learn`, and per-unit
  `merrill_type`, `source_markdown`, `content_markdown`, `image_ideas`.

## Key flows
1. **Extraction** (`structure_transcript_markdown:86`): build the prompt from the transcript → call the
   LLM → **`validate_keep_dict(text, StructureOutput)`** (`:126`) — validates the shape but returns the
   model's EXACT dict (not a Pydantic re-serialization) → on failure, one repair round-trip with an
   explicit schema hint (top-level keys `root_object`, `outline`) then re-validate (`:147`).
2. **Asset handling:** `_reinject_unit_assets` (`:169`) + `_restore_latex_escapes` (`:199`) preserve
   images/LaTeX through structuring (the content_markdown can contain code fences + math).
3. **Persist** (`sync_structure_from_session:29`): iterate `outline` → each section `update_or_create`
   by `external_id` (`_derive_section_id`), each unit by `external_id` (`_derive_unit_id`); prune rows
   not in the new structure. This is why `outline`-is-a-list-of-sections-with-`units` is the load-bearing
   invariant.

## Data & invariants
- **Uses `validate_keep_dict`, NOT `generate_structured`** — the structure dict is stored verbatim and
  consumed by asset-reinjection + `sync_structure`, so it must survive un-normalized (L2). Don't switch
  to `generate_structured` here.
- The schema's strongest guarantee: `outline` is a list of sections each with a `units` list
  (`schemas.py:54-56`); everything else is `extra="allow"` (soft). Asset reinjection + sync iterate
  exactly this.
- Output keys are the L3 contract — byte-for-byte with the widgets/parsers.
- `sync_structure` derives stable `external_id`s so re-running structuring updates rows rather than
  duplicating them.

## Gotchas
- Historic bug: a non-greedy fence regex truncated structure JSON whose `content_markdown` held
  ` ```code``` ` fences — fixed by the greedy `_FENCE_RE` in `extract_json_object` (L2, memory
  `pdf-structure-json-bug-fixed`). Don't reintroduce non-greedy.
- `StructureUnit`/`Section`/`RootObject` all set `extra="allow"` — new prompt fields don't break
  validation, but their output keys must still be added to the L3 contract if downstream reads them.

## Cross-links
[llm-structured-output.md](llm-structured-output.md) (L2, `validate_keep_dict` + schemas) ·
[llm-prompts-contract.md](llm-prompts-contract.md) (L3, `structure_content` output keys) ·
[backend-classes-models.md](backend-classes-models.md) (B4, `ClassSection`/`ClassUnit`) · L7 (next stage
consumes this structure) · memory: `pdf-structure-json-bug-fixed` · `.claude/agents/ai-engineer.md`.

## Verified-by
- `rg "^def |validate_keep_dict|PROMPTS\[|StructureOutput" structure.py` → confirms `validate_keep_dict`
  usage (`:126`,`:147`), prompt key `structure_content.default` (`:98`), the repair round-trip.
- `rg "^def |ClassSection|ClassUnit|external_id|update_or_create" sync_structure.py` → the
  section/unit upsert-by-external_id + orphan prune (`:72-105`).
- Read (2026-07-02): `schemas.py:20-63` (the StructureOutput shape + the `outline`/`units` invariant
  docstring).
- NOT read whole: `structure.py`/`sync_structure.py` bodies (grep covers the contract). NOT verified
  live: LLM structuring (Avalai VPN-blocked).
