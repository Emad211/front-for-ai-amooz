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
