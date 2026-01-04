from django.urls import path

from .views import RegisterView, LogoutView, PasswordChangeView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='auth_register'),
    path('logout/', LogoutView.as_view(), name='auth_logout'),
    path('password-change/', PasswordChangeView.as_view(), name='auth_password_change'),
]
