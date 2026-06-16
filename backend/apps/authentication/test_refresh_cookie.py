"""Tests for the HttpOnly refresh-token cookie.

Login/refresh deliver the refresh token as an HttpOnly cookie; refresh and logout
read it from the cookie. APIClient keeps a cookie jar, so these exercise the real
cookie round-trip (the same mechanics as the same-origin /api proxy in prod).
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()
PW = 'StrongPass123!@#'
COOKIE = 'refresh_token'


def _user(username='cookieuser'):
    return User.objects.create_user(username=username, password=PW)


@pytest.mark.django_db
def test_login_sets_httponly_refresh_cookie():
    _user()
    client = APIClient()
    resp = client.post('/api/token/', {'username': 'cookieuser', 'password': PW}, format='json')
    assert resp.status_code == 200, resp.content
    morsel = resp.cookies.get(COOKIE)
    assert morsel is not None and morsel.value
    assert morsel['httponly']  # not readable by JS
    # The access token is NOT placed in a cookie (stays a Bearer token).
    assert 'access' in resp.data


@pytest.mark.django_db
def test_refresh_works_from_cookie_only_and_rotates():
    _user('rotuser')
    client = APIClient()
    client.post('/api/token/', {'username': 'rotuser', 'password': PW}, format='json')
    # No body — the refresh comes purely from the cookie in the client's jar.
    r = client.post('/api/token/refresh/', {}, format='json')
    assert r.status_code == 200, r.content
    assert r.data.get('access')
    # Rotation re-sets the cookie.
    assert r.cookies.get(COOKIE) is not None and r.cookies.get(COOKIE).value


@pytest.mark.django_db
def test_logout_clears_cookie_and_blacklists_session():
    _user('logoutuser')
    client = APIClient()
    login = client.post('/api/token/', {'username': 'logoutuser', 'password': PW}, format='json')
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

    out = client.post('/api/auth/logout/', {}, format='json')
    assert out.status_code == 205, out.content
    # delete_cookie emits an expired cookie.
    assert out.cookies.get(COOKIE) is not None and out.cookies.get(COOKIE).value == ''

    # After logout the session refresh is no longer usable.
    client.credentials()
    r = client.post('/api/token/refresh/', {}, format='json')
    assert r.status_code in (400, 401)
