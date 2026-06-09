import uuid
from typing import Iterable

from django.db import IntegrityError, transaction

from apps.classes.models import StudentInviteCode
from apps.classes.models import ClassInvitation


def _generate_invite_code() -> str:
    """A globally-unique, manually-typeable invite code (<= 64 chars)."""
    return f"INV-{uuid.uuid4().hex[:10].upper()}"


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
        code = _generate_invite_code()

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


def get_or_create_invite_codes_for_phones(phones: Iterable[str]) -> dict[str, str]:
    """Batched form of :func:`get_or_create_invite_code_for_phone`.

    Returns ``{normalized_phone: code}`` for every non-empty input phone, creating
    any missing ``StudentInviteCode`` rows in a CONSTANT number of queries instead
    of the O(N) the per-phone helper costs when called in a loop. Same contract:
    stable per phone, globally-unique codes, and backward-compatible reuse of a
    phone's earliest legacy ``ClassInvitation.invite_code`` when no
    ``StudentInviteCode`` exists yet.

    Use this anywhere a set of phones needs codes at once (bulk invite, teacher
    roster). Falls back to the per-phone helper only for the rare phone whose
    legacy code collides with an existing code.
    """
    # Normalize + de-dupe, preserving first-seen order.
    normalized: list[str] = []
    seen: set[str] = set()
    for p in phones:
        n = (p or '').strip()
        if n and n not in seen:
            seen.add(n)
            normalized.append(n)

    result: dict[str, str] = {}
    if not normalized:
        return result

    # 1) Existing codes — one query.
    for obj in StudentInviteCode.objects.filter(phone__in=normalized).only('phone', 'code'):
        result[obj.phone] = obj.code
    missing = [p for p in normalized if p not in result]
    if not missing:
        return result

    # 2) Earliest legacy invite_code per still-missing phone — one query.
    legacy_by_phone: dict[str, str] = {}
    for row in (
        ClassInvitation.objects.filter(phone__in=missing)
        .exclude(invite_code='')
        .order_by('phone', 'created_at', 'id')
        .values('phone', 'invite_code')
    ):
        p = row['phone']
        if p not in legacy_by_phone:
            code = (row['invite_code'] or '').strip()
            if code:
                legacy_by_phone[p] = code

    # 3) Insert all missing rows in one shot: reuse the legacy code when present,
    #    else generate a unique one. ignore_conflicts drops any row whose phone
    #    was concurrently inserted or whose legacy code collides with an existing
    #    code; we reconcile both below.
    to_create = [
        StudentInviteCode(phone=p, code=legacy_by_phone.get(p) or _generate_invite_code())
        for p in missing
    ]
    StudentInviteCode.objects.bulk_create(to_create, ignore_conflicts=True)

    # 4) Re-read to learn the actually-stored code for every missing phone — one query.
    for obj in StudentInviteCode.objects.filter(phone__in=missing).only('phone', 'code'):
        result[obj.phone] = obj.code

    # 5) Slow path ONLY for phones still without a row (their legacy code collided
    #    with an existing code, so the bulk insert skipped them). Very rare.
    for p in missing:
        if p not in result:
            result[p] = get_or_create_invite_code_for_phone(p)

    return result
