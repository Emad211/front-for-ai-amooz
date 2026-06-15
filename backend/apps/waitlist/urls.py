from django.urls import path

from .views import (
    AccessRequestApproveView,
    AccessRequestCreateView,
    AccessRequestListView,
    AccessRequestRejectView,
    TeacherRegistrationCompleteView,
)

urlpatterns = [
    # Public intake
    path('requests/', AccessRequestCreateView.as_view(), name='waitlist_request_create'),
    # Approved teacher completes registration via their one-time token
    path('complete/', TeacherRegistrationCompleteView.as_view(), name='waitlist_complete'),

    # Platform-admin review
    path('admin/requests/', AccessRequestListView.as_view(), name='waitlist_admin_list'),
    path('admin/requests/<int:pk>/approve/', AccessRequestApproveView.as_view(), name='waitlist_admin_approve'),
    path('admin/requests/<int:pk>/reject/', AccessRequestRejectView.as_view(), name='waitlist_admin_reject'),
]
