from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classes', '0009_final_exam'),
    ]

    operations = [
        migrations.AddField(
            model_name='classcreationsession',
            name='duration',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
        migrations.AddField(
            model_name='classcreationsession',
            name='level',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
    ]
