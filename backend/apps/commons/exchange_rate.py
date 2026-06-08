"""USDT→Toman exchange rate.

The live rate is fetched from the Tetherland API by a Celery-beat task
(``apps.commons.tasks.refresh_usdt_toman_rate_task``) and stored in the SHARED
Redis cache. The request / LLM-write path (``get_usdt_toman_rate`` →
``convert_usd_to_toman``) only ever reads the cache (or a settings fallback) and
must NEVER make a blocking network call — token tracking runs on every LLM write,
so a slow/down external FX API there would tie up gunicorn workers under load.
"""

from __future__ import annotations

import json
import logging
import ssl
import urllib.request
from typing import Optional, Tuple

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

TETHERLAND_API_URL = getattr(
    settings,
    'TETHERLAND_API_URL',
    'https://api.tetherland.com/currencies',
)

# Shared-cache key + TTL. The TTL is comfortably longer than the beat interval
# so a single missed refresh doesn't drop callers back to the fallback.
_RATE_CACHE_KEY = 'usdt_toman_rate'
_RATE_CACHE_TTL = 60 * 60  # 1 hour


def _parse_float(value: object) -> Optional[float]:
    """Safely parse a numeric value to float."""
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value).strip().replace(',', '')
        return float(s)
    except (ValueError, TypeError):
        return None


def fetch_usdt_toman_rate(timeout_sec: float = 5.0) -> Tuple[Optional[float], Optional[str]]:
    """Fetch live USDT price in Toman from Tetherland API.

    Returns:
        (rate, error) — rate is Toman per 1 USDT, or None on failure.
    """
    ctx = ssl.create_default_context()
    last_err: Optional[str] = None

    for attempt in range(2):
        try:
            req = urllib.request.Request(
                TETHERLAND_API_URL,
                headers={'User-Agent': 'AI-AMOOZ/1.0'},
                method='GET',
            )
            with urllib.request.urlopen(req, timeout=timeout_sec, context=ctx) as resp:
                raw = resp.read().decode('utf-8', errors='ignore')
            data = json.loads(raw)
            break
        except Exception as exc:
            last_err = str(exc)
            data = None
    else:
        return None, last_err or 'Failed to fetch Tetherland rate'

    try:
        # Tetherland shape: data -> currencies -> USDT -> price
        usdt_info = (((data or {}).get('data') or {}).get('currencies') or {}).get('USDT')
        if isinstance(usdt_info, dict):
            rate = _parse_float(usdt_info.get('price'))
            if rate is not None and rate > 0:
                return rate, None

        return None, 'No USDT price field in Tetherland response'
    except Exception as exc:
        return None, str(exc)


def _fallback_rate() -> Optional[float]:
    return _parse_float(getattr(settings, 'USDT_TOMAN_FALLBACK', None))


def refresh_usdt_toman_rate(timeout_sec: float = 8.0) -> Tuple[Optional[float], Optional[str]]:
    """Fetch the live rate and store it in the SHARED cache.

    Called by the Celery-beat task — NEVER on the request path. Returns
    ``(rate, error)``.
    """
    rate, err = fetch_usdt_toman_rate(timeout_sec=timeout_sec)
    if rate is not None:
        try:
            cache.set(_RATE_CACHE_KEY, rate, _RATE_CACHE_TTL)
        except Exception:  # pragma: no cover - cache write must never break refresh
            logger.warning('Could not write USDT rate to cache', exc_info=True)
    return rate, err


def get_usdt_toman_rate(ttl_sec: float | None = None) -> Tuple[Optional[float], Optional[str]]:
    """Return the USDT→Toman rate WITHOUT any blocking network call.

    Reads the shared cache (kept fresh by ``refresh_usdt_toman_rate_task``);
    falls back to ``settings.USDT_TOMAN_FALLBACK`` until the first refresh lands
    or if the FX API is unavailable. ``ttl_sec`` is accepted for backwards
    compatibility and ignored.

    Returns:
        (rate, error) — rate is Toman per 1 USDT, or ``None`` if neither a
        cached rate nor a fallback is configured.
    """
    try:
        cached = cache.get(_RATE_CACHE_KEY)
    except Exception:  # pragma: no cover - cache read must never break tracking
        cached = None
    if cached is not None:
        return cached, None

    fb = _fallback_rate()
    if fb is not None:
        return fb, 'using fallback rate (live rate not cached yet)'
    return None, 'no USDT rate available (cache empty and no USDT_TOMAN_FALLBACK)'


def usd_to_toman(usd_amount: float) -> Tuple[Optional[float], Optional[str]]:
    """Convert a USD amount to Toman using live USDT rate.

    Returns:
        (toman_amount, error)
    """
    rate, err = get_usdt_toman_rate()
    if rate is None:
        return None, err
    return round(usd_amount * rate, 0), None


def convert_usd_to_toman(usd_amount: float) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """Convert USD to Toman and also return the rate that was applied.

    Unlike :func:`usd_to_toman`, this exposes the rate so callers (e.g. the
    token tracker) can snapshot it on each row for an audit trail.

    Returns:
        (toman_amount, rate, error) — ``toman_amount``/``rate`` are ``None``
        when no rate (live, stale, or fallback) is available.
    """
    rate, err = get_usdt_toman_rate()
    if rate is None:
        return None, None, err
    return round(usd_amount * rate, 0), rate, err
