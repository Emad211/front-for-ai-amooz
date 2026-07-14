from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from rest_framework import serializers
import base64
import binascii
import uuid

from drf_spectacular.utils import extend_schema_field
from drf_spectacular.types import OpenApiTypes

from apps.commons.phone_utils import is_valid_iran_mobile, normalize_phone

from .models import AdminProfile, StudentProfile, TeacherProfile


User = get_user_model()


class MeSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True, help_text="Unique ID of the user.")
    username = serializers.CharField(read_only=True, help_text="Username of the user.")
    first_name = serializers.CharField(read_only=True, help_text="First name of the user.")
    last_name = serializers.CharField(read_only=True, help_text="Last name of the user.")
    email = serializers.EmailField(read_only=True, help_text="Email address of the user.")
    phone = serializers.CharField(read_only=True, allow_null=True, help_text="Phone number of the user.")
    avatar = serializers.ImageField(read_only=True, allow_null=True, help_text="Avatar image.")
    role = serializers.CharField(read_only=True, help_text="Role of the user (STUDENT/TEACHER/ADMIN).")
    is_staff = serializers.BooleanField(read_only=True, help_text="Indicates if the user can access admin resources.")
    is_superuser = serializers.BooleanField(read_only=True, help_text="Indicates if the user is a Django superuser.")
    is_profile_completed = serializers.BooleanField(read_only=True, help_text="Indicates if the user has completed their profile.")
    is_freelancer = serializers.BooleanField(read_only=True, help_text="TEACHER only: may use a personal (freelancer) workspace. False = org-only.")

    join_date = serializers.DateTimeField(source='date_joined', read_only=True)
    bio = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()
    grade = serializers.SerializerMethodField()
    major = serializers.SerializerMethodField()
    is_verified = serializers.SerializerMethodField()

    @extend_schema_field(OpenApiTypes.STR)
    def get_bio(self, obj) -> str | None:
        if getattr(obj, 'role', None) == User.Role.STUDENT and hasattr(obj, 'studentprofile'):
            return getattr(obj.studentprofile, 'bio', None)
        if getattr(obj, 'role', None) == User.Role.TEACHER and hasattr(obj, 'teacherprofile'):
            return getattr(obj.teacherprofile, 'bio', None)
        if getattr(obj, 'role', None) == User.Role.ADMIN and hasattr(obj, 'adminprofile'):
            return getattr(obj.adminprofile, 'bio', None)
        return None

    @extend_schema_field(OpenApiTypes.STR)
    def get_location(self, obj) -> str | None:
        if getattr(obj, 'role', None) == User.Role.STUDENT and hasattr(obj, 'studentprofile'):
            return getattr(obj.studentprofile, 'location', None)
        if getattr(obj, 'role', None) == User.Role.TEACHER and hasattr(obj, 'teacherprofile'):
            return getattr(obj.teacherprofile, 'location', None)
        if getattr(obj, 'role', None) == User.Role.ADMIN and hasattr(obj, 'adminprofile'):
            return getattr(obj.adminprofile, 'location', None)
        return None

    @extend_schema_field(OpenApiTypes.STR)
    def get_grade(self, obj) -> str | None:
        if getattr(obj, 'role', None) != User.Role.STUDENT:
            return None
        if not hasattr(obj, 'studentprofile'):
            return None
        grade = getattr(obj.studentprofile, 'grade', None)
        return obj.studentprofile.get_grade_display() if grade else None

    @extend_schema_field(OpenApiTypes.STR)
    def get_major(self, obj) -> str | None:
        if getattr(obj, 'role', None) != User.Role.STUDENT:
            return None
        if not hasattr(obj, 'studentprofile'):
            return None
        major = getattr(obj.studentprofile, 'major', None)
        return obj.studentprofile.get_major_display() if major else None

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_is_verified(self, obj) -> bool:
        if getattr(obj, 'role', None) == User.Role.TEACHER and hasattr(obj, 'teacherprofile'):
            return bool(getattr(obj.teacherprofile, 'verification_status', False))
        return bool(getattr(obj, 'is_profile_completed', False))


class MeUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=15)
    avatar = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    bio = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    location = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    expertise = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    grade = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    major = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def _normalize_student_grade(self, raw: str | None) -> str | None:
        s = (raw or '').strip()
        if not s:
            return None
        mapping = {
            '10': '10',
            '11': '11',
            '12': '12',
            'دهم': '10',
            'یازدهم': '11',
            'دوازدهم': '12',
        }
        return mapping.get(s)

    def _normalize_student_major(self, raw: str | None) -> str | None:
        s = (raw or '').strip()
        if not s:
            return None
        mapping = {
            'math': 'math',
            'science': 'science',
            'humanities': 'humanities',
            'ریاضی فیزیک': 'math',
            'علوم تجربی': 'science',
            'علوم انسانی': 'humanities',
        }
        return mapping.get(s)

    def validate_grade(self, value: str | None) -> str | None:
        user = self.instance
        if not user or getattr(user, 'role', None) != User.Role.STUDENT:
            return None
        normalized = self._normalize_student_grade(value)
        if value and normalized is None:
            raise serializers.ValidationError('پایه تحصیلی نامعتبر است.')
        return normalized

    def validate_major(self, value: str | None) -> str | None:
        user = self.instance
        if not user or getattr(user, 'role', None) != User.Role.STUDENT:
            return None
        normalized = self._normalize_student_major(value)
        if value and normalized is None:
            raise serializers.ValidationError('رشته تحصیلی نامعتبر است.')
        return normalized

    def validate_email(self, value: str) -> str:
        # Allow setting/updating email (including first-time set). Normalize to lowercase.
        email = (value or '').strip()
        return email.lower()

    def validate_phone(self, value: str) -> str | None:
        user = self.instance
        normalized = normalize_phone(value) or None
        if normalized and not is_valid_iran_mobile(normalized):
            raise serializers.ValidationError('شماره موبایل معتبر نیست.')
        if not user:
            return normalized

        # Students must never be able to change their phone number after account
        # creation. Compare on the canonical form so a no-op resubmission of a
        # legacy-formatted number isn't mistaken for a change.
        if getattr(user, 'role', None) == User.Role.STUDENT:
            current = normalize_phone(getattr(user, 'phone', None)) or None
            if normalized != current:
                raise serializers.ValidationError('شماره موبایل قابل تغییر نیست.')
            return current

        return normalized

    def update(self, instance, validated_data):
        user_update_fields: list[str] = []

        for field in ['first_name', 'last_name', 'email', 'phone']:
            if field in validated_data:
                value = validated_data.get(field)
                if field == 'phone':
                    # validate_phone handles student immutability; keep non-students normalized
                    value = (value or '').strip() or None
                if field == 'email':
                    value = (value or '').strip().lower()
                setattr(instance, field, value)
                user_update_fields.append(field)

        # Handle avatar upload/clear only when the client explicitly sent it.
        if 'avatar' in validated_data:
            avatar_data = validated_data.get('avatar')
            if not avatar_data:
                if instance.avatar:
                    instance.avatar.delete(save=False)
                instance.avatar = None
                user_update_fields.append('avatar')
            elif avatar_data.startswith('data:image'):
                try:
                    format, imgstr = avatar_data.split(';base64,')
                    ext = format.split('/')[-1]
                    # Clean up extension (e.g. image/jpeg -> jpg)
                    if ext == 'jpeg': ext = 'jpg'
                    
                    data = ContentFile(
                        base64.b64decode(imgstr), 
                        name=f'avatar_{instance.id}_{uuid.uuid4().hex[:8]}.{ext}'
                    )
                    instance.avatar = data
                    user_update_fields.append('avatar')
                except (ValueError, TypeError, binascii.Error) as exc:
                    raise serializers.ValidationError({'avatar': 'تصویر پروفایل نامعتبر است.'}) from exc

        if user_update_fields:
            instance.save(update_fields=user_update_fields)

        # Profile fields logic
        def update_base_profile(profile, data):
            changed = False
            if 'bio' in data:
                profile.bio = (data.get('bio') or '').strip() or None
                changed = True
            if 'location' in data:
                profile.location = (data.get('location') or '').strip() or None
                changed = True
            return changed

        if getattr(instance, 'role', None) == User.Role.STUDENT:
            profile, _ = StudentProfile.objects.get_or_create(user=instance)
            profile_changed = update_base_profile(profile, validated_data)

            if 'grade' in validated_data:
                profile.grade = self._normalize_student_grade(validated_data.get('grade'))
                profile_changed = True

            if 'major' in validated_data:
                profile.major = self._normalize_student_major(validated_data.get('major'))
                profile_changed = True

            if profile_changed:
                profile.save()

        elif getattr(instance, 'role', None) == User.Role.TEACHER:
            profile, _ = TeacherProfile.objects.get_or_create(user=instance)
            profile_changed = update_base_profile(profile, validated_data)
            
            if 'expertise' in validated_data:
                profile.expertise = (validated_data.get('expertise') or '').strip() or None
                profile_changed = True
                
            if profile_changed:
                profile.save()

        elif getattr(instance, 'role', None) == User.Role.ADMIN:
            profile, _ = AdminProfile.objects.get_or_create(user=instance)
            if update_base_profile(profile, validated_data):
                profile.save()

        return instance


