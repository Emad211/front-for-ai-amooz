from django.urls import path

from .views import (
    AdminNotificationBroadcastView,
    AdminNotificationRecipientsView,
    TeacherNotificationListView,
    MarkNotificationReadView,
    MarkAllNotificationsReadView,
)

urlpatterns = [
    path('admin/broadcast/', AdminNotificationBroadcastView.as_view(), name='admin_notifications_broadcast'),
    path('admin/recipients/', AdminNotificationRecipientsView.as_view(), name='admin_notifications_recipients'),
    path('teacher/', TeacherNotificationListView.as_view(), name='teacher_notifications_list'),
    path('<str:notification_id>/read/', MarkNotificationReadView.as_view(), name='notifications_mark_read'),
    path('read-all/', MarkAllNotificationsReadView.as_view(), name='notifications_mark_all_read'),
]
