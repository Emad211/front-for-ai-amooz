# Wave 6b (2026-08-31): MistakeEntry.resolved_at — when the student closed the
# loop on a mistake. Set on the first is_resolved=True transition in
# services/mistakes.update_mistake, cleared on un-resolve. The RunPython backfill
# fills the column for rows already resolved before it existed, using their
# ``updated_at`` as the best available proxy for when the loop was closed.

from django.db import migrations, models


def backfill_resolved_at(apps, schema_editor):
    MistakeEntry = apps.get_model('advisory', 'MistakeEntry')
    MistakeEntry.objects.filter(
        is_resolved=True, resolved_at__isnull=True,
    ).update(resolved_at=models.F('updated_at'))


class Migration(migrations.Migration):

    dependencies = [
        ('advisory', '0020_parent_links'),
    ]

    operations = [
        migrations.AddField(
            model_name='mistakeentry',
            name='resolved_at',
            field=models.DateTimeField(
                blank=True,
                help_text='لحظهٔ اولین رفع؛ با بازگشتن به حالت رفع‌نشده پاک می‌شود.',
                null=True,
                verbose_name='زمان رفع',
            ),
        ),
        migrations.RunPython(backfill_resolved_at, migrations.RunPython.noop),
    ]
