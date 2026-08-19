"""The invite lifecycle: an advisor offers, a student claims — or does not.

This module exists because the invite is the **only** place in the advisory
feature where one user names another by phone number, which makes it the only
place that can be turned into an oracle. Three properties are load-bearing and
every function here is shaped by them:

1. **Lookup only, never create** (B4). ``accounts.User`` has a partial unique
   constraint ``uniq_student_phone``, so a phone number *is* a platform identity.
   Advisory must never call ``get_or_create_student_by_phone``: an advisor typing
   a wrong digit would otherwise mint a real account for a stranger's number, and
   that account is reachable by passwordless invite-code login.

2. **No credential ever leaves over SMS** (B1). The platform's stable invite code
   is a permanent passwordless credential (``authentication/views.py`` turns
   code + phone straight into a JWT). Advisory sends a *notification* only. The
   authority to accept is an authenticated session belonging to exactly the
   invited student, re-verified against the phone the invite was addressed to.

3. **The response is uniform, in content and in latency** (B2). "Student exists",
   "no such number", "on cooldown" and "blocked by a past rejection" are four
   different facts about a phone number, and the caller must not be able to tell
   them apart. So the view does no phone-dependent work at all: it validates the
   shape of the string, charges the quota, enqueues **exactly one** background
   task and answers ``202 {"status": "sent"}``. Everything that depends on who
   owns the number happens in the worker, where the advisor cannot time it.

The module is also, deliberately, the one non-``scope.py`` file allowed to import
``AdvisoryEngagement``: it *constructs* tenancy rather than reading across it, so
there is no queryset here to scope. See ``test_import_boundaries``.
"""

from __future__ import annotations

import datetime
import logging
import os

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.commons.phone_utils import is_valid_iran_mobile, normalize_phone

from ..models import INVITE_TTL_DAYS, REJECT_BLOCK_DAYS, AdvisoryEngagement
from .text import mask_phone

logger = logging.getLogger(__name__)

# ── B3: four independent limits, each closing a different abuse ───────────────
# The DRF scope 'advisory_invite' (10/hour) is the first and lives in settings;
# without it an authenticated SMS trigger would inherit the generic 'user' scope
# of 300/minute, i.e. 18000 SMS an hour from one account.

# One SMS per phone per day, across ALL advisors. This is the anti-bombing limit:
# it is keyed on the victim's number, not on the sender, so ten advisors cannot
# take turns. It gates the *SMS only* — the engagement row is still created, so a
# second advisor's invite is not lost, it is just silent.
PHONE_COOLDOWN_SECONDS = 24 * 60 * 60

# A working freelance advisor onboards a handful of students a week. 30/day is
# far above real use and far below a campaign.
ADVISOR_DAILY_INVITE_CAP = 30

# Open, unanswered invites. Distinct from the daily cap: it bounds the *standing*
# claim an advisor can hold over other people's accounts, which a daily cap alone
# would let them accumulate one day at a time.
ADVISOR_OPEN_PENDING_CAP = 50

# Platform-wide breaker. If advisory as a whole ever tries to send more than this
# in a day, something is wrong (a bug, a compromised account) and the right answer
# is to stop sending, not to keep paying the SMS bill.
PLATFORM_DAILY_INVITE_CAP = 2000

_CACHE_PREFIX = 'advinv:'
_COUNTER_TTL_SECONDS = 26 * 60 * 60  # a day-stamped key only needs to outlive its day


class InviteError(Exception):
    """Base class so a view can catch the whole family in one clause."""


class InviteNotFound(InviteError):
    """404. Also raised for a wrong claimant or an expired invite.

    Never 403: a 403 confirms the row exists, which tells an attacker that some
    advisor has invited this person. B6 makes the absence indistinguishable from
    the lack of permission.
    """


class InviteConflict(InviteError):
    """409 — the invite was real but the transition is no longer possible."""


class InviteQuotaExceeded(InviteError):
    """One of the B3 limits tripped. ``kind`` selects the status code."""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message


