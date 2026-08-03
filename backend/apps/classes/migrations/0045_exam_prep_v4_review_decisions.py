from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ('classes', '0044_exam_prep_v4_typed_records_and_matches'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ExamReviewDecision',
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
                (
                    'action',
                    models.CharField(
                        choices=[
                            ('match', 'Match to question'),
                            ('out_of_scope', 'Confirm out of scope'),
                            ('ignore', 'Ignore answer record'),
                        ],
                        max_length=24,
                    ),
                ),
                ('note', models.CharField(blank=True, default='', max_length=500)),
                ('question_set_fingerprint', models.CharField(max_length=64)),
                ('answer_set_fingerprint', models.CharField(max_length=64)),
                ('source_match_fingerprint', models.CharField(max_length=64)),
                ('fingerprint', models.CharField(db_index=True, max_length=64)),
                (
                    'lifecycle_status',
                    models.CharField(
                        choices=[
                            ('accepted', 'Accepted'),
                            ('superseded', 'Superseded'),
                            ('failed', 'Failed'),
                        ],
                        db_index=True,
                        default='accepted',
                        max_length=16,
                    ),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'answer_record',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name='teacher_reviews',
                        to='classes.examanswersolutionrecord',
                    ),
                ),
                (
                    'created_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='exam_v4_review_decisions',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'match_decision',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name='teacher_reviews',
                        to='classes.exammatchdecision',
                    ),
                ),
                (
                    'project',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='review_decisions_v4',
                        to='classes.examproject',
                    ),
                ),
                (
                    'question_record',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='teacher_review_matches',
                        to='classes.examquestionrecord',
                    ),
                ),
            ],
            options={'ordering': ['revision', 'id']},
        ),
        migrations.AddConstraint(
            model_name='examreviewdecision',
            constraint=models.UniqueConstraint(
                fields=('answer_record', 'revision'),
                name='uniq_exam_v4_review_answer_revision',
            ),
        ),
        migrations.AddConstraint(
            model_name='examreviewdecision',
            constraint=models.CheckConstraint(
                condition=Q(revision__gte=1),
                name='exam_v4_review_revision_gte_1',
            ),
        ),
        migrations.AddConstraint(
            model_name='examreviewdecision',
            constraint=models.CheckConstraint(
                condition=(
                    Q(action='match', question_record__isnull=False)
                    | Q(
                        action__in=['out_of_scope', 'ignore'],
                        question_record__isnull=True,
                    )
                ),
                name='exam_v4_review_action_question',
            ),
        ),
        migrations.AddIndex(
            model_name='examreviewdecision',
            index=models.Index(
                fields=['project', 'lifecycle_status', 'action', '-updated_at'],
                name='exam_v4_review_current_idx',
            ),
        ),
    ]
