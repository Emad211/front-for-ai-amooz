"""S1 — the ADVISOR (مشاور) platform role exists and grants nothing by default.

Zero-token, no-network. Guards the landmines documented in
docs/features/advisor-mvp.md §4-الف (A3, A4, A5, A6) — every one of them is a
*silent* failure mode, so a regression here looks like working software.
"""

import pytest
from django.contrib.auth import get_user_model
from model_bakery import baker
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.classes.permissions import IsStudentUser, IsTeacherUser
from apps.core.permissions import IsAdvisorUser, IsPlatformAdmin, IsStudentRole
from apps.organizations.models import InvitationCode, OrganizationMembership

User = get_user_model()

pytestmark = pytest.mark.django_db


# ── the role value itself ────────────────────────────────────────────────────

def test_advisor_role_value_fits_the_column():
    """'ADVISOR' must fit max_length=10 — that is why no column rewrite is needed."""
    assert User.Role.ADVISOR == 'ADVISOR'
    assert len(User.Role.ADVISOR.value) <= User._meta.get_field('role').max_length


def test_advisor_is_an_offered_choice():
    assert 'ADVISOR' in dict(User.Role.choices)
    # The admin user-update serializer derives its dropdown from Role.choices, so
    # the platform admin can assign the role without any extra wiring.
    from apps.commons.views import UserUpdateSerializer

    assert 'ADVISOR' in dict(UserUpdateSerializer().fields['role'].choices)


def test_advisor_org_role_value_exists_and_fits():
    assert OrganizationMembership.OrgRole.ADVISOR == 'advisor'
    field = OrganizationMembership._meta.get_field('org_role')
    assert len(OrganizationMembership.OrgRole.ADVISOR.value) <= field.max_length
    assert 'advisor' in dict(field.choices)


def test_invitation_code_cannot_target_an_advisor():
    """An advisor account is admin-created only.

    The org invite code is a permanent passwordless login credential
    (authentication/views.py redeems code+phone straight into a JWT). Letting a
    code mint an ADVISOR would hand an advisor identity to anyone holding it.
    """
    assert 'advisor' not in dict(InvitationCode.TargetRole.choices)


# ── A3: the staff tick force-flips a brand-new user to ADMIN ─────────────────

def test_new_user_with_staff_tick_lands_on_admin_not_advisor():
    """accounts/signals.py promotes any newly created staff user to ADMIN.

    So an advisor account created in Django admin must NEVER get the staff tick —
    it would silently become a platform admin. This test is the tripwire for
    anyone who "fixes" that signal or the runbook step.
    """
    user = baker.make(
        'accounts.User', username='adv-staff', role=User.Role.ADVISOR, is_staff=True,
    )
    user.refresh_from_db()
    assert user.role == User.Role.ADMIN


def test_advisor_without_staff_tick_keeps_the_role():
    user = baker.make('accounts.User', username='adv-clean', role=User.Role.ADVISOR)
    user.refresh_from_db()
    assert user.role == User.Role.ADVISOR
    assert not user.is_staff and not user.is_superuser


# ── A4: ADVISOR has no profile model, on purpose ─────────────────────────────

def test_advisor_gets_no_profile_row():
    """Like MANAGER, ADVISOR is not a learner/teacher/admin identity.

    The profile chain in signals.py and MeUpdateSerializer.update both stop
    before ADVISOR, so `PUT /api/accounts/profile/` would 200 while saving
    nothing. The MVP answer is "no profile model + hide those fields in the UI",
    not a fourth profile table. If someone adds one, this test tells them the UI
    and the serializer must change too.
    """
    advisor = baker.make('accounts.User', username='adv-noprofile', role=User.Role.ADVISOR)

    assert not hasattr(advisor, 'studentprofile')
    assert not hasattr(advisor, 'teacherprofile')
    assert not hasattr(advisor, 'adminprofile')


# ── A6: a fifth role must widen nothing ─────────────────────────────────────

def _has_perm(permission, user) -> bool:
    request = APIRequestFactory().get('/')
    force_authenticate(request, user=user)
    request.user = user
    return permission().has_permission(request, view=None)


def test_advisor_inherits_no_existing_permission():
    advisor = baker.make('accounts.User', username='adv-perm', role=User.Role.ADVISOR)

    assert not _has_perm(IsPlatformAdmin, advisor)
    assert not _has_perm(IsTeacherUser, advisor)
    # IsStudentUser admits STUDENT + TEACHER; an advisor must not slip in.
    assert not _has_perm(IsStudentUser, advisor)
    assert not _has_perm(IsStudentRole, advisor)


def test_is_advisor_user_admits_only_advisors():
    advisor = baker.make('accounts.User', username='adv-ok', role=User.Role.ADVISOR)
    assert _has_perm(IsAdvisorUser, advisor)

    for role in (User.Role.STUDENT, User.Role.TEACHER, User.Role.MANAGER, User.Role.ADMIN):
        other = baker.make('accounts.User', username=f'other-{role.lower()}', role=role)
        assert not _has_perm(IsAdvisorUser, other), f'{role} must not pass IsAdvisorUser'


def test_is_advisor_user_rejects_a_platform_admin_and_superuser():
    """An admin manages accounts; they do not inherit an advisor's roster."""
    superuser = baker.make(
        'accounts.User', username='root', is_superuser=True, is_staff=True,
    )
    assert not _has_perm(IsAdvisorUser, superuser)


def test_is_student_role_is_stricter_than_is_student_user():
    teacher = baker.make('accounts.User', username='t-strict', role=User.Role.TEACHER)
    student = baker.make('accounts.User', username='s-strict', role=User.Role.STUDENT)

    # The legacy class-facing permission lets teachers act as learners …
    assert _has_perm(IsStudentUser, teacher)
    # … the advisory one must not.
    assert not _has_perm(IsStudentRole, teacher)
    assert _has_perm(IsStudentRole, student)


def test_unauthenticated_request_passes_neither_advisory_permission():
    from django.contrib.auth.models import AnonymousUser

    anon = AnonymousUser()
    assert not _has_perm(IsAdvisorUser, anon)
    assert not _has_perm(IsStudentRole, anon)
