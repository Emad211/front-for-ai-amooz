import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.accounts.models import StudentProfile, TeacherProfile, AdminProfile

User = get_user_model()

@pytest.mark.django_db
class TestUserProfileCreation:
    def test_student_profile_created(self):
        user = User.objects.create_user(
            username='student_user',
            password='password123',
            role=User.Role.STUDENT
        )
        assert StudentProfile.objects.filter(user=user).exists()
        assert not TeacherProfile.objects.filter(user=user).exists()
        assert not AdminProfile.objects.filter(user=user).exists()

    def test_teacher_profile_created(self):
        user = User.objects.create_user(
            username='teacher_user',
            password='password123',
            role=User.Role.TEACHER
        )
        assert TeacherProfile.objects.filter(user=user).exists()
        assert not StudentProfile.objects.filter(user=user).exists()

    def test_admin_profile_created(self):
        user = User.objects.create_user(
            username='admin_user',
            password='password123',
            role=User.Role.ADMIN
        )
        assert AdminProfile.objects.filter(user=user).exists()
        assert not StudentProfile.objects.filter(user=user).exists()


@pytest.mark.django_db
class TestAccountsMeEndpoint:
    def test_me_requires_authentication(self):
        client = APIClient()
        response = client.get('/api/accounts/me/')
        assert response.status_code == 401

    def test_me_returns_current_user(self):
        user = User.objects.create_user(
            username='me_user',
            password='password123',
            role=User.Role.STUDENT,
        )

        client = APIClient()
        token_response = client.post(
            '/api/token/',
            {'username': 'me_user', 'password': 'password123'},
            format='json',
        )
        assert token_response.status_code == 200

        access = token_response.data['access']
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        response = client.get('/api/accounts/me/')

        assert response.status_code == 200
        assert response.data['username'] == 'me_user'
        assert response.data['role'] == User.Role.STUDENT
