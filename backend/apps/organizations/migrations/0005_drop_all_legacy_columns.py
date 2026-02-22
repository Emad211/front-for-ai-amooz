"""Drop every column from organizations_organization that is not in
the current Django model.  Pure SQL, no PL/pgSQL RAISE, no f-strings.
"""

from django.db import migrations


_SQL = """
DO $$
DECLARE
    col RECORD;
BEGIN
    FOR col IN
        SELECT column_name::text AS cname
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
        EXECUTE format(
            'ALTER TABLE organizations_organization DROP COLUMN IF EXISTS %I CASCADE',
            col.cname
        );
    END LOOP;
END $$;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0004_drop_legacy_max_columns"),
    ]

    operations = [
        migrations.RunSQL(sql=_SQL, reverse_sql=migrations.RunSQL.noop),
    ]
