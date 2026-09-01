"""The parent-link lifecycle, OTP login and the Thursday digest fan-out.

Wave 5 (2026-08-31). The parent is the first advisory reader who is neither
the student nor the advisor, so this module is the write door for how that
read is granted — the parent-side counterpart of ``invites.py``. Three
properties, each load-bearing:

1. **Lookup only, never create on the advisor's say-so** (B4, inherited from
   ``invites.py``). An advisor naming a phone creates a PENDING *link*, not a
   user. The account is minted only by ``complete_parent_login`` — after an
   OTP was verified against a phone an advisor linked — and through the same
   ``accounts.services.get_or_create_user_by_phone`` seam every other
   phone-based onboarding uses.

2. **The OTP request is uniform** (B2). "Phone has a pending link", "phone
   has a parent account" and "phone is unknown to advisory" all answer
   ``202 {"status": "sent"}``; only the second path enqueues anything, and
   the code itself is sent by a worker task, never in the response.

3. **The OTP storage is the password-reset pattern, deliberately copied and
   keyed by phone instead of user id** (there may be no user yet — that is
   the point). Hashed code, 10-minute TTL, 5 attempts, 90-second resend
   cooldown. ``apps/authentication/otp_service.py`` is NOT modified: parents
   are an advisory concern and the two caches must never collide.

This file is on the ``test_import_boundaries`` exempt list, like ``invites.py``:
it constructs tenancy (the link row) rather than reading across it.
"""

from __future__ import annotations

import logging
import os
import secrets
import time

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.core.cache import cache
from django.db import transaction
from django.db import IntegrityError
from django.utils import timezone

from apps.accounts.services import get_or_create_user_by_phone
from apps.commons.phone_utils import is_valid_iran_mobile, normalize_phone

from ..models import (
    MAX_PARENTS_PER_STUDENT,
    PARENT_DIGEST_VIEW_ACTION,
    PARENT_RELATION_CHOICES,
    AdvisoryAccessLog,
    ParentLink,
)
from . import scope

logger = logging.getLogger(__name__)

MSG_BAD_PHONE = 'شمارهٔ همراه معتبر نیست (۰۹…).'
MSG_BAD_RELATION = 'نسبت والد معتبر نیست.'
MSG_QUOTA = 'حداکثر دو والد برای هر دانش‌آموز مجاز است.'
MSG_DUPLICATE_PHONE = 'این شماره قبلاً برای این دانش‌آموز ثبت شده است.'
MSG_BAD_OTP = 'کد واردشده درست یا معتبر نیست.'

# ── OTP policy (mirrors apps/authentication/otp_service.py, keyed by phone) ──
PARENT_OTP_TTL_SECONDS = 10 * 60
PARENT_OTP_MAX_ATTEMPTS = 5
PARENT_OTP_RESEND_COOLDOWN_SECONDS = 90
_OTP_CACHE_PREFIX = 'parotp:'

_RELATION_CODES = {code for code, _label in PARENT_RELATION_CHOICES}


class ParentLinkError(Exception):
    """Base class so a view can catch the whole family in one clause."""


def _display_name(user) -> str:
    full = ' '.join(filter(None, [user.first_name, user.last_name])).strip()
    return full or user.username


# ── advisor side: the invite lifecycle ────────────────────────────────────────

def enqueue_parent_invite_sms(*, phone: str, advisor_name: str) -> None:
    """Hand the invite SMS to the worker. Called exactly once per created link.

    Same deferred-import shape as ``invites.enqueue_invite``: ``tasks`` imports
    this module back, so both sides stay lazy and neither must load first.
    """
    from ..tasks import send_parent_invite_sms_task

    send_parent_invite_sms_task.delay(phone, advisor_name)


