# Reference — Stage: exam-prep pipeline (the 2-step set)

- **Status:** Verified · **Created:** 2026-07-02 · **Last-verified:** 2026-07-02 (post-fix)
- **Owner (doc):** technical-writer · **Spec source:** `docs/reference/ROADMAP.md` step L9
- **Layer:** llm (the standalone exam-prep pipeline)

## Purpose
The exam-prep feature's LLM half: a standalone 2-step pipeline (transcribe → extract Q&A structure)
distinct from the class 5-step pipeline, plus the student-facing exam-prep chat + per-answer hint +
handwriting-vision. Turns a teacher's exam/solutions upload into structured, gradable questions.

## Scope & paths
| File | Role |
|---|---|
| `apps/classes/services/exam_prep_structure.py` | `extract_exam_prep_structure` (step 2) |
| `apps/classes/services/exam_prep_utils.py` | `normalize_exam_prep_questions` / `normalize_exam_prep_json` (validation/dedupe) |

**Out of scope:** prompt bodies → L3; the views (submit/check-answer/result/reset) → B7; models → B4;
step-1 transcription (shared infra) → L5.

## Public surface
- **`extract_exam_prep_structure(*, transcript_markdown) -> (dict, provider, model)`**
  (`exam_prep_structure.py:92`) — prompt `exam_prep_structure.default`. Output contract (L3):
  `exam_prep`, `question_text_markdown`, `options`, `correct_option_label`, `teacher_solution_markdown`,
  `final_answer_markdown`.
- **`normalize_exam_prep_questions(exam_prep_obj) -> (dict, changed)`** (`exam_prep_utils.py:11`) — every
  question validated + deduped; returns whether it mutated.
- **`normalize_exam_prep_json(raw_value) -> (str|None, changed)`** (`:44`).
- Prompt keys also used by B7 views: `exam_prep_hint` (per-answer hint), `exam_prep_chat` (tutor),
  `exam_prep_handwriting_vision` (multimodal handwriting read).

## Key flows
1. **Step 2 (structure):** transcript → `PROMPTS["exam_prep_structure"]["default"]` (system) +
   transcript (user) → `generate_text` → `_attempt_parse_with_repair` (`:81`) → `_reinject_exam_assets`
   (`:50`) + `_restore_latex_escapes` (`:30`) → validated/deduped by `normalize_exam_prep_questions`.
   Status EXAM_STRUCTURING → EXAM_STRUCTURED (B4/L4).
2. **Windowing:** exam-prep step 2 extracts per overlapping window so it never crashes on big input
   (every question validated/deduped) — shares the chunked-transcription infra (L5, memory
   `chunked-transcription-500mb` follow-up).
3. **Student interactions** (B7 views call these): `exam_prep_hint` for a per-question hint,
   `exam_prep_chat` for the tutor, `exam_prep_handwriting_vision` (standard multimodal, L1
   `part_from_bytes`) to read handwritten work.

## Data & invariants
- Distinct 2-step flow (EXAM_TRANSCRIBING → EXAM_TRANSCRIBED → EXAM_STRUCTURING → EXAM_STRUCTURED) —
  never merged with the class 5-step machine (B4/L4).
- Output-JSON keys are the L3 contract (the exam question shape frontend widgets read).
- Every question passes `normalize_exam_prep_questions` (validate + dedupe) before storage.
- Handwriting-vision uses the standard multimodal shapes (L1) — not the legacy ignored shape.
- Model env chain: `STRUCTURE_MODEL` → `REWRITE_MODEL` → `MODEL_NAME`.

## Gotchas
- **Model resolution is ENV-only** (`_select_model("STRUCTURE_MODEL", "REWRITE_MODEL")` → `MODEL_NAME`,
  then **raises**). The old hardcoded `"gpt-4.1"` fallback was **removed** (2026-07-02) so a misconfigured
  deploy fails loudly instead of silently calling a specific model. The sibling PDF stage's
  `pdf_extraction._select_vision_model` was fixed the same way (dropped `"gemini-2.5-flash"`). Guard:
  `apps/classes/test_model_selection_env_only.py`. (The chat-client default `llm_client._default_model`
  still keeps `CHAT_MODEL or "gemini-2.5-flash"` — a deliberate general-chat default, out of scope here.)
- Exam-prep has no adaptive-regenerate loop (that's the class quiz/final-exam feature, B6/L8); it has a
  reset-to-retake instead (B7).
- Uses the `generate_text`+repair path, not `generate_structured` (part of L2's pending migration).

## Cross-links
[llm-prompts-contract.md](llm-prompts-contract.md) (L3, the 4 exam-prep keys) ·
[backend-classes-exam-prep.md](backend-classes-exam-prep.md) (B7, the views) ·
[llm-transcription.md](llm-transcription.md) (L5, shared windowing infra) ·
[llm-pipeline-orchestration.md](llm-pipeline-orchestration.md) (L4, statuses) ·
[backend-classes-models.md](backend-classes-models.md) (B4) · memory: `chunked-transcription-500mb` ·
`.claude/agents/ai-engineer.md`.

## Verified-by
- `rg "^def |PROMPTS\[|exam_prep_*" exam_prep_structure.py` → `extract_exam_prep_structure:92`, prompt
  key `exam_prep_structure.default:112`, the parse-repair + asset-reinject helpers.
- Read (2026-07-02): `exam_prep_structure.py:92-136` (env model chain via `_select_model` — **the
  `gpt-4.1` fallback removed 2026-07-02**, now raises; prompt build, generate_text call).
- `rg "^def |normalize" exam_prep_utils.py` → `normalize_exam_prep_questions:11`,
  `normalize_exam_prep_json:44`.
- Output keys cross-checked against `test_prompts_contract.py:147-150`.
- NOT read whole: service bodies. NOT verified live: exam-prep LLM pipeline (Avalai VPN-blocked).
