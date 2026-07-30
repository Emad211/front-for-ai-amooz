from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('classes', '0038_exam_prep_inventory_artifacts'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='examprepextractionartifact',
            name='active_task_id',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='examprepextractionartifact',
            name='heartbeat_at',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='examprepextractionartifact',
            name='revision',
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name='examprepextractionartifact',
            name='reviewed_projection_fingerprint',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
        migrations.AddField(
            model_name='examprepextractionartifact',
            name='reviewed_revision',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='examprepextractionartifact',
            name='source_retain_until',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='examprepextractionartifact',
            name='teacher_reviewed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='examprepextractionartifact',
            name='teacher_reviewed_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='reviewed_exam_prep_extractions',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.CreateModel(
            name='ExamPrepExtractionUnit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stage', models.CharField(choices=[('ocr', 'OCR'), ('manifest', 'Manifest'), ('questions', 'Questions'), ('answers', 'Answers'), ('visuals', 'Visuals')], db_index=True, max_length=16)),
                ('unit_key', models.CharField(max_length=160)),
                ('revision', models.PositiveIntegerField(default=1)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('processing', 'Processing'), ('accepted', 'Accepted'), ('retryable', 'Retryable'), ('quarantined', 'Quarantined'), ('failed', 'Failed'), ('superseded', 'Superseded')], db_index=True, default='pending', max_length=16)),
                ('source_page', models.PositiveIntegerField(blank=True, null=True)),
                ('source_timestamp_ms', models.PositiveBigIntegerField(blank=True, null=True)),
                ('source_segment', models.PositiveIntegerField(blank=True, null=True)),
                ('input_fingerprint', models.CharField(max_length=64)),
                ('output_payload', models.JSONField(blank=True, default=dict)),
                ('quality_report', models.JSONField(blank=True, default=dict)),
                ('attempt_count', models.PositiveSmallIntegerField(default=0)),
                ('processing_task_id', models.CharField(blank=True, default='', max_length=255)),
                ('provider', models.CharField(blank=True, default='', max_length=32)),
                ('model_name', models.CharField(blank=True, default='', max_length=128)),
                ('prompt_version', models.CharField(blank=True, default='', max_length=32)),
                ('response_id', models.CharField(blank=True, default='', max_length=255)),
                ('finish_reason', models.CharField(blank=True, default='', max_length=64)),
                ('input_length', models.PositiveIntegerField(default=0)),
                ('output_length', models.PositiveIntegerField(default=0)),
                ('duration_ms', models.PositiveIntegerField(default=0)),
                ('error_code', models.CharField(blank=True, default='', max_length=64)),
                ('error_detail', models.TextField(blank=True, default='')),
                ('heartbeat_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('artifact', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='units', to='classes.examprepextractionartifact')),
            ],
            options={
                'indexes': [
                    models.Index(fields=['artifact', 'stage', 'status'], name='exam_unit_art_stage_status_idx'),
                    models.Index(fields=['status', 'heartbeat_at'], name='exam_unit_status_heartbeat_idx'),
                ],
                'constraints': [
                    models.UniqueConstraint(fields=('artifact', 'stage', 'unit_key', 'revision'), name='uniq_exam_extract_unit_revision'),
                ],
            },
        ),
        migrations.AddIndex(
            model_name='examprepvisualasset',
            index=models.Index(
                fields=['source_file'],
                name='exam_visual_src_file_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='examprepvisualasset',
            index=models.Index(
                fields=['generated_file'],
                name='exam_visual_gen_file_idx',
            ),
        ),
    ]
