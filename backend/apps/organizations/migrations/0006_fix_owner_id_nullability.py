"""Fix owner_id nullability drift on organizations_organization.

Some production databases have owner_id as NOT NULL while the model defines
`owner = ForeignKey(..., null=True, blank=True, on_delete=SET_NULL)`.

This migration makes owner_id nullable and drops any default to align DB schema
with the Django model in an idempotent way.
"""

from django.db import migrations


_SQL = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'organizations_organization'
          AND column_name = 'owner_id'
    ) THEN
        ALTER TABLE organizations_organization
            ALTER COLUMN owner_id DROP NOT NULL;

        ALTER TABLE organizations_organization
            ALTER COLUMN owner_id DROP DEFAULT;
    END IF;
END $$;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0005_drop_all_legacy_columns"),
    ]

    operations = [
        migrations.RunSQL(sql=_SQL, reverse_sql=migrations.RunSQL.noop),
    ]
