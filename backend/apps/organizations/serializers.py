"""Serializers for the organizations app.

READ serializers output camelCase keys to match the Next.js frontend types.
WRITE (input) serializers keep snake_case to match Django model field names.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from .models import InvitationCode, Organization, OrganizationMembership

User = get_user_model()


# ═══════════════════════════════════════════════════════════════════════════════
# Organization — READ
# ═══════════════════════════════════════════════════════════════════════════════

class OrganizationSerializer(serializers.ModelSerializer):
    """Read-only representation of an Organization (camelCase output)."""

    studentCapacity = serializers.IntegerField(source='student_capacity', read_only=True)
    subscriptionStatus = serializers.CharField(source='subscription_status', read_only=True)
    currentStudentCount = serializers.SerializerMethodField()
    ownerName = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = Organization
        fields = [
            'id', 'name', 'slug', 'logo', 'studentCapacity',
            'subscriptionStatus', 'owner', 'ownerName',
            'description', 'phone', 'address',
            'currentStudentCount', 'createdAt', 'updatedAt',
        ]

    @staticmethod
    def get_currentStudentCount(obj) -> int:  # noqa: N802
        """Use annotated count if available, else fall back to property."""
        return getattr(obj, '_student_count', obj.current_student_count)

    @staticmethod
    def get_ownerName(obj) -> str:  # noqa: N802
        if obj.owner:
            return obj.owner.get_full_name() or obj.owner.username
        return ''


# ═══════════════════════════════════════════════════════════════════════════════
# Organization — WRITE (create)
# ═══════════════════════════════════════════════════════════════════════════════

class OrganizationCreateSerializer(serializers.ModelSerializer):
    """Input serializer for creating an organization (snake_case input)."""

    class Meta:
        model = Organization
        fields = [
            'name', 'slug', 'student_capacity', 'subscription_status',
            'description', 'phone', 'address',
        ]

    def validate_slug(self, value: str) -> str:
        if Organization.objects.filter(slug=value).exists():
            raise serializers.ValidationError('این شناسه قبلاً استفاده شده است.')
        return value


# ═══════════════════════════════════════════════════════════════════════════════
# Membership — READ
# ═══════════════════════════════════════════════════════════════════════════════

class MembershipSerializer(serializers.ModelSerializer):
    """Read-only representation of a membership (camelCase output)."""

    userId = serializers.IntegerField(source='user.id', read_only=True)
    userName = serializers.SerializerMethodField()
    userEmail = serializers.SerializerMethodField()
    userPhone = serializers.SerializerMethodField()
    orgRole = serializers.CharField(source='org_role', read_only=True)
    orgRoleDisplay = serializers.CharField(source='get_org_role_display', read_only=True)
    internalId = serializers.CharField(source='internal_id', read_only=True)
    statusDisplay = serializers.CharField(source='get_status_display', read_only=True)
    joinedAt = serializers.DateTimeField(source='joined_at', read_only=True)

    class Meta:
        model = OrganizationMembership
        fields = [
            'id', 'userId', 'userName', 'userEmail', 'userPhone',
            'orgRole', 'orgRoleDisplay', 'internalId',
            'status', 'statusDisplay', 'joinedAt',
        ]

    @staticmethod
    def get_userName(obj) -> str:  # noqa: N802
        return obj.user.get_full_name() or obj.user.username

    @staticmethod
    def get_userEmail(obj) -> str:  # noqa: N802
        return obj.user.email or ''

    @staticmethod
    def get_userPhone(obj) -> str:  # noqa: N802
        return getattr(obj.user, 'phone', '') or ''


# ═══════════════════════════════════════════════════════════════════════════════
# Membership — WRITE (update role / status / internal_id)
# ═══════════════════════════════════════════════════════════════════════════════

class MembershipUpdateSerializer(serializers.Serializer):
    """Input serializer — accepts snake_case from frontend."""

    org_role = serializers.ChoiceField(
        choices=OrganizationMembership.OrgRole.choices, required=False,
    )
    status = serializers.ChoiceField(
        choices=OrganizationMembership.MemberStatus.choices, required=False,
    )
    internal_id = serializers.CharField(max_length=64, required=False, allow_blank=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Invitation Code — READ
# ═══════════════════════════════════════════════════════════════════════════════

class InvitationCodeSerializer(serializers.ModelSerializer):
    """Read-only representation of an invitation code (camelCase output)."""

    targetRole = serializers.CharField(source='target_role', read_only=True)
    targetRoleDisplay = serializers.CharField(source='get_target_role_display', read_only=True)
    organizationName = serializers.CharField(source='organization.name', read_only=True)
    maxUses = serializers.IntegerField(source='max_uses', read_only=True)
    useCount = serializers.IntegerField(source='use_count', read_only=True)
    remainingUses = serializers.IntegerField(source='remaining_uses', read_only=True)
    isValid = serializers.BooleanField(source='is_valid', read_only=True)
    isActive = serializers.BooleanField(source='is_active', read_only=True)
    expiresAt = serializers.DateTimeField(source='expires_at', read_only=True, allow_null=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = InvitationCode
        fields = [
            'id', 'code', 'organization', 'organizationName',
            'targetRole', 'targetRoleDisplay', 'label',
            'maxUses', 'useCount', 'remainingUses', 'isValid',
            'expiresAt', 'isActive', 'createdAt',
        ]


# ═══════════════════════════════════════════════════════════════════════════════
# Invitation Code — WRITE (create)
# ═══════════════════════════════════════════════════════════════════════════════

class InvitationCodeCreateSerializer(serializers.Serializer):
    """Input serializer — accepts snake_case from frontend."""

    target_role = serializers.ChoiceField(choices=InvitationCode.TargetRole.choices)
    label = serializers.CharField(max_length=128, required=False, allow_blank=True, default='')
    max_uses = serializers.IntegerField(min_value=1, default=30)
    expires_at = serializers.DateTimeField(required=False, allow_null=True, default=None)
    custom_code = serializers.CharField(max_length=64, required=False, allow_blank=True, default='')


# ═══════════════════════════════════════════════════════════════════════════════
# Invitation Code Redemption (join org)
# ═══════════════════════════════════════════════════════════════════════════════

class RedeemInvitationSerializer(serializers.Serializer):
    """Input for redeeming an invite code.  Accepts snake_case."""

    code = serializers.CharField(max_length=64)

    # Optional: for new user registration during redemption
    username = serializers.CharField(max_length=150, required=False)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    password = serializers.CharField(min_length=8, write_only=True, required=False)

    def validate_code(self, value: str) -> str:
        value = value.strip().upper()
        try:
            invite = InvitationCode.objects.select_related('organization').get(
                code__iexact=value,
            )
        except InvitationCode.DoesNotExist:
            raise serializers.ValidationError('کد دعوت نامعتبر است.')

        if not invite.is_valid:
            if invite.use_count >= invite.max_uses:
                raise serializers.ValidationError('ظرفیت این کد تمام شده است.')
            if invite.expires_at and timezone.now() > invite.expires_at:
                raise serializers.ValidationError('این کد منقضی شده است.')
            raise serializers.ValidationError('این کد غیرفعال است.')

        # Check student capacity
        if invite.target_role == InvitationCode.TargetRole.STUDENT:
            if invite.organization.is_at_capacity:
                raise serializers.ValidationError('ظرفیت دانش‌آموز سازمان تکمیل شده است.')

        return value
