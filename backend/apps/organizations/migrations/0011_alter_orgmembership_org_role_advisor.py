# Add the ADVISOR (مشاور) value to OrganizationMembership.org_role choices.
#
# Choices-only change: 'advisor' fits the existing max_length=16, so this is a
# pure AlterField with no column rewrite. Landing it now (S1) is what lets the
# org-mode step (S9) ship with ZERO migrations.
#
# InvitationCode.target_role is intentionally NOT widened — an advisor account is
# created by a platform admin, never self-onboarded by an invite code.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0010_drop_legacy_invitationcode_columns'),
    ]

    operations = [
        migrations.AlterField(
            model_name='organizationmembership',
            name='org_role',
            field=models.CharField(
                choices=[
                    ('admin', 'مدیر'),
                    ('deputy', 'معاون'),
                    ('teacher', 'معلم'),
                    ('student', 'دانش‌آموز'),
                    ('advisor', 'مشاور'),
                ],
                default='student',
                max_length=16,
                verbose_name='نقش سازمانی',
            ),
        ),
    ]
