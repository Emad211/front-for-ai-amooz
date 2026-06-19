"""Serializers for the public waitlist intake."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import AccessRequest

User = get_user_model()


def normalize_iran_phone(raw: str) -> str:
    """Normalize an Iranian mobile number to the canonical 09XXXXXXXXX form.

    Mirrors the logic in ``authentication.InviteCodeLoginSerializer`` so the
    waitlist stores phones in the same shape the rest of the platform uses.
    """
    digits = ''.join(ch for ch in str(raw or '') if ch.isdigit())
    if digits.startswith('98') and len(digits) == 12:
        digits = '0' + digits[2:]
    if len(digits) == 10 and digits.startswith('9'):
        digits = '0' + digits
    return digits


class AccessRequestCreateSerializer(serializers.ModelSerializer):
    """Public intake. ``kind`` drives which extra fields are required."""

    # Accept messier raw input (spaces, +98, dashes) than the model's 15-char
    # column — we normalize to the canonical 11-digit form in validate_phone.
    phone = serializers.CharField(max_length=32)

    class Meta:
        model = AccessRequest
        fields = [
            'id', 'kind', 'full_name', 'phone', 'email',
            'expertise',
            'org_name', 'city', 'expected_students', 'website',
            'note',
        ]
        read_only_fields = ['id']

    def validate_kind(self, value: str) -> str:
        if value not in AccessRequest.Kind.values:
            raise serializers.ValidationError('نوع درخواست نامعتبر است.')
        return value

    def validate_full_name(self, value: str) -> str:
        v = (value or '').strip()
        if len(v) < 3:
            raise serializers.ValidationError('نام و نام خانوادگی را کامل وارد کنید.')
        return v

    def validate_phone(self, value: str) -> str:
        digits = normalize_iran_phone(value)
        if not digits.startswith('09') or len(digits) != 11:
            raise serializers.ValidationError('شماره تماس معتبر نیست.')
        return digits

    def validate(self, attrs):
        kind = attrs.get('kind')

        # Organization requests must name the organization.
        if kind == AccessRequest.Kind.ORGANIZATION:
            if not (attrs.get('org_name') or '').strip():
                raise serializers.ValidationError({'org_name': ['نام سازمان آموزشی الزامی است.']})

        # Dedup: one open (pending/contacted) request per phone+kind. After a
        # decision (approved/rejected) they may apply again.
        phone = attrs.get('phone')
        if phone and AccessRequest.objects.filter(
            kind=kind,
            phone=phone,
            status__in=[AccessRequest.Status.PENDING, AccessRequest.Status.CONTACTED],
        ).exists():
            raise serializers.ValidationError(
                'یک درخواست با این شماره تماس از قبل ثبت شده و در حال بررسی است.'
            )

        return attrs


class AccessRequestAdminSerializer(serializers.ModelSerializer):
    """Full read representation for the admin review panel."""

    kind_display = serializers.CharField(source='get_kind_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reviewed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = AccessRequest
        fields = [
            'id', 'kind', 'kind_display', 'full_name', 'phone', 'email', 'expertise',
            'org_name', 'city', 'expected_students', 'website', 'note',
            'status', 'status_display', 'admin_note', 'reject_reason',
            'reviewed_by_name', 'reviewed_at', 'registration_token',
            'created_user', 'created_organization', 'created_at', 'updated_at',
        ]
        read_only_fields = fields

    @staticmethod
    def get_reviewed_by_name(obj):
        u = obj.reviewed_by
        if not u:
            return None
        return u.get_full_name() or u.username


class AccessRequestRejectSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=255)


class TeacherRegistrationCompleteSerializer(serializers.Serializer):
    """An approved teacher completes registration with their one-time token."""

    token = serializers.CharField()
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)

    def validate_username(self, value: str) -> str:
        v = (value or '').strip()
        if len(v) < 3:
            raise serializers.ValidationError('نام کاربری باید حداقل ۳ کاراکتر باشد.')
        if User.objects.filter(username=v).exists():
            raise serializers.ValidationError('این نام کاربری قبلاً استفاده شده است.')
        return v

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value
