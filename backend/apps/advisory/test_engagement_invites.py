"""S3 — the invite lifecycle: uniform responses, quotas, and the claim.

This file is where the security decisions of section ب) are pinned. Most of the
tests are *negative*, and most of the positive ones assert that two different
situations look **identical** from outside — which is the unusual thing an invite
endpoint has to guarantee and the thing a refactor is most likely to break.

The one property to keep in mind while reading: the endpoint must never tell the
caller whether a phone number belongs to anyone. Any test below that compares two
responses for equality is protecting that, not being pedantic.
"""

from __future__ import annotations

import datetime
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from model_bakery import baker
from rest_framework.test import APIClient

from apps.advisory.models import INVITE_TTL_DAYS, REJECT_BLOCK_DAYS, AdvisoryEngagement
from apps.advisory.services import invites as invite_service

User = get_user_model()
Status = AdvisoryEngagement.Status
Mode = AdvisoryEngagement.Mode

pytestmark = [pytest.mark.django_db, pytest.mark.api]

INVITE_URL = '/api/advisory/invites/'
STUDENTS_URL = '/api/advisory/students/'
ENGAGEMENT_URL = '/api/advisory/me/engagement/'


def _accept_url(pk: int) -> str:
    return f'/api/advisory/me/invites/{pk}/accept/'


def _reject_url(pk: int) -> str:
    return f'/api/advisory/me/invites/{pk}/reject/'


# ── fixtures ──────────────────────────────────────────────────────────────────

