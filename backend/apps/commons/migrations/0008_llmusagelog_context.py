from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('commons', '0007_exercise_reference_ingest_feature'),
    ]

    operations = [
        migrations.AddField(
            model_name='llmusagelog',
            name='context',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
