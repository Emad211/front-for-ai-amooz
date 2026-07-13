from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('classes', '0029_classcreationsession_workflow_and_pending_exercises'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TeacherStudentAccess',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_suspended', models.BooleanField(default=False)),
                ('suspended_at', models.DateTimeField(blank=True, null=True)),
                ('reason', models.CharField(blank=True, max_length=240)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='teacher_access_states', to=settings.AUTH_USER_MODEL)),
                ('teacher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='managed_student_access', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name='teacherstudentaccess',
            constraint=models.UniqueConstraint(fields=('teacher', 'student'), name='uniq_teacher_student_access'),
        ),
        migrations.AddIndex(
            model_name='teacherstudentaccess',
            index=models.Index(fields=['teacher', 'is_suspended'], name='classes_tea_teacher_38d252_idx'),
        ),
    ]