def _auth(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _advisor(username='adv', **kwargs):
    return baker.make(User, username=username, role=User.Role.ADVISOR, **kwargs)


def _student(username='stu', phone='09120000001', **kwargs):
    return baker.make(User, username=username, role=User.Role.STUDENT, phone=phone, **kwargs)


def _pending(advisor, student, **kwargs):
    """A PENDING invite in the shape ``deliver_invite`` would have created."""
    defaults = {
        'invited_phone': student.phone or '',
        'mode': Mode.FREELANCE,
        'organization': None,
        'status': Status.PENDING,
        'invite_expires_at': timezone.now() + datetime.timedelta(days=INVITE_TTL_DAYS),
    }
    defaults.update(kwargs)
    return AdvisoryEngagement.objects.create(advisor=advisor, student=student, **defaults)


@pytest.fixture
def no_enqueue():
    """Swallow the ``.delay()`` and record it.

    The view's contract is "exactly one enqueue, whatever the number turns out to
    be" — asserting on the call is the whole test. Delivery itself is exercised by
    calling ``deliver_invite`` directly further down, which keeps the API tests
    from depending on a broker.
    """
    with patch.object(invite_service, 'enqueue_invite') as mock:
        yield mock


@pytest.fixture
def no_sms():
    with patch.object(invite_service, '_send_invite_sms', return_value=True) as mock:
        yield mock


# ── permission matrix ─────────────────────────────────────────────────────────

@pytest.mark.permission
@pytest.mark.parametrize('method,url', [
    ('get', STUDENTS_URL),
    ('post', INVITE_URL),
    ('get', ENGAGEMENT_URL),
    ('post', '/api/advisory/me/invites/1/accept/'),
    ('post', '/api/advisory/me/invites/1/reject/'),
])
def test_anonymous_is_rejected_everywhere(method, url):
    assert getattr(APIClient(), method)(url).status_code == 401


@pytest.mark.permission
def test_teacher_is_forbidden_on_every_advisory_route(teacher_user):
    """A teacher is 403, not 404 — they have no business on any of these.

    Worth stating explicitly because ``apps.classes.permissions.IsStudentUser``
    admits teachers so they can consume courses as learners. Advisory uses the
    strict ``IsStudentRole`` precisely so that habit does not leak in here.
    """
    client = _auth(teacher_user)
    assert client.get(STUDENTS_URL).status_code == 403
    assert client.post(INVITE_URL, {'phone': '09120000001'}).status_code == 403
    assert client.get(ENGAGEMENT_URL).status_code == 403
    assert client.post(_accept_url(1)).status_code == 403


@pytest.mark.permission
def test_student_cannot_use_the_advisor_side(student_user):
    client = _auth(student_user)
    assert client.get(STUDENTS_URL).status_code == 403
    assert client.post(INVITE_URL, {'phone': '09120000001'}).status_code == 403


@pytest.mark.permission
def test_advisor_cannot_use_the_student_side():
    client = _auth(_advisor())
    assert client.get(ENGAGEMENT_URL).status_code == 403
    assert client.post(_accept_url(1)).status_code == 403


@pytest.mark.permission
def test_platform_admin_does_not_inherit_the_advisor_side(admin_user):
    """An admin manages accounts; they do not silently get a caseload."""
    assert _auth(admin_user).get(STUDENTS_URL).status_code == 403


# ── B2: the response is uniform, whoever owns the number ──────────────────────

def test_invite_to_a_registered_student_is_accepted(no_enqueue):
    _student(phone='09121110000')
    response = _auth(_advisor()).post(INVITE_URL, {'phone': '09121110000'})
    assert response.status_code == 202
    assert response.data == {'status': 'sent'}
    assert no_enqueue.call_count == 1


def test_invite_to_an_unknown_number_looks_identical(no_enqueue):
    """The load-bearing test of section ب).

    If these two responses ever differ — body, status, or the presence of the
    enqueue — an authenticated advisor account becomes a phone→identity lookup
    service for every number in Iran, at 30 numbers a day.
    """
    _student(phone='09121110000')
    advisor = _advisor()
    known = _auth(advisor).post(INVITE_URL, {'phone': '09121110000'})
    unknown = _auth(advisor).post(INVITE_URL, {'phone': '09129999999'})

    assert (known.status_code, known.data) == (unknown.status_code, unknown.data)
    assert no_enqueue.call_count == 2


def test_invite_to_a_teacher_number_also_looks_identical(no_enqueue, teacher_user):
    teacher_user.phone = '09121112222'
    teacher_user.save(update_fields=['phone'])
    response = _auth(_advisor()).post(INVITE_URL, {'phone': '09121112222'})
    assert (response.status_code, response.data) == (202, {'status': 'sent'})


def test_a_rejected_pair_still_answers_202(no_enqueue):
    """Even "this person already said no to you" must not be visible in the reply."""
    advisor, student = _advisor(), _student(phone='09121110000')
    AdvisoryEngagement.objects.create(
        advisor=advisor, student=student, invited_phone=student.phone,
        status=Status.REJECTED, ended_at=timezone.now(),
    )
    response = _auth(advisor).post(INVITE_URL, {'phone': '09121110000'})
    assert (response.status_code, response.data) == (202, {'status': 'sent'})


@pytest.mark.parametrize('bad', ['', '0912', '123456789012345', 'abcdefghijk', '08120000000'])
def test_a_malformed_number_is_400(no_enqueue, bad):
    """400 is safe here: it describes the caller's own typing, not our user table."""
    assert _auth(_advisor()).post(INVITE_URL, {'phone': bad}).status_code == 400
    assert no_enqueue.call_count == 0


def test_persian_digits_are_normalized_before_enqueue(no_enqueue):
    _auth(_advisor()).post(INVITE_URL, {'phone': '۰۹۱۲۱۱۱۰۰۰۰'})
    assert no_enqueue.call_args.kwargs['phone'] == '09121110000'


def test_international_prefix_is_normalized_before_enqueue(no_enqueue):
    _auth(_advisor()).post(INVITE_URL, {'phone': '+98 912 111 0000'})
    assert no_enqueue.call_args.kwargs['phone'] == '09121110000'


# ── B3: four quotas, each closing a different abuse ───────────────────────────

def test_the_invite_endpoint_has_its_own_configured_throttle_scope():
    """Without this scope the view inherits 'user' — 300/minute of SMS.

    Asserted by inspection rather than by hammering the endpoint, because
    ``conftest`` disables throttling for the whole suite. Both halves are checked:
    a scope name with no rate behind it silently no-ops (that is by design in
    ``SafeScopedRateThrottle``, which is why it has to be verified here), and a
    rate with no scope on the view protects nothing.

    The rate is read from the settings *module*, not from ``django.conf.settings``:
    the autouse fixture in ``conftest`` swaps in a copy with ``DEFAULT_THROTTLE_RATES``
    emptied, so the only place the deployed value survives during a test run is the
    module that defined it.
    """
    import core.settings as project_settings

    from apps.advisory.views import AdvisoryInviteCreateView
    from apps.core.throttling import SafeScopedRateThrottle

    assert AdvisoryInviteCreateView.throttle_scope == 'advisory_invite'
    assert any(
        issubclass(c, SafeScopedRateThrottle)
        for c in AdvisoryInviteCreateView.throttle_classes
    )
    rates = project_settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']
    assert rates.get('advisory_invite'), 'advisory_invite has no configured rate'


def test_the_daily_cap_returns_429(no_enqueue):
    client = _auth(_advisor())
    for i in range(invite_service.ADVISOR_DAILY_INVITE_CAP):
        assert client.post(INVITE_URL, {'phone': f'0912000{i:04d}'}).status_code == 202
    over = client.post(INVITE_URL, {'phone': '09129999999'})
    assert over.status_code == 429
    assert no_enqueue.call_count == invite_service.ADVISOR_DAILY_INVITE_CAP


def test_the_daily_cap_is_per_advisor_not_global(no_enqueue):
    a, b = _advisor('a'), _advisor('b')
    for i in range(invite_service.ADVISOR_DAILY_INVITE_CAP):
        _auth(a).post(INVITE_URL, {'phone': f'0912000{i:04d}'})
    assert _auth(b).post(INVITE_URL, {'phone': '09129999999'}).status_code == 202


def test_too_many_open_invites_returns_429(no_enqueue):
    """Bounds the *standing* claim, which a daily cap alone would let accumulate."""
    advisor = _advisor()
    for i in range(invite_service.ADVISOR_OPEN_PENDING_CAP):
        _pending(advisor, _student(f'stu{i}', f'0913000{i:04d}'))
    response = _auth(advisor).post(INVITE_URL, {'phone': '09129999999'})
    assert response.status_code == 429
    assert no_enqueue.call_count == 0


def test_the_platform_breaker_returns_503(no_enqueue):
    """503, not 429: the advisor did nothing wrong and retrying later is correct."""
    with patch.object(invite_service, 'PLATFORM_DAILY_INVITE_CAP', 2):
        client = _auth(_advisor())
        assert client.post(INVITE_URL, {'phone': '09120000001'}).status_code == 202
        assert client.post(INVITE_URL, {'phone': '09120000002'}).status_code == 202
        assert client.post(INVITE_URL, {'phone': '09120000003'}).status_code == 503


def test_the_platform_breaker_is_charged_before_the_advisor_budget():
    """Order matters: a platform incident must not also burn innocent quotas."""
    advisor = _advisor()
    with patch.object(invite_service, 'PLATFORM_DAILY_INVITE_CAP', 0):
        with pytest.raises(invite_service.InviteQuotaExceeded) as caught:
            invite_service.charge_invite_quota(advisor, open_pending_count=0)
    assert caught.value.kind == 'platform'

    # The advisor's own counter was never touched, so they still have a full day.
    with patch.object(invite_service, 'PLATFORM_DAILY_INVITE_CAP', 100):
        invite_service.charge_invite_quota(advisor, open_pending_count=0)


def test_a_rejected_attempt_still_consumes_quota():
    """bump-then-compare, not check-then-increment.

    The naive order lets N concurrent requests all read the same under-limit value
    and all pass. Paying for a rejected attempt is the price of a cap that is
    actually a cap.
    """
    advisor = _advisor()
    with patch.object(invite_service, 'ADVISOR_DAILY_INVITE_CAP', 1):
        invite_service.charge_invite_quota(advisor, open_pending_count=0)
        with pytest.raises(invite_service.InviteQuotaExceeded):
            invite_service.charge_invite_quota(advisor, open_pending_count=0)
        with pytest.raises(invite_service.InviteQuotaExceeded):
            invite_service.charge_invite_quota(advisor, open_pending_count=0)


# ── B4: lookup only. Never, under any circumstance, create a user ─────────────

def test_an_unknown_number_creates_no_account_and_no_engagement(no_sms):
    advisor = _advisor()
    before = User.objects.count()
    result = invite_service.deliver_invite(advisor_id=advisor.pk, phone='09129999999')

    assert result['status'] == 'no_student'
    assert User.objects.count() == before
    assert AdvisoryEngagement.objects.count() == 0
    assert no_sms.call_count == 0


def test_delivery_never_calls_an_account_creation_helper(no_sms):
    """A guard against the tempting shortcut, stated at the seam it would be made.

    ``accounts.services`` has two of these, and both mint a real account for a
    phone number — an account reachable by passwordless invite-code login. One
    mistyped digit would hand a stranger's number a live account on the platform.
    """
    _student(phone='09121110000')
    with patch('apps.accounts.services.get_or_create_user_by_phone') as generic, \
            patch('apps.accounts.services.get_or_create_student_by_phone') as student:
        invite_service.deliver_invite(advisor_id=_advisor().pk, phone='09121110000')
    assert generic.call_count == 0
    assert student.call_count == 0


def test_advisory_source_never_references_an_account_creation_helper():
    """The runtime test above only covers the paths it walks; this covers the files.

    Cheap, total, and it fails on the *pull request that adds the import* rather
    than on the first advisor who mistypes a digit in production.

    It walks the AST rather than the text on purpose. The prohibition is worth
    writing about — ``services/invites.py`` explains it twice, in the module
    docstring and at the lookup itself — and a text scan cannot tell documenting
    the rule apart from breaking it. Names bound by an ``as`` alias are checked on
    both sides so a rename cannot launder the import.
    """
    import ast
    from pathlib import Path

    banned = {'get_or_create_user_by_phone', 'get_or_create_student_by_phone'}

    def identifiers(node) -> set[str]:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = set()
            for alias in node.names:
                names.add(alias.name.rsplit('.', 1)[-1])
                if alias.asname:
                    names.add(alias.asname)
            return names
        if isinstance(node, ast.Name):
            return {node.id}
        if isinstance(node, ast.Attribute):
            return {node.attr}
        return set()

    advisory_dir = Path(invite_service.__file__).resolve().parent.parent
    offenders = []
    for path in sorted(advisory_dir.rglob('*.py')):
        if '__pycache__' in path.parts or path.name.startswith('test_'):
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        for node in ast.walk(tree):
            if identifiers(node) & banned:
                offenders.append(f'{path.relative_to(advisory_dir)}:{node.lineno}')

    assert offenders == [], f'advisory must never create a user by phone: {offenders}'


# ── delivery: the branches the advisor is not allowed to observe ──────────────

def test_delivery_creates_a_pending_invite_with_the_addressed_phone(no_sms):
    advisor, student = _advisor(), _student(phone='09121110000')
    result = invite_service.deliver_invite(advisor_id=advisor.pk, phone='0912 111 0000')

    assert result['status'] == 'created'
    engagement = AdvisoryEngagement.objects.get(pk=result['engagement_id'])
    assert (engagement.advisor, engagement.student) == (advisor, student)
    assert engagement.status == Status.PENDING
    assert engagement.mode == Mode.FREELANCE
    assert engagement.organization_id is None
    # Stored canonical, not as typed: it is compared against the student's phone at
    # accept time, and a comparison between two different formats never matches.
    assert engagement.invited_phone == '09121110000'
    assert engagement.started_on is None
    assert engagement.terms_accepted_at is None


def test_the_invite_expires_in_fourteen_days(no_sms):
    result = invite_service.deliver_invite(
        advisor_id=_advisor().pk, phone=_student(phone='09121110000').phone,
    )
    engagement = AdvisoryEngagement.objects.get(pk=result['engagement_id'])
    expected = timezone.now() + datetime.timedelta(days=INVITE_TTL_DAYS)
    assert abs((engagement.invite_expires_at - expected).total_seconds()) < 60


def test_the_masked_phone_is_what_reaches_the_result_backend(no_sms):
    result = invite_service.deliver_invite(
        advisor_id=_advisor().pk, phone=_student(phone='09121110000').phone,
    )
    assert result['phone'] == '0912***0000'


def test_an_advisor_cannot_invite_their_own_number(no_sms):
    """Self-invite dies at the student lookup, not at the explicit guard.

    The lookup is scoped to ``role=STUDENT``, so an advisor's own number is simply
    not found and the run returns ``no_student`` — indistinguishable, from outside,
    from any other unknown number. The explicit ``self_invite`` branch is therefore
    unreachable today and is kept for the day an account can hold two roles; this
    test pins the *outcome* (no engagement) rather than which branch produced it.
    """
    advisor = _advisor(phone='09121110000')
    result = invite_service.deliver_invite(advisor_id=advisor.pk, phone='09121110000')

    assert result['status'] in {'no_student', 'self_invite'}
    assert AdvisoryEngagement.objects.count() == 0


def test_a_second_invite_to_the_same_pair_is_a_no_op(no_sms):
    advisor, student = _advisor(), _student(phone='09121110000')
    invite_service.deliver_invite(advisor_id=advisor.pk, phone=student.phone)
    second = invite_service.deliver_invite(advisor_id=advisor.pk, phone=student.phone)

    assert second['status'] == 'already_pending'
    assert AdvisoryEngagement.objects.count() == 1


def test_a_recent_rejection_blocks_a_new_invite(no_sms):
    advisor, student = _advisor(), _student(phone='09121110000')
    AdvisoryEngagement.objects.create(
        advisor=advisor, student=student, invited_phone=student.phone,
        status=Status.REJECTED, ended_at=timezone.now() - datetime.timedelta(days=1),
    )
    result = invite_service.deliver_invite(advisor_id=advisor.pk, phone=student.phone)

    assert result['status'] == 'reject_blocked'
    assert not AdvisoryEngagement.objects.filter(status=Status.PENDING).exists()


def test_an_old_rejection_stops_blocking(no_sms):
    """The block is a cooling-off period, not a permanent ban."""
    advisor, student = _advisor(), _student(phone='09121110000')
    AdvisoryEngagement.objects.create(
        advisor=advisor, student=student, invited_phone=student.phone,
        status=Status.REJECTED,
        ended_at=timezone.now() - datetime.timedelta(days=REJECT_BLOCK_DAYS + 1),
    )
    result = invite_service.deliver_invite(advisor_id=advisor.pk, phone=student.phone)
    assert result['status'] == 'created'


def test_another_advisors_rejection_does_not_block(no_sms):
    """The block is per pair. A student saying no to one advisor is not a do-not-call."""
    student = _student(phone='09121110000')
    AdvisoryEngagement.objects.create(
        advisor=_advisor('rejected_one'), student=student, invited_phone=student.phone,
        status=Status.REJECTED, ended_at=timezone.now(),
    )
    result = invite_service.deliver_invite(advisor_id=_advisor('fresh').pk, phone=student.phone)
    assert result['status'] == 'created'


def test_an_invite_is_created_even_when_the_student_already_has_an_advisor(no_sms):
    """Harmless while it waits, claimable if the current engagement ends, 409 if not.

    The alternative — refusing to create it — would leak "this person already has
    an advisor" through the outbox, and would silently drop a legitimate second
    offer to a student who is about to change advisors.
    """
    student = _student(phone='09121110000')
    _pending(
        _advisor('first'), student,
        status=Status.ACTIVE, started_on=timezone.localdate(), invite_expires_at=None,
    )

    result = invite_service.deliver_invite(advisor_id=_advisor('second').pk, phone=student.phone)
    assert result['status'] == 'created'
    assert AdvisoryEngagement.objects.filter(status=Status.PENDING).count() == 1


def test_a_demoted_advisor_delivers_nothing(no_sms):
    """The role is re-checked in the worker: the enqueue is not an authorization."""
    advisor = _advisor()
    _student(phone='09121110000')
    advisor.role = User.Role.STUDENT
    advisor.save(update_fields=['role'])

    result = invite_service.deliver_invite(advisor_id=advisor.pk, phone='09121110000')
    assert result['status'] == 'advisor_gone'
    assert AdvisoryEngagement.objects.count() == 0


# ── the anti-bombing cooldown gates the SMS, never the row ────────────────────

def test_the_first_invite_to_a_number_sends_one_sms(no_sms):
    invite_service.deliver_invite(
        advisor_id=_advisor().pk, phone=_student(phone='09121110000').phone,
    )
    assert no_sms.call_count == 1


def test_a_second_advisor_within_a_day_creates_the_row_but_sends_no_sms(no_sms):
    """«same number twice in 24h → 202 but no second SMS», from the other side.

    Ten advisors taking turns must not be able to text one teenager ten times, and
    the victim's number is the only key that stops that. Suppressing the *row* as
    well would silently lose a legitimate second offer.
    """
    student = _student(phone='09121110000')
    first = invite_service.deliver_invite(advisor_id=_advisor('a').pk, phone=student.phone)
    second = invite_service.deliver_invite(advisor_id=_advisor('b').pk, phone=student.phone)

    assert first['status'] == 'created'
    assert second['status'] == 'created_cooldown'
    assert AdvisoryEngagement.objects.filter(status=Status.PENDING).count() == 2
    assert no_sms.call_count == 1


def test_a_failed_delivery_does_not_burn_the_cooldown(no_sms):
    """The cooldown is claimed after the row exists, so a no-op does not spend it."""
    invite_service.deliver_invite(advisor_id=_advisor().pk, phone='09129999999')
    invite_service.deliver_invite(
        advisor_id=_advisor('b').pk, phone=_student(phone='09129999999').phone,
    )
    assert no_sms.call_count == 1


def test_the_sms_carries_no_code_or_link():
    """B1: nothing credential-like ever leaves over SMS.

    The platform's stable invite code turns code + phone straight into a JWT. If
    advisory ever sends something claimable, it inherits that whole threat model —
    so the message says "open the app" and nothing else.
    """
    advisor = _advisor(first_name='زهرا', last_name='مرادی')
    sent: list[dict] = []
    with patch.dict('os.environ', {'MEDIANA_API_KEY': 'test-key'}):
        with patch(
            'apps.classes.services.mediana_sms.send_peer_to_peer_sms',
            side_effect=lambda **kw: sent.append(kw),
        ):
            invite_service._send_invite_sms(phone='09121110000', advisor=advisor)

    body = sent[0]['requests'][0]['TextMessage']
    assert 'زهرا مرادی' in body
    assert 'http' not in body.lower()
    for token in ('کد', 'code', 'رمز', 'token'):
        assert token not in body.lower()


def test_a_dead_sms_provider_does_not_fail_the_invite():
    """The row is already committed; the student sees the banner on their next visit."""
    with patch.dict('os.environ', {'MEDIANA_API_KEY': 'test-key'}):
        with patch(
            'apps.classes.services.mediana_sms.send_peer_to_peer_sms',
            side_effect=RuntimeError('provider down'),
        ):
            assert invite_service._send_invite_sms(phone='09121110000', advisor=_advisor()) is False


def test_no_sms_key_is_not_an_error():
    with patch.dict('os.environ', {'MEDIANA_API_KEY': ''}):
        assert invite_service._send_invite_sms(phone='09121110000', advisor=_advisor()) is False


# ── accept ────────────────────────────────────────────────────────────────────

def test_accept_activates_the_engagement():
    advisor, student = _advisor(), _student(phone='09121110000')
    invite = _pending(advisor, student)

    response = _auth(student).post(_accept_url(invite.pk))
    assert response.status_code == 200

    invite.refresh_from_db()
    assert invite.status == Status.ACTIVE
    assert invite.terms_accepted_at is not None
    # Cleared so the row stops matching the "expiring soon" sweep in step 9.
    assert invite.invite_expires_at is None


def test_accept_starts_the_engagement_today_not_at_invite_time():
    """C3 forbids a retroactive view.

    An invite sent three weeks ago must not hand the advisor three weeks of a
    student's study log the moment it is accepted.
    """
    advisor, student = _advisor(), _student(phone='09121110000')
    invite = _pending(advisor, student)
    AdvisoryEngagement.objects.filter(pk=invite.pk).update(
        invited_at=timezone.now() - datetime.timedelta(days=21),
    )

    _auth(student).post(_accept_url(invite.pk))
    invite.refresh_from_db()
    assert invite.started_on == timezone.localdate()


def test_accepting_someone_elses_invite_is_404_not_403():
    """404 on purpose: a 403 would confirm that *some* advisor invited this person."""
    invite = _pending(_advisor(), _student('target', '09121110000'))
    intruder = _student('intruder', '09122220000')

    assert _auth(intruder).post(_accept_url(invite.pk)).status_code == 404
    invite.refresh_from_db()
    assert invite.status == Status.PENDING


def test_accepting_a_nonexistent_invite_is_404():
    assert _auth(_student()).post(_accept_url(999_999)).status_code == 404


def test_accepting_twice_is_409():
    """A double-click deserves "already done", not "no such invite".

    This is why ``_locked_invite`` locks on ``(pk, student)`` and checks status
    after the lock, rather than filtering on ``status='PENDING'`` in the lock query.
    """
    advisor, student = _advisor(), _student(phone='09121110000')
    invite = _pending(advisor, student)

    assert _auth(student).post(_accept_url(invite.pk)).status_code == 200
    assert _auth(student).post(_accept_url(invite.pk)).status_code == 409


def test_two_advisors_race_for_one_student_and_exactly_one_wins():
    """The concurrent-accept case, made deterministic.

    Sequential here, but it exercises the same code path a real race does: the
    second update is refused by ``uniq_active_advisory_per_student`` at the
    database, not by an application check that a race could slip past.
    """
    student = _student(phone='09121110000')
    first = _pending(_advisor('a'), student)
    second = _pending(_advisor('b'), student)

    assert _auth(student).post(_accept_url(first.pk)).status_code == 200
    assert _auth(student).post(_accept_url(second.pk)).status_code == 409

    assert AdvisoryEngagement.objects.filter(status=Status.ACTIVE).count() == 1
    second.refresh_from_db()
    assert second.status == Status.PENDING  # still claimable if the first one ends


def test_accepting_an_expired_invite_is_404():
    advisor, student = _advisor(), _student(phone='09121110000')
    invite = _pending(
        advisor, student, invite_expires_at=timezone.now() - datetime.timedelta(minutes=1),
    )
    assert _auth(student).post(_accept_url(invite.pk)).status_code == 404


@pytest.mark.parametrize('settled', [Status.REJECTED, Status.ENDED])
def test_accepting_a_settled_engagement_is_404_not_403(settled):
    """«همکاری ENDED → ۴۰۴، نه ۴۰۳».

    Resurrecting a settled row would let a student silently undo a rejection the
    advisor was already told about, or restart an engagement that was ended for a
    reason nobody here can see.
    """
    advisor, student = _advisor(), _student(phone='09121110000')
    invite = _pending(advisor, student, status=settled, ended_at=timezone.now())
    assert _auth(student).post(_accept_url(invite.pk)).status_code == 404


def test_a_reassigned_phone_number_cannot_claim_the_invite():
    """B6's «بازتأییدِ شماره», at the point where it earns its keep.

    Iranian mobile numbers get recycled. If the number changed hands between
    invite and accept, the person holding it now is a different teenager, and
    accepting would hand their study log to an advisor who never asked for it.
    """
    advisor, student = _advisor(), _student(phone='09121110000')
    invite = _pending(advisor, student)

    student.phone = '09125550000'
    student.save(update_fields=['phone'])

    assert _auth(student).post(_accept_url(invite.pk)).status_code == 404
    invite.refresh_from_db()
    assert invite.status == Status.PENDING


# ── reject ────────────────────────────────────────────────────────────────────

def test_reject_settles_the_invite():
    advisor, student = _advisor(), _student(phone='09121110000')
    invite = _pending(advisor, student)

    response = _auth(student).post(_reject_url(invite.pk))
    assert response.status_code == 200
    assert response.data == {'status': 'rejected'}

    invite.refresh_from_db()
    assert invite.status == Status.REJECTED
    assert invite.ended_at is not None
    assert invite.started_on is None


def test_reject_is_terminal():
    advisor, student = _advisor(), _student(phone='09121110000')
    invite = _pending(advisor, student)
    _auth(student).post(_reject_url(invite.pk))

    assert _auth(student).post(_accept_url(invite.pk)).status_code == 404
    assert _auth(student).post(_reject_url(invite.pk)).status_code == 404


def test_rejecting_someone_elses_invite_is_404():
    invite = _pending(_advisor(), _student('target', '09121110000'))
    intruder = _student('intruder', '09122220000')

    assert _auth(intruder).post(_reject_url(invite.pk)).status_code == 404
    invite.refresh_from_db()
    assert invite.status == Status.PENDING


def test_rejecting_then_being_re_invited_is_blocked_for_thirty_days(no_sms):
    """The two halves of B6 meet here: reject is terminal *and* it blocks re-offer."""
    advisor, student = _advisor(), _student(phone='09121110000')
    _auth(student).post(_reject_url(_pending(advisor, student).pk))

    result = invite_service.deliver_invite(advisor_id=advisor.pk, phone=student.phone)
    assert result['status'] == 'reject_blocked'
