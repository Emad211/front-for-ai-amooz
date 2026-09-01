# Wave 7 (2026-08-31): the official konkur syllabus tree (درخت بودجه‌بندی) —
# SyllabusChapter + SyllabusTopic as catalog tables off Subject, plus the
# optional TopicProgress.syllabus_topic link that lets a coverage row point at
# a tree leaf while its free-text ``topic`` mirrors the leaf's title.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('advisory', '0021_mistakeentry_resolved_at'),
    ]

    operations = [
        migrations.CreateModel(
            name='SyllabusChapter',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='عنوان فصل')),
                ('order', models.PositiveSmallIntegerField(default=0, help_text='جایگاه فصل در نمایش درخت.', verbose_name='ترتیب')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='زمان ایجاد')),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='syllabus_chapters', to='advisory.subject', verbose_name='درس')),
            ],
            options={
                'verbose_name': 'فصل درخت بودجه\u200cبندی',
                'verbose_name_plural': 'فصل\u200cهای درخت بودجه\u200cبندی',
                'ordering': ['subject__name', 'order', 'title'],
            },
        ),
        migrations.CreateModel(
            name='SyllabusTopic',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='عنوان مبحث')),
                ('order', models.PositiveSmallIntegerField(default=0, help_text='جایگاه مبحث در فصل.', verbose_name='ترتیب')),
                ('konkur_weight', models.PositiveSmallIntegerField(blank=True, help_text='تعداد تقریبی سؤالات کنکور از این مبحث.', null=True, verbose_name='وزن کنکوری')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='زمان ایجاد')),
                ('chapter', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='syllabus_topics', to='advisory.syllabuschapter', verbose_name='فصل')),
            ],
            options={
                'verbose_name': 'مبحث درخت بودجه\u200cبندی',
                'verbose_name_plural': 'مباحث درخت بودجه\u200cبندی',
                'ordering': ['chapter__order', 'order', 'title'],
            },
        ),
        migrations.AddField(
            model_name='topicprogress',
            name='syllabus_topic',
            field=models.ForeignKey(blank=True, help_text='پیوند اختیاری به درخت بودجه\u200cبندی؛ خالی یعنی متن آزاد.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='progress_rows', to='advisory.syllabustopic', verbose_name='مبحث درخت بودجه\u200cبندی'),
        ),
        migrations.AddConstraint(
            model_name='syllabuschapter',
            constraint=models.UniqueConstraint(fields=('subject', 'title'), name='uniq_syllabus_chapter_per_subject', violation_error_message='این فصل برای این درس از قبل ثبت شده است.'),
        ),
        migrations.AddConstraint(
            model_name='syllabustopic',
            constraint=models.UniqueConstraint(fields=('chapter', 'title'), name='uniq_syllabus_topic_per_chapter', violation_error_message='این مبحث در این فصل از قبل ثبت شده است.'),
        ),
    ]
