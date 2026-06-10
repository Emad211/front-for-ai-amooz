# Data migration: promote existing active org admins/deputies (currently the
# platform TEACHER role) to the new distinct MANAGER role. Reversible.
#
# NOTE: renumbered to 0008 for this branch — the original backup numbered this
# 0011 on top of StudyGroup/phone/is_active migrations that are NOT on main.
# Here it depends directly on organizations/0007 + accounts/0004.

from django.db import migrations


def promote_org_admins_to_manager(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    OrganizationMembership = apps.get_model('organizations', 'OrganizationMembership')

    manager_user_ids = list(
        OrganizationMembership.objects
        .filter(org_role__in=['admin', 'deputy'], status='active')
        .values_list('user_id', flat=True)
        .distinct()
    )
    if manager_user_ids:
        User.objects.filter(id__in=manager_user_ids, role='TEACHER').update(role='MANAGER')


def revert_managers_to_teacher(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    User.objects.filter(role='MANAGER').update(role='TEACHER')


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0007_ensure_invitationcode_table'),
        ('accounts', '0004_alter_user_role'),
    ]

    operations = [
        migrations.RunPython(promote_org_admins_to_manager, revert_managers_to_teacher),
    ]
