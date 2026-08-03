from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('classes', '0040_exam_prep_v4_source_foundation'),
    ]

    operations = [
        migrations.AddField(
            model_name='examsourcedocument',
            name='source_map_fingerprint',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
        migrations.AddField(
            model_name='examsourcedocument',
            name='teacher_confirmed_fingerprint',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
        migrations.AddField(
            model_name='examsourcedocument',
            name='teacher_confirmed_revision',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name='examsourcedocument',
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(teacher_confirmed_revision__isnull=True)
                    | models.Q(teacher_confirmed_revision__gte=1)
                ),
                name='exam_v4_confirmed_revision_gte_1',
            ),
        ),
    ]
