import pytest
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError


@pytest.mark.parametrize(
    'password',
    ['12345678', '________', 'رمزعبورقوی۱', 'lowercase1', 'UPPERCASE1', 'NoDigitsHere', 'Valid Pass1'],
)
def test_password_policy_rejects_non_compliant_passwords(password):
    with pytest.raises(ValidationError):
        validate_password(password)


def test_password_policy_accepts_ascii_upper_lower_and_digit():
    validate_password('StrongPass123!')
