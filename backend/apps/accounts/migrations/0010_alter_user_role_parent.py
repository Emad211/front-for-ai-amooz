# Add the PARENT (والد) platform role to User.role choices (wave 5, 2026-08-31).
#
# Choices-only change: 'PARENT' is 6 chars and fits the existing max_length=10,
# so no column alteration is needed. Same shape as 0008_alter_user_role_advisor
# (which added ADVISOR) and 0004_alter_user_role (which added MANAGER).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0009_alter_studentprofile_grade_and_more'),
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
                    ('ADVISOR', 'Advisor'),
                    ('PARENT', 'Parent'),
                ],
                default='STUDENT',
                max_length=10,
            ),
        ),
    ]
