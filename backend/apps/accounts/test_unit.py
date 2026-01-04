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
            'email',
            'role',
            'is_profile_completed',
        }
        assert data['username'] == 'serializer_user'
        assert data['email'] == 'teacher@example.com'
        assert data['role'] == User.Role.TEACHER
        assert data['is_profile_completed'] is False