# ── quota bookkeeping ─────────────────────────────────────────────────────────

def _day_key(*parts: object) -> str:
    """A key that resets itself at local midnight instead of on a rolling window.

    "30 per day" is what an advisor was told; a day-stamped key is exactly that,
    with no sorted-set bookkeeping and no way for a stale window to leak quota.
    """
    return _CACHE_PREFIX + ':'.join([*(str(p) for p in parts), timezone.localdate().isoformat()])


def _bump(key: str) -> int:
    """Atomically increment a counter, creating it at 0 first.

    ``cache.add`` is a SETNX, so exactly one racing caller creates the key and
    both then increment — the naive ``incr``-except-``set`` version silently
    loses one count per race, which is the difference between a cap and a
    suggestion.
    """
    cache.add(key, 0, _COUNTER_TTL_SECONDS)
    try:
        return int(cache.incr(key))
    except ValueError:
        # The key expired between add and incr. Treat as the first of a new day.
        cache.set(key, 1, _COUNTER_TTL_SECONDS)
        return 1


def charge_invite_quota(advisor, *, open_pending_count: int) -> None:
    """Spend one invite from every budget, or raise ``InviteQuotaExceeded``.

    Counters are incremented *before* the comparison rather than after. Under
    concurrency a check-then-increment lets N simultaneous requests all read the
    same under-limit value and all pass; bump-then-compare cannot. The cost is
    that a rejected attempt still consumes quota, which for an abuse limit is a
    feature.

    Order is deliberate: the platform breaker is charged before the per-advisor
    budget, so a platform-wide incident does not also burn through the quota of
    every innocent advisor who happened to be working at the time.
    """
    if open_pending_count >= ADVISOR_OPEN_PENDING_CAP:
        raise InviteQuotaExceeded(
            'open_pending',
            f'شما {ADVISOR_OPEN_PENDING_CAP} دعوت‌نامه‌ی بی‌پاسخ دارید. '
            'تا پاسخ‌گرفتن یا انقضای آن‌ها، دعوت جدید ممکن نیست.',
        )

    if _bump(_day_key('platform')) > PLATFORM_DAILY_INVITE_CAP:
        logger.error('Advisory invite platform breaker tripped for today')
        raise InviteQuotaExceeded(
            'platform',
            'ارسال دعوت‌نامه موقتاً در دسترس نیست. کمی بعد دوباره تلاش کنید.',
        )

    if _bump(_day_key('advisor', advisor.pk)) > ADVISOR_DAILY_INVITE_CAP:
        raise InviteQuotaExceeded(
            'advisor_daily',
            f'سقف ارسال دعوت‌نامه در یک روز {ADVISOR_DAILY_INVITE_CAP} است. فردا دوباره تلاش کنید.',
        )


def enqueue_invite(*, advisor_id: int, phone: str) -> None:
    """Hand the invite to the worker. Exactly one call, unconditionally.

    Lives here rather than in the view so that the B2 latency property has a
    single implementation to point at: whatever the phone number turns out to be,
    the request does this and nothing else. A view that branched — "look up the
    student first, only enqueue if found" — would be uniform in body and still
    leak through the clock.

    The import is deferred because ``tasks`` imports this module back; both sides
    keep it lazy so neither can be loaded first.
    """
    from ..tasks import deliver_advisory_invite_task

    deliver_advisory_invite_task.delay(advisor_id, phone)


# ── the worker half: everything that depends on who owns the number ──────────

def _phone_cooldown_key(phone: str) -> str:
    return f'{_CACHE_PREFIX}phone:{phone}'


