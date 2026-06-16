from django.urls import path

from .views import (
    RegisterView, LogoutView, PasswordChangeView, InviteCodeLoginView,
    PasswordResetRequestView, PasswordResetConfirmView,
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='auth_register'),
    path('invite-login/', InviteCodeLoginView.as_view(), name='auth_invite_login'),
    path('logout/', LogoutView.as_view(), name='auth_logout'),
    path('password-change/', PasswordChangeView.as_view(), name='auth_password_change'),
    path('password-reset/request/', PasswordResetRequestView.as_view(), name='auth_password_reset_request'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='auth_password_reset_confirm'),
]
