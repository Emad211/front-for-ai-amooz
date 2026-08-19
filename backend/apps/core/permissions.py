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


class IsAdvisorUser(BasePermission):
    """Allow access only to the ADVISOR (مشاور) platform role.

    Strictly ``role == 'ADVISOR'``. A platform admin is NOT included: an admin
    manages accounts, they do not silently inherit a named advisor's student
    roster. Admin-side visibility, if ever needed, gets its own endpoint.
    """

    message = 'فقط مشاوران اجازه دسترسی دارند.'

    def has_permission(self, request, view) -> bool:
        user = getattr(request, 'user', None)
        return bool(
            user and user.is_authenticated and user.role == User.Role.ADVISOR
        )


class IsStudentRole(BasePermission):
    """Allow access only to the STUDENT platform role — strictly.

    Deliberately NOT ``apps.classes.permissions.IsStudentUser``, which also
    admits TEACHER so teachers can consume courses as learners. Advisory data is
    a real teenager's study log; the reader set is explicit and counted
    (the student, their active advisor, a platform admin, an org manager in
    aggregate only). Widening this class re-opens that set by accident.
    """

    message = 'فقط دانش‌آموزان اجازه دسترسی دارند.'

    def has_permission(self, request, view) -> bool:
        user = getattr(request, 'user', None)
        return bool(
            user and user.is_authenticated and user.role == User.Role.STUDENT
        )
