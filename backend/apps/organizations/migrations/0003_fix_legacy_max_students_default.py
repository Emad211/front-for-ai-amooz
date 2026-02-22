"""Fix legacy organizations.max_students / max_teachers schema drift.

Some production databases still contain old `max_students` and/or
`max_teachers` columns on `organizations_organization` that are NOT NULL
and have no DEFAULT.  The current model no longer writes to these
columns, so inserts fail with
  ``null value in column "max_students" violates not-null constraint``
  ``null value in column "max_teachers" violates not-null constraint``

This migration is idempotent and only applies changes when the legacy
columns exist.
"""

from django.db import migrations


_FIX_LEGACY_COLUMNS_SQL = """
DO $$
BEGIN
    -- max_students -----------------------------------------------------------
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name  = 'organizations_organization'
          AND column_name = 'max_students'
    ) THEN
        EXECUTE 'ALTER TABLE organizations_organization ALTER COLUMN max_students SET DEFAULT 100';
        EXECUTE '
            UPDATE organizations_organization
            SET max_students = COALESCE(max_students, student_capacity, 100)
            WHERE max_students IS NULL
        ';
    END IF;

    -- max_teachers -----------------------------------------------------------
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name  = 'organizations_organization'
          AND column_name = 'max_teachers'
    ) THEN
        EXECUTE 'ALTER TABLE organizations_organization ALTER COLUMN max_teachers SET DEFAULT 50';
        EXECUTE '
            UPDATE organizations_organization
            SET max_teachers = COALESCE(max_teachers, 50)
            WHERE max_teachers IS NULL
        ';
    END IF;
END $$;
"""

_REVERSE_SQL = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name  = 'organizations_organization'
          AND column_name = 'max_students'
    ) THEN
        EXECUTE 'ALTER TABLE organizations_organization ALTER COLUMN max_students DROP DEFAULT';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name  = 'organizations_organization'
          AND column_name = 'max_teachers'
    ) THEN
        EXECUTE 'ALTER TABLE organizations_organization ALTER COLUMN max_teachers DROP DEFAULT';
    END IF;
END $$;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0002_add_missing_columns"),
    ]

    operations = [
        migrations.RunSQL(sql=_FIX_LEGACY_COLUMNS_SQL, reverse_sql=_REVERSE_SQL),
    ]
