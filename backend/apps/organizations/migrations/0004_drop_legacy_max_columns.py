"""Drop ALL legacy columns from organizations_organization.

The production database has accumulated columns that no longer exist in
the Django model (e.g. max_students, max_teachers, subscription_active).
Instead of playing whack-a-mole, this migration dynamically discovers
every column that is NOT part of the current model and drops it.

The authoritative list of model columns is hardcoded here so the
migration is deterministic and reviewable.
"""

from django.db import migrations


# Every column that the Organization model actually defines.
# This MUST be kept in sync with apps.organizations.models.Organization.
_MODEL_COLUMNS = frozenset({
    'id',
    'name',
    'slug',
    'logo',
    'student_capacity',
    'subscription_status',
    'owner_id',          # FK column name in DB
    'description',
    'phone',
    'address',
    'created_at',
    'updated_at',
})

_DROP_ALL_LEGACY_SQL = """
DO $$
DECLARE
    col RECORD;
BEGIN
    FOR col IN
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name   = 'organizations_organization'
          AND column_name NOT IN (
              'id', 'name', 'slug', 'logo',
              'student_capacity', 'subscription_status',
              'owner_id', 'description', 'phone', 'address',
              'created_at', 'updated_at'
          )
    LOOP
        RAISE NOTICE 'Dropping legacy column: %%', col.column_name;
        EXECUTE format(
            'ALTER TABLE organizations_organization DROP COLUMN %I',
            col.column_name
        );
    END LOOP;
END $$;
"""

_NOOP_REVERSE = "SELECT 1;"


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0003_fix_legacy_max_students_default"),
    ]

    operations = [
        migrations.RunSQL(sql=_DROP_ALL_LEGACY_SQL, reverse_sql=_NOOP_REVERSE),
    ]
