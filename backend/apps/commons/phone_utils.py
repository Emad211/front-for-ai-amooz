"""Canonical Iranian-mobile phone normalization — the single source of truth.

The platform's student identity is keyed on phone (invite-code login, org-code
redemption, class-roster matching). For that key to be reliably unique, every
write/lookup site MUST canonicalize the phone the same way. Historically the
same algorithm was copy-pasted in three serializers and skipped entirely in a
few others, which let one human become two `User` rows. This module is the one
place that logic lives now.

Canonical form: ``09XXXXXXXXX`` (11 ASCII digits).
"""

from __future__ import annotations

# Persian (U+06F0–U+06F9) and Arabic-Indic (U+0660–U+0669) digits → ASCII.
# The legacy copies used ``str.isdigit()`` which is True for these glyphs but
# left them as-is, so a phone typed with Persian digits never matched the
# ``09…`` shape and was rejected/duplicated. Translate them first.
_DIGIT_MAP = str.maketrans(
    '۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩',
    '01234567890123456789',
)


def normalize_phone(raw: object) -> str:
    """Return the canonical ``09XXXXXXXXX`` form, best-effort.

    Strips everything but digits (after Persian/Arabic→ASCII), maps the common
    Iran prefixes to a leading zero. Does NOT validate — callers that need to
    reject bad input should pair this with :func:`is_valid_iran_mobile`.

    Examples: ``+98 912 000 0000`` → ``09120000000``; ``۰۹۱۲۰۰۰۰۰۰۰`` →
    ``09120000000``; ``9120000000`` → ``09120000000``.
    """
    s = str(raw or '').translate(_DIGIT_MAP)
    digits = ''.join(ch for ch in s if ch.isascii() and ch.isdigit())
    if digits.startswith('98') and len(digits) == 12:
        digits = '0' + digits[2:]
    if len(digits) == 10 and digits.startswith('9'):
        digits = '0' + digits
    return digits


def is_valid_iran_mobile(norm: str) -> bool:
    """True if ``norm`` is a canonical Iranian mobile (``09`` + 11 digits)."""
    return norm.startswith('09') and len(norm) == 11
