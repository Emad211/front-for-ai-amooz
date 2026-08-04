from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('classes', '0046_exam_prep_v4_legacy_projection'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExamV4SessionBridge',
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
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'project',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='create_flow_bridge',
                        to='classes.examproject',
                    ),
                ),
                (
                    'session',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='source_aware_exam_bridge',
                        to='classes.classcreationsession',
                    ),
                ),
            ],
        ),
    ]
