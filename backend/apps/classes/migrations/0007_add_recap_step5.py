from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classes', '0006_remove_teaching_markdown_and_rename_prereq_teaching'),
    ]

    operations = [
        migrations.AddField(
            model_name='classcreationsession',
            name='recap_markdown',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='classcreationsession',
            name='status',
            field=models.CharField(
                choices=[
                    ('transcribing', 'Transcribing'),
                    ('transcribed', 'Transcribed'),
                    ('structuring', 'Structuring'),
                    ('structured', 'Structured'),
                    ('prereq_extracting', 'Prerequisites: Extracting'),
                    ('prereq_extracted', 'Prerequisites: Extracted'),
                    ('prereq_teaching', 'Prerequisites: Teaching'),
                    ('prereq_taught', 'Prerequisites: Taught'),
                    ('recapping', 'Recap: Generating'),
                    ('recapped', 'Recap: Ready'),
                    ('failed', 'Failed'),
                ],
                default='transcribing',
                max_length=32,
            ),
        ),
    ]
