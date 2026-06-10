# Add the MANAGER platform role to User.role choices.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_promote_superusers_to_admin'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(
                choices=[
                    ('ADMIN', 'Admin'),
                    ('MANAGER', 'Manager'),
                    ('TEACHER', 'Teacher'),
                    ('STUDENT', 'Student'),
                ],
                default='STUDENT',
                max_length=10,
            ),
        ),
    ]
