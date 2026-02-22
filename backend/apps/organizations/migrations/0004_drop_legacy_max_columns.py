"""Drop legacy max_students / max_teachers columns.

These columns no longer exist in the Django model.  Migration 0003 set
DEFAULT values but some environments still fail because the columns carry
a NOT NULL constraint and PostgreSQL sometimes ignores the DEFAULT.

The definitive fix is to drop the columns entirely.
This migration is idempotent – it only acts when the columns exist.
"""

from django.db import migrations


_DROP_LEGACY_COLUMNS_SQL = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name   = 'organizations_organization'
          AND column_name  = 'max_students'
    ) THEN
        EXECUTE 'ALTER TABLE organizations_organization DROP COLUMN max_students';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name   = 'organizations_organization'
          AND column_name  = 'max_teachers'
    ) THEN
        EXECUTE 'ALTER TABLE organizations_organization DROP COLUMN max_teachers';
    END IF;
END $$;
"""

_NOOP_REVERSE = "SELECT 1;"


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0003_fix_legacy_max_students_default"),
    ]

    operations = [
        migrations.RunSQL(sql=_DROP_LEGACY_COLUMNS_SQL, reverse_sql=_NOOP_REVERSE),
    ]
