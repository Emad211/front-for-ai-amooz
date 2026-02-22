"""Shared permission classes used across multiple apps."""

from __future__ import annotations

from rest_framework.permissions import BasePermission

from apps.accounts.models import User


class IsPlatformAdmin(BasePermission):
    """Allow access only to platform admins.

    A user is considered an admin if *any* of these are true:
    - ``user.role == 'ADMIN'``
    - ``user.is_superuser``
    - ``user.is_staff``

    This ensures Django superusers (created via ``createsuperuser``)
    always have access, even when their ``role`` field was never
    explicitly set to ``ADMIN``.
    """

    message = 'فقط ادمین‌ها اجازه دسترسی دارند.'

    def has_permission(self, request, view) -> bool:
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return False
        return (
            user.role == User.Role.ADMIN
            or user.is_superuser
            or user.is_staff
        )
