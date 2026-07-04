"""API tests for the ``/api/token/`` login-by-identifier serializer
(``TokenObtainPairByIdentifierSerializer``) and refresh negatives.

Extends — does NOT duplicate — the existing suite:
* username/email happy paths + multi-account-by-password + admin-priority live in
  ``test_e2e.py``;
* missing-field 400s in ``test_e2e.test_authentication_error_handling``;
* inactive-user 401 in ``test_edge_cases``;
* unknown-user 401 + no-leak / timing parity in ``test_security``;
* refresh rotation/blacklist in ``test_token_rotation`` / ``test_refresh_cookie``.

Covered HERE (previously untested branches): the explicit ``role`` disambiguation
param (select a specific account among email-sharing accounts), the ADMIN→
superuser/staff fallback, malformed-refresh 401, the phone-is-not-an-identifier
boundary, and enumeration parity on the *email* code path.
"""
import pytest
from rest_framework.test import APIClient

from django.contrib.auth import get_user_model

User = get_user_model()
pytestmark = [pytest.mark.django_db, pytest.mark.api]

PW = 'SharedPass123!@#'


def _me_role(client, access):
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
    resp = client.get('/api/accounts/me/')
    client.credentials()
    return resp


class TestRoleDisambiguation:
    """When several accounts share an email AND the same password, the explicit
    ``role`` field picks which one to authenticate (else admin-priority)."""

    def _two_accounts_same_email_same_password(self):
        email = 'dup@example.com'
        student = User.objects.create_user(
            username='dup_student', email=email, password=PW, role=User.Role.STUDENT,
        )
        teacher = User.objects.create_user(
            username='dup_teacher', email=email, password=PW, role=User.Role.TEACHER,
        )
        return email, student, teacher

    def test_role_param_selects_student(self):
        email, student, _ = self._two_accounts_same_email_same_password()
        client = APIClient()
        resp = client.post('/api/token/', {
            'username': email, 'password': PW, 'role': 'STUDENT',
        }, format='json')
        assert resp.status_code == 200, resp.content
        me = _me_role(client, resp.data['access'])
        assert me.status_code == 200
        assert me.data['username'] == student.username
        assert me.data['role'] == User.Role.STUDENT

    def test_role_param_selects_teacher(self):
        email, _, teacher = self._two_accounts_same_email_same_password()
        client = APIClient()
        resp = client.post('/api/token/', {
            'username': email, 'password': PW, 'role': 'TEACHER',
        }, format='json')
        assert resp.status_code == 200, resp.content
        me = _me_role(client, resp.data['access'])
        assert me.data['username'] == teacher.username
        assert me.data['role'] == User.Role.TEACHER

    def test_role_admin_falls_back_to_superuser_when_no_admin_role(self):
        """role='ADMIN' also matches a superuser/staff account whose role field
        isn't literally ADMIN (the documented fallback branch)."""
        email = 'ops@example.com'
        User.objects.create_user(
            username='plain_student', email=email, password=PW, role=User.Role.STUDENT,
        )
        superuser = User.objects.create_user(
            username='ops_super', email=email, password=PW, role=User.Role.TEACHER,
            is_superuser=True, is_staff=True,
        )
        client = APIClient()
        resp = client.post('/api/token/', {
            'username': email, 'password': PW, 'role': 'ADMIN',
        }, format='json')
        assert resp.status_code == 200, resp.content
        me = _me_role(client, resp.data['access'])
        assert me.data['username'] == superuser.username


class TestRefreshNegatives:
    def test_malformed_refresh_token_is_rejected(self):
        client = APIClient()
        resp = client.post(
            '/api/token/refresh/', {'refresh': 'not.a.real.jwt'}, format='json',
        )
        assert resp.status_code == 401

    def test_garbage_string_refresh_is_rejected(self):
        client = APIClient()
        resp = client.post(
            '/api/token/refresh/', {'refresh': 'xxxxxxxx'}, format='json',
        )
        assert resp.status_code == 401


class TestIdentifierBoundaries:
    def test_phone_is_not_a_token_identifier(self):
        """Login-by-identifier is username OR email only — NOT phone. A phone in
        the username field must fail closed (401), never mint a token."""
        User.objects.create_user(
            username='has_phone', password=PW, phone='09121234567',
            role=User.Role.STUDENT,
        )
        client = APIClient()
        resp = client.post('/api/token/', {
            'username': '09121234567', 'password': PW,
        }, format='json')
        assert resp.status_code == 401
        assert 'access' not in (resp.data or {})

    def test_email_path_enumeration_parity(self):
        """Known-email + wrong-password and unknown-email must be indistinguishable:
        both 401, neither leaking a token — no user enumeration on the email path."""
        User.objects.create_user(
            username='real', email='real@example.com', password=PW,
            role=User.Role.STUDENT,
        )
        client = APIClient()
        wrong_pw = client.post('/api/token/', {
            'username': 'real@example.com', 'password': 'WrongPass999!',
        }, format='json')
        unknown = client.post('/api/token/', {
            'username': 'ghost@example.com', 'password': 'WrongPass999!',
        }, format='json')
        assert wrong_pw.status_code == 401
        assert unknown.status_code == wrong_pw.status_code  # parity
        assert 'access' not in (wrong_pw.data or {})
        assert 'access' not in (unknown.data or {})