class OnboardingSerializer(serializers.Serializer):
    """Forced post-login onboarding: a code-logged-in user (any role) sets the
    credentials they'll log in with from now on, plus contact + light profile.

    Operates on ``self.instance`` = the authenticated user (a passwordless shell
    created by the invite/redeem flow). Sets username + password + email + phone,
    flips ``is_profile_completed``, and delegates role profile fields to
    :class:`MeUpdateSerializer` (reusing its grade/major normalization).
    """

    username = serializers.CharField(max_length=150, min_length=3)
    password = serializers.CharField(min_length=8, write_only=True)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=32)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    # Light, role-specific profile (optional) — handed to MeUpdateSerializer.
    grade = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    major = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    expertise = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_username(self, value: str) -> str:
        v = (value or '').strip()
        qs = User.objects.filter(username=v)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('این نام کاربری قبلاً استفاده شده است.')
        return v

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value

    def validate_email(self, value: str) -> str:
        return (value or '').strip().lower()

    def validate_phone(self, value: str) -> str:
        norm = normalize_phone(value)
        if not is_valid_iran_mobile(norm):
            raise serializers.ValidationError('شماره موبایل معتبر نیست.')
        user = self.instance
        # A student's phone is their login identity (set at code login) and is
        # immutable; they may only re-confirm it. Non-students set it here.
        if user is not None and getattr(user, 'role', None) == User.Role.STUDENT:
            current = normalize_phone(getattr(user, 'phone', None))
            if current and norm != current:
                raise serializers.ValidationError('شماره موبایل قابل تغییر نیست.')
            return current or norm
        return norm

    def save(self, **kwargs):
        user = self.instance
        vd = self.validated_data
        try:
            with transaction.atomic():
                user.username = vd['username']
                user.set_password(vd['password'])
                user.email = vd['email']
                user.phone = vd['phone'] or None
                user.first_name = vd.get('first_name', '') or ''
                user.last_name = vd.get('last_name', '') or ''
                user.is_profile_completed = True
                user.save()

                # Delegate role profile fields (reuses grade/major normalization).
                profile_fields = {k: vd[k] for k in ('grade', 'major', 'expertise') if k in vd}
                if profile_fields:
                    mu = MeUpdateSerializer(instance=user, data=profile_fields, partial=True)
                    mu.is_valid(raise_exception=True)
                    mu.save()
        except IntegrityError:
            # Lost the username (or student-phone) uniqueness race between the
            # validate check and the save — surface a clean 400, not a 500.
            raise serializers.ValidationError(
                {'username': ['این نام کاربری قبلاً استفاده شده است.']}
            )
        return user
