"""Fix legacy organizations.max_students schema drift.

Some production databases still contain an old `max_students` column on
`organizations_organization` that is NOT NULL and has no DEFAULT.
The current model no longer writes to that column, so inserts fail with
`null value in column "max_students" violates not-null constraint`.

This migration is idempotent and only applies changes when the legacy
column exists.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0002_add_missing_columns"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'organizations_organization'
                      AND column_name = 'max_students'
                ) THEN
                    -- Ensure future inserts do not fail when ORM does not provide this legacy field.
                    EXECUTE 'ALTER TABLE organizations_organization ALTER COLUMN max_students SET DEFAULT 100';

                    -- Keep legacy values aligned with the modern column where possible.
                    EXECUTE '
                        UPDATE organizations_organization
                        SET max_students = COALESCE(max_students, student_capacity, 100)
                        WHERE max_students IS NULL
                    ';
                END IF;
            END $$;
            """,
            reverse_sql="""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'organizations_organization'
                      AND column_name = 'max_students'
                ) THEN
                    EXECUTE 'ALTER TABLE organizations_organization ALTER COLUMN max_students DROP DEFAULT';
                END IF;
            END $$;
            """,
        ),
    ]
