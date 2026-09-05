# Grade 9 shared exam: make the demo visible in production

- **Status:** Living · **Created:** 2026-09-05 · **Last-verified:** 2026-09-05 · **Owner:** devops-engineer (with engineering)

Follows the feature spec at `docs/features/grade9-shared-exam-mvp.md` and the release note at `docs/releases/2026-09-03-grade9-shared-exam-mvp.md`.

## 1. Goal and the content rule

The goal is one published grade 9 Exam Prep demo in the production deployment, with 120 real questions and ten demo students who each have a finalized result.

The exam CONTENT (120 questions, images, teacher solutions, and generated visuals) must be produced by the production OCR pipeline from the merged PDF `allexamdata.pdf` (40 pages, 120 questions merged). Do that by uploading the PDF through the real Exam Prep intake (teacher UI, or the equivalent HTTP intake request below). The production pipeline writes the source file and all visuals into the production object storage (MinIO/S3 private storage), and live OCR is an owner-run deployment action, never a dev/CI action (see `AGENTS.md`, "Deliberate behavior" and the live-LLM rule). A local exam JSON transferred by hand is not a substitute in production: the seeded `--from-exam-json` mode exists for deterministic dev/CI only, and a JSON-only session has no visuals or stored assets.

All commands below must run where the file storage matches the production worker storage: inside the backend container (or equivalent production app process) that shares the production database, Redis, and object storage configuration. Running them from a laptop pointed at the production API does not place result or roster files where the production process can read them.

## 2. Production flow map (only real symbols from this branch)

The three operator verbs "ingest PDF", "publish session", and "import results" each have a management command twin on branch `feat/grade9-shared-exam-mvp`, plus the HTTP/UI mechanism they mirror:

| Step | Operator management command (this branch) | HTTP/UI mechanism it mirrors | Where defined |
|---|---|---|---|
| 1. Ingest the merged PDF | `python manage.py ingest_exam_prep_pdf --pdf <path> --title <title> [--teacher-username grade9_demo_teacher]` — creates/reuses the `EXAM_PREP` session (`source_type=pdf`, status `exam_transcribing`) and dispatches the OCR task on queue `pipeline`; never runs OCR synchronously. Idempotent per `client_request_id` derived from the PDF sha256. | `POST /api/classes/exam-prep-sessions/step-1/` (frontend `transcribeExamPrepStep1`, `frontend/src/components/teacher/create-class/create-class-page.tsx`) | `backend/apps/classes/management/commands/ingest_exam_prep_pdf.py`; mirror view `ExamPrepPdfStep1View` in `views_exam_prep.py` (aliased `ExamPrepStep1IntakeView`) |
| 2. OCR pipeline | Celery task `process_exam_prep_pdf_session` on queue `pipeline` runs the production facade `run_exam_prep_mistral_pipeline` and writes `exam_prep_json` with final status `exam_structured` when publishable. | same task | `backend/apps/classes/tasks_exam_prep.py` |
| 3. Wait for structure | Poll the session (see 4.3) until `status == exam_structured`. | `GET /api/classes/exam-prep-sessions/<session_id>/` (frontend `fetchExamPrepSession`) | `PageFirstExamPrepSessionDetailView`, `core/urls.py` |
| 4. Publish | `python manage.py publish_exam_prep_session --session-id <id>` — requires `exam_structured`, sets `is_published=True` + `published_at`, never sends SMS, and reports the parsed question count. Rejects if already published. | `POST /api/classes/exam-prep-sessions/<session_id>/publish/` (frontend `publishExamPrepSession`; HTTP publish is idempotent, the command is not) | `backend/apps/classes/management/commands/publish_exam_prep_session.py`; mirror `ExamPrepSessionPublishView`, `views.py` (~line 3938) |
| 5. Attach ten students | `python manage.py seed_grade9_exam_mvp --session-id <session_id>` | n/a (operator command) | `backend/apps/classes/management/commands/seed_grade9_exam_mvp.py` |
| 6. Record results | `python manage.py import_grade9_exam_results --session-id <id> --results-json <real export> [--roster-json <path>] [--dry-run] [--force]` — reads the real external array/BOM file directly, maps each `q_no` to the session `question_id`, converts `white`/`"0"` to unanswered, and delegates to `import_exam_prep_results`. | n/a (operator command) | `backend/apps/classes/management/commands/import_grade9_exam_results.py` |

