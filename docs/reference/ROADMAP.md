# Reference documentation program — per-step specs (council 2026-07-02)

- **Status:** Living · **Created:** 2026-07-02 · **Owner:** tech-lead (chair) + technical-writer
- Decision record: [ADR-0002](../adr/ADR-0002-reference-docs-program.md) · Progress checklist: [README.md](README.md)

This file is the program's brain: the condensed spec each loop step follows. Written by the 5-member
council (tech-lead chair; technical-writer, backend-engineer, frontend-engineer, ai-engineer). Each step
= ONE doc following [TEMPLATE.md](TEMPLATE.md). Rules for every step: grep-targeted reads (god files
`classes/views.py` 5199 / `commons/views.py` 1829 / `organizations/views.py` 1042 — NEVER read whole);
every claim gets a `Verified-by` entry; link CLAUDE.md/ADRs/features instead of restating; the user's
machine-local memory files are cited for history only — durable contracts (env knobs, output keys,
guards) are restated in-repo. Steps marked **[a/b]** may split into two iterations, each shipping a
coherent doc.

## S1 — `00-architecture-overview.md` (system map)
Scope: whole repo. Capture: monorepo layout; the verified `/api/*` routing table (`core/urls.py:94-128`);
app inventory incl. the resolved facts — `authentication`/`chatbot`/`material` ARE in INSTALLED_APPS
(`settings.py:57,62,63`); chatbot = service-only (hosts `llm_client.py` god node, no HTTP surface);
`material` empty; the two pipelines at a glance; frontend route-group map; the frozen-contracts list.

## B0 — `backend-core.md` (core/ project package)
Scope: `backend/core/*` + `apps/core/` (health 71, permissions, throttling). Capture: INSTALLED_APPS +
routing table; `AUTH_USER_MODEL='accounts.User'`; DRF defaults (deny-by-default, `SafeScopedRateThrottle`
+ every scoped rate incl. `onboarding` 20/hour); exception-handler error envelope (link
`apps/core/test_error_contract.py`); storage gate on `AWS_STORAGE_BUCKET_NAME` + `/media/<path>` proxy;
env-var catalogue; throttle auto-disable in tests (`backend/conftest.py`).

## B1 — `backend-accounts.md` (identity & user model)
Scope: `apps/accounts/{models,serializers,views,urls}.py` (85/330/78/8) + 7 migrations +
`commons/phone_utils.py` + `accounts/services.py`. Capture: 4 roles + profile inheritance; **phone =
unique student identity** (`normalize_phone`, atomic `get_or_create_user_by_phone`, partial constraint
`uniq_student_phone`); `is_profile_completed`; endpoints table; migration lineage 0001→0007 (the 0006
non-admin wipe + the canonical **DML/DDL split** precedent 0006/0007). Link memory
`onboarding-and-user-uniqueness` for history.

## B2 — `backend-authentication.md` (JWT/OTP/login layer)
Scope: `apps/authentication/{views(371),serializers(275),otp_service,cookies,openapi,urls}.py`
(0 migrations — operates on accounts models). Capture: SimpleJWT flow (lifetimes, refresh rotation,
cookies); OTP service; code-login rules (unusable password + `is_profile_completed=False`; completed
accounts blocked from code re-entry → 400); `/api/token/*` + `/api/auth/*` endpoint table; throttle
scopes; canonical negative tests (test_security, test_token_rotation, test_invite_login).

## B3 — `backend-organizations.md` + `backend-waitlist.md` [a/b]
Scope: `apps/organizations/{models(423),serializers(340),views(1042 — slice by viewset),urls}.py` + 10
migrations; `apps/waitlist/` (104/126/202/21 + 1 mig); `classes/services/{invite_codes,org_roster}.py`.
Capture: tenancy model (Organization, Membership, InvitationCode, StudyGroup×3); MANAGER grant via
admin/deputy redemption; `is_freelancer`; manager = oversight-only; org roster = study group sync (free
invite → 403); waitlist approval gate (no account until approved; org approval auto-creates org+code;
SMS-only); tenant-boundary rules. Consult security-auditor claims. Link memory
`org-teacher-dashboard-rework`, `waitlist-feature`, `manager-role-on-main`.

