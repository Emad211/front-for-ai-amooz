from django.db import migrations, models
import django.db.models.deletion
import core.storage_backends


class Migration(migrations.Migration):
    dependencies = [
        ('classes', '0037_answer_asset_private_storage'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExamPrepExtractionArtifact',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pipeline_version', models.PositiveSmallIntegerField(default=2)),
                ('status', models.CharField(choices=[('collecting_pages', 'Collecting source pages'), ('inventory', 'Building page inventory'), ('extracting', 'Extracting questions and answers'), ('matching', 'Matching answers'), ('visuals', 'Processing visuals'), ('ready', 'Ready for review'), ('failed', 'Failed')], db_index=True, default='collecting_pages', max_length=32)),
                ('source_fingerprint', models.CharField(blank=True, default='', max_length=64)),
                ('source_blocks', models.JSONField(blank=True, default=list)),
                ('page_manifest', models.JSONField(blank=True, default=dict)),
                ('question_records', models.JSONField(blank=True, default=list)),
                ('answer_records', models.JSONField(blank=True, default=list)),
                ('audit', models.JSONField(blank=True, default=dict)),
                ('failed_chunks', models.JSONField(blank=True, default=list)),
                ('prompt_version', models.CharField(blank=True, default='', max_length=32)),
                ('provider', models.CharField(blank=True, default='', max_length=32)),
                ('model_name', models.CharField(blank=True, default='', max_length=128)),
                ('error_code', models.CharField(blank=True, default='', max_length=64)),
                ('error_detail', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('session', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='exam_extraction_artifact', to='classes.classcreationsession')),
            ],
            options={
                'indexes': [models.Index(fields=['status', 'updated_at'], name='exam_art_status_updated_idx')],
            },
        ),
        migrations.CreateModel(
            name='ExamPrepVisualAsset',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('asset_key', models.CharField(max_length=64)),
                ('question_key', models.CharField(blank=True, default='', max_length=160)),
                ('role', models.CharField(choices=[('question', 'Question'), ('option', 'Option'), ('solution', 'Solution')], max_length=16)),
                ('option_label', models.CharField(blank=True, default='', max_length=16)),
                ('source_kind', models.CharField(choices=[('pdf_page', 'PDF page'), ('video_frame', 'Video frame'), ('source_image', 'Source image')], max_length=24)),
                ('source_page', models.PositiveIntegerField(blank=True, null=True)),
                ('source_timestamp_ms', models.PositiveBigIntegerField(blank=True, null=True)),
                ('source_bbox', models.JSONField(blank=True, default=dict)),
                ('order', models.PositiveIntegerField(default=0)),
                ('source_file', models.FileField(storage=core.storage_backends.answer_source_storage, upload_to='exam-prep/visuals/source/')),
                ('source_content_type', models.CharField(default='image/png', max_length=100)),
                ('source_byte_size', models.PositiveBigIntegerField(default=0)),
                ('source_sha256', models.CharField(max_length=64)),
                ('generated_file', models.FileField(blank=True, storage=core.storage_backends.answer_source_storage, upload_to='exam-prep/visuals/generated/')),
                ('generated_content_type', models.CharField(blank=True, default='', max_length=100)),
                ('generated_byte_size', models.PositiveBigIntegerField(default=0)),
                ('generated_sha256', models.CharField(blank=True, default='', max_length=64)),
                ('alt_text', models.TextField(blank=True, default='')),
                ('visual_spec', models.JSONField(blank=True, default=dict)),
                ('verification', models.JSONField(blank=True, default=dict)),
                ('fingerprint', models.CharField(max_length=64)),
                ('status', models.CharField(choices=[('source_ready', 'Source crop ready'), ('generating', 'Generating candidate'), ('generated', 'Candidate generated'), ('verified', 'Candidate verified'), ('needs_review', 'Needs teacher review'), ('failed', 'Failed')], db_index=True, default='source_ready', max_length=24)),
                ('selected_variant', models.CharField(choices=[('source', 'Original source'), ('generated', 'Generated candidate')], default='source', max_length=16)),
                ('teacher_approved_generated', models.BooleanField(default=False)),
                ('generation_provider', models.CharField(blank=True, default='', max_length=32)),
                ('generation_model', models.CharField(blank=True, default='', max_length=128)),
                ('generation_prompt_version', models.CharField(blank=True, default='', max_length=32)),
                ('error_detail', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('artifact', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='visual_assets', to='classes.examprepextractionartifact')),
            ],
            options={
                'indexes': [
                    models.Index(fields=['artifact', 'question_key', 'order'], name='exam_visual_question_order_idx'),
                ],
                'constraints': [
                    models.UniqueConstraint(fields=('artifact', 'asset_key'), name='uniq_exam_visual_asset_key'),
                ],
            },
        ),
    ]
