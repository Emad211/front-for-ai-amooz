"""Contract tests for the per-endpoint brute-force throttles (login-audit Batch B)."""

import importlib

from rest_framework.test import APIRequestFactory

from apps.core.throttling import SafeScopedRateThrottle
from apps.authentication.views import RegisterView, InviteCodeLoginView
from apps.organizations.views import RedeemInvitationView
from core.urls import TokenObtainPairViewDocs


def _assert_scoped(view_cls, scope):
    assert getattr(view_cls, 'throttle_scope', None) == scope, f'{view_cls} scope'
    classes = getattr(view_cls, 'throttle_classes', [])
    assert any(issubclass(c, SafeScopedRateThrottle) for c in classes), f'{view_cls} throttle_classes'


def test_credential_endpoints_declare_scoped_throttles():
    _assert_scoped(TokenObtainPairViewDocs, 'login')
    _assert_scoped(InviteCodeLoginView, 'invite_login')
    _assert_scoped(RegisterView, 'register')
    _assert_scoped(RedeemInvitationView, 'redeem')


def test_throttle_rates_configured_in_settings():
    # Read from the module (conftest clears the LIVE rates during tests).
    rates = importlib.import_module('core.settings').REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']
    for scope in ('login', 'invite_login', 'register', 'redeem'):
        assert rates.get(scope), f'missing rate for scope {scope}'


def test_safe_throttle_noops_when_rate_missing():
    # conftest clears DEFAULT_THROTTLE_RATES → the throttle must allow the request
    # (return True) and NOT raise ImproperlyConfigured. This is what keeps the
    # suite green even though these views hardcode throttle_classes.
    class _DummyView:
        throttle_scope = 'login'

    request = APIRequestFactory().post('/api/token/')
    assert SafeScopedRateThrottle().allow_request(request, _DummyView()) is True