## L1 — `llm-provider-client.md` (provider & client foundation)
Scope: `apps/chatbot/services/llm_client.py`; `apps/commons/llm_provider.py`; env consumers. Capture:
`gemini|avalai|auto` selector + legacy `MODE=avalai` prod alias; `_normalize_base_url` `/v1`-append rule;
the env→model matrix (`MODEL_NAME`, `TRANSCRIPTION_MODEL`, `IMAGE_MODEL`, `EMBEDDING_MODEL_NAME` — none
hardcoded); `generate_text`/`generate_json` signatures; **local code default `gapgpt.app` vs prod
`api.avalai.ir`** distinction. LINKS to `AvalAI-Developer-Documentation.md` for gateway limits.

## L2 — `llm-structured-output.md`
Scope: `commons/{structured_llm,json_utils}.py`, `classes/services/{json_utils,schemas}.py`. Capture:
never raw `extract_json_object`+silent-`{}`; `generate_structured` (JSON-mode → validate → one repair →
**raises**) vs `validate_keep_dict` (structure.py); `parse_structured`/`validate_obj`;
response_format-unsupported fallback; schema→stage map; the **pending** `generate_structured` migration
for recap/prereqs/quizzes/exam_prep_structure (deferred: VPN-untestable).

## L3 — `llm-prompts-contract.md` (HUB doc)
Scope: `commons/llm_prompts/prompts.py` + `classes/test_prompts_contract.py`. Capture: the **26 live
keys** (`LIVE_KEYS` at test:39) with strategies (`section_quiz`/`final_exam_pool` = [default, adaptive];
`transcribe_media` = [default, chunked]), each key's PLACEHOLDERS + OUTPUT_KEYS (mirror the test — the
test is the source of truth, the doc cites it); `str.replace` never `str.format`; shared blocks
(SAFETY_PREAMBLE, AUDIENCE_ADAPTIVE, MCQ_QUALITY, MATH_FORMAT_INSTRUCTIONS) edit-in-one-place; dead-key
policy; mandatory contract-test gate after any edit.

## B4 — `backend-classes-models.md` (classes data model)
Scope: `classes/{models(579),serializers(673),permissions(27)}.py` + 23 migrations. Capture: full ER map
(session → sections/units → quizzes/exam → attempts → progress, 17 models); status state-machine incl.
CANCELLED + `cancel_requested` + `celery_task_id`; JSON-field contracts (`questions`, `exam`,
`result['per_question']`) — field semantics here, generation contract in L8; constraints/indexes;
migration lineage (renumber precedent 0022). Consult database-engineer.

## L4 — `llm-pipeline-orchestration.md` (HUB doc)
Scope: `classes/tasks.py` (1101) — orchestration only. Capture: step→status state machine (class:
TRANSCRIBING→…→RECAPPED; exam-prep: EXAM_TRANSCRIBING→EXAM_STRUCTURED); the two full-pipeline chainers
(status-guarded, resumable, `max_retries=0`; step tasks `max_retries=3`, `acks_late=True`);
`_check_cancelled` cooperative checkpoints + hard revoke → CANCELLED; `_make_step1_heartbeat` (bumps
`updated_at` vs `cleanup_stale_sessions`; abort → `TranscriptionAborted`, never retried);
`_ingest_source_to_markdown`; `_attribute_llm_usage_to_teacher`; pipeline vs default queue. Seam: view →
task dispatch belongs to B5/B7; task bodies' LLM logic to L5–L9.

## B5 — `backend-classes-teacher-views.md`
Scope: `classes/views.py` ~L446–1791 (grep-targeted) + `urls.py`; `services/{progress,sync_structure,
background}.py`. Capture: step1–5 trigger views, session list/detail/cancel/publish (owner-only; cancel
sets `cancel_requested` + revokes), invitations, announcements, TeacherAnalytics* shapes; the view→task
dispatch boundary (bodies → L4+). Link memory `pipeline-cancellation`, `admin-analytics`.

