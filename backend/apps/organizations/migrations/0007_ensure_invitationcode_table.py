"""Self-healing migration: ensure organizations_invitationcode table exists.

Production drift can mark 0001 as applied while the InvitationCode table is
missing. This migration creates the table only when absent, using Django's
schema editor so DB types/constraints are generated correctly.
"""

from django.db import migrations


def ensure_invitationcode_table(apps, schema_editor):
    InvitationCode = apps.get_model("organizations", "InvitationCode")
    table_name = InvitationCode._meta.db_table
    existing_tables = set(schema_editor.connection.introspection.table_names())

    if table_name not in existing_tables:
        schema_editor.create_model(InvitationCode)


def noop_reverse(apps, schema_editor):
    # no-op: do not drop table in reverse to avoid destructive rollback
    return


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0006_fix_owner_id_nullability"),
    ]

    operations = [
        migrations.RunPython(ensure_invitationcode_table, noop_reverse),
    ]
