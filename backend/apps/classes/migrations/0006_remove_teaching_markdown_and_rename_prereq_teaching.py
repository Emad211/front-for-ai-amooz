from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classes', '0005_normalized_structure_and_prerequisites'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='classunit',
            name='teaching_markdown',
        ),
        migrations.RenameField(
            model_name='classprerequisite',
            old_name='teaching_markdown',
            new_name='teaching_text',
        ),
    ]
