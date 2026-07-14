import pytest

from apps.authentication.serializers import InviteCodeLoginSerializer


@pytest.mark.parametrize('phone', ['09121234567', '+989121234567', '989121234567', '۹۱۲۱۲۳۴۵۶۷'])
def test_invite_login_normalizes_supported_phone_formats(phone):
    serializer = InviteCodeLoginSerializer(data={'code': 'INV-123', 'phone': phone})

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data['phone'] == '09121234567'


def test_invite_login_rejects_code_longer_than_model_contract():
    serializer = InviteCodeLoginSerializer(data={'code': 'x' * 65, 'phone': '09121234567'})

    assert not serializer.is_valid()
    assert 'code' in serializer.errors


def test_invite_login_rejects_overlong_or_invalid_phone():
    serializer = InviteCodeLoginSerializer(data={'code': 'INV-123', 'phone': '09' + ('1' * 30)})

    assert not serializer.is_valid()
    assert 'phone' in serializer.errors
