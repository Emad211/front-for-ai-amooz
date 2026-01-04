import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient


User = get_user_model()


@pytest.mark.django_db
class TestApiErrorContract:
    def test_register_duplicate_username_returns_unified_validation_error(self):
        client = APIClient()

        r1 = client.post(
            '/api/auth/register/',
            {'username': 'dup_user', 'password': 'StrongPass123!@#'},
            format='json',
        )
        assert r1.status_code == 201

        r2 = client.post(
            '/api/auth/register/',
            {'username': 'dup_user', 'password': 'StrongPass123!@#'},
            format='json',
        )
        assert r2.status_code == 400
        assert r2.data['detail'] == 'Validation error.'
        assert 'errors' in r2.data
        assert 'username' in r2.data['errors']

    def test_password_change_wrong_old_password_returns_unified_validation_error(self):
        user = User.objects.create_user(username='pw_user', password='OldPass123!@#')

        client = APIClient()
        token = client.post(
            '/api/token/',
            {'username': 'pw_user', 'password': 'OldPass123!@#'},
            format='json',
        )
        assert token.status_code == 200

        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.data['access']}")
        resp = client.post(
            '/api/auth/password-change/',
            {'old_password': 'WRONG', 'new_password': 'NewPass123!@#'},
            format='json',
        )

        assert resp.status_code == 400
        assert resp.data['detail'] == 'Validation error.'
        assert resp.data['errors']['old_password']

    def test_unauthorized_me_keeps_detail_shape(self):
        client = APIClient()
        resp = client.get('/api/accounts/me/')
        assert resp.status_code == 401
        assert 'detail' in resp.data
        assert 'errors' not in resp.data
