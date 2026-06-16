"""Waitlist approval / rejection logic and SMS notification.

Approval is the heart of the gate:
- teacher  → mint a one-time registration token (consumed later in Phase 3).
- organization → provision the Organization + admin activation code (the manager
  redeems that code at `/org-login`); the code doubles as the registration token.

SMS is best-effort (Mediana) and never breaks the approval transaction.
"""

from __future__ import annotations

import logging
import os
import secrets
from datetime import timedelta
from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.organizations.services import generate_unique_org_slug, provision_organization

from .models import AccessRequest

logger = logging.getLogger(__name__)
User = get_user_model()

REGISTRATION_TOKEN_TTL_DAYS = 14


class InvalidRegistrationToken(Exception):
    """Raised when a teacher registration token is missing, expired, or used."""


def generate_registration_token() -> str:
    return secrets.token_urlsafe(32)


def approve_access_request(access_request: AccessRequest, reviewer) -> AccessRequest:
    """Approve a request and stamp review metadata.

    Caller must guard terminal states (only PENDING/CONTACTED should reach here).
    """
    ar = access_request
    ar.status = AccessRequest.Status.APPROVED
    ar.reviewed_by = reviewer
    ar.reviewed_at = timezone.now()
    ar.token_expires_at = timezone.now() + timedelta(days=REGISTRATION_TOKEN_TTL_DAYS)

    if ar.kind == AccessRequest.Kind.ORGANIZATION:
        org, admin_code = provision_organization(
            data={
                'name': ar.org_name or ar.full_name,
                'slug': generate_unique_org_slug(),
                'student_capacity': ar.expected_students or 100,
            },
            created_by=reviewer,
            owner=None,
        )
        ar.created_organization = org
        # For orgs, the manager registers by redeeming the admin code — so the
        # code IS the registration token.
        ar.registration_token = admin_code or ''
    else:
        ar.registration_token = generate_registration_token()

    ar.save(update_fields=[
        'status', 'reviewed_by', 'reviewed_at', 'token_expires_at',
        'created_organization', 'registration_token', 'updated_at',
    ])
    return ar


