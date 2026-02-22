"""REST API views for organizations."""

from __future__ import annotations

import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import Count, F, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsPlatformAdmin as IsAdminUser
from rest_framework_simplejwt.tokens import RefreshToken

from apps.classes.models import ClassCreationSession

from .models import InvitationCode, Organization, OrganizationMembership
from .serializers import (
    InvitationCodeCreateSerializer,
    InvitationCodeSerializer,
    MembershipSerializer,
    MembershipUpdateSerializer,
    OrganizationCreateSerializer,
    OrganizationSerializer,
    RedeemInvitationSerializer,
)

User = get_user_model()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Permission helpers
# ---------------------------------------------------------------------------

class IsOrgAdmin:
    """Check the user is admin/deputy of the given org."""

    @staticmethod
    def check(user, org_id: int) -> bool:
        if not user or not user.is_authenticated:
            return False
        return OrganizationMembership.objects.filter(
            user=user,
            organization_id=org_id,
            org_role__in=[
                OrganizationMembership.OrgRole.ADMIN,
                OrganizationMembership.OrgRole.DEPUTY,
            ],
            status=OrganizationMembership.MemberStatus.ACTIVE,
        ).exists()


# ═══════════════════════════════════════════════════════════════════════════
# Platform Admin — Organization CRUD (superuser only)
# ═══════════════════════════════════════════════════════════════════════════

class OrganizationListCreateView(APIView):
    """GET: list all orgs. POST: create a new org (platform admin)."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        qs = (
            Organization.objects
            .select_related('owner')
            .annotate(
                _student_count=Count(
                    'memberships',
                    filter=Q(
                        memberships__org_role=OrganizationMembership.OrgRole.STUDENT,
                        memberships__status=OrganizationMembership.MemberStatus.ACTIVE,
                    ),
                ),
            )
            .all()
        )
        return Response(OrganizationSerializer(qs, many=True).data)

    def post(self, request):
        ser = OrganizationCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        created_codes: list[dict[str, object]] = []
        try:
            with transaction.atomic():
                org_data = dict(ser.validated_data)
                if not org_data.get('owner'):
                    org_data['owner'] = request.user
                org = Organization.objects.create(**org_data)

                initial_code_specs = [
                    {
                        'target_role': InvitationCode.TargetRole.ADMIN,
                        'label': 'کد فعالسازی مدیر',
                        'max_uses': 1,
                    },
                    {
                        'target_role': InvitationCode.TargetRole.DEPUTY,
                        'label': 'کد دعوت معاون',
                        'max_uses': 5,
                    },
                    {
                        'target_role': InvitationCode.TargetRole.TEACHER,
                        'label': 'کد دعوت معلم',
                        'max_uses': 30,
                    },
                    {
                        'target_role': InvitationCode.TargetRole.STUDENT,
                        'label': 'کد دعوت دانش‌آموز',
                        'max_uses': 100,
                    },
                ]

                for spec in initial_code_specs:
                    try:
                        code = InvitationCode.objects.create(
                            organization=org,
                            target_role=spec['target_role'],
                            label=spec['label'],
                            max_uses=spec['max_uses'],
                            created_by=request.user,
                        )
                        created_codes.append(
                            {
                                'targetRole': spec['target_role'],
                                'label': spec['label'],
                                'maxUses': spec['max_uses'],
                                'code': code.code,
                            }
                        )
                    except DatabaseError:
                        logger.exception(
                            'Organization created but InvitationCode insert failed for role=%s. '
                            'Run organizations migrations to repair schema drift.',
                            spec['target_role'],
                        )
        except IntegrityError as exc:
            logger.error('Organization create IntegrityError: %s', exc, exc_info=True)
            return Response(
                {
                    'detail': (
                        'خطای پایگاه داده هنگام ساخت سازمان. '
                        'لطفاً migration جدید organizations را اجرا کنید: '
                        'python manage.py migrate organizations'
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        data = OrganizationSerializer(org).data
        admin_code = next((c for c in created_codes if c.get('targetRole') == InvitationCode.TargetRole.ADMIN), None)
        data['adminActivationCode'] = admin_code.get('code') if admin_code else None
        data['initialInvitationCodes'] = created_codes
        return Response(data, status=status.HTTP_201_CREATED)


class OrganizationDetailView(APIView):
    """GET / PATCH / DELETE a single org (platform admin)."""

    permission_classes = [IsAdminUser]

    def get(self, request, org_pk):
        try:
            org = Organization.objects.select_related('owner').get(pk=org_pk)
        except Organization.DoesNotExist:
            return Response({'detail': 'سازمان یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(OrganizationSerializer(org).data)

    def patch(self, request, org_pk):
        try:
            org = Organization.objects.get(pk=org_pk)
        except Organization.DoesNotExist:
            return Response({'detail': 'سازمان یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        # Validate slug uniqueness if being changed
        new_slug = request.data.get('slug')
        if new_slug and new_slug != org.slug:
            if Organization.objects.filter(slug=new_slug).exclude(pk=org_pk).exists():
                return Response(
                    {'slug': ['این شناسه قبلاً استفاده شده است.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        allowed = ['name', 'slug', 'student_capacity', 'subscription_status',
                    'description', 'phone', 'address']
        for field in allowed:
            if field in request.data:
                setattr(org, field, request.data[field])

        # Handle owner FK separately
        if 'owner' in request.data:
            owner_id = request.data['owner']
            if owner_id is None:
                org.owner = None
            else:
                try:
                    org.owner = User.objects.get(pk=owner_id)
                except User.DoesNotExist:
                    return Response(
                        {'owner': ['کاربر یافت نشد.']},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        org.save()
        return Response(OrganizationSerializer(org).data)

    def delete(self, request, org_pk):
        try:
            org = Organization.objects.get(pk=org_pk)
        except Organization.DoesNotExist:
            return Response({'detail': 'سازمان یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)
        org.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ═══════════════════════════════════════════════════════════════════════════
# Org Admin — Members management
# ═══════════════════════════════════════════════════════════════════════════

class OrgMemberListView(APIView):
    """List members of an organization (org admin/deputy)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, org_pk):
        if not (request.user.is_staff or IsOrgAdmin.check(request.user, org_pk)):
            return Response({'detail': 'دسترسی ندارید.'}, status=status.HTTP_403_FORBIDDEN)

        qs = (
            OrganizationMembership.objects
            .filter(organization_id=org_pk)
            .select_related('user')
            .order_by('org_role', '-joined_at')
        )

        # Optional filters
        role_filter = request.query_params.get('role')
        if role_filter:
            qs = qs.filter(org_role=role_filter)

        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        search = request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(user__username__icontains=search) |
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(internal_id__icontains=search)
            )

        return Response(MembershipSerializer(qs, many=True).data)


