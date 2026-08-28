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


def _has_impersonation_claim(request) -> bool:
    """True when the request's access token carries the ``imp`` claim.

    An impersonation token acts *as* a member; it must never be able to mint
    another impersonation, touch org-manager endpoints, or outlive its 30-minute
    TTL silently. The claim lives on the JWT payload (SimpleJWT exposes it as
    ``request.auth.payload``); a force-authenticated test client (or session
    auth) has no token at all, hence the defensive getattr chain.
    """
    token = getattr(request, 'auth', None)
    payload = getattr(token, 'payload', None)
    return isinstance(payload, dict) and bool(payload.get('imp'))


class IsOrgManager(BasePermission):
    """Allow only a platform-MANAGER account that is NOT an impersonated token.

    Role-level gate only (risman step 3): the *organizational* half — which org
    this manager may see — is resolved per-view from their own ACTIVE
    admin/deputy membership, exactly like the existing ``organizations``
    endpoints resolve tenancy. Strictly excludes platform admins
    (``IsAdvisorUser`` precedent: admins manage accounts, they do not inherit a
    named school's oversight) and rejects tokens bearing the impersonation
    claim both here and at the re-impersonate door.
    """

    message = 'فقط مدیر موسسه اجازه دسترسی دارد.'

    def has_permission(self, request, view) -> bool:
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return False
        if _has_impersonation_claim(request):
            self.message = 'این جلسه در حالت ورود مستقیم است و این کار مجاز نیست.'
            return False
        return user.role == User.Role.MANAGER
