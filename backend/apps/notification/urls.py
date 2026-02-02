from django.urls import path

from .views import (
    AdminNotificationBroadcastView,
    AdminNotificationRecipientsView,
    TeacherNotificationListView,
)

urlpatterns = [
    path('admin/broadcast/', AdminNotificationBroadcastView.as_view(), name='admin_notifications_broadcast'),
    path('admin/recipients/', AdminNotificationRecipientsView.as_view(), name='admin_notifications_recipients'),
    path('teacher/', TeacherNotificationListView.as_view(), name='teacher_notifications_list'),
]
