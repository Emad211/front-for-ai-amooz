# Reference — `apps/classes` teacher views (pipeline control + roster + analytics)

- **Status:** Verified · **Created:** 2026-07-02 · **Last-verified:** 2026-07-12 (working tree)
- **Owner (doc):** technical-writer · **Spec source:** `docs/reference/ROADMAP.md` step B5
- **Layer:** backend-app (teacher-facing slice of the classes god view)

## Purpose
The teacher's control surface over class-creation: trigger the 5 pipeline steps, list/inspect/publish/
cancel sessions, manage invitations + announcements, view the real student roster, and read teacher
analytics. Documents the **view→task dispatch boundary** only — LLM step bodies are L5-L10.

## Scope & paths
| File | Role |
|---|---|
| `apps/classes/views.py` ~L446–1520 (grep-targeted slice of the 5199-line god file) | teacher view classes |
| `apps/classes/urls.py` | route table (below) |
| `apps/classes/services/{progress,sync_structure,background}.py` | supporting logic |

**Out of scope:** student-facing views → B6; exam-prep views → B7; LLM step bodies → L5-L10;
model shapes → B4.

## Public surface (`/api/classes/…`, all `[IsAuthenticated, IsTeacherUser]`)
| Route | View (`views.py:line`) | Role |
|---|---|---|
| `POST creation-sessions/step-1/` … `step-5/` | Step1Transcribe `:446` (FormParser/MultiPart) … Step5Recap `:853` | trigger each pipeline step |
| `GET creation-sessions/` | ClassCreationSessionList `:923` | teacher's sessions |
| `GET creation-sessions/<id>/` | ClassCreationSessionDetail `:961` | one session (status, structure) |
| `POST …/<id>/publish/` | ClassCreationSessionPublish `:1095` | publish → SMS dispatch |
| `POST …/<id>/cancel/` | ClassCreationSessionCancel `:1065` | **owner-only cancel** (404 if not owner, 409 if not active) |
| `GET …/<id>/prerequisites/` | ClassPrerequisiteList | generated prereqs |
| `GET/POST …/<id>/invites/` (+`/<invite_id>/`) | ClassInvitationListCreate `:1143` | phone invites |
| `GET …/<id>/students/` | ClassSessionStudents `:1244` | **resolved roster** (name, progress, score, status) |
| `GET/POST …/<id>/announcements/` (+`/<id>/`) | ClassAnnouncementListCreate `:1343` | announcements |
| `GET teacher/analytics/{stats,chart,distribution,activities,export-csv}/` | TeacherAnalytics* `:1433`+ | teacher analytics (Tehran-tz) |
| `GET teacher/students/` | TeacherStudentsList `:1473` | all the teacher's students |

## Key flows
1. **Pipeline trigger:** `Step1TranscribeView` (`:446`) accepts the upload (FormParser/MultiPartMax
   `TRANSCRIPTION_MAX_UPLOAD_MB`), creates a `ClassCreationSession`, and dispatches the pipeline task
   (async when `CLASS_PIPELINE_ASYNC`). Steps 2-5 advance an existing session. The view's job ends at
   **dispatch** — the task body is L4/L5-L7.
2. **Cancel** (`ClassCreationSessionCancelView:1065`): owner-scoped query (`teacher=request.user`,
   `pipeline_type=CLASS`) → 404 if none → 409 if `not is_active_pipeline` → `_cancel_session_pipeline`
   (sets `cancel_requested` + hard-revokes `celery_task_id`; the cooperative side is L4).
3. **Publish** (`:1095`): flips `is_published`, which unlocks student invite-login and dispatches
   `send_publish_sms_task` / `send_new_invites_sms_task` on the `default` queue.
4. **Roster** (`ClassSessionStudents`): unlike raw `invites/`, resolves actual enrolled students +
   their progress/score/status (joins Enrollment + StudentUnitProgress). A student is a distinct invited
   phone; the teacher's own phone is excluded consistently from class counts and teacher-wide rosters.
5. **Analytics:** the dashboard total is the all-time teacher-wide distinct roster. The activity chart
   counts a phone only on its first invitation, while the class distribution is class-only and counts
   distinct invited phones per class. Therefore the total roster and any one class roster have different
   scopes, but every surface for the same class uses the same count.

## Data & invariants
- Every teacher endpoint is `[IsAuthenticated, IsTeacherUser]`; owner-scoping is done in the queryset
  (`teacher=request.user`) — the deny-by-default + object-ownership rule.
- Cancel is owner-only and returns 404 (not 403) for a non-owner (avoids leaking existence).
- The view layer only DISPATCHES pipeline work; it must not inline LLM calls (services/tasks own those).
- Analytics buckets are **Asia/Tehran** (the analytics rule — B9/memory `admin-analytics`).
- A student added to multiple classes is still one teacher-wide student and one chart event; it appears
  once in each relevant class roster.
- SMS goes on the `default` queue; publish/invite are the dispatch points.

## Gotchas
- `views.py` is 5199 lines — this slice is ~L446–1520; grep by class name, never read whole.
- `cancel` filters on `pipeline_type=CLASS` so it can't cancel an exam-prep session by id (that's B7's
  separate endpoint).
- Step-1 is the only multipart/upload view; steps 2-5 are JSON.

## Cross-links
[backend-classes-models.md](backend-classes-models.md) (B4, session/invite/announcement models) ·
[llm-pipeline-orchestration.md](llm-pipeline-orchestration.md) (L4, what dispatch triggers) ·
[backend-classes-student-views.md] (B6) · [backend-classes-exam-prep.md] (B7) · B9 (analytics detail) ·
memory: `pipeline-cancellation`, `admin-analytics`, `chunked-transcription-500mb`.

## Verified-by
- Read (2026-07-02): `urls.py` (128), `views.py:1065-1093` (cancel — owner scoping + 404/409).
- Re-verified (2026-07-12): `views.py` teacher roster/analytics queries and
  `serializers.py` `invites_count` fallbacks; regression coverage in
  `test_teacher_students.py` covers own-phone exclusion, class/list/detail agreement, first-invite
  charting, and class-only distribution.
- `rg "^class …View" + -A3 views.py` → confirmed the teacher view classes + their
  `[IsAuthenticated, IsTeacherUser]` permission and line numbers cited above.
- NOT read whole: `views.py` (5199 lines — only the teacher slice + cancel body). NOT verified live:
  pipeline dispatch/SMS (Avalai/Mediana VPN-blocked; guarded by `pipeline-cancellation` tests).