## B6 — `backend-classes-student-views.md`
Scope: `classes/views.py` ~L1791–3400 + `urls.py`; `services/{student_chat_history,markdown_assets}.py`.
Capture: student course list/content, lesson-complete, PDF export, course chat (+media), chapter quiz +
final exam submit/regenerate; **the adaptive regenerate guard** (409 unless `last_passed is False`; 400
if none; resets `last_passed`/`last_score` = rate-limiter); **answer-reveal-on-submit contract**
(`correct_answer`/`explanation` in POST per_question; hidden on GET); pregeneration dispatch
(`cache.add`). Consult frontend widget shapes. Link memory `adaptive-quiz-loop`.

## B7 — `backend-classes-exam-prep.md`
Scope: `classes/views.py` ~L3400–5199 + `urls.py`; `services/{exam_prep_utils (non-LLM),
student_exam_chat_history}.py`. Capture: exam-prep session CRUD/cancel/publish; student
list/detail/submit/check-answer/chat/result/reset/history/media; dispatch boundary to
`process_exam_prep_*`.

## L5 — `llm-transcription.md`
Scope: `services/{transcription,transcription_media,media_compressor}.py`; `text_sanitize`. Capture:
standard multimodal shapes (`input_audio`, `image_url`) + the silently-ignored legacy `attachments` trap;
chunked design (ffmpeg `-f segment` → sequential mono-mp3; per-chunk frames + transcript tail; prompt
`transcribe_media.chunked`; `progress_cb` heartbeat; cancel → `TranscriptionAborted`); ~1.5× threshold;
env knobs (`TRANSCRIPTION_CHUNK_SECONDS` 600, `TRANSCRIPTION_FRAMES_PER_CHUNK`, `FRAME_*`,
`TRANSCRIPTION_MAX_DURATION_SECONDS` 4h); never collapse to one request; `transcribe_media_bytes` stays
single-shot; sanitize every chunk. Link memory `chunked-transcription-500mb`, `avalai-multimodal-format`.

## L6 — `llm-structure-stage.md`
Scope: `services/{structure,sync_structure}.py`; prompt `structure_content`. Capture: transcript →
root_object/outline/units JSON (merrill_type, source_markdown verbatim, content_markdown, image_ideas);
why `validate_keep_dict` here; `sync_structure` → DB rows; greedy-fence-regex gotcha (link memory
`pdf-structure-json-bug-fixed`).

## L7 — `llm-prereqs-recap.md`
Scope: `services/{prerequisites,recap}.py`; prompts `prerequisites_prompt`, `prerequisite_teaching`,
`recap_and_notes`. Capture: inputs/outputs per stage (recap tree: by_unit / common_mistakes_markdown /
formula_sheet_markdown); status transitions; pending generate_structured migration; shared-block usage.

## L8 — `llm-quizzes-adaptive.md`
Scope: `services/{quizzes,adaptive_quiz}.py`; prompts `section_quiz.*`, `final_exam_pool.*`, plus
`fetch_quizzes`, `practice_tests`, `flash_cards`, `match_games`, `meril`, `notes_ai`, `text_grading`,
`exam_prep_hint`; `tasks.pregenerate_student_assessments`. Capture: fail→reveal→regenerate loop;
`compute_weak_points_from` (pure; handles `score_0_100`/70 AND `score_points`/`max_points`); adaptive
strategies share default's exact output contract (test-enforced); `last_passed` reset semantics;
MCQ_QUALITY. Consult data-analyst on regeneration cost multiplier. Link memory `adaptive-quiz-loop`.

## L9 — `llm-exam-prep.md`
Scope: `services/{exam_prep_structure,exam_prep_utils}.py`; prompts `exam_prep_structure`,
`exam_prep_hint`, `exam_prep_chat`, `exam_prep_handwriting_vision`. Capture: the standalone 2-step flow;
exam-question JSON contract (question_text_markdown, options, correct_option_label,
teacher_solution_markdown, final_answer_markdown); handwriting-vision call; windowing (shares chunked
infra).

