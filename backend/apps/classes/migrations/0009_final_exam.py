from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('classes', '0008_section_quizzes'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ClassFinalExam',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('exam', models.JSONField(blank=True, default=dict)),
                ('last_score_0_100', models.PositiveIntegerField(blank=True, null=True)),
                ('last_passed', models.BooleanField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='final_exams', to='classes.classcreationsession')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='class_final_exams', to=settings.AUTH_USER_MODEL)),
            ],
            options={},
        ),
        migrations.CreateModel(
            name='ClassFinalExamAttempt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('answers', models.JSONField(blank=True, default=dict)),
                ('result', models.JSONField(blank=True, default=dict)),
                ('score_0_100', models.PositiveIntegerField()),
                ('passed', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('exam', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attempts', to='classes.classfinalexam')),
            ],
            options={},
        ),
        migrations.AddConstraint(
            model_name='classfinalexam',
            constraint=models.UniqueConstraint(fields=('session', 'student'), name='uniq_class_final_exam_session_student'),
        ),
    ]
