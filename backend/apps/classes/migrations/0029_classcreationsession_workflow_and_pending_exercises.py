from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classes', '0028_classexercise_cancellation'),
    ]

    operations = [
        migrations.AddField(
            model_name='classcreationsession',
            name='pending_exercises',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='classcreationsession',
            name='review_ready_notified_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='classcreationsession',
            name='workflow_state',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
