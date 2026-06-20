"""Clean slate + enforce one STUDENT per phone.

The phone number is the platform's student identity key, but it had no DB
uniqueness, which let one human become two ``User`` rows. Per the product owner
the existing data is disposable, so this migration takes a clean slate — it
deletes every non-admin user (cascading their classes/enrollments/attempts/
memberships) and then adds the partial unique constraint. On a fresh database
there are no users yet, so the wipe is a harmless no-op.
"""

from django.db import migrations, models
from django.db.models import Q


def wipe_non_admin_users(apps, schema_editor):
    """Keep only the main admin(s); delete everyone else (one-time clean slate)."""
    User = apps.get_model('accounts', 'User')
    keep = Q(is_superuser=True) | Q(role='ADMIN')
    doomed = User.objects.exclude(keep)
    count = doomed.count()
    # .delete() cascades through the ORM collector (memberships, classes,
    # enrollments, quiz/exam attempts, chat threads, notifications, …).
    doomed.delete()
    # Surviving accounts are the platform admin(s) — already set up with real
    # credentials, NOT code-onboarded passwordless shells. Mark them completed so
    # the forced-onboarding gate never bounces them.
    User.objects.update(is_profile_completed=True)
    if count:
        print(f"[accounts.0006] clean slate: deleted {count} non-admin user(s).")


def canonicalize_remaining_phones(apps, schema_editor):
    """Canonicalize any phone on the surviving admin accounts."""
    from apps.commons.phone_utils import normalize_phone

    User = apps.get_model('accounts', 'User')
    for u in User.objects.exclude(phone__isnull=True).exclude(phone=''):
        norm = normalize_phone(u.phone)
        if norm != (u.phone or ''):
            u.phone = norm or None
            u.save(update_fields=['phone'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_user_is_freelancer'),
    ]

    operations = [
        migrations.RunPython(wipe_non_admin_users, noop),
        migrations.RunPython(canonicalize_remaining_phones, noop),
        migrations.AddConstraint(
            model_name='user',
            constraint=models.UniqueConstraint(
                fields=['phone'],
                condition=models.Q(role='STUDENT', phone__isnull=False),
                name='uniq_student_phone',
            ),
        ),
    ]
