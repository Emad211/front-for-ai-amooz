from django.db import migrations, models
import django.db.models.deletion
from django.db.models import F, Q


class Migration(migrations.Migration):
    dependencies = [
        ('classes', '0042_exam_prep_v4_virtual_page_order'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExamSourceBlock',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('revision', models.PositiveIntegerField(default=1)),
                ('order', models.PositiveIntegerField(default=0)),
                ('kind', models.CharField(choices=[('question', 'Question'), ('answer_solution', 'Answer and solution'), ('answer_key', 'Answer key'), ('inline_question_answer', 'Inline question and answer'), ('continuation', 'Continuation candidate'), ('ignored', 'Ignored'), ('unknown', 'Unknown')], db_index=True, default='unknown', max_length=32)),
                ('printed_number', models.CharField(blank=True, default='', max_length=64)),
                ('confidence', models.DecimalField(decimal_places=4, default=0, max_digits=5)),
                ('source_map_fingerprint', models.CharField(db_index=True, max_length=64)),
                ('set_fingerprint', models.CharField(db_index=True, max_length=64)),
                ('fingerprint', models.CharField(db_index=True, max_length=64)),
                ('status', models.CharField(choices=[('accepted', 'Accepted'), ('superseded', 'Superseded'), ('failed', 'Failed')], db_index=True, default='accepted', max_length=16)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('error_code', models.CharField(blank=True, default='', max_length=64)),
                ('error_detail', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('continuation_of', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='continuations', to='classes.examsourceblock')),
                ('document', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='source_blocks', to='classes.examsourcedocument')),
                ('segment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='source_blocks', to='classes.examsourcesegment')),
            ],
            options={
                'ordering': ['revision', 'order', 'id'],
            },
        ),
        migrations.CreateModel(
            name='ExamSourceBlockFragment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveIntegerField(default=0)),
                ('x0', models.DecimalField(decimal_places=6, max_digits=7)),
                ('y0', models.DecimalField(decimal_places=6, max_digits=7)),
                ('x1', models.DecimalField(decimal_places=6, max_digits=7)),
                ('y1', models.DecimalField(decimal_places=6, max_digits=7)),
                ('column_index', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('is_continuation', models.BooleanField(default=False)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('block', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='fragments', to='classes.examsourceblock')),
                ('page', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='block_fragments', to='classes.examsourcepage')),
            ],
            options={
                'ordering': ['order', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='examsourceblock',
            constraint=models.UniqueConstraint(fields=('document', 'revision', 'order'), name='uniq_exam_v4_block_order'),
        ),
        migrations.AddConstraint(
            model_name='examsourceblock',
            constraint=models.CheckConstraint(condition=Q(revision__gte=1), name='exam_v4_block_revision_gte_1'),
        ),
        migrations.AddConstraint(
            model_name='examsourceblock',
            constraint=models.CheckConstraint(condition=Q(confidence__gte=0) & Q(confidence__lte=1), name='exam_v4_block_confidence_range'),
        ),
        migrations.AddConstraint(
            model_name='examsourceblock',
            constraint=models.CheckConstraint(condition=~Q(id=F('continuation_of')), name='exam_v4_block_not_self_continuation'),
        ),
        migrations.AddIndex(
            model_name='examsourceblock',
            index=models.Index(fields=['document', 'source_map_fingerprint', 'status', 'order'], name='exam_v4_block_current_idx'),
        ),
        migrations.AddIndex(
            model_name='examsourceblock',
            index=models.Index(fields=['segment', 'kind', 'order'], name='exam_v4_block_segment_idx'),
        ),
        migrations.AddConstraint(
            model_name='examsourceblockfragment',
            constraint=models.UniqueConstraint(fields=('block', 'order'), name='uniq_exam_v4_block_fragment_order'),
        ),
        migrations.AddConstraint(
            model_name='examsourceblockfragment',
            constraint=models.CheckConstraint(condition=Q(x0__gte=0) & Q(x0__lte=1), name='exam_v4_fragment_x0_range'),
        ),
        migrations.AddConstraint(
            model_name='examsourceblockfragment',
            constraint=models.CheckConstraint(condition=Q(y0__gte=0) & Q(y0__lte=1), name='exam_v4_fragment_y0_range'),
        ),
        migrations.AddConstraint(
            model_name='examsourceblockfragment',
            constraint=models.CheckConstraint(condition=Q(x1__gte=0) & Q(x1__lte=1), name='exam_v4_fragment_x1_range'),
        ),
        migrations.AddConstraint(
            model_name='examsourceblockfragment',
            constraint=models.CheckConstraint(condition=Q(y1__gte=0) & Q(y1__lte=1), name='exam_v4_fragment_y1_range'),
        ),
        migrations.AddConstraint(
            model_name='examsourceblockfragment',
            constraint=models.CheckConstraint(condition=Q(x1__gt=F('x0')), name='exam_v4_fragment_positive_width'),
        ),
        migrations.AddConstraint(
            model_name='examsourceblockfragment',
            constraint=models.CheckConstraint(condition=Q(y1__gt=F('y0')), name='exam_v4_fragment_positive_height'),
        ),
        migrations.AddIndex(
            model_name='examsourceblockfragment',
            index=models.Index(fields=['page', 'order'], name='exam_v4_fragment_page_idx'),
        ),
    ]
