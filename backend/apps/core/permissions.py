"""Shared permission classes used across multiple apps."""

from __future__ import annotations

from rest_framework.permissions import BasePermission

from apps.accounts.models import User


class IsPlatformAdmin(BasePermission):
    """Allow access only to platform admins (role == ADMIN).

    Checks `user.role` instead of Django's `is_staff` flag so that
    the behaviour is consistent across *all* admin endpoints.
    """

    message = 'فقط ادمین‌ها اجازه دسترسی دارند.'

    def has_permission(self, request, view) -> bool:
        user = getattr(request, 'user', None)
        return bool(user and user.is_authenticated and user.role == User.Role.ADMIN)
