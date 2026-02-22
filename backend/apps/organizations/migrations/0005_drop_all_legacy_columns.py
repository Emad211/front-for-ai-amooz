"""Comprehensive cleanup: drop every column in organizations_organization
that is NOT part of the current Django model.

Why this migration exists
─────────────────────────
The production database accumulated columns from earlier model revisions
(max_students, max_teachers, subscription_active, etc.) that are no
longer declared in ``apps.organizations.models.Organization``.  Because
Django does not write to these columns, INSERT statements leave them
NULL, which triggers NOT-NULL constraint violations.

Migration 0004 attempted the same fix but was edited in-place after it
had already been applied, so Django skipped the updated SQL.  This
migration (0005) is a fresh file that will always be picked up.

Strategy
────────
Instead of listing known-bad columns one by one, we enumerate the DB
table and drop every column whose name is NOT in the authoritative
allowlist below.  This makes the migration immune to any future
schema-drift columns that may appear.

The allowlist is derived from the model fields as of this writing.
"""

from django.db import migrations


# ── Authoritative column allowlist ──────────────────────────────────────
# Every column the Organization model actually maps to in the DB.
# If you add a field to the model, add its db_column here too.
_ALLOWED_COLUMNS = (
    'id',
    'name',
    'slug',
    'logo',
    'student_capacity',
    'subscription_status',
    'owner_id',
    'description',
    'phone',
    'address',
    'created_at',
    'updated_at',
)

# Build the IN-list for SQL safely (all values are hardcoded strings).
_in_list = ", ".join(f"'{c}'" for c in _ALLOWED_COLUMNS)

_SQL = f"""
DO $$
DECLARE
    col RECORD;
    dropped INT := 0;
BEGIN
    FOR col IN
        SELECT column_name::text AS cname
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name   = 'organizations_organization'
          AND column_name NOT IN ({_in_list})
    LOOP
        RAISE NOTICE 'organizations_organization: dropping legacy column "%%"', col.cname;
        EXECUTE format(
            'ALTER TABLE organizations_organization DROP COLUMN IF EXISTS %I CASCADE',
            col.cname
        );
        dropped := dropped + 1;
    END LOOP;

    IF dropped = 0 THEN
        RAISE NOTICE 'organizations_organization: no legacy columns found — table is clean';
    ELSE
        RAISE NOTICE 'organizations_organization: dropped %% legacy column(s)', dropped;
    END IF;
END $$;
"""

_NOOP_REVERSE = "SELECT 1;  -- reverse is a no-op; columns were orphaned anyway"


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0004_drop_legacy_max_columns"),
    ]

    operations = [
        migrations.RunSQL(sql=_SQL, reverse_sql=_NOOP_REVERSE),
    ]
