# Pipeline cancellation: CANCELLED status + celery_task_id + cancel_requested.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classes', '0021_enrollment_studentunitprogress'),
    ]

    operations = [
        migrations.AddField(
            model_name='classcreationsession',
            name='celery_task_id',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='classcreationsession',
            name='cancel_requested',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='classcreationsession',
            name='status',
            field=models.CharField(
                choices=[
                    ('transcribing', 'Transcribing'),
                    ('transcribed', 'Transcribed'),
                    ('structuring', 'Structuring'),
                    ('structured', 'Structured'),
                    ('prereq_extracting', 'Prerequisites: Extracting'),
                    ('prereq_extracted', 'Prerequisites: Extracted'),
                    ('prereq_teaching', 'Prerequisites: Teaching'),
                    ('prereq_taught', 'Prerequisites: Taught'),
                    ('recapping', 'Recap: Generating'),
                    ('recapped', 'Recap: Ready'),
                    ('exam_transcribing', 'Exam Prep: Transcribing'),
                    ('exam_transcribed', 'Exam Prep: Transcribed'),
                    ('exam_structuring', 'Exam Prep: Extracting Q&A'),
                    ('exam_structured', 'Exam Prep: Ready'),
                    ('failed', 'Failed'),
                    ('cancelled', 'Cancelled'),
                ],
                db_index=True,
                default='transcribing',
                max_length=32,
            ),
        ),
    ]
