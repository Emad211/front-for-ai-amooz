from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classes', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='classcreationsession',
            name='structure_json',
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
                    ('failed', 'Failed'),
                ],
                default='transcribing',
                max_length=32,
            ),
        ),
    ]
