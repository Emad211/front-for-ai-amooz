from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

from apps.classes.models import ClassCreationSession

logger = logging.getLogger(__name__)


def _get_env(name: str) -> str:
    return (os.getenv(name) or '').strip()


def _post_json(*, url: str, api_key: str, payload: dict, max_retries: int = 2) -> dict:
    """POST JSON to the Mediana API with retry on transient errors."""
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')

    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 2):
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'X-API-KEY': api_key,
            },
            method='POST',
        )

        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read().decode('utf-8')
            try:
                return json.loads(raw) if raw else {}
            except Exception as exc:
                raise RuntimeError(f'Mediana SMS invalid JSON response: {raw[:500]}') from exc

        except urllib.error.HTTPError as exc:
            raw = (exc.read() or b'').decode('utf-8', errors='replace')[:300]
            # Don't retry client errors (4xx)
            if 400 <= exc.code < 500:
                raise RuntimeError(f'Mediana SMS HTTP {exc.code}: {raw}') from exc
            last_exc = RuntimeError(f'Mediana SMS HTTP {exc.code}: {raw}')
            logger.warning(
                'Mediana SMS transient error (attempt %d/%d): HTTP %s',
                attempt, max_retries + 1, exc.code,
            )

        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_exc = RuntimeError(f'Mediana SMS request failed: {exc}')
            logger.warning(
                'Mediana SMS network error (attempt %d/%d): %s',
                attempt, max_retries + 1, exc,
            )

    raise last_exc or RuntimeError('Mediana SMS failed after retries')


def send_peer_to_peer_sms(*, api_key: str, requests: list[dict], message_type: str = 'Informational') -> dict:
    """Send personalized SMS messages via Mediana /sms/v1/send/array.

    Schema reference (OpenAPI): SendSmsP2PWithType
    """

    url = 'https://api.mediana.ir/sms/v1/send/array'
    payload = {
        'Type': message_type,
        'Requests': requests,
    }
    return _post_json(url=url, api_key=api_key, payload=payload)


def send_publish_sms_for_session(session_id: int) -> None:
    api_key = _get_env('MEDIANA_API_KEY')
    if not api_key:
        logger.info('MEDIANA_API_KEY not set; skipping SMS send for session=%s', session_id)
        return

    session = ClassCreationSession.objects.filter(id=session_id).prefetch_related('invites').first()
    if session is None:
        logger.info('Publish SMS skipped: session not found session=%s', session_id)
        return

    invites = list(session.invites.all())
    if not invites:
        logger.info('Publish SMS skipped: no invites session=%s', session_id)
        return

    logger.info('Publish SMS starting: invites=%s session=%s', len(invites), session_id)

    sms_requests: list[dict] = []
    for inv in invites:
        text = f'کلاس "{session.title}" منتشر شد. کد دعوت شما: {inv.invite_code}'
        sms_requests.append(
            {
                'RefId': str(inv.invite_code),
                'TextMessage': text,
                'Recipients': [inv.phone],
            }
        )

    # Mediana allows up to 1000 requests per call.
    chunk_size = 1000
    for i in range(0, len(sms_requests), chunk_size):
        chunk = sms_requests[i : i + chunk_size]
        result = send_peer_to_peer_sms(api_key=api_key, requests=chunk)

        meta = result.get('meta') if isinstance(result, dict) else None
        if isinstance(meta, dict) and meta.get('errorMessage'):
            logger.warning('Mediana SMS responded with errorMessage: %s', meta.get('errorMessage'))

        data = result.get('data') if isinstance(result, dict) else None
        if isinstance(data, dict):
            logger.info(
                'Mediana SMS sent: TotalSent=%s TotalRequested=%s session=%s',
                data.get('TotalSent'),
                data.get('TotalRequested'),
                session_id,
            )
