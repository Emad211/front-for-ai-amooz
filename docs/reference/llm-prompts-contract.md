# Reference — The PROMPTS contract (HUB)

- **Status:** Verified · **Created:** 2026-07-02 · **Last-verified:** 2026-07-02 (commit `a4d5a23`)
- **Owner (doc):** technical-writer · **Spec source:** `docs/reference/ROADMAP.md` step L3
- **Layer:** llm (cross-cutting HUB — every stage doc links here for its prompt key)

## Purpose
The single source of every LLM prompt in the project, and the hardest contract in the repo: keys,
placeholder tokens, and output-JSON keys are a byte-for-byte agreement with parsers, Pydantic schemas,
and frontend widgets. This doc is the map; `test_prompts_contract.py` is the enforced source of truth.

## Scope & paths
| File | Role |
|---|---|
| `apps/commons/llm_prompts/prompts.py` | The `PROMPTS` dict + shared blocks; **only `PROMPTS` is exported** |
| `apps/commons/llm_prompts/__init__.py` | `from .prompts import PROMPTS` (nothing else public) |
| `apps/classes/test_prompts_contract.py` (264) | **The zero-token guard** — live keys, placeholders, output keys, shared blocks |

## Public surface — the 26 live top-level keys (`LIVE_KEYS`, test:39-65)
A key's value is a plain string (sub = `None`) or a `{strategy: str}` dict. Callers look up by these
**exact literal keys**.

| Key | Strategies | Key | Strategies |
|---|---|---|---|
| `pdf_extraction` | default | `chat_intent` | (string) |
| `prerequisites_prompt` | default | `chat_system_prompt` | (string) |
| `prerequisite_teaching` | default | `image_plan` | default |
| `structure_content` | default | `text_grading` | default |
| `recap_and_notes` | default | `exam_prep_hint` | default |
| `exam_prep_structure` | default | `json_repair` | default |
| `chat_image_description` | default | `memory_summary` | default |
| `final_exam_pool` | **default, adaptive** | `exam_prep_chat` | default |
| `section_quiz` | **default, adaptive** | `exam_prep_handwriting_vision` | default |
| `transcribe_media` | **default, chunked** | `notes_ai` | detailed_notes |
| `fetch_quizzes` | multiple_choice | `practice_tests` | mixed_questions |
| `flash_cards` | standard_qa | `match_games` | term_definition |
| `meril` | problem_centered | | |

Adaptive strategies (`section_quiz`, `final_exam_pool`) share the **EXACT same output contract** as their
default sibling — the test enforces identical OUTPUT_KEYS for both.

**Shared blocks** (concatenated into prompts, edit-in-one-place): `SAFETY_PREAMBLE` (injection/leak/
accuracy guards), `AUDIENCE_ADAPTIVE` (no hardcoded "K-12" — any level), `MCQ_QUALITY` (distractor/Bloom
rubric), `MATH_FORMAT_INSTRUCTIONS`.

## Key flows
1. **Rendering:** templates render with **`str.replace`, never `str.format`** — so literal JSON braces
   `{ }` in a template are harmless, but the documented placeholder tokens must appear verbatim. A
   dropped token silently no-ops (the model gets literal `{user_message}` text). Placeholder map:
   `test_prompts_contract.py:96-132` (PLACEHOLDERS) — e.g. `chat_system_prompt` needs
   `{student_name}/{unit_content}/{history_str}/{user_message}`; `section_quiz.default` needs
   `{count}/{section_content}/{{blank}}`; `transcribe_media.chunked` needs
   `{part_number}/{total_parts}/{previous_transcript_tail}`; `notes_ai`/quiz-generators use the literal
   token `STRUCTURED_BLOCKS_JSON`.
2. **Output keys:** each generating prompt's output-JSON keys are a contract with the parser/Pydantic/UI.
   Map: `test_prompts_contract.py:135-173` (OUTPUT_KEYS) — e.g. `structure_content` → `root_object/
   outline/merrill_type/source_markdown/content_markdown/image_ideas`; `section_quiz` → `questions/
   correct_answer/difficulty`; `exam_prep_structure` → `question_text_markdown/options/
   correct_option_label/teacher_solution_markdown/final_answer_markdown`.
3. **Guard test (run after ANY prompt edit):**
   `python -m pytest backend/apps/classes/test_prompts_contract.py -q` — asserts all live keys present,
   NO unexpected top-level keys, dead keys stay removed, placeholders + output keys present, safety block
   in untrusted-content prompts, MCQ block in quiz generators, no "K-12". Zero tokens.

## Data & invariants
- Only `PROMPTS` is exported (`__init__.py`) — a key is a "feature"; callers use literal keys.
- `str.replace` templating (never `str.format`) — invariant.
- **Dead-key policy:** 9 dead top-level keys + 3 dead sub-keys were audited out (test:67-84,
  `test_no_unexpected_top_level_keys`); **don't re-add unreferenced prompts.**
- Placeholder tokens + output-JSON keys are byte-for-byte; adaptive ≡ default output contract.
- Shared safety/MCQ/math/audience blocks are edited in ONE place and asserted present where required.

## Gotchas
- The contract test is the SOURCE OF TRUTH — if this doc and the test ever disagree, the test wins;
  this doc cites it rather than duplicating the full maps.
- A prompt edit that "reads fine" can still break production silently by dropping a placeholder or
  renaming an output key — always run the contract test.
- `pdf_extraction.default` is built via parenthesized string concatenation (test `_text` str-casts it).

## Cross-links
[llm-provider-client.md](llm-provider-client.md) (L1) · [llm-structured-output.md](llm-structured-output.md)
(L2, consumes these output keys) · every stage doc L5–L10 links here for its specific key ·
`.claude/agents/ai-engineer.md` · CLAUDE.md §"Prompt repository".

## Verified-by
- Full read (2026-07-02): `test_prompts_contract.py` (264) — the authoritative maps (LIVE_KEYS 26 keys,
  PLACEHOLDERS, OUTPUT_KEYS, DEAD lists).
- `rg "^__all__|^PROMPTS|^SAFETY_PREAMBLE|str\.format|\.replace" prompts.py` → confirmed `PROMPTS`
  dict at `:182`, shared blocks at `:32/54/73/82`, no `str.format` (the doc-comment at `:10` states the
  `str.replace` rule); `__init__.py` exports only `PROMPTS`.
- NOT read whole: `prompts.py` body (large; the contract test enumerates its contract, which is what
  callers depend on — reading the prose wording adds no contract information).
- NOT verified live: model behavior given these prompts (Avalai VPN-blocked; the contract is string-level).
