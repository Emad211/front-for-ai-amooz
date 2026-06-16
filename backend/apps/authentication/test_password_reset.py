"""Tests for the SMS-OTP password reset flow."""

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient

User = get_user_model()
REQ = '/api/auth/password-reset/request/'
CONF = '/api/auth/password-reset/confirm/'
NEW = 'NewPass123!@#'
OLD = 'OldPass123!@#'


@pytest.fixture(autouse=True)
def _locmem_cache(settings):
    # OTPs live in the cache; force a local in-memory cache so tests don't need Redis.
    settings.CACHES = {
        'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'pwreset-tests'}
    }
    cache.clear()


def _fixed_code(monkeypatch, code='123456'):
    monkeypatch.setattr('apps.authentication.otp_service._generate_code', lambda: code)


def _teacher(username='teach', password=OLD, phone='09120000000'):
    return User.objects.create_user(username=username, password=password, phone=phone, role=User.Role.TEACHER)


@pytest.mark.django_db
def test_request_is_generic_for_unknown_identifier():
    resp = APIClient().post(REQ, {'identifier': 'nobody'}, format='json')
    assert resp.status_code == 200  # no account enumeration


@pytest.mark.django_db
def test_request_issues_otp_for_known_user(monkeypatch):
    _fixed_code(monkeypatch)
    u = _teacher()
    assert APIClient().post(REQ, {'identifier': 'teach'}, format='json').status_code == 200
    assert cache.get(f'pwreset:{u.id}') is not None


@pytest.mark.django_db
def test_student_with_unusable_password_gets_no_otp():
    u = User.objects.create_user(username='stu', phone='09120000001', role=User.Role.STUDENT)
    u.set_unusable_password()
    u.save()
    assert APIClient().post(REQ, {'identifier': 'stu'}, format='json').status_code == 200
    assert cache.get(f'pwreset:{u.id}') is None


@pytest.mark.django_db
def test_full_reset_flow_revokes_old_tokens(monkeypatch):
    _fixed_code(monkeypatch)
    u = _teacher()
    client = APIClient()
    login = client.post('/api/token/', {'username': 'teach', 'password': OLD}, format='json')
    old_refresh = login.data['refresh']

    assert client.post(REQ, {'identifier': 'teach'}, format='json').status_code == 200
    conf = client.post(CONF, {'identifier': 'teach', 'code': '123456', 'new_password': NEW}, format='json')
    assert conf.status_code == 200, conf.content
    assert conf.data.get('access') and conf.data.get('refresh')

    # Old refresh is blacklisted; new password works; old password fails.
    assert client.post('/api/token/refresh/', {'refresh': old_refresh}, format='json').status_code == 401
    assert client.post('/api/token/', {'username': 'teach', 'password': NEW}, format='json').status_code == 200
    assert client.post('/api/token/', {'username': 'teach', 'password': OLD}, format='json').status_code == 401
    # OTP is single-use → consumed.
    assert cache.get(f'pwreset:{u.id}') is None


@pytest.mark.django_db
def test_wrong_code_rejected_then_correct_works(monkeypatch):
    _fixed_code(monkeypatch)
    _teacher()
    client = APIClient()
    client.post(REQ, {'identifier': 'teach'}, format='json')
    assert client.post(CONF, {'identifier': 'teach', 'code': '000000', 'new_password': NEW}, format='json').status_code == 400
    # A wrong attempt does NOT consume the OTP — the correct code still works.
    assert client.post(CONF, {'identifier': 'teach', 'code': '123456', 'new_password': NEW}, format='json').status_code == 200


@pytest.mark.django_db
def test_otp_locked_after_max_attempts(monkeypatch):
    _fixed_code(monkeypatch)
    _teacher()
    client = APIClient()
    client.post(REQ, {'identifier': 'teach'}, format='json')
    for _ in range(5):
        client.post(CONF, {'identifier': 'teach', 'code': '000000', 'new_password': NEW}, format='json')
    # After max wrong attempts the OTP is invalidated — even the correct code fails.
    final = client.post(CONF, {'identifier': 'teach', 'code': '123456', 'new_password': NEW}, format='json')
    assert final.status_code == 400


@pytest.mark.django_db
def test_confirm_without_request_is_rejected():
    _teacher()
    resp = APIClient().post(CONF, {'identifier': 'teach', 'code': '123456', 'new_password': NEW}, format='json')
    assert resp.status_code == 400


@pytest.mark.django_db
def test_resend_cooldown_does_not_reissue(monkeypatch):
    from apps.authentication.otp_service import issue_reset_otp
    _fixed_code(monkeypatch, '111111')
    u = _teacher()
    issue_reset_otp(u)
    first = cache.get(f'pwreset:{u.id}')
    issue_reset_otp(u)  # immediate re-request → cooldown, no reissue
    second = cache.get(f'pwreset:{u.id}')
    assert first['issued_at'] == second['issued_at']
