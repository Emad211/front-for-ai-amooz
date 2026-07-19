import logging

from django.db import migrations


FINALIZED_STATUSES = {'submitted', 'grading', 'graded', 'grading_failed'}
logger = logging.getLogger(__name__)


def _question_snapshots(Question, exercise_ids):
    snapshots = {exercise_id: [] for exercise_id in exercise_ids}
    rows = (
        Question.objects.filter(section__exercise_id__in=exercise_ids)
        .values(
            'id', 'section__exercise_id', 'section__order', 'order',
            'question_type', 'question_markdown', 'options',
            'reference_answer_markdown', 'grading_notes', 'max_points',
        )
        .order_by('section__exercise_id', 'section__order', 'order', 'id')
    )
    for row in rows.iterator(chunk_size=500):
        snapshots[row['section__exercise_id']].append({
            'id': row['id'],
            'section_order': row['section__order'],
            'order': row['order'],
            'question_type': row['question_type'],
            'question_markdown': row['question_markdown'] or '',
            'options': row['options'] if isinstance(row['options'], list) else [],
            'reference_answer_markdown': row['reference_answer_markdown'] or '',
            'grading_notes': row['grading_notes'] or '',
            'max_points': str(row['max_points'] or 0),
        })
    return snapshots


def _create_attempt_batch(Attempt, Question, submissions):
    existing_submission_ids = set(
        Attempt.objects.filter(
            submission_id__in=[submission.id for submission in submissions],
            attempt_number=1,
        ).values_list('submission_id', flat=True)
    )
    to_create = [
        submission
        for submission in submissions
        if submission.id not in existing_submission_ids
    ]
    snapshots = _question_snapshots(
        Question,
        {submission.exercise_id for submission in to_create},
    )
    Attempt.objects.bulk_create([
        Attempt(
            submission_id=submission.id,
            attempt_number=1,
            status=submission.status,
            answers=submission.answers if isinstance(submission.answers, dict) else {},
            question_snapshot=snapshots.get(submission.exercise_id, []),
            result=submission.result if isinstance(submission.result, dict) else {},
            score_points=submission.score_points,
            max_points=submission.max_points,
            is_late=submission.is_late,
            grading_task_id=submission.grading_task_id,
            graded_at=submission.graded_at,
            overridden_at=submission.overridden_at,
            grader_metadata={'backfilled': True},
        )
        for submission in to_create
    ], ignore_conflicts=True)
    return len(to_create), len(existing_submission_ids)


def backfill_exercise_attempts(apps, schema_editor):
    Submission = apps.get_model('classes', 'StudentExerciseSubmission')
    Attempt = apps.get_model('classes', 'StudentExerciseAttempt')
    Question = apps.get_model('classes', 'ClassExerciseQuestion')
    pending_submissions = []
    targeted = Submission.objects.filter(
        status__in=FINALIZED_STATUSES,
    ).count()
    created = 0
    skipped_existing = 0
    linked = 0

    queryset = Submission.objects.filter(status__in=FINALIZED_STATUSES).order_by('id')
    for submission in queryset.iterator(chunk_size=500):
        pending_submissions.append(submission)
        if len(pending_submissions) == 500:
            batch_created, batch_skipped = _create_attempt_batch(
                Attempt, Question, pending_submissions,
            )
            created += batch_created
            skipped_existing += batch_skipped
            pending_submissions.clear()

    if pending_submissions:
        batch_created, batch_skipped = _create_attempt_batch(
            Attempt, Question, pending_submissions,
        )
        created += batch_created
        skipped_existing += batch_skipped

    current_batch = []
    for attempt in Attempt.objects.filter(attempt_number=1).iterator(chunk_size=500):
        metadata = attempt.grader_metadata if isinstance(attempt.grader_metadata, dict) else {}
        if metadata.get('backfilled') is not True:
            continue
        current_batch.append(attempt)
        if len(current_batch) == 500:
            submissions = Submission.objects.in_bulk([row.submission_id for row in current_batch])
            changed_submissions = []
            changed_attempts = []
            for row in current_batch:
                submission = submissions.get(row.submission_id)
                if (
                    submission
                    and submission.status in FINALIZED_STATUSES
                    and submission.current_attempt_id is None
                ):
                    submission.current_attempt_id = row.id
                    changed_submissions.append(submission)
                    if row.submitted_at != submission.created_at:
                        row.submitted_at = submission.created_at
                        changed_attempts.append(row)
            if changed_submissions:
                Submission.objects.bulk_update(changed_submissions, ['current_attempt'])
                linked += len(changed_submissions)
            if changed_attempts:
                Attempt.objects.bulk_update(changed_attempts, ['submitted_at'])
            current_batch.clear()
    if current_batch:
        submissions = Submission.objects.in_bulk([row.submission_id for row in current_batch])
        changed_submissions = []
        changed_attempts = []
        for row in current_batch:
            submission = submissions.get(row.submission_id)
            if (
                submission
                and submission.status in FINALIZED_STATUSES
                and submission.current_attempt_id is None
            ):
                submission.current_attempt_id = row.id
                changed_submissions.append(submission)
                if row.submitted_at != submission.created_at:
                    row.submitted_at = submission.created_at
                    changed_attempts.append(row)
        if changed_submissions:
            Submission.objects.bulk_update(changed_submissions, ['current_attempt'])
            linked += len(changed_submissions)
        if changed_attempts:
            Attempt.objects.bulk_update(changed_attempts, ['submitted_at'])

    logger.info(
        'Exercise attempt backfill complete targeted=%s created=%s '
        'skipped_existing=%s linked=%s',
        targeted, created, skipped_existing, linked,
    )


class Migration(migrations.Migration):
    dependencies = [
        ('classes', '0032_studentexerciseattempt'),
    ]

    operations = [
        migrations.RunPython(backfill_exercise_attempts, migrations.RunPython.noop),
    ]
