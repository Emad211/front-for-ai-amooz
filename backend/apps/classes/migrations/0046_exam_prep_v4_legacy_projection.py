from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ('classes', '0045_exam_prep_v4_review_decisions'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExamV4Projection',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('revision', models.PositiveIntegerField(default=1)),
                ('question_set_fingerprint', models.CharField(max_length=64)),
                ('answer_set_fingerprint', models.CharField(max_length=64)),
                ('review_set_fingerprint', models.CharField(max_length=64)),
                ('projection_fingerprint', models.CharField(db_index=True, max_length=64)),
                ('question_count', models.PositiveIntegerField(default=0)),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('ready', 'Ready'),
                            ('published', 'Published'),
                            ('superseded', 'Superseded'),
                            ('failed', 'Failed'),
                        ],
                        db_index=True,
                        default='ready',
                        max_length=16,
                    ),
                ),
                ('published_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'project',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='legacy_projection_v4',
                        to='classes.examproject',
                    ),
                ),
                (
                    'session',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='source_exam_v4_projection',
                        to='classes.classcreationsession',
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name='examv4projection',
            constraint=models.CheckConstraint(
                condition=Q(revision__gte=1),
                name='exam_v4_projection_revision_gte_1',
            ),
        ),
        migrations.AddIndex(
            model_name='examv4projection',
            index=models.Index(
                fields=['status', '-updated_at'],
                name='exam_v4_projection_status_idx',
            ),
        ),
    ]
