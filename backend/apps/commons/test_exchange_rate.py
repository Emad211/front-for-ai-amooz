"""Tests for the request-path-safe USDT→Toman rate accessor.

The read path (get_usdt_toman_rate / convert_usd_to_toman) must serve from the
shared cache or a settings fallback and NEVER make a blocking network call — the
live rate is refreshed by a Celery-beat task.
"""
import pytest
from django.core.cache import cache
from django.test import override_settings

from apps.commons import exchange_rate as ex

pytestmark = pytest.mark.django_db


def _boom(*a, **k):
    raise AssertionError('fetch_usdt_toman_rate must NOT be called on the read path')


def setup_function():
    cache.delete(ex._RATE_CACHE_KEY)


def test_read_path_never_fetches_uses_fallback(monkeypatch):
    monkeypatch.setattr(ex, 'fetch_usdt_toman_rate', _boom)
    cache.delete(ex._RATE_CACHE_KEY)
    with override_settings(USDT_TOMAN_FALLBACK=90000):
        rate, err = ex.get_usdt_toman_rate()
    assert rate == 90000
    assert err  # signals "fallback in use"


def test_read_path_prefers_cached_rate(monkeypatch):
    monkeypatch.setattr(ex, 'fetch_usdt_toman_rate', _boom)
    cache.set(ex._RATE_CACHE_KEY, 123456, 60)
    rate, err = ex.get_usdt_toman_rate()
    assert rate == 123456
    assert err is None


def test_convert_uses_rate_and_returns_snapshot(monkeypatch):
    monkeypatch.setattr(ex, 'fetch_usdt_toman_rate', _boom)
    cache.set(ex._RATE_CACHE_KEY, 100000, 60)
    toman, rate, _err = ex.convert_usd_to_toman(0.5)
    assert rate == 100000
    assert toman == 50000


def test_refresh_writes_cache(monkeypatch):
    cache.delete(ex._RATE_CACHE_KEY)
    monkeypatch.setattr(ex, 'fetch_usdt_toman_rate', lambda timeout_sec=8.0: (111111, None))
    rate, err = ex.refresh_usdt_toman_rate()
    assert rate == 111111 and err is None
    assert cache.get(ex._RATE_CACHE_KEY) == 111111
