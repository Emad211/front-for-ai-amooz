"""Unit tests for the canonical phone normalizer (single source of truth)."""

import pytest

from apps.commons.phone_utils import is_valid_iran_mobile, normalize_phone


@pytest.mark.parametrize(
    'raw,expected',
    [
        ('09120000001', '09120000001'),        # already canonical
        ('+989120000001', '09120000001'),       # +98 prefix
        ('989120000001', '09120000001'),        # 98 prefix
        ('9120000001', '09120000001'),          # missing leading zero
        ('+98 912 000 0001', '09120000001'),    # spaces
        ('0912-000-0001', '09120000001'),       # dashes
        ('۰۹۱۲۰۰۰۰۰۰۱', '09120000001'),         # Persian digits
        ('٠٩١٢٠٠٠٠٠٠١', '09120000001'),         # Arabic-Indic digits
        ('', ''),                                # empty
        (None, ''),                              # None
    ],
)
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize(
    'norm,ok',
    [
        ('09120000001', True),
        ('0912000000', False),   # 10 digits
        ('091200000012', False), # 12 digits
        ('08120000001', False),  # wrong prefix
        ('', False),
    ],
)
def test_is_valid_iran_mobile(norm, ok):
    assert is_valid_iran_mobile(norm) is ok


def test_normalize_then_validate_cross_forms_agree():
    """All spellings of one number collapse to the same valid canonical form."""
    forms = ['09120000001', '+989120000001', '9120000001', '۰۹۱۲۰۰۰۰۰۰۱']
    canon = {normalize_phone(f) for f in forms}
    assert canon == {'09120000001'}
    assert is_valid_iran_mobile('09120000001')