def _split_name(full_name: str, first: str, last: str) -> tuple[str, str]:
    """Prefer explicit names; otherwise split the request's full_name on the
    first space."""
    if first or last:
        return (first or '').strip(), (last or '').strip()
    parts = (full_name or '').strip().split(' ', 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return (parts[0] if parts and parts[0] else ''), ''


@transaction.atomic
def complete_teacher_registration(*, token, username, password, first_name='', last_name=''):
    """Consume an approved TEACHER token and create the real teacher account.

    Returns ``(user, access_request)``. Raises ``InvalidRegistrationToken`` if the
    token is unknown, not approved, already consumed, or expired. The row is
    locked (``select_for_update``) so a token can't be consumed twice in a race.
    """
    from apps.accounts.models import TeacherProfile

    ar = (
        AccessRequest.objects.select_for_update()
        .filter(
            registration_token=token,
            kind=AccessRequest.Kind.TEACHER,
            status=AccessRequest.Status.APPROVED,
            token_consumed_at__isnull=True,
        )
        .first()
    )
    if ar is None:
        raise InvalidRegistrationToken('لینک ثبت‌نام نامعتبر یا قبلاً استفاده شده است.')
    if not token:
        raise InvalidRegistrationToken('توکن ثبت‌نام نامعتبر است.')
    if ar.token_expires_at and ar.token_expires_at < timezone.now():
        raise InvalidRegistrationToken('مهلت این لینک ثبت‌نام به پایان رسیده است.')

    first, last = _split_name(ar.full_name, first_name, last_name)
    user = User.objects.create_user(
        username=username,
        password=password,
        role=User.Role.TEACHER,
        email=ar.email or '',
        first_name=first,
        last_name=last,
        is_freelancer=True,  # waitlist teachers are freelancers (own personal space)
    )
    if ar.phone:
        user.phone = ar.phone
        user.save(update_fields=['phone'])
    # Approved by a platform admin → mark the teacher profile verified. An
    # accounts post_save signal already created the profile (vs=False) and the
    # `save_user_profile` signal re-saves the *cached* reverse relation on every
    # user.save(); so we update the row AND refresh user.teacherprofile, or a
    # later user.save() (e.g. update_last_login in the view) would clobber it.
    profile, _ = TeacherProfile.objects.update_or_create(
        user=user, defaults={'verification_status': True},
    )
    user.teacherprofile = profile

    ar.created_user = user
    ar.token_consumed_at = timezone.now()
    ar.save(update_fields=['created_user', 'token_consumed_at', 'updated_at'])
    return user, ar


def reject_access_request(access_request: AccessRequest, reviewer, reason: str = '') -> AccessRequest:
    ar = access_request
    ar.status = AccessRequest.Status.REJECTED
    ar.reviewed_by = reviewer
    ar.reviewed_at = timezone.now()
    ar.reject_reason = (reason or '').strip()[:255]
    ar.save(update_fields=[
        'status', 'reviewed_by', 'reviewed_at', 'reject_reason', 'updated_at',
    ])
    return ar


# ── Notification (SMS, best-effort) ─────────────────────────────────────────

def _resolve_frontend_base(explicit: str = '') -> str:
    """Pick the frontend origin for building registration links.

    Priority: an explicit value (the approving admin's request ``Origin`` —
    captured in the view, so links work with zero config) → ``FRONTEND_BASE_URL``
    env. Normalized to ``scheme://host`` (no path/trailing slash); a bare host is
    assumed https.
    """
    for candidate in (explicit, os.getenv('FRONTEND_BASE_URL') or ''):
        c = (candidate or '').strip()
        if not c:
            continue
        parts = urlsplit(c if '//' in c else f'https://{c}')
        if parts.scheme and parts.netloc:
            return f'{parts.scheme}://{parts.netloc}'
    return ''


def _registration_link(token: str, frontend_base: str = '') -> str:
    base = _resolve_frontend_base(frontend_base)
    return f'{base}/register/complete?token={token}' if base else ''


def build_approval_sms_text(access_request: AccessRequest, frontend_base: str = '') -> str:
    ar = access_request
    if ar.kind == AccessRequest.Kind.ORGANIZATION:
        base = _resolve_frontend_base(frontend_base)
        tail = (
            f'ثبت‌نام مدیر سازمان:\n{base}/org-login'
            if base
            else 'با این کد در صفحه «ورود سازمانی» ثبت‌نام کنید.'
        )
        return (
            'AI_AMOOZ\n'
            f'درخواست سازمان «{ar.org_name}» تأیید شد.\n'
            f'کد فعال‌سازی مدیر: {ar.registration_token}\n'
            f'{tail}'
        )
    tail = _registration_link(ar.registration_token, frontend_base) or f'کد ثبت‌نام: {ar.registration_token}'
    return (
        'AI_AMOOZ\n'
        'درخواست شما برای عضویت به عنوان معلم تأیید شد.\n'
        f'برای تکمیل ثبت‌نام روی لینک بزنید:\n{tail}'
    )


def notify_access_request_approved(access_request: AccessRequest, frontend_base: str = '') -> bool:
    """Best-effort approval SMS. Never raises. Returns True if a send was attempted.

    ``frontend_base`` (the approving admin's request Origin) lets the SMS carry a
    clickable registration link without any env configuration.
    """
    ar = access_request
    api_key = (os.getenv('MEDIANA_API_KEY') or '').strip()
    if not api_key:
        logger.info('MEDIANA_API_KEY not set; skipping approval SMS for access_request=%s', ar.pk)
        return False
    phone = (ar.phone or '').strip()
    if not phone:
        return False
    try:
        from apps.classes.services.mediana_sms import send_peer_to_peer_sms
        send_peer_to_peer_sms(
            api_key=api_key,
            requests=[{
                'RefId': f'waitlist-approve-{ar.pk}',
                'TextMessage': build_approval_sms_text(ar, frontend_base),
                'Recipients': [phone],
            }],
        )
        return True
    except Exception:
        logger.exception('Approval SMS failed for access_request=%s', ar.pk)
        return False
