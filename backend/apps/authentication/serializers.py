from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(
        max_length=150,
        help_text="Unique username for the account."
    )
    first_name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=150,
        help_text="User's full name or first name."
    )
    last_name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=150,
        help_text="User's last name (optional)."
    )
    email = serializers.EmailField(
        required=False, 
        allow_blank=True,
        help_text="Optional email address."
    )
    phone = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=15,
        help_text="Optional phone number."
    )
    password = serializers.CharField(
        write_only=True, 
        min_length=8,
        help_text="Strong password (min 8 characters)."
    )
    role = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="User role: 'STUDENT' or 'TEACHER'. Defaults to 'STUDENT'. Case-insensitive."
    )

    _VALID_ROLES = {User.Role.STUDENT, User.Role.TEACHER}

    def validate_role(self, value: str) -> str:
        """Accept role in any case (e.g. 'teacher' -> 'TEACHER')."""
        if not value:
            return User.Role.STUDENT
        upper = value.upper()
        if upper not in self._VALID_ROLES:
            raise serializers.ValidationError(
                f"Invalid role '{value}'. Must be one of: {', '.join(sorted(self._VALID_ROLES))}"
            )
        return upper

    def validate_username(self, value: str) -> str:
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('Username already exists.')
        return value

    def validate_email(self, value: str) -> str:
        if not value:
            return value
        return value

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value

    def validate(self, attrs):
        email = (attrs.get('email') or '').strip()
        role = attrs.get('role') or User.Role.STUDENT

        if email and User.objects.filter(email__iexact=email, role=role).exists():
            raise serializers.ValidationError({
                'email': ['برای این نقش، این ایمیل قبلاً ثبت شده است.'],
            })

        return attrs

    def create(self, validated_data):
        role = validated_data.get('role') or User.Role.STUDENT
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email') or '',
            password=validated_data['password'],
            role=role,
            first_name=validated_data.get('first_name') or '',
            last_name=validated_data.get('last_name') or '',
        )
        phone = (validated_data.get('phone') or '').strip()
        if phone:
            user.phone = phone
            user.save(update_fields=['phone'])
        return user


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(help_text="The refresh token to be blacklisted.")


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(
        required=True,
        help_text="Current password of the user."
    )
    new_password = serializers.CharField(
        required=True, 
        min_length=8,
        help_text="New strong password."
    )

    def validate_new_password(self, value):
        validate_password(value)
        return value


class InviteCodeLoginSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=64)
    phone = serializers.CharField(max_length=32)

    def _normalize_phone(self, raw: str) -> str:
        digits = ''.join(ch for ch in str(raw or '') if ch.isdigit())
        if digits.startswith('98') and len(digits) == 12:
            digits = '0' + digits[2:]
        if len(digits) == 10 and digits.startswith('9'):
            digits = '0' + digits
        return digits

    def validate_code(self, value: str) -> str:
        s = (value or '').strip()
        if not s:
            raise serializers.ValidationError('کد دعوت الزامی است.')
        return s

    def validate_phone(self, value: str) -> str:
        digits = self._normalize_phone(value)
        if not digits.startswith('09') or len(digits) != 11:
            raise serializers.ValidationError('شماره تماس معتبر نیست.')
        return digits


class TokenObtainPairByIdentifierSerializer(TokenObtainPairSerializer):
    """Allow SimpleJWT login with either username or email.

    Keeps the request payload compatible with the default SimpleJWT contract:
    {"username": "...", "password": "..."}
    """

    def validate(self, attrs):
        identifier = attrs.get(self.username_field)
        password = attrs.get('password')
        request = self.context.get('request')

        if identifier and isinstance(identifier, str) and '@' in identifier:
            matches = User.objects.filter(email__iexact=identifier).order_by('id')

            authenticated_user = None
            if password:
                for candidate in matches:
                    authed = authenticate(
                        request=request,
                        username=getattr(candidate, User.USERNAME_FIELD),
                        password=password,
                    )
                    if authed is not None:
                        authenticated_user = candidate
                        break

            if authenticated_user is not None:
                attrs[self.username_field] = getattr(authenticated_user, User.USERNAME_FIELD)
            else:
                user = matches.first()
                if user is not None:
                    attrs[self.username_field] = getattr(user, User.USERNAME_FIELD)

        return super().validate(attrs)
