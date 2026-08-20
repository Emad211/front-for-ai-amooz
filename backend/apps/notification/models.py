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
    # This stores identifiers like 'admin-123', 'announcement-456' or 'teacher-789'
    notification_id = models.CharField(max_length=100)
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'notification_id')
        indexes = [
            models.Index(fields=['user', 'notification_id']),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} read {self.notification_id}"


class TeacherNotification(models.Model):
    """A message a teacher broadcasts to their OWN students.

    Mirrors ``AdminNotification`` but is teacher-scoped: recipients are explicit
    phone numbers (each must be a student of the sending teacher) stored in
    ``TeacherNotificationRecipient``. Surfaced in the student feed with the id
    ``teacher-<id>`` and read-tracked via ``NotificationReadReceipt``.
    """

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='teacher_notifications',
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=16,
        choices=AdminNotification.NotificationType.choices,
        default=AdminNotification.NotificationType.MESSAGE,
    )
    sms_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['teacher', 'created_at']),
        ]

    def __str__(self) -> str:
        return f"{self.title} (teacher={self.teacher_id})"


class TeacherNotificationRecipient(models.Model):
    notification = models.ForeignKey(
        TeacherNotification,
        on_delete=models.CASCADE,
        related_name='recipients',
    )
    phone = models.CharField(max_length=32, db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['notification', 'phone'],
                name='uniq_teacher_notif_recipient',
            ),
        ]
        indexes = [
            models.Index(fields=['phone']),
        ]

    def __str__(self) -> str:
        return f"{self.notification_id}:{self.phone}"


class DirectNotification(models.Model):
    """A notification addressed to ONE specific user, regardless of role.

    ``AdminNotification`` fans out to an audience and ``TeacherNotification``
    targets a teacher's own students by phone; neither can carry a message from a
    third app to a single arbitrary account. This model closes that gap and is the
    seam other apps use to reach the student feed: they call
    ``services.notify_user`` rather than importing this model, and the row surfaces
    in the student feed with the id ``direct-<id>``, read-tracked through the same
    ``NotificationReadReceipt`` as every other source.

    ``source`` records the origin (e.g. ``'advisory'``) for support and cleanup; it
    is provenance only and never gates delivery. ``link`` is an in-app relative
    path the feed item points at — never an external URL or any credential.
    """

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='direct_notifications',
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=16,
        choices=AdminNotification.NotificationType.choices,
        default=AdminNotification.NotificationType.INFO,
    )
    link = models.CharField(max_length=255, blank=True, default='')
    source = models.CharField(max_length=32, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'created_at']),
        ]

    def __str__(self) -> str:
        return f"{self.title} (to={self.recipient_id})"


class UserNotificationPreference(models.Model):
    """Per-user notification channel preferences (role-agnostic).

    Replaces the previous client-only stub where teacher notification toggles
    never persisted. One row per user, created lazily on first GET/PATCH.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preference',
    )
    email_enabled = models.BooleanField(default=True)
    browser_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=False)
    marketing_enabled = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"prefs({self.user_id})"