All six steps also have their web/HTTP equivalent where the UI is preferred; the management commands exist so an operator can run the exact same flow headlessly inside the backend container. Management commands such as `extract_exam_prep_source_first` or `smoke_exam_prep_v4_avalai_ocr` run live OCR only into diagnostic bundles or smoke output; they do not create or advance a UI-visible session, so they are not a substitute for step 1.

Session statuses on this branch (`backend/apps/classes/models.py`, `ClassCreationSession.Status`): `exam_transcribing`, `exam_transcribed`, `exam_structuring`, `exam_structured`, plus terminal `failed` and `cancelled`.

## 3. Prerequisites (operator checklist)

1. This branch is deployed to production (frontend and backend), and `python manage.py migrate` has run. The MVP release itself adds no migration (`docs/releases/2026-09-03-grade9-shared-exam-mvp.md`).
2. A Celery worker consumes the `pipeline` queue. Without it the session stays in `exam_transcribing` because the intake dispatch never runs. Example worker command:
   ```bash
   celery -A core worker --loglevel=info -Q default,pipeline --concurrency=2
   ```
   (The `interactive` queue exists for a dedicated worker and is not needed for this flow.)
3. The Avalai gateway is configured in the production backend environment. Live OCR fails without a key. Verified env knobs (no values printed here):
   - `AVALAI_API_KEY` (required for live OCR; the OCR transport raises when missing)
   - `AVALAI_BASE_URL` (default `https://api.avalai.ir/v1`)
   - `AVALAI_OCR_ENDPOINT` (default `https://api.avalai.ir/v1/ocr`)
   - `EXAM_PREP_MISTRAL_OCR_MODEL` (default `mistral-ocr-4-0`)
   - `EXAM_PREP_TOTAL_PDF_BUDGET_USD` (default `1.50`)
4. Backend, pipeline worker, and management command runs share the same database, Redis, and private object storage (MinIO/S3).
5. Real input files are available to the production process:
   - `allexamdata.pdf` (merged source PDF, 40 pages, 120 questions)
   - `exam-result.json` (external results export; see section 6)
   In this repo the demo inputs live under `tmp/grade9-mvp-input/`. Copy them to a path the backend container can read, for example:
   ```bash
   docker compose cp tmp/grade9-mvp-input/allexamdata.pdf backend:/tmp/grade9/allexamdata.pdf
   docker compose cp tmp/grade9-mvp-input/exam-result.json backend:/tmp/grade9/exam-result.json
   ```
   Adjust the compose service name to the production deployment.

## 4. Exact sequence

### 4.1 Make sure the demo teacher exists

Upload and publish run under a teacher account. Create the deterministic demo teacher exactly as the seed command does (same username, role, email, password assignment), so later steps and student logins stay consistent:

```bash
docker compose exec backend python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
teacher, created = User.objects.get_or_create(
    username='grade9_demo_teacher',
    defaults={'role': User.Role.TEACHER, 'email': 'grade9-demo-teacher@example.com'},
)
if created or not teacher.has_usable_password():
    teacher.set_password('grade9-teacher-123')
teacher.role = User.Role.TEACHER
teacher.save()
print('teacher ok', teacher.username)
"
```

Alternatively use any existing production teacher account for steps 4.2 to 4.4. `seed_grade9_exam_mvp --session-id` only requires a published `EXAM_PREP` session, not that the demo teacher owns it.

### 4.2 Ingest `allexamdata.pdf`

Operator command (runs inside the backend container so `source_file` storage matches the worker; create the deterministic demo teacher first in 4.1):

```bash
docker compose exec backend python manage.py ingest_exam_prep_pdf \
  --pdf /tmp/grade9/allexamdata.pdf \
  --title "Grade 9 Exam Prep Demo" \
  --teacher-username grade9_demo_teacher
```

Expected output: `Queued exam-prep session <SESSION_ID> (title: Grade 9 Exam Prep Demo).` Record the session id as `<SESSION_ID>`. Re-running the same command with the same PDF reuses the same session and does not re-dispatch the OCR task.

Alternative (identical intake request the UI sends): log in to the production Exam Prep UI as the demo teacher and upload `allexamdata.pdf` in the exam creation flow:

