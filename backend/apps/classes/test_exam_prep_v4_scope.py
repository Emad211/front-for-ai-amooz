import pytest
from model_bakery import baker

from apps.classes.services.exam_prep_v4_scope import (
    ExamPrepV4ScopeError,
    resolve_exam_scope,
)
from apps.organizations.models import (
    Organization,
    OrganizationMembership,
    StudyGroup,
    StudyGroupTeacher,
)


pytestmark = pytest.mark.django_db


def _user(role='TEACHER'):
    return baker.make('accounts.User', role=role)


def _organization(owner=None, **kwargs):
    return Organization.objects.create(
        owner=owner,
        name=kwargs.pop('name', 'مدرسه'),
        slug=kwargs.pop('slug', f'org-{Organization.objects.count() + 1}'),
        **kwargs,
    )


def test_personal_scope_requires_no_organization_rows():
    user = _user()

    scope = resolve_exam_scope(user=user)

    assert scope.organization is None
    assert scope.study_group is None


def test_owner_can_use_active_organization_and_group_without_membership():
    owner = _user()
    organization = _organization(owner=owner)
    group = StudyGroup.objects.create(
        organization=organization,
        name='دوازدهم تجربی',
    )

    scope = resolve_exam_scope(
        user=owner,
        organization_id=organization.id,
        study_group_id=group.id,
    )

    assert scope.organization == organization
    assert scope.study_group == group


@pytest.mark.parametrize(
    'org_role',
    [
        OrganizationMembership.OrgRole.ADMIN,
        OrganizationMembership.OrgRole.DEPUTY,
        OrganizationMembership.OrgRole.TEACHER,
    ],
)
def test_active_staff_membership_can_use_organization(org_role):
    owner = _user()
    user = _user()
    organization = _organization(owner=owner)
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        org_role=org_role,
        status=OrganizationMembership.MemberStatus.ACTIVE,
    )

    scope = resolve_exam_scope(user=user, organization_id=organization.id)

    assert scope.organization == organization
    assert scope.study_group is None


def test_student_or_suspended_membership_is_hidden():
    owner = _user()
    student = _user(role='STUDENT')
    suspended_teacher = _user()
    organization = _organization(owner=owner)
    OrganizationMembership.objects.create(
        user=student,
        organization=organization,
        org_role=OrganizationMembership.OrgRole.STUDENT,
    )
    OrganizationMembership.objects.create(
        user=suspended_teacher,
        organization=organization,
        org_role=OrganizationMembership.OrgRole.TEACHER,
        status=OrganizationMembership.MemberStatus.SUSPENDED,
    )

    with pytest.raises(ExamPrepV4ScopeError):
        resolve_exam_scope(user=student, organization_id=organization.id)
    with pytest.raises(ExamPrepV4ScopeError):
        resolve_exam_scope(
            user=suspended_teacher,
            organization_id=organization.id,
        )


def test_teacher_needs_explicit_study_group_assignment():
    owner = _user()
    teacher = _user()
    organization = _organization(owner=owner)
    group = StudyGroup.objects.create(
        organization=organization,
        name='گروه الف',
    )
    OrganizationMembership.objects.create(
        user=teacher,
        organization=organization,
        org_role=OrganizationMembership.OrgRole.TEACHER,
    )

    with pytest.raises(ExamPrepV4ScopeError):
        resolve_exam_scope(
            user=teacher,
            organization_id=organization.id,
            study_group_id=group.id,
        )

    StudyGroupTeacher.objects.create(
        study_group=group,
        teacher=teacher,
        assigned_by=owner,
    )
    scope = resolve_exam_scope(
        user=teacher,
        organization_id=organization.id,
        study_group_id=group.id,
    )
    assert scope.study_group == group


def test_inactive_group_and_suspended_organization_are_hidden():
    owner = _user()
    suspended = _organization(
        owner=owner,
        name='تعلیق',
        slug='suspended-org',
        subscription_status=Organization.SubscriptionStatus.SUSPENDED,
    )
    active = _organization(owner=owner, name='فعال', slug='active-org')
    archived_group = StudyGroup.objects.create(
        organization=active,
        name='قدیمی',
        status=StudyGroup.Status.ARCHIVED,
    )

    with pytest.raises(ExamPrepV4ScopeError):
        resolve_exam_scope(user=owner, organization_id=suspended.id)
    with pytest.raises(ExamPrepV4ScopeError):
        resolve_exam_scope(user=owner, study_group_id=archived_group.id)


def test_group_cannot_be_paired_with_another_organization():
    owner = _user()
    first = _organization(owner=owner, name='اول', slug='first-org')
    second = _organization(owner=owner, name='دوم', slug='second-org')
    group = StudyGroup.objects.create(organization=first, name='گروه')

    with pytest.raises(ExamPrepV4ScopeError, match='does not belong'):
        resolve_exam_scope(
            user=owner,
            organization_id=second.id,
            study_group_id=group.id,
        )
