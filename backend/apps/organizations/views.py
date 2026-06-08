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

from .models import (
    InvitationCode,
    Organization,
    OrganizationMembership,
    StudyGroup,
    StudyGroupMembership,
    StudyGroupTeacher,
)
from .serializers import (
    InvitationCodeCreateSerializer,
    InvitationCodeSerializer,
    MembershipSerializer,
    MembershipUpdateSerializer,
    OrganizationCreateSerializer,
    OrganizationSerializer,
    RedeemInvitationSerializer,
    StudyGroupSerializer,
    StudyGroupWriteSerializer,
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
        admin_code_value = None
        try:
            with transaction.atomic():
                org_data = dict(ser.validated_data)
                if not org_data.get('owner'):
                    org_data['owner'] = request.user
                org = Organization.objects.create(**org_data)

                # Auto-generate an admin activation code for this org
                try:
                    admin_code = InvitationCode.objects.create(
                        organization=org,
                        target_role=InvitationCode.TargetRole.ADMIN,
                        label='کد فعالسازی مدیر',
                        max_uses=1,
                        created_by=request.user,
                    )
                    admin_code_value = admin_code.code
                except DatabaseError:
                    logger.exception(
                        'Organization created but InvitationCode table/insert failed. '
                        'Run organizations migrations to repair schema drift.'
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
        data['adminActivationCode'] = admin_code_value
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


# ═══════════════════════════════════════════════════════════════════════════
# Study Groups (گروه آموزشی) — cohorts inside an organization
# ═══════════════════════════════════════════════════════════════════════════

def _annotated_study_groups(org_pk):
    """Study-group queryset with student/teacher/class counts annotated."""
    return (
        StudyGroup.objects
        .filter(organization_id=org_pk)
        .annotate(
            _student_count=Count(
                'student_memberships',
                filter=Q(student_memberships__status=StudyGroupMembership.Status.ACTIVE),
                distinct=True,
            ),
            _teacher_count=Count('teacher_links', distinct=True),
            _class_count=Count('classes', distinct=True),
        )
        .order_by('-created_at')
    )


class StudyGroupListCreateView(APIView):
    """GET: list an org's study groups. POST: create one (org admin)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, org_pk):
        if not (request.user.is_staff or IsOrgAdmin.check(request.user, org_pk)):
            return Response({'detail': 'دسترسی ندارید.'}, status=status.HTTP_403_FORBIDDEN)

        qs = _annotated_study_groups(org_pk)
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        search = request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(subject__icontains=search))
        return Response(StudyGroupSerializer(qs, many=True).data)

    def post(self, request, org_pk):
        if not (request.user.is_staff or IsOrgAdmin.check(request.user, org_pk)):
            return Response({'detail': 'دسترسی ندارید.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            org = Organization.objects.get(pk=org_pk)
        except Organization.DoesNotExist:
            return Response({'detail': 'سازمان یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        ser = StudyGroupWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        if StudyGroup.objects.filter(organization=org, name=d['name']).exists():
            return Response(
                {'detail': 'گروهی با این نام در سازمان وجود دارد.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        group = StudyGroup.objects.create(
            organization=org,
            name=d['name'],
            grade_label=d.get('grade_label', ''),
            subject=d.get('subject', ''),
            description=d.get('description', ''),
            status=d.get('status', StudyGroup.Status.ACTIVE),
            created_by=request.user,
        )
        group = _annotated_study_groups(org_pk).get(pk=group.pk)
        return Response(StudyGroupSerializer(group).data, status=status.HTTP_201_CREATED)


class StudyGroupDetailView(APIView):
    """GET (with roster + courses) / PATCH / DELETE a study group."""

    permission_classes = [IsAuthenticated]

    def _get_group(self, org_pk, group_pk):
        return _annotated_study_groups(org_pk).get(pk=group_pk)

    def get(self, request, org_pk, group_pk):
        try:
            group = self._get_group(org_pk, group_pk)
        except StudyGroup.DoesNotExist:
            return Response({'detail': 'گروه یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        is_admin = request.user.is_staff or IsOrgAdmin.check(request.user, org_pk)
        is_teacher = group.teacher_links.filter(teacher=request.user).exists()
        if not (is_admin or is_teacher):
            return Response({'detail': 'دسترسی ندارید.'}, status=status.HTTP_403_FORBIDDEN)

        data = StudyGroupSerializer(group).data
        students = (
            group.student_memberships
            .select_related('student')
            .filter(status=StudyGroupMembership.Status.ACTIVE)
            .order_by('-joined_at')
        )
        data['students'] = [
            {
                'membershipId': m.id,
                'id': m.student_id,
                'name': m.student.get_full_name() or m.student.username,
                'phone': getattr(m.student, 'phone', '') or '',
                'joinedAt': m.joined_at,
            }
            for m in students
        ]
        courses = group.classes.select_related('teacher').order_by('-created_at')[:100]
        data['courses'] = [
            {
                'id': c.id,
                'title': c.title,
                'teacherId': c.teacher_id,
                'teacherName': (c.teacher.get_full_name() or c.teacher.username) if c.teacher else '',
                'isPublished': bool(getattr(c, 'is_published', False)),
            }
            for c in courses
        ]
        return Response(data)

    def patch(self, request, org_pk, group_pk):
        if not (request.user.is_staff or IsOrgAdmin.check(request.user, org_pk)):
            return Response({'detail': 'دسترسی ندارید.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            group = StudyGroup.objects.get(pk=group_pk, organization_id=org_pk)
        except StudyGroup.DoesNotExist:
            return Response({'detail': 'گروه یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        new_name = request.data.get('name')
        if new_name and new_name != group.name:
            if StudyGroup.objects.filter(
                organization_id=org_pk, name=new_name,
            ).exclude(pk=group_pk).exists():
                return Response(
                    {'detail': 'گروهی با این نام در سازمان وجود دارد.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        for field in ['name', 'grade_label', 'subject', 'description', 'status']:
            if field in request.data:
                setattr(group, field, request.data[field])
        group.save()
        group = self._get_group(org_pk, group_pk)
        return Response(StudyGroupSerializer(group).data)

    def delete(self, request, org_pk, group_pk):
        if not (request.user.is_staff or IsOrgAdmin.check(request.user, org_pk)):
            return Response({'detail': 'دسترسی ندارید.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            group = StudyGroup.objects.get(pk=group_pk, organization_id=org_pk)
        except StudyGroup.DoesNotExist:
            return Response({'detail': 'گروه یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)
        group.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class StudyGroupTeacherView(APIView):
    """POST: assign a teacher to a group. DELETE: unassign (org admin)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, org_pk, group_pk):
        if not (request.user.is_staff or IsOrgAdmin.check(request.user, org_pk)):
            return Response({'detail': 'دسترسی ندارید.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            group = StudyGroup.objects.get(pk=group_pk, organization_id=org_pk)
        except StudyGroup.DoesNotExist:
            return Response({'detail': 'گروه یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        user_id = request.data.get('user_id')
        if not user_id:
            return Response({'detail': 'شناسه معلم لازم است.'}, status=status.HTTP_400_BAD_REQUEST)

        membership = OrganizationMembership.objects.filter(
            organization_id=org_pk,
            user_id=user_id,
            status=OrganizationMembership.MemberStatus.ACTIVE,
        ).first()
        if not membership:
            return Response(
                {'detail': 'این کاربر عضو فعال سازمان نیست.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if membership.org_role not in (
            OrganizationMembership.OrgRole.TEACHER,
            OrganizationMembership.OrgRole.DEPUTY,
            OrganizationMembership.OrgRole.ADMIN,
        ):
            return Response(
                {'detail': 'فقط معلمان سازمان قابل تخصیص به گروه هستند.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        StudyGroupTeacher.objects.get_or_create(
            study_group=group, teacher_id=user_id,
            defaults={'assigned_by': request.user},
        )
        group = _annotated_study_groups(org_pk).get(pk=group_pk)
        return Response(StudyGroupSerializer(group).data, status=status.HTTP_200_OK)

    def delete(self, request, org_pk, group_pk, user_id):
        if not (request.user.is_staff or IsOrgAdmin.check(request.user, org_pk)):
            return Response({'detail': 'دسترسی ندارید.'}, status=status.HTTP_403_FORBIDDEN)
        StudyGroupTeacher.objects.filter(
            study_group_id=group_pk,
            study_group__organization_id=org_pk,
            teacher_id=user_id,
        ).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class StudyGroupStudentView(APIView):
    """POST: add a student to a group. DELETE: remove (org admin)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, org_pk, group_pk):
        if not (request.user.is_staff or IsOrgAdmin.check(request.user, org_pk)):
            return Response({'detail': 'دسترسی ندارید.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            group = StudyGroup.objects.get(pk=group_pk, organization_id=org_pk)
        except StudyGroup.DoesNotExist:
            return Response({'detail': 'گروه یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        user_id = request.data.get('user_id')
        if not user_id:
            return Response({'detail': 'شناسه دانش‌آموز لازم است.'}, status=status.HTTP_400_BAD_REQUEST)

        membership = OrganizationMembership.objects.filter(
            organization_id=org_pk,
            user_id=user_id,
            status=OrganizationMembership.MemberStatus.ACTIVE,
        ).first()
        if not membership:
            return Response(
                {'detail': 'این کاربر عضو فعال سازمان نیست.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if membership.org_role != OrganizationMembership.OrgRole.STUDENT:
            return Response(
                {'detail': 'فقط دانش‌آموزان سازمان قابل افزودن به گروه هستند.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        StudyGroupMembership.objects.get_or_create(
            study_group=group, student_id=user_id,
            defaults={'added_by': request.user},
        )
        group = _annotated_study_groups(org_pk).get(pk=group_pk)
        return Response(StudyGroupSerializer(group).data, status=status.HTTP_200_OK)

    def delete(self, request, org_pk, group_pk, user_id):
        if not (request.user.is_staff or IsOrgAdmin.check(request.user, org_pk)):
            return Response({'detail': 'دسترسی ندارید.'}, status=status.HTTP_403_FORBIDDEN)
        StudyGroupMembership.objects.filter(
            study_group_id=group_pk,
            study_group__organization_id=org_pk,
            student_id=user_id,
        ).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyStudyGroupsView(APIView):
    """GET: study groups the current user teaches in (org-teacher view)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, org_pk):
        # Must be an active member of the org.
        is_member = OrganizationMembership.objects.filter(
            organization_id=org_pk,
            user=request.user,
            status=OrganizationMembership.MemberStatus.ACTIVE,
        ).exists()
        if not (request.user.is_staff or is_member):
            return Response({'detail': 'دسترسی ندارید.'}, status=status.HTTP_403_FORBIDDEN)

        qs = _annotated_study_groups(org_pk).filter(teacher_links__teacher=request.user)
        return Response(StudyGroupSerializer(qs.distinct(), many=True).data)
