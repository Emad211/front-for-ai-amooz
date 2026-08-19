# Add the ADVISOR (مشاور) platform role to User.role choices.
#
# Choices-only change: 'ADVISOR' is 7 chars and fits the existing max_length=10,
# so no column alteration and no expand-then-contract is needed. Same shape as
# 0004_alter_user_role (which added MANAGER).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_uniq_student_phone'),
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
                ],
                default='STUDENT',
                max_length=10,
            ),
        ),
    ]
