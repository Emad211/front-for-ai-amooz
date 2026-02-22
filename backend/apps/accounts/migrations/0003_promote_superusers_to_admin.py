"""Data migration: set role='ADMIN' on every existing superuser / staff user
whose role is still the default 'STUDENT'.  This is a one-time fix – the
creation signal now handles future superusers automatically."""

from django.db import migrations


def promote_superusers(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    updated = User.objects.filter(
        is_superuser=True, role="STUDENT"
    ).update(role="ADMIN")
    if updated:
        print(f"\n  ↳ Promoted {updated} superuser(s) to role=ADMIN")

    updated_staff = User.objects.filter(
        is_staff=True, role="STUDENT"
    ).exclude(is_superuser=True).update(role="ADMIN")
    if updated_staff:
        print(f"  ↳ Promoted {updated_staff} staff user(s) to role=ADMIN")


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_adminprofile_location_studentprofile_location_and_more"),
    ]

    operations = [
        migrations.RunPython(promote_superusers, migrations.RunPython.noop),
    ]
