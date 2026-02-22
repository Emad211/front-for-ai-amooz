"""Tests for the organizations app."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.organizations.models import (
    InvitationCode,
    Organization,
    OrganizationMembership,
)

User = get_user_model()


@pytest.fixture
def platform_admin(db):
    return User.objects.create_superuser(
        username='superadmin',
        password='AdminPass123!',
        email='admin@example.com',
        role='ADMIN',
    )


@pytest.fixture
def teacher_user(db):
    return User.objects.create_user(
        username='teacher1',
        password='TeacherPass1!',
        role='TEACHER',
    )


@pytest.fixture
def student_user(db):
    return User.objects.create_user(
        username='student1',
        password='StudentPass1!',
        role='STUDENT',
    )


@pytest.fixture
def admin_client(platform_admin):
    client = APIClient()
    client.force_authenticate(user=platform_admin)
    return client


@pytest.fixture
def teacher_client(teacher_user):
    client = APIClient()
    client.force_authenticate(user=teacher_user)
    return client


@pytest.fixture
def student_client(student_user):
    client = APIClient()
    client.force_authenticate(user=student_user)
    return client


@pytest.fixture
def anon_client():
    return APIClient()


@pytest.fixture
def org(db, platform_admin):
    return Organization.objects.create(
        name='مدرسه تست',
        slug='test-school',
        student_capacity=60,
        owner=platform_admin,
    )


@pytest.fixture
def org_admin_membership(org, teacher_user):
    return OrganizationMembership.objects.create(
        user=teacher_user,
        organization=org,
        org_role=OrganizationMembership.OrgRole.ADMIN,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Organization CRUD (platform admin only)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestOrganizationCRUD:
    """Platform admin org CRUD endpoints."""

    def test_create_org(self, admin_client):
        resp = admin_client.post(
            reverse('organizations:org-list-create'),
            {'name': 'آموزشگاه نمونه', 'slug': 'sample-school', 'student_capacity': 100},
            format='json',
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data['name'] == 'آموزشگاه نمونه'
        assert resp.data['slug'] == 'sample-school'
        assert 'adminActivationCode' in resp.data
        # Verify org + code were actually created
        assert Organization.objects.filter(slug='sample-school').exists()
        assert InvitationCode.objects.filter(
            organization__slug='sample-school',
            target_role='admin',
        ).exists()

    def test_create_org_duplicate_slug(self, admin_client, org):
        resp = admin_client.post(
            reverse('organizations:org-list-create'),
            {'name': 'تکراری', 'slug': org.slug},
            format='json',
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_list_orgs(self, admin_client, org):
        resp = admin_client.get(reverse('organizations:org-list-create'))
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) >= 1

    def test_get_org(self, admin_client, org):
        resp = admin_client.get(
            reverse('organizations:org-detail', kwargs={'org_pk': org.pk}),
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['name'] == org.name

    def test_update_org(self, admin_client, org):
        resp = admin_client.patch(
            reverse('organizations:org-detail', kwargs={'org_pk': org.pk}),
            {'name': 'نام جدید'},
            format='json',
        )
        assert resp.status_code == status.HTTP_200_OK
        org.refresh_from_db()
        assert org.name == 'نام جدید'

    def test_delete_org(self, admin_client, org):
        resp = admin_client.delete(
            reverse('organizations:org-detail', kwargs={'org_pk': org.pk}),
        )
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        assert not Organization.objects.filter(pk=org.pk).exists()

    def test_non_admin_cannot_create_org(self, teacher_client):
        resp = teacher_client.post(
            reverse('organizations:org-list-create'),
            {'name': 'test', 'slug': 'test'},
            format='json',
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_non_admin_cannot_list_orgs(self, student_client):
        resp = student_client.get(reverse('organizations:org-list-create'))
        assert resp.status_code == status.HTTP_403_FORBIDDEN


# ═══════════════════════════════════════════════════════════════════════════════
# Membership Management
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestMemberManagement:
    """Org admin/deputy member management."""

    def test_list_members(self, teacher_client, org, org_admin_membership):
        resp = teacher_client.get(
            reverse('organizations:org-member-list', kwargs={'org_pk': org.pk}),
        )
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) >= 1

    def test_update_member_role(self, teacher_client, org, org_admin_membership, student_user):
        # Add a student membership first
        mem = OrganizationMembership.objects.create(
            user=student_user,
            organization=org,
            org_role='student',
        )
        resp = teacher_client.patch(
            reverse('organizations:org-member-detail',
                    kwargs={'org_pk': org.pk, 'membership_pk': mem.pk}),
            {'org_role': 'teacher'},
            format='json',
        )
        assert resp.status_code == status.HTTP_200_OK
        mem.refresh_from_db()
        assert mem.org_role == 'teacher'

    def test_remove_member(self, teacher_client, org, org_admin_membership, student_user):
        mem = OrganizationMembership.objects.create(
            user=student_user,
            organization=org,
            org_role='student',
        )
        resp = teacher_client.delete(
            reverse('organizations:org-member-detail',
                    kwargs={'org_pk': org.pk, 'membership_pk': mem.pk}),
        )
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        assert not OrganizationMembership.objects.filter(pk=mem.pk).exists()

    def test_non_org_admin_cannot_list_members(self, student_client, org):
        resp = student_client.get(
            reverse('organizations:org-member-list', kwargs={'org_pk': org.pk}),
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_platform_admin_can_list_members(self, admin_client, org, org_admin_membership):
        resp = admin_client.get(
            reverse('organizations:org-member-list', kwargs={'org_pk': org.pk}),
        )
        assert resp.status_code == status.HTTP_200_OK


# ═══════════════════════════════════════════════════════════════════════════════
# Invitation Codes
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestInvitationCodes:
    """Invitation code management."""

    def test_create_code(self, teacher_client, org, org_admin_membership):
        resp = teacher_client.post(
            reverse('organizations:org-invite-list-create', kwargs={'org_pk': org.pk}),
            {'target_role': 'student', 'label': 'کلاس ۱۰', 'max_uses': 30},
            format='json',
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data['targetRole'] == 'student'
        assert InvitationCode.objects.filter(organization=org, target_role='student').exists()

    def test_create_custom_code(self, teacher_client, org, org_admin_membership):
        resp = teacher_client.post(
            reverse('organizations:org-invite-list-create', kwargs={'org_pk': org.pk}),
            {'target_role': 'teacher', 'custom_code': 'MYCODE123'},
            format='json',
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data['code'] == 'MYCODE123'

    def test_list_codes(self, teacher_client, org, org_admin_membership):
        InvitationCode.objects.create(
            organization=org, target_role='student', created_by=None,
        )
        resp = teacher_client.get(
            reverse('organizations:org-invite-list-create', kwargs={'org_pk': org.pk}),
        )
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) >= 1

    def test_deactivate_code(self, teacher_client, org, org_admin_membership):
        code = InvitationCode.objects.create(
            organization=org, target_role='student', created_by=None,
        )
        resp = teacher_client.patch(
            reverse('organizations:org-invite-detail',
                    kwargs={'org_pk': org.pk, 'code_pk': code.pk}),
            {'is_active': False},
            format='json',
        )
        assert resp.status_code == status.HTTP_200_OK
        code.refresh_from_db()
        assert not code.is_active

    def test_delete_code(self, teacher_client, org, org_admin_membership):
        code = InvitationCode.objects.create(
            organization=org, target_role='student', created_by=None,
        )
        resp = teacher_client.delete(
            reverse('organizations:org-invite-detail',
                    kwargs={'org_pk': org.pk, 'code_pk': code.pk}),
        )
        assert resp.status_code == status.HTTP_204_NO_CONTENT


# ═══════════════════════════════════════════════════════════════════════════════
# Redeem Invitation Code
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRedeemCode:
    """Redeem invitation code (join org)."""

    def test_authenticated_user_redeems_code(self, teacher_client, org, teacher_user):
        code = InvitationCode.objects.create(
            organization=org, target_role='teacher', max_uses=5,
        )
        resp = teacher_client.post(
            reverse('organizations:redeem-code'),
            {'code': code.code},
            format='json',
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data['success'] is True
        assert OrganizationMembership.objects.filter(
            user=teacher_user, organization=org,
        ).exists()
        code.refresh_from_db()
        assert code.use_count == 1

    def test_anonymous_user_registers_and_joins(self, anon_client, org):
        code = InvitationCode.objects.create(
            organization=org, target_role='student', max_uses=10,
        )
        resp = anon_client.post(
            reverse('organizations:redeem-code'),
            {
                'code': code.code,
                'username': 'newstudent',
                'password': 'SecurePass123!',
                'first_name': 'علی',
                'last_name': 'محمدی',
            },
            format='json',
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert 'access' in resp.data
        assert 'refresh' in resp.data
        assert User.objects.filter(username='newstudent').exists()
        new_user = User.objects.get(username='newstudent')
        assert OrganizationMembership.objects.filter(
            user=new_user, organization=org,
        ).exists()

    def test_redeem_invalid_code(self, teacher_client):
        resp = teacher_client.post(
            reverse('organizations:redeem-code'),
            {'code': 'NONEXISTENT'},
            format='json',
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_redeem_expired_code(self, teacher_client, org):
        from django.utils import timezone
        from datetime import timedelta
        code = InvitationCode.objects.create(
            organization=org,
            target_role='student',
            expires_at=timezone.now() - timedelta(days=1),
        )
        resp = teacher_client.post(
            reverse('organizations:redeem-code'),
            {'code': code.code},
            format='json',
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_redeem_duplicate_membership(self, teacher_client, org, teacher_user):
        OrganizationMembership.objects.create(
            user=teacher_user, organization=org, org_role='teacher',
        )
        code = InvitationCode.objects.create(
            organization=org, target_role='teacher', max_uses=5,
        )
        resp = teacher_client.post(
            reverse('organizations:redeem-code'),
            {'code': code.code},
            format='json',
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_admin_code_sets_org_owner(self, anon_client, org):
        # Remove existing owner
        org.owner = None
        org.save(update_fields=['owner'])
        code = InvitationCode.objects.create(
            organization=org, target_role='admin', max_uses=1,
        )
        resp = anon_client.post(
            reverse('organizations:redeem-code'),
            {
                'code': code.code,
                'username': 'orgadmin',
                'password': 'AdminPass123!',
            },
            format='json',
        )
        assert resp.status_code == status.HTTP_201_CREATED
        org.refresh_from_db()
        assert org.owner is not None
        assert org.owner.username == 'orgadmin'


# ═══════════════════════════════════════════════════════════════════════════════
# Validate Invitation Code
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestValidateCode:
    """Validate invitation code endpoint."""

    def test_valid_code(self, anon_client, org):
        code = InvitationCode.objects.create(
            organization=org, target_role='student', max_uses=10,
        )
        resp = anon_client.get(
            reverse('organizations:validate-code') + f'?code={code.code}',
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['valid'] is True
        assert resp.data['organization']['name'] == org.name

    def test_invalid_code(self, anon_client):
        resp = anon_client.get(
            reverse('organizations:validate-code') + '?code=NOPE',
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['valid'] is False

    def test_empty_code(self, anon_client):
        resp = anon_client.get(reverse('organizations:validate-code'))
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ═══════════════════════════════════════════════════════════════════════════════
# Workspaces
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestWorkspaces:
    """My workspaces endpoint."""

    def test_user_with_memberships(self, teacher_client, org, teacher_user):
        OrganizationMembership.objects.create(
            user=teacher_user, organization=org, org_role='teacher',
        )
        resp = teacher_client.get(reverse('organizations:my-workspaces'))
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) == 1
        assert resp.data[0]['slug'] == org.slug

    def test_user_without_memberships(self, student_client):
        resp = student_client.get(reverse('organizations:my-workspaces'))
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) == 0

    def test_anonymous_cannot_access(self, anon_client):
        resp = anon_client.get(reverse('organizations:my-workspaces'))
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ═══════════════════════════════════════════════════════════════════════════════
# Org Dashboard
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestOrgDashboard:
    """Org dashboard stats."""

    def test_org_admin_can_view(self, teacher_client, org, org_admin_membership):
        resp = teacher_client.get(
            reverse('organizations:org-dashboard', kwargs={'org_pk': org.pk}),
        )
        assert resp.status_code == status.HTTP_200_OK
        assert 'stats' in resp.data
        assert 'organization' in resp.data

    def test_non_member_forbidden(self, student_client, org):
        resp = student_client.get(
            reverse('organizations:org-dashboard', kwargs={'org_pk': org.pk}),
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_platform_admin_can_view(self, admin_client, org):
        resp = admin_client.get(
            reverse('organizations:org-dashboard', kwargs={'org_pk': org.pk}),
        )
        assert resp.status_code == status.HTTP_200_OK


# ═══════════════════════════════════════════════════════════════════════════════
# Model constraints
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestModelConstraints:
    """Test model-level constraints."""

    def test_unique_slug(self, db, platform_admin):
        Organization.objects.create(name='A', slug='unique-slug', owner=platform_admin)
        with pytest.raises(Exception):
            Organization.objects.create(name='B', slug='unique-slug', owner=platform_admin)

    def test_unique_membership(self, org, teacher_user):
        OrganizationMembership.objects.create(
            user=teacher_user, organization=org, org_role='teacher',
        )
        with pytest.raises(Exception):
            OrganizationMembership.objects.create(
                user=teacher_user, organization=org, org_role='student',
            )

    def test_invitation_code_auto_generated(self, org):
        code = InvitationCode.objects.create(
            organization=org, target_role='student',
        )
        assert len(code.code) == 6
        assert code.code == code.code.upper()

    def test_is_valid_property(self, org):
        code = InvitationCode.objects.create(
            organization=org, target_role='student', max_uses=1,
        )
        assert code.is_valid is True
        code.use_count = 1
        code.save()
        assert code.is_valid is False

    def test_organization_student_count(self, org, teacher_user, student_user):
        OrganizationMembership.objects.create(
            user=student_user, organization=org, org_role='student',
        )
        assert org.current_student_count == 1

        OrganizationMembership.objects.create(
            user=teacher_user, organization=org, org_role='teacher',
        )
        # Teacher membership should not count as student
        assert org.current_student_count == 1


# ═══════════════════════════════════════════════════════════════════════════════
# camelCase serializer output validation
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestSerializerCamelCase:
    """Verify all API responses use camelCase keys matching the frontend types."""

    def test_org_list_uses_camel_case(self, admin_client, org):
        resp = admin_client.get(reverse('organizations:org-list-create'))
        assert resp.status_code == status.HTTP_200_OK
        item = resp.data[0]
        assert 'studentCapacity' in item
        assert 'subscriptionStatus' in item
        assert 'currentStudentCount' in item
        assert 'ownerName' in item
        assert 'createdAt' in item
        assert 'updatedAt' in item
        # Verify old snake_case keys are NOT present
        assert 'student_capacity' not in item
        assert 'subscription_status' not in item
        assert 'current_student_count' not in item

    def test_org_create_returns_camel_case_key(self, admin_client):
        resp = admin_client.post(
            reverse('organizations:org-list-create'),
            {'name': 'CamelTest', 'slug': 'camel-test', 'student_capacity': 50},
            format='json',
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert 'adminActivationCode' in resp.data

    def test_member_list_uses_camel_case(self, teacher_client, org, org_admin_membership):
        resp = teacher_client.get(
            reverse('organizations:org-member-list', kwargs={'org_pk': org.pk}),
        )
        assert resp.status_code == status.HTTP_200_OK
        item = resp.data[0]
        assert 'orgRole' in item
        assert 'orgRoleDisplay' in item
        assert 'userName' in item
        assert 'joinedAt' in item
        assert 'org_role' not in item

    def test_invitation_code_list_uses_camel_case(self, teacher_client, org, org_admin_membership):
        InvitationCode.objects.create(organization=org, target_role='student')
        resp = teacher_client.get(
            reverse('organizations:org-invite-list-create', kwargs={'org_pk': org.pk}),
        )
        assert resp.status_code == status.HTTP_200_OK
        item = resp.data[0]
        assert 'targetRole' in item
        assert 'targetRoleDisplay' in item
        assert 'maxUses' in item
        assert 'useCount' in item
        assert 'remainingUses' in item
        assert 'isValid' in item
        assert 'isActive' in item
        assert 'target_role' not in item
        assert 'max_uses' not in item

    def test_validate_code_returns_camel_case(self, anon_client, org):
        code = InvitationCode.objects.create(
            organization=org, target_role='student', max_uses=10,
        )
        resp = anon_client.get(
            reverse('organizations:validate-code') + f'?code={code.code}',
        )
        assert resp.status_code == status.HTTP_200_OK
        assert 'targetRole' in resp.data
        assert 'targetRoleDisplay' in resp.data
        assert 'remainingUses' in resp.data
        assert 'needsRegistration' in resp.data

    def test_workspace_list_returns_camel_case(self, teacher_client, org, teacher_user):
        OrganizationMembership.objects.create(
            user=teacher_user, organization=org, org_role='teacher',
        )
        resp = teacher_client.get(reverse('organizations:my-workspaces'))
        assert resp.status_code == status.HTTP_200_OK
        item = resp.data[0]
        assert 'orgRole' in item
        assert 'orgRoleDisplay' in item
        assert 'org_role' not in item

    def test_dashboard_stats_use_camel_case(self, teacher_client, org, org_admin_membership):
        resp = teacher_client.get(
            reverse('organizations:org-dashboard', kwargs={'org_pk': org.pk}),
        )
        assert resp.status_code == status.HTTP_200_OK
        stats = resp.data['stats']
        assert 'totalMembers' in stats
        assert 'studentCapacity' in stats
        assert 'totalClasses' in stats
        assert 'publishedClasses' in stats
        assert 'activeInviteCodes' in stats
        # Verify org uses camelCase too
        org_data = resp.data['organization']
        assert 'studentCapacity' in org_data


# ═══════════════════════════════════════════════════════════════════════════════
# Security & Authorization (negative tests)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestSecurityAuthorization:
    """Verify deny-by-default and unauthorized/forbidden paths."""

    def test_anon_cannot_list_orgs(self, anon_client):
        resp = anon_client.get(reverse('organizations:org-list-create'))
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_anon_cannot_create_org(self, anon_client):
        resp = anon_client.post(
            reverse('organizations:org-list-create'),
            {'name': 'hack', 'slug': 'hacked'},
            format='json',
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_student_cannot_create_org(self, student_client):
        resp = student_client.post(
            reverse('organizations:org-list-create'),
            {'name': 'hack', 'slug': 'hacked'},
            format='json',
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_student_cannot_delete_org(self, student_client, org):
        resp = student_client.delete(
            reverse('organizations:org-detail', kwargs={'org_pk': org.pk}),
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_student_cannot_manage_members(self, student_client, org):
        resp = student_client.get(
            reverse('organizations:org-member-list', kwargs={'org_pk': org.pk}),
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_org_admin_cannot_manage_other_org(self, teacher_client, org_admin_membership, db, platform_admin):
        """Org admin of org A cannot access org B."""
        other_org = Organization.objects.create(
            name='Other Org', slug='other-org', owner=platform_admin,
        )
        resp = teacher_client.get(
            reverse('organizations:org-member-list', kwargs={'org_pk': other_org.pk}),
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_anon_cannot_access_workspaces(self, anon_client):
        resp = anon_client.get(reverse('organizations:my-workspaces'))
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_anon_cannot_access_dashboard(self, anon_client, org):
        resp = anon_client.get(
            reverse('organizations:org-dashboard', kwargs={'org_pk': org.pk}),
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_non_member_cannot_view_dashboard(self, student_client, org):
        resp = student_client.get(
            reverse('organizations:org-dashboard', kwargs={'org_pk': org.pk}),
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_student_member_cannot_manage_codes(self, student_client, org, student_user):
        """A student member of the org is not an admin — cannot create invite codes."""
        OrganizationMembership.objects.create(
            user=student_user, organization=org, org_role='student',
        )
        resp = student_client.post(
            reverse('organizations:org-invite-list-create', kwargs={'org_pk': org.pk}),
            {'target_role': 'student'},
            format='json',
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_redeem_code_with_weak_password(self, anon_client, org):
        """Anonymous registration with a weak password should be rejected."""
        code = InvitationCode.objects.create(
            organization=org, target_role='student', max_uses=10,
        )
        resp = anon_client.post(
            reverse('organizations:redeem-code'),
            {'code': code.code, 'username': 'weakuser', 'password': '123'},
            format='json',
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_redeem_code_duplicate_username(self, anon_client, org, teacher_user):
        """If username already exists, reject registration."""
        code = InvitationCode.objects.create(
            organization=org, target_role='student', max_uses=10,
        )
        resp = anon_client.post(
            reverse('organizations:redeem-code'),
            {
                'code': code.code,
                'username': teacher_user.username,
                'password': 'StrongPass123!',
            },
            format='json',
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_redeem_code_missing_credentials(self, anon_client, org):
        """Anonymous user must provide username+password."""
        code = InvitationCode.objects.create(
            organization=org, target_role='student', max_uses=10,
        )
        resp = anon_client.post(
            reverse('organizations:redeem-code'),
            {'code': code.code},
            format='json',
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ═══════════════════════════════════════════════════════════════════════════════
# Edge Cases
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_redeem_at_max_capacity(self, db, platform_admin):
        """Student code redemption when org is at student capacity."""
        org = Organization.objects.create(
            name='Small', slug='small', student_capacity=1, owner=platform_admin,
        )
        # Fill capacity
        existing = User.objects.create_user(username='existing', password='Pass123!')
        OrganizationMembership.objects.create(
            user=existing, organization=org, org_role='student',
        )
        # Try to add another student
        code = InvitationCode.objects.create(
            organization=org, target_role='student', max_uses=10,
        )
        client = APIClient()
        new_user = User.objects.create_user(username='overflow', password='Pass123!')
        client.force_authenticate(user=new_user)
        resp = client.post(
            reverse('organizations:redeem-code'),
            {'code': code.code},
            format='json',
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_teacher_not_blocked_by_student_capacity(self, db, platform_admin):
        """Teacher code should work even when student capacity is full."""
        org = Organization.objects.create(
            name='Full', slug='full', student_capacity=0, owner=platform_admin,
        )
        code = InvitationCode.objects.create(
            organization=org, target_role='teacher', max_uses=5,
        )
        client = APIClient()
        user = User.objects.create_user(username='teacher_ok', password='Pass123!')
        client.force_authenticate(user=user)
        resp = client.post(
            reverse('organizations:redeem-code'),
            {'code': code.code},
            format='json',
        )
        assert resp.status_code == status.HTTP_201_CREATED

    def test_redeem_code_at_max_uses(self, teacher_client, org, teacher_user):
        """Code at max_uses should not be redeemable."""
        code = InvitationCode.objects.create(
            organization=org, target_role='teacher', max_uses=1, use_count=1,
        )
        resp = teacher_client.post(
            reverse('organizations:redeem-code'),
            {'code': code.code},
            format='json',
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_deactivated_code_cannot_be_redeemed(self, teacher_client, org):
        code = InvitationCode.objects.create(
            organization=org, target_role='student', max_uses=10, is_active=False,
        )
        resp = teacher_client.post(
            reverse('organizations:redeem-code'),
            {'code': code.code},
            format='json',
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_case_insensitive_code_redeem(self, teacher_client, org):
        """Code redemption should be case-insensitive."""
        code = InvitationCode.objects.create(
            organization=org, target_role='teacher', max_uses=5,
        )
        resp = teacher_client.post(
            reverse('organizations:redeem-code'),
            {'code': code.code.lower()},  # lowercase input
            format='json',
        )
        assert resp.status_code == status.HTTP_201_CREATED

    def test_org_detail_not_found(self, admin_client):
        resp = admin_client.get(
            reverse('organizations:org-detail', kwargs={'org_pk': 9999}),
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_dashboard_not_found(self, admin_client):
        resp = admin_client.get(
            reverse('organizations:org-dashboard', kwargs={'org_pk': 9999}),
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_custom_code_duplicate(self, teacher_client, org, org_admin_membership):
        """Creating a code with an already-existing custom code should fail."""
        InvitationCode.objects.create(
            organization=org, target_role='student', code='DUPE123',
        )
        resp = teacher_client.post(
            reverse('organizations:org-invite-list-create', kwargs={'org_pk': org.pk}),
            {'target_role': 'student', 'custom_code': 'DUPE123'},
            format='json',
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_update_org_slug_does_not_collide(self, admin_client, org, db, platform_admin):
        """Updating org slug to an existing slug should fail."""
        Organization.objects.create(name='Other', slug='other-slug', owner=platform_admin)
        resp = admin_client.patch(
            reverse('organizations:org-detail', kwargs={'org_pk': org.pk}),
            {'slug': 'other-slug'},
            format='json',
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_suspended_member_not_in_workspace_list(self, teacher_client, teacher_user, org):
        """Suspended membership should not appear in workspace list."""
        OrganizationMembership.objects.create(
            user=teacher_user, organization=org, org_role='teacher',
            status='suspended',
        )
        resp = teacher_client.get(reverse('organizations:my-workspaces'))
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) == 0

    def test_member_search_filter(self, teacher_client, org, org_admin_membership, student_user, db):
        """Member list respects search query parameter."""
        OrganizationMembership.objects.create(
            user=student_user, organization=org, org_role='student',
        )
        resp = teacher_client.get(
            reverse('organizations:org-member-list', kwargs={'org_pk': org.pk}),
            {'search': student_user.username},
        )
        assert resp.status_code == status.HTTP_200_OK
        # The search should return at least the matching member
        usernames = [m['userName'] for m in resp.data]
        assert student_user.username in usernames

    def test_member_role_filter(self, teacher_client, org, org_admin_membership, student_user, db):
        """Member list respects role query parameter."""
        OrganizationMembership.objects.create(
            user=student_user, organization=org, org_role='student',
        )
        resp = teacher_client.get(
            reverse('organizations:org-member-list', kwargs={'org_pk': org.pk}),
            {'role': 'student'},
        )
        assert resp.status_code == status.HTTP_200_OK
        for m in resp.data:
            assert m['orgRole'] == 'student'


# ═══════════════════════════════════════════════════════════════════════════════
# Query / Database integrity
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestQueryIntegrity:
    """Database-level checks: constraints, ordering, counts."""

    def test_invitation_use_count_increments_atomically(self, db, platform_admin):
        """After redemption, use_count is actually incremented in DB."""
        org = Organization.objects.create(
            name='AtomicOrg', slug='atomic-org', student_capacity=100, owner=platform_admin,
        )
        code = InvitationCode.objects.create(
            organization=org, target_role='student', max_uses=10,
        )
        user = User.objects.create_user(username='atomicuser', password='Pass1234!')
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.post(
            reverse('organizations:redeem-code'),
            {'code': code.code},
            format='json',
        )
        assert resp.status_code == status.HTTP_201_CREATED
        code.refresh_from_db()
        assert code.use_count == 1

    def test_delete_org_cascades_memberships(self, admin_client, org, org_admin_membership):
        """Deleting org should cascade-delete memberships."""
        mem_pk = org_admin_membership.pk
        admin_client.delete(
            reverse('organizations:org-detail', kwargs={'org_pk': org.pk}),
        )
        assert not OrganizationMembership.objects.filter(pk=mem_pk).exists()

    def test_delete_org_cascades_codes(self, admin_client, org):
        """Deleting org should cascade-delete invitation codes."""
        code = InvitationCode.objects.create(
            organization=org, target_role='student',
        )
        code_pk = code.pk
        admin_client.delete(
            reverse('organizations:org-detail', kwargs={'org_pk': org.pk}),
        )
        assert not InvitationCode.objects.filter(pk=code_pk).exists()

    def test_dashboard_stats_accuracy(self, teacher_client, org, org_admin_membership, db, platform_admin):
        """Dashboard stats should accurately reflect actual DB counts."""
        # Add members
        s1 = User.objects.create_user(username='s1', password='Pass!')
        s2 = User.objects.create_user(username='s2', password='Pass!')
        t1 = User.objects.create_user(username='t1', password='Pass!')
        OrganizationMembership.objects.create(user=s1, organization=org, org_role='student')
        OrganizationMembership.objects.create(user=s2, organization=org, org_role='student')
        OrganizationMembership.objects.create(user=t1, organization=org, org_role='teacher')
        # Add a suspended member — should not count
        suspended = User.objects.create_user(username='susp', password='Pass!')
        OrganizationMembership.objects.create(
            user=suspended, organization=org, org_role='student', status='suspended',
        )
        # Add invitation codes
        InvitationCode.objects.create(organization=org, target_role='student', is_active=True)
        InvitationCode.objects.create(organization=org, target_role='student', is_active=False)

        resp = teacher_client.get(
            reverse('organizations:org-dashboard', kwargs={'org_pk': org.pk}),
        )
        assert resp.status_code == status.HTTP_200_OK
        stats = resp.data['stats']
        # org_admin_membership (admin) + 2 students + 1 teacher = 4 active members
        assert stats['totalMembers'] == 4
        assert stats['students'] == 2
        assert stats['teachers'] == 1
        assert stats['studentCapacity'] == org.student_capacity
        assert stats['activeInviteCodes'] == 1  # only 1 active code

    def test_is_at_capacity_property(self, db, platform_admin):
        """Organization.is_at_capacity returns True when at limit."""
        org = Organization.objects.create(
            name='Tiny', slug='tiny', student_capacity=1, owner=platform_admin,
        )
        assert not org.is_at_capacity
        user = User.objects.create_user(username='cap_user', password='Pass!')
        OrganizationMembership.objects.create(user=user, organization=org, org_role='student')
        assert org.is_at_capacity

    def test_remaining_uses_property(self, org):
        code = InvitationCode.objects.create(
            organization=org, target_role='student', max_uses=5, use_count=3,
        )
        assert code.remaining_uses == 2
