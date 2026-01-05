from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

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
    role = serializers.ChoiceField(
        choices=[(User.Role.STUDENT, 'Student'), (User.Role.TEACHER, 'Teacher')],
        required=False,
        help_text="User role: 'student' or 'teacher'. Defaults to 'student'."
    )

    def validate_username(self, value: str) -> str:
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('Username already exists.')
        return value

    def validate_email(self, value: str) -> str:
        if not value:
            return value
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Email already exists.')
        return value

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value

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
