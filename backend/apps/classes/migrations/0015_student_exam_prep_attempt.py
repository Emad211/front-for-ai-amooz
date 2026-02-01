from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('classes', '0014_ensure_student_invite_code_table'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='StudentExamPrepAttempt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('answers', models.JSONField(default=dict)),
                ('score_0_100', models.IntegerField(blank=True, null=True)),
                ('total_questions', models.IntegerField(default=0)),
                ('correct_count', models.IntegerField(default=0)),
                ('finalized', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exam_prep_attempts', to='classes.classcreationsession')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exam_prep_attempts', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name='studentexamprepattempt',
            constraint=models.UniqueConstraint(fields=('session', 'student'), name='uniq_exam_prep_attempt_session_student'),
        ),
    ]
