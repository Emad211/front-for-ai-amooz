from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('classes', '0031_clamp_exercise_teacher_scores'),
    ]

    operations = [
        migrations.CreateModel(
            name='StudentExerciseAttempt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('attempt_number', models.PositiveIntegerField()),
                ('status', models.CharField(choices=[('submitted', 'Submitted'), ('grading', 'Grading'), ('graded', 'Graded'), ('grading_failed', 'Grading Failed')], db_index=True, default='submitted', max_length=16)),
                ('answers', models.JSONField(blank=True, default=dict)),
                ('question_snapshot', models.JSONField(blank=True, default=list)),
                ('result', models.JSONField(blank=True, default=dict)),
                ('question_fingerprints', models.JSONField(blank=True, default=dict)),
                ('ocr_text', models.JSONField(blank=True, default=dict)),
                ('grader_metadata', models.JSONField(blank=True, default=dict)),
                ('score_points', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ('max_points', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ('is_late', models.BooleanField(default=False)),
                ('grading_task_id', models.CharField(blank=True, default='', max_length=255)),
                ('graded_at', models.DateTimeField(blank=True, null=True)),
                ('overridden_at', models.DateTimeField(blank=True, null=True)),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('submission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attempts', to='classes.studentexercisesubmission')),
            ],
            options={'ordering': ['attempt_number']},
        ),
        migrations.AddConstraint(
            model_name='studentexerciseattempt',
            constraint=models.UniqueConstraint(fields=('submission', 'attempt_number'), name='uniq_exercise_submission_attempt_number'),
        ),
        migrations.AddConstraint(
            model_name='studentexerciseattempt',
            constraint=models.CheckConstraint(condition=models.Q(('attempt_number__gte', 1)), name='exercise_attempt_number_gte_1'),
        ),
        migrations.AddIndex(
            model_name='studentexerciseattempt',
            index=models.Index(fields=['status', 'updated_at'], name='classes_stu_status_3dd24e_idx'),
        ),
        migrations.AddField(
            model_name='studentexercisesubmission',
            name='current_attempt',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='classes.studentexerciseattempt'),
        ),
    ]