```bash
# Get a teacher access token (demo password is the deterministic default above).
TOKEN=$(curl -s -X POST "$API_BASE/api/token/" \
  -H 'Content-Type: application/json' \
  -d '{"username":"grade9_demo_teacher","password":"grade9-teacher-123"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access'])")

curl -s -X POST "$API_BASE/api/classes/exam-prep-sessions/step-1/" \
  -H "Authorization: Bearer $TOKEN" \
  -F "title=Grade 9 Exam Prep Demo" \
  -F "file=@allexamdata.pdf"
```

Expected: a response containing the new session `id` (the UI reads `result.id` after the same call) and a status of `exam_transcribing`. The worker writes workflow state with the message `PDF در صف پردازش قرار گرفت.`. Record the session id as `<SESSION_ID>`.

If the file is not a valid PDF the intake answers `برای آمادگی آزمون یک فایل PDF معتبر بارگذاری کنید.`. More than five concurrently active exam sessions return `حداکثر ۵ آزمون همزمان در حال پردازش است.`.

### 4.3 Wait until the session reaches `exam_structured`

The teacher UI polls automatically. To watch from a shell inside the backend container:

```bash
docker compose exec backend python manage.py shell -c "
import time
from apps.classes.models import ClassCreationSession
session_id = <SESSION_ID>
for _ in range(180):
    s = ClassCreationSession.objects.get(pk=session_id)
    print(s.status, s.is_published)
    if s.status in ('exam_structured', 'failed', 'cancelled'):
        break
    time.sleep(10)
"
```

Expected end state: `exam_structured`. If it ends in `failed` or `cancelled`, inspect backend/worker logs for that session and Celery task id (`session.celery_task_id`), fix the underlying cause, and start a fresh session with the same PDF. Content questions exist in `exam_prep_json` once the task writes it; `exam_structured` is the state at which publish is allowed (publish rejects other states with the message `فقط جلسه‌های با وضعیت exam_structured قابل انتشار هستند. وضعیت فعلی: <status>`).

### 4.4 Publish the session

Operator command (requires `exam_structured`; prints the parsed question count):

```bash
docker compose exec backend python manage.py publish_exam_prep_session --session-id <SESSION_ID>
```

Expected output: `Published Exam Prep session <SESSION_ID> with 120 question(s).` The command rejects a session that is not `exam_structured`, has no questions in `exam_prep_json`, or is already published.

Alternative (the same request the UI sends via `publishExamPrepSession`; HTTP publish is idempotent):

```bash
curl -s -X POST "$API_BASE/api/classes/exam-prep-sessions/<SESSION_ID>/publish/" \
  -H "Authorization: Bearer $TOKEN"
```

Expected: HTTP 200 with the session detail, `is_published: true`. Publish is idempotent; publishing an already published session returns the same detail.

Conditional blocking responses that can appear when the pipeline audit flags items (all real responses from `ExamPrepSessionPublishView`):

- HTTP 409 `code: extraction_review_required`, Persian message `پیش از انتشار، خطاهای بحرانی استخراج را در بخش بازبینی برطرف کنید.`
- HTTP 409 `code: visual_approval_required`, Persian message `نسخه بازطراحی‌شده تصویر باید پیش از انتشار توسط معلم تأیید شود.`
- HTTP 409 `code: teacher_extraction_confirmation_required`, Persian message `پیش از انتشار، بازبینی نهایی استخراج را تأیید کنید.`

When one of these appears, resolve the item in the Exam Prep review UI for the session (review actions exist for retry and for confirm, for example `confirmExamPrepExtractionReview` posts to `/extraction-review/confirm/`), then repeat the publish request. Expected final state: `is_published: true`.

Note: when a question is OCR-flawed (missing options, inline-option text, or an image-heavy stem/option/solution that extraction could not transcribe), the teacher can repair it by hand before publishing. Open the session's edit page (`/teacher/my-exams/<SESSION_ID>/edit`) and use the **افزودن تصویر به سؤال** control on the affected question card to attach the correct image to the question stem, to a specific option, or to the solution (PNG/JPG/WebP, ≤ 5 MB). Teacher-uploaded visuals are stored under the same private storage family as OCR assets, render through the protected visual path, and never expose a storage path. This feature (added on this branch) is documented under `docs/features/grade9-shared-exam-mvp.md`, "Teacher visual repair".

### 4.5 Attach the ten demo students

Create one roster file from the export **row order** so names, phones, and result import stay aligned (row 1 of the export ↔ `grade9_student_01` ↔ `09129090001`, and so on). The names in the export are real student names; use them as `name` in the roster. Example shell that writes `/tmp/grade9/roster.json` inside the backend container from the export order:

