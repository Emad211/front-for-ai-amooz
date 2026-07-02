# Reference — Frontend student dashboard `(dashboard)`

- **Status:** Verified · **Created:** 2026-07-02 · **Last-verified:** 2026-07-02 (commit `6a751ec`)
- **Owner (doc):** technical-writer · **Spec source:** `docs/reference/ROADMAP.md` step F6 [a/b — kept single: ~44 components, manageable]
- **Layer:** frontend-route-group (student area)

## Purpose
The student's learning UI: home, course list, the learn viewer (structured content + tutor +
interactive widgets), the final exam, exam-prep, calendar, profile, notifications, tickets. Consumes the
B6 student endpoints via F3 hooks.

## Scope & paths
| Route | Page | Purpose |
|---|---|---|
| `home` | `home/page.tsx` | dashboard (stats, welcome, recent activity, upcoming) |
| `classes` | course list |
| `learn/[courseId]` | `learn/page.tsx` | the learn viewer (content + chat + quizzes) |
| `exam/[examId]` (+`/result`) | final exam take + result |
| `exam-prep` | exam-prep list/take |
| `calendar`, `profile`, `notifications`, `tickets` | supporting screens |

Components: `frontend/src/components/dashboard/**` (~44 files): `learn/` (course-sidebar, lesson-content,
chapter-quiz, final-exam, learn-chat-assistant + `widgets/` interactive-quiz/flashcard/match-game/notes/
scenario), `exam/` (exam-header, chat-assistant, question-content), `calendar/` (grid/header/day-cell/
event-*), `home/` (stats-grid, welcome, recent-activity, upcoming-events), `notifications/`, `profile/`,
`tickets/`, `ui/` (cards).

**Out of scope:** the B6 endpoint contracts → B6; the adaptive quiz JSON → L8; shared primitives → F11.

## Public surface / key screens
- **Learn viewer** (`learn/[courseId]/page.tsx` + `components/dashboard/learn/`): `course-sidebar` +
  `lesson-content` (structured content, `MarkdownWithMath`/`MathText`, F2) + `learn-chat-assistant`
  (course tutor, B6 chat) + `widgets/` (interactive quiz/flashcard/match-game/notes/scenario — the
  study aids from L8).
- **Chapter quiz + final exam** (`learn/chapter-quiz.tsx`, `learn/final-exam.tsx`,
  `exam/[examId]`): take/submit → the adaptive loop (reveal-on-fail, regenerate) driven by B6 endpoints;
  green/red + «پاسخ صحیح» reveal on submit.
- **Calendar** (`calendar/` components), **profile** (`profile/profile-form.tsx`), **notifications**,
  **tickets**.
- Hooks: `use-course-content`, `use-exam`, `use-courses`, `use-calendar`, `use-dashboard-data`,
  `use-notifications`, `use-profile`, `use-tickets` (F3).

## Key flows
1. **Learn:** `use-course-content` → render structured lesson + sidebar; `learn-chat-assistant` posts to
   the course chat (B6); interactive widgets render the L8 study aids.
2. **Adaptive assessment (UI half):** take chapter quiz / final exam → on submit the response reveals
   `correct_answer` (B6) → widget shows correct/incorrect + the answer → «آزمون جدید» regenerate
   (enabled only after a fail, B6 409/400 guards).
3. **Content entry** triggers backend pregeneration on first load (B6/L4) — transparent to the UI.

## Data & invariants
- All API access via F3 hooks/services (no ad-hoc fetch); the layout mounts `OnboardingGate` (F4).
- Math: lesson body → `MarkdownWithMath`, titles → `MathText` (F2) — never raw LaTeX.
- The quiz/exam widgets consume the B6/L8 JSON shapes verbatim (`questions`/`exam`/`per_question` with
  `correct_answer`) — a shape change there must update these widgets.
- RTL + Persian digits/Jalali throughout (F2).
- Student-only route group (guarded); `IsStudentUser` server-side allows teachers too (B4).

## Gotchas
- The learn widgets (`interactive-*`) are tightly coupled to the L8 output keys — renaming an output key
  breaks the widget silently (build hides type errors; run tsc).
- The reveal-on-submit UI depends on the POST response carrying `correct_answer`; GET hides it (B6) —
  don't cache a GET response and treat it as post-submit.
- Component count (~44) is under the split threshold — kept as one doc (roadmap [a/b] not needed).

## Cross-links
[backend-classes-student-views.md](backend-classes-student-views.md) (B6, the endpoints) ·
[llm-quizzes-adaptive.md](llm-quizzes-adaptive.md) (L8, quiz/widget JSON) ·
[frontend-services-hooks.md](frontend-services-hooks.md) (F3) · [frontend-conventions.md](frontend-conventions.md)
(F2, math/RTL) · [frontend-shared-ui.md] (F11) · memory: `adaptive-quiz-loop`, `title-math-rendering` ·
`.claude/agents/frontend-engineer.md`, `ux-designer.md`.

## Verified-by
- `Glob (dashboard)/**/page.tsx` → 10 student routes tabulated above.
- `Glob components/dashboard/**/*.tsx` → ~44 components; the learn/exam/calendar/home/widgets groupings
  cited are from the real paths.
- Component→backend mapping cross-checked against B6 (endpoints) + L8 (widget JSON).
- NOT read whole: component bodies (grep/glob gives the inventory + structure). NOT run this pass:
  tsc/lint (F-layer AUDIT gate).