def _send_invite_sms(*, phone: str, advisor) -> bool:
    """Notify the student that an invite is waiting. Best-effort; never raises.

    Contains **no code, link or token** — only "open the app". That is what makes
    it safe to send: an intercepted message grants nothing, so there is no need
    for the short-lived hashed secret B1 requires of anything that *is* a
    credential. Failure to send is not failure to invite: the engagement row is
    already committed and the student sees the banner on their next visit.
    """
    api_key = (os.getenv('MEDIANA_API_KEY') or '').strip()
    if not api_key:
        logger.info('MEDIANA_API_KEY not set; skipping advisory invite SMS')
        return False
    try:
        from apps.classes.services.mediana_sms import send_peer_to_peer_sms

        advisor_name = (
            ' '.join(filter(None, [advisor.first_name, advisor.last_name])).strip()
            or advisor.username
        )
        text = (
            'AI_AMOOZ\n'
            f'مشاور «{advisor_name}» برای شما درخواست همکاری فرستاده است.\n'
            'برای دیدن و تأیید، وارد حساب کاربری خود شوید.'
        )
        send_peer_to_peer_sms(
            api_key=api_key,
            requests=[{
                'RefId': f'advinv-{phone}',
                'TextMessage': text,
                'Recipients': [phone],
            }],
        )
        return True
    except Exception:
        logger.exception('Advisory invite SMS failed')
        return False


def deliver_invite(*, advisor_id: int, phone: str) -> dict:
    """Resolve a phone number to a student and create the PENDING engagement.

    Runs in a worker, never in a request. Returns a small dict for the Celery
    result — the phone is masked in it, because task results are readable from
    Flower and the result backend.

    Every ``return`` below is a *different* fact about the number, and none of
    them reaches the advisor: the view already answered ``202``.
    """
    User = get_user_model()
    normalized = normalize_phone(phone)
    if not is_valid_iran_mobile(normalized):
        return {'status': 'invalid_phone'}

    advisor = User.objects.filter(pk=advisor_id, role='ADVISOR').first()
    if advisor is None:
        # Demoted between enqueue and execution. Not an error worth retrying.
        return {'status': 'advisor_gone'}

    student = User.objects.filter(role=User.Role.STUDENT, phone=normalized).first()
    if student is None:
        # B4: no account is created. A freelance advisor whose student has not
        # registered yet has to wait for them to register — supporting that case
        # needs a phone-only invite table, which is a post-MVP step, NOT a
        # get_or_create here.
        return {'status': 'no_student'}

    if student.pk == advisor.pk:
        return {'status': 'self_invite'}

    # B6: a rejection is a real answer, not a rate limit. The same pair is blocked
    # for 30 days, counted from when the student said no.
    block_since = timezone.now() - datetime.timedelta(days=REJECT_BLOCK_DAYS)
    recently_rejected = AdvisoryEngagement.objects.filter(
        advisor=advisor,
        student=student,
        status=AdvisoryEngagement.Status.REJECTED,
        ended_at__gte=block_since,
    ).exists()
    if recently_rejected:
        return {'status': 'reject_blocked'}

    already_open = AdvisoryEngagement.objects.filter(
        advisor=advisor,
        student=student,
        status=AdvisoryEngagement.Status.PENDING,
    ).exists()
    if already_open:
        # The partial unique constraint would refuse the insert anyway; checking
        # first keeps the log free of IntegrityErrors that mean nothing.
        return {'status': 'already_pending'}

    try:
        with transaction.atomic():
            engagement = AdvisoryEngagement.objects.create(
                advisor=advisor,
                student=student,
                invited_phone=normalized,
                mode=AdvisoryEngagement.Mode.FREELANCE,
                organization=None,
                status=AdvisoryEngagement.Status.PENDING,
                invite_expires_at=timezone.now() + datetime.timedelta(days=INVITE_TTL_DAYS),
            )
    except IntegrityError:
        # Lost a race with another worker on the same pair.
        return {'status': 'already_pending'}

    # An engagement is created even when the student already has an ACTIVE
    # advisor: the invite is harmless while it waits, may become claimable if the
    # current engagement ends, and accepting it early simply 409s.

    # Cooldown is claimed only now, so a run that failed before creating anything
    # does not burn the student's one daily notification.
    if not cache.add(_phone_cooldown_key(normalized), 1, PHONE_COOLDOWN_SECONDS):
        return {'status': 'created_cooldown', 'engagement_id': engagement.pk}

    sent = _send_invite_sms(phone=normalized, advisor=advisor)
    return {
        'status': 'created',
        'engagement_id': engagement.pk,
        'phone': mask_phone(normalized),
        'sms': sent,
    }


