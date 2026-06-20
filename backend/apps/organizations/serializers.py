"""Serializers for the organizations app.

READ serializers output camelCase keys to match the Next.js frontend types.
WRITE (input) serializers keep snake_case to match Django model field names.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from apps.commons.phone_utils import is_valid_iran_mobile, normalize_phone

from .models import (
    InvitationCode,
    Organization,
    OrganizationMembership,
    StudyGroup,
)

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
    """Input for redeeming an invite code.  Accepts snake_case.

    Uniform across ALL roles: redemption is phone-based & passwordless. The code
    + phone create (or re-enter) a passwordless shell for the mapped role; the
    user then sets their real username/password/email in the forced onboarding
    step. (An already-authenticated user redeeming needs no phone.)
    """

    code = serializers.CharField(max_length=64)

    # Phone is the account identity for every anonymous redemption.
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True)

    # Optional display name captured at the code step (also editable in onboarding).
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)

    def validate_phone(self, value: str) -> str:
        """Canonicalize the student phone so it matches every other flow.

        Blank is allowed (account-based codes don't carry a phone). A non-blank
        phone MUST be a valid Iranian mobile — this is what was missing and let
        org-redeemed students diverge from class-login students.
        """
        norm = normalize_phone(value)
        if value and not is_valid_iran_mobile(norm):
            raise serializers.ValidationError('شماره تماس معتبر نیست.')
        return norm

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

        # Check student capacity — but never block someone who is ALREADY a
        # member (a returning student re-entering the org code to log in is not a
        # new seat). New seats are still rejected here (400) and re-checked under
        # the row lock in the view (409).
        if (
            invite.target_role == InvitationCode.TargetRole.STUDENT
            and invite.organization.is_at_capacity
            and not self._is_returning_member(invite.organization)
        ):
            raise serializers.ValidationError('ظرفیت دانش‌آموز سازمان آموزشی تکمیل شده است.')

        return value

    def _is_returning_member(self, organization) -> bool:
        """True if the redeeming party already belongs to this org."""
        request = self.context.get('request') if hasattr(self, 'context') else None
        if request is not None and request.user.is_authenticated:
            return OrganizationMembership.objects.filter(
                user=request.user, organization=organization,
            ).exists()
        phone = normalize_phone(self.initial_data.get('phone'))
        if phone:
            return OrganizationMembership.objects.filter(
                user__phone=phone,
                user__role=User.Role.STUDENT,
                organization=organization,
            ).exists()
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# StudyGroup (گروه آموزشی) — READ
# ═══════════════════════════════════════════════════════════════════════════════

class StudyGroupSerializer(serializers.ModelSerializer):
    """Read-only study group (camelCase). List shape: counts + teacher briefs.

    ``studentCount``/``teacherCount`` read annotated values when present (list
    view annotates them to avoid N+1) and fall back to the model properties.
    ``teachers`` reads the ``teacher_links__teacher`` prefetch cache.
    """

    gradeLabel = serializers.CharField(source='grade_label', read_only=True)
    statusDisplay = serializers.CharField(source='get_status_display', read_only=True)
    studentCount = serializers.SerializerMethodField()
    teacherCount = serializers.SerializerMethodField()
    classCount = serializers.SerializerMethodField()
    teachers = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = StudyGroup
        fields = [
            'id', 'name', 'gradeLabel', 'subject', 'description',
            'status', 'statusDisplay', 'studentCount', 'teacherCount',
            'classCount', 'teachers', 'createdAt',
        ]

    @staticmethod
    def get_studentCount(obj) -> int:  # noqa: N802
        val = getattr(obj, '_student_count', None)
        return val if val is not None else obj.student_count

    @staticmethod
    def get_teacherCount(obj) -> int:  # noqa: N802
        val = getattr(obj, '_teacher_count', None)
        return val if val is not None else obj.teacher_count

    @staticmethod
    def get_classCount(obj) -> int:  # noqa: N802
        val = getattr(obj, '_class_count', None)
        # 'class' is ClassCreationSession.PipelineType.CLASS (avoid a cross-app import).
        return val if val is not None else obj.study_group_sessions.filter(pipeline_type='class').count()

    @staticmethod
    def get_teachers(obj):
        return [
            {'id': link.teacher_id, 'name': link.teacher.get_full_name() or link.teacher.username}
            for link in obj.teacher_links.all()
        ]


class StudyGroupDetailSerializer(StudyGroupSerializer):
    """Detail shape: adds the student roster (reads the prefetch cache)."""

    students = serializers.SerializerMethodField()

    class Meta(StudyGroupSerializer.Meta):
        fields = StudyGroupSerializer.Meta.fields + ['students']

    @staticmethod
    def get_students(obj):
        return [
            {
                'id': m.student_id,
                'name': m.student.get_full_name() or m.student.username,
                'phone': getattr(m.student, 'phone', '') or '',
                'status': m.status,
            }
            for m in obj.student_memberships.all()
        ]


# ═══════════════════════════════════════════════════════════════════════════════
# StudyGroup — WRITE (create / update)
# ═══════════════════════════════════════════════════════════════════════════════

class StudyGroupWriteSerializer(serializers.Serializer):
    """Input for create/update — snake_case (use partial=True for updates)."""

    name = serializers.CharField(max_length=128)
    grade_label = serializers.CharField(max_length=64, required=False, allow_blank=True, default='')
    subject = serializers.CharField(max_length=128, required=False, allow_blank=True, default='')
    description = serializers.CharField(required=False, allow_blank=True, default='')
    status = serializers.ChoiceField(choices=StudyGroup.Status.choices, required=False)
