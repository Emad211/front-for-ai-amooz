import uuid

import core.storage_backends
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('classes', '0039_exam_prep_extraction_v3'),
        ('organizations', '0010_drop_legacy_invitationcode_columns'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ExamProject',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('client_request_id', models.UUIDField(blank=True, default=None, null=True)),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, default='')),
                ('engine_version', models.PositiveSmallIntegerField(default=4, editable=False)),
                ('revision', models.PositiveIntegerField(default=1)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('uploading', 'Uploading'), ('classifying', 'Classifying sources'), ('awaiting_source_confirmation', 'Awaiting source confirmation'), ('segmenting', 'Segmenting source pages'), ('extracting_questions', 'Extracting questions'), ('extracting_answers', 'Extracting answers and solutions'), ('matching', 'Matching records'), ('awaiting_review', 'Awaiting teacher review'), ('ready_to_publish', 'Ready to publish'), ('published', 'Published'), ('cancelled', 'Cancelled'), ('failed', 'Failed')], db_index=True, default='draft', max_length=40)),
                ('workflow_state', models.JSONField(blank=True, default=dict)),
                ('error_code', models.CharField(blank=True, default='', max_length=64)),
                ('error_detail', models.TextField(blank=True, default='')),
                ('cancel_requested', models.BooleanField(default=False)),
                ('is_published', models.BooleanField(db_index=True, default=False)),
                ('published_at', models.DateTimeField(blank=True, null=True)),
                ('reviewed_revision', models.PositiveIntegerField(blank=True, null=True)),
                ('reviewed_projection_fingerprint', models.CharField(blank=True, default='', max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('organization', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='exam_v4_projects', to='organizations.organization')),
                ('study_group', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='exam_v4_projects', to='organizations.studygroup')),
                ('teacher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exam_v4_projects', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='ExamSourceDocument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('client_document_id', models.UUIDField(default=uuid.uuid4)),
                ('upload_order', models.PositiveIntegerField(default=0)),
                ('original_name', models.CharField(max_length=255)),
                ('mime_type', models.CharField(default='application/pdf', max_length=127)),
                ('source_file', models.FileField(blank=True, storage=core.storage_backends.answer_source_storage, upload_to='exam-prep-v4/source/documents/')),
                ('source_sha256', models.CharField(blank=True, db_index=True, default='', max_length=64)),
                ('byte_size', models.PositiveBigIntegerField(default=0)),
                ('page_count', models.PositiveIntegerField(default=0)),
                ('status', models.CharField(choices=[('pending_upload', 'Pending upload'), ('uploaded', 'Uploaded'), ('rendering', 'Rendering pages'), ('classifying', 'Classifying pages'), ('awaiting_confirmation', 'Awaiting confirmation'), ('confirmed', 'Confirmed'), ('failed', 'Failed')], db_index=True, default='pending_upload', max_length=32)),
                ('classification_revision', models.PositiveIntegerField(default=1)),
                ('classification_fingerprint', models.CharField(blank=True, default='', max_length=64)),
                ('classification_metadata', models.JSONField(blank=True, default=dict)),
                ('teacher_confirmed_at', models.DateTimeField(blank=True, null=True)),
                ('source_retain_until', models.DateTimeField(blank=True, null=True)),
                ('error_code', models.CharField(blank=True, default='', max_length=64)),
                ('error_detail', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='source_documents', to='classes.examproject')),
                ('teacher_confirmed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='confirmed_exam_v4_sources', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['upload_order', 'id']},
        ),
        migrations.CreateModel(
            name='ExamSourcePage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('page_number', models.PositiveIntegerField()),
                ('rendered_file', models.FileField(blank=True, storage=core.storage_backends.answer_source_storage, upload_to='exam-prep-v4/source/pages/')),
                ('thumbnail_file', models.FileField(blank=True, storage=core.storage_backends.answer_source_storage, upload_to='exam-prep-v4/source/thumbnails/')),
                ('content_type', models.CharField(default='image/png', max_length=100)),
                ('byte_size', models.PositiveBigIntegerField(default=0)),
                ('width', models.PositiveIntegerField(default=0)),
                ('height', models.PositiveIntegerField(default=0)),
                ('sha256', models.CharField(blank=True, db_index=True, default='', max_length=64)),
                ('perceptual_hash', models.CharField(blank=True, db_index=True, default='', max_length=64)),
                ('native_text_sample', models.TextField(blank=True, default='')),
                ('native_text_length', models.PositiveIntegerField(default=0)),
                ('predicted_role', models.CharField(choices=[('cover', 'Cover'), ('questions', 'Questions'), ('answer_solutions', 'Answers and solutions'), ('answer_key', 'Answer key'), ('inline_question_answer', 'Question with inline answer'), ('ignored', 'Ignored'), ('unknown', 'Unknown')], db_index=True, default='unknown', max_length=32)),
                ('predicted_confidence', models.DecimalField(decimal_places=4, default=0, max_digits=5)),
                ('teacher_role', models.CharField(blank=True, choices=[('cover', 'Cover'), ('questions', 'Questions'), ('answer_solutions', 'Answers and solutions'), ('answer_key', 'Answer key'), ('inline_question_answer', 'Question with inline answer'), ('ignored', 'Ignored'), ('unknown', 'Unknown')], default='', max_length=32)),
                ('orientation', models.PositiveSmallIntegerField(choices=[(0, '0°'), (90, '90°'), (180, '180°'), (270, '270°')], default=0)),
                ('classification_metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('document', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pages', to='classes.examsourcedocument')),
                ('duplicate_of', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='duplicates', to='classes.examsourcepage')),
            ],
            options={'ordering': ['page_number']},
        ),
        migrations.CreateModel(
            name='ExamSourceSegment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('revision', models.PositiveIntegerField(default=1)),
                ('order', models.PositiveIntegerField(default=0)),
                ('start_page', models.PositiveIntegerField()),
                ('end_page', models.PositiveIntegerField()),
                ('role', models.CharField(choices=[('cover', 'Cover'), ('questions', 'Questions'), ('answer_solutions', 'Answers and solutions'), ('answer_key', 'Answer key'), ('inline_question_answer', 'Question with inline answer'), ('ignored', 'Ignored'), ('unknown', 'Unknown')], db_index=True, default='unknown', max_length=32)),
                ('predicted_role', models.CharField(choices=[('cover', 'Cover'), ('questions', 'Questions'), ('answer_solutions', 'Answers and solutions'), ('answer_key', 'Answer key'), ('inline_question_answer', 'Question with inline answer'), ('ignored', 'Ignored'), ('unknown', 'Unknown')], default='unknown', max_length=32)),
                ('predicted_confidence', models.DecimalField(decimal_places=4, default=0, max_digits=5)),
                ('teacher_confirmed', models.BooleanField(default=False)),
                ('section_key', models.CharField(blank=True, default='', max_length=160)),
                ('expected_number_start', models.PositiveIntegerField(blank=True, null=True)),
                ('expected_number_end', models.PositiveIntegerField(blank=True, null=True)),
                ('fingerprint', models.CharField(blank=True, default='', max_length=64)),
                ('status', models.CharField(choices=[('proposed', 'Proposed'), ('confirmed', 'Confirmed'), ('processing', 'Processing'), ('complete', 'Complete'), ('failed', 'Failed'), ('superseded', 'Superseded')], db_index=True, default='proposed', max_length=16)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('error_code', models.CharField(blank=True, default='', max_length=64)),
                ('error_detail', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('document', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='segments', to='classes.examsourcedocument')),
            ],
            options={'ordering': ['revision', 'order', 'id']},
        ),
        migrations.AddConstraint(
            model_name='examproject',
            constraint=models.UniqueConstraint(fields=('teacher', 'client_request_id'), name='uniq_exam_v4_teacher_request'),
        ),
        migrations.AddConstraint(
            model_name='examproject',
            constraint=models.CheckConstraint(condition=models.Q(('engine_version', 4)), name='exam_v4_engine_version_4'),
        ),
        migrations.AddConstraint(
            model_name='examproject',
            constraint=models.CheckConstraint(condition=models.Q(('revision__gte', 1)), name='exam_v4_revision_gte_1'),
        ),
        migrations.AddIndex(
            model_name='examproject',
            index=models.Index(fields=['teacher', 'status', '-updated_at'], name='exam_v4_owner_status_idx'),
        ),
        migrations.AddIndex(
            model_name='examproject',
            index=models.Index(fields=['organization', 'status', '-updated_at'], name='exam_v4_org_status_idx'),
        ),
        migrations.AddConstraint(
            model_name='examsourcedocument',
            constraint=models.UniqueConstraint(fields=('project', 'client_document_id'), name='uniq_exam_v4_project_document'),
        ),
        migrations.AddConstraint(
            model_name='examsourcedocument',
            constraint=models.UniqueConstraint(fields=('project', 'upload_order'), name='uniq_exam_v4_project_upload_order'),
        ),
        migrations.AddConstraint(
            model_name='examsourcedocument',
            constraint=models.CheckConstraint(condition=models.Q(('classification_revision__gte', 1)), name='exam_v4_doc_revision_gte_1'),
        ),
        migrations.AddIndex(
            model_name='examsourcedocument',
            index=models.Index(fields=['project', 'status', 'upload_order'], name='exam_v4_doc_status_idx'),
        ),
        migrations.AddConstraint(
            model_name='examsourcepage',
            constraint=models.UniqueConstraint(fields=('document', 'page_number'), name='uniq_exam_v4_document_page'),
        ),
        migrations.AddConstraint(
            model_name='examsourcepage',
            constraint=models.CheckConstraint(condition=models.Q(('page_number__gte', 1)), name='exam_v4_page_number_gte_1'),
        ),
        migrations.AddConstraint(
            model_name='examsourcepage',
            constraint=models.CheckConstraint(condition=models.Q(('predicted_confidence__gte', 0), ('predicted_confidence__lte', 1)), name='exam_v4_page_confidence_range'),
        ),
        migrations.AddConstraint(
            model_name='examsourcepage',
            constraint=models.CheckConstraint(condition=~models.Q(('id', models.F('duplicate_of'))), name='exam_v4_page_not_self_duplicate'),
        ),
        migrations.AddIndex(
            model_name='examsourcepage',
            index=models.Index(fields=['document', 'predicted_role', 'page_number'], name='exam_v4_page_role_idx'),
        ),
        migrations.AddConstraint(
            model_name='examsourcesegment',
            constraint=models.UniqueConstraint(fields=('document', 'revision', 'order'), name='uniq_exam_v4_segment_order'),
        ),
        migrations.AddConstraint(
            model_name='examsourcesegment',
            constraint=models.CheckConstraint(condition=models.Q(('revision__gte', 1)), name='exam_v4_segment_revision_gte_1'),
        ),
        migrations.AddConstraint(
            model_name='examsourcesegment',
            constraint=models.CheckConstraint(condition=models.Q(('start_page__gte', 1)), name='exam_v4_segment_start_gte_1'),
        ),
        migrations.AddConstraint(
            model_name='examsourcesegment',
            constraint=models.CheckConstraint(condition=models.Q(('end_page__gte', models.F('start_page'))), name='exam_v4_segment_page_range'),
        ),
        migrations.AddConstraint(
            model_name='examsourcesegment',
            constraint=models.CheckConstraint(condition=models.Q(('predicted_confidence__gte', 0), ('predicted_confidence__lte', 1)), name='exam_v4_segment_conf_range'),
        ),
        migrations.AddConstraint(
            model_name='examsourcesegment',
            constraint=models.CheckConstraint(condition=models.Q(('expected_number_start__isnull', True), ('expected_number_end__isnull', True), ('expected_number_end__gte', models.F('expected_number_start')), _connector='OR'), name='exam_v4_segment_number_range'),
        ),
        migrations.AddIndex(
            model_name='examsourcesegment',
            index=models.Index(fields=['document', 'revision', 'role', 'order'], name='exam_v4_segment_role_idx'),
        ),
        migrations.AddIndex(
            model_name='examsourcesegment',
            index=models.Index(fields=['status', 'updated_at'], name='exam_v4_segment_status_idx'),
        ),
    ]
