from django.urls import path

from .views import (
    AdminNotificationBroadcastView,
    AdminNotificationRecipientsView,
    NotificationPreferencesView,
    TeacherMessageRecipientsView,
    TeacherNotificationBroadcastView,
    TeacherNotificationListView,
    MarkNotificationReadView,
    MarkAllNotificationsReadView,
)

urlpatterns = [
    path('admin/broadcast/', AdminNotificationBroadcastView.as_view(), name='admin_notifications_broadcast'),
    path('admin/recipients/', AdminNotificationRecipientsView.as_view(), name='admin_notifications_recipients'),
    path('teacher/broadcast/', TeacherNotificationBroadcastView.as_view(), name='teacher_notifications_broadcast'),
    path('teacher/recipients/', TeacherMessageRecipientsView.as_view(), name='teacher_message_recipients'),
    path('teacher/', TeacherNotificationListView.as_view(), name='teacher_notifications_list'),
    path('preferences/', NotificationPreferencesView.as_view(), name='notification_preferences'),
    path('<str:notification_id>/read/', MarkNotificationReadView.as_view(), name='notifications_mark_read'),
    path('read-all/', MarkAllNotificationsReadView.as_view(), name='notifications_mark_all_read'),
]
