"""REST API views for organizations."""

from __future__ import annotations

import logging
import secrets

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import Count, F, Q, Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsPlatformAdmin as IsAdminUser
from apps.core.throttling import SafeScopedRateThrottle
from apps.authentication.cookies import set_refresh_cookie
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import StudentProfile
from apps.accounts.services import get_or_create_student_by_phone
from apps.classes.models import ClassCreationSession

from .models import (
    InvitationCode,
    Organization,
    OrganizationMembership,
    StudyGroup,
    StudyGroupMembership,
    StudyGroupTeacher,
)
from .services import provision_organization
from .serializers import (
    InvitationCodeCreateSerializer,
    InvitationCodeSerializer,
    MembershipSerializer,
    MembershipUpdateSerializer,
    OrganizationCreateSerializer,
    OrganizationSerializer,
    RedeemInvitationSerializer,
    StudyGroupDetailSerializer,
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
        org_data = dict(ser.validated_data)
        owner = org_data.pop('owner', None) or request.user
        try:
            org, admin_code_value = provision_organization(
                data=org_data, created_by=request.user, owner=owner,
            )
        except IntegrityError as exc:
            logger.error('Organization create IntegrityError: %s', exc, exc_info=True)
            return Response(
                {
                    'detail': (
                        'خطای پایگاه داده هنگام ساخت سازمان آموزشی. '
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
            return Response({'detail': 'سازمان آموزشی یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(OrganizationSerializer(org).data)

    def patch(self, request, org_pk):
        try:
            org = Organization.objects.get(pk=org_pk)
        except Organization.DoesNotExist:
            return Response({'detail': 'سازمان آموزشی یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

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
            return Response({'detail': 'سازمان آموزشی یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)
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
            return Response({'detail': 'سازمان آموزشی یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

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
    throttle_classes = [SafeScopedRateThrottle]
    throttle_scope = 'redeem'

    @transaction.atomic
    def post(self, request):
        ser = RedeemInvitationSerializer(data=request.data, context={'request': request})
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

        # Re-validate UNDER THE LOCK. The serializer's is_valid / capacity checks
        # ran on an UNLOCKED read (ser.is_valid above) before this row was locked,
        # so they are stale: two concurrent redemptions of a max_uses=1 code could
        # both pass them and both create a membership. Now that the row is locked,
        # re-read the authoritative state — a second concurrent request blocks on
        # select_for_update() until the first commits, then observes the
        # incremented use_count here and is rejected. (Prevents e.g. a single-use
        # org-admin code minting two MANAGER accounts.)
        if not invite.is_valid:
            return Response(
                {'detail': 'این کد دیگر معتبر نیست یا به سقف استفاده رسیده است.'},
                status=status.HTTP_409_CONFLICT,
            )

        org = invite.organization
        is_student_code = invite.target_role == InvitationCode.TargetRole.STUDENT
        # Already canonicalized by RedeemInvitationSerializer.validate_phone — same
        # 09XXXXXXXXX shape used by class-invite login, so the two flows converge.
        phone = data.get('phone') or ''

        # Is the redeeming party ALREADY a member? (cheap lookup, no creation) — a
        # returning student re-entering the org code to log in does not consume a
        # new seat, so it must bypass the capacity guard below.
        if request.user.is_authenticated:
            is_returning = OrganizationMembership.objects.filter(
                user=request.user, organization=org,
            ).exists()
        elif is_student_code and phone:
            is_returning = OrganizationMembership.objects.filter(
                user__phone=phone, user__role=User.Role.STUDENT, organization=org,
            ).exists()
        else:
            is_returning = False

        # Capacity guard for a NEW student seat — re-checked under the lock (409),
        # mirroring the serializer's pre-lock 400. Runs BEFORE any account is
        # created so an over-capacity redemption never mints a stray user.
        if is_student_code and not is_returning and org.is_at_capacity:
            return Response(
                {'detail': 'ظرفیت دانش‌آموزان سازمان آموزشی تکمیل است.'},
                status=status.HTTP_409_CONFLICT,
            )

        # ── Resolve / create the user ──
        user = request.user if request.user.is_authenticated else None
        if user is None:
            if is_student_code and phone:
                # Phone-based PASSWORDLESS student onboarding — the SAME helper
                # class-invite login uses (apps.accounts.services), so org-redeemed
                # and class-login students resolve to one STUDENT identity per
                # phone. `phone` is canonical (RedeemInvitationSerializer).
                user, _ = get_or_create_student_by_phone(
                    phone,
                    first_name=data.get('first_name', ''),
                    last_name=data.get('last_name', ''),
                )
            else:
                # Account-based onboarding (admin/deputy/teacher; or a student
                # code redeemed with explicit credentials — back-compat).
                username = data.get('username')
                password = data.get('password')
                if not username or not password:
                    detail = (
                        'برای پیوستن دانش‌آموز، شماره موبایل لازم است.'
                        if is_student_code
                        else 'برای ثبت‌نام لطفاً نام کاربری و رمز عبور وارد کنید.'
                    )
                    return Response({'detail': detail}, status=status.HTTP_400_BAD_REQUEST)

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

                # Map invitation target_role to platform User.Role.
                # An org admin/deputy is a MANAGER — a distinct platform role that
                # manages the organization but does NOT teach (and is NOT a platform
                # ADMIN: no /admin access, no staff powers). Org teachers map to
                # TEACHER, students to STUDENT. (The org-level org_role membership is
                # still created below with the original admin/deputy value.)
                role_map = {
                    InvitationCode.TargetRole.ADMIN: 'MANAGER',
                    InvitationCode.TargetRole.DEPUTY: 'MANAGER',
                    InvitationCode.TargetRole.TEACHER: 'TEACHER',
                    InvitationCode.TargetRole.STUDENT: 'STUDENT',
                }
                platform_role = role_map.get(invite.target_role, 'STUDENT')

                # A brand-new account that joins through an org admin/deputy/teacher
                # code is ORG-ONLY: no personal/freelancer workspace. An EXISTING
                # user redeeming is untouched, so a freelancer who joins an org
                # keeps their personal space and becomes "both".
                org_only = invite.target_role in (
                    InvitationCode.TargetRole.ADMIN,
                    InvitationCode.TargetRole.DEPUTY,
                    InvitationCode.TargetRole.TEACHER,
                )
                user = User.objects.create_user(
                    username=username,
                    password=password,
                    first_name=data.get('first_name', ''),
                    last_name=data.get('last_name', ''),
                    role=platform_role,
                    is_freelancer=not org_only,
                )

        # ── Membership: create, or treat as an idempotent student login ──
        membership = OrganizationMembership.objects.filter(
            user=user, organization=org,
        ).first()
        created = membership is None

        if created:
            OrganizationMembership.objects.create(
                user=user, organization=org, org_role=invite.target_role,
            )
            # If admin invite and org has no owner, set this user as owner
            if invite.target_role == InvitationCode.TargetRole.ADMIN and not org.owner:
                org.owner = user
                org.save(update_fields=['owner'])
            # Atomic increment to prevent race conditions
            InvitationCode.objects.filter(pk=invite.pk).update(use_count=F('use_count') + 1)
        elif not (is_student_code and request.user.is_anonymous):
            # An account user (or authenticated student) re-redeeming is an error.
            # An anonymous phone-student who is already a member falls through to a
            # fresh token below — i.e. the org code doubles as their login.
            return Response(
                {'detail': 'شما قبلاً عضو این سازمان آموزشی هستید.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Generate JWT tokens for anonymous onboarding OR a returning-student login.
        token_data = {}
        if not request.user.is_authenticated:
            refresh = RefreshToken.for_user(user)
            token_data = {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }

        role_display = dict(InvitationCode.TargetRole.choices).get(invite.target_role, '')

        response = Response({
            'success': True,
            'organization': {
                'id': org.id,
                'name': org.name,
                'slug': org.slug,
            },
            'membership': {
                'orgRole': invite.target_role,
                'orgRoleDisplay': role_display,
            },
            **token_data,
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
        set_refresh_cookie(response, token_data.get('refresh'))
        return response


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
            # ``exists: False`` lets the unified code page fall through and try the
            # code as a class-invite code instead of showing an org error.
            return Response({'valid': False, 'exists': False, 'detail': 'کد نامعتبر است.'})

        if not invite.is_valid:
            # The code IS an org code, just unusable — don't treat it as a class code.
            return Response({'valid': False, 'exists': True, 'detail': 'این کد منقضی یا غیرفعال شده است.'})

        return Response({
            'valid': True,
            'exists': True,
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
            return Response({'detail': 'سازمان آموزشی یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

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
# Study Groups (گروه آموزشی) — manager CRUD + teacher/student assignment
# ═══════════════════════════════════════════════════════════════════════════

def _get_org_group(org_pk: int, group_pk: int):
    """Fetch a study group scoped to its organization (or None)."""
    return StudyGroup.objects.filter(organization_id=org_pk, pk=group_pk).first()


def _sync_group_classes(group_id: int) -> None:
    """Best-effort: re-sync the rosters of all classes linked to a study group.

    Lazily imports the classes service to avoid a hard import cycle, and never lets
    a roster hiccup break the membership change that triggered it.
    """
    try:
        from apps.classes.services.org_roster import sync_group_classes
        sync_group_classes(group_id)
    except Exception:
        logger.warning('group class roster sync failed group=%s', group_id, exc_info=True)


def _annotated_groups(org_pk: int):
    """Study groups for an org with member/teacher counts annotated (no N+1)."""
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
            _class_count=Count(
                'study_group_sessions',
                filter=Q(study_group_sessions__pipeline_type='class'),
                distinct=True,
            ),
        )
    )


class StudyGroupListCreateView(APIView):
    """GET: list the org's study groups. POST: create one. (org admin/deputy)"""

    permission_classes = [IsAuthenticated]

    def get(self, request, org_pk):
        if not (request.user.is_staff or IsOrgAdmin.check(request.user, org_pk)):
            return Response({'detail': 'دسترسی ندارید.'}, status=status.HTTP_403_FORBIDDEN)
        groups = _annotated_groups(org_pk).prefetch_related('teacher_links__teacher')
        return Response(StudyGroupSerializer(groups, many=True).data)

    def post(self, request, org_pk):
        if not (request.user.is_staff or IsOrgAdmin.check(request.user, org_pk)):
            return Response({'detail': 'دسترسی ندارید.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            org = Organization.objects.get(pk=org_pk)
        except Organization.DoesNotExist:
            return Response({'detail': 'سازمان آموزشی یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        ser = StudyGroupWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        if StudyGroup.objects.filter(organization=org, name=data['name']).exists():
            return Response(
                {'detail': 'گروهی با این نام در سازمان آموزشی وجود دارد.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        group = StudyGroup.objects.create(
            organization=org,
            name=data['name'],
            grade_label=data.get('grade_label', ''),
            subject=data.get('subject', ''),
            description=data.get('description', ''),
            status=data.get('status', StudyGroup.Status.ACTIVE),
            created_by=request.user,
        )
        return Response(StudyGroupDetailSerializer(group).data, status=status.HTTP_201_CREATED)


class StudyGroupDetailView(APIView):
    """GET / PATCH / DELETE a single study group. (org admin/deputy)"""

    permission_classes = [IsAuthenticated]

    def get(self, request, org_pk, group_pk):
        if not (request.user.is_staff or IsOrgAdmin.check(request.user, org_pk)):
            return Response({'detail': 'دسترسی ندارید.'}, status=status.HTTP_403_FORBIDDEN)
        group = _get_org_group(org_pk, group_pk)
        if not group:
            return Response({'detail': 'گروه یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(StudyGroupDetailSerializer(group).data)

    def patch(self, request, org_pk, group_pk):
        if not (request.user.is_staff or IsOrgAdmin.check(request.user, org_pk)):
            return Response({'detail': 'دسترسی ندارید.'}, status=status.HTTP_403_FORBIDDEN)
        group = _get_org_group(org_pk, group_pk)
        if not group:
            return Response({'detail': 'گروه یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        ser = StudyGroupWriteSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        new_name = data.get('name')
        if (
            new_name and new_name != group.name
            and StudyGroup.objects.filter(organization_id=org_pk, name=new_name).exists()
        ):
            return Response(
                {'detail': 'گروهی با این نام در سازمان آموزشی وجود دارد.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for field, value in data.items():
            setattr(group, field, value)
        group.save()
        return Response(StudyGroupDetailSerializer(group).data)

    def delete(self, request, org_pk, group_pk):
        if not (request.user.is_staff or IsOrgAdmin.check(request.user, org_pk)):
            return Response({'detail': 'دسترسی ندارید.'}, status=status.HTTP_403_FORBIDDEN)
        group = _get_org_group(org_pk, group_pk)
        if not group:
            return Response({'detail': 'گروه یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)
        group.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class StudyGroupTeacherView(APIView):
    """POST: assign an org teacher to the group. DELETE: remove one. (org admin)"""

    permission_classes = [IsAuthenticated]

    def post(self, request, org_pk, group_pk):
        if not (request.user.is_staff or IsOrgAdmin.check(request.user, org_pk)):
            return Response({'detail': 'دسترسی ندارید.'}, status=status.HTTP_403_FORBIDDEN)
        group = _get_org_group(org_pk, group_pk)
        if not group:
            return Response({'detail': 'گروه یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        teacher_id = request.data.get('teacher_id')
        if not OrganizationMembership.objects.filter(
            user_id=teacher_id, organization_id=org_pk,
            org_role=OrganizationMembership.OrgRole.TEACHER,
            status=OrganizationMembership.MemberStatus.ACTIVE,
        ).exists():
            return Response(
                {'detail': 'این کاربر معلمِ فعالِ این سازمان آموزشی نیست.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        StudyGroupTeacher.objects.get_or_create(
            study_group=group, teacher_id=teacher_id,
            defaults={'assigned_by': request.user},
        )
        return Response(StudyGroupDetailSerializer(group).data, status=status.HTTP_201_CREATED)

    def delete(self, request, org_pk, group_pk, user_id):
        if not (request.user.is_staff or IsOrgAdmin.check(request.user, org_pk)):
            return Response({'detail': 'دسترسی ندارید.'}, status=status.HTTP_403_FORBIDDEN)
        group = _get_org_group(org_pk, group_pk)
        if not group:
            return Response({'detail': 'گروه یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)
        StudyGroupTeacher.objects.filter(study_group=group, teacher_id=user_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class StudyGroupStudentView(APIView):
    """POST: add an org student to the group. DELETE: remove one. (org admin)"""

    permission_classes = [IsAuthenticated]

    def post(self, request, org_pk, group_pk):
        if not (request.user.is_staff or IsOrgAdmin.check(request.user, org_pk)):
            return Response({'detail': 'دسترسی ندارید.'}, status=status.HTTP_403_FORBIDDEN)
        group = _get_org_group(org_pk, group_pk)
        if not group:
            return Response({'detail': 'گروه یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        student_id = request.data.get('student_id')
        if not OrganizationMembership.objects.filter(
            user_id=student_id, organization_id=org_pk,
            org_role=OrganizationMembership.OrgRole.STUDENT,
            status=OrganizationMembership.MemberStatus.ACTIVE,
        ).exists():
            return Response(
                {'detail': 'این کاربر دانش‌آموزِ فعالِ این سازمان آموزشی نیست.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        StudyGroupMembership.objects.get_or_create(
            study_group=group, student_id=student_id,
            defaults={'added_by': request.user},
        )
        # Reflect the new roster in every class linked to this group.
        _sync_group_classes(group.id)
        return Response(StudyGroupDetailSerializer(group).data, status=status.HTTP_201_CREATED)

    def delete(self, request, org_pk, group_pk, user_id):
        if not (request.user.is_staff or IsOrgAdmin.check(request.user, org_pk)):
            return Response({'detail': 'دسترسی ندارید.'}, status=status.HTTP_403_FORBIDDEN)
        group = _get_org_group(org_pk, group_pk)
        if not group:
            return Response({'detail': 'گروه یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)
        StudyGroupMembership.objects.filter(study_group=group, student_id=user_id).delete()
        # Drop the removed student from every class linked to this group.
        _sync_group_classes(group.id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyStudyGroupsView(APIView):
    """GET: study groups the current teacher is assigned to in this org.

    Powers the org-teacher (group-centric) dashboard. Any active org member may
    call it; a teacher with no assigned groups simply gets an empty list.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, org_pk):
        if not OrganizationMembership.objects.filter(
            user=request.user, organization_id=org_pk,
            status=OrganizationMembership.MemberStatus.ACTIVE,
        ).exists():
            return Response({'detail': 'دسترسی ندارید.'}, status=status.HTTP_403_FORBIDDEN)

        groups = (
            _annotated_groups(org_pk)
            .filter(teacher_links__teacher=request.user)
            .prefetch_related('teacher_links__teacher', 'student_memberships__student')
            .distinct()
        )
        return Response(StudyGroupDetailSerializer(groups, many=True).data)


# ═══════════════════════════════════════════════════════════════════════════
# Manager oversight: all org classes + AI-cost breakdown (IsOrgAdmin)
# ═══════════════════════════════════════════════════════════════════════════

class OrgClassesView(APIView):
    """GET: every class/exam session in the org (oversight — ALL teachers).

    A manager doesn't create content; this is read-only oversight of what the
    org's teachers have built.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, org_pk):
        if not (request.user.is_staff or IsOrgAdmin.check(request.user, org_pk)):
            return Response({'detail': 'دسترسی ندارید.'}, status=status.HTTP_403_FORBIDDEN)

        sessions = (
            ClassCreationSession.objects
            .filter(organization_id=org_pk)
            .select_related('teacher', 'study_group')
            .annotate(_invites=Count('invites', distinct=True))
            .order_by('-created_at')
        )
        data = [
            {
                'id': s.id,
                'title': s.title,
                'teacherName': (s.teacher.get_full_name() or s.teacher.username) if s.teacher else '',
                'pipelineType': s.pipeline_type,
                'status': s.status,
                'isPublished': s.is_published,
                'studentCount': s._invites,
                'studyGroupName': s.study_group.name if s.study_group else None,
                'createdAt': s.created_at,
            }
            for s in sessions
        ]
        return Response(data)


class OrgCostsView(APIView):
    """GET: org AI-cost breakdown — total + by teacher / class / group / feature.

    Costs attribute via ``LLMUsageLog.session_id`` → the org's class sessions
    (each carries its teacher + study group), so every breakdown is exact. No
    extra schema is needed.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, org_pk):
        if not (request.user.is_staff or IsOrgAdmin.check(request.user, org_pk)):
            return Response({'detail': 'دسترسی ندارید.'}, status=status.HTTP_403_FORBIDDEN)

        from apps.commons.models import LLMUsageLog

        sessions = (
            ClassCreationSession.objects
            .filter(organization_id=org_pk)
            .select_related('teacher', 'study_group')
        )
        session_map = {s.id: s for s in sessions}
        session_ids = list(session_map.keys())

        logs = LLMUsageLog.objects.filter(session_id__in=session_ids)

        def _f(value) -> float:
            return float(value or 0)

        totals = logs.aggregate(
            toman=Sum('estimated_cost_toman'),
            tokens=Sum('total_tokens'),
            calls=Count('id'),
        )

        by_class = []
        teacher_acc: dict = {}
        group_acc: dict = {}
        for row in logs.values('session_id').annotate(
            toman=Sum('estimated_cost_toman'),
            tokens=Sum('total_tokens'),
            calls=Count('id'),
        ):
            s = session_map.get(row['session_id'])
            if not s:
                continue
            toman, tokens, calls = _f(row['toman']), int(row['tokens'] or 0), row['calls']
            by_class.append({
                'sessionId': s.id,
                'title': s.title,
                'teacherName': (s.teacher.get_full_name() or s.teacher.username) if s.teacher else '',
                'studyGroupName': s.study_group.name if s.study_group else None,
                'toman': toman, 'tokens': tokens, 'calls': calls,
            })
            tname = (s.teacher.get_full_name() or s.teacher.username) if s.teacher else 'نامشخص'
            t = teacher_acc.setdefault(s.teacher_id, {'teacherName': tname, 'toman': 0.0, 'tokens': 0, 'calls': 0})
            t['toman'] += toman; t['tokens'] += tokens; t['calls'] += calls
            gname = s.study_group.name if s.study_group else 'بدون گروه'
            g = group_acc.setdefault(s.study_group_id, {'studyGroupName': gname, 'toman': 0.0, 'tokens': 0, 'calls': 0})
            g['toman'] += toman; g['tokens'] += tokens; g['calls'] += calls

        by_feature = [
            {'feature': r['feature'], 'toman': _f(r['toman']), 'tokens': int(r['tokens'] or 0), 'calls': r['calls']}
            for r in logs.values('feature').annotate(
                toman=Sum('estimated_cost_toman'), tokens=Sum('total_tokens'), calls=Count('id'),
            )
        ]

        by_class.sort(key=lambda x: x['toman'], reverse=True)
        by_feature.sort(key=lambda x: x['toman'], reverse=True)

        return Response({
            'total': {
                'toman': _f(totals['toman']),
                'tokens': int(totals['tokens'] or 0),
                'calls': totals['calls'],
            },
            'byTeacher': sorted(teacher_acc.values(), key=lambda x: x['toman'], reverse=True),
            'byClass': by_class,
            'byGroup': sorted(group_acc.values(), key=lambda x: x['toman'], reverse=True),
            'byFeature': by_feature,
        })
