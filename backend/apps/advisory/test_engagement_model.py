"""S3 — what the database refuses, and what the API is allowed to say.

Three groups, each protecting a different kind of failure:

* **Constraints.** Every rule below is enforced by PostgreSQL, not by a service
  function, because "one active advisor per student" has to survive two workers
  racing. Testing them here documents *which* invariants are structural — a
  future refactor that moves a check into Python has to delete a test to do it.
* **Scope.** ``services/scope.py`` is the only place in advisory allowed to build
  a queryset over engagements. These tests are the reason: the organization-side
  join it applies is invisible at the call site, so a view that "helpfully"
  filtered by ``advisor=request.user`` instead would look right and leak.
* **Projections.** Section ب)۵ — the advisor's outbox must not become a
  phone→identity lookup. That is a property of a field list, and a field list is
  exactly the sort of thing that grows quietly.
"""

from __future__ import annotations

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone
from model_bakery import baker
from rest_framework.test import APIClient

from apps.advisory.models import INVITE_TTL_DAYS, AdvisoryEngagement
from apps.advisory.services import scope
from apps.advisory.services.text import mask_phone
from apps.organizations.models import Organization, OrganizationMembership

User = get_user_model()
Status = AdvisoryEngagement.Status
Mode = AdvisoryEngagement.Mode

pytestmark = [pytest.mark.django_db]

STUDENTS_URL = '/api/advisory/students/'
ENGAGEMENT_URL = '/api/advisory/me/engagement/'