# ── the student half: claiming or declining ──────────────────────────────────

def _locked_invite(student, pk: int) -> AdvisoryEngagement:
    """Lock the row and prove the caller may act on it, or raise.

    Locked by ``(pk, student)`` and **not** by status, on purpose: locking on
    ``status='PENDING'`` would make a double-click return 404 (PostgreSQL
    re-evaluates the WHERE clause after the lock is released), and a student who
    just pressed «قبول» twice deserves a 409, not "no such invite".
    """
    engagement = (
        AdvisoryEngagement.objects.select_for_update()
        .filter(pk=pk, student=student)
        .first()
    )
    if engagement is None:
        raise InviteNotFound('دعوت‌نامه پیدا نشد.')
    if engagement.status == AdvisoryEngagement.Status.ACTIVE:
        raise InviteConflict('این دعوت‌نامه از قبل پذیرفته شده است.')
    if engagement.status != AdvisoryEngagement.Status.PENDING:
        # REJECTED / ENDED are settled. Resurrecting them would let a student
        # undo a rejection the advisor was already told about.
        raise InviteNotFound('دعوت‌نامه پیدا نشد.')
    if engagement.is_expired:
        raise InviteNotFound('دعوت‌نامه پیدا نشد.')

    # B6, phone re-verification. If the number changed hands between invite and
    # accept, the person holding it now is not the person who was invited, and
    # accepting would hand an advisor a different teenager's study log.
    if engagement.invited_phone:
        if normalize_phone(getattr(student, 'phone', '')) != engagement.invited_phone:
            logger.warning(
                'Advisory invite %s claimed by a mismatched phone; refusing.',
                engagement.pk,
            )
            raise InviteNotFound('دعوت‌نامه پیدا نشد.')
    return engagement


def accept_invite(student, pk: int) -> AdvisoryEngagement:
    """Turn a PENDING invite into the student's one ACTIVE engagement.

    ``started_on`` is **today**, never the invite date: C3 forbids a retroactive
    view, so an advisor cannot accept their way into last month's study log.
    """
    try:
        with transaction.atomic():
            engagement = _locked_invite(student, pk)
            now = timezone.now()
            updated = AdvisoryEngagement.objects.filter(
                pk=engagement.pk,
                status=AdvisoryEngagement.Status.PENDING,
            ).update(
                status=AdvisoryEngagement.Status.ACTIVE,
                started_on=timezone.localdate(),
                terms_accepted_at=now,
                invite_expires_at=None,
            )
            if not updated:
                # Unreachable while the lock is held; kept because a future
                # refactor that drops the lock must fail loudly, not silently.
                raise InviteConflict('وضعیت دعوت‌نامه تغییر کرده است.')
    except IntegrityError:
        # uniq_active_advisory_per_student — the student accepted a different
        # invite first. This is the concurrent-accept case and it is a 409.
        raise InviteConflict('شما از قبل مشاور فعال دارید.')

    engagement.refresh_from_db()
    return engagement


def reject_invite(student, pk: int) -> AdvisoryEngagement:
    """Decline an invite. Terminal — see ``REJECT_BLOCK_DAYS``."""
    with transaction.atomic():
        engagement = _locked_invite(student, pk)
        updated = AdvisoryEngagement.objects.filter(
            pk=engagement.pk,
            status=AdvisoryEngagement.Status.PENDING,
        ).update(
            status=AdvisoryEngagement.Status.REJECTED,
            ended_at=timezone.now(),
        )
        if not updated:
            raise InviteConflict('وضعیت دعوت‌نامه تغییر کرده است.')

    engagement.refresh_from_db()
    return engagement
