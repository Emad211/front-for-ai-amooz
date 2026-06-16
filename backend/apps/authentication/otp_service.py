"""SMS one-time-password service for password reset.

Cache-backed (Redis) so there is no DB model/migration and the OTP auto-expires.
One active OTP per user, keyed by user id; the code is stored hashed (defense in
depth if the cache is dumped). Email is disabled platform-wide, so SMS (Mediana)
is the only delivery channel — and only password-using accounts (teachers /
managers / admins) can reset; students authenticate by invite code and have an
unusable password.
"""

from __future__ import annotations

import logging
import os
import secrets
import time

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.core.cache import cache

logger = logging.getLogger(__name__)
User = get_user_model()

OTP_TTL_SECONDS = int(os.getenv('PASSWORD_RESET_OTP_TTL_SECONDS', '600'))  # 10 min
OTP_MAX_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 90
_CACHE_PREFIX = 'pwreset:'


def _key(user_id) -> str:
    return f'{_CACHE_PREFIX}{user_id}'


def find_user_by_identifier(identifier: str):
    """Resolve a login identifier (username, or email if it contains '@')."""
    ident = (identifier or '').strip()
    if not ident:
        return None
    user = User.objects.filter(username=ident).first()
    if user is None and '@' in ident:
        user = User.objects.filter(email__iexact=ident).first()
    return user


def _generate_code() -> str:
    return f'{secrets.randbelow(1_000_000):06d}'


def _send_sms(phone: str, code: str) -> bool:
    api_key = (os.getenv('MEDIANA_API_KEY') or '').strip()
    if not api_key:
        logger.info('MEDIANA_API_KEY not set; skipping password-reset SMS')
        return False
    try:
        from apps.classes.services.mediana_sms import send_peer_to_peer_sms
        text = (
            'AI_AMOOZ\n'
            f'کد بازیابی رمز عبور شما: {code}\n'
            'این کد تا چند دقیقه معتبر است. اگر شما درخواست نداده‌اید، نادیده بگیرید.'
        )
        send_peer_to_peer_sms(
            api_key=api_key,
            requests=[{'RefId': f'pwreset-{phone}', 'TextMessage': text, 'Recipients': [phone]}],
        )
        return True
    except Exception:
        logger.exception('Password-reset SMS failed')
        return False


def issue_reset_otp(user) -> bool:
    """Generate + cache an OTP for the user and SMS it. Best-effort; never raises.

    Returns True if an SMS send was attempted. A short resend cooldown prevents
    SMS-bombing a victim's phone via repeated requests.
    """
    key = _key(user.id)
    now = time.time()
    existing = cache.get(key)
    if existing and now - existing.get('issued_at', 0) < RESEND_COOLDOWN_SECONDS:
        return False  # too soon — caller still returns a generic response

    code = _generate_code()
    cache.set(
        key,
        {'hash': make_password(code), 'attempts': 0, 'expires_at': now + OTP_TTL_SECONDS, 'issued_at': now},
        OTP_TTL_SECONDS + 60,
    )

    phone = (getattr(user, 'phone', '') or '').strip()
    if not phone:
        logger.info('Password-reset requested for user %s with no phone on file', user.id)
        return False
    return _send_sms(phone, code)


def verify_reset_otp(user, code: str) -> bool:
    """Verify a submitted OTP. Single-use; capped attempts; honors absolute expiry."""
    key = _key(user.id)
    rec = cache.get(key)
    if not rec:
        return False
    if time.time() > rec.get('expires_at', 0):
        cache.delete(key)
        return False
    if rec.get('attempts', 0) >= OTP_MAX_ATTEMPTS:
        cache.delete(key)
        return False
    if check_password((code or '').strip(), rec.get('hash', '')):
        cache.delete(key)  # single-use
        return True
    # Wrong code: count the attempt without extending the real expiry.
    rec['attempts'] = rec.get('attempts', 0) + 1
    remaining = max(1, int(rec['expires_at'] - time.time()) + 60)
    cache.set(key, rec, remaining)
    return False
