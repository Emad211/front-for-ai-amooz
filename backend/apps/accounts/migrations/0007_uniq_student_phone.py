"""Add the partial unique constraint — one STUDENT per phone.

Split out from 0006 so it runs in its OWN transaction: 0006's cascading deletes
leave pending trigger events on ``accounts_user``, and PostgreSQL refuses to
CREATE INDEX on a table with pending trigger events in the same transaction
(``cannot CREATE INDEX ... because it has pending trigger events``). By the time
this migration runs, 0006 has committed and those events are cleared.

One STUDENT per phone; a phone may still belong to a different-role account, and
NULL phones (non-students / pre-phone accounts) are unconstrained.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_student_phone_unique'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='user',
            constraint=models.UniqueConstraint(
                fields=['phone'],
                condition=models.Q(role='STUDENT', phone__isnull=False),
                name='uniq_student_phone',
            ),
        ),
    ]
