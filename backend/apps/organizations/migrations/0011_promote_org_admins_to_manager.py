"""Data migration: promote existing org admins/deputies to the new MANAGER role.

Before this change org admins/deputies were redeemed as platform-role TEACHER.
The MANAGER role now exists as a distinct identity (an org manager is NOT a
teacher), so any user who is an ACTIVE org admin/deputy and is currently a
TEACHER is promoted to MANAGER. Students and platform admins are left untouched,
and a TEACHER who is *not* an org admin/deputy is left as a teacher.
"""
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
        # Only flip TEACHER → MANAGER; never touch ADMIN/STUDENT accounts.
        User.objects.filter(id__in=manager_user_ids, role='TEACHER').update(role='MANAGER')


def revert_managers_to_teacher(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    User.objects.filter(role='MANAGER').update(role='TEACHER')


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0010_drop_membership_legacy_is_active'),
        ('accounts', '0004_alter_user_role'),
    ]

    operations = [
        migrations.RunPython(promote_org_admins_to_manager, revert_managers_to_teacher),
    ]
