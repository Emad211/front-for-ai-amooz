from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classes', '0012_add_exam_prep_pipeline'),
    ]

    operations = [
        migrations.CreateModel(
            name='StudentInviteCode',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('phone', models.CharField(max_length=32, unique=True)),
                ('code', models.CharField(max_length=64, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
