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


def _send_sms_for_invites(api_key: str, session, invites) -> None:
    """Build and send SMS messages for a list of ClassInvitation objects."""
    if not invites:
        return

    logger.info('Sending SMS: invites=%d session=%s', len(invites), session.id)

    sms_requests: list[dict] = []
    for inv in invites:
        text = f'AI_AMOOZ\nکلاس "{session.title}" منتشر شد. کد دعوت شما: {inv.invite_code}'
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
                session.id,
            )


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

    _send_sms_for_invites(api_key, session, invites)


def send_teacher_message_sms(notification_id: int) -> None:
    """Send a teacher broadcast message to its recipient phones via SMS."""
    from apps.notification.models import TeacherNotification

    api_key = _get_env('MEDIANA_API_KEY')
    if not api_key:
        logger.info('MEDIANA_API_KEY not set; skipping teacher message SMS notif=%s', notification_id)
        return

    notif = (
        TeacherNotification.objects.filter(id=notification_id)
        .select_related('teacher')
        .prefetch_related('recipients')
        .first()
    )
    if notif is None:
        logger.info('Teacher message SMS skipped: notification not found id=%s', notification_id)
        return

    phones = [r.phone for r in notif.recipients.all() if (r.phone or '').strip()]
    if not phones:
        logger.info('Teacher message SMS skipped: no recipients notif=%s', notification_id)
        return

    title = (notif.title or '').strip()
    body = (notif.message or '').strip()
    sender_name = notif.teacher.get_full_name().strip() or notif.teacher.username
    title_line = f'{title}\n' if title else ''
    text = f'AI_AMOOZ\nفرستنده: {sender_name}\n{title_line}{body}'

    sms_requests = [
        {
            'RefId': f'tmsg-{notif.id}-{idx}',
            'TextMessage': text,
            'Recipients': [phone],
        }
        for idx, phone in enumerate(phones)
    ]

    chunk_size = 1000
    for i in range(0, len(sms_requests), chunk_size):
        chunk = sms_requests[i : i + chunk_size]
        result = send_peer_to_peer_sms(api_key=api_key, requests=chunk)
        meta = result.get('meta') if isinstance(result, dict) else None
        if isinstance(meta, dict) and meta.get('errorMessage'):
            logger.warning('Mediana teacher-message SMS errorMessage: %s', meta.get('errorMessage'))


def send_exercise_review_ready_sms(exercise_id: int) -> None:
    """Send the teacher a one-shot SMS when an exercise draft is ready to review."""
    from apps.classes.models import ClassExercise

    api_key = _get_env('MEDIANA_API_KEY')
    if not api_key:
        logger.info('MEDIANA_API_KEY not set; skipping exercise-ready SMS exercise=%s', exercise_id)
        return

    exercise = (
        ClassExercise.objects.filter(id=exercise_id)
        .select_related('session__teacher')
        .first()
    )
    if exercise is None:
        logger.info('Exercise-ready SMS skipped: exercise not found id=%s', exercise_id)
        return

    phone = (getattr(exercise.session.teacher, 'phone', None) or '').strip()
    if not phone:
        logger.info('Exercise-ready SMS skipped: teacher phone missing exercise=%s', exercise_id)
        return

    text = 'پیش‌نویس تمرین شما آماده است. برای بررسی و انتشار، وارد پنل معلم AI-Amooz شوید.'
    result = send_peer_to_peer_sms(
        api_key=api_key,
        requests=[{
            'RefId': f'exercise-ready-{exercise.id}',
            'TextMessage': text,
            'Recipients': [phone],
        }],
    )
    meta = result.get('meta') if isinstance(result, dict) else None
    if isinstance(meta, dict) and meta.get('errorMessage'):
        logger.warning('Mediana exercise-ready SMS errorMessage: %s', meta.get('errorMessage'))


def send_session_review_ready_sms(session_id: int) -> None:
    """Send the teacher a one-shot SMS when a class/exam draft is ready to review."""
    api_key = _get_env('MEDIANA_API_KEY')
    if not api_key:
        logger.info('MEDIANA_API_KEY not set; skipping session-ready SMS session=%s', session_id)
        return

    session = (
        ClassCreationSession.objects.filter(id=session_id)
        .select_related('teacher')
        .first()
    )
    if session is None:
        logger.info('Session-ready SMS skipped: session not found id=%s', session_id)
        return

    phone = (getattr(session.teacher, 'phone', None) or '').strip()
    if not phone:
        logger.info('Session-ready SMS skipped: teacher phone missing session=%s', session_id)
        return

    if session.pipeline_type == ClassCreationSession.PipelineType.EXAM_PREP:
        text = 'پیش‌نویس آمادگی آزمون شما آماده بازبینی است. برای بررسی و انتشار، وارد پنل معلم AI-Amooz شوید.'
        ref_id = f'exam-ready-{session.id}'
    else:
        text = 'پیش‌نویس کلاس شما آماده بازبینی است. برای بررسی و انتشار، وارد پنل معلم AI-Amooz شوید.'
        ref_id = f'class-ready-{session.id}'

    result = send_peer_to_peer_sms(
        api_key=api_key,
        requests=[{
            'RefId': ref_id,
            'TextMessage': text,
            'Recipients': [phone],
        }],
    )
    meta = result.get('meta') if isinstance(result, dict) else None
    if isinstance(meta, dict) and meta.get('errorMessage'):
        logger.warning('Mediana session-ready SMS errorMessage: %s', meta.get('errorMessage'))


def send_invite_sms_for_ids(session_id: int, invite_ids: list[int]) -> None:
    """Send SMS to specific invitations (e.g. newly added to a published session)."""
    from apps.classes.models import ClassInvitation

    api_key = _get_env('MEDIANA_API_KEY')
    if not api_key:
        logger.info('MEDIANA_API_KEY not set; skipping invite SMS session=%s', session_id)
        return

    session = ClassCreationSession.objects.filter(id=session_id).first()
    if session is None:
        logger.info('Invite SMS skipped: session not found session=%s', session_id)
        return

    invites = list(ClassInvitation.objects.filter(id__in=invite_ids, session=session))
    if not invites:
        logger.info('Invite SMS skipped: no matching invites session=%s ids=%s', session_id, invite_ids)
        return

    _send_sms_for_invites(api_key, session, invites)
