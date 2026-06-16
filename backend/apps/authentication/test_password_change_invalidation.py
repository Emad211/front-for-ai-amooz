"""Regression test: a password change must invalidate existing sessions (HIGH fix).

Previously PasswordChangeView only called set_password(); SimpleJWT is stateless,
so a stolen refresh token kept working for its full lifetime after the victim
changed their password. The view now blacklists all outstanding refresh tokens
and reissues a fresh pair to the requester.
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()
CHANGE_URL = '/api/auth/password-change/'


@pytest.mark.django_db
def test_password_change_blacklists_old_refresh_and_reissues():
    User.objects.create_user(username='pwuser', password='OldPass123!@#')
    client = APIClient()

    login = client.post('/api/token/', {'username': 'pwuser', 'password': 'OldPass123!@#'}, format='json')
    assert login.status_code == 200, login.content
    old_refresh = login.data['refresh']

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    chg = client.post(
        CHANGE_URL,
        {'old_password': 'OldPass123!@#', 'new_password': 'NewPass123!@#'},
        format='json',
    )
    assert chg.status_code == 200, chg.content

    # The OLD refresh token must now be rejected (blacklisted).
    client.credentials()
    r_old = client.post('/api/token/refresh/', {'refresh': old_refresh}, format='json')
    assert r_old.status_code == 401, r_old.content

    # The FRESH pair returned by password-change must still work (requester stays logged in).
    assert chg.data.get('access') and chg.data.get('refresh')
    r_new = client.post('/api/token/refresh/', {'refresh': chg.data['refresh']}, format='json')
    assert r_new.status_code == 200, r_new.content
