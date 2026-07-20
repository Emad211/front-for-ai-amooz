import core.storage_backends
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('classes', '0036_backfill_attempt_answer_asset_ids'),
    ]

    operations = [
        migrations.AlterField(
            model_name='studentexerciseanswerasset',
            name='file',
            field=models.FileField(
                storage=core.storage_backends.answer_source_storage,
                upload_to='exercises/answers/sources/',
            ),
        ),
    ]
