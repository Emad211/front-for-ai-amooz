"""Unit tests for ``apps.accounts.services.get_or_create_user_by_phone``.

This is the ONE place a phone becomes a user of a given role (every invite/redeem
path funnels through it), so its invariants are load-bearing:

* passwordless shell on create (onboarding sets real credentials later),
* idempotent + role-scoped lookup (one human, many roles, never a duplicate),
* ``is_freelancer`` applied ONLY on creation,
* the role profile always exists afterwards (signal + ``_ensure_profile`` net),
* a username base-collision still succeeds with a suffixed username.

The DB-level ``uniq_student_phone`` constraint that backs the concurrency race is
exercised in ``test_student_phone_unique.py`` — not re-covered here.
"""
import pytest
from django.contrib.auth import get_user_model

from apps.accounts.models import StudentProfile, TeacherProfile
from apps.accounts.services import (
    get_or_create_user_by_phone,
    get_or_create_student_by_phone,
)

User = get_user_model()
pytestmark = [pytest.mark.django_db, pytest.mark.unit]

PHONE = '09121234567'


class TestGetOrCreateUserByPhone:
    def test_creates_passwordless_student_shell_with_profile(self):
        user, created = get_or_create_user_by_phone(
            PHONE, User.Role.STUDENT, first_name='سارا', last_name='رضایی',
        )
        assert created is True
        assert user.role == User.Role.STUDENT
        assert user.phone == PHONE
        assert user.first_name == 'سارا' and user.last_name == 'رضایی'
        # Passwordless — onboarding sets the real credentials.
        assert not user.has_usable_password()
        # Auto-username is role-prefixed off the phone.
        assert user.username == f'student_{PHONE}'
        assert StudentProfile.objects.filter(user=user).exists()

    def test_idempotent_same_phone_and_role_returns_existing(self):
        first, c1 = get_or_create_user_by_phone(PHONE, User.Role.STUDENT)
        second, c2 = get_or_create_user_by_phone(PHONE, User.Role.STUDENT)
        assert c1 is True and c2 is False
        assert first.pk == second.pk
        assert User.objects.filter(phone=PHONE, role=User.Role.STUDENT).count() == 1

    def test_role_scoped_same_phone_different_role_is_a_separate_user(self):
        student, _ = get_or_create_user_by_phone(PHONE, User.Role.STUDENT)
        teacher, created = get_or_create_user_by_phone(PHONE, User.Role.TEACHER)
        assert created is True
        assert teacher.pk != student.pk
        assert teacher.role == User.Role.TEACHER
        # Two humans-as-roles, one phone — both persist.
        assert User.objects.filter(phone=PHONE).count() == 2

    def test_teacher_gets_teacher_profile_not_student_profile(self):
        teacher, _ = get_or_create_user_by_phone(PHONE, User.Role.TEACHER)
        assert TeacherProfile.objects.filter(user=teacher).exists()
        assert not StudentProfile.objects.filter(user=teacher).exists()

    def test_manager_gets_no_role_profile(self):
        manager, _ = get_or_create_user_by_phone(PHONE, User.Role.MANAGER)
        assert not StudentProfile.objects.filter(user=manager).exists()
        assert not TeacherProfile.objects.filter(user=manager).exists()

    def test_is_freelancer_false_applied_on_create(self):
        teacher, _ = get_or_create_user_by_phone(
            PHONE, User.Role.TEACHER, is_freelancer=False,
        )
        assert teacher.is_freelancer is False

    def test_is_freelancer_defaults_true_when_not_passed(self):
        teacher, _ = get_or_create_user_by_phone(PHONE, User.Role.TEACHER)
        # Model default is True (personal workspace allowed unless org says otherwise).
        assert teacher.is_freelancer is True

    def test_is_freelancer_not_reapplied_to_existing_user(self):
        teacher, _ = get_or_create_user_by_phone(
            PHONE, User.Role.TEACHER, is_freelancer=False,
        )
        # A later call must NOT flip the flag — it's a create-only argument.
        again, created = get_or_create_user_by_phone(
            PHONE, User.Role.TEACHER, is_freelancer=True,
        )
        assert created is False
        again.refresh_from_db()
        assert again.is_freelancer is False

    def test_username_base_collision_gets_suffixed_username(self):
        # A pre-existing account already owns the base username `student_<phone>`
        # (contrived: a TEACHER row), so the new STUDENT must get a suffixed one.
        User.objects.create_user(
            username=f'student_{PHONE}', role=User.Role.TEACHER, phone='09120000001',
        )
        student, created = get_or_create_user_by_phone(PHONE, User.Role.STUDENT)
        assert created is True
        assert student.username != f'student_{PHONE}'
        assert student.username.startswith(f'student_{PHONE}_')
        assert student.role == User.Role.STUDENT

    def test_ensure_profile_recreates_missing_profile_on_return(self):
        student, _ = get_or_create_user_by_phone(PHONE, User.Role.STUDENT)
        StudentProfile.objects.filter(user=student).delete()
        assert not StudentProfile.objects.filter(user=student).exists()
        # A returning lookup heals the missing profile (safety net for old rows).
        again, created = get_or_create_user_by_phone(PHONE, User.Role.STUDENT)
        assert created is False
        assert StudentProfile.objects.filter(user=again).exists()


class TestStudentWrapper:
    def test_wrapper_delegates_with_student_role(self):
        user, created = get_or_create_student_by_phone(
            PHONE, first_name='علی', last_name='محمدی',
        )
        assert created is True
        assert user.role == User.Role.STUDENT
        assert user.phone == PHONE
        assert user.first_name == 'علی' and user.last_name == 'محمدی'
