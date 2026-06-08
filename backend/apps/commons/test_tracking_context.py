"""Tests for the request-scoped, lazily-resolved LLM tracking user context.

The token tracker stashes the request and resolves the user only when an LLM
call reads it (avoids a redundant User SELECT on every request). This locks the
precedence + lazy-resolution + cleanup behavior that makes it safe under threaded
(gthread) workers.
"""
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model

from apps.commons import token_tracker as tt

User = get_user_model()
pytestmark = pytest.mark.django_db


def _fake_request(user=None, auth_header=None):
    meta = {}
    if auth_header is not None:
        meta['HTTP_AUTHORIZATION'] = auth_header
    return SimpleNamespace(user=user, META=meta)


def teardown_function():
    tt.clear_request_context()


def test_no_context_returns_none():
    tt.clear_request_context()
    assert tt.get_current_user() is None


def test_explicit_user_takes_precedence():
    u = User.objects.create_user(username='explicit', password='p')
    tt.set_current_user(u)
    # Even with a request stashed, the explicit user wins.
    tt.set_current_request(_fake_request(user=None))
    tt.set_current_user(u)
    assert tt.get_current_user() == u


def test_lazy_resolution_from_authenticated_request():
    # The request's already-authenticated user object is returned as-is.
    req = _fake_request(user=SimpleNamespace(is_authenticated=True, pk=42))
    tt.set_current_request(req)
    resolved = tt.get_current_user()
    assert resolved is req.user


def test_unauthenticated_request_resolves_to_none_and_caches():
    req = _fake_request(user=SimpleNamespace(is_authenticated=False), auth_header='')
    tt.set_current_request(req)
    assert tt.get_current_user() is None
    # cache sentinel set → second call still None without re-resolving
    assert tt.get_current_user() is None


def test_clear_resets_everything():
    u = User.objects.create_user(username='clearme', password='p')
    tt.set_current_user(u)
    tt.set_current_request(_fake_request(user=SimpleNamespace(is_authenticated=True, pk=u.pk)))
    tt.clear_request_context()
    assert tt.get_current_user() is None
