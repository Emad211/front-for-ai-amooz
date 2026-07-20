from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('classes', '0033_backfill_exercise_attempts')]

    operations = [
        migrations.CreateModel(
            name='StudentExerciseAnswerSource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('scope', models.CharField(choices=[('question', 'Question'), ('exercise', 'Exercise')], max_length=12)),
                ('status', models.CharField(choices=[('queued', 'Queued'), ('reading', 'Reading'), ('segmenting', 'Segmenting'), ('matching', 'Matching'), ('ready', 'Ready'), ('needs_review', 'Needs review'), ('failed', 'Failed'), ('superseded', 'Superseded')], db_index=True, default='queued', max_length=16)),
                ('revision', models.PositiveIntegerField(default=1)),
                ('workflow_state', models.JSONField(blank=True, default=dict)),
                ('source_fingerprint', models.CharField(blank=True, default='', max_length=80)),
                ('raw_result', models.JSONField(blank=True, default=dict)),
                ('reviewed_result', models.JSONField(blank=True, default=dict)),
                ('processor_metadata', models.JSONField(blank=True, default=dict)),
                ('processing_task_id', models.CharField(blank=True, default='', max_length=255)),
                ('error_code', models.CharField(blank=True, default='', max_length=64)),
                ('applied_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('submission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='answer_sources', to='classes.studentexercisesubmission')),
                ('target_question', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='classes.classexercisequestion')),
            ],
        ),
        migrations.CreateModel(
            name='StudentExerciseAnswerAsset',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='exercises/answers/sources/')),
                ('order', models.PositiveIntegerField(default=0)),
                ('content_type', models.CharField(max_length=100)),
                ('byte_size', models.PositiveBigIntegerField(default=0)),
                ('sha256', models.CharField(max_length=64)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('source', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assets', to='classes.studentexerciseanswersource')),
            ],
            options={'ordering': ['order', 'id']},
        ),
        migrations.AddConstraint(
            model_name='studentexerciseanswersource',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('scope', 'question'), ('target_question__isnull', False)), models.Q(('scope', 'exercise'), ('target_question__isnull', True)), _connector='OR'), name='answer_ocr_source_scope_target_valid'),
        ),
        migrations.AddConstraint(
            model_name='studentexerciseanswersource',
            constraint=models.UniqueConstraint(condition=models.Q(('scope', 'question')), fields=('submission', 'target_question'), name='uniq_question_answer_ocr_source'),
        ),
        migrations.AddConstraint(
            model_name='studentexerciseanswersource',
            constraint=models.UniqueConstraint(condition=models.Q(('scope', 'exercise')), fields=('submission',), name='uniq_exercise_answer_ocr_source'),
        ),
        migrations.AddIndex(
            model_name='studentexerciseanswersource',
            index=models.Index(fields=['submission', 'status'], name='classes_stu_submiss_4a3ad0_idx'),
        ),
        migrations.AddConstraint(
            model_name='studentexerciseanswerasset',
            constraint=models.UniqueConstraint(fields=('source', 'order'), name='uniq_answer_source_asset_order'),
        ),
    ]
