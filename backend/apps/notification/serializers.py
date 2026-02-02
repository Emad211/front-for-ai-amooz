from rest_framework import serializers

from apps.accounts.models import User
from .models import AdminNotification


class AdminNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminNotification
        fields = ['id', 'title', 'message', 'notification_type', 'audience', 'created_at']


class AdminNotificationCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    message = serializers.CharField()
    notification_type = serializers.ChoiceField(
        choices=AdminNotification.NotificationType.choices,
        default=AdminNotification.NotificationType.INFO,
    )
    audience = serializers.ChoiceField(
        choices=AdminNotification.Audience.choices,
        default=AdminNotification.Audience.ALL,
    )


class NotificationRecipientSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    email = serializers.EmailField()
    avatar = serializers.CharField(allow_blank=True, required=False)
    role = serializers.ChoiceField(choices=[('student', 'student'), ('teacher', 'teacher')])


class UserRecipientSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'name', 'email', 'avatar', 'role']

    def get_name(self, obj: User) -> str:
        return (obj.get_full_name() or obj.username or '').strip()

    def get_role(self, obj: User) -> str:
        role = (obj.role or '').lower()
        if role == User.Role.TEACHER.lower():
            return 'teacher'
        return 'student'

    def get_avatar(self, obj: User) -> str:
        value = getattr(obj, 'avatar', None)
        if not value:
            return ''
        try:
            return value.url
        except Exception:
            return str(value)
