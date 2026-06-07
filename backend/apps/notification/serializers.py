from rest_framework import serializers

from apps.accounts.models import User
from .models import AdminNotification, UserNotificationPreference


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


class TeacherMessageRecipientSerializer(serializers.Serializer):
    """A student the teacher can message (for the recipient picker)."""

    id = serializers.CharField()  # phone (stable key)
    name = serializers.CharField()
    phone = serializers.CharField()
    email = serializers.CharField(allow_blank=True)
    hasAccount = serializers.BooleanField()


class TeacherBroadcastCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    message = serializers.CharField()
    notification_type = serializers.ChoiceField(
        choices=AdminNotification.NotificationType.choices,
        default=AdminNotification.NotificationType.MESSAGE,
    )
    # Either pass explicit recipient phones, or set sendToAll to message every student.
    recipientPhones = serializers.ListField(
        child=serializers.CharField(), required=False, default=list,
    )
    sendToAll = serializers.BooleanField(required=False, default=False)
    sendSms = serializers.BooleanField(required=False, default=False)


class TeacherBroadcastResultSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    message = serializers.CharField()
    type = serializers.CharField()
    recipientCount = serializers.IntegerField()
    smsQueued = serializers.BooleanField()
    createdAt = serializers.CharField()


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """Maps the per-user preference model to the frontend's settings shape."""

    emailNotifications = serializers.BooleanField(source='email_enabled', required=False)
    browserNotifications = serializers.BooleanField(source='browser_enabled', required=False)
    smsNotifications = serializers.BooleanField(source='sms_enabled', required=False)
    marketingEmails = serializers.BooleanField(source='marketing_enabled', required=False)

    class Meta:
        model = UserNotificationPreference
        fields = ['emailNotifications', 'browserNotifications', 'smsNotifications', 'marketingEmails']
