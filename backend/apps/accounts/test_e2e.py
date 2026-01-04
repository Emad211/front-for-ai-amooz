import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestAccountsE2E:
    def test_register_then_me_returns_same_user(self):
        client = APIClient()

        register_response = client.post(
            '/api/auth/register/',
            {
                'username': 'e2e_accounts_user',
                'password': 'StrongPass123!@#',
                'role': 'STUDENT',
            },
            format='json',
        )
        assert register_response.status_code == 201

        access = register_response.data['tokens']['access']
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')

        me_response = client.get('/api/accounts/me/')
        assert me_response.status_code == 200
        assert me_response.data['username'] == 'e2e_accounts_user'
        assert me_response.data['role'] == 'STUDENT'
