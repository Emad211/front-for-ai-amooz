from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('classes', '0004_publish_and_invites'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClassLearningObjective',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveIntegerField()),
                ('text', models.TextField()),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='learning_objectives', to='classes.classcreationsession')),
            ],
            options={
                'constraints': [
                    models.UniqueConstraint(fields=('session', 'order'), name='uniq_class_objective_session_order'),
                ],
            },
        ),
        migrations.CreateModel(
            name='ClassSection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('external_id', models.CharField(max_length=128)),
                ('order', models.PositiveIntegerField()),
                ('title', models.CharField(max_length=255)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sections', to='classes.classcreationsession')),
            ],
            options={
                'constraints': [
                    models.UniqueConstraint(fields=('session', 'external_id'), name='uniq_class_section_session_external_id'),
                ],
            },
        ),
        migrations.CreateModel(
            name='ClassUnit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('external_id', models.CharField(max_length=128)),
                ('order', models.PositiveIntegerField()),
                ('title', models.CharField(max_length=255)),
                ('merrill_type', models.CharField(blank=True, max_length=64)),
                ('source_markdown', models.TextField(blank=True)),
                ('content_markdown', models.TextField(blank=True)),
                ('teaching_markdown', models.TextField(blank=True)),
                ('image_ideas', models.JSONField(blank=True, default=list)),
                ('section', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='units', to='classes.classsection')),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='units', to='classes.classcreationsession')),
            ],
            options={
                'constraints': [
                    models.UniqueConstraint(fields=('session', 'external_id'), name='uniq_class_unit_session_external_id'),
                ],
            },
        ),
        migrations.CreateModel(
            name='ClassPrerequisite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveIntegerField()),
                ('name', models.CharField(max_length=255)),
                ('teaching_markdown', models.TextField(blank=True)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='prerequisites', to='classes.classcreationsession')),
            ],
            options={
                'constraints': [
                    models.UniqueConstraint(fields=('session', 'order'), name='uniq_class_prereq_session_order'),
                    models.UniqueConstraint(fields=('session', 'name'), name='uniq_class_prereq_session_name'),
                ],
            },
        ),
    ]
