"""Add columns that may be missing from production DB.

The initial migration (0001_initial) was edited in-place after it had
already been applied to production, so the production tables are missing
several columns that the current model defines.  This migration uses
idempotent ``IF NOT EXISTS`` / ``IF EXISTS`` SQL so it is safe to run on
both old databases (where columns are missing) and new databases (where
0001_initial already created them).
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0001_initial"),
    ]

    operations = [
        # ── Organization table ────────────────────────────────────────
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'organizations_organization'
                      AND column_name = 'student_capacity'
                ) THEN
                    ALTER TABLE organizations_organization
                        ADD COLUMN student_capacity integer NOT NULL DEFAULT 100;
                END IF;
            END $$;
            """,
            reverse_sql="""
            ALTER TABLE organizations_organization
                DROP COLUMN IF EXISTS student_capacity;
            """,
        ),
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'organizations_organization'
                      AND column_name = 'subscription_status'
                ) THEN
                    ALTER TABLE organizations_organization
                        ADD COLUMN subscription_status varchar(16) NOT NULL DEFAULT 'active';
                    CREATE INDEX IF NOT EXISTS idx_org_subscription_status
                        ON organizations_organization (subscription_status);
                END IF;
            END $$;
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS idx_org_subscription_status;
            ALTER TABLE organizations_organization
                DROP COLUMN IF EXISTS subscription_status;
            """,
        ),
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'organizations_organization'
                      AND column_name = 'description'
                ) THEN
                    ALTER TABLE organizations_organization
                        ADD COLUMN description text NOT NULL DEFAULT '';
                END IF;
            END $$;
            """,
            reverse_sql="""
            ALTER TABLE organizations_organization
                DROP COLUMN IF EXISTS description;
            """,
        ),
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'organizations_organization'
                      AND column_name = 'phone'
                ) THEN
                    ALTER TABLE organizations_organization
                        ADD COLUMN phone varchar(20) NOT NULL DEFAULT '';
                END IF;
            END $$;
            """,
            reverse_sql="""
            ALTER TABLE organizations_organization
                DROP COLUMN IF EXISTS phone;
            """,
        ),
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'organizations_organization'
                      AND column_name = 'address'
                ) THEN
                    ALTER TABLE organizations_organization
                        ADD COLUMN address text NOT NULL DEFAULT '';
                END IF;
            END $$;
            """,
            reverse_sql="""
            ALTER TABLE organizations_organization
                DROP COLUMN IF EXISTS address;
            """,
        ),

        # ── OrganizationMembership table ──────────────────────────────
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'organizations_organizationmembership'
                      AND column_name = 'internal_id'
                ) THEN
                    ALTER TABLE organizations_organizationmembership
                        ADD COLUMN internal_id varchar(64) NOT NULL DEFAULT '';
                END IF;
            END $$;
            """,
            reverse_sql="""
            ALTER TABLE organizations_organizationmembership
                DROP COLUMN IF EXISTS internal_id;
            """,
        ),
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'organizations_organizationmembership'
                      AND column_name = 'status'
                ) THEN
                    ALTER TABLE organizations_organizationmembership
                        ADD COLUMN status varchar(16) NOT NULL DEFAULT 'active';
                    CREATE INDEX IF NOT EXISTS idx_orgmembership_status
                        ON organizations_organizationmembership (status);
                END IF;
            END $$;
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS idx_orgmembership_status;
            ALTER TABLE organizations_organizationmembership
                DROP COLUMN IF EXISTS status;
            """,
        ),
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'organizations_organizationmembership'
                      AND column_name = 'updated_at'
                ) THEN
                    ALTER TABLE organizations_organizationmembership
                        ADD COLUMN updated_at timestamptz NOT NULL DEFAULT NOW();
                END IF;
            END $$;
            """,
            reverse_sql="""
            ALTER TABLE organizations_organizationmembership
                DROP COLUMN IF EXISTS updated_at;
            """,
        ),
    ]
