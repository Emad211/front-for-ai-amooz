from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ('classes', '0043_exam_prep_v4_source_blocks'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExamQuestionRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('revision', models.PositiveIntegerField(default=1)),
                ('order', models.PositiveIntegerField(default=0)),
                ('section_key', models.CharField(blank=True, default='', max_length=128)),
                ('printed_number', models.CharField(blank=True, default='', max_length=64)),
                ('question_text', models.TextField()),
                ('options', models.JSONField(blank=True, default=list)),
                ('confidence', models.DecimalField(decimal_places=4, default=0, max_digits=5)),
                ('block_set_fingerprint', models.CharField(db_index=True, max_length=64)),
                ('set_fingerprint', models.CharField(db_index=True, max_length=64)),
                ('fingerprint', models.CharField(db_index=True, max_length=64)),
                ('lifecycle_status', models.CharField(choices=[('accepted', 'Accepted'), ('superseded', 'Superseded'), ('failed', 'Failed')], db_index=True, default='accepted', max_length=16)),
                ('warnings', models.JSONField(blank=True, default=list)),
                ('raw_payload', models.JSONField(blank=True, default=dict)),
                ('error_code', models.CharField(blank=True, default='', max_length=64)),
                ('error_detail', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('document', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='question_records_v4', to='classes.examsourcedocument')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='question_records_v4', to='classes.examproject')),
                ('source_block', models.ForeignKey(on_delete=django.db.models.deletion.RESTRICT, related_name='question_records', to='classes.examsourceblock')),
            ],
            options={'ordering': ['revision', 'order', 'id']},
        ),
        migrations.CreateModel(
            name='ExamQuestionRecordEvidence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('block', models.ForeignKey(on_delete=django.db.models.deletion.RESTRICT, related_name='question_evidence_links', to='classes.examsourceblock')),
                ('record', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='evidence_links', to='classes.examquestionrecord')),
            ],
            options={'ordering': ['order', 'id']},
        ),
        migrations.CreateModel(
            name='ExamAnswerSolutionRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('revision', models.PositiveIntegerField(default=1)),
                ('order', models.PositiveIntegerField(default=0)),
                ('section_key', models.CharField(blank=True, default='', max_length=128)),
                ('printed_number', models.CharField(blank=True, default='', max_length=64)),
                ('correct_option', models.CharField(blank=True, default='', max_length=32)),
                ('final_answer', models.TextField(blank=True, default='')),
                ('solution_text', models.TextField(blank=True, default='')),
                ('confidence', models.DecimalField(decimal_places=4, default=0, max_digits=5)),
                ('block_set_fingerprint', models.CharField(db_index=True, max_length=64)),
                ('set_fingerprint', models.CharField(db_index=True, max_length=64)),
                ('fingerprint', models.CharField(db_index=True, max_length=64)),
                ('lifecycle_status', models.CharField(choices=[('accepted', 'Accepted'), ('superseded', 'Superseded'), ('failed', 'Failed')], db_index=True, default='accepted', max_length=16)),
                ('warnings', models.JSONField(blank=True, default=list)),
                ('raw_payload', models.JSONField(blank=True, default=dict)),
                ('error_code', models.CharField(blank=True, default='', max_length=64)),
                ('error_detail', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('document', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='answer_solution_records_v4', to='classes.examsourcedocument')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='answer_solution_records_v4', to='classes.examproject')),
                ('source_block', models.ForeignKey(on_delete=django.db.models.deletion.RESTRICT, related_name='answer_solution_records', to='classes.examsourceblock')),
            ],
            options={'ordering': ['revision', 'order', 'id']},
        ),
        migrations.CreateModel(
            name='ExamAnswerSolutionRecordEvidence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('block', models.ForeignKey(on_delete=django.db.models.deletion.RESTRICT, related_name='answer_solution_evidence_links', to='classes.examsourceblock')),
                ('record', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='evidence_links', to='classes.examanswersolutionrecord')),
            ],
            options={'ordering': ['order', 'id']},
        ),
        migrations.CreateModel(
            name='ExamMatchDecision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('revision', models.PositiveIntegerField(default=1)),
                ('order', models.PositiveIntegerField(default=0)),
                ('decision', models.CharField(choices=[('matched', 'Matched'), ('out_of_scope', 'Out of scope'), ('unresolved', 'Unresolved'), ('ambiguous', 'Ambiguous'), ('conflict', 'Conflict')], max_length=24)),
                ('method', models.CharField(choices=[('exact_scope_number', 'Exact scope and number'), ('unique_number', 'Unique project number'), ('none', 'No automatic method')], default='none', max_length=32)),
                ('normalized_section', models.CharField(blank=True, default='', max_length=128)),
                ('normalized_number', models.CharField(blank=True, default='', max_length=64)),
                ('reason_code', models.CharField(blank=True, default='', max_length=64)),
                ('question_set_fingerprint', models.CharField(max_length=64)),
                ('answer_set_fingerprint', models.CharField(max_length=64)),
                ('set_fingerprint', models.CharField(db_index=True, max_length=64)),
                ('fingerprint', models.CharField(db_index=True, max_length=64)),
                ('lifecycle_status', models.CharField(choices=[('accepted', 'Accepted'), ('superseded', 'Superseded'), ('failed', 'Failed')], db_index=True, default='accepted', max_length=16)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('answer_record', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='match_decisions', to='classes.examanswersolutionrecord')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='match_decisions_v4', to='classes.examproject')),
                ('question_record', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='match_decisions', to='classes.examquestionrecord')),
            ],
            options={'ordering': ['revision', 'order', 'id']},
        ),
        migrations.AddConstraint(
            model_name='examquestionrecord',
            constraint=models.UniqueConstraint(fields=('document', 'revision', 'order'), name='uniq_exam_v4_question_order'),
        ),
        migrations.AddConstraint(
            model_name='examquestionrecord',
            constraint=models.UniqueConstraint(fields=('source_block', 'revision'), name='uniq_exam_v4_question_block_revision'),
        ),
        migrations.AddConstraint(
            model_name='examquestionrecord',
            constraint=models.CheckConstraint(condition=Q(revision__gte=1), name='exam_v4_question_revision_gte_1'),
        ),
        migrations.AddConstraint(
            model_name='examquestionrecord',
            constraint=models.CheckConstraint(condition=Q(confidence__gte=0) & Q(confidence__lte=1), name='exam_v4_question_confidence_range'),
        ),
        migrations.AddConstraint(
            model_name='examquestionrecord',
            constraint=models.CheckConstraint(condition=~Q(question_text=''), name='exam_v4_question_text_not_empty'),
        ),
        migrations.AddIndex(
            model_name='examquestionrecord',
            index=models.Index(fields=['project', 'lifecycle_status', 'section_key', 'printed_number'], name='exam_v4_question_lookup_idx'),
        ),
        migrations.AddIndex(
            model_name='examquestionrecord',
            index=models.Index(fields=['document', 'block_set_fingerprint', 'revision', 'order'], name='exam_v4_question_current_idx'),
        ),
        migrations.AddConstraint(
            model_name='examquestionrecordevidence',
            constraint=models.UniqueConstraint(fields=('record', 'order'), name='uniq_exam_v4_question_evidence_order'),
        ),
        migrations.AddConstraint(
            model_name='examquestionrecordevidence',
            constraint=models.UniqueConstraint(fields=('record', 'block'), name='uniq_exam_v4_question_evidence_block'),
        ),
        migrations.AddConstraint(
            model_name='examanswersolutionrecord',
            constraint=models.UniqueConstraint(fields=('document', 'revision', 'order'), name='uniq_exam_v4_answer_order'),
        ),
        migrations.AddConstraint(
            model_name='examanswersolutionrecord',
            constraint=models.UniqueConstraint(fields=('source_block', 'revision'), name='uniq_exam_v4_answer_block_revision'),
        ),
        migrations.AddConstraint(
            model_name='examanswersolutionrecord',
            constraint=models.CheckConstraint(condition=Q(revision__gte=1), name='exam_v4_answer_revision_gte_1'),
        ),
        migrations.AddConstraint(
            model_name='examanswersolutionrecord',
            constraint=models.CheckConstraint(condition=Q(confidence__gte=0) & Q(confidence__lte=1), name='exam_v4_answer_confidence_range'),
        ),
        migrations.AddConstraint(
            model_name='examanswersolutionrecord',
            constraint=models.CheckConstraint(condition=~Q(correct_option='') | ~Q(final_answer='') | ~Q(solution_text=''), name='exam_v4_answer_content_not_empty'),
        ),
        migrations.AddIndex(
            model_name='examanswersolutionrecord',
            index=models.Index(fields=['project', 'lifecycle_status', 'section_key', 'printed_number'], name='exam_v4_answer_lookup_idx'),
        ),
        migrations.AddIndex(
            model_name='examanswersolutionrecord',
            index=models.Index(fields=['document', 'block_set_fingerprint', 'revision', 'order'], name='exam_v4_answer_current_idx'),
        ),
        migrations.AddConstraint(
            model_name='examanswersolutionrecordevidence',
            constraint=models.UniqueConstraint(fields=('record', 'order'), name='uniq_exam_v4_answer_evidence_order'),
        ),
        migrations.AddConstraint(
            model_name='examanswersolutionrecordevidence',
            constraint=models.UniqueConstraint(fields=('record', 'block'), name='uniq_exam_v4_answer_evidence_block'),
        ),
        migrations.AddConstraint(
            model_name='exammatchdecision',
            constraint=models.UniqueConstraint(fields=('project', 'revision', 'order'), name='uniq_exam_v4_match_order'),
        ),
        migrations.AddConstraint(
            model_name='exammatchdecision',
            constraint=models.UniqueConstraint(fields=('answer_record', 'revision'), name='uniq_exam_v4_match_answer_revision'),
        ),
        migrations.AddConstraint(
            model_name='exammatchdecision',
            constraint=models.CheckConstraint(condition=Q(revision__gte=1), name='exam_v4_match_revision_gte_1'),
        ),
        migrations.AddIndex(
            model_name='exammatchdecision',
            index=models.Index(fields=['project', 'lifecycle_status', 'decision', 'order'], name='exam_v4_match_current_idx'),
        ),
    ]
