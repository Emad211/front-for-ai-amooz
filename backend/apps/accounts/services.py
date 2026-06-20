"""Account-level services shared across apps.

`get_or_create_student_by_phone` is the ONE place that turns a phone number into
a STUDENT user. Both phone-based onboarding paths (class-invite login and org-code
redemption) call it, so they can never diverge into two users for one human.
"""

from __future__ import annotations

import secrets

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from .models import StudentProfile

User = get_user_model()


def get_or_create_student_by_phone(
    phone: str,
    *,
    first_name: str = '',
    last_name: str = '',
) -> tuple['User', bool]:
    """Return ``(user, created)`` for the STUDENT account owning ``phone``.

    ``phone`` MUST already be canonical — call
    :func:`apps.commons.phone_utils.normalize_phone` before passing it in.

    A phone may belong to several accounts of *different* roles, so the lookup is
    scoped to ``role=STUDENT``. Students are passwordless
    (``set_unusable_password``). Creation is atomic and idempotent: if a
    concurrent request wins the race (username unique today, plus the Phase B
    ``uniq_student_phone`` constraint), the ``IntegrityError`` is caught and the
    winning row is returned instead of raising or duplicating.
    """
    existing = User.objects.filter(phone=phone, role=User.Role.STUDENT).first()
    if existing is not None:
        StudentProfile.objects.get_or_create(user=existing)
        return existing, False

    base_username = f'student_{phone}'
    username = base_username
    # Username is globally unique; derive a stable one, suffix on collision.
    if User.objects.filter(username=username).exists():
        username = f'{base_username}_{secrets.token_hex(3)}'

    try:
        with transaction.atomic():
            user = User(
                username=username,
                role=User.Role.STUDENT,
                phone=phone,
                first_name=first_name or '',
                last_name=last_name or '',
            )
            user.set_unusable_password()
            user.save()
    except IntegrityError:
        # Lost a concurrent create (same username or, post-Phase-B, same phone).
        # The winner exists now — return it rather than duplicating/500-ing.
        winner = User.objects.filter(phone=phone, role=User.Role.STUDENT).first()
        if winner is None:
            raise
        StudentProfile.objects.get_or_create(user=winner)
        return winner, False

    StudentProfile.objects.get_or_create(user=user)
    return user, True
