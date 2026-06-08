"""Drop the legacy ``is_active`` column from organizations_organizationmembership.

The membership model originally carried a boolean ``is_active``; it was later
replaced by the ``status`` CharField (active/suspended) but the old column was
never dropped on already-migrated databases. Because it is ``NOT NULL`` with no
default and is absent from the current model, every ORM insert of a membership
(redeeming an invite code, adding a member, onboarding a manager) fails on those
databases with ``null value in column "is_active" ... violates not-null``.
Fresh/test DBs built from the models don't have the column, which is why this
went unnoticed in the test suite.

Idempotent: drops the column only if it still exists.
"""

from django.db import migrations


_DROP_SQL = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'organizations_organizationmembership'
          AND column_name = 'is_active'
    ) THEN
        ALTER TABLE organizations_organizationmembership DROP COLUMN is_active CASCADE;
    END IF;
END $$;
"""


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0009_invitationcode_phone'),
    ]

    operations = [
        migrations.RunSQL(sql=_DROP_SQL, reverse_sql=migrations.RunSQL.noop),
    ]
