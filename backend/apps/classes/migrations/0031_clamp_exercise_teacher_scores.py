from decimal import Decimal, InvalidOperation

from django.db import migrations


def _finite_decimal(value):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return number if number.is_finite() else None


def clamp_exercise_teacher_scores(apps, schema_editor):
    Submission = apps.get_model('classes', 'StudentExerciseSubmission')
    pending = []

    for submission in Submission.objects.exclude(result={}).iterator(chunk_size=500):
        result = submission.result if isinstance(submission.result, dict) else {}
        per_question = result.get('per_question')
        if not isinstance(per_question, list):
            continue

        changed = False
        for item in per_question:
            if not isinstance(item, dict) or item.get('teacher_score') is None:
                continue
            score = _finite_decimal(item.get('teacher_score'))
            max_points = _finite_decimal(item.get('max_points'))
            if score is None or max_points is None or max_points < 0:
                item['teacher_score'] = None
                changed = True
                continue
            bounded = min(max(score, Decimal('0')), max_points)
            if bounded != score:
                item['teacher_score'] = float(bounded)
                changed = True

        if not changed:
            continue

        total = Decimal('0')
        for item in per_question:
            if not isinstance(item, dict):
                continue
            raw_score = item.get('teacher_score')
            if raw_score is None:
                raw_score = item.get('llm_score')
            if raw_score is None:
                raw_score = item.get('score_points')
            score = _finite_decimal(raw_score) or Decimal('0')
            max_points = _finite_decimal(item.get('max_points'))
            if max_points is None or max_points < 0:
                effective = Decimal('0')
            else:
                effective = min(max(score, Decimal('0')), max_points)
            item['score_points'] = float(round(effective, 2))
            total += effective

        submission.result = {**result, 'per_question': per_question}
        submission.score_points = round(total, 2)
        pending.append(submission)
        if len(pending) == 500:
            Submission.objects.bulk_update(pending, ['result', 'score_points'])
            pending.clear()

    if pending:
        Submission.objects.bulk_update(pending, ['result', 'score_points'])


class Migration(migrations.Migration):
    dependencies = [
        ('classes', '0030_teacherstudentaccess'),
    ]

    operations = [
        migrations.RunPython(clamp_exercise_teacher_scores, migrations.RunPython.noop),
    ]
