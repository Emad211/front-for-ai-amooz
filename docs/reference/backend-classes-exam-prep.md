# Reference — `apps/classes` exam-prep views (teacher + student)

- **Status:** Verified · **Created:** 2026-07-02 · **Last-verified:** 2026-07-02 (commit `9edfb4e`)
- **Owner (doc):** technical-writer · **Spec source:** `docs/reference/ROADMAP.md` step B7
- **Layer:** backend-app (exam-prep slice of the classes god view)

## Purpose
The exam-prep feature: teachers build a 2-step exam-prep session (upload → Q&A structure) distinct from
the 5-step class pipeline; students then take it, check individual answers (with hints), chat, view
results, and reset to retake. Documents the view→task dispatch boundary; LLM bodies are L9.

## Scope & paths
| File | Role |
|---|---|
| `apps/classes/views.py` ~L3400–5100 (grep-targeted slice) | exam-prep view classes |
| `apps/classes/services/{exam_prep_utils (non-LLM), student_exam_chat_history}.py` | supporting |

**Out of scope:** class pipeline views → B5/B6; exam-prep LLM structure/hint bodies → L9; models → B4.

## Public surface (`/api/classes/…`)
**Teacher** (`[IsAuthenticated, IsTeacherUser]`)
| Route | View (`views.py:line`) |
|---|---|
| `POST exam-prep-sessions/step-1/` · `step-2/` | ExamPrepStep1Transcribe `:3400` (upload) / Step2Structure `:3562` |
| `GET exam-prep-sessions/` · `/<id>/` | List `:3721` / Detail `:3607` (status polling) |
| `POST …/<id>/publish/` · `cancel/` | Publish `:3758` / **Cancel `:3691` (owner-only)** |
| `GET/POST …/<id>/invites/` (+`/<id>/`) | Invitation `:3813`/`:3897` |
| `GET/POST …/<id>/announcements/` (+`/<id>/`) | Announcement `:3927`/`:3974` |

**Student** (`[IsAuthenticated, IsStudentUser]`)
| Route | View (`views.py:line`) |
|---|---|
| `GET student/exam-preps/` · `/<id>/` | List `:4105` / Detail `:4169` (questions) |
| `POST …/<id>/submit/` | Submit `:4257` |
| `POST …/<id>/check-answer/` | CheckAnswer `:4489` (per-question feedback/hint) |
| `GET …/<id>/result/` | Result `:4809` (score + per-question correctness) |
| `POST …/<id>/reset/` | Reset `:4926` (retake) |
| `POST …/<id>/chat/` · `chat-media/` · `GET chat-history/` | Chat `:4708` / Media `:5026` / History `:4997` |

## Key flows
1. **Exam-prep pipeline (2-step):** `ExamPrepStep1Transcribe` uploads media → dispatches the exam-prep
   pipeline (`process_exam_prep_*`, L4/L9); status advances EXAM_TRANSCRIBING → EXAM_TRANSCRIBED →
   EXAM_STRUCTURING → EXAM_STRUCTURED (B4). Distinct `pipeline_type=EXAM_PREP` on the session — the same
   `ClassCreationSession` model, different type.
2. **Cancel** (`ExamPrepSessionCancel:3691`): owner-only, filtered on `pipeline_type=EXAM_PREP` (parallels
   B5's class cancel; can't cross-cancel a class session).
3. **Student attempt:** submit (`:4257`, phone-scoped via `invites__phone` + `pipeline_type=EXAM_PREP`) →
   check-answer for per-question hints (L9 `exam_prep_hint`) → result (score + per-question) → reset to
   retake. Attempts persist on `StudentExamPrepAttempt` (B4, `answers` JSON).
4. **Chat:** exam-prep-specific tutor with handwriting-vision support (L9 `exam_prep_handwriting_vision`).

## Data & invariants
- Exam-prep reuses `ClassCreationSession` with `pipeline_type=EXAM_PREP` — cancel/publish/roster queries
  MUST filter on that type so class and exam-prep sessions never cross.
- Student endpoints are phone-scoped (`invites__phone`); no phone → 400.
- Cancel is owner-only (404 for non-owner) and 409 if not in an active pipeline state — same contract as B5.
- The question JSON contract (`question_text_markdown`, `options`, `correct_option_label`,
  `teacher_solution_markdown`, `final_answer_markdown`) is generated in L9 and read here.

## Gotchas
- `views.py` 5199 lines; this slice ~L3400–5100 — grep by class.
- Both class and exam-prep sessions live in ONE table (`ClassCreationSession`); every exam-prep query
  needs the `pipeline_type=EXAM_PREP` filter, or it would leak/act on class sessions.
- Reset clears the attempt so the student can retake — exam-prep has no adaptive-regenerate loop (that's
  the class quiz/final-exam feature, B6).

## Cross-links
[backend-classes-models.md](backend-classes-models.md) (B4, `StudentExamPrepAttempt` + Status) ·
[llm-exam-prep.md] (L9, structure/hint/handwriting bodies) · [backend-classes-teacher-views.md] (B5,
parallel cancel/publish) · [llm-pipeline-orchestration.md](llm-pipeline-orchestration.md) (L4) · memory:
`chunked-transcription-500mb` (exam-prep windowing), `pipeline-cancellation`.

## Verified-by
- `rg "^class ExamPrep…/StudentExamPrep…View" + -A1 views.py` → the 19-view inventory + line numbers.
- Read (2026-07-02): `views.py:4257-4286` (`StudentExamPrepSubmit` — phone + `pipeline_type=EXAM_PREP`
  scoping) + `urls.py` exam-prep route map (B5 doc).
- NOT read whole: `views.py` (5199 lines — only the exam-prep slice + submit head). NOT verified live:
  exam-prep LLM pipeline (Avalai VPN-blocked).
