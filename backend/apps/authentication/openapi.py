from rest_framework import serializers

from apps.accounts.serializers import MeSerializer


class TokenPairSerializer(serializers.Serializer):
    access = serializers.CharField(help_text="JWT access token")
    refresh = serializers.CharField(help_text="JWT refresh token")


class RegisterResponseSerializer(serializers.Serializer):
    user = MeSerializer()
    tokens = TokenPairSerializer()


class ErrorDetailSerializer(serializers.Serializer):
    detail = serializers.CharField(help_text="Error message")


class ValidationErrorResponseSerializer(serializers.Serializer):
    detail = serializers.CharField(help_text="Error summary")
    errors = serializers.DictField(
        child=serializers.ListField(child=serializers.CharField()),
        help_text="Field-level validation errors",
    )


class TokenObtainPairRequestSerializer(serializers.Serializer):
    username = serializers.CharField(help_text="Username")
    password = serializers.CharField(help_text="Password")


class TokenObtainPairResponseSerializer(TokenPairSerializer):
    pass


class TokenRefreshRequestSerializer(serializers.Serializer):
    refresh = serializers.CharField(help_text="JWT refresh token")


class TokenRefreshResponseSerializer(serializers.Serializer):
    access = serializers.CharField(help_text="New JWT access token")
    refresh = serializers.CharField(required=False, help_text="New refresh token (if rotation enabled)")


class PasswordChangeResponseSerializer(serializers.Serializer):
    detail = serializers.CharField(help_text="Result message")
