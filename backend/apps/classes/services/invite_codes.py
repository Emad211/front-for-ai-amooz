import uuid

from django.db import IntegrityError, transaction

from apps.classes.models import StudentInviteCode
from apps.classes.models import ClassInvitation


def get_or_create_invite_code_for_phone(phone: str) -> str:
    """Return a stable invite code for a given phone.

    - If it already exists, returns the stored code.
    - Otherwise creates one and returns it.

    The code is globally unique, and *stable* for the phone.
    """

    normalized_phone = (phone or '').strip()
    if not normalized_phone:
        raise ValueError('Phone is required to create invite code.')

    existing = StudentInviteCode.objects.filter(phone=normalized_phone).only('code').first()
    if existing is not None:
        return existing.code

    # Backward compatibility: if the phone was already invited before we introduced
    # StudentInviteCode, keep using the earliest known invite_code for that phone.
    legacy = (
        ClassInvitation.objects.filter(phone=normalized_phone)
        .only('invite_code', 'created_at')
        .order_by('created_at', 'id')
        .first()
    )
    if legacy is not None and (legacy.invite_code or '').strip():
        legacy_code = legacy.invite_code.strip()
        try:
            with transaction.atomic():
                obj, _created = StudentInviteCode.objects.get_or_create(
                    phone=normalized_phone,
                    defaults={'code': legacy_code},
                )
                return obj.code
        except IntegrityError:
            # If legacy_code is already taken by another phone (bad legacy data),
            # fall back to generating a new globally-unique code.
            pass

    # Generate with a short prefix. Must be consistent across pipelines.
    # Note: length <= 64 and still reasonably short for manual entry.
    tries = 0
    while True:
        tries += 1
        code = f"INV-{uuid.uuid4().hex[:10].upper()}"

        try:
            with transaction.atomic():
                obj, created = StudentInviteCode.objects.get_or_create(
                    phone=normalized_phone,
                    defaults={'code': code},
                )
                return obj.code
        except IntegrityError:
            # Collision on code or phone due to concurrent request.
            # Retry a couple times; in worst case, raise.
            if tries >= 10:
                raise