## L10 — `llm-pdf-and-cost.md` [a/b]
Scope (a): `services/{pdf_extraction,pdf_export,pdf_metrics,markdown_assets}.py`; prompt
`pdf_extraction`. Scope (b): `commons/{token_tracker,models(LLMUsageLog/ModelPrice),exchange_rate}.py`;
usage views; `tasks._attribute_llm_usage_to_teacher`. Capture: LLM-only PDF→Markdown path (link memory
`pdf-llm-extraction` for benchmarks); WeasyPrint export; every-call logging via `llm_tracking_context` /
`get_current_session_id` → per-session/teacher/class/feature attribution; `estimate_cost` + USD→Toman;
cost-discipline rules. Consult data-analyst.

## B8 — `backend-celery-ops.md`
Scope: `core/celery.py`, task routes + beat, `tasks.py` inventory (defs only), `services/{mediana_sms
(199),media_compressor(447),pdf_metrics}.py`. Capture: task→queue map; `cleanup_stale_sessions` beat +
heartbeat interplay; time limits (hard 2h/soft 100min, prefetch=1); idempotent dispatch; Mediana SMS
contract + `MEDIANA_API_KEY`; ffmpeg knobs. Seam: task bodies → L-docs.

## B9 — `backend-commons-admin.md` + `backend-notification.md` [a/b]
Scope: `commons/{models(484),views(1829 — slice by admin area),urls(106)}.py` + 5 migs;
`apps/notification/*` + 4 migs. Capture: `/api/admin/*` endpoint table with elevated permissions;
analytics (Tehran-tz rule; link memory `admin-analytics`); LLM usage aggregation views; tickets
(FK is `author` — the `43815ef` fix); AdminSetting; notification models + `/api/notifications/*`.
Consult security-auditor on the admin surface.

## F1 — `frontend-app-shell.md`
Scope: `frontend/src/app/layout.tsx`, `next.config.ts`, route-group tree (61 page/layout files).
Capture: `<html lang="fa" dir="rtl">` + Vazirmatn + providers; full route inventory table per group —
(marketing), (auth)+start/+join/+onboarding/, (dashboard), (teacher), (org), (admin); the `/api` rewrite
+ `skipTrailingSlashRedirect` + `BACKEND_URL || NEXT_PUBLIC_API_URL` rules; `output: standalone`;
`ignoreBuildErrors` ⇒ typecheck+lint are the real gates.

## F2 — `frontend-conventions.md` (theming/RTL/Persian + lib catalog)
Scope: `globals.css` tokens, `theme-provider`, `lib/*` (utils, persian-digits, persian-option-label,
date-utils, normalize-math-text, calendar, auth-routing, classes/course-structure, validations/).
Capture: HSL semantic-token list + phantom-token gotcha; dark/light parity + `hidden dark:block`
pattern; RTL logical utilities + icon flipping; Persian digits + Jalali rules; math rule (body→
`MarkdownWithMath`, titles→`MathText`); the A–Z lib catalog (one-line contract per util) + zod/RHF
multi-step pattern (canonical: `validations/onboarding.ts`). (Absorbs the old F12.)

## F3 — `frontend-services-hooks.md`
Scope: all 9 `services/*.ts` + shared request core (baseRequest/extractError/normalizeApiError) + the
**34 `hooks/use-*.ts`**. Capture: service→endpoint mapping table (fn → verb + `/api/...` + auth); error
normalization → RHF field errors; no-ad-hoc-fetch rule; `NEXT_PUBLIC_API_URL` construction (5 throwing
services vs 2 `/api` fallbacks); hooks-as-data-seam convention.

## F4 — `frontend-auth-guards.md`
Scope: `components/auth/` (auth-auto-redirect, onboarding-gate, login-form, unified-code-form),
`lib/auth-routing.ts`, `lib/validations/{auth,onboarding}.ts`, mount points. Capture: token storage;
role→home routing; onboarding-gate logic + mounts (dashboard/org/teacher — **admin does NOT mount it**,
deliberate); multi-step wizard pattern. Link memory `onboarding-and-user-uniqueness`.

