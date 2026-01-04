import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from apps.accounts.models import StudentProfile, TeacherProfile, AdminProfile


User = get_user_model()


@pytest.mark.django_db
class TestAccountsDatabase:
    def test_profile_created_for_student(self):
        user = User.objects.create_user(
            username='db_student',
            password='StrongPass123!@#',
            role=User.Role.STUDENT,
        )
        assert StudentProfile.objects.filter(user=user).exists()
        assert not TeacherProfile.objects.filter(user=user).exists()
        assert not AdminProfile.objects.filter(user=user).exists()

    def test_profile_created_for_teacher(self):
        user = User.objects.create_user(
            username='db_teacher',
            password='StrongPass123!@#',
            role=User.Role.TEACHER,
        )
        assert TeacherProfile.objects.filter(user=user).exists()
        assert not StudentProfile.objects.filter(user=user).exists()

    def test_profile_created_for_admin(self):
        user = User.objects.create_user(
            username='db_admin',
            password='StrongPass123!@#',
            role=User.Role.ADMIN,
        )
        assert AdminProfile.objects.filter(user=user).exists()
        assert not StudentProfile.objects.filter(user=user).exists()

    def test_studentprofile_one_to_one_enforced(self):
        user = User.objects.create_user(
            username='db_student_o2o',
            password='StrongPass123!@#',
            role=User.Role.STUDENT,
        )

        with pytest.raises(IntegrityError):
            StudentProfile.objects.create(user=user)

    def test_cascade_delete_user_deletes_profiles(self):
        user = User.objects.create_user(
            username='db_student_delete',
            password='StrongPass123!@#',
            role=User.Role.STUDENT,
        )
        assert StudentProfile.objects.filter(user=user).count() == 1

        user_id = user.id
        user.delete()

        assert not User.objects.filter(id=user_id).exists()
        assert StudentProfile.objects.filter(user_id=user_id).count() == 0
