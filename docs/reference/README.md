# Reference documentation — index & progress (the loop's control file)

- **Status:** Living · **Created:** 2026-07-02 · **Owner:** technical-writer
- Program decision: [ADR-0002](../adr/ADR-0002-reference-docs-program.md) · Per-step specs: [ROADMAP.md](ROADMAP.md) · Doc shape: [TEMPLATE.md](TEMPLATE.md)

Comprehensive, code-verified module/domain reference. Complements — never restates — `features/`
(behavior), `adr/` (decisions), `CLAUDE.md` (conventions), runbooks (ops).

## How the loop resumes (deterministic)
1. Find the **first ☐ row** below. That is the next step — exactly one per loop iteration, hard stop.
2. Open its spec in [ROADMAP.md](ROADMAP.md); write the doc per [TEMPLATE.md](TEMPLATE.md).
   Work solo (agent files = free checklists; no agent fan-out). Grep-targeted reads only; god files
   (`classes/views.py` 5199 / `commons/views.py` 1829 / `organizations/views.py` 1042) never read whole.
3. Definition of done (all five): written to template · every claim has a `Verified-by` entry ·
   no duplication (link, don't restate; memory files cited for history only — durable contracts restated
   in-repo) · cross-links resolve · committed as `docs(reference): <ID> <module>` with this checklist
   flipped **in the same commit**, then pushed.
4. Steps marked [a/b] may split into two iterations, each shipping a coherent doc + a flipped sub-box.
5. After the last step, run AUDIT, then the loop ends.

Legend: ☐ not started · ◐ drafting · ☑ verified & merged

## Master checklist (dependency-ordered)
| # | ID | Doc file | Covers | Status | Last-verified |
|---|----|----------|--------|--------|---------------|
| 1 | S1 | `00-architecture-overview.md` | System map: monorepo, routing, apps, pipelines, contracts | ☑ | 2026-07-02 |
| 2 | B0 | `backend-core.md` | `core/` settings, urls, DRF defaults, throttling, storage | ☑ | 2026-07-02 |
| 3 | B1 | `backend-accounts.md` | Identity: roles, phone uniqueness, onboarding fields, migrations | ☑ | 2026-07-02 |
| 4 | B2 | `backend-authentication.md` | JWT/OTP/login layer, code-login rules | ☑ | 2026-07-02 |
| 5 | B3 | `backend-organizations.md` + `backend-waitlist.md` [a/b] | Tenancy, StudyGroup, invite codes, waitlist gate | ☑ | 2026-07-02 |
| 6 | L1 | `llm-provider-client.md` | Provider selector, llm_client, env→model matrix | ☑ | 2026-07-02 |
| 7 | L2 | `llm-structured-output.md` | generate_structured / validate_keep_dict / schemas | ☑ | 2026-07-02 |
| 8 | L3 | `llm-prompts-contract.md` | **HUB** — 26 live PROMPTS keys, placeholders, output keys | ☑ | 2026-07-02 |
| 9 | B4 | `backend-classes-models.md` | Classes ER map (17 models), status machine, JSON fields | ☑ | 2026-07-02 |
| 10 | L4 | `llm-pipeline-orchestration.md` | **HUB** — tasks.py state machines, cancellation, heartbeats | ☑ | 2026-07-02 |
| 11 | B5 | `backend-classes-teacher-views.md` | Teacher surface: pipeline control, invites, analytics | ☑ | 2026-07-02 |
| 12 | B6 | `backend-classes-student-views.md` | Student surface: content, chat, adaptive quiz/exam contract | ☑ | 2026-07-02 |
| 13 | B7 | `backend-classes-exam-prep.md` | Exam-prep surface (teacher + student) | ☑ | 2026-07-02 |
| 14 | L5 | `llm-transcription.md` | Chunked transcription, multimodal shapes, env knobs | ☑ | 2026-07-02 |
| 15 | L6 | `llm-structure-stage.md` | Structure extraction (step 2), validate_keep_dict | ☑ | 2026-07-02 |
| 16 | L7 | `llm-prereqs-recap.md` | Steps 3–5: prerequisites, teaching, recap | ☑ | 2026-07-02 |
| 17 | L8 | `llm-quizzes-adaptive.md` | Quizzes, final exam, adaptive weak-point loop | ☑ | 2026-07-02 |
| 18 | L9 | `llm-exam-prep.md` | Exam-prep 2-step pipeline, question JSON contract | ☑ | 2026-07-02 |
| 19 | L10 | `llm-pdf-and-cost.md` [a/b] | PDF ingest/export + LLMUsageLog cost attribution | ☑ | 2026-07-02 |
| 20 | B8 | `backend-celery-ops.md` | Queues, beat, time limits, SMS, media compressor | ☐ | — |
| 21 | B9 | `backend-commons-admin.md` + `backend-notification.md` [a/b] | Admin API, analytics, tickets, notifications | ☐ | — |
| 22 | F1 | `frontend-app-shell.md` | Root layout, route-group inventory, next.config contract | ☐ | — |
| 23 | F2 | `frontend-conventions.md` | Tokens/RTL/Persian/math rules + lib catalog | ☐ | — |
| 24 | F3 | `frontend-services-hooks.md` | 9 services + 34 hooks, endpoint mapping, error contract | ☐ | — |
| 25 | F4 | `frontend-auth-guards.md` | Auth redirect, onboarding gate, routing, zod wizard | ☐ | — |
| 26 | F5 | `frontend-auth-screens.md` | (auth) + start/ + join/ + onboarding screens | ☐ | — |
| 27 | F6 | `frontend-dashboard-student.md` [a/b] | Student area: learn, exam, chat, calendar, profile | ☐ | — |
| 28 | F7 | `frontend-teacher.md` [a/b] | Teacher area: create-class, classes, students, analytics | ☐ | — |
| 29 | F8 | `frontend-org.md` | Org manager area + workspace switcher | ☐ | — |
| 30 | F9 | `frontend-admin.md` | Admin area (13 routes) | ☐ | — |
| 31 | F10 | `frontend-marketing.md` | Landing (thin index) | ☐ | — |
| 32 | F11 | `frontend-shared-ui.md` | ui/ primitives + shared/layout/content components | ☐ | — |
| 33 | I1 | `infra-deploy.md` | Docker/compose/k8s/Hamravesh rebuild matrix | ☐ | — |
| 34 | I2 | `infra-testing.md` | pytest layout, markers, sqlite fallback, frontend gates | ☐ | — |
| 35 | AUDIT | — | Final coverage pass: 8-point gate across the whole tree | ☐ | — |

## Coverage ledger
- Total steps: 35 · Verified: 19 · Drafting: 0 · Not started: 16
- Stale (Last-verified > 60 days): none