## F5 — `frontend-auth-screens.md`
Scope: `app/(auth)/*` (login, admin-login, org-login, forgot-password, register/complete,
teacher-signup, organization-signup, join-code) + `start/` + `join/` + `onboarding/` pages. Capture:
per-screen purpose · service fns · zod schema · states · Persian copy notes; role picker + invite
redemption flows. Link memory `waitlist-feature`.

## F6 — `frontend-dashboard-student.md` [a/b]
Scope: `app/(dashboard)/*` + `components/dashboard/` (48 files) + hooks (use-course-content, use-exam,
use-courses, use-calendar, use-dashboard-data). Capture: route inventory + guards; learn viewer +
ChatAssistant; adaptive quiz/final-exam widgets (link memory `adaptive-quiz-loop`); calendar; profile;
tickets. Split: (a) learn+exam+chat, (b) home/calendar/profile/notifications/tickets.

## F7 — `frontend-teacher.md` [a/b]
Scope: `app/(teacher)/teacher/*` + `components/teacher/` (48) + teacher sidebar/header + `use-teacher-*`.
Capture: route inventory + nav menus (freelancer vs org variants); create-class pipeline UI + cancel;
class editor; students; messages; analytics charts. Link memory `pipeline-cancellation`,
`teacher-dashboard-and-prompts-audit`.

## F8 — `frontend-org.md`
Scope: `app/(org)/*` + `components/organization/` + `components/layout/workspace-switcher.tsx` +
`hooks/use-workspace.tsx`. Capture: manager oversight-only nav; **the workspace-switcher context**
(org-teacher multi-workspace); AI-cost views; study-group roster. Link memory
`org-teacher-dashboard-rework`, `manager-role-on-main`.

## F9 — `frontend-admin.md`
Scope: `app/(admin)/admin/*` (13 routes) + `components/admin/` (18) + admin sidebar/header +
`use-admin-*`. Capture: ADMIN_NAV_MENU; no onboarding-gate (deliberate); analytics/LLM-usage dashboards
(link memory `admin-analytics`); waitlist review; user management + manager assign/revoke.

## F10 — `frontend-marketing.md`
Scope: `app/(marketing)/page.tsx` + `components/landing/` (11) + landing-service. Capture: thin index —
section inventory, dark hero halo+dot-grid pattern; heavy links to memory `figma-landing-rebuild`. Size S.

## F11 — `frontend-shared-ui.md`
Scope: `components/ui/` (39 shadcn primitives), `components/shared/` (9), `components/layout/` (10),
`components/content/` (2). Capture: stock-vs-customized primitive inventory; layout shell (headers,
sidebars, mobile-nav, user-profile); RTL-audited primitives. Written LAST of frontend (usage informed by
F5–F10).

## I1 — `infra-deploy.md`
Scope: Dockerfiles, compose files, `scripts/dev-*.ps1`, `k8s/`, `nginx/`. Capture: local stack map +
runbook link; prod Hamravesh service map (one backend image for web+worker; front bakes env at build);
rebuild matrix; links CLAUDE.md §Production + `backend/DEPLOY_CHECKLIST.md`; NO secrets.

## I2 — `infra-testing.md`
Scope: `pytest.ini` ×2, `backend/conftest.py`, test layout, markers. Capture: run commands (root vs
backend/), sqlite fallback, `--no-migrations` note, throttle auto-disable, markers (unit/benchmark
opt-in), known pre-existing failures list (canonical home: `.claude/agents/qa-engineer.md` — link),
frontend gates (tsc 0-new / lint).

## AUDIT — final coverage pass
technical-writer's 8-point gate re-applied across the tree: every doc Status=Verified with fresh
Last-verified; cross-links resolve both ways; no duplication vs CLAUDE.md/features/ADRs; `docs/README.md`
+ this README's ledger updated; leftovers become follow-up steps.
