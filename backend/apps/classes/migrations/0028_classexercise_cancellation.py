from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classes', '0027_classexercise_intake_config_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='classexercise',
            name='cancel_requested',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='classexercise',
            name='status',
            field=models.CharField(
                choices=[
                    ('draft', 'Draft'),
                    ('extracting', 'Extracting'),
                    ('extracted', 'Extracted'),
                    ('published', 'Published'),
                    ('cancelled', 'Cancelled'),
                    ('failed', 'Failed'),
                ],
                db_index=True,
                default='draft',
                max_length=16,
            ),
        ),
    ]
