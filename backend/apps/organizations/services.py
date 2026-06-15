"""Reusable organization provisioning.

Shared by the platform-admin CRUD view (`OrganizationListCreateView`) and the
waitlist approval flow, so "create an org + its admin activation code" lives in
exactly one place.
"""

from __future__ import annotations

import logging

from django.db import DatabaseError, transaction
from django.utils.crypto import get_random_string

from .models import InvitationCode, Organization

logger = logging.getLogger(__name__)


def generate_unique_org_slug(base: str = 'org') -> str:
    """Return an ASCII slug guaranteed unique against existing organizations.

    Org names are usually Persian (non-ASCII) while ``Organization.slug`` is
    ASCII-only, so we mint a short random slug; an admin can rename it later.
    """
    for _ in range(20):
        candidate = f'{base}-{get_random_string(8, "abcdefghijklmnopqrstuvwxyz0123456789")}'
        if not Organization.objects.filter(slug=candidate).exists():
            return candidate
    # Extremely unlikely; fall back to a longer token.
    return f'{base}-{get_random_string(16, "abcdefghijklmnopqrstuvwxyz0123456789")}'


def provision_organization(*, data: dict, created_by, owner=None) -> tuple[Organization, str | None]:
    """Create an Organization and its one-time admin activation code, atomically.

    ``data`` is a dict of Organization field values (already validated). Returns
    ``(organization, admin_code_value)``; ``admin_code_value`` is ``None`` only if
    the InvitationCode insert failed due to schema drift (the org is still created
    so the caller can surface a clear error).
    """
    admin_code_value: str | None = None
    with transaction.atomic():
        org_data = dict(data)
        org_data.setdefault('owner', owner)
        org = Organization.objects.create(**org_data)

        try:
            admin_code = InvitationCode.objects.create(
                organization=org,
                target_role=InvitationCode.TargetRole.ADMIN,
                label='کد فعالسازی مدیر',
                max_uses=1,
                created_by=created_by,
            )
            admin_code_value = admin_code.code
        except DatabaseError:
            logger.exception(
                'Organization %s created but InvitationCode insert failed. '
                'Run organizations migrations to repair schema drift.',
                getattr(org, 'pk', None),
            )

    return org, admin_code_value
