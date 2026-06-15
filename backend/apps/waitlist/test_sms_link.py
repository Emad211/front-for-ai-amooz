"""Unit tests for the approval-SMS link builder (no DB, no network)."""

from apps.waitlist.models import AccessRequest
from apps.waitlist.services import build_approval_sms_text


def _teacher(token='abc123'):
    return AccessRequest(
        kind=AccessRequest.Kind.TEACHER, full_name='علی', phone='09120000000',
        registration_token=token,
    )


def _org(token='ORG1'):
    return AccessRequest(
        kind=AccessRequest.Kind.ORGANIZATION, full_name='مدیر', phone='09120000001',
        org_name='مدرسه البرز', registration_token=token,
    )


def test_teacher_sms_has_clickable_link_from_origin():
    text = build_approval_sms_text(_teacher('tok9'), frontend_base='https://app.example.com')
    assert 'https://app.example.com/register/complete?token=tok9' in text
    assert 'کد ثبت‌نام:' not in text


def test_origin_with_path_and_query_is_normalized():
    text = build_approval_sms_text(
        _teacher('tok9'), frontend_base='https://app.example.com/admin/waitlist?x=1'
    )
    assert 'https://app.example.com/register/complete?token=tok9' in text


def test_bare_host_is_assumed_https():
    text = build_approval_sms_text(_teacher('tok9'), frontend_base='app.example.com')
    assert 'https://app.example.com/register/complete?token=tok9' in text


def test_falls_back_to_token_without_base(monkeypatch):
    monkeypatch.delenv('FRONTEND_BASE_URL', raising=False)
    text = build_approval_sms_text(_teacher('tok9'))
    assert 'کد ثبت‌نام: tok9' in text
    assert 'register/complete' not in text


def test_uses_env_when_no_origin(monkeypatch):
    monkeypatch.setenv('FRONTEND_BASE_URL', 'https://aiamooz.ir/')
    text = build_approval_sms_text(_teacher('tok9'))
    assert 'https://aiamooz.ir/register/complete?token=tok9' in text


def test_explicit_origin_beats_env(monkeypatch):
    monkeypatch.setenv('FRONTEND_BASE_URL', 'https://env.example.com')
    text = build_approval_sms_text(_teacher('tok9'), frontend_base='https://origin.example.com')
    assert 'https://origin.example.com/register/complete?token=tok9' in text


def test_org_sms_has_org_login_link():
    text = build_approval_sms_text(_org('ORG9'), frontend_base='https://app.example.com')
    assert 'https://app.example.com/org-login' in text
    assert 'کد فعال‌سازی مدیر: ORG9' in text


def test_org_sms_without_base_keeps_instruction(monkeypatch):
    monkeypatch.delenv('FRONTEND_BASE_URL', raising=False)
    text = build_approval_sms_text(_org('ORG9'))
    assert 'ORG9' in text
    assert 'org-login' not in text
