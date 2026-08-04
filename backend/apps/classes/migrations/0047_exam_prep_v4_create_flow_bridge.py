from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('classes', '0046_exam_prep_v4_legacy_projection'),
    ]

    operations = [
        migrations.AddField(
            model_name='examproject',
            name='legacy_session',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='source_aware_exam_project',
                to='classes.classcreationsession',
            ),
        ),
    ]
