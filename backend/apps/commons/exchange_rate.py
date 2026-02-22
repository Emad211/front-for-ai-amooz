"""Fetch live USDT→Toman exchange rate from Tetherland API.

Cached in-memory with a configurable TTL to avoid hammering the API.
"""

from __future__ import annotations

import json
import logging
import ssl
import threading
import time
import urllib.request
from typing import Optional, Tuple

from django.conf import settings

logger = logging.getLogger(__name__)

TETHERLAND_API_URL = getattr(
    settings,
    'TETHERLAND_API_URL',
    'https://api.tetherland.com/currencies',
)

# In-memory cache
_lock = threading.Lock()
_cached_rate: Optional[float] = None
_cached_at: float = 0.0


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


def get_usdt_toman_rate(ttl_sec: float = 60.0) -> Tuple[Optional[float], Optional[str]]:
    """Get cached USDT→Toman rate with a short TTL.

    Returns:
        (rate, error) — rate is Toman per 1 USDT.
    """
    global _cached_rate, _cached_at
    now = time.time()

    with _lock:
        if _cached_rate is not None and (now - _cached_at) <= ttl_sec:
            return _cached_rate, None

    rate, err = fetch_usdt_toman_rate(timeout_sec=5.0)
    if rate is None:
        # Return stale cache if available
        with _lock:
            if _cached_rate is not None:
                logger.warning('Tetherland API failed (%s), using stale rate', err)
                return _cached_rate, err

        # Fallback from settings
        fallback = getattr(settings, 'USDT_TOMAN_FALLBACK', None)
        if fallback:
            fb_rate = _parse_float(fallback)
            if fb_rate is not None:
                return fb_rate, err

        return None, err

    with _lock:
        _cached_rate = rate
        _cached_at = now

    return rate, None


def usd_to_toman(usd_amount: float) -> Tuple[Optional[float], Optional[str]]:
    """Convert a USD amount to Toman using live USDT rate.

    Returns:
        (toman_amount, error)
    """
    rate, err = get_usdt_toman_rate()
    if rate is None:
        return None, err
    return round(usd_amount * rate, 0), None
