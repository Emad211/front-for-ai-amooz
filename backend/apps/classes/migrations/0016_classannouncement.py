from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('classes', '0015_student_exam_prep_attempt'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClassAnnouncement',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('content', models.TextField()),
                (
                    'priority',
                    models.CharField(
                        choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')],
                        default='medium',
                        max_length=16,
                    ),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'session',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='announcements',
                        to='classes.classcreationsession',
                    ),
                ),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