def _auth(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _advisor(username='adv', **kwargs):
    return baker.make(User, username=username, role=User.Role.ADVISOR, **kwargs)


def _student(username='stu', phone='09120000001', **kwargs):
    return baker.make(User, username=username, role=User.Role.STUDENT, phone=phone, **kwargs)


def _engagement(advisor, student, **kwargs):
    defaults = {
        'invited_phone': student.phone or '',
        'mode': Mode.FREELANCE,
        'organization': None,
        'status': Status.ACTIVE,
        'started_on': timezone.localdate(),
        'terms_accepted_at': timezone.now(),
    }
    defaults.update(kwargs)
    return AdvisoryEngagement.objects.create(advisor=advisor, student=student, **defaults)


def _pending(advisor, student, **kwargs):
    kwargs.setdefault('status', Status.PENDING)
    kwargs.setdefault('started_on', None)
    kwargs.setdefault('terms_accepted_at', None)
    kwargs.setdefault(
        'invite_expires_at',
        timezone.now() + datetime.timedelta(days=INVITE_TTL_DAYS),
    )
    return _engagement(advisor, student, **kwargs)


# ── constraints ───────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_org_mode_requires_an_organization():
    """An org engagement with no org is an engagement nobody can revoke.

    Step 9 ends an engagement when its membership row disappears; that lookup is
    keyed on the organization. A NULL there produces a row that survives the
    student leaving the organization — a permanent, unrevokable read grant.
    """
    with pytest.raises(IntegrityError), transaction.atomic():
        AdvisoryEngagement.objects.create(
            advisor=_advisor(), student=_student(),
            mode=Mode.ORG, organization=None, status=Status.ACTIVE,
        )


@pytest.mark.unit
def test_freelance_mode_forbids_an_organization():
    """The other half of the same constraint, and the one that matters for billing.

    A freelance engagement carrying an organization would be counted in that
    organization's seat usage and would appear on its manager's aggregate report,
    for a student the organization has no relationship with.
    """
    org = baker.make(Organization, name='مدرسه‌ی نمونه')
    with pytest.raises(IntegrityError), transaction.atomic():
        AdvisoryEngagement.objects.create(
            advisor=_advisor(), student=_student(),
            mode=Mode.FREELANCE, organization=org, status=Status.ACTIVE,
        )


@pytest.mark.unit
def test_a_student_can_have_only_one_active_advisor():
    student = _student()
    _engagement(_advisor('a'), student)
    with pytest.raises(IntegrityError), transaction.atomic():
        _engagement(_advisor('b'), student)


@pytest.mark.unit
def test_a_settled_engagement_does_not_block_a_new_one():
    """The uniqueness is partial — on ACTIVE only.

    A student who finishes with one advisor must be able to hire another, and the
    old row has to stay for the audit trail. A plain unique constraint would force
    a choice between those two.
    """
    student = _student()
    _engagement(_advisor('a'), student, status=Status.ENDED, ended_at=timezone.now())
    _engagement(_advisor('b'), student)  # must not raise
    assert AdvisoryEngagement.objects.filter(student=student).count() == 2


@pytest.mark.unit
def test_the_same_pair_cannot_have_two_open_invites():
    advisor, student = _advisor(), _student()
    _pending(advisor, student)
    with pytest.raises(IntegrityError), transaction.atomic():
        _pending(advisor, student)


@pytest.mark.unit
def test_two_advisors_may_both_have_an_open_invite_to_one_student():
    """Deliberately allowed: the student chooses. Only *accepting* both is refused."""
    student = _student()
    _pending(_advisor('a'), student)
    _pending(_advisor('b'), student)
    assert AdvisoryEngagement.objects.filter(status=Status.PENDING).count() == 2


@pytest.mark.unit
def test_an_advisor_with_engagements_cannot_be_deleted():
    """PROTECT on ``advisor``, CASCADE on ``student`` — asymmetric on purpose.

    Deleting an advisor account must not silently take a student's plan history
    with it; the operator has to end the engagements first, which is a decision
    someone should make consciously. A student deleting their own account, by
    contrast, is entitled to take their data with them (D3).
    """
    advisor = _advisor()
    _engagement(advisor, _student())
    with pytest.raises(Exception), transaction.atomic():
        advisor.delete()


@pytest.mark.unit
def test_deleting_a_student_removes_their_engagements():
    student = _student()
    _engagement(_advisor(), student)
    student.delete()
    assert AdvisoryEngagement.objects.count() == 0


# ── the model's own small helpers ──────────────────────────────────────────────

@pytest.mark.unit
def test_is_expired_is_false_when_there_is_no_deadline():
    """An accepted engagement clears ``invite_expires_at``; it is not expired.

    Getting this backwards would make every ACTIVE engagement report itself as
    expired, which the accept path treats as "not found".
    """
    engagement = _engagement(_advisor(), _student(), invite_expires_at=None)
    assert engagement.is_expired is False


@pytest.mark.unit
@pytest.mark.parametrize('offset,expected', [(-60, True), (60, False)])
def test_is_expired_tracks_the_deadline(offset, expected):
    engagement = _pending(
        _advisor(), _student(),
        invite_expires_at=timezone.now() + datetime.timedelta(seconds=offset),
    )
    assert engagement.is_expired is expected


@pytest.mark.unit
@pytest.mark.parametrize('raw,expected', [
    ('09121110000', '0912***0000'),
    ('۰۹۱۲۱۱۱۰۰۰۰', '***'),      # Persian digits are not ASCII: masked, never echoed
    ('0912', '***'),
    ('', '***'),
    (None, '***'),
])
def test_mask_phone_never_echoes_an_unexpected_value(raw, expected):
    """The conservative branch is the point: a malformed value is hidden, not passed through."""
    assert mask_phone(raw) == expected


# ── scope: the advisor sees exactly their own caseload ────────────────────────

@pytest.mark.api
def test_an_advisor_never_sees_another_advisors_student():
    """The core tenancy test of the feature.

    Both advisors are legitimate users of the platform; nothing about the request
    is malformed. Only the engagement join separates them.
    """
    mine, theirs = _advisor('mine'), _advisor('theirs')
    _engagement(mine, _student('a', '09121110001'))
    _engagement(theirs, _student('b', '09121110002'))

    response = _auth(mine).get(STUDENTS_URL)
    assert response.status_code == 200
    assert [row['studentName'] for row in response.data['students']] == ['a']


@pytest.mark.api
def test_a_pending_invite_is_not_a_student_yet():
    """The roster is people who agreed. The outbox is people who have not answered."""
    advisor = _advisor()
    _pending(advisor, _student('waiting', '09121110001'))

    response = _auth(advisor).get(STUDENTS_URL)
    assert response.data['students'] == []
    assert len(response.data['pendingInvites']) == 1


@pytest.mark.api
@pytest.mark.parametrize('settled', [Status.REJECTED, Status.ENDED])
def test_a_settled_engagement_leaves_both_lists(settled):
    advisor = _advisor()
    _engagement(advisor, _student(), status=settled, ended_at=timezone.now())

    response = _auth(advisor).get(STUDENTS_URL)
    # Risman step 1 added the advisor's ``folders`` array to the same body.
    assert response.data == {'students': [], 'pendingInvites': [], 'folders': []}


@pytest.mark.api
def test_an_expired_invite_stays_in_the_outbox():
    """Shown, flagged, and no longer claimable — deliberately not hidden.

    An invite that vanishes silently is one the advisor re-sends, burning the
    student's daily notification. ``isExpired`` lets the UI say "منقضی شد" and
    offer a resend, which is the honest version of the same interaction.
    """
    advisor = _advisor()
    _pending(
        advisor, _student(),
        invite_expires_at=timezone.now() - datetime.timedelta(minutes=1),
    )
    response = _auth(advisor).get(STUDENTS_URL)
    assert len(response.data['pendingInvites']) == 1
    assert response.data['pendingInvites'][0]['isExpired'] is True


@pytest.mark.api
def test_an_expired_invite_is_not_claimable_by_the_student():
    """The asymmetry with the test above is the whole design: visible, not actionable."""
    student = _student()
    _pending(
        _advisor(), student,
        invite_expires_at=timezone.now() - datetime.timedelta(minutes=1),
    )
    response = _auth(student).get(ENGAGEMENT_URL)
    assert response.data == {'active': None, 'invites': []}


@pytest.mark.unit
def test_scope_refuses_a_non_advisor_outright():
    """A defence in depth behind the permission class, not a duplicate of it.

    ``visible_engagements`` is called by services that may one day run outside a
    request — a management command, the step 9 reconciler. An empty queryset for a
    non-advisor means those callers cannot leak by forgetting a role check.
    """
    teacher = baker.make(User, username='t', role=User.Role.TEACHER)
    assert not scope.advisor_students(teacher).exists()
    assert not scope.advisor_pending_invites(teacher).exists()
    assert scope.student_active_engagement(teacher) is None


@pytest.mark.unit
def test_scope_refuses_a_platform_admin_a_caseload():
    """An admin has every permission and no students. The two are separate questions."""
    admin = baker.make(User, username='root', role=User.Role.ADMIN, is_staff=True)
    assert not scope.advisor_students(admin).exists()


# ── C1: an org engagement lives only as long as the membership ────────────────

@pytest.mark.api
def test_an_org_engagement_disappears_when_the_advisor_leaves_the_organization():
    """Layer one of the three-layer revocation, and the only synchronous one.

    ``OrgMembership`` is hard-deleted with no signal, so nothing tells advisory
    that a removal happened. The live join is what makes the next request correct
    regardless — the background reconciler in step 9 then cleans the row up.
    """
    org = baker.make(Organization, name='مدرسه‌ی الف')
    advisor, student = _advisor(), _student()
    membership = baker.make(
        OrganizationMembership, organization=org, user=advisor,
        org_role=OrganizationMembership.OrgRole.ADVISOR,
        status=OrganizationMembership.MemberStatus.ACTIVE,
    )
    _engagement(advisor, student, mode=Mode.ORG, organization=org)

    assert len(_auth(advisor).get(STUDENTS_URL).data['students']) == 1

    membership.delete()

    assert _auth(advisor).get(STUDENTS_URL).data['students'] == []
    # The row is still there — revoked from the API, not destroyed. Ending it is
    # the reconciler's job, so the audit trail survives a mistaken removal.
    assert AdvisoryEngagement.objects.filter(status=Status.ACTIVE).count() == 1


@pytest.mark.api
def test_a_freelance_engagement_is_unaffected_by_organizations():
    """The switchable dashboard's independence, asserted at its narrowest point."""
    org = baker.make(Organization, name='مدرسه‌ی ب')
    advisor = _advisor()
    membership = baker.make(
        OrganizationMembership, organization=org, user=advisor,
        org_role=OrganizationMembership.OrgRole.ADVISOR,
        status=OrganizationMembership.MemberStatus.ACTIVE,
    )
    _engagement(advisor, _student())

    membership.delete()
    assert len(_auth(advisor).get(STUDENTS_URL).data['students']) == 1


# ── B5: the projection is an allowlist, and it must not grow ──────────────────

@pytest.mark.api
def test_the_outbox_says_nothing_about_the_person_invited():
    """The residual-oracle boundary, pinned as a field list.

    An invite row appearing here already implies "this number belongs to a
    registered student" — a bounded, attributable, quota-capped signal that section
    ب)۲ accepts as the price of a working outbox. Adding a *name* would upgrade it
    to the full phone→identity oracle the uniform ``202`` exists to prevent. The
    student's name becomes visible the moment they accept, which is the correct
    trigger, so nothing is lost by keeping this closed.
    """
    advisor = _advisor()
    _pending(advisor, _student('ali', '09121110000', first_name='علی', last_name='رضایی'))

    invite = _auth(advisor).get(STUDENTS_URL).data['pendingInvites'][0]

    assert set(invite) == {'id', 'phoneMasked', 'invitedAt', 'expiresAt', 'isExpired'}
    serialized = str(invite)
    for leak in ('علی', 'رضایی', 'ali', '09121110000'):
        assert leak not in serialized


@pytest.mark.api
def test_the_roster_exposes_no_student_id():
    """An architectural lock, not a privacy nicety.

    Every advisory route from step 5 on is keyed by **engagement** id, because the
    engagement *is* the tenancy check. Publishing the student id invites a client —
    or a future endpoint — to build ``/students/<studentId>/plans/``, which looks
    equivalent and skips the join. Not publishing it is what stops that URL from
    being invented.
    """
    advisor = _advisor()
    student = _student('ali', '09121110000', first_name='علی', last_name='رضایی')
    engagement = _engagement(advisor, student)

    row = _auth(advisor).get(STUDENTS_URL).data['students'][0]

    assert set(row) == {
        'id', 'studentName', 'phoneMasked', 'mode', 'organizationName',
        'startedOn', 'status',
        # Risman step 1: which of the advisor's folders the row sits in.
        'folderId',
    }
    assert row['id'] == engagement.pk != student.pk
    assert 'studentId' not in row


@pytest.mark.api
def test_no_phone_number_is_ever_returned_in_full():
    """Including back to the advisor who typed it.

    A masked number is still recognisable to the person who entered it, so the
    rule costs nothing — and it means a stolen advisor session cannot be harvested
    into a contact list. One uniform rule also cannot be got wrong in step 9, when
    org-mode students arrive whose numbers this advisor never typed.
    """
    advisor = _advisor()
    _engagement(advisor, _student(phone='09121110000'))
    _pending(advisor, _student('other', '09122220000'))

    body = str(_auth(advisor).get(STUDENTS_URL).data)
    assert '09121110000' not in body
    assert '09122220000' not in body
    assert '0912***0000' in body


@pytest.mark.api
def test_the_student_is_told_who_is_asking():
    """The banner has to name the advisor, or the student is accepting blind.

    They are being asked to grant a stranger read access to their study log. A
    banner that cannot say *who* is asking gets accepted carelessly or rejects a
    legitimate advisor — both worse than naming them.
    """
    advisor = _advisor(first_name='زهرا', last_name='مرادی')
    student = _student(phone='09121110000')
    _pending(advisor, student)

    invite = _auth(student).get(ENGAGEMENT_URL).data['invites'][0]

    assert invite['advisorName'] == 'زهرا مرادی'
    assert invite['invitedPhoneMasked'] == '0912***0000'
    assert 'advisorId' not in invite


@pytest.mark.api
def test_an_advisor_with_no_name_still_gets_a_label():
    """Falls back to the username rather than to a generic «مشاور».

    A nameless banner is an unidentifiable request for access; the username is at
    least something the student can recognise or refuse on.
    """
    advisor = _advisor('moshaver_ahmadi', first_name='', last_name='')
    student = _student(phone='09121110000')
    _pending(advisor, student)

    invite = _auth(student).get(ENGAGEMENT_URL).data['invites'][0]
    assert invite['advisorName'] == 'moshaver_ahmadi'


@pytest.mark.api
def test_the_student_sees_their_active_advisor():
    advisor = _advisor(first_name='زهرا', last_name='مرادی')
    student = _student(phone='09121110000')
    engagement = _engagement(advisor, student)

    response = _auth(student).get(ENGAGEMENT_URL)
    assert response.data['active'] == {
        'id': engagement.pk,
        'advisorName': 'زهرا مرادی',
        'mode': Mode.FREELANCE,
        'organizationName': None,
        'startedOn': engagement.started_on.isoformat(),
        'status': Status.ACTIVE,
    }


@pytest.mark.api
def test_a_student_with_no_advisor_gets_an_empty_shape_not_a_404():
    """The absence of an advisor is the normal case for most of the platform.

    A 404 here would make every student dashboard render an error state, and there
    is no feature flag to gate the panel with — the presence of ``active`` *is* the
    flag, so it has to be a value, not an exception.
    """
    response = _auth(_student()).get(ENGAGEMENT_URL)
    assert response.status_code == 200
    assert response.data == {'active': None, 'invites': []}


@pytest.mark.api
def test_neither_list_is_paginated():
    """Both are bounded by design — a caseload and a hard-capped outbox.

    DRF's default pagination is global, so a list endpoint that forgets to opt out
    silently truncates at PAGE_SIZE. A roster that quietly loses students is a much
    worse failure than a long response.
    """
    advisor = _advisor()
    for i in range(3):
        _engagement(advisor, _student(f's{i}', f'0912111{i:04d}'))

    data = _auth(advisor).get(STUDENTS_URL).data
    assert isinstance(data['students'], list)
    assert len(data['students']) == 3
    assert 'results' not in data
