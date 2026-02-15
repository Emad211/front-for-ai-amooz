from rest_framework.permissions import BasePermission

from apps.accounts.models import User


class IsTeacherUser(BasePermission):
    message = 'Only teachers can perform this action.'

    def has_permission(self, request, view) -> bool:
        user = getattr(request, 'user', None)
        return bool(user and user.is_authenticated and user.role == User.Role.TEACHER)


class IsStudentUser(BasePermission):
    """Allow both STUDENT and TEACHER users to access student-facing endpoints.

    Teachers may also want to take exams, view courses, etc. as learners.
    """
    message = 'Only students (or teachers) can perform this action.'

    def has_permission(self, request, view) -> bool:
        user = getattr(request, 'user', None)
        return bool(
            user
            and user.is_authenticated
            and user.role in (User.Role.STUDENT, User.Role.TEACHER)
        )
