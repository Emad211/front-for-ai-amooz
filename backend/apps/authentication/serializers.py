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
        password = attrs.get('password', '')

        if email and User.objects.filter(email__iexact=email, role=role).exists():
            raise serializers.ValidationError({
                'email': ['برای این نقش، این ایمیل قبلاً ثبت شده است.'],
            })

        # Prevent same email + same password across different roles.
        # When multiple accounts share an email, the login endpoint can
        # only reliably distinguish them when their passwords differ.
        if email and password:
            other_accounts = User.objects.filter(email__iexact=email).exclude(role=role)
            for other in other_accounts:
                if other.check_password(password):
                    raise serializers.ValidationError({
                        'password': [
                            'این رمز عبور قبلاً برای ایمیلی مشابه در نقش دیگری استفاده شده. '
                            'لطفاً رمز عبور متفاوتی انتخاب کنید.'
                        ],
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

    An optional ``role`` field lets the caller specify which account to
    authenticate when multiple accounts share the same email.  When
    omitted the old admin-priority logic is used.
    """

    role = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, attrs):
        identifier = attrs.get(self.username_field)
        password = attrs.get('password')
        request = self.context.get('request')
        requested_role = (attrs.pop('role', '') or '').upper().strip()

        if identifier and isinstance(identifier, str) and '@' in identifier:
            matches = User.objects.filter(email__iexact=identifier).order_by('id')

            authenticated_users: list[User] = []
            if password:
                for candidate in matches:
                    authed = authenticate(
                        request=request,
                        username=getattr(candidate, User.USERNAME_FIELD),
                        password=password,
                    )
                    if authed is not None:
                        authenticated_users.append(candidate)

            if authenticated_users:
                selected_user = None

                # When the caller explicitly asks for a role, prefer that.
                if requested_role:
                    selected_user = next(
                        (u for u in authenticated_users if u.role == requested_role),
                        None,
                    )
                    # Also match superuser/staff when ADMIN is requested.
                    if not selected_user and requested_role == User.Role.ADMIN:
                        selected_user = next(
                            (
                                u for u in authenticated_users
                                if u.is_superuser or u.is_staff
                            ),
                            None,
                        )

                # Fallback: admin-priority heuristic for backwards compat.
                if not selected_user:
                    admin_like = next(
                        (
                            user
                            for user in authenticated_users
                            if bool(getattr(user, 'is_superuser', False))
                            or bool(getattr(user, 'is_staff', False))
                            or getattr(user, 'role', None) == User.Role.ADMIN
                        ),
                        None,
                    )
                    selected_user = admin_like or authenticated_users[0]

                attrs[self.username_field] = getattr(selected_user, User.USERNAME_FIELD)
            else:
                user = matches.first()
                if user is not None:
                    attrs[self.username_field] = getattr(user, User.USERNAME_FIELD)

        return super().validate(attrs)
