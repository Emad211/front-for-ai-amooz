from rest_framework.permissions import BasePermission

from apps.accounts.models import User


class IsAdminUser(BasePermission):
    message = 'Only admins can perform this action.'

    def has_permission(self, request, view) -> bool:
        user = getattr(request, 'user', None)
        return bool(user and user.is_authenticated and user.role == User.Role.ADMIN)
