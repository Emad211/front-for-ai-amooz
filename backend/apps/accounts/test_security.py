import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient


User = get_user_model()


@pytest.mark.django_db
class TestAccountsSecurity:
    def test_me_does_not_leak_sensitive_fields(self):
        user = User.objects.create_user(
            username='sec_me',
            password='StrongPass123!@#',
            role=User.Role.STUDENT,
        )

        client = APIClient()
        token_response = client.post(
            '/api/token/',
            {'username': 'sec_me', 'password': 'StrongPass123!@#'},
            format='json',
        )
        assert token_response.status_code == 200

        access = token_response.data['access']
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        response = client.get('/api/accounts/me/')
        assert response.status_code == 200

        # Ensure response doesn't include secrets/privileged fields.
        response_text = str(response.data)
        assert 'password' not in response_text
        assert 'is_superuser' not in response_text
        assert 'user_permissions' not in response_text

    def test_inactive_user_cannot_access_me_even_with_token(self):
        user = User.objects.create_user(
            username='inactive_user',
            password='StrongPass123!@#',
            role=User.Role.STUDENT,
        )

        client = APIClient()
        token_response = client.post(
            '/api/token/',
            {'username': 'inactive_user', 'password': 'StrongPass123!@#'},
            format='json',
        )
        assert token_response.status_code == 200

        user.is_active = False
        user.save(update_fields=['is_active'])

        access = token_response.data['access']
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        response = client.get('/api/accounts/me/')
        assert response.status_code == 401
