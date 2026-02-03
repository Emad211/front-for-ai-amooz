from django.conf import settings
from django.db import models


class AdminNotification(models.Model):
    class Audience(models.TextChoices):
        ALL = 'all', 'All'
        STUDENTS = 'students', 'Students'
        TEACHERS = 'teachers', 'Teachers'

    class NotificationType(models.TextChoices):
        INFO = 'info', 'Info'
        SUCCESS = 'success', 'Success'
        WARNING = 'warning', 'Warning'
        ERROR = 'error', 'Error'
        MESSAGE = 'message', 'Message'
        ALERT = 'alert', 'Alert'

    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=16,
        choices=NotificationType.choices,
        default=NotificationType.INFO,
    )
    audience = models.CharField(
        max_length=16,
        choices=Audience.choices,
        default=Audience.ALL,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='admin_notifications',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['audience', 'created_at']),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.audience})"


class NotificationReadReceipt(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_receipts'
    )
    # This stores identifiers like 'admin-123' or 'announcement-456'
    notification_id = models.CharField(max_length=100)
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'notification_id')
        indexes = [
            models.Index(fields=['user', 'notification_id']),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} read {self.notification_id}"
