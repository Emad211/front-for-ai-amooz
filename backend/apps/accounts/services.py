"""Account-level services shared across apps.

`get_or_create_user_by_phone` is the ONE place that turns a phone number into a
user of a given role. Every phone-based onboarding path (class-invite login and
org-code redemption, for ALL roles) calls it, so they can never diverge into two
users for one human. Created users are passwordless shells — credentials are set
later in the forced onboarding step (apps.accounts CompleteOnboardingView).
"""

from __future__ import annotations

import secrets

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from .models import StudentProfile, TeacherProfile

User = get_user_model()

# Stable, role-prefixed auto-username for the passwordless shell. The user picks
# their real username during onboarding, so this only needs to be unique.
_USERNAME_PREFIX = {
    'STUDENT': 'student',
    'TEACHER': 'teacher',
    'MANAGER': 'manager',
    'ADMIN': 'admin',
}


def _ensure_profile(user: 'User') -> None:
    """Defensively ensure the role's profile row exists.

    A post_save signal already creates it on user creation (MANAGER gets none by
    design); this is a safety net for older/returning rows.
    """
    if user.role == User.Role.STUDENT:
        StudentProfile.objects.get_or_create(user=user)
    elif user.role == User.Role.TEACHER:
        TeacherProfile.objects.get_or_create(user=user)


def get_or_create_user_by_phone(
    phone: str,
    role: str,
    *,
    first_name: str = '',
    last_name: str = '',
    is_freelancer: bool | None = None,
) -> tuple['User', bool]:
    """Return ``(user, created)`` for the account owning ``phone`` in ``role``.

    ``phone`` MUST already be canonical — call
    :func:`apps.commons.phone_utils.normalize_phone` before passing it in.

    A phone may belong to several accounts of *different* roles, so the lookup is
    scoped to ``role``. The created account is a passwordless shell
    (``set_unusable_password``) — onboarding sets the real credentials. Creation
    is atomic and idempotent: if a concurrent request wins the race (username is
    unique, plus the STUDENT ``uniq_student_phone`` constraint), the
    ``IntegrityError`` is caught and the winning row is returned.

    ``is_freelancer`` is applied only on creation when not None (org-created
    teachers/managers are org-only → False).
    """
    existing = User.objects.filter(phone=phone, role=role).first()
    if existing is not None:
        _ensure_profile(existing)
        return existing, False

    prefix = _USERNAME_PREFIX.get(role, 'user')
    base_username = f'{prefix}_{phone}'
    username = base_username
    if User.objects.filter(username=username).exists():
        username = f'{base_username}_{secrets.token_hex(3)}'

    try:
        with transaction.atomic():
            user = User(
                username=username,
                role=role,
                phone=phone,
                first_name=first_name or '',
                last_name=last_name or '',
            )
            if is_freelancer is not None:
                user.is_freelancer = is_freelancer
            user.set_unusable_password()
            user.save()
    except IntegrityError:
        # Lost a concurrent create (same username or, for students, same phone).
        # The winner exists now — return it rather than duplicating/500-ing.
        winner = User.objects.filter(phone=phone, role=role).first()
        if winner is None:
            raise
        _ensure_profile(winner)
        return winner, False

    _ensure_profile(user)
    return user, True


def get_or_create_student_by_phone(
    phone: str,
    *,
    first_name: str = '',
    last_name: str = '',
) -> tuple['User', bool]:
    """Student-scoped wrapper over :func:`get_or_create_user_by_phone`."""
    return get_or_create_user_by_phone(
        phone, User.Role.STUDENT, first_name=first_name, last_name=last_name,
    )
