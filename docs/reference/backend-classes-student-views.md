# Reference — `apps/classes` student course views (content, chat, adaptive assessment)

- **Status:** Verified · **Created:** 2026-07-02 · **Last-verified:** 2026-07-02 (commit `04a85f3`)
- **Owner (doc):** technical-writer · **Spec source:** `docs/reference/ROADMAP.md` step B6
- **Layer:** backend-app (student-facing slice of the classes god view)

## Purpose
The student's learning surface: browse course content, mark progress, export PDF, chat with the
course-aware tutor, and take the chapter quizzes + final exam — including the **adaptive weak-point
loop** (fail → reveal answers → regenerate targeting missed concepts). The endpoint contracts here are
consumed verbatim by the frontend quiz/exam widgets.

## Scope & paths
| File | Role |
|---|---|
| `apps/classes/views.py` ~L1791–3260 (grep-targeted slice) | student view classes |
| `apps/classes/services/{student_chat_history,markdown_assets}.py` · `adaptive_quiz.py` (view side) | supporting |

**Out of scope:** teacher views → B5; exam-prep → B7; quiz/exam LLM generation → L8; model shapes → B4.

## Public surface (`/api/classes/…`, `[IsAuthenticated, IsStudentUser]` unless noted)
| Route | View (`views.py:line`) | Role |
|---|---|---|
| `GET student/courses/` | StudentCourseList `:1791` | enrolled courses |
| `GET student/courses/<id>/content/` | StudentCourseContent `:1855` | structured content (dispatches pregeneration on first entry) |
| `POST …/lessons/<lesson_id>/complete/` | StudentLessonComplete `:1953` | mark unit complete |
| `GET …/export-pdf/` | StudentCoursePdfExport `:2005` | WeasyPrint export (L10) |
| `POST …/chat/` · `chat-media/` · `GET chat-history/` | StudentCourseChat `:2079` / Media `:2203` / History `:2179` | course tutor |
| `GET/POST …/chapters/<chapter_id>/quiz/` | StudentChapterQuiz `:2370` | take a chapter quiz |
| `POST …/chapters/<chapter_id>/quiz/regenerate/` | StudentChapterQuizRegenerate `:2623` | adaptive regenerate (guarded) |
| `GET/POST …/final-exam/` | StudentFinalExam `:2753` | take the final exam |
| `POST …/final-exam/regenerate/` | StudentFinalExamRegenerate `:3021` | adaptive regenerate (guarded) |
| `POST invites/verify/` | InviteCodeVerify `:3147` | **AllowAny** (pre-login code check) |
| `GET student/notifications/` | StudentNotificationList `:3206` | announcements feed |

## Key flows
1. **Content entry** (`StudentCourseContent:1855`): student scoped via `invites__phone` (enrollment by
   phone); on first entry dispatches `pregenerate_student_assessments` (L4) guarded by a `cache.add`
   flag (idempotent, best-effort) so quizzes/exam are pre-built.
2. **Adaptive quiz loop** (the product's core learning mechanic):
   - **Take/submit** (`StudentChapterQuiz:2370`): the **POST (submit)** response reveals
     `correct_answer` (final exam also `explanation`) in `per_question` — the failed assessment is about
     to be replaced. **GET before answering still HIDES them.**
   - **Regenerate** (`StudentChapterQuizRegenerate:2623`): allowed ONLY when `last_passed is False`
     (else **409**; no quiz yet → **400**). Computes `compute_weak_points(quiz)` from the attempt's
     `result['per_question']` and generates a new quiz targeting them (L8). Overwrites `questions` and
     **resets `last_passed`/`last_score` to None** — that reset is the deliberate rate-limiter (must
     take+fail the fresh one before regenerating again → a natural forever-loop, not a spam button).
   - Final exam mirrors this (`StudentFinalExam*:2753/3021`), grading on `score_points`/`max_points`.
3. **Chat:** course-aware tutor (chatbot L-layer) with history + media upload; PDF export via WeasyPrint.

## Data & invariants
- Enrollment scoping is by **phone** (`invites__phone=user.phone`) — a student with no phone gets 400.
- **Answer-reveal contract:** `correct_answer`/`explanation` present in POST `per_question`, absent in
  GET-before-answering. Don't "tidy" the keys off the submit response, and don't leak them on GET.
- **`last_passed` reset = rate-limiter** — the whole loop's safety depends on it (B4/L8).
- Regenerate guards: 409 unless `last_passed is False`; 400 if no assessment exists yet.
- No migration for the loop — reuses `ClassSectionQuiz.questions` / `ClassFinalExam.exam` JSON (B4).
- `IsStudentUser` allows TEACHER too (teachers can learn) — intentional.

## Gotchas
- `views.py` is 5199 lines; this slice is ~L1791–3260 — grep by class, never read whole.
- `chapter_id` resolves by `external_id` first, then falls back to integer PK — both accepted.
- `invites/verify/` is AllowAny (pre-login) — the only public endpoint in this slice.

## Cross-links
[backend-classes-models.md](backend-classes-models.md) (B4, quiz/exam JSON fields + last_passed) ·
[llm-quizzes-adaptive.md] (L8, generation + `compute_weak_points`) · [backend-classes-teacher-views.md]
(B5) · [llm-pipeline-orchestration.md](llm-pipeline-orchestration.md) (L4, pregeneration) · L10 (PDF
export) · memory: `adaptive-quiz-loop`, `title-math-rendering` · frontend consumer → F6.

## Verified-by
- `rg "^class Student…View" + -A2 views.py` → the student view inventory + permissions + lines above.
- Read (2026-07-02): `views.py:2623-2682` (`StudentChapterQuizRegenerate` — the 409/400 guards,
  `last_passed is False` rule, `compute_weak_points`, phone-scoped session lookup) + `urls.py` route map.
- NOT read whole: `views.py` (5199 lines — only the student slice + regenerate body). NOT verified live:
  LLM quiz generation (Avalai VPN-blocked; guarded by `adaptive-quiz-loop` tests).