```bash
docker compose exec backend python manage.py shell -c "
import json
rows = json.loads(open('/tmp/grade9/exam-result.json', encoding='utf-8-sig').read())
roster = []
for i, r in enumerate(rows, start=1):
    roster.append({
        'name': (str(r.get('first_name') or '') + ' ' + str(r.get('last_name') or '')).strip(),
        'phone': '091290900%02d' % i,
        'password': 'grade9-demo-123',
    })
open('/tmp/grade9/roster.json', 'w', encoding='utf-8').write(json.dumps(roster, ensure_ascii=False))
print('roster rows', len(roster))
"
```

Then run the seed command inside the backend container with that roster:

```bash
docker compose exec backend python manage.py seed_grade9_exam_mvp \
  --session-id <SESSION_ID> \
  --students-file /tmp/grade9/roster.json
```

Expected output ends with a success line and a tab-separated credential table:

```text
Seeded shared grade-9 exam: session <SESSION_ID> (Grade 9 Exam Prep Demo)
username        phone           password        invite_code
grade9_student_01       09129090001     grade9-demo-123  INV-...
... (10 rows)
```

The roster is deterministic: `grade9_student_01` to `grade9_student_10`, phones `09129090001` to `09129090010`. Those demo phones are intentionally used in production per the owner decision. The command creates student accounts and `ClassInvitation` rows without sending SMS. Re-running is idempotent and preserves credentials.

Errors to expect if the command is misused:

- `Exam Prep session <id> was not found.`
- `--session-id must refer to a published EXAM_PREP session.`
- `The grade-9 demo requires exactly ten students with unique phones.` (when a roster of the wrong size is passed)

### 4.6 Import the finalized results

The dedicated operator command `import_grade9_exam_results` reads the real external export directly and performs the mapping for you, so no manual adaptation script is needed. Pass the same roster file you used for seeding so identity stays aligned:

```bash
docker compose exec backend python manage.py import_grade9_exam_results \
  --session-id <SESSION_ID> \
  --results-json /tmp/grade9/exam-result.json \
  --roster-json /tmp/grade9/roster.json \
  --dry-run
```

What the command does with the real file (`tmp/grade9-mvp-input/exam-result.json`):

- Reads the export with `utf-8-sig` decoding, so the UTF-8 BOM is handled (the raw file starts with a BOM).
- Accepts the top-level array of student records (`counter`, `first_name`, `test_date`, `last_name`, `group`, `courses`) with no phone field; phone identity comes from the roster.
- Default roster maps the ten export array positions to the seeded demo phones `09129090001` ... `09129090010`. Use `--roster-json <path>` to override (array or `{"students": [...]}` of `name`/`phone`/`password`); the command requires exactly ten unique, valid Iranian mobile numbers and rejects a roster whose phone count differs from the export's student count.
- Maps each external `q_no` to the published session's `question_id` from `exam_prep_json` (accepted when the question id ends with `-<q_no>` or its `source_question_number` equals `q_no`), and errors on any unknown or ambiguous number.
- Converts `result: white` and any `answer: "0"` to unanswered (no record is emitted for that question).
- Keeps `correct` and `wrong` as answered statuses. When the export carries an option label (`"1"`..`"4"`), the label is stored as the selected answer; the underlying service still validates status/answer consistency against the session's `correct_option_label`.
- Delegates to `import_exam_prep_results` for the atomic, finalized attempt write and the full published-question-set score denominator.

Expected dry-run output:

```text
created\t09129090001
created\t09129090002
...
Dry run validated 10 result(s) across <N> question(s).
```

Nothing is written in dry-run mode. Then import for real:

```bash
docker compose exec backend python manage.py import_grade9_exam_results \
  --session-id <SESSION_ID> \
  --results-json /tmp/grade9/exam-result.json \
  --roster-json /tmp/grade9/roster.json
```

Expected: `Imported 10 result(s) across <N> question(s).` The import is atomic and finalizes one attempt per student with `correct_count`, `total_questions`, and `score_0_100` over the full published question set.

Meaningful importer errors (all real):

