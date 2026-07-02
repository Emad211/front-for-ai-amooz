# Reference — Stage: quizzes, final exam & the adaptive weak-point loop

- **Status:** Verified · **Created:** 2026-07-02 · **Last-verified:** 2026-07-02 (commit `94b0fa1`)
- **Owner (doc):** technical-writer · **Spec source:** `docs/reference/ROADMAP.md` step L8
- **Layer:** llm (assessment generation + the student-facing adaptive loop)

## Purpose
Generates chapter quizzes and the course final exam, plus the chat-triggered study aids — and owns the
adaptive remediation loop's generation half: after a student fails, produce a NEW assessment targeting
exactly the concepts they missed. The `compute_weak_points` half is pure/zero-token.

## Scope & paths
| File | Role |
|---|---|
| `apps/classes/services/quizzes.py` | all quiz/exam/study-aid generators |
| `apps/classes/services/adaptive_quiz.py` (112) | `compute_weak_points_from` / `compute_weak_points` (pure) |
| `apps/classes/tasks.py` `pregenerate_student_assessments` | pre-build a student's assessments (L4) |

**Out of scope:** prompt bodies → L3; the view endpoints (regenerate guards, answer-reveal) → B6;
model fields → B4.

## Public surface
Generators in `quizzes.py`:
- `generate_section_quiz_questions(...)` (`:102`) — prompt `section_quiz.default`; `{questions:[...]}`.
- `generate_adaptive_section_quiz(...)` (`:132`) — prompt `section_quiz.adaptive`; **same JSON shape** as
  default.
- `generate_final_exam_pool(...)` (`:224`) — `final_exam_pool.default`.
- `generate_adaptive_final_exam(...)` (`:254`) — `final_exam_pool.adaptive`; same shape as default.
- `grade_open_text_answer(...)` (`:189`) — `text_grading.default` (`score_0_100`/label/feedback).
- `generate_answer_hint(...)` (`:304`) — `exam_prep_hint.default`.
- Plus the chat/study-aid generators using keys `fetch_quizzes`, `practice_tests`, `flash_cards`,
  `match_games`, `meril`, `notes_ai` (L3).

Weak-point (pure, zero-token) in `adaptive_quiz.py`:
- `compute_weak_points_from(questions_obj, attempts) -> list[dict]` (`:65`) — one entry per distinct
  missed question, most-missed-first (`{id, question, correct_answer, difficulty, student_answer,
  times_wrong}`).
- `compute_weak_points(quiz, *, max_attempts=3)` (`:105`) — the `ClassSectionQuiz` wrapper.

## Key flows
1. **Adaptive loop generation:** student fails → view reveals answers (B6) → regenerate endpoint calls
   `compute_weak_points(quiz)` → `generate_adaptive_section_quiz(..., weak_points)` (prompt
   `section_quiz.adaptive` with `{review_count}`+`{weak_points_json}`) → overwrites `questions`, resets
   `last_passed` (B6/B4).
2. **Both grading shapes** (`_is_wrong:44`): section quizzes report `score_0_100` (threshold **70**);
   the final exam reports `score_points`/`max_points`. The weak-point join handles both uniformly.
3. **Pre-generation:** `pregenerate_student_assessments` (L4) builds every section quiz + the final exam
   on a student's first entry (idempotent, best-effort); on-demand generation is the fallback.

## Data & invariants
- **Adaptive strategies share the EXACT default output contract** — the L3 contract test enforces
  `section_quiz` / `final_exam_pool` = `[default, adaptive]` with identical OUTPUT_KEYS, so frontend
  widgets and parsers are unchanged. Don't diverge the adaptive JSON shape.
- `WEAK_POINT_SCORE_THRESHOLD = 70` (`adaptive_quiz.py:28`) — mirrors the quiz passing band.
- `compute_weak_points_from` is **pure Python over stored data, zero LLM calls** — cheap + unit-testable;
  keep it that way (don't add an LLM call into weak-point computation).
- Sources it reads: `ClassSectionQuiz.questions` (carries `correct_answer`) +
  `ClassSectionQuizAttempt.result['per_question']` (carries misses); works for `ClassFinalExam.exam` too.
- All quiz generators carry `MCQ_QUALITY` (L3 contract-tested) + safety/math blocks; model names env-driven.
- These generators use the `_parse_json_result` path — the `generate_structured` migration for quizzes
  is part of the still-pending follow-up (L2).

## Gotchas
- Newest-first attempt scan means the recorded `student_answer` is from the LATEST attempt
  (`adaptive_quiz.py:96`).
- No-label + no-score per-question → treated as NOT wrong (avoids noise) — an intentional conservative bias.
- The rate-limiter is the `last_passed` reset in the VIEW (B6), not anything in this generation code.

## Cross-links
[llm-prompts-contract.md](llm-prompts-contract.md) (L3, all the quiz/exam/study-aid keys) ·
[backend-classes-student-views.md](backend-classes-student-views.md) (B6, regenerate guards +
answer-reveal) · [backend-classes-models.md](backend-classes-models.md) (B4, questions/exam/result JSON) ·
[llm-pipeline-orchestration.md](llm-pipeline-orchestration.md) (L4, pregeneration) · memory:
`adaptive-quiz-loop` · `.claude/agents/ai-engineer.md`, `data-analyst.md` (regeneration cost).

## Verified-by
- `rg "^def |PROMPTS\[|generate_adaptive" quizzes.py` → the generator inventory + the 6 quiz/exam prompt
  keys (default+adaptive for section_quiz/final_exam_pool) + text_grading + exam_prep_hint.
- Full read (2026-07-02): `adaptive_quiz.py` (112) — `compute_weak_points_from`, both grading shapes
  (`_is_wrong`), the 70 threshold, pure/zero-token property.
- Adaptive≡default output contract cross-checked against `test_prompts_contract.py:156-159`.
- NOT read whole: `quizzes.py` body. NOT verified live: LLM quiz generation (Avalai VPN-blocked; guarded
  by `adaptive-quiz-loop` tests).
