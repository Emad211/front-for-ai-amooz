# 2026-07-07 — Exercise Reference Ingest

## Summary
Adds a teacher-only reference-answer ingest flow for Exercise Hub. Teachers can paste text or upload small PDF/photos containing answer keys or mixed question+answer content, preview the extracted matches, then explicitly apply selected items to existing exercise questions.

## Changes
- New prompt contract: `exercise_reference_ingest/default`.
- New LLM usage feature: `EXERCISE_REFERENCE_INGEST`.
- New no-op choices migration: `commons/0007_exercise_reference_ingest_feature`.
- New teacher endpoints:
  - `POST /api/classes/exercises/<id>/reference-ingest/preview/`
  - `POST /api/classes/exercises/<id>/reference-ingest/apply/`
- Hardened exercise/source uploads with file count, size, PDF magic-byte, and image sniff validation.
- Hardened student answer-image upload so non-draft submissions cannot leave orphan media files.
- Frontend teacher editor now includes a visible review panel for extracted reference answers.

## Config
No secrets are added. Optional env names:
- `EXERCISE_REFERENCE_INGEST_MODEL`
- `EXERCISE_REFERENCE_MAX_FILES`
- `EXERCISE_REFERENCE_MAX_FILE_BYTES`
- `EXERCISE_REFERENCE_MATCH_THRESHOLD`
- `EXERCISE_MAX_SOURCE_FILES`
- `EXERCISE_MAX_SOURCE_FILE_BYTES`
- `EXERCISE_MAX_IMAGES_PER_QUESTION`

## Verification
Run before deploy:
- `DATABASE_URL='sqlite:///test_run.sqlite3' backend/.venv/Scripts/python.exe -m pytest backend/apps/classes/test_exercise_ingest.py backend/apps/classes/test_exercise_teacher_api.py backend/apps/classes/test_exercise_student_api.py backend/apps/classes/test_exercise_grading.py backend/apps/classes/test_prompts_contract.py --no-migrations -p no:cacheprovider -q`
- `cd frontend && npx tsc --noEmit`
- `cd backend && ../backend/.venv/Scripts/python.exe manage.py makemigrations --check --dry-run`

## Rollback
- Revert the application commit.
- Migrate `commons` back to `0006_exercise_features` if the migration was applied.
- Rebuild backend/celery images; rebuild frontend if the UI changes were deployed.
