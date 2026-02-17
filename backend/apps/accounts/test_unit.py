import pytest
from django.contrib.auth import get_user_model

from apps.accounts.serializers import MeSerializer


User = get_user_model()


@pytest.mark.django_db
class TestAccountsUnit:
    def test_user_str_includes_username_and_role(self):
        user = User.objects.create_user(
            username='unit_user',
            password='StrongPass123!@#',
            role=User.Role.STUDENT,
        )
        assert str(user) == f"{user.username} ({user.role})"

    def test_me_serializer_fields(self):
        user = User.objects.create_user(
            username='serializer_user',
            password='StrongPass123!@#',
            role=User.Role.TEACHER,
            email='teacher@example.com',
        )

        data = MeSerializer(user).data

        assert set(data.keys()) == {
            'id',
            'username',
            'first_name',
            'last_name',
            'email',
            'phone',
            'avatar',
            'role',
            'is_staff',
            'is_superuser',
            'is_profile_completed',
            'join_date',
            'bio',
            'location',
            'grade',
            'major',
            'is_verified',
        }
        assert data['username'] == 'serializer_user'
        assert data['first_name'] == ''
        assert data['last_name'] == ''
        assert data['email'] == 'teacher@example.com'
        assert data['phone'] in ('', None)
        assert data['avatar'] is None
        assert data['role'] == User.Role.TEACHER
        assert data['is_profile_completed'] is False
        assert data['join_date']
        assert data['bio'] in ('', None)
        assert data['grade'] is None
        assert data['major'] is None
        assert data['is_verified'] in (True, False)
