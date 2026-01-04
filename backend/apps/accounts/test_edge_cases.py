import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient


User = get_user_model()


@pytest.mark.django_db
class TestAccountsEdgeCases:
    def test_me_handles_blank_email(self):
        user = User.objects.create_user(
            username='blank_email_user',
            password='StrongPass123!@#',
            email='',
            role=User.Role.STUDENT,
        )

        client = APIClient()
        token_response = client.post(
            '/api/token/',
            {'username': 'blank_email_user', 'password': 'StrongPass123!@#'},
            format='json',
        )
        assert token_response.status_code == 200

        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_response.data['access']}")
        response = client.get('/api/accounts/me/')
        assert response.status_code == 200
        assert response.data['email'] in ['', None]

    def test_me_rejects_malformed_bearer_token(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Bearer not-a-jwt')
        response = client.get('/api/accounts/me/')
        assert response.status_code == 401
