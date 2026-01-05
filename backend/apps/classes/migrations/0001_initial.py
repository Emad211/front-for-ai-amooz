from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClassCreationSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('source_file', models.FileField(upload_to='class_creation/source/')),
                ('source_mime_type', models.CharField(blank=True, max_length=127)),
                ('source_original_name', models.CharField(blank=True, max_length=255)),
                (
                    'status',
                    models.CharField(
                        choices=[('transcribing', 'Transcribing'), ('transcribed', 'Transcribed'), ('failed', 'Failed')],
                        default='transcribing',
                        max_length=32,
                    ),
                ),
                ('transcript_markdown', models.TextField(blank=True)),
                ('llm_provider', models.CharField(blank=True, max_length=32)),
                ('llm_model', models.CharField(blank=True, max_length=128)),
                ('error_detail', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'teacher',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='class_creation_sessions',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