def advisor_create_parent_link(engagement, *, phone: str, relation: str, created_by):
    """Create the PENDING link for one parent phone, or raise ``ParentLinkError``.

    The quota counts standing links only (PENDING + ACTIVE): a REVOKED row is
    audit history, not a claim, so revoking frees the slot for a fresh invite.
    The unique constraint below the service (``uniq_active_parent_link``) is
    the same rule at the DB level for the same (engagement, phone) twice.
    """
    normalized = normalize_phone(phone)
    if not is_valid_iran_mobile(normalized):
        raise ParentLinkError(MSG_BAD_PHONE)
    if relation not in _RELATION_CODES:
        raise ParentLinkError(MSG_BAD_RELATION)

    standing = ParentLink.objects.filter(
        engagement=engagement,
        status__in=(ParentLink.Status.PENDING, ParentLink.Status.ACTIVE),
    )
    if standing.count() >= MAX_PARENTS_PER_STUDENT:
        raise ParentLinkError(MSG_QUOTA)
    if standing.filter(phone=normalized).exists():
        raise ParentLinkError(MSG_DUPLICATE_PHONE)

    try:
        link = ParentLink.objects.create(
            engagement=engagement,
            phone=normalized,
            relation=relation,
            status=ParentLink.Status.PENDING,
            created_by=created_by,
        )
    except IntegrityError:
        # Race with the partial unique constraint (engagement, phone).
        raise ParentLinkError(MSG_DUPLICATE_PHONE)
    enqueue_parent_invite_sms(phone=normalized, advisor_name=_display_name(created_by))
    return link


def advisor_parent_links(engagement):
    """Every link of one engagement, oldest first — PENDING and ACTIVE and
    REVOKED alike, because the advisor's list doubles as the revoke log."""
    return ParentLink.objects.filter(engagement=engagement).order_by('created_at', 'id')


def advisor_revoke_parent_link(engagement, link_id: int) -> ParentLink | None:
    """Revoke one of this engagement's standing links, or ``None`` (→ 404).

    A foreign link id and an already-revoked one are indistinguishable — the
    404-not-403 convention (ق۶), at the row level this time. Revoke keeps the
    row (audit trail); it never deletes.
    """
    link = (
        ParentLink.objects.filter(
            pk=link_id,
            engagement=engagement,
            status__in=(ParentLink.Status.PENDING, ParentLink.Status.ACTIVE),
        ).first()
    )
    if link is None:
        return None
    link.status = ParentLink.Status.REVOKED
    link.save(update_fields=['status'])
    return link


# ── the OTP half: issue over SMS, verify against the cache ────────────────────

def _otp_cache_key(phone: str) -> str:
    return f'{_OTP_CACHE_PREFIX}{phone}'


def _generate_code() -> str:
    return f'{secrets.randbelow(1_000_000):06d}'


def enqueue_parent_login_otp_sms(phone: str, code: str) -> None:
    """Send the OTP via the worker, never in-request (B2 latency uniformity)."""
    from ..tasks import send_parent_login_otp_sms_task

    send_parent_login_otp_sms_task.delay(phone, code)


def parent_login_target_exists(phone: str) -> bool:
    """True when this phone is a legitimate parent-login target.

    Two doors, deliberately both open: a PENDING/ACTIVE link (an advisor
    invited this number) OR an existing PARENT account (the human already
    claimed once; their links may have been revoked since, but their account
    is still theirs to log into).
    """
    User = get_user_model()
    return (
        ParentLink.objects.filter(
            phone=phone,
            status__in=(ParentLink.Status.PENDING, ParentLink.Status.ACTIVE),
        ).exists()
        or User.objects.filter(role=User.Role.PARENT, phone=phone).exists()
    )


def issue_parent_otp(phone: str) -> bool:
    """Generate + cache the OTP and enqueue its SMS. Honors the resend cooldown.

    Returns True when a code was actually issued. Mirrors
    ``otp_service.issue_reset_otp`` line for line except the cache key, so the
    two flows cannot share or evict each other's codes.
    """
    key = _otp_cache_key(phone)
    now = time.time()
    existing = cache.get(key)
    if existing and now - existing.get('issued_at', 0) < PARENT_OTP_RESEND_COOLDOWN_SECONDS:
        return False

    code = _generate_code()
    cache.set(
        key,
        {
            'hash': make_password(code),
            'attempts': 0,
            'expires_at': now + PARENT_OTP_TTL_SECONDS,
            'issued_at': now,
        },
        PARENT_OTP_TTL_SECONDS + 60,
    )
    enqueue_parent_login_otp_sms(phone, code)
    return True