- `Could not read JSON file <path>: ...` when the file is missing or malformed.
- `Roster has <n> phone(s) but the results file has <m> student(s).` when counts differ.
- `unknown question numbers: <q_no...>` when an export question cannot be mapped to the published session.
- `student <phone> is not invited` or `invited student <phone> has no account` for an identity that does not match the seeded roster.
- `conflicting attempt for student <phone>` when a student already has an attempt (re-import with `--force` to replace).

Lower-level variant (same underlying service, raw adapter payload expected): `import_exam_prep_results --session-id <SESSION_ID> --results-json <adapted payload file>` — use it only when you already have an adapter-shaped payload and want the raw service behavior.

## 5. Verification

Run the student-facing check in the production frontend:

1. Log in at the login page as `grade9_student_01` (password `grade9-demo-123`; the seed output prints it). Login posts to `POST /api/token/`.
2. Open the student exam list (`/exam-prep`). The published grade 9 session appears because the student phone has a `ClassInvitation` for a published `EXAM_PREP` session.
3. Open the exam, then its result page (`/exam/<SESSION_ID>/result`, the route rendered by `frontend/src/app/(dashboard)/exam/[examId]/result/page.tsx`).
4. On the result page check the section `جزئیات پاسخ‌ها`. Confirm the score, the correct count, and the total question count match the imported values for this student.
5. The filter starts on **all**. Switch to the wrong-answer filter using the `پاسخ‌های غلط` button (default view button is `همه`). Confirm it lists only answered items whose answer is not correct, and that the filter hides unanswered items. If there are no wrong answers the page shows `پاسخ غلطی برای نمایش وجود ندارد.`
6. Repeat for a second student (for example `grade9_student_05`) and confirm the imported values differ as the export predicts.

## 6. Rollback

Replace an existing result set without touching accounts (re-import with `--force`):

```bash
docker compose exec backend python manage.py import_grade9_exam_results \
  --session-id <SESSION_ID> \
  --results-json /tmp/grade9/exam-result.json \
  --force
```

To clear imported results entirely before re-importing (for example to fix the adaptation), delete the attempts first:

```bash
docker compose exec backend python manage.py shell -c "
from apps.classes.models import ClassCreationSession, StudentExamPrepAttempt
s = ClassCreationSession.objects.get(pk=<SESSION_ID>)
deleted, _ = StudentExamPrepAttempt.objects.filter(session=s).delete()
print('deleted attempts', deleted)
"
```

To tear down the whole demo (session, invitations, demo users), scope strictly to the demo data:

```bash
docker compose exec backend python manage.py shell -c "
from apps.accounts.models import User
from apps.classes.models import ClassCreationSession, ClassInvitation, StudentExamPrepAttempt
s = ClassCreationSession.objects.get(pk=<SESSION_ID>)
StudentExamPrepAttempt.objects.filter(session=s).delete()
ClassInvitation.objects.filter(session=s).delete()
s.delete()
User.objects.filter(username__startswith='grade9_student_').delete()
User.objects.filter(username='grade9_demo_teacher').delete()
"
```

`ClassInvitation` cascades from the session (`on_delete=CASCADE`), so the explicit delete is belt and braces. Permanent `StudentInviteCode` rows per phone remain reusable by `get_or_create`; delete them too only if a pristine reset is required:

```bash
docker compose exec backend python manage.py shell -c "
from apps.classes.models import StudentInviteCode
phones = ['091290900%02d' % i for i in range(1, 11)]
print('deleted codes', StudentInviteCode.objects.filter(phone__in=phones).delete())
"
```

After a full teardown, re-run sections 4.1 through 4.6 to recreate the demo.

## 7. Verification checklist

- [ ] The session reached `exam_structured` (not `failed`/`cancelled`) after the PDF upload.
- [ ] Publish succeeded (`publish_exam_prep_session` printed the question count, or HTTP publish returned `is_published: true`).
- [ ] `seed_grade9_exam_mvp --session-id <SESSION_ID>` printed 10 students with phones `09129090001` to `09129090010`.
- [ ] `import_grade9_exam_results --dry-run` reported `Dry run validated 10 result(s) across <N> question(s).`
- [ ] `import_grade9_exam_results` reported `Imported 10 result(s) across <N> question(s).`
- [ ] Logging in as `grade9_student_01` and opening `/exam/<SESSION_ID>/result` shows the score, `همه` view, and `پاسخ‌های غلط` filter with correct counts.
- [ ] The wrong-answer filter hides unanswered items and, when empty, shows `پاسخ غلطی برای نمایش وجود ندارد.`
