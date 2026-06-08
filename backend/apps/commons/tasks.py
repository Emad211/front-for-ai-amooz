"""Lightweight periodic tasks for the commons app (run on the default queue)."""
from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=30, acks_late=True)
def refresh_usdt_toman_rate_task(self):
    """Refresh the USDT→Toman rate into the shared cache (Celery-beat).

    Keeps the request/LLM-write path free of any blocking FX network call: the
    web tier only ever reads the cached value (see exchange_rate.get_usdt_toman_rate).
    """
    from apps.commons.exchange_rate import refresh_usdt_toman_rate

    rate, err = refresh_usdt_toman_rate()
    if rate is None:
        logger.warning('USDT→Toman rate refresh failed: %s', err)
    else:
        logger.info('USDT→Toman rate refreshed: %s toman/USDT', rate)
    return {'rate': rate, 'error': err}
