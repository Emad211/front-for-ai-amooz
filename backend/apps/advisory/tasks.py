"""Advisory background work — one task, and it exists for a security reason.

§7 of the spec puts "any Celery task" out of the MVP, and this file is the single
documented amendment to that. The reason is B2: the four possible outcomes of an
invite (student found · no such number · phone on cooldown · pair blocked by a
past rejection) take visibly different amounts of time. Doing that work inside the
request would make the response time itself a phone-number→identity oracle,
regardless of how uniform the response *body* is. Moving all of it behind exactly
one ``.delay()`` makes the request cost constant by construction.

The secondary reason is consistency: every SMS send in this repository already
goes through a ``default``-queue task (``send_publish_sms_task`` and friends), so
a synchronous send here would be the odd one out.
"""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5, acks_late=True)
def deliver_advisory_invite_task(self, advisor_id: int, phone: str) -> dict:
    """Resolve the phone, create the PENDING engagement, notify the student.

    Retries only on *infrastructure* failure. Every business outcome — including
    "no such student" and "blocked" — is a successful run that happens to have
    created nothing, because retrying it would never produce a different answer.

    Mirrors ``apps.classes.tasks.send_publish_sms_task``: exponential backoff,
    and after the last attempt it returns a failure dict rather than raising, so a
    dead SMS provider does not fill the result backend with tracebacks.
    """
    from .services.invites import deliver_invite

    try:
        return deliver_invite(advisor_id=advisor_id, phone=phone)
    except Exception as exc:  # noqa: BLE001 — retried, then reported
        if self.request.retries >= self.max_retries:
            logger.exception('Advisory invite delivery failed permanently')
            return {'status': 'failed', 'error': str(exc)[:500]}
        backoff = 30 * (2 ** self.request.retries)  # 30, 60, 120, 240, 480
        raise self.retry(exc=exc, countdown=backoff)


# ── Wave 5 (2026-08-31): parent SMS + the Thursday digest beat ────────────────
#
# Same shape as deliver_advisory_invite_task on purpose: retry only on
# infrastructure failure, back off exponentially, and after the last attempt
# report a failure dict instead of raising into the result backend.


@shared_task(bind=True, max_retries=5, acks_late=True)
def send_parent_invite_sms_task(self, phone: str, advisor_name: str) -> dict:
    """The parent-invite notification SMS (no code, no link — B1)."""
    from .services.parent_links import send_parent_invite_sms

    try:
        sent = send_parent_invite_sms(phone=phone, advisor_name=advisor_name)
        return {'status': 'sent' if sent else 'skipped'}
    except Exception as exc:  # noqa: BLE001 — retried, then reported
        if self.request.retries >= self.max_retries:
            logger.exception('Parent invite SMS failed permanently')
            return {'status': 'failed', 'error': str(exc)[:500]}
        raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=5, acks_late=True)
def send_parent_login_otp_sms_task(self, phone: str, code: str) -> dict:
    """The parent login OTP SMS — the one credential-bearing message of the
    flow, sent from the worker so the request's latency stays uniform (B2)."""
    from .services.parent_links import send_parent_login_otp_sms

    try:
        sent = send_parent_login_otp_sms(phone=phone, code=code)
        return {'status': 'sent' if sent else 'skipped'}
    except Exception as exc:  # noqa: BLE001 — retried, then reported
        if self.request.retries >= self.max_retries:
            logger.exception('Parent login OTP SMS failed permanently')
            return {'status': 'failed', 'error': str(exc)[:500]}
        raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=5, acks_late=True)
def send_parent_weekly_digest(self) -> dict:
    """Thursday 17:30 Tehran beat: tell every linked parent the weekly digest
    is ready (in-app notification + one short, credential-free SMS).

    Per-link failures never abort the batch — one parent's broken phone must
    not silence every other parent's nudge — so the service-level summary is
    the task result, and only an infrastructure-level failure retries.
    """
    from .services.parent_links import deliver_weekly_digest_notifications

    try:
        return deliver_weekly_digest_notifications()
    except Exception as exc:  # noqa: BLE001 — retried, then reported
        if self.request.retries >= self.max_retries:
            logger.exception('Parent weekly digest beat failed permanently')
            return {'status': 'failed', 'error': str(exc)[:500]}
        raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))
