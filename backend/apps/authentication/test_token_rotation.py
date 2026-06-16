"""Documents the refresh-token rotation contract the frontend must honor.

With ROTATE_REFRESH_TOKENS + BLACKLIST_AFTER_ROTATION, each /token/refresh/ call
returns a NEW refresh token and blacklists the one just used. The frontend must
persist the rotated token (it previously kept the old one, causing a premature
logout on the next refresh). These tests guard the backend side of that contract
and the 3-day session window.
"""

from datetime import timedelta

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


@pytest.mark.django_db
def test_refresh_rotates_and_old_token_is_blacklisted():
    User.objects.create_user(username='rot', password='OldPass123!@#')
    client = APIClient()
    login = client.post('/api/token/', {'username': 'rot', 'password': 'OldPass123!@#'}, format='json')
    assert login.status_code == 200, login.content
    r1 = login.data['refresh']

    # First refresh rotates → returns a NEW refresh token.
    resp1 = client.post('/api/token/refresh/', {'refresh': r1}, format='json')
    assert resp1.status_code == 200, resp1.content
    r2 = resp1.data.get('refresh')
    assert r2 and r2 != r1, 'refresh endpoint must return a rotated refresh token'

    # The rotated token works (an active user stays logged in by using it)...
    resp2 = client.post('/api/token/refresh/', {'refresh': r2}, format='json')
    assert resp2.status_code == 200, resp2.content

    # ...and the original token is now blacklisted (keeping it = premature logout).
    old = client.post('/api/token/refresh/', {'refresh': r1}, format='json')
    assert old.status_code == 401, old.content


def test_session_window_is_three_days():
    # The refresh lifetime is the effective session length (env-tunable, default 3d).
    assert settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'] >= timedelta(days=3)