class OrgMemberDetailView(APIView):
    """Update or remove a member (org admin)."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, org_pk, membership_pk):
        if not (request.user.is_staff or IsOrgAdmin.check(request.user, org_pk)):
            return Response({'detail': 'دسترسی ندارید.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            membership = OrganizationMembership.objects.get(
                pk=membership_pk, organization_id=org_pk,
            )
        except OrganizationMembership.DoesNotExist:
            return Response({'detail': 'عضو یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        ser = MembershipUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        for field, value in ser.validated_data.items():
            setattr(membership, field, value)
        membership.save()
        return Response(MembershipSerializer(membership).data)

    def delete(self, request, org_pk, membership_pk):
        if not (request.user.is_staff or IsOrgAdmin.check(request.user, org_pk)):
            return Response({'detail': 'دسترسی ندارید.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            membership = OrganizationMembership.objects.get(
                pk=membership_pk, organization_id=org_pk,
            )
        except OrganizationMembership.DoesNotExist:
            return Response({'detail': 'عضو یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        membership.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ═══════════════════════════════════════════════════════════════════════════
# Org Admin — Invitation Codes
# ═══════════════════════════════════════════════════════════════════════════

class OrgInviteCodeListCreateView(APIView):
    """List and create invitation codes for an organization."""

    permission_classes = [IsAuthenticated]

    def get(self, request, org_pk):
        if not (request.user.is_staff or IsOrgAdmin.check(request.user, org_pk)):
            return Response({'detail': 'دسترسی ندارید.'}, status=status.HTTP_403_FORBIDDEN)

        qs = InvitationCode.objects.filter(organization_id=org_pk).order_by('-created_at')
        return Response(InvitationCodeSerializer(qs, many=True).data)

    def post(self, request, org_pk):
        if not (request.user.is_staff or IsOrgAdmin.check(request.user, org_pk)):
            return Response({'detail': 'دسترسی ندارید.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            org = Organization.objects.get(pk=org_pk)
        except Organization.DoesNotExist:
            return Response({'detail': 'سازمان یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        ser = InvitationCodeCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        code_value = (data.get('custom_code') or '').strip().upper()
        if code_value:
            if InvitationCode.objects.filter(code__iexact=code_value).exists():
                return Response(
                    {'detail': 'این کد قبلاً استفاده شده است.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            code_value = None  # Let model default generate it

        invite = InvitationCode(
            organization=org,
            target_role=data['target_role'],
            label=data.get('label', ''),
            max_uses=data.get('max_uses', 30),
            expires_at=data.get('expires_at'),
            created_by=request.user,
        )
        if code_value:
            invite.code = code_value
        invite.save()

        return Response(
            InvitationCodeSerializer(invite).data,
            status=status.HTTP_201_CREATED,
        )


class OrgInviteCodeDetailView(APIView):
    """Deactivate or delete an invitation code."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, org_pk, code_pk):
        if not (request.user.is_staff or IsOrgAdmin.check(request.user, org_pk)):
            return Response({'detail': 'دسترسی ندارید.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            code = InvitationCode.objects.get(pk=code_pk, organization_id=org_pk)
        except InvitationCode.DoesNotExist:
            return Response({'detail': 'کد یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        if 'is_active' in request.data:
            code.is_active = bool(request.data['is_active'])
        if 'max_uses' in request.data:
            code.max_uses = int(request.data['max_uses'])
        if 'expires_at' in request.data:
            code.expires_at = request.data['expires_at'] or None
        code.save()
        return Response(InvitationCodeSerializer(code).data)

    def delete(self, request, org_pk, code_pk):
        if not (request.user.is_staff or IsOrgAdmin.check(request.user, org_pk)):
            return Response({'detail': 'دسترسی ندارید.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            code = InvitationCode.objects.get(pk=code_pk, organization_id=org_pk)
        except InvitationCode.DoesNotExist:
            return Response({'detail': 'کد یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        code.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ═══════════════════════════════════════════════════════════════════════════
# Public — Redeem Invitation Code (join org or register + join)
# ═══════════════════════════════════════════════════════════════════════════

class RedeemInvitationView(APIView):
    """
    POST: Redeem an invitation code.

    Two modes:
    1) Authenticated user → just joins the org.
    2) Anonymous user with username+password → creates account then joins.
    """

    permission_classes = []  # allow unauthenticated

    @transaction.atomic
    def post(self, request):
        ser = RedeemInvitationSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        code_value = data['code'].strip().upper()
        # Lock the row to prevent race conditions on concurrent redemptions
        try:
            invite = (
                InvitationCode.objects
                .select_related('organization')
                .select_for_update()
                .get(code__iexact=code_value)
            )
        except InvitationCode.DoesNotExist:
            return Response(
                {'detail': 'کد نامعتبر است.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Determine the user
        user = request.user if request.user.is_authenticated else None

        if user is None:
            # Must create a new account
            username = data.get('username')
            password = data.get('password')
            if not username or not password:
                return Response(
                    {'detail': 'برای ثبت‌نام لطفاً نام کاربری و رمز عبور وارد کنید.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if User.objects.filter(username=username).exists():
                return Response(
                    {'detail': 'این نام کاربری قبلاً استفاده شده است.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                validate_password(password)
            except DjangoValidationError as e:
                messages = e.messages if hasattr(e, 'messages') else [str(e)]
                return Response(
                    {'detail': ' '.join(messages)},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Map invitation target_role to platform User.Role
            role_map = {
                InvitationCode.TargetRole.ADMIN: 'ADMIN',
                InvitationCode.TargetRole.DEPUTY: 'TEACHER',
                InvitationCode.TargetRole.TEACHER: 'TEACHER',
                InvitationCode.TargetRole.STUDENT: 'STUDENT',
            }
            platform_role = role_map.get(invite.target_role, 'STUDENT')

            user = User.objects.create_user(
                username=username,
                password=password,
                first_name=data.get('first_name', ''),
                last_name=data.get('last_name', ''),
                role=platform_role,
            )

        # Check if already a member
        if OrganizationMembership.objects.filter(
            user=user, organization=invite.organization,
        ).exists():
            return Response(
                {'detail': 'شما قبلاً عضو این سازمان هستید.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create membership
        OrganizationMembership.objects.create(
            user=user,
            organization=invite.organization,
            org_role=invite.target_role,
        )

        # If admin invite and org has no owner, set this user as owner
        if invite.target_role == InvitationCode.TargetRole.ADMIN and not invite.organization.owner:
            invite.organization.owner = user
            invite.organization.save(update_fields=['owner'])

        # Atomic increment to prevent race conditions
        InvitationCode.objects.filter(pk=invite.pk).update(use_count=F('use_count') + 1)

        # Generate JWT tokens for the new user (anonymous registration)
        token_data = {}
        if not request.user.is_authenticated:
            refresh = RefreshToken.for_user(user)
            token_data = {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }

        role_display = dict(InvitationCode.TargetRole.choices).get(invite.target_role, '')

        return Response({
            'success': True,
            'organization': {
                'id': invite.organization.id,
                'name': invite.organization.name,
                'slug': invite.organization.slug,
            },
            'membership': {
                'orgRole': invite.target_role,
                'orgRoleDisplay': role_display,
            },
            **token_data,
        }, status=status.HTTP_201_CREATED)


# ═══════════════════════════════════════════════════════════════════════════
# Validate Invitation Code (check before form)
# ═══════════════════════════════════════════════════════════════════════════

class ValidateInvitationView(APIView):
    """GET: check if an invite code is valid without consuming it."""

    permission_classes = []

    def get(self, request):
        code_value = (request.query_params.get('code') or '').strip().upper()
        if not code_value:
            return Response(
                {'valid': False, 'detail': 'کد وارد نشده است.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            invite = InvitationCode.objects.select_related('organization').get(
                code__iexact=code_value,
            )
        except InvitationCode.DoesNotExist:
            return Response({'valid': False, 'detail': 'کد نامعتبر است.'})

        if not invite.is_valid:
            return Response({'valid': False, 'detail': 'این کد منقضی یا غیرفعال شده است.'})

        return Response({
            'valid': True,
            'organization': {
                'id': invite.organization.id,
                'name': invite.organization.name,
                'slug': invite.organization.slug,
                'logo': invite.organization.logo.url if invite.organization.logo else None,
            },
            'targetRole': invite.target_role,
            'targetRoleDisplay': dict(InvitationCode.TargetRole.choices).get(invite.target_role, ''),
            'remainingUses': invite.remaining_uses,
            'needsRegistration': not request.user.is_authenticated,
        })


# ═══════════════════════════════════════════════════════════════════════════
# Workspace Switching (for authenticated users)
# ═══════════════════════════════════════════════════════════════════════════

class MyWorkspacesView(APIView):
    """Return the list of organizations the current user belongs to."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        memberships = (
            OrganizationMembership.objects
            .filter(
                user=request.user,
                status=OrganizationMembership.MemberStatus.ACTIVE,
                organization__subscription_status=Organization.SubscriptionStatus.ACTIVE,
            )
            .select_related('organization')
            .order_by('organization__name')
        )

        workspaces = [
            {
                'id': m.organization.id,
                'name': m.organization.name,
                'slug': m.organization.slug,
                'logo': m.organization.logo.url if m.organization.logo else None,
                'orgRole': m.org_role,
                'orgRoleDisplay': m.get_org_role_display(),
            }
            for m in memberships
        ]

        return Response(workspaces)


# ═══════════════════════════════════════════════════════════════════════════
# Org Dashboard — Stats for org admin
# ═══════════════════════════════════════════════════════════════════════════

class OrgDashboardView(APIView):
    """Stats for the org admin dashboard."""

    permission_classes = [IsAuthenticated]

    def get(self, request, org_pk):
        if not (request.user.is_staff or IsOrgAdmin.check(request.user, org_pk)):
            return Response({'detail': 'دسترسی ندارید.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            org = Organization.objects.get(pk=org_pk)
        except Organization.DoesNotExist:
            return Response({'detail': 'سازمان یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        memberships = org.memberships.all()
        students = memberships.filter(
            org_role=OrganizationMembership.OrgRole.STUDENT,
            status=OrganizationMembership.MemberStatus.ACTIVE,
        ).count()
        teachers = memberships.filter(
            org_role=OrganizationMembership.OrgRole.TEACHER,
            status=OrganizationMembership.MemberStatus.ACTIVE,
        ).count()
        total_members = memberships.filter(
            status=OrganizationMembership.MemberStatus.ACTIVE,
        ).count()

        # Classes belonging to this org
        org_classes = ClassCreationSession.objects.filter(organization_id=org_pk)
        total_classes = org_classes.count()
        published_classes = org_classes.filter(is_published=True).count()

        # Active invite codes
        active_codes = InvitationCode.objects.filter(
            organization=org, is_active=True,
        ).count()

        return Response({
            'organization': OrganizationSerializer(org).data,
            'stats': {
                'totalMembers': total_members,
                'students': students,
                'teachers': teachers,
                'studentCapacity': org.student_capacity,
                'totalClasses': total_classes,
                'publishedClasses': published_classes,
                'activeInviteCodes': active_codes,
            },
        })
