import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.accounts.models import StudentProfile

User = get_user_model()


@pytest.mark.django_db
class TestAuthRegisterLogout:
    def test_register_creates_user_and_student_profile_and_returns_tokens(self):
        client = APIClient()
        response = client.post(
            '/api/auth/register/',
            {
                'username': 'new_student',
                'password': 'StrongPass123!@#',
                'role': 'STUDENT',
            },
            format='json',
        )

        assert response.status_code == 201
        assert response.data['user']['username'] == 'new_student'
        assert response.data['user']['role'] == 'STUDENT'
        assert 'access' in response.data['tokens']
        assert 'refresh' in response.data['tokens']

        user = User.objects.get(username='new_student')
        assert StudentProfile.objects.filter(user=user).exists()

    def test_logout_requires_authentication(self):
        client = APIClient()
        response = client.post('/api/auth/logout/', {'refresh': 'x'}, format='json')
        assert response.status_code == 401

    def test_logout_blacklists_refresh_token(self):
        # Create user
        user = User.objects.create_user(
            username='logout_user',
            password='StrongPass123!@#',
            role=User.Role.STUDENT,
        )

        client = APIClient()

        # Obtain tokens
        token_response = client.post(
            '/api/token/',
            {'username': 'logout_user', 'password': 'StrongPass123!@#'},
            format='json',
        )
        assert token_response.status_code == 200
        access = token_response.data['access']
        refresh = token_response.data['refresh']

        # Logout
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        logout_response = client.post('/api/auth/logout/', {'refresh': refresh}, format='json')
        assert logout_response.status_code == 205

        # Refresh should now fail (blacklisted)
        client.credentials()
        refresh_response = client.post('/api/token/refresh/', {'refresh': refresh}, format='json')
        assert refresh_response.status_code in {401, 400}

    def test_logout_rejects_refresh_token_of_other_user(self):
        user_a = User.objects.create_user(
            username='user_a',
            password='StrongPass123!@#',
            role=User.Role.STUDENT,
        )
        user_b = User.objects.create_user(
            username='user_b',
            password='StrongPass123!@#',
            role=User.Role.STUDENT,
        )

        client = APIClient()

        # token for user_a
        token_a = client.post('/api/token/', {'username': 'user_a', 'password': 'StrongPass123!@#'}, format='json')
        assert token_a.status_code == 200
        refresh_a = token_a.data['refresh']

        # access for user_b
        token_b = client.post('/api/token/', {'username': 'user_b', 'password': 'StrongPass123!@#'}, format='json')
        assert token_b.status_code == 200
        access_b = token_b.data['access']

        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_b}')
        resp = client.post('/api/auth/logout/', {'refresh': refresh_a}, format='json')
        assert resp.status_code == 403

    def test_register_rejects_admin_role(self):
        client = APIClient()
        response = client.post(
            '/api/auth/register/',
            {
                'username': 'fake_admin',
                'password': 'StrongPass123!@#',
                'role': 'ADMIN',
            },
            format='json',
        )
        assert response.status_code == 400
        assert response.data['detail'] == 'Validation error.'
        assert 'role' in response.data['errors']

    def test_register_rejects_duplicate_username(self):
        User.objects.create_user(username='existing_user', password='password123')
        client = APIClient()
        response = client.post(
            '/api/auth/register/',
            {
                'username': 'existing_user',
                'password': 'StrongPass123!@#',
            },
            format='json',
        )
        assert response.status_code == 400
        assert response.data['detail'] == 'Validation error.'
        assert 'username' in response.data['errors']

    def test_password_change_success(self):
        user = User.objects.create_user(username='change_pass', password='OldPassword123!')
        client = APIClient()
        
        # Login to get token
        token_resp = client.post('/api/token/', {'username': 'change_pass', 'password': 'OldPassword123!'}, format='json')
        access = token_resp.data['access']
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')

        response = client.post(
            '/api/auth/password-change/',
            {
                'old_password': 'OldPassword123!',
                'new_password': 'NewPassword123!',
            },
            format='json',
        )
        assert response.status_code == 200
        
        # Verify login with new password
        client.credentials()
        login_resp = client.post('/api/token/', {'username': 'change_pass', 'password': 'NewPassword123!'}, format='json')
        assert login_resp.status_code == 200

    def test_password_change_fails_with_wrong_old_password(self):
        user = User.objects.create_user(username='wrong_old', password='CorrectOld123!')
        client = APIClient()
        token_resp = client.post('/api/token/', {'username': 'wrong_old', 'password': 'CorrectOld123!'}, format='json')
        access = token_resp.data['access']
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')

        response = client.post(
            '/api/auth/password-change/',
            {
                'old_password': 'WrongOldPassword',
                'new_password': 'NewPassword123!',
            },
            format='json',
        )
        assert response.status_code == 400
        assert response.data['detail'] == 'Validation error.'
        assert 'old_password' in response.data['errors']

    def test_register_rejects_duplicate_email(self):
        User.objects.create_user(username='user1', email='duplicate@example.com', password='password123')
        client = APIClient()
        response = client.post(
            '/api/auth/register/',
            {
                'username': 'user2',
                'email': 'duplicate@example.com',
                'password': 'StrongPass123!@#',
            },
            format='json',
        )
        assert response.status_code == 400
        assert response.data['detail'] == 'Validation error.'
        assert 'email' in response.data['errors']

    def test_register_rejects_weak_password(self):
        client = APIClient()
        response = client.post(
            '/api/auth/register/',
            {
                'username': 'weak_user',
                'password': '123',
            },
            format='json',
        )
        assert response.status_code == 400
        assert response.data['detail'] == 'Validation error.'
        assert 'password' in response.data['errors']

    def test_token_refresh_works(self):
        user = User.objects.create_user(username='refresh_user', password='password123')
        client = APIClient()
        token_resp = client.post('/api/token/', {'username': 'refresh_user', 'password': 'password123'}, format='json')
        refresh = token_resp.data['refresh']

        refresh_resp = client.post('/api/token/refresh/', {'refresh': refresh}, format='json')
        assert refresh_resp.status_code == 200
        assert 'access' in refresh_resp.data
        # Since ROTATE_REFRESH_TOKENS is True, we should also get a new refresh token
        assert 'refresh' in refresh_resp.data
