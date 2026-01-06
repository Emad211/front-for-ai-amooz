from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('classes', '0007_add_recap_step5'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ClassSectionQuiz',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('questions', models.JSONField(blank=True, default=dict)),
                ('last_score_0_100', models.PositiveIntegerField(blank=True, null=True)),
                ('last_passed', models.BooleanField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('section', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='quizzes', to='classes.classsection')),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='section_quizzes', to='classes.classcreationsession')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='class_section_quizzes', to=settings.AUTH_USER_MODEL)),
            ],
            options={},
        ),
        migrations.CreateModel(
            name='ClassSectionQuizAttempt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('answers', models.JSONField(blank=True, default=dict)),
                ('result', models.JSONField(blank=True, default=dict)),
                ('score_0_100', models.PositiveIntegerField()),
                ('passed', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('quiz', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attempts', to='classes.classsectionquiz')),
            ],
            options={},
        ),
        migrations.AddConstraint(
            model_name='classsectionquiz',
            constraint=models.UniqueConstraint(fields=('session', 'section', 'student'), name='uniq_class_section_quiz_session_section_student'),
        ),
    ]