def request_parent_login(phone: str) -> bool:
    """The request view's whole job: issue if (and only if) the phone is known.

    An unknown phone enqueues nothing yet still gets its 202 from the view —
    the no-leak rule. Raises ``ParentLinkError`` for a badly shaped number so
    the view can 400 on shape alone, which reveals nothing about the table.
    """
    normalized = normalize_phone(phone)
    if not is_valid_iran_mobile(normalized):
        raise ParentLinkError(MSG_BAD_PHONE)
    if not parent_login_target_exists(normalized):
        return False
    return issue_parent_otp(normalized)


def verify_parent_otp(phone: str, code: str) -> bool:
    """Verify a submitted OTP. Single-use; capped attempts; absolute expiry."""
    key = _otp_cache_key(normalize_phone(phone))
    record = cache.get(key)
    if not record:
        return False
    if time.time() > record.get('expires_at', 0):
        cache.delete(key)
        return False
    if record.get('attempts', 0) >= PARENT_OTP_MAX_ATTEMPTS:
        cache.delete(key)
        return False
    if check_password((code or '').strip(), record.get('hash', '')):
        cache.delete(key)  # single-use
        return True
    record['attempts'] = record.get('attempts', 0) + 1
    remaining = max(1, int(record['expires_at'] - time.time()) + 60)
    cache.set(key, record, remaining)
    return False


def complete_parent_login(phone: str):
    """Mint/fetch the PARENT account and claim every PENDING link for the phone.

    The account side goes through ``get_or_create_user_by_phone`` — the ONE
    phone→user seam — and the digest reader needs no onboarding of its own,
    so ``is_profile_completed`` is set immediately.

    The link claim is atomic under ``select_for_update``: two simultaneous
    verifies cannot double-claim or race the revoke path.
    """
    User = get_user_model()
    normalized = normalize_phone(phone)
    user, _created = get_or_create_user_by_phone(normalized, User.Role.PARENT)
    if not user.is_profile_completed:
        user.is_profile_completed = True
        user.save(update_fields=['is_profile_completed'])

    with transaction.atomic():
        links = ParentLink.objects.select_for_update().filter(
            phone=normalized,
            status=ParentLink.Status.PENDING,
        )
        today = timezone.localdate()
        for link in links:
            link.parent = user
            link.status = ParentLink.Status.ACTIVE
            link.activated_at = today
            link.save(update_fields=['parent', 'status', 'activated_at'])
    return user


# ── parent-side reads (the digest itself lives in parent_digest.py) ──────────

def parent_active_links(parent):
    """The links this parent may actually read: ACTIVE **and** on an ACTIVE
    engagement. A revoked link, an unclaimed PENDING one and an engagement
    that has since ended are all invisible, for the same reason the advisor's
    ``visible_engagements`` re-checks org membership live."""
    return (
        ParentLink.objects.filter(parent=parent, status=ParentLink.Status.ACTIVE)
        .filter(engagement__status='ACTIVE')
        .select_related('engagement__student', 'engagement__advisor')
        .order_by('created_at', 'id')
    )


def parent_digest_link(parent, link_id: int) -> ParentLink | None:
    """Resolve one digest link id out of the parent's readable set, or ``None``.

    Foreign, revoked and ended are all ``None`` → the view's 404. Same
    indistinguishability rule as ``scope.advisor_engagement``, one level down.
    """
    return parent_active_links(parent).filter(pk=link_id).first()


def student_active_parents(student):
    """The student's transparency list: ACTIVE links of their one engagement.

    Quiet by construction — a student with no active engagement gets an empty
    queryset, which the view renders as ``{"parents": []}``, never an error.
    """
    engagement = scope.student_active_engagement(student)
    if engagement is None:
        return ParentLink.objects.none()
    return ParentLink.objects.filter(
        engagement=engagement,
        status=ParentLink.Status.ACTIVE,
    ).order_by('created_at', 'id')


