"""Drop legacy columns left on organizations_invitationcode and
organizations_organizationmembership by a since-reverted schema (prod drift).

A prior backup-branch schema left a NOT-NULL ``phone`` column on
organizations_invitationcode that the current model doesn't define, so
``provision_organization`` failed with: null value in column "phone" ... violates
not-null constraint. The redeem-code flow writes memberships next, so we repair
that table too (no-op if already clean).

Mirrors 0005_drop_all_legacy_columns. Pure SQL, idempotent, Postgres-only — it
runs on prod; tests use --no-migrations (schema built from models). Each DO-loop
drops only columns NOT in the current model, so a clean table is untouched.
"""

from django.db import migrations


def _drop_legacy_sql(table: str, keep_columns: tuple[str, ...]) -> str:
    keep_list = ", ".join(f"'{c}'" for c in keep_columns)
    return f"""
DO $$
DECLARE
    col RECORD;
BEGIN
    FOR col IN
        SELECT column_name::text AS cname
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name   = '{table}'
          AND column_name NOT IN ({keep_list})
    LOOP
        EXECUTE format(
            'ALTER TABLE {table} DROP COLUMN IF EXISTS %I CASCADE',
            col.cname
        );
    END LOOP;
END $$;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0009_studygroup_studygroupteacher_studygroup_teachers_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql=_drop_legacy_sql(
                "organizations_invitationcode",
                (
                    "id", "code", "organization_id", "target_role",
                    "label", "max_uses", "use_count", "expires_at",
                    "is_active", "created_by_id", "created_at",
                ),
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql=_drop_legacy_sql(
                "organizations_organizationmembership",
                (
                    "id", "user_id", "organization_id", "org_role",
                    "internal_id", "status", "joined_at", "updated_at",
                ),
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