def record_parent_digest_view(engagement, reader) -> None:
    """Append the D4 line for a digest read — same shape as
    ``study_plans.record_study_feed_view``, one row per successful 200."""
    AdvisoryAccessLog.objects.create(
        reader=reader,
        engagement=engagement,
        action=PARENT_DIGEST_VIEW_ACTION,
    )


# ── the worker half: SMS bodies + the Thursday beat fan-out ───────────────────

def _send_mediana_sms(phone: str, text: str, ref_id: str) -> bool:
    """One Mediana send. Best-effort; never raises (a dead SMS provider must
    not fail a task that has already done its DB work)."""
    api_key = (os.getenv('MEDIANA_API_KEY') or '').strip()
    if not api_key:
        logger.info('MEDIANA_API_KEY not set; skipping parent SMS')
        return False
    try:
        from apps.classes.services.mediana_sms import send_peer_to_peer_sms

        send_peer_to_peer_sms(
            api_key=api_key,
            requests=[{
                'RefId': ref_id,
                'TextMessage': text,
                'Recipients': [phone],
            }],
        )
        return True
    except Exception:
        logger.exception('Parent SMS failed (ref=%s)', ref_id)
        return False


def send_parent_invite_sms(*, phone: str, advisor_name: str) -> bool:
    """The invite notification — carries NO code, link or token (B1): it says
    "an advisor linked you", and the OTP login is the only door that opens."""
    text = (
        'AI_AMOOZ\n'
        f'مشاور «{advisor_name}» شما را به‌عنوان والدِ دانش‌آموزش در '
        'سامانهٔ مشاورهٔ تحصیلی ثبت کرده است.\n'
        'برای دیدن گزارش هفتگی، با شمارهٔ خود وارد شوید.'
    )
    return _send_mediana_sms(phone, text, f'parinv-{phone}')


def send_parent_login_otp_sms(*, phone: str, code: str) -> bool:
    """The one credential-bearing SMS in the parent flow — the OTP itself,
    exactly like the password-reset SMS it mirrors."""
    text = f'کد ورود والدین: {code} — سامانهٔ مشاورهٔ تحصیلی'
    return _send_mediana_sms(phone, text, f'parotp-{phone}')


def _notify_parent_digest_ready(parent, student_name: str) -> bool:
    """The in-app half of the Thursday beat. Best-effort; never raises."""
    try:
        from apps.notification import services as notification_services

        message = 'گزارش هفتگی فرزند شما آماده است.'
        if student_name:
            message = f'گزارش هفتگی فرزند شما ({student_name}) آماده است.'
        notification_services.notify_user(
            recipient=parent,
            title='گزارش هفتگی مشاوره',
            message=message,
            notification_type='info',
            link='/parent',
            source='advisory',
        )
        return True
    except Exception:
        logger.exception('Parent weekly-digest feed notification failed')
        return False


def deliver_weekly_digest_notifications() -> dict:
    """The beat task body: every ACTIVE link on an ACTIVE engagement gets its
    "the weekly report is ready" nudge, in-app plus one short SMS that carries
    no credentials. Links with no user yet (invited, never logged in) are
    skipped silently — there is no account to notify in-app, and the invite
    SMS already told the phone the feature exists."""
    notified = skipped = failed = 0
    links = (
        ParentLink.objects.filter(
            status=ParentLink.Status.ACTIVE,
            engagement__status='ACTIVE',
        )
        .select_related('parent', 'engagement__student')
        .order_by('pk')
    )
    for link in links:
        if link.parent_id is None:
            skipped += 1
            continue
        try:
            student_name = _display_name(link.engagement.student)
            _notify_parent_digest_ready(link.parent, student_name)
            _send_mediana_sms(
                link.phone,
                'AI_AMOOZ\nگزارش هفتگی فرزند شما در سامانهٔ مشاورهٔ تحصیلی آماده است.',
                f'pardig-{link.pk}',
            )
            notified += 1
        except Exception:  # noqa: BLE001 — one bad link must not stop the batch
            failed += 1
            logger.exception('Parent weekly digest failed for link %s', link.pk)
    return {'notified': notified, 'skipped_unlinked': skipped, 'failed': failed}
